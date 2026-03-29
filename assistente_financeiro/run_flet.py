"""Inicia a nova interface Flet do Assistente Financeiro.

Uso:
    python run_flet.py
"""

import atexit
import os
import subprocess
import sys
import time
from urllib.parse import urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import flet as ft
import requests

from interface_flet.app_flet import main


_api_proc: subprocess.Popen | None = None


def _api_base_url() -> str:
    raw = os.getenv("FLET_API_BASE_URL", "").strip()
    if raw:
        return raw.rstrip("/")

    assistente_url = os.getenv("ASSISTENTE_API_URL", "http://127.0.0.1:8000/assistente/").strip()
    if "/assistente" in assistente_url:
        assistente_url = assistente_url.split("/assistente", 1)[0]
    return assistente_url.rstrip("/")


def _api_online(base_url: str) -> bool:
    try:
        response = requests.get(f"{base_url}/diagnostico/ambiente", timeout=2)
        return response.status_code < 500
    except Exception:
        return False


def _start_api_if_needed() -> None:
    global _api_proc

    if _api_proc is not None:
        return

    if os.getenv("VORCARO_SKIP_FLET_API_AUTOSTART", "").strip().lower() in {"1", "true", "yes", "sim", "on"}:
        return

    base_url = _api_base_url()
    if _api_online(base_url):
        return

    app_dir = os.path.dirname(os.path.abspath(__file__))
    run_api = os.path.join(app_dir, "run_api.py")
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    _api_proc = subprocess.Popen(
        [sys.executable, run_api],
        cwd=app_dir,
        creationflags=creationflags,
    )

    # Aguarda alguns segundos para a API ficar de pé antes de abrir a UI.
    for _ in range(16):
        if _api_proc.poll() is not None:
            print(f"Erro ao iniciar API automaticamente (código {_api_proc.returncode}).")
            _api_proc = None
            return
        if _api_online(base_url):
            print(f"API iniciada automaticamente em {base_url}")
            return
        time.sleep(0.5)

    parsed = urlsplit(base_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 8000
    print("Aviso: API ainda não respondeu a tempo.")
    print(f"Se necessário, inicie manualmente: {sys.executable} run_api.py (HOST={host} PORT={port})")


def _stop_started_api() -> None:
    global _api_proc
    if _api_proc is None:
        return
    if _api_proc.poll() is None:
        _api_proc.terminate()
        try:
            _api_proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            _api_proc.kill()
    _api_proc = None


if __name__ == "__main__":
    _start_api_if_needed()
    atexit.register(_stop_started_api)
    if hasattr(ft, "run"):
        ft.run(main)
    else:
        ft.app(target=main)
