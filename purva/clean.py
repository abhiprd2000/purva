from __future__ import annotations

import re
import unicodedata

_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_PHONE = re.compile(r"(?:(?:\+?91[\-\s]?)|0)?[6-9]\d{9}\b")
_HANDLE = re.compile(r"(?<!\w)@\w{2,}")
_URL = re.compile(r"https?://\S+|www\.\S+")
_SENT_SPLIT = re.compile(r"[।॥?!]+|\.(?:\s)|\n+")
_WS = re.compile(r"\s+")


def strip_pii(text: str) -> str:
    text = _URL.sub(" ", text)
    text = _EMAIL.sub(" ", text)
    text = _PHONE.sub(" ", text)
    text = _HANDLE.sub(" ", text)
    return text


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = _WS.sub(" ", text)
    return text.strip()


def split_sentences(text: str) -> list[str]:
    text = unicodedata.normalize("NFC", text)
    parts = _SENT_SPLIT.split(text)
    return [normalize(p) for p in parts if normalize(p)]


def has_devanagari(text: str) -> bool:
    return any("\u0900" <= ch <= "\u097F" for ch in text)


def clean_sentence(raw: str, min_chars: int = 15) -> str | None:
    cleaned = normalize(strip_pii(raw))
    if len(cleaned) < min_chars:
        return None
    if not has_devanagari(cleaned):
        return None
    return cleaned