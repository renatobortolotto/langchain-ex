# langchain-ex

Servico de LLM para receber um `xlsx`, extrair os ranges necessarios por slide e gerar o JSON final consumido pelo `ppt-doc`.

## Fluxo

1. A rota `analyze_file` recebe o `xlsx`.
2. `config/slide_agents.json` define um agente por slide.
3. Cada agente:
   - extrai apenas os ranges configurados
   - carrega seu prompt dedicado em `config/prompts/`
   - chama Gemini via LangChain `ChatVertexAI`
   - retorna apenas o trecho de JSON daquele slide
4. O servico agrega tudo em um unico payload:

```json
{
  "response": {
    "titles": {
      "slide1_title": "...",
      "slide2_title": "..."
    },
    "subtitles": {
      "slide1_subtitle": "...",
      "slide2_subtitle": "..."
    }
  }
}
```

## Arquivos principais

- `src/routes/analyze_file.py`: rota corporativa de upload do `xlsx`
- `src/presentation_agents/service.py`: orquestracao dos agentes por slide
- `config/slide_agents.json`: configuracao dos agentes, modelos e specs
- `config/prompts/*.md`: prompts individuais por slide

## Configuracao

- `SLIDE_AGENTS_CONFIG_PATH`: sobrescreve o caminho do `slide_agents.json`
- `GOOGLE_CLOUD_PROJECT` ou `PROJECT_ID`: projeto GCP
- `GOOGLE_CLOUD_REGION` ou `LOCATION`: regiao do Vertex AI

## Testes

```bash
cd /home/renato/projetos/double-projects/langchain-ex
python3 -m unittest discover -s tests/unit -v
```
