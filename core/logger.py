from datetime import datetime

# lista global de logs
logs = []


def log(msg: str):
    try:
        timestamp = datetime.now().strftime("%H:%M:%S")
        mensagem = f"[{timestamp}] {str(msg)}"
        logs.append(mensagem)
    except Exception:
        logs.append(str(msg))


def log_erro(msg: str, erro: Exception = None):
    try:
        timestamp = datetime.now().strftime("%H:%M:%S")
        if erro:
            mensagem = f"[{timestamp}] ❌ {msg} | {str(erro)}"
        else:
            mensagem = f"[{timestamp}] ❌ {msg}"
        logs.append(mensagem)
    except Exception:
        logs.append(f"❌ {msg}")


def log_info(msg: str):
    try:
        timestamp = datetime.now().strftime("%H:%M:%S")
        logs.append(f"[{timestamp}] ℹ️ {msg}")
    except Exception:
        logs.append(f"ℹ️ {msg}")


def limpar_logs():
    logs.clear()
