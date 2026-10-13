"""Detect factual claims on a TOBIZ page that are absent from the approved brief."""

from __future__ import annotations

import json
import re
from html import unescape
from typing import Any, Callable

from . import content


def _plain(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", value))).strip()


def _digits(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    return digits[-10:] if len(digits) >= 10 else digits


def _number(value: str) -> str:
    return re.sub(r"\D", "", value)


PATTERNS: tuple[tuple[str, re.Pattern[str], Callable[[str], str]], ...] = (
    ("phone", re.compile(r"(?:\+7|8)[\s(\-]*\d{3}[\s)\-]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}"), _digits),
    ("email", re.compile(r"[\w.+-]+@[\w.-]+\.[a-zа-я]{2,}", re.I), lambda value: value.lower()),
    ("price", re.compile(r"\b\d[\d\s]{0,8}(?:[.,]\d{1,2})?\s*(?:₽|руб(?:\.|лей|ля)?)", re.I), _number),
    ("discount", re.compile(r"\b\d{1,3}\s*%"), _number),
    ("experience", re.compile(
        r"(?:\b\d{1,2}\s*(?:лет|года?|год)\s+(?:опыта|работы|практики)|"
        r"\b(?:опыт|стаж)\s+(?:работы\s+)?\d{1,2}\s*(?:лет|года?|год))", re.I), _number),
    ("duration", re.compile(r"\b\d{1,3}\s*(?:минут|час(?:а|ов)?|дн(?:я|ей)|недел(?:я|и|ь)|месяц(?:а|ев)?)\b", re.I), lambda value: re.sub(r"\s+", " ", value.lower())),
    ("statistic", re.compile(r"\b\d[\d\s]{0,7}\+?\s*(?:клиент(?:а|ов)?|ученик(?:а|ов)?|проект(?:а|ов)?|объект(?:а|ов)?|заказ(?:а|ов)?)\b", re.I), lambda value: re.sub(r"\s+", " ", value.lower())),
)


def _claims(text: str) -> list[dict[str, str]]:
    found = []
    occupied: set[tuple[int, int]] = set()
    for kind, pattern, canonical in PATTERNS:
        for match in pattern.finditer(text):
            span = match.span()
            if span in occupied:
                continue
            occupied.add(span)
            found.append({"kind": kind, "value": match.group(0),
                          "canonical": canonical(match.group(0))})
    return found


def analyze(draft, brief: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(brief, dict):
        raise ValueError("brief must be an object")
    approved_text = json.dumps(brief, ensure_ascii=False, sort_keys=True)
    approved = {(item["kind"], item["canonical"]) for item in _claims(approved_text)}
    claims, issues = [], []
    for block_id in draft.order:
        block = draft.blocks[block_id]
        if block.deleted:
            continue
        for path, kind, value in content.fields(block.values):
            if kind != "text":
                continue
            plain = _plain(value)
            for item in _claims(plain):
                supported = (item["kind"], item["canonical"]) in approved
                record = {"block_id": str(block_id), "type_id": str(block.type_id),
                          "path": path, "text": plain[:240], **item, "supported": supported}
                claims.append(record)
                if not supported:
                    issues.append({
                        "priority": "must_fix", "code": f"unsupported_{item['kind']}_claim",
                        "block_id": str(block_id), "path": path, "value": item["value"],
                        "action": "Подтвердить утверждение в брифе или удалить его из штатного поля.",
                    })
    return {
        "ready": not issues, "claims": claims, "issues": issues,
        "supported": sum(1 for item in claims if item["supported"]),
        "unsupported": len(issues),
        "checked_kinds": [item[0] for item in PATTERNS],
        "rule": "Отсутствие факта в брифе блокирует выдачу, но инструмент ничего не изменяет.",
    }


def analyze_recipe(recipe: dict[str, Any], brief: dict[str, Any]) -> dict[str, Any]:
    """Check proposed native slot values before a page is copied."""
    approved_text = json.dumps(brief, ensure_ascii=False, sort_keys=True)
    approved = {(item["kind"], item["canonical"]) for item in _claims(approved_text)}
    claims, issues = [], []
    for slot in recipe.get("slots") or []:
        if not isinstance(slot, dict) or not isinstance(slot.get("value"), str):
            continue
        for item in _claims(_plain(slot["value"])):
            supported = (item["kind"], item["canonical"]) in approved
            record = {"block_index": slot.get("block_index"), "path": slot.get("path"),
                      **item, "supported": supported}
            claims.append(record)
            if not supported:
                issues.append({
                    "priority": "must_fix", "code": f"unsupported_{item['kind']}_claim",
                    "block_index": slot.get("block_index"), "path": slot.get("path"),
                    "value": item["value"],
                    "action": "Добавить подтверждение в бриф или изменить текст до создания страницы.",
                })
    return {"ready": not issues, "claims": claims, "issues": issues,
            "supported": sum(1 for item in claims if item["supported"]),
            "unsupported": len(issues)}
