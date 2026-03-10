from __future__ import annotations

import json
from typing import Any, Dict


def strip_fences(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        nl = text.find("\n")
        if nl != -1:
            text = text[nl + 1 :]
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()


def first_json_object_slice(text: str) -> str:
    start = text.find("{")
    if start == -1:
        raise json.JSONDecodeError("No JSON object found", text, 0)

    depth = 0
    in_str = False
    esc = False

    for i in range(start, len(text)):
        ch = text[i]

        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]

    raise json.JSONDecodeError("No complete JSON object found", text, start)


def coerce_json(text: str) -> Dict[str, Any]:
    body = strip_fences(text)
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return json.loads(first_json_object_slice(body))
