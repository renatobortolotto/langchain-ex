from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from genai_framework.decorators import file_input_route  # type: ignore
from genai_framework.models import FileInput  # type: ignore

from src.presentation_agents.service import analyze_workbook, load_slide_agents, resolve_default_agents_path


@file_input_route("analyze_file")
def analyze_file(file: FileInput):
    try:
        config_path = os.getenv("SLIDE_AGENTS_CONFIG_PATH") or str(resolve_default_agents_path())
        agents = load_slide_agents(config_path)
        response, results = analyze_workbook(file.content, agents)
        return {
            "response": response,
            "meta": {
                "agents": [result.agent_id for result in results],
                "configPath": config_path,
            },
        }
    except Exception as exc:
        return {
            "error": "Falha ao processar o XLSX com os agentes por slide.",
            "details": str(exc),
            "configPath": os.getenv("SLIDE_AGENTS_CONFIG_PATH") or str(resolve_default_agents_path()),
        }
