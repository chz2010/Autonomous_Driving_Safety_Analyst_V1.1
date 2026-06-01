"""Streamlit app for Autonomous Driving Safety Analyst."""

from __future__ import annotations

import base64
import logging
import tempfile
import uuid
from pathlib import Path
from textwrap import shorten

import streamlit as st

from agent.agent import (
    _review_lifecycle_answer,
    _synthesize_answer_audio,
    build_agent,
    run_finetuned_lora_answer,
    run_open_source_draft_answer,
)
from config import cfg
from ingestion.video_ingestion import get_vector_store as get_video_store


logger = logging.getLogger(__name__)


st.set_page_config(
    page_title="Autonomous Driving Safety Analyst",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)


APP_DIR = Path(__file__).resolve().parent
BACKGROUND_IMAGE = APP_DIR / "assets" / "autonomous-car-headlights.png"
USER_AVATAR_IMAGE = APP_DIR / "assets" / "avatar_q.svg"
ASSISTANT_AVATAR_IMAGE = APP_DIR / "assets" / "avatar_a.svg"


APP_CSS_TEMPLATE = """
<style>
:root {
  --bg: #080b10;
  --panel: rgba(18, 24, 35, 0.78);
  --panel-strong: rgba(22, 31, 46, 0.94);
  --line: rgba(255, 255, 255, 0.34);
  --line-strong: rgba(255, 255, 255, 0.68);
  --glow: rgba(255, 255, 255, 0.18);
  --cyan: #ffffff;
  --green: #f1f6ff;
  --text: #eaf3ff;
  --muted: #91a4bd;
}

html, body, [class*="css"], .stApp {
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Helvetica Neue", Helvetica, Arial, sans-serif;
}

@keyframes scanSweep {
  0% { transform: translateX(-120%); opacity: 0; }
  12% { opacity: 0.85; }
  52% { opacity: 0.55; }
  100% { transform: translateX(120%); opacity: 0; }
}

@keyframes borderPulse {
  0%, 100% { border-color: var(--line); box-shadow: 0 0 18px rgba(255, 255, 255, 0.06), inset 0 0 18px rgba(255, 255, 255, 0.025); }
  50% { border-color: var(--line-strong); box-shadow: 0 0 34px var(--glow), inset 0 0 24px rgba(255, 255, 255, 0.045); }
}

@keyframes signalRise {
  0%, 100% { transform: scaleY(0.35); opacity: 0.45; }
  50% { transform: scaleY(1); opacity: 1; }
}

@keyframes driftIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes headlightBreath {
  0%, 100% {
    opacity: 0.72;
    filter: blur(1.8px);
    transform: translateX(-50%) rotate(-4deg) scaleX(1.08) scaleY(0.82);
  }
  50% {
    opacity: 0.96;
    filter: blur(2.6px);
    transform: translateX(-50%) rotate(-5.5deg) scaleX(1.24) scaleY(0.76);
  }
}

@keyframes headlightSlashPulse {
  0%, 100% {
    opacity: 0.78;
    filter: drop-shadow(0 0 10px rgba(255, 255, 255, 0.80)) drop-shadow(0 0 26px rgba(255, 255, 255, 0.28));
    transform: translateX(-50%) scaleX(1);
  }
  50% {
    opacity: 1;
    filter: drop-shadow(0 0 18px rgba(255, 255, 255, 1)) drop-shadow(0 0 46px rgba(255, 255, 255, 0.48));
    transform: translateX(-50%) scaleX(1.05);
  }
}

.stApp {
  background:
    linear-gradient(180deg, rgba(0, 0, 0, 0.66) 0%, rgba(0, 0, 0, 0.86) 44%, rgba(0, 0, 0, 0.98) 100%),
    url("__APP_BACKGROUND_IMAGE__"),
    #000000;
  background-size: 100% 100%, cover, 100% 100%;
  background-attachment: fixed, fixed, fixed;
  background-repeat: no-repeat, no-repeat, no-repeat;
  background-position: center top, center 12vh, 0 0;
  color: var(--text);
}

.stApp::before {
  content: "";
  position: fixed;
  left: 50%;
  top: 34.5vh;
  width: min(1040px, 56vw);
  height: 128px;
  pointer-events: none;
  background:
    linear-gradient(14deg, transparent 0 18%, rgba(255, 255, 255, 0.98) 20%, rgba(255, 255, 255, 1) 22%, rgba(255, 255, 255, 0.50) 25%, transparent 31%) left 9% top 56% / 33% 46% no-repeat,
    linear-gradient(166deg, transparent 0 18%, rgba(255, 255, 255, 0.98) 20%, rgba(255, 255, 255, 1) 22%, rgba(255, 255, 255, 0.50) 25%, transparent 31%) right 9% top 55% / 33% 46% no-repeat,
    linear-gradient(96deg, transparent 0 23%, rgba(255, 255, 255, 0.96) 26%, rgba(255, 255, 255, 1) 28%, rgba(255, 255, 255, 0.34) 32%, transparent 39%) left 20% top 38% / 38% 50% no-repeat,
    linear-gradient(84deg, transparent 0 23%, rgba(255, 255, 255, 0.96) 26%, rgba(255, 255, 255, 1) 28%, rgba(255, 255, 255, 0.34) 32%, transparent 39%) right 20% top 36% / 38% 50% no-repeat,
    linear-gradient(112deg, transparent 0 19%, rgba(255, 255, 255, 0.78) 22%, rgba(255, 255, 255, 0.96) 24%, transparent 30%) left 28% top 18% / 22% 44% no-repeat,
    linear-gradient(68deg, transparent 0 19%, rgba(255, 255, 255, 0.78) 22%, rgba(255, 255, 255, 0.96) 24%, transparent 30%) right 28% top 16% / 22% 44% no-repeat,
    radial-gradient(ellipse at 22% 58%, rgba(255, 255, 255, 0.24), transparent 34%),
    radial-gradient(ellipse at 78% 57%, rgba(255, 255, 255, 0.24), transparent 34%);
  mix-blend-mode: screen;
  animation: headlightSlashPulse 3.4s ease-in-out infinite;
  z-index: 0;
}

.stApp::after {
  content: "";
  position: fixed;
  left: 0;
  right: 0;
  top: 34.7vh;
  height: 118px;
  pointer-events: none;
  background:
    linear-gradient(7deg, transparent 0 44%, rgba(255, 255, 255, 0.08) 49%, rgba(255, 255, 255, 0.24) 52%, rgba(255, 255, 255, 0.08) 55%, transparent 61%) left center / 52vw 78% no-repeat,
    linear-gradient(173deg, transparent 0 44%, rgba(255, 255, 255, 0.08) 49%, rgba(255, 255, 255, 0.24) 52%, rgba(255, 255, 255, 0.08) 55%, transparent 61%) right center / 52vw 78% no-repeat,
    radial-gradient(ellipse at 0% 52%, rgba(255, 255, 255, 0.11), transparent 26%),
    radial-gradient(ellipse at 100% 52%, rgba(255, 255, 255, 0.11), transparent 26%);
  mix-blend-mode: screen;
  opacity: 0.76;
  z-index: 0;
}

.block-container {
  position: relative;
  z-index: 1;
}

[data-testid="stHeader"] {
  background: rgba(8, 11, 16, 0.72);
  backdrop-filter: blur(16px);
}

[data-testid="stSidebar"] {
  position: relative;
  background:
    radial-gradient(ellipse at 100% 18%, rgba(255, 255, 255, 0.13), transparent 34%),
    radial-gradient(ellipse at 100% 72%, rgba(255, 255, 255, 0.10), transparent 38%),
    linear-gradient(180deg, rgba(8, 13, 21, 0.99), rgba(4, 7, 12, 0.98));
  border-right: 1px solid rgba(255, 255, 255, 0.54);
  box-shadow:
    inset -1px 0 0 rgba(255, 255, 255, 0.24),
    14px 0 46px rgba(255, 255, 255, 0.075);
}

[data-testid="stSidebar"]::after {
  content: "";
  position: absolute;
  inset: 0 0 0 auto;
  width: 1px;
  pointer-events: none;
  background: linear-gradient(
    180deg,
    transparent 0%,
    rgba(255, 255, 255, 0.48) 18%,
    rgba(255, 255, 255, 0.92) 48%,
    rgba(255, 255, 255, 0.36) 78%,
    transparent 100%
  );
  box-shadow:
    0 0 18px rgba(255, 255, 255, 0.55),
    0 0 42px rgba(255, 255, 255, 0.22);
}

[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] strong {
  color: #ffffff;
  text-shadow: 0 0 18px rgba(255, 255, 255, 0.15);
}

[data-testid="stSidebar"] label,
[data-testid="stSidebar"] p {
  color: rgba(234, 243, 255, 0.92);
}

[data-testid="stSidebar"] hr {
  border-color: rgba(255, 255, 255, 0.24);
  box-shadow: 0 0 16px rgba(255, 255, 255, 0.08);
}

.hero {
  position: relative;
  overflow: visible;
  z-index: 5;
  border: 1px solid var(--line);
  background:
    linear-gradient(135deg, rgba(20, 30, 45, 0.82), rgba(10, 15, 23, 0.62)),
    linear-gradient(90deg, rgba(255, 255, 255, 0.09), transparent 68%);
  backdrop-filter: blur(12px);
  border-radius: 8px;
  padding: 22px 24px;
  box-shadow: 0 20px 70px rgba(0, 0, 0, 0.32), 0 0 24px rgba(255, 255, 255, 0.08);
  animation: driftIn 420ms ease-out both, borderPulse 5s ease-in-out infinite;
  transition: padding-bottom 180ms ease, min-height 180ms ease;
}

.hero:has(.telemetry-help[open]) {
  min-height: 365px;
  padding-bottom: 168px;
}

.hero::before {
  content: "";
  position: absolute;
  top: 0;
  bottom: 0;
  width: 55%;
  pointer-events: none;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.22), transparent);
  animation: scanSweep 6s ease-in-out infinite;
}

.hero::after {
  content: "";
  position: absolute;
  inset: auto 0 0 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--cyan), var(--green), transparent);
}

.hero h1 {
  position: relative;
  font-size: 2.05rem;
  line-height: 1.12;
  margin: 0 0 8px 0;
  letter-spacing: 0;
}

.hero p {
  position: relative;
  color: var(--muted);
  margin: 0;
  max-width: 980px;
}

.telemetry-strip {
  position: relative;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 16px;
}

.rag-status {
  position: absolute;
  top: 18px;
  right: 18px;
  z-index: 2;
}

.telemetry-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid var(--line);
  background: rgba(5, 10, 16, 0.55);
  border-radius: 8px;
  padding: 8px 10px;
  color: var(--muted);
  font-size: 0.82rem;
  box-shadow: 0 0 16px rgba(255, 255, 255, 0.055), inset 0 0 14px rgba(255, 255, 255, 0.025);
}

.telemetry-help {
  position: relative;
}

.telemetry-help summary {
  list-style: none;
  cursor: pointer;
}

.telemetry-help summary::-webkit-details-marker {
  display: none;
}

.telemetry-help[open] summary {
  border-color: var(--line-strong);
  box-shadow: 0 0 24px rgba(255, 255, 255, 0.14), inset 0 0 16px rgba(255, 255, 255, 0.04);
}

.telemetry-explain {
  position: absolute;
  z-index: 50;
  top: calc(100% + 8px);
  left: 0;
  width: min(560px, 82vw);
  border: 1px solid var(--line-strong);
  border-radius: 8px;
  background: rgba(2, 4, 8, 0.98);
  color: #dfe7f5;
  padding: 14px 16px;
  box-shadow: 0 22px 54px rgba(0, 0, 0, 0.72), 0 0 34px rgba(255, 255, 255, 0.16);
  backdrop-filter: blur(14px);
  font-size: 0.9rem;
  line-height: 1.55;
  max-height: 138px;
  overflow: auto;
}

.telemetry-explain strong {
  color: #ffffff;
}

.signal {
  display: inline-grid;
  grid-template-columns: repeat(4, 3px);
  gap: 2px;
  height: 16px;
  align-items: end;
}

.signal span {
  display: block;
  width: 3px;
  height: 16px;
  background: linear-gradient(180deg, var(--cyan), var(--green));
  transform-origin: bottom;
  animation: signalRise 1.35s ease-in-out infinite;
}

.signal span:nth-child(2) { animation-delay: 0.12s; }
.signal span:nth-child(3) { animation-delay: 0.24s; }
.signal span:nth-child(4) { animation-delay: 0.36s; }

.status-grid {
  display: none;
  position: relative;
  z-index: 1;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin: 14px 0 18px;
}

.status-tile {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--line);
  background: rgba(16, 23, 34, 0.72);
  border-radius: 8px;
  padding: 12px 14px;
  min-height: 76px;
  box-shadow: 0 0 18px rgba(255, 255, 255, 0.06), inset 0 0 18px rgba(255, 255, 255, 0.025);
  transition: transform 160ms ease, border-color 160ms ease, background 160ms ease, box-shadow 160ms ease;
}

.status-tile::after {
  content: "";
  position: absolute;
  inset: auto 12px 9px 12px;
  height: 2px;
  background: linear-gradient(90deg, #ffffff, transparent);
  opacity: 0.72;
}

.status-tile:hover {
  transform: translateY(-2px);
  border-color: var(--line-strong);
  background: rgba(20, 31, 46, 0.86);
  box-shadow: 0 0 30px var(--glow), inset 0 0 20px rgba(255, 255, 255, 0.04);
}

.status-tile .label {
  color: var(--muted);
  font-size: 0.78rem;
  text-transform: uppercase;
}

.status-tile .value {
  color: var(--text);
  font-size: 1rem;
  margin-top: 5px;
}

.mode-note {
  border-left: 3px solid #ffffff;
  border-top: 1px solid rgba(255, 255, 255, 0.16);
  border-bottom: 1px solid rgba(255, 255, 255, 0.12);
  background:
    linear-gradient(100deg, rgba(255, 255, 255, 0.18), rgba(255, 255, 255, 0.065) 58%, rgba(255, 255, 255, 0.025));
  padding: 10px 12px;
  color: rgba(222, 232, 246, 0.84);
  margin: 8px 0 14px;
  box-shadow:
    0 0 22px rgba(255, 255, 255, 0.08),
    inset 0 0 20px rgba(255, 255, 255, 0.045);
}

.model-unavailable {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  border: 1px dashed rgba(255, 255, 255, 0.24);
  background: rgba(255, 255, 255, 0.035);
  border-radius: 8px;
  padding: 10px 12px;
  color: rgba(205, 216, 231, 0.66);
  margin: 8px 0 8px;
  cursor: not-allowed;
}

.model-unavailable .badge {
  border: 1px solid rgba(255, 255, 255, 0.22);
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 0.72rem;
  color: rgba(230, 237, 248, 0.68);
  background: rgba(255, 255, 255, 0.04);
  white-space: nowrap;
}

.stButton button {
  border-radius: 8px;
  border: 1px solid var(--line);
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.16), rgba(255, 255, 255, 0.06));
  box-shadow: 0 0 16px rgba(255, 255, 255, 0.055), inset 0 0 14px rgba(255, 255, 255, 0.025);
  transition: transform 140ms ease, border-color 140ms ease, box-shadow 140ms ease;
}

.stButton button:hover {
  transform: translateY(-1px);
  border-color: var(--line-strong);
  box-shadow: 0 0 26px var(--glow), inset 0 0 18px rgba(255, 255, 255, 0.04);
}

[data-testid="stSidebar"] .stButton button {
  border-color: rgba(255, 255, 255, 0.46);
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.18), rgba(255, 255, 255, 0.07));
  box-shadow:
    0 0 18px rgba(255, 255, 255, 0.07),
    inset 0 0 16px rgba(255, 255, 255, 0.03);
}

[data-testid="stSidebar"] .stButton button:hover {
  border-color: rgba(255, 255, 255, 0.76);
  box-shadow:
    0 0 28px rgba(255, 255, 255, 0.20),
    inset 0 0 20px rgba(255, 255, 255, 0.055);
}

[data-testid="stSidebar"] [data-testid="stCheckbox"],
[data-testid="stSidebar"] [data-testid="stRadio"] {
  text-shadow: 0 0 14px rgba(255, 255, 255, 0.08);
}

[data-testid="stSidebar"] input[type="radio"],
[data-testid="stSidebar"] input[type="checkbox"] {
  accent-color: #ffffff !important;
}

[data-testid="stSidebar"] label:has(input[type="radio"]:checked) > div:first-child,
[data-testid="stSidebar"] label:has(input[type="checkbox"]:checked) > div:first-child {
  border-color: #ffffff !important;
  background: #ffffff !important;
  box-shadow:
    0 0 0 1px rgba(255, 255, 255, 0.34),
    0 0 18px rgba(255, 255, 255, 0.42) !important;
}

[data-testid="stSidebar"] label:has(input[type="radio"]:checked) > div:first-child::before,
[data-testid="stSidebar"] label:has(input[type="radio"]:checked) > div:first-child::after {
  background: #05070b !important;
}

[data-testid="stSidebar"] label:has(input[type="checkbox"]:checked) > div:first-child svg {
  fill: #05070b !important;
  stroke: #05070b !important;
}

[data-testid="stSidebar"] [data-testid="stCheckbox"] label:has(input[type="checkbox"]:checked) > span:first-child,
[data-testid="stSidebar"] [data-testid="stCheckbox"] label:has(input[type="checkbox"]:checked) > div:first-child,
[data-testid="stSidebar"] [data-testid="stCheckbox"] [data-baseweb="checkbox"]:has(input[type="checkbox"]:checked) > span:first-child,
[data-testid="stSidebar"] [data-testid="stCheckbox"] [data-baseweb="checkbox"]:has(input[type="checkbox"]:checked) > div:first-child {
  border-color: #ffffff !important;
  background: #ffffff !important;
  background-color: #ffffff !important;
  box-shadow:
    0 0 0 1px rgba(255, 255, 255, 0.34),
    0 0 18px rgba(255, 255, 255, 0.42) !important;
}

[data-testid="stSidebar"] [data-testid="stCheckbox"] label:has(input[type="checkbox"]:checked) > span:first-child svg,
[data-testid="stSidebar"] [data-testid="stCheckbox"] label:has(input[type="checkbox"]:checked) > div:first-child svg,
[data-testid="stSidebar"] [data-testid="stCheckbox"] [data-baseweb="checkbox"]:has(input[type="checkbox"]:checked) > span:first-child svg,
[data-testid="stSidebar"] [data-testid="stCheckbox"] [data-baseweb="checkbox"]:has(input[type="checkbox"]:checked) > div:first-child svg {
  fill: #05070b !important;
  stroke: #05070b !important;
}

[data-testid="stSidebar"] [data-testid="stToggle"] label:has(input[type="checkbox"]:checked) > div:first-child {
  background: #ffffff !important;
  border-color: #ffffff !important;
  box-shadow: 0 0 18px rgba(255, 255, 255, 0.42) !important;
}

[data-testid="stSidebar"] [data-testid="stToggle"] label:has(input[type="checkbox"]:checked) > div:first-child::before,
[data-testid="stSidebar"] [data-testid="stToggle"] label:has(input[type="checkbox"]:checked) > div:first-child::after {
  background: #05070b !important;
}

[data-testid="stChatMessage"] {
  border: 1px solid rgba(255, 255, 255, 0.22);
  border-radius: 8px;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.08), rgba(8, 12, 20, 0.82) 38%, rgba(0, 0, 0, 0.72)),
    rgba(6, 9, 15, 0.84);
  box-shadow:
    0 0 24px rgba(255, 255, 255, 0.08),
    inset 0 0 22px rgba(255, 255, 255, 0.035);
  animation: driftIn 220ms ease-out both;
  backdrop-filter: blur(8px);
}

[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"],
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] p,
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] li,
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] td,
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] th {
  color: rgba(255, 255, 255, 0.96) !important;
}

[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] h1,
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] h2,
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] h3,
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] h4,
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] strong {
  color: #ffffff !important;
  text-shadow: 0 0 14px rgba(255, 255, 255, 0.18);
}

[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] a {
  color: #ffffff !important;
  text-decoration-color: rgba(255, 255, 255, 0.55);
}

[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] blockquote {
  border-left-color: rgba(255, 255, 255, 0.72);
  color: rgba(255, 255, 255, 0.9) !important;
  background: rgba(255, 255, 255, 0.045);
  border-radius: 0 8px 8px 0;
}

[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] table {
  color: rgba(255, 255, 255, 0.96) !important;
  border-color: rgba(255, 255, 255, 0.28) !important;
}

textarea, input {
  border-radius: 8px !important;
}

[data-testid="stChatInput"] {
  left: min(26rem, 24vw);
  right: 26px;
  padding: 10px 0 16px;
  background: transparent !important;
}

[data-testid="stBottom"],
[data-testid="stBottomBlockContainer"],
[data-testid="stChatFloatingInputContainer"],
div:has(> [data-testid="stChatInput"]) {
  background: #000000 !important;
  border-top: 0 !important;
  box-shadow: none !important;
}

[data-testid="stChatInput"] > div {
  border: 1px solid rgba(255, 255, 255, 0.46) !important;
  border-radius: 8px !important;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.06), rgba(11, 15, 23, 0.96) 42%, rgba(0, 0, 0, 0.98)) !important;
  box-shadow:
    0 0 14px rgba(255, 255, 255, 0.08),
    inset 0 0 24px rgba(255, 255, 255, 0.045) !important;
}

[data-testid="stChatInput"] textarea {
  color: #ffffff !important;
  caret-color: #ffffff !important;
  background: transparent !important;
}

[data-testid="stChatInput"] textarea::placeholder {
  color: rgba(234, 243, 255, 0.58) !important;
}

[data-testid="stChatInput"] button {
  color: #05070b !important;
  background: #ffffff !important;
  border-radius: 999px !important;
  box-shadow: 0 0 18px rgba(255, 255, 255, 0.36) !important;
}

[data-testid="stChatInput"] button svg {
  fill: #05070b !important;
}

.voice-dock {
  height: 0 !important;
}

[data-testid="stPopover"] {
  display: flex !important;
  justify-content: flex-end !important;
  margin: 0 0 8px 0 !important;
  position: relative !important;
  z-index: 40 !important;
}

[data-testid="stPopover"] > div {
  width: auto !important;
}

[data-testid="stPopover"] button {
  min-width: 54px !important;
  width: 54px !important;
  height: 38px !important;
  min-height: 38px !important;
  padding: 0 !important;
  border-radius: 999px !important;
  border: 1px solid rgba(255, 255, 255, 0.44) !important;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.18), rgba(6, 10, 18, 0.96)) !important;
  color: #ffffff !important;
  box-shadow:
    0 0 18px rgba(255, 255, 255, 0.18),
    inset 0 0 14px rgba(255, 255, 255, 0.05) !important;
  font-size: 0 !important;
  font-weight: 800 !important;
}

[data-testid="stPopover"] button::before {
  content: "Mic";
  font-size: 12px;
  letter-spacing: 0;
  line-height: 1;
}

[data-testid="stPopover"] button p,
[data-testid="stPopover"] button span {
  display: none !important;
}

[data-testid="stPopover"] button:hover {
  border-color: rgba(255, 255, 255, 0.74) !important;
  box-shadow:
    0 0 26px rgba(255, 255, 255, 0.25),
    inset 0 0 16px rgba(255, 255, 255, 0.07) !important;
}

[data-testid="stExpander"] {
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: 0 0 18px rgba(255, 255, 255, 0.055), inset 0 0 16px rgba(255, 255, 255, 0.025);
}

[data-testid="stExpander"] summary {
  color: var(--text);
}

.scenario-intake-shell {
  margin-top: 10px;
}

.scenario-intake-shell + div .stButton button {
  justify-content: space-between;
  min-height: 48px;
  font-weight: 650;
  text-align: left;
  color: var(--text);
  border-color: rgba(255, 255, 255, 0.58);
  background: rgba(0, 0, 0, 0.58);
  box-shadow:
    0 0 18px rgba(255, 255, 255, 0.085),
    inset 0 0 16px rgba(255, 255, 255, 0.02);
}

[data-testid="stVerticalBlockBorderWrapper"] {
  border-color: rgba(255, 255, 255, 0.42);
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.52);
  box-shadow:
    0 0 28px rgba(255, 255, 255, 0.09),
    inset 0 0 24px rgba(255, 255, 255, 0.025);
}

@media (max-width: 900px) {
  .status-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
"""


