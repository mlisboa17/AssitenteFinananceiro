import subprocess
import sys
import time
from pathlib import Path


def _resolve_python_executable(base_dir: Path) -> str:
    venv_python = base_dir / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def main() -> int:
    base_dir = Path(__file__).resolve().parent
    app_dir = base_dir / "assistente_financeiro"
    api_script = app_dir / "run_api.py"
    gui_script = app_dir / "run_gui.py"

    if not api_script.exists() or not gui_script.exists():
        print("Erro: nao encontrei run_api.py e run_gui.py em assistente_financeiro/.")
        return 1

    python_exec = _resolve_python_executable(base_dir)

    print("Iniciando API...")
    api_proc = subprocess.Popen(
        [python_exec, str(api_script)],
        cwd=str(app_dir),
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
    )

    try:
        time.sleep(3)
        if api_proc.poll() is not None:
            print(f"Erro: a API encerrou logo no inicio (codigo {api_proc.returncode}).")
            return api_proc.returncode or 1

        print("API ativa. Iniciando interface grafica...")
        gui_proc = subprocess.Popen([python_exec, str(gui_script)], cwd=str(app_dir))
        gui_exit = gui_proc.wait()

        if gui_exit != 0:
            print(f"GUI encerrada com erro (codigo {gui_exit}).")
            return gui_exit

        print("GUI encerrada. Finalizando API...")
        return 0
    except KeyboardInterrupt:
        print("Interrompido pelo usuario. Encerrando processos...")
        return 130
    finally:
        if api_proc.poll() is None:
            api_proc.terminate()
            try:
                api_proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                api_proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
