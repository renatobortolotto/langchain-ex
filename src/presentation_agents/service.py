from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from .json_utils import coerce_json
from .xlsx_extract import ExtractSpec, extract_xlsx_bytes_to_dict, parse_specs_data


@dataclass(frozen=True)
class SlideAgentConfig:
    id: str
    prompt_path: Path
    specs: tuple[ExtractSpec, ...]
    model: str
    temperature: float
    max_output_tokens: int
    default_sheet: Optional[str] = None


@dataclass(frozen=True)
class SlideAgentResult:
    agent_id: str
    extracted: Dict[str, Any]
    response: Dict[str, Any]


InvokeAgentFn = Callable[[SlideAgentConfig, str], str]


def resolve_default_agents_path() -> Path:
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        candidate = parent / "config" / "slide_agents.json"
        if candidate.exists():
            return candidate
    return Path("config") / "slide_agents.json"


def load_slide_agents(path: str | Path) -> List[SlideAgentConfig]:
    config_path = Path(path).expanduser().resolve()
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("slide_agents.json deve ser um objeto")

    default_model = str(raw.get("default_model") or "gemini-2.5-flash-lite")
    default_temperature = float(raw.get("default_temperature") or 0.2)
    default_max_output_tokens = int(raw.get("default_max_output_tokens") or 4096)
    agents = raw.get("agents")
    if not isinstance(agents, list) or not agents:
        raise ValueError("slide_agents.json precisa ter a lista 'agents'")

    config_dir = config_path.parent
    out: List[SlideAgentConfig] = []
    for item in agents:
        if not isinstance(item, dict):
            raise ValueError("Cada agente deve ser um objeto JSON")

        agent_id = str(item.get("id") or "").strip()
        if not agent_id:
            raise ValueError("Agente sem 'id'")

        prompt_path_raw = item.get("prompt_path")
        if not prompt_path_raw:
            raise ValueError(f"Agente {agent_id!r} sem 'prompt_path'")
        prompt_path = Path(str(prompt_path_raw))
        if not prompt_path.is_absolute():
            prompt_path = (config_dir / prompt_path).resolve()
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt nao encontrado para {agent_id!r}: {prompt_path}")

        specs = parse_specs_data(item.get("specs") or [])
        if not specs:
            raise ValueError(f"Agente {agent_id!r} precisa ter ao menos um spec")

        model = str(item["model"]) if "model" in item else default_model
        temperature = float(item["temperature"]) if "temperature" in item else default_temperature
        max_output_tokens = (
            int(item["max_output_tokens"])
            if "max_output_tokens" in item
            else default_max_output_tokens
        )
        default_sheet = str(item["default_sheet"]) if item.get("default_sheet") else None

        out.append(
            SlideAgentConfig(
                id=agent_id,
                prompt_path=prompt_path,
                specs=tuple(specs),
                model=model,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                default_sheet=default_sheet,
            )
        )

    return out


def _build_agent_messages(*, agent: SlideAgentConfig, extracted: Dict[str, Any]) -> list[tuple[str, str]]:
    prompt_text = agent.prompt_path.read_text(encoding="utf-8").strip()
    workbook_json = json.dumps(extracted, ensure_ascii=False, indent=2)
    return [
        (
            "system",
            "Voce escreve apenas JSON valido para consumo de um pipeline de geracao de PowerPoint.",
        ),
        (
            "human",
            f"{prompt_text}\n\nDados do workbook:\n{workbook_json}",
        ),
    ]


def _resolve_vertex_project_and_region() -> tuple[str, str]:
    project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("PROJECT_ID")
    if not project:
        try:
            import google.auth  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "Nao foi possivel resolver o projeto GCP via ADC."
            ) from exc

        _credentials, detected_project = google.auth.default()
        if not detected_project:
            raise RuntimeError(
                "Defina GOOGLE_CLOUD_PROJECT/PROJECT_ID ou autentique ADC com projeto padrao."
            )
        project = detected_project

    region = os.getenv("GOOGLE_CLOUD_REGION") or os.getenv("LOCATION") or "us-central1"
    return project, region


def _default_invoke_agent(agent: SlideAgentConfig, prompt: str) -> str:
    try:
        from langchain_google_vertexai import ChatVertexAI  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "Dependencia 'langchain-google-vertexai' nao instalada."
        ) from exc

    project, location = _resolve_vertex_project_and_region()

    llm = ChatVertexAI(
        model=agent.model,
        project=project,
        location=location,
        temperature=agent.temperature,
        max_output_tokens=agent.max_output_tokens,
        response_mime_type="application/json",
    )
    response = llm.invoke([("human", prompt)])
    content = getattr(response, "content", response)
    if isinstance(content, list):
        return "".join(str(part) for part in content)
    return str(content)


def _merge_section(dst: Dict[str, str], src: object) -> None:
    if not isinstance(src, dict):
        return
    for key, value in src.items():
        if value is None:
            continue
        dst[str(key)] = str(value)


def merge_agent_payloads(results: Sequence[SlideAgentResult]) -> Dict[str, Any]:
    merged_titles: Dict[str, str] = {}
    merged_subtitles: Dict[str, str] = {}
    extra_fields: Dict[str, str] = {}

    for result in results:
        payload = result.response
        _merge_section(merged_titles, payload.get("titles"))
        _merge_section(merged_subtitles, payload.get("subtitles"))
        for key, value in payload.items():
            if key in {"titles", "subtitles"} or value is None:
                continue
            if isinstance(value, str):
                extra_fields[str(key)] = value

    merged: Dict[str, Any] = {}
    if merged_titles:
        merged["titles"] = merged_titles
    if merged_subtitles:
        merged["subtitles"] = merged_subtitles
    merged.update(extra_fields)
    return merged


def analyze_workbook(
    xlsx_bytes: bytes,
    agents: Sequence[SlideAgentConfig],
    *,
    invoke_agent: Optional[InvokeAgentFn] = None,
) -> tuple[Dict[str, Any], List[SlideAgentResult]]:
    if not xlsx_bytes:
        raise ValueError("XLSX vazio")

    invoker = invoke_agent or _default_invoke_agent
    results: List[SlideAgentResult] = []

    for agent in agents:
        extracted = extract_xlsx_bytes_to_dict(
            xlsx_bytes,
            agent.specs,
            default_sheet=agent.default_sheet,
            include_meta=True,
            lowercase_fields=True,
        )
        messages = _build_agent_messages(agent=agent, extracted=extracted)
        prompt = "\n\n".join(text for _, text in messages)
        raw_response = invoker(agent, prompt)
        parsed_response = coerce_json(raw_response)
        results.append(
            SlideAgentResult(
                agent_id=agent.id,
                extracted=extracted,
                response=parsed_response,
            )
        )

    return merge_agent_payloads(results), results