def image_data_uri(path: Path) -> str:
    """Return a data URI for CSS background images."""
    if not path.exists():
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def app_css() -> str:
    """Inject the generated autonomous-car image into the app stylesheet."""
    return APP_CSS_TEMPLATE.replace("__APP_BACKGROUND_IMAGE__", image_data_uri(BACKGROUND_IMAGE))


MODE_HELP = {
    "Scenario Analysis": (
        "Analyze a described incident, near miss, edge case, or unsafe behavior. "
        "Blank fields are allowed; the agent will state assumptions."
    ),
    "Item Safety Case": (
        "Generate an engineering safety case or lifecycle for an item/system "
        "using ISO 26262, ISO 21448 (SOTIF), and ISO 8800."
    ),
    "Standards Q&A": (
        "Ask targeted questions about ISO 26262, ISO 21448 (SOTIF), ISO 8800, NCAP, IIHS, "
        "HARA, safety goals, or safety evidence."
    ),
    "Dataset / AI Safety Review": (
        "Review dataset coverage, AI model robustness, OOD behavior, release gates, "
        "monitoring, and ISO 8800 evidence."
    ),
}


SAMPLE_PROMPTS = {
    "Scenario Analysis": [
        "A robotaxi failed to brake for a pedestrian at night. The pedestrian was partly occluded by a parked vehicle. Analyze using ISO 26262, ISO 21448 (SOTIF), and ISO 8800.",
        "An L2 lane keeping system drifted toward the lane boundary in heavy rain with faded markings. Give a standards-based safety analysis.",
    ],
    "Item Safety Case": [
        "Build a safety case for a camera-based traffic light recognition system used by an automated vehicle.",
        "Give me the whole safety lifecycle for developing a radar perception system for ACC according to ISO 26262, ISO 21448 (SOTIF), and ISO 8800.",
    ],
    "Standards Q&A": [
        "Compare ISO 26262, ISO 21448 (SOTIF), and ISO 8800 for an AI-based perception system.",
        "How should HARA evaluate Severity, Exposure, and Controllability for an AEB pedestrian function?",
    ],
    "Dataset / AI Safety Review": [
        "What dataset gaps could make an AI perception model unsafe for detecting pedestrians and cyclists? Relate the answer to ISO 8800 and ISO 21448 (SOTIF).",
        "A new model improves average accuracy but regresses occluded cyclists at night. Should it be released?",
    ],
}


