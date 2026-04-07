from __future__ import annotations

import json
import os
import re
from html import unescape
from typing import Any
from urllib.parse import urlparse


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.normpath(os.path.join(BASE_DIR, "..", "output"))
FORNECEDORES_DB_PATH = os.path.join(OUTPUT_DIR, "fornecedores_adaptativos.json")


# ==========================================================
# BASE / ARQUIVO
# ==========================================================
def garantir_pasta_fornecedores() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def texto_limpo_fornecedor(valor: Any) -> str:
    texto = unescape(str(valor or ""))
    texto = texto.replace("\xa0", " ")
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def slug_fornecedor(texto: str) -> str:
    texto = texto_limpo_fornecedor(texto).lower()
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def safe_float_fornecedor(valor: Any, default: float = 0.0) -> float:
    try:
        return float(valor)
    except Exception:
        return default


def safe_bool_fornecedor(valor: Any, default: bool = False) -> bool:
    if isinstance(valor, bool):
        return valor

    texto = str(valor or "").strip().lower()
    if texto in {"1", "true", "sim", "yes", "y"}:
        return True
    if texto in {"0", "false", "nao", "não", "no", "n"}:
        return False

    return default


def safe_dict_fornecedor(valor: Any) -> dict[str, Any]:
    return valor if isinstance(valor, dict) else {}


def load_fornecedores_db() -> dict[str, Any]:
    garantir_pasta_fornecedores()

    if not os.path.exists(FORNECEDORES_DB_PATH):
        return {}

    try:
        with open(FORNECEDORES_DB_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_fornecedores_db(data: dict[str, Any]) -> None:
    garantir_pasta_fornecedores()
    with open(FORNECEDORES_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ==========================================================
# DOMÍNIO
# ==========================================================
def extrair_dominio(url: str) -> str:
    try:
        host = urlparse(str(url or "").strip()).netloc.lower()
        host = host.replace("www.", "").strip()
        return host
    except Exception:
        return ""


# ==========================================================
# BANCO DE FORNECEDORES
# ==========================================================
def carregar_fornecedor(dominio: str) -> dict[str, Any]:
    dominio = extrair_dominio(dominio)
    if not dominio:
        return {}

    db = load_fornecedores_db()
    item = db.get(dominio, {})
    return item if isinstance(item, dict) else {}


def listar_fornecedores() -> dict[str, Any]:
    return load_fornecedores_db()


def salvar_fornecedor(
    dominio: str,
    config: dict[str, Any],
    sobrescrever: bool = False,
) -> bool:
    dominio = extrair_dominio(dominio)
    if not dominio or not isinstance(config, dict) or not config:
        return False

    db = load_fornecedores_db()

    if dominio in db and not sobrescrever:
        return False

    atual = db.get(dominio, {}) if isinstance(db.get(dominio, {}), dict) else {}

    novo_item = {
        "dominio": dominio,
        "tipo": str(config.get("tipo", atual.get("tipo", "generico")) or "generico").strip(),
        "confianca": safe_float_fornecedor(
            config.get("confianca", atual.get("confianca", 0.0)),
            0.0,
        ),
        "seletores": safe_dict_fornecedor(
            config.get("seletores", atual.get("seletores", {}))
        ) or {},
        "links": safe_dict_fornecedor(
            config.get("links", atual.get("links", {}))
        ) or {},
        "imagens_multiplas": safe_bool_fornecedor(
            config.get("imagens_multiplas", atual.get("imagens_multiplas", True)),
            True,
        ),
        "origem": str(
            config.get("origem", atual.get("origem", "ia_adaptativa")) or "ia_adaptativa"
        ).strip(),
        "principal": safe_bool_fornecedor(
            config.get("principal", atual.get("principal", False)),
            False,
        ),
    }

    db[dominio] = novo_item
    save_fornecedores_db(db)
    return True


def atualizar_fornecedor(
    dominio: str,
    patch: dict[str, Any],
) -> bool:
    dominio = extrair_dominio(dominio)
    if not dominio or not isinstance(patch, dict):
        return False

    db = load_fornecedores_db()
    atual = db.get(dominio, {})
    if not isinstance(atual, dict):
        atual = {}

    if "seletores" in patch and isinstance(patch["seletores"], dict):
        seletores = atual.get("seletores", {})
        if not isinstance(seletores, dict):
            seletores = {}
        for chave, valor in patch["seletores"].items():
            if valor is not None:
                seletores[chave] = valor
        atual["seletores"] = seletores

    if "links" in patch and isinstance(patch["links"], dict):
        links = atual.get("links", {})
        if not isinstance(links, dict):
            links = {}
        for chave, valor in patch["links"].items():
            if valor is not None:
                links[chave] = valor
        atual["links"] = links

    for chave in ["tipo", "origem"]:
        if chave in patch and patch.get(chave) is not None:
            atual[chave] = patch.get(chave)

    if "confianca" in patch and patch.get("confianca") is not None:
        atual["confianca"] = safe_float_fornecedor(
            patch.get("confianca"),
            atual.get("confianca", 0.0),
        )

    if "imagens_multiplas" in patch:
        atual["imagens_multiplas"] = safe_bool_fornecedor(
            patch.get("imagens_multiplas"),
            atual.get("imagens_multiplas", True),
        )

    if "principal" in patch:
        atual["principal"] = safe_bool_fornecedor(
            patch.get("principal"),
            atual.get("principal", False),
        )

    db[dominio] = atual
    save_fornecedores_db(db)
    return True
