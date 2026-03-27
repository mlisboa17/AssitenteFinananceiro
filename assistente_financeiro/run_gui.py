"""
Inicia a interface gráfica do Assistente Financeiro Pessoal.

Uso:
    python run_gui.py

Requisitos:
    pip install customtkinter matplotlib
"""

import sys
import os
import threading
import tkinter.font as _tkfont
import gc
import logging
import faulthandler

# Garante que o diretório raiz do projeto está no PATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ──────────────────────────────────────────────────────────────────────────────
# FIX: Python 3.13 GC cross-thread crash com CustomTkinter
#
# O GC do Python 3.13 pode rodar em qualquer thread, inclusive threads de
# background. Quando coleta objetos mortos de CustomTkinter (DoubleVar,
# PhotoImage), o __del__ desses objetos chama tk.call() fora da main thread
# → RuntimeError → Tcl_AsyncDelete fatal.
#
# Solução: fazer Variable.__del__ e Image.__del__ ignorarem silenciosamente
# quando chamados de threads não-principais.
# As variáveis Tcl permanecem em memória até o root ser destruído (aceitável).
# ──────────────────────────────────────────────────────────────────────────────
import tkinter as _tk

_orig_var_del = _tk.Variable.__del__
def _safe_var_del(self):
    if threading.current_thread() is threading.main_thread():
        _orig_var_del(self)
_tk.Variable.__del__ = _safe_var_del

_orig_img_del = _tk.Image.__del__
def _safe_img_del(self):
    if threading.current_thread() is threading.main_thread():
        _orig_img_del(self)
_tk.Image.__del__ = _safe_img_del

_orig_font_del = _tkfont.Font.__del__
def _safe_font_del(self):
    if threading.current_thread() is threading.main_thread():
        _orig_font_del(self)
_tkfont.Font.__del__ = _safe_font_del


def _iniciar_log_crash_runtime():
    """Habilita dump de falhas fatais em arquivo para diagnóstico."""
    try:
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "crash_log.txt")
        log_path = os.path.abspath(log_path)
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        f = open(log_path, "a", encoding="utf-8")
        f.write("\n=== INICIO EXECUCAO run_gui.py ===\n")
        f.flush()
        faulthandler.enable(file=f, all_threads=True)
        return f
    except Exception:
        return None


def _iniciar_gc_main_thread(root, intervalo_ms: int = 2000):
    """Coleta GC sempre na main thread para evitar Tcl_AsyncDelete no Python 3.13."""
    gc.disable()

    def _coletar():
        try:
            gc.collect()
        except Exception:
            pass
        try:
            root.after(intervalo_ms, _coletar)
        except Exception:
            pass

    try:
        root.after(intervalo_ms, _coletar)
    except Exception:
        pass

def _handle_thread_exception(args):
    """Loga exceções não capturadas em threads de background."""
    import traceback as _tb
    logging.getLogger("thread").error(
        "Exceção não capturada em thread:\n%s",
        "".join(_tb.format_exception(args.exc_type, args.exc_value, args.exc_traceback)),
    )

threading.excepthook = _handle_thread_exception

if __name__ == "__main__":
    _arquivo_crash = _iniciar_log_crash_runtime()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.FileHandler(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "crash_log.txt")), encoding="utf-8")],
    )
    try:
        from interface.app_gui import AssistenteFinanceiroApp
        app = AssistenteFinanceiroApp()
        _iniciar_gc_main_thread(app)
        app.mainloop()
    finally:
        if _arquivo_crash:
            try:
                _arquivo_crash.flush()
                _arquivo_crash.close()
            except Exception:
                pass