STANDARD_OPTIONS = {
    "ISO 26262": "ISO 26262",
    "ISO 21448 (SOTIF)": "ISO 21448 (SOTIF)",
    "ISO 8800": "ISO 8800",
}

MODEL_OPTIONS = {
    "OpenAI - advanced analysis": (
        "Best for detailed standards reasoning, HARA, lifecycle analysis, and safety-case generation."
    ),
    "Local Qwen - before fine-tuning": (
        "Base Ollama Qwen model with local standards retrieval. Good for showing the pre-training baseline."
    ),
    "Local Qwen - after LoRA fine-tuning": (
        "Domain-adapted Qwen LoRA model. Requires a running LoRA inference endpoint."
    ),
}

AVAILABLE_MODEL_OPTIONS = [
    "OpenAI - advanced analysis",
    "Local Qwen - before fine-tuning",
]
LORA_MODEL_LABEL = "Local Qwen - after LoRA fine-tuning"
LORA_EXPERIMENT_TOOLTIP = (
    "Currently unavailable for selection in the app. This path was used as a "
    "LoRA fine-tuning experiment and is shown for portfolio completeness."
)


def _new_chat_name(existing_count: int) -> str:
    """Generate a human-readable default chat name."""
    return f"Topic {existing_count + 1}"


def _new_chat_state(name: str) -> dict:
    """Create one isolated conversation state."""
    return {
        "name": name,
        "messages": [],
        "pending_prompt": "",
        "scenario_intake_open": False,
        "transcribed_prompt": "",
        "mode": "Scenario Analysis",
        "voice_enabled": False,
        "selected_standards": list(STANDARD_OPTIONS),
        "reasoning_model": "OpenAI - advanced analysis",
    }


