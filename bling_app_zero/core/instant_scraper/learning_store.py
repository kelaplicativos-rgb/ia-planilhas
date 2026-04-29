# bling_app_zero/core/instant_scraper/learning_store.py

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlparse


STORE_PATH = Path(".cache/instant_scraper_learning.json")


def dominio_da_url(url: str) -> str:
    try:
        host = urlparse(str(url or "").strip()).netloc.lower()
        return host.replace("www.", "")
    except Exception:
        return ""


def _carregar_store() -> Dict[str, Any]:
    try:
        if STORE_PATH.exists():
            return json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _salvar_store(data: Dict[str, Any]) -> None:
    try:
        STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STORE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def salvar_aprendizado(url: str, opcao_id: int, score: int = 0, pattern: Any = "") -> None:
    dominio = dominio_da_url(url)
    if not dominio:
        return

    data = _carregar_store()
    data[dominio] = {
        "opcao_id": int(opcao_id),
        "score": int(score or 0),
        "pattern": str(pattern or ""),
    }
    _salvar_store(data)


def obter_aprendizado(url: str) -> Dict[str, Any]:
    dominio = dominio_da_url(url)
    if not dominio:
        return {}

    data = _carregar_store()
    valor = data.get(dominio, {})
    return valor if isinstance(valor, dict) else {}


def limpar_aprendizado(url: str) -> None:
    dominio = dominio_da_url(url)
    if not dominio:
        return

    data = _carregar_store()
    data.pop(dominio, None)
    _salvar_store(data)
