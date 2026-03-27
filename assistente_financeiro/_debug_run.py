import sys
import traceback

# Redireciona erros para arquivo de log
log_file = open("crash_log.txt", "w", encoding="utf-8")


def _escrever_log(texto: str) -> None:
    """Escreve no log de crash sem quebrar o fluxo em encerramentos tardios."""
    try:
        if not log_file.closed:
            log_file.write(texto)
            log_file.flush()
    except Exception:
        # Evita erros recursivos no próprio handler de exceções.
        pass

# Handler global de exceções não capturadas
def handle_exception(exc_type, exc_value, exc_traceback):
    msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    _escrever_log("=== EXCECAO NAO CAPTURADA ===\n")
    _escrever_log(msg)
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

sys.excepthook = handle_exception

import threading
original_thread_init = threading.Thread.__init__


def patched_thread_init(self, *args, **kwargs):
    original_run = kwargs.get("target")
    args_mut = list(args)

    # Compatível com chamadas posicionais de Thread.__init__(..., target, ...).
    if original_run is None and len(args_mut) >= 2:
        original_run = args_mut[1]

    if original_run:
        def wrapped(*a, **kw):
            try:
                original_run(*a, **kw)
            except Exception:
                msg = traceback.format_exc()
                _escrever_log("=== EXCECAO EM THREAD ===\n")
                _escrever_log(msg)
                raise

        if "target" in kwargs:
            kwargs["target"] = wrapped
        elif len(args_mut) >= 2:
            args_mut[1] = wrapped

    original_thread_init(self, *tuple(args_mut), **kwargs)


threading.Thread.__init__ = patched_thread_init

# Inicia o app normalmente
try:
    sys.path.insert(0, ".")
    from interface.app_gui import main
    main()
except Exception:
    msg = traceback.format_exc()
    _escrever_log("=== CRASH NO MAINLOOP ===\n")
    _escrever_log(msg)
finally:
    sys.excepthook = sys.__excepthook__
    _escrever_log("=== APP ENCERRADO ===\n")
    try:
        if not log_file.closed:
            log_file.close()
    except Exception:
        pass