def ensure_chat_sessions() -> None:
    """Initialize multi-chat state once per Streamlit session."""
    if "chats" in st.session_state and "active_chat_id" in st.session_state:
        if st.session_state.active_chat_id in st.session_state.chats:
            return

    chat_id = f"chat_{uuid.uuid4().hex[:8]}"
    st.session_state.chats = {chat_id: _new_chat_state("Topic 1")}
    st.session_state.active_chat_id = chat_id


def active_chat() -> dict:
    """Return the active chat state object."""
    ensure_chat_sessions()
    return st.session_state.chats[st.session_state.active_chat_id]


def standards_text(selected_standards: list[str]) -> str:
    """Return a readable standards scope."""
    return ", ".join(selected_standards)


def scoped_prompt(prompt: str, selected_standards: list[str]) -> str:
    """Append the user's selected standards as an explicit evaluation scope."""
    selected = standards_text(selected_standards)
    return (
        f"{prompt.strip()}\n\n"
        f"User-selected evaluation standards: {selected}.\n"
        "Evaluate the request only against the selected standard(s). If another "
        "standard is clearly relevant but not selected, mention it briefly as "
        "outside the selected scope instead of using it as a main evaluation lens."
    )


def render_shell() -> None:
    """Render the static app chrome."""
    st.markdown(app_css(), unsafe_allow_html=True)
    st.markdown(
        """
        <div class="hero">
          <h1>Autonomous Driving Safety Analyst</h1>
          <p>
            Technical RAG assistant for ISO 26262, ISO 21448 (SOTIF), ISO 8800, NCAP/IIHS,
            HARA, AI safety evidence, scenario analysis, and item safety cases.
          </p>
          <div class="rag-status">
            <div class="telemetry-pill"><span class="signal"><span></span><span></span><span></span><span></span></span>RAG signal active</div>
          </div>
          <div class="telemetry-strip">
            <details class="telemetry-help" name="hero-telemetry">
              <summary class="telemetry-pill">ISO 26262 / ISO 21448 (SOTIF) / ISO 8800</summary>
              <div class="telemetry-explain">
                <strong>ISO 26262</strong> addresses functional safety of road-vehicle E/E systems and malfunctions.
                <br><strong>ISO 21448 (SOTIF)</strong> addresses unsafe behavior from intended-function limitations, triggering conditions, ODD gaps, and foreseeable misuse.
                <br><strong>ISO 8800</strong> addresses safety of AI in road vehicles, including data quality, model robustness, validation, monitoring, and change control.
              </div>
            </details>
            <details class="telemetry-help" name="hero-telemetry">
              <summary class="telemetry-pill">Function-level safety reasoning</summary>
              <div class="telemetry-explain">
                The agent decomposes an item into its functions, then analyzes each function for ISO 26262 malfunction risk, ISO 21448 (SOTIF) performance limitations, ISO 8800 AI/data/model concerns, HARA impact, verification evidence, and engineering improvements.
              </div>
            </details>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


@st.cache_resource(show_spinner=False)
def get_agent():
    """Cache the LangChain agent for the Streamlit session."""
    return build_agent()


def make_scenario_prompt(fields: dict[str, str], selected_standards: list[str]) -> str:
    """Create a structured prompt from optional scenario fields."""
    lines = [
        f"Analyze this autonomous-driving/ADAS scenario according to: {standards_text(selected_standards)}.",
        "Blank or unknown fields are intentionally allowed. State assumptions before rating risk.",
        "",
    ]
    for label, value in fields.items():
        lines.append(f"{label}: {value.strip() if value and value.strip() else 'unknown'}")
    lines.extend(
        [
            "",
            "Please provide: assumptions used, failure classification, function-level analysis, HARA S/E/C with rationale where applicable, selected-standard interpretation, recommended engineering actions, V&V/release criteria, and evidence limitations.",
        ]
    )
    return "\n".join(lines)


def run_agent(question: str, reasoning_model: str) -> tuple[str, list[Path]]:
    """Invoke the agent and optionally synthesize answer audio."""
    if reasoning_model == "Local Qwen - before fine-tuning":
        answer = run_open_source_draft_answer(question)
    elif reasoning_model == "Local Qwen - after LoRA fine-tuning":
        answer = run_finetuned_lora_answer(question)
    else:
        agent = get_agent()
        result = agent.invoke({"input": question})
        answer = _review_lifecycle_answer(question, result["output"])
    audio_paths = _synthesize_answer_audio(answer, autoplay=False)
    return answer, audio_paths


def format_video_timestamp(seconds: float | int | str) -> str:
    """Format a video timestamp as HH:MM:SS or MM:SS."""
    total = int(float(seconds or 0))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def video_link_at_timestamp(url: str, seconds: int) -> str:
    """Create a YouTube link that opens near the retrieved transcript timestamp."""
    if not url:
        return ""
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}t={seconds}s"


def should_show_video_evidence(prompt: str, reasoning_model: str) -> bool:
    """Show video playback only for the OpenAI/full-RAG path when useful."""
    if reasoning_model != "OpenAI - advanced analysis":
        return False
    text = prompt.lower()
    video_terms = (
        "video",
        "transcript",
        "timestamp",
        "evidence",
        "failure",
        "edge case",
        "unsafe",
        "near miss",
        "perception",
    )
    return any(term in text for term in video_terms)


def retrieve_video_evidence(prompt: str, limit: int = 3) -> list[dict[str, str | int]]:
    """Retrieve playable video evidence metadata from the video vector DB."""
    try:
        store = get_video_store()
        docs = store.similarity_search(prompt, k=limit)
    except Exception:
        logger.exception("Video evidence retrieval failed")
        return []

    evidence: list[dict[str, str | int]] = []
    seen: set[tuple[str, int]] = set()
    for doc in docs:
        meta = doc.metadata
        url = str(meta.get("url") or "")
        timestamp = int(float(meta.get("timestamp_start") or 0))
        key = (url, timestamp)
        if not url or key in seen:
            continue
        seen.add(key)
        evidence.append(
            {
                "title": str(meta.get("title") or "Untitled video"),
                "channel": str(meta.get("channel") or "Unknown channel"),
                "url": url,
                "timestamp": timestamp,
                "timestamp_label": format_video_timestamp(timestamp),
                "link": video_link_at_timestamp(url, timestamp),
                "snippet": shorten(doc.page_content.strip(), width=420, placeholder="..."),
            }
        )
    return evidence


def render_video_evidence_player(video_evidence: list[dict[str, str | int]]) -> None:
    """Render retrieved video evidence with timestamp playback."""
    if not video_evidence:
        return

    with st.expander("Video evidence playback", expanded=False):
        for index, item in enumerate(video_evidence, start=1):
            title = item.get("title", "Untitled video")
            channel = item.get("channel", "Unknown channel")
            timestamp = int(item.get("timestamp", 0))
            timestamp_label = item.get("timestamp_label", "00:00")
            link = item.get("link", "")
            url = item.get("url", "")

            st.markdown(f"**{index}. {title}**")
            st.caption(f"{channel} · timestamp {timestamp_label}")
            if url:
                st.video(str(url), start_time=timestamp)
            if link:
                st.link_button("Open at timestamp", str(link))
            snippet = str(item.get("snippet", "")).strip()
            if snippet:
                st.markdown(f"> {snippet}")


@st.cache_resource(show_spinner=False)
def get_whisper_model(model_name: str):
    """Load the local Whisper model for speech-to-text input."""
    import whisper

    return whisper.load_model(model_name)


def transcribe_audio_file(audio_bytes: bytes, suffix: str) -> str:
    """Transcribe an uploaded/recorded audio file using local Whisper."""
    suffix = suffix if suffix.startswith(".") else f".{suffix}"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(audio_bytes)
        temp_path = Path(temp_file.name)
    try:
        model = get_whisper_model(cfg.STT_MODEL)
        options = {"fp16": False}
        if cfg.STT_LANGUAGE.strip():
            options["language"] = cfg.STT_LANGUAGE.strip()
        result = model.transcribe(str(temp_path), **options)
        return str(result.get("text", "")).strip()
    finally:
        temp_path.unlink(missing_ok=True)


def sidebar_controls() -> tuple[str, bool, list[str], str]:
    """Render sidebar controls."""
    ensure_chat_sessions()
    chat_ids = list(st.session_state.chats.keys())
    selected_chat_id = st.session_state.active_chat_id
    chat = active_chat()

    with st.sidebar:
        st.subheader("Conversations")
        chat_labels = {cid: st.session_state.chats[cid]["name"] for cid in chat_ids}
        selected_chat_id = st.selectbox(
            "Choose conversation",
            chat_ids,
            index=chat_ids.index(selected_chat_id),
            format_func=lambda cid: chat_labels.get(cid, cid),
            label_visibility="collapsed",
        )
        if selected_chat_id != st.session_state.active_chat_id:
            st.session_state.active_chat_id = selected_chat_id
            st.rerun()

        col_new, col_del = st.columns(2)
        with col_new:
            if st.button("New chat", use_container_width=True):
                new_id = f"chat_{uuid.uuid4().hex[:8]}"
                st.session_state.chats[new_id] = _new_chat_state(
                    _new_chat_name(len(st.session_state.chats))
                )
                st.session_state.active_chat_id = new_id
                st.rerun()
        with col_del:
            if st.button(
                "Delete chat",
                use_container_width=True,
                disabled=len(st.session_state.chats) == 1,
            ):
                current_id = st.session_state.active_chat_id
                if len(st.session_state.chats) > 1:
                    del st.session_state.chats[current_id]
                    st.session_state.active_chat_id = next(iter(st.session_state.chats.keys()))
                    st.rerun()

        rename_key = f"chat_rename_{st.session_state.active_chat_id}"
        proposed_name = st.text_input(
            "Rename active chat",
            value=chat["name"],
            key=rename_key,
            label_visibility="collapsed",
            placeholder="Rename active conversation",
        ).strip()
        if proposed_name and proposed_name != chat["name"]:
            chat["name"] = proposed_name

        st.divider()
        st.subheader("Analysis Mode")
        mode = st.radio(
            "Choose workflow",
            list(MODE_HELP),
            index=list(MODE_HELP).index(chat.get("mode", "Scenario Analysis")),
            label_visibility="collapsed",
        )
        chat["mode"] = mode
        st.markdown(f"<div class='mode-note'>{MODE_HELP[mode]}</div>", unsafe_allow_html=True)
        st.subheader("Evaluation Standards")
        selected_standards = [
            label
            for label in STANDARD_OPTIONS
            if st.checkbox(
                label,
                value=label in chat.get("selected_standards", list(STANDARD_OPTIONS)),
                key=f"standard_{st.session_state.active_chat_id}_{label}",
            )
        ]
        chat["selected_standards"] = selected_standards
        if not selected_standards:
            st.warning("Select at least one standard before asking a question.")
        st.subheader("Reasoning Model")
        reasoning_model = st.radio(
            "Choose model backend",
            AVAILABLE_MODEL_OPTIONS,
            index=AVAILABLE_MODEL_OPTIONS.index(
                chat.get("reasoning_model", "OpenAI - advanced analysis")
                if chat.get("reasoning_model", "OpenAI - advanced analysis") in AVAILABLE_MODEL_OPTIONS
                else "OpenAI - advanced analysis"
            ),
            label_visibility="collapsed",
        )
        chat["reasoning_model"] = reasoning_model
        st.markdown(
            f"<div class='mode-note'>{MODEL_OPTIONS[reasoning_model]}</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            (
                f"<div class='model-unavailable' title='{LORA_EXPERIMENT_TOOLTIP}'>"
                f"<span>{LORA_MODEL_LABEL}</span>"
                "<span class='badge'>Unavailable</span>"
                "</div>"
                "<div class='mode-note'>"
                "LoRA fine-tuning path implemented as an experiment; currently not active in this demo build."
                "</div>"
            ),
            unsafe_allow_html=True,
        )
        voice_enabled = st.toggle(
            "Generate audio answer",
            value=bool(chat.get("voice_enabled", False)),
            help="Uses the fixed TTS provider configured in .env. Users cannot choose the voice.",
        )
        chat["voice_enabled"] = voice_enabled
        st.divider()
        st.caption("Suggested tests")
        for sample in SAMPLE_PROMPTS[mode]:
            if st.button(sample, use_container_width=True):
                chat["pending_prompt"] = sample
        st.divider()
        if st.button("Clear conversation", use_container_width=True):
            chat["messages"] = []
            chat["pending_prompt"] = ""
            chat["scenario_intake_open"] = False
            chat["transcribed_prompt"] = ""
            st.rerun()
    return mode, voice_enabled, selected_standards, reasoning_model


def render_scenario_form(
    voice_enabled: bool,
    selected_standards: list[str],
    reasoning_model: str,
) -> None:
    """Render optional scenario intake form."""
    chat = active_chat()
    if "scenario_intake_open" not in chat:
        chat["scenario_intake_open"] = False

    st.markdown("<div class='scenario-intake-shell'></div>", unsafe_allow_html=True)
    if st.button("Structured Scenario Intake", key="scenario_intake_toggle", use_container_width=True):
        chat["scenario_intake_open"] = not chat["scenario_intake_open"]

    if chat["scenario_intake_open"]:
        with st.container(border=True):
            st.caption("Fill what you know. Leave the rest blank; assumptions will be stated.")
            col1, col2 = st.columns(2)
            with col1:
                item = st.text_input("Item/system")
                functions = st.text_input("Main functions")
                happened = st.text_area("What happened", height=90)
                expected = st.text_area("Expected behavior", height=80)
                actual = st.text_area("Actual behavior", height=80)
                road_type = st.text_input("Road type")
                ego_speed = st.text_input("Ego vehicle speed")
                object_speed = st.text_input("Object/road-user speed")
            with col2:
                weather = st.text_input("Weather")
                lighting = st.text_input("Lighting")
                occlusion = st.text_input("Occlusion or visibility issue")
                traffic_density = st.text_input("Traffic density")
                mode = st.text_input("Automation/ADAS mode")
                odd = st.text_input("ODD status, if known")
                ai_ml = st.text_input("AI/ML involved, if known")
                outcome = st.text_area("Collision, near miss, warning, fallback, or disengagement outcome", height=90)
                evidence = st.text_area("Available logs/test reports/sensor evidence", height=80)

            if st.button("Analyze Scenario", use_container_width=True):
                if not selected_standards:
                    st.warning("Select at least one standard before running the analysis.")
                    return
                prompt = make_scenario_prompt(
                    {
                        "Item/system": item,
                        "Main functions": functions,
                        "What happened": happened,
                        "Expected behavior": expected,
                        "Actual behavior": actual,
                        "Road type": road_type,
                        "Ego vehicle speed": ego_speed,
                        "Object/road-user speed": object_speed,
                        "Weather": weather,
                        "Lighting": lighting,
                        "Occlusion or visibility issue": occlusion,
                        "Traffic density": traffic_density,
                        "Automation/ADAS mode": mode,
                        "ODD status": odd,
                        "AI/ML involved": ai_ml,
                        "Outcome": outcome,
                        "Evidence": evidence,
                    },
                    selected_standards,
                )
                submit_prompt(prompt, voice_enabled, selected_standards, reasoning_model)


def render_speech_input(
    voice_enabled: bool,
    selected_standards: list[str],
    reasoning_model: str,
) -> None:
    """Render speech-to-text input controls."""
    chat = active_chat()
    if "transcribed_prompt" not in chat:
        chat["transcribed_prompt"] = ""

    st.markdown("<div class='voice-dock'></div>", unsafe_allow_html=True)
    with st.popover("Voice", use_container_width=False):
        st.caption("Upload a short voice note and convert it into a request. Transcription uses local Whisper.")
        audio_file = None
        if hasattr(st, "audio_input"):
            audio_file = st.audio_input("Record request")
        uploaded_file = st.file_uploader(
            "Upload audio request",
            type=["wav", "mp3", "m4a", "aac", "flac", "ogg", "webm"],
            help="Use this if browser recording is unavailable. Short clips work best.",
        )
        audio_source = audio_file or uploaded_file
        if audio_source is not None:
            st.audio(audio_source)

        col1, col2 = st.columns([1, 1])
        with col1:
            transcribe_clicked = st.button(
                "Transcribe audio",
                use_container_width=True,
                disabled=audio_source is None,
            )
        with col2:
            clear_clicked = st.button("Clear transcription", use_container_width=True)

        if clear_clicked:
            chat["transcribed_prompt"] = ""

        if transcribe_clicked and audio_source is not None:
            suffix = Path(audio_source.name).suffix or ".wav"
            with st.spinner(f"Transcribing with local Whisper `{cfg.STT_MODEL}`..."):
                try:
                    st.session_state.transcribed_prompt = transcribe_audio_file(
                        audio_source.getvalue(),
                        suffix,
                    )
                except Exception:
                    logger.exception("Speech-to-text transcription failed")
                    st.error("Speech transcription failed. Please try a shorter/clearer audio file.")
                else:
                    chat["transcribed_prompt"] = st.session_state.transcribed_prompt
                    # Keep widget value and chat state aligned after successful transcription.
                    st.session_state.transcribed_prompt = chat["transcribed_prompt"]
        # Keep the widget key unique per conversation to avoid cross-chat leakage.
        transcript_widget_key = f"transcribed_prompt_{st.session_state.active_chat_id}"
        if transcript_widget_key not in st.session_state:
            st.session_state[transcript_widget_key] = chat["transcribed_prompt"]
        transcript = st.text_area(
            "Transcribed request",
            value=st.session_state[transcript_widget_key],
            key=transcript_widget_key,
            height=110,
            placeholder="Your transcribed request will appear here. You can edit it before submitting.",
        )
        chat["transcribed_prompt"] = transcript

        if st.button("Submit transcribed request", use_container_width=True, disabled=not transcript.strip()):
            submit_prompt(transcript, voice_enabled, selected_standards, reasoning_model)


def submit_prompt(
    prompt: str,
    voice_enabled: bool,
    selected_standards: list[str],
    reasoning_model: str,
) -> None:
    """Submit prompt to the active chat and update chat history."""
    chat = active_chat()
    if not prompt.strip():
        return
    if not selected_standards:
        st.warning("Select at least one standard before asking a question.")
        return

    prompt_with_scope = scoped_prompt(prompt, selected_standards)
    chat["messages"].append({"role": "user", "content": prompt})
    with st.spinner("Running standards-grounded safety analysis..."):
        previous_tts = cfg.TTS_ENABLED
        cfg.TTS_ENABLED = voice_enabled
        try:
            answer, audio_paths = run_agent(prompt_with_scope, reasoning_model)
        except Exception:
            logger.exception("Agent request failed")
            answer, audio_paths = "error, please try again", []
        finally:
            cfg.TTS_ENABLED = previous_tts
    video_evidence = (
        retrieve_video_evidence(prompt_with_scope)
        if should_show_video_evidence(prompt, reasoning_model)
        else []
    )
    chat["messages"].append(
        {
            "role": "assistant",
            "content": answer,
            "audio_paths": [str(path) for path in audio_paths],
            "video_evidence": video_evidence,
        }
    )
    st.rerun()


def render_chat(
    mode: str,
    voice_enabled: bool,
    selected_standards: list[str],
    reasoning_model: str,
) -> None:
    """Render active chat history and input."""
    chat = active_chat()
    if "messages" not in chat:
        chat["messages"] = []
    if "pending_prompt" not in chat:
        chat["pending_prompt"] = ""

    if mode == "Scenario Analysis":
        render_scenario_form(voice_enabled, selected_standards, reasoning_model)

    avatar_by_role = {
        "user": str(USER_AVATAR_IMAGE),
        "assistant": str(ASSISTANT_AVATAR_IMAGE),
    }
    for message in chat["messages"]:
        role = message["role"]
        with st.chat_message(role, avatar=avatar_by_role.get(role, str(ASSISTANT_AVATAR_IMAGE))):
            st.markdown(message["content"])
            render_video_evidence_player(message.get("video_evidence", []))
            for audio_path in message.get("audio_paths", []):
                if Path(audio_path).exists():
                    st.audio(audio_path)

    pending = chat["pending_prompt"]
    if pending:
        chat["pending_prompt"] = ""
        submit_prompt(pending, voice_enabled, selected_standards, reasoning_model)

    placeholder = {
        "Scenario Analysis": "Describe the scenario or failure. Unknown details are okay.",
        "Item Safety Case": "Ask for a safety case or lifecycle for an item/system.",
        "Standards Q&A": "Ask a standards or safety engineering question.",
        "Dataset / AI Safety Review": "Ask about data gaps, model risk, release gates, or monitoring.",
    }[mode]
    render_speech_input(voice_enabled, selected_standards, reasoning_model)
    if prompt := st.chat_input(placeholder):
        submit_prompt(prompt, voice_enabled, selected_standards, reasoning_model)


def main() -> None:
    """Run the Streamlit app."""
    render_shell()
    mode, voice_enabled, selected_standards, reasoning_model = sidebar_controls()
    render_chat(mode, voice_enabled, selected_standards, reasoning_model)


if __name__ == "__main__":
    main()
