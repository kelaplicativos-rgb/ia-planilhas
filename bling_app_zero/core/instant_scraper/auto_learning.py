# bling_app_zero/core/instant_scraper/auto_learning.py

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd


LEARNING_DIR = Path("bling_app_zero/output/auto_learning")
LEARNING_FILE = LEARNING_DIR / "site_patterns.json"


COLUNAS_ALVO = {
    "nome": ["nome", "descrição", "descricao", "produto", "title"],
    "preco": ["preco", "preço", "valor", "price"],
    "url_produto": ["url_produto", "url", "link", "produto_url"],
    "imagem": ["imagem", "imagens", "image", "img", "fotos"],
    "sku": ["sku", "codigo", "código", "cod", "referencia", "referência"],
    "gtin": ["gtin", "ean", "codigo_barras", "código de barras"],
    "estoque": ["estoque", "stock", "availability", "disponibilidade"],
    "categoria": ["categoria", "category", "breadcrumb"],
    "marca": ["marca", "brand", "fabricante"],
}


def _safe_domain(url: str) -> str:
    try:
        host = urlparse(str(url or "").strip()).netloc.lower()
        return host.replace("www.", "") or "desconhecido"
    except Exception:
        return "desconhecido"


def _read_memory() -> dict:
    try:
        if LEARNING_FILE.exists():
            return json.loads(LEARNING_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _write_memory(data: dict) -> None:
    try:
        LEARNING_DIR.mkdir(parents=True, exist_ok=True)
        LEARNING_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _normalizar_coluna(nome: object) -> str:
    return str(nome or "").strip().lower()


def _score_coluna(df: pd.DataFrame, coluna: str) -> int:
    if coluna not in df.columns:
        return 0
    serie = df[coluna].astype(str).fillna("").str.strip()
    return int(serie.ne("").sum())


def aprender_padrao(url: str, df: pd.DataFrame, fonte: str = "instant_scraper") -> None:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return

    dominio = _safe_domain(url)
    memoria = _read_memory()
    registro = memoria.get(dominio, {})

    colunas = [str(c) for c in df.columns]
    mapa: dict[str, str] = {}

    for alvo, candidatos in COLUNAS_ALVO.items():
        melhor_coluna = ""
        melhor_score = 0
        for coluna in colunas:
            coluna_norm = _normalizar_coluna(coluna)
            if any(cand in coluna_norm for cand in candidatos):
                score = _score_coluna(df, coluna)
                if score > melhor_score:
                    melhor_score = score
                    melhor_coluna = coluna
        if melhor_coluna:
            mapa[alvo] = melhor_coluna

    historico = registro.get("historico", [])
    historico.append({
        "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "url": url,
        "fonte": fonte,
        "linhas": int(len(df)),
        "colunas": colunas,
        "mapa": mapa,
    })

    registro.update({
        "dominio": dominio,
        "ultima_url": url,
        "ultima_atualizacao": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_execucoes": int(registro.get("total_execucoes", 0)) + 1,
        "ultimo_total_linhas": int(len(df)),
        "mapa_preferido": mapa or registro.get("mapa_preferido", {}),
        "historico": historico[-20:],
    })

    memoria[dominio] = registro
    _write_memory(memoria)


def obter_padrao(url: str) -> dict:
    dominio = _safe_domain(url)
    return _read_memory().get(dominio, {})


def aplicar_padrao_aprendido(url: str, df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()

    padrao = obter_padrao(url)
    mapa = padrao.get("mapa_preferido", {}) if isinstance(padrao, dict) else {}
    if not mapa:
        return df.copy().fillna("")

    base = df.copy().fillna("")
    renames = {}
    destino_por_alvo = {
        "nome": "nome",
        "preco": "preco",
        "url_produto": "url_produto",
        "imagem": "imagem",
        "sku": "sku",
        "gtin": "gtin",
        "estoque": "estoque",
        "categoria": "categoria",
        "marca": "marca",
    }

    for alvo, coluna in mapa.items():
        destino = destino_por_alvo.get(str(alvo))
        if destino and coluna in base.columns and destino not in base.columns:
            renames[coluna] = destino

    if renames:
        base = base.rename(columns=renames)

    return base.fillna("")
