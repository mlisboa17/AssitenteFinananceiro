"""
Serviço de IA online com modelos gratuitos via OpenRouter.

Uso principal:
- fallback quando Gemini falha por cota/créditos
- alternativa gratuita (não local), depende de OPENROUTER_API_KEY
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import requests
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Você é o Vorcaro, assistente financeiro pessoal em português do Brasil. "
    "Seja humano, claro e objetivo. Não invente valores."
)

# Modelos gratuitos para tentar em ordem (fallback interno se o primary falhar)
_MODELOS_BACKUP = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-3-27b-it:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
    "meta-llama/llama-3.2-3b-instruct:free",
    "qwen/qwen3-4b:free",
    "arcee-ai/trinity-mini:free",
]

class OpenRouterService:
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        self.base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
        self.model = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
        try:
            self.timeout = int(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "45"))
        except ValueError as exc:
            raise RuntimeError(
                "Valor inválido em OPENROUTER_TIMEOUT_SECONDS. Use um número inteiro (ex: 45)."
            ) from exc
        self.enabled = os.getenv("VORCARO_OPENROUTER_ENABLED", "true").strip().lower() in {"1", "true", "yes", "sim", "on"}
        self.disabled_reason = self._build_disabled_reason()

    def _build_disabled_reason(self) -> str:
        if not self.enabled:
            return "OpenRouter desativado por VORCARO_OPENROUTER_ENABLED=false"
        if not self.api_key:
            return "OPENROUTER_API_KEY ausente no .env"
        return ""

    def disponivel(self) -> bool:
        return not self.disabled_reason

    def diagnostico(self) -> dict:
        return {
            "enabled": self.enabled,
            "api_key_ok": bool(self.api_key),
            "base_url": self.base_url,
            "model": self.model,
            "mensagem": self.disabled_reason or "OpenRouter pronto para uso.",
        }

    def enviar(self, pergunta: str, db: Optional[Session] = None) -> str:
        if not self.disponivel():
            raise RuntimeError(f"OpenRouter indisponível: {self.disabled_reason}")

        contexto = ""
        if db is not None:
            try:
                from app.services.gemini_service import GeminiService

                contexto = GeminiService.construir_contexto(db)
            except Exception as exc:
                logger.warning("Sem contexto financeiro para OpenRouter: %s", exc)

        mensagens = [{"role": "system", "content": SYSTEM_PROMPT}]
        if contexto:
            mensagens.append({"role": "system", "content": "Contexto financeiro:\n\n" + contexto})
        mensagens.append({"role": "user", "content": pergunta.strip()})

        headers: dict = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost",
            "X-Title": "Vorcaro Assistente Financeiro",
        }

        # Constrói lista de modelos a tentar: primary + backups (sem duplicar)
        modelos = [self.model] + [m for m in _MODELOS_BACKUP if m != self.model]

        ultimo_erro: Exception | None = None
        for modelo in modelos:
            payload = {"model": modelo, "messages": mensagens, "temperature": 0.4}
            try:
                resp = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )
                if resp.status_code == 429:
                    raw = ((resp.json() or {}).get("error") or {}).get("metadata", {}).get("raw", "")
                    logger.warning("OpenRouter modelo %s rate-limited upstream; tentando próximo. raw=%s", modelo, raw[:120])
                    ultimo_erro = RuntimeError(f"rate-limited: {raw[:80]}")
                    continue
                if resp.status_code == 404:
                    logger.warning("OpenRouter modelo %s não encontrado; tentando próximo.", modelo)
                    ultimo_erro = RuntimeError(f"modelo não encontrado: {modelo}")
                    continue
                resp.raise_for_status()
                data = resp.json() or {}
                choices = data.get("choices") or []
                if not choices:
                    logger.warning("OpenRouter modelo %s retornou choices vazio; tentando próximo.", modelo)
                    ultimo_erro = RuntimeError("choices vazio")
                    continue
                texto = (((choices[0] or {}).get("message") or {}).get("content") or "").strip()
                if not texto:
                    logger.warning("OpenRouter modelo %s retornou texto vazio; tentando próximo.", modelo)
                    ultimo_erro = RuntimeError("texto vazio")
                    continue
                if modelo != self.model:
                    logger.info("OpenRouter respondeu usando modelo de backup: %s", modelo)
                return texto
            except (RuntimeError, Exception) as exc:  # noqa: BLE001
                if isinstance(exc, RuntimeError):
                    raise
                logger.warning("OpenRouter modelo %s erro inesperado: %s; tentando próximo.", modelo, exc)
                ultimo_erro = exc

        raise RuntimeError(f"Todos os modelos OpenRouter falharam. Último erro: {ultimo_erro}")
