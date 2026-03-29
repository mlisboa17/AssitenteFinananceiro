"""Testa modelos gratuitos do OpenRouter e retorna o melhor disponível."""
import os, requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)
key = os.getenv("OPENROUTER_API_KEY", "")
print(f"Chave: {key[:20]}...")

MODELOS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-3-27b-it:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
    "meta-llama/llama-3.2-3b-instruct:free",
    "qwen/qwen3-4b:free",
]

for model in MODELOS:
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "user", "content": "responda apenas: ok"}], "max_tokens": 10},
            timeout=25,
        )
        if r.status_code == 200:
            resposta = (r.json().get("choices") or [{}])[0].get("message", {}).get("content", "")
            print(f"OK {model} -> {resposta!r}")
        else:
            print(f"FALHA {model} -> {r.status_code} {r.text[:80]}")
    except Exception as e:
        print(f"ERRO {model} -> {e}")
