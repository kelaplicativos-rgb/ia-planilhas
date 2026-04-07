from __future__ import annotations

import re
import unicodedata
from typing import Any


# =========================================================
# LIMPEZA DE TEXTO
# =========================================================
def limpar_texto(valor: Any) -> str:
    """
    Limpa textos removendo quebras, espaços duplicados e valores nulos.
    """
    try:
        if valor is None:
            return ""

        try:
            if hasattr(valor, "isna") and valor.isna():
                return ""
        except Exception:
            pass

        texto = str(valor)

        if texto.strip().lower() in {"nan", "none", "null", "<na>"}:
            return ""

        texto = texto.replace("\n", " ").replace("\r", " ").replace("\t", " ")
        texto = re.sub(r"\s+", " ", texto)

        return texto.strip()
    except Exception:
        return ""


# =========================================================
# REMOVER ACENTOS
# =========================================================
def remover_acentos(texto: str) -> str:
    """
    Remove acentos de um texto.
    """
    try:
        if not texto:
            return ""

        return "".join(
            c
            for c in unicodedata.normalize("NFKD", str(texto))
            if not unicodedata.combining(c)
        )
    except Exception:
        return ""


# =========================================================
# NORMALIZAR NOME DE COLUNA (SLUG)
# =========================================================
def slug_coluna(nome: str) -> str:
    """
    Normaliza nome de coluna para comparação inteligente.
    Ex: 'Descrição do Produto' -> 'descricao produto'
    """
    try:
        nome_limpo = limpar_texto(nome)

        if not nome_limpo:
            return ""

        nome_limpo = remover_acentos(nome_limpo).lower()

        nome_limpo = (
            nome_limpo.replace("/", " ")
            .replace("\\", " ")
            .replace("-", " ")
            .replace("_", " ")
        )

        nome_limpo = re.sub(r"[^a-z0-9 ]+", "", nome_limpo)
        nome_limpo = re.sub(r"\s+", " ", nome_limpo)

        return nome_limpo.strip()
    except Exception:
        return ""


# =========================================================
# PREVIEW SEGURO (para UI)
# =========================================================
def formatar_preview_valor(valor: Any, limite: int = 90) -> str:
    """
    Limita tamanho do texto para preview no app.
    """
    try:
        txt = limpar_texto(valor)

        if limite <= 0:
            return txt

        if len(txt) > limite:
            return txt[: max(0, limite - 3)] + "..."

        return txt
    except Exception:
        return ""


# =========================================================
# SOMENTE DÍGITOS
# =========================================================
def somente_digitos(valor: Any) -> str:
    """
    Remove tudo que não for número.
    """
    try:
        return re.sub(r"\D+", "", limpar_texto(valor))
    except Exception:
        return ""


# =========================================================
# EXPORTS
# =========================================================
__all__ = [
    "limpar_texto",
    "remover_acentos",
    "slug_coluna",
    "formatar_preview_valor",
    "somente_digitos",
]
