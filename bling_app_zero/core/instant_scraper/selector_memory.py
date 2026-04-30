from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse


MEMORY_DIR = Path("bling_app_zero/output/auto_learning")
MEMORY_FILE = MEMORY_DIR / "selector_memory.json"


def _domain(url: str) -> str:
    try:
        host = urlparse(str(url or "").strip()).netloc.lower().replace("www.", "")
        return host or "desconhecido"
    except Exception:
        return "desconhecido"


def _read() -> dict:
    try:
        if MEMORY_FILE.exists():
            return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _write(data: dict) -> None:
    try:
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        MEMORY_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def remember_selector(url: str, selector: str, score: int, rows: int, kind: str = "") -> None:
    selector = str(selector or "").strip()
    if not selector:
        return
    data = _read()
    dominio = _domain(url)
    atual = data.get(dominio, {})
    historico = atual.get("historico", []) if isinstance(atual, dict) else []
    historico.append({
        "selector": selector,
        "score": int(score or 0),
        "rows": int(rows or 0),
        "kind": str(kind or ""),
        "url": str(url or ""),
        "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    historico = sorted(historico, key=lambda x: (int(x.get("score", 0)), int(x.get("rows", 0))), reverse=True)[:25]
    data[dominio] = {
        "dominio": dominio,
        "melhor_selector": historico[0].get("selector", selector),
        "melhor_score": int(historico[0].get("score", score)),
        "melhor_rows": int(historico[0].get("rows", rows)),
        "ultima_atualizacao": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "historico": historico,
    }
    _write(data)


def get_best_selector(url: str) -> str:
    data = _read()
    registro = data.get(_domain(url), {})
    if not isinstance(registro, dict):
        return ""
    return str(registro.get("melhor_selector", "") or "").strip()


def get_selector_report(url: str) -> dict:
    data = _read()
    return data.get(_domain(url), {}) if isinstance(data.get(_domain(url), {}), dict) else {}
