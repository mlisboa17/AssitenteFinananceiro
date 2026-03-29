"""
Serviço de IA local (Ollama) para fallback do Vorcaro.

Objetivo:
- Assumir quando Gemini estiver indisponível (quota, rate limit, erro de crédito, etc.)
- Rodar localmente sem custo de API
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import requests
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


SYSTEM_PROMPT_LOCAL = (
    "Você é o Vorcaro, assistente financeiro pessoal em português do Brasil. "
    "Seja claro, humano e objetivo. Use os dados de contexto fornecidos. "
    "Não invente números. Quando faltar informação, diga isso claramente."
)


class LocalAIService:
    """Cliente simples para Ollama com suporte ao contexto financeiro do usuário."""

    def __init__(self):
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
        self.model = os.getenv("VORCARO_OLLAMA_MODEL", os.getenv("OLLAMA_MODEL", "qwen2.5:3b"))
        try:
            self.timeout = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "90"))
        except ValueError as exc:
            raise RuntimeError(
                "Valor inválido em OLLAMA_TIMEOUT_SECONDS. Use um número inteiro (ex: 90)."
            ) from exc
        self.enabled = os.getenv("VORCARO_LOCAL_AI_ENABLED", "true").strip().lower() in {"1", "true", "yes", "sim", "on"}
        self.disabled_reason = "" if self.enabled else "Fallback local desativado por VORCARO_LOCAL_AI_ENABLED=false"

    def disponivel(self) -> bool:
        if not self.enabled:
            return False
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=4)
            return resp.status_code == 200
        except Exception:
            return False

    def diagnostico(self) -> dict:
        return {
            "enabled": self.enabled,
            "base_url": self.base_url,
            "model": self.model,
            "ollama_ok": self.disponivel(),
            "mensagem": self.disabled_reason or "Fallback local habilitado. Verifique se o Ollama está em execução.",
        }

    def enviar(self, pergunta: str, db: Optional[Session] = None) -> str:
        if not self.enabled:
            raise RuntimeError(self.disabled_reason)

        contexto = ""
        if db is not None:
            try:
                from app.services.gemini_service import GeminiService

                contexto = GeminiService.construir_contexto(db)
            except Exception as exc:
                logger.warning("Não foi possível montar contexto para IA local: %s", exc)

        mensagens = [
            {"role": "system", "content": SYSTEM_PROMPT_LOCAL},
        ]
        if contexto:
            mensagens.append(
                {
                    "role": "system",
                    "content": "Contexto financeiro atual do usuário:\n\n" + contexto,
                }
            )
        mensagens.append({"role": "user", "content": pergunta.strip()})

        resp = requests.post(
            f"{self.base_url}/api/chat",
            json={"model": self.model, "messages": mensagens, "stream": False},
            timeout=self.timeout,
        )
        resp.raise_for_status()

        data = resp.json() or {}
        texto = ((data.get("message") or {}).get("content") or "").strip()
        if not texto:
            raise RuntimeError("IA local não retornou conteúdo")
        return texto
