
from __future__ import annotations

import re
import unicodedata
from typing import Any


def _valor_vazio(valor: Any) -> bool:
    if valor is None:
        return True

    texto = str(valor).strip()
    return texto == "" or texto.lower() in {"nan", "none", "nat", ""}


def normalizar_texto(valor: Any) -> str:
    if _valor_vazio(valor):
        return ""
    return str(valor).strip()


def _remover_acentos(texto: str) -> str:
    texto_nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(ch for ch in texto_nfkd if not unicodedata.combining(ch))


def normalizar_coluna_busca(valor: Any) -> str:
    texto = normalizar_texto(valor).lower()
    texto = _remover_acentos(texto)
    texto = re.sub(r"[_\-/().]+", " ", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def safe_lower(valor: Any) -> str:
    return normalizar_texto(valor).lower()
