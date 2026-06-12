"""Optional FastAPI conversation memory service for Project 1.

The Streamlit app remains the main UI. This small API gives Project 1 a
lightweight conversation store that future clients can use for follow-up
questions, selected standards, model mode, and retrieved source summaries.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


DATA_DIR = Path("outputs/conversations")
DATA_PATH = DATA_DIR / "conversations.json"

app = FastAPI(
    title="Autonomous Driving Safety Analyst Conversation API",
    version="0.1.0",
    description="Lightweight conversation memory for the Streamlit safety analyst.",
)


class ConversationCreate(BaseModel):
    title: str | None = None
    mode: str = "Standards Q&A"
    selected_standards: list[str] = Field(default_factory=lambda: ["ISO 26262", "ISO 21448", "ISO 8800"])
    model: str = "openai"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationRead(ConversationCreate):
    id: str
    message_count: int = 0
    created_at: datetime
    updated_at: datetime


class ConversationMessageCreate(BaseModel):
    role: str = Field(default="user", pattern="^(user|assistant|system)$")
    content: str
    retrieved_sources: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationMessageRead(ConversationMessageCreate):
    id: str
    conversation_id: str
    created_at: datetime


class ConversationHistory(BaseModel):
    conversation: ConversationRead
    messages: list[ConversationMessageRead]


def _utc_now() -> datetime:
    return datetime.utcnow()


def _load_store() -> dict[str, Any]:
    if not DATA_PATH.exists():
        return {"conversations": {}, "messages": {}}
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def _save_store(store: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(json.dumps(store, indent=2, default=str), encoding="utf-8")


def _conversation_or_404(conversation_id: str, store: dict[str, Any]) -> dict[str, Any]:
    conversation = store["conversations"].get(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


def _conversation_read(conversation: dict[str, Any], message_count: int) -> ConversationRead:
    payload = conversation.copy()
    payload["created_at"] = datetime.fromisoformat(conversation["created_at"])
    payload["updated_at"] = datetime.fromisoformat(conversation["updated_at"])
    return ConversationRead(
        **payload,
        message_count=message_count,
    )


def _message_read(message: dict[str, Any]) -> ConversationMessageRead:
    payload = message.copy()
    payload["created_at"] = datetime.fromisoformat(message["created_at"])
    return ConversationMessageRead(
        **payload,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "conversation_memory"}


@app.post("/conversations", response_model=ConversationRead)
def create_conversation(payload: ConversationCreate) -> ConversationRead:
    store = _load_store()
    now = _utc_now()
    next_id = f"conv-{len(store['conversations']) + 1:04d}"
    conversation = {
        "id": next_id,
        "title": payload.title or f"{payload.mode} conversation",
        "mode": payload.mode,
        "selected_standards": payload.selected_standards,
        "model": payload.model,
        "metadata": payload.metadata,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
    store["conversations"][next_id] = conversation
    store["messages"][next_id] = []
    _save_store(store)
    return _conversation_read(conversation, 0)


@app.get("/conversations/{conversation_id}", response_model=ConversationRead)
def get_conversation(conversation_id: str) -> ConversationRead:
    store = _load_store()
    conversation = _conversation_or_404(conversation_id, store)
    return _conversation_read(conversation, len(store["messages"].get(conversation_id, [])))


@app.post("/conversations/{conversation_id}/messages", response_model=ConversationMessageRead)
def add_conversation_message(conversation_id: str, payload: ConversationMessageCreate) -> ConversationMessageRead:
    store = _load_store()
    conversation = _conversation_or_404(conversation_id, store)
    messages = store["messages"].setdefault(conversation_id, [])
    now = _utc_now()
    message = {
        "id": f"msg-{len(messages) + 1:04d}",
        "conversation_id": conversation_id,
        "role": payload.role,
        "content": payload.content,
        "retrieved_sources": payload.retrieved_sources,
        "metadata": payload.metadata,
        "created_at": now.isoformat(),
    }
    messages.append(message)
    conversation["updated_at"] = now.isoformat()
    _save_store(store)
    return _message_read(message)


@app.get("/conversations/{conversation_id}/history", response_model=ConversationHistory)
def get_conversation_history(conversation_id: str) -> ConversationHistory:
    store = _load_store()
    conversation = _conversation_or_404(conversation_id, store)
    messages = [_message_read(message) for message in store["messages"].get(conversation_id, [])]
    return ConversationHistory(
        conversation=_conversation_read(conversation, len(messages)),
        messages=messages,
    )
