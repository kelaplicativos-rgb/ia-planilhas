from __future__ import annotations

import pandas as pd


# ==========================================================
# 🧠 BASE DE INTELIGÊNCIA
# ==========================================================
MAPA_INTELIGENTE = {
    "descricao": ["descricao", "descrição", "nome", "produto", "titulo", "title"],
    "preco": ["preco", "preço", "valor", "price", "vlr"],
    "estoque": ["estoque", "quantidade", "qtd", "saldo", "stock", "inventory"],
    "gtin": ["gtin", "ean", "codigo de barras", "código de barras", "barcode"],
    "marca": ["marca", "brand"],
    "categoria": ["categoria", "departamento", "grupo"],
    "ncm": ["ncm"],
}


def _normalizar(txt: str) -> str:
    return str(txt).lower().strip()


def _score_coluna(destino: str, origem: str) -> int:
    destino = _normalizar(destino)
    origem = _normalizar(origem)

    score = 0

    # match direto
    if destino == origem:
        score += 100

    # contém texto
    if destino in origem:
        score += 50

    # mapa inteligente
    for chave, palavras in MAPA_INTELIGENTE.items():
        if chave in destino:
            for p in palavras:
                if p in origem:
                    score += 30

    return score


# ==========================================================
# 🚀 IA PRINCIPAL
# ==========================================================
def sugestao_automatica(df: pd.DataFrame, colunas_destino: list[str] | None = None) -> dict:

    if df is None or df.empty:
        return {}

    colunas_origem = list(df.columns)

    if not colunas_destino:
        return {col: col for col in colunas_origem}

    sugestoes = {}

    for destino in colunas_destino:
        melhor_match = None
        melhor_score = 0

        for origem in colunas_origem:
            score = _score_coluna(destino, origem)

            if score > melhor_score:
                melhor_score = score
                melhor_match = origem

        # só aceita se tiver um mínimo de confiança
        if melhor_match and melhor_score >= 30:
            sugestoes[destino] = melhor_match

    return sugestoes
