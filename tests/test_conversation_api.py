from fastapi.testclient import TestClient

import conversation_api


def test_conversation_memory_api_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(conversation_api, "DATA_DIR", tmp_path)
    monkeypatch.setattr(conversation_api, "DATA_PATH", tmp_path / "conversations.json")

    with TestClient(conversation_api.app) as client:
        created = client.post(
            "/conversations",
            json={
                "title": "HARA follow-up",
                "mode": "Safety Scenario",
                "selected_standards": ["ISO 26262", "ISO 21448"],
                "model": "gpt-4o",
            },
        )
        assert created.status_code == 200
        conversation = created.json()
        assert conversation["message_count"] == 0

        message = client.post(
            f"/conversations/{conversation['id']}/messages",
            json={
                "role": "user",
                "content": "What HARA evidence is needed for night pedestrian AEB?",
                "retrieved_sources": [{"standard": "ISO 26262", "part": "Part 3"}],
            },
        )
        assert message.status_code == 200

        history = client.get(f"/conversations/{conversation['id']}/history")
        assert history.status_code == 200
        body = history.json()
        assert body["conversation"]["message_count"] == 1
        assert body["messages"][0]["retrieved_sources"][0]["standard"] == "ISO 26262"
