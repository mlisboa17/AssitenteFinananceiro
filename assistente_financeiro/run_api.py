"""
Inicia o servidor FastAPI do Assistente Financeiro Pessoal.

Uso:
    python run_api.py

Acesse a documentação interativa em:
    http://localhost:8000/docs   (Swagger UI)
    http://localhost:8000/redoc  (ReDoc)
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _env_bool(nome: str, padrao: bool = False) -> bool:
    valor = os.getenv(nome)
    if valor is None:
        return padrao
    return valor.strip().lower() in {"1", "true", "yes", "sim", "on"}

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    reload_enabled = _env_bool("API_RELOAD", padrao=False)

    # Evita múltiplos processos competindo no polling do Telegram.
    if _env_bool("TELEGRAM_POLLING_ENABLED", padrao=True) and reload_enabled:
        reload_enabled = False

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload_enabled,
        reload_dirs=["app"],
    )
