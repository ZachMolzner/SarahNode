# SarahNode Local AI

SarahNode can run without OpenAI or any paid cloud LLM. The backend now supports any OpenAI-compatible local model server.

## Recommended first target: Ollama

Ollama exposes an OpenAI-compatible API at `http://127.0.0.1:11434/v1` and supports chat completions and tool calling.

1. Install Ollama for Windows.
2. Pull a model, for example:

   ```powershell
   ollama pull llama3.2
   ```

3. Make sure Ollama is running.
4. Configure `backend/.env`:

   ```env
   LLM_PROVIDER=local
   LOCAL_LLM_BASE_URL=http://127.0.0.1:11434/v1
   LOCAL_LLM_MODEL=llama3.2
   LOCAL_LLM_API_KEY=local
   LOCAL_LLM_TEMPERATURE=0.4
   LOCAL_LLM_MAX_TOOL_ROUNDS=5
   ```

5. Start SarahNode normally.

## llama.cpp alternative

`llama-server` also exposes an OpenAI-compatible API. If it is running on port 8080, use:

```env
LLM_PROVIDER=local
LOCAL_LLM_BASE_URL=http://127.0.0.1:8080/v1
LOCAL_LLM_MODEL=local-model
LOCAL_LLM_API_KEY=local
```

Start llama.cpp separately with the GGUF model you want Sarah to use.

## How Sarah "learns"

SarahNode should not continuously rewrite model weights after every conversation. Personal learning is handled by persistent memory, project/profile/entity memory, retrieval, and later curated fine-tuning/LoRA if useful. This keeps the base model stable while allowing Sarah to become increasingly personalized.

## Provider modes

- `LLM_PROVIDER=local`: use the configured local OpenAI-compatible server.
- `LLM_PROVIDER=openai`: use the OpenAI cloud API.
- `LLM_PROVIDER=mock`: diagnostics only.

OpenAI credentials are not required in local mode.
