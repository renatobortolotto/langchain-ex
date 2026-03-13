import importlib.util
import json
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


class DummyFileInput:
    def __init__(self, content: bytes):
        self.content = content


def _install_dummy_framework():
    m_decorators = types.ModuleType("genai_framework.decorators")

    def file_input_route(_name):
        def decorator(fn):
            return fn
        return decorator

    m_decorators.file_input_route = file_input_route

    m_models = types.ModuleType("genai_framework.models")

    class FileInput:
        def __init__(self, content: bytes):
            self.content = content

    m_models.FileInput = FileInput

    sys.modules["genai_framework"] = types.ModuleType("genai_framework")
    sys.modules["genai_framework.decorators"] = m_decorators
    sys.modules["genai_framework.models"] = m_models


def _load_route_module():
    _install_dummy_framework()
    route_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "routes"
        / "analyze_file.py"
    )
    spec = importlib.util.spec_from_file_location("langchain_ex_analyze_file", str(route_path))
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["langchain_ex_analyze_file"] = module
    spec.loader.exec_module(module)
    return module


class TestAnalyzeFileRoute(unittest.TestCase):
    def test_analyze_file_success(self):
        module = _load_route_module()
        fake_response = {
            "titles": {"slide1_title": "Titulo"},
            "subtitles": {"slide1_subtitle": "Subtitulo"},
        }
        fake_result = types.SimpleNamespace(agent_id="slide1")
        with patch.object(module, "load_slide_agents", return_value=["agent"]):
            with patch.object(module, "analyze_workbook", return_value=(fake_response, [fake_result])):
                payload = module.analyze_file(DummyFileInput(b"xlsx-bytes"))

        self.assertEqual(payload["response"], fake_response)
        self.assertEqual(payload["meta"]["agents"], ["slide1"])

    def test_analyze_file_failure(self):
        module = _load_route_module()
        with patch.object(module, "load_slide_agents", side_effect=ValueError("config invalida")):
            payload = module.analyze_file(DummyFileInput(b"xlsx-bytes"))

        self.assertEqual(
            payload["error"],
            "Falha ao processar o XLSX com os agentes por slide.",
        )
        self.assertIn("config invalida", payload["details"])


class TestPresentationAgentsService(unittest.TestCase):
    def test_load_slide_agents(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from src.presentation_agents.service import load_slide_agents, resolve_default_agents_path

        agents = load_slide_agents(resolve_default_agents_path())

        self.assertEqual([agent.id for agent in agents], ["slide1", "slide2"])
        self.assertTrue(all(agent.prompt_path.exists() for agent in agents))

    def test_analyze_workbook_merges_agent_payloads(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from src.presentation_agents.service import analyze_workbook, load_slide_agents, resolve_default_agents_path

        agents = load_slide_agents(resolve_default_agents_path())

        def fake_invoke(agent, prompt):
            self.assertIn("Dados do workbook", prompt)
            return json.dumps(
                {
                    "titles": {f"{agent.id}_title": f"Titulo {agent.id}"},
                    "subtitles": {f"{agent.id}_subtitle": f"Subtitulo {agent.id}"},
                }
            )

        fake_workbook = {
            "lucroTrimestre": {
                "labels": ["2T25", "3T25"],
                "values": [459.0, 461.0],
                "sheet": "DRE Saida",
                "ranges": {"labels": "C3:K3", "values": "C18:K18"},
            }
        }

        with patch(
            "src.presentation_agents.service.extract_xlsx_bytes_to_dict",
            return_value=fake_workbook,
        ):
            merged, results = analyze_workbook(b"xlsx", agents, invoke_agent=fake_invoke)

        self.assertEqual(len(results), 2)
        self.assertEqual(merged["titles"]["slide1_title"], "Titulo slide1")
        self.assertEqual(merged["titles"]["slide2_title"], "Titulo slide2")

    def test_resolve_vertex_project_and_region_uses_adc_and_default_region(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from src.presentation_agents.service import _resolve_vertex_project_and_region

        old_project = os.environ.pop("GOOGLE_CLOUD_PROJECT", None)
        old_project_id = os.environ.pop("PROJECT_ID", None)
        old_region = os.environ.pop("GOOGLE_CLOUD_REGION", None)
        old_location = os.environ.pop("LOCATION", None)
        try:
            with patch("google.auth.default", return_value=(object(), "adc-project")):
                project, region = _resolve_vertex_project_and_region()
        finally:
            if old_project is not None:
                os.environ["GOOGLE_CLOUD_PROJECT"] = old_project
            if old_project_id is not None:
                os.environ["PROJECT_ID"] = old_project_id
            if old_region is not None:
                os.environ["GOOGLE_CLOUD_REGION"] = old_region
            if old_location is not None:
                os.environ["LOCATION"] = old_location

        self.assertEqual(project, "adc-project")
        self.assertEqual(region, "us-central1")


if __name__ == "__main__":
    unittest.main()
