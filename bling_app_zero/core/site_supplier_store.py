from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse


OUTPUT_DIR = Path("bling_app_zero/output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SUPPLIERS_FILE = OUTPUT_DIR / "fornecedores_usuario.json"


def _clean_text(value: Any) -> str:
    text = str(value or "").strip()
    return "" if text.lower() in {"none", "null", "nan"} else text


def _normalize_url(url: str) -> str:
    value = _clean_text(url)
    if not value:
        return ""
    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"
    return value.strip()


def _slugify(value: str) -> str:
    text = _clean_text(value).lower()
    text = re.sub(r"^https?://", "", text)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "fornecedor"


def _infer_name_from_url(url: str) -> str:
    try:
        hostname = (urlparse(_normalize_url(url)).hostname or "").replace("www.", "").strip()
        if not hostname:
            return "Fornecedor"
        parts = [p for p in hostname.split(".") if p and p not in {"com", "br", "net", "org"}]
        if not parts:
            return "Fornecedor"
        return " ".join(p.capitalize() for p in parts[:2])
    except Exception:
        return "Fornecedor"


def _default_payload() -> Dict[str, Any]:
    return {
        "fornecedores": [],
    }


def _normalize_supplier(item: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(item, dict):
        return None

    nome = _clean_text(item.get("nome"))
    url_base = _normalize_url(item.get("url_base"))
    login_url = _normalize_url(item.get("login_url"))
    products_url = _normalize_url(item.get("products_url"))
    auth_mode = _clean_text(item.get("auth_mode"))
    observacoes = _clean_text(item.get("observacoes"))
    slug = _clean_text(item.get("slug"))

    if not nome and url_base:
        nome = _infer_name_from_url(url_base)

    if not slug:
        slug = _slugify(nome or url_base)

    if not nome or not url_base:
        return None

    return {
        "slug": slug,
        "nome": nome,
        "url_base": url_base,
        "login_url": login_url,
        "products_url": products_url,
        "auth_mode": auth_mode,
        "observacoes": observacoes,
    }


def load_site_suppliers() -> List[Dict[str, Any]]:
    try:
        if not SUPPLIERS_FILE.exists():
            save_site_suppliers([])
            return []

        raw = SUPPLIERS_FILE.read_text(encoding="utf-8")

        if not raw.strip():
            save_site_suppliers([])
            return []

        data = json.loads(raw)
    except Exception:
        save_site_suppliers([])
        return []

    if not isinstance(data, dict):
        save_site_suppliers([])
        return []

    fornecedores = data.get("fornecedores", [])
    if not isinstance(fornecedores, list):
        save_site_suppliers([])
        return []

    normalizados: List[Dict[str, Any]] = []
    vistos = set()

    for item in fornecedores:
        fornecedor = _normalize_supplier(item)
        if not fornecedor:
            continue

        chave = fornecedor["slug"]
        if chave in vistos:
            continue

        vistos.add(chave)
        normalizados.append(fornecedor)

    normalizados.sort(key=lambda x: x.get("nome", "").lower())
    save_site_suppliers(normalizados)
    return normalizados


def save_site_suppliers(fornecedores: List[Dict[str, Any]]) -> None:
    payload = _default_payload()
    payload["fornecedores"] = fornecedores
    SUPPLIERS_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def list_site_suppliers() -> List[Dict[str, Any]]:
    return load_site_suppliers()


def get_site_supplier_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    slug_clean = _clean_text(slug)
    if not slug_clean:
        return None

    for fornecedor in load_site_suppliers():
        if fornecedor.get("slug") == slug_clean:
            return fornecedor

    return None


def upsert_site_supplier(
    *,
    nome: str,
    url_base: str,
    login_url: str = "",
    products_url: str = "",
    auth_mode: str = "",
    observacoes: str = "",
) -> Dict[str, Any]:
    novo = _normalize_supplier(
        {
            "nome": nome,
            "url_base": url_base,
            "login_url": login_url,
            "products_url": products_url,
            "auth_mode": auth_mode,
            "observacoes": observacoes,
        }
    )
    if not novo:
        raise ValueError("Fornecedor inválido. Informe nome e URL base.")

    fornecedores = load_site_suppliers()
    atualizados: List[Dict[str, Any]] = []
    substituido = False

    for item in fornecedores:
        mesma_slug = item.get("slug") == novo["slug"]
        mesma_url = item.get("url_base") == novo["url_base"]

        if mesma_slug or mesma_url:
            atualizados.append(novo)
            substituido = True
        else:
            atualizados.append(item)

    if not substituido:
        atualizados.append(novo)

    atualizados.sort(key=lambda x: x.get("nome", "").lower())
    save_site_suppliers(atualizados)
    return novo


def delete_site_supplier(slug: str) -> bool:
    slug_clean = _clean_text(slug)
    if not slug_clean:
        return False

    fornecedores = load_site_suppliers()
    novos = [item for item in fornecedores if item.get("slug") != slug_clean]

    if len(novos) == len(fornecedores):
        return False

    save_site_suppliers(novos)
    return True


def get_site_supplier_options() -> List[Dict[str, str]]:
    opcoes = []
    for fornecedor in load_site_suppliers():
        opcoes.append(
            {
                "label": fornecedor.get("nome", "Fornecedor"),
                "value": fornecedor.get("slug", ""),
            }
        )
    return opcoes
