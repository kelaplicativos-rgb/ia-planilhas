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
    "ncm": ["ncm"],
}

VISUAL_TO_ALVO = {
    "codigo": "sku",
    "descricao": "nome",
    "preco": "preco",
    "estoque": "estoque",
    "gtin": "gtin",
    "imagens": "imagem",
    "url_produto": "url_produto",
    "marca": "marca",
    "categoria": "categoria",
    "ncm": "ncm",
}

DESTINO_POR_ALVO = {
    "nome": "nome",
    "preco": "preco",
    "url_produto": "url_produto",
    "imagem": "imagem",
    "sku": "sku",
    "gtin": "gtin",
    "estoque": "estoque",
    "categoria": "categoria",
    "marca": "marca",
    "ncm": "ncm",
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


def _mapa_heuristico(df: pd.DataFrame) -> dict[str, str]:
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
    return mapa


def aprender_padrao(url: str, df: pd.DataFrame, fonte: str = "instant_scraper") -> None:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return

    dominio = _safe_domain(url)
    memoria = _read_memory()
    registro = memoria.get(dominio, {})
    colunas = [str(c) for c in df.columns]
    mapa = _mapa_heuristico(df)

    historico = registro.get("historico", [])
    historico.append({
        "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "url": url,
        "fonte": fonte,
        "linhas": int(len(df)),
        "colunas": colunas,
        "mapa": mapa,
    })

    mapa_manual = registro.get("mapa_manual_preferido", {})
    mapa_preferido = mapa_manual or mapa or registro.get("mapa_preferido", {})

    registro.update({
        "dominio": dominio,
        "ultima_url": url,
        "ultima_atualizacao": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_execucoes": int(registro.get("total_execucoes", 0)) + 1,
        "ultimo_total_linhas": int(len(df)),
        "mapa_preferido": mapa_preferido,
        "mapa_heuristico": mapa,
        "historico": historico[-20:],
    })

    memoria[dominio] = registro
    _write_memory(memoria)


def aprender_padrao_visual(url: str, papeis_visuais: dict[str, str], df: pd.DataFrame | None = None) -> None:
    """
    Salva uma decisão manual do painel BLINGAI PRO como memória do domínio.

    Entrada esperada:
        {"coluna_original": "descricao|preco|gtin|imagens|..."}

    A memória visual tem prioridade sobre a heurística porque foi confirmada pelo usuário.
    """
    if not isinstance(papeis_visuais, dict) or not papeis_visuais:
        return

    dominio = _safe_domain(url)
    memoria = _read_memory()
    registro = memoria.get(dominio, {})

    mapa_manual: dict[str, str] = {}
    for coluna, papel_visual in papeis_visuais.items():
        coluna = str(coluna or "").strip()
        papel_visual = str(papel_visual or "").strip()
        alvo = VISUAL_TO_ALVO.get(papel_visual)
        if coluna and alvo:
            mapa_manual[alvo] = coluna

    if not mapa_manual:
        return

    colunas = [str(c) for c in df.columns] if isinstance(df, pd.DataFrame) else []
    historico_visual = registro.get("historico_visual", [])
    historico_visual.append({
        "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "url": url,
        "colunas": colunas,
        "papeis_visuais": papeis_visuais,
        "mapa_manual": mapa_manual,
    })

    registro.update({
        "dominio": dominio,
        "ultima_url": url,
        "ultima_atualizacao": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mapa_manual_preferido": mapa_manual,
        "mapa_preferido": mapa_manual,
        "historico_visual": historico_visual[-20:],
        "memoria_visual_ativa": True,
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
    mapa = padrao.get("mapa_manual_preferido", {}) or padrao.get("mapa_preferido", {}) if isinstance(padrao, dict) else {}
    if not mapa:
        return df.copy().fillna("")

    base = df.copy().fillna("")
    renames = {}

    for alvo, coluna in mapa.items():
        destino = DESTINO_POR_ALVO.get(str(alvo))
        if destino and coluna in base.columns and destino not in base.columns:
            renames[coluna] = destino

    if renames:
        base = base.rename(columns=renames)

    return base.fillna("")


def listar_memorias() -> dict:
    return _read_memory()


def apagar_memoria_dominio(url: str) -> bool:
    dominio = _safe_domain(url)
    memoria = _read_memory()
    if dominio not in memoria:
        return False
    memoria.pop(dominio, None)
    _write_memory(memoria)
    return True
