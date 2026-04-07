from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from typing import Iterable

try:
    import pandas as pd
except Exception:  # pragma: no cover
    pd = None


# ==========================================================
# NORMALIZAÇÃO
# ==========================================================
def _strip_accents(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    return "".join(ch for ch in texto if not unicodedata.combining(ch))


def _normalizar(texto: str) -> str:
    texto = _strip_accents(str(texto or "").strip().lower())
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _tokens(texto: str) -> set[str]:
    normalizado = _normalizar(texto)
    if not normalizado:
        return set()
    return {t for t in normalizado.split(" ") if t}


# ==========================================================
# BASE DE SINÔNIMOS
# ==========================================================
CAMPO_SINONIMOS: dict[str, list[str]] = {
    "codigo": [
        "codigo", "codigo produto", "cod", "sku", "ref", "referencia",
        "id produto", "codigo interno", "codigo item", "part number", "pn"
    ],
    "descricao_curta": [
        "descricao curta", "desc curta", "descricao resumida", "resumo",
        "descricao pequena", "texto curto", "short description"
    ],
    "nome": [
        "nome", "titulo", "produto", "descricao", "descricao produto",
        "nome produto", "title", "product name"
    ],
    "preco_custo": [
        "preco custo", "preco de custo", "custo", "valor custo",
        "preco compra", "preco de compra", "compra", "cost"
    ],
    "preco": [
        "preco", "preco venda", "valor", "valor venda", "price",
        "preco final", "valor final"
    ],
    "estoque": [
        "estoque", "saldo", "qtd", "quantidade", "quant", "inventory",
        "stock", "saldo estoque", "disponivel"
    ],
    "gtin": [
        "gtin", "ean", "codigo barras", "cod barras", "barcode",
        "cbarra", "codigo de barras"
    ],
    "marca": [
        "marca", "fabricante", "brand", "manufacturer"
    ],
    "categoria": [
        "categoria", "departamento", "secao", "sessao", "grupo",
        "category", "tipo"
    ],
    "ncm": [
        "ncm", "classificacao fiscal", "classificacao"
    ],
    "cest": [
        "cest"
    ],
    "cfop": [
        "cfop"
    ],
    "unidade": [
        "unidade", "und", "un", "u m", "unid", "unit"
    ],
    "fornecedor": [
        "fornecedor", "supplier", "vendor"
    ],
    "cnpj_fornecedor": [
        "cnpj", "cnpj fornecedor", "documento fornecedor"
    ],
    "numero_nfe": [
        "numero nfe", "nfe", "nf e", "nota fiscal", "numero nota"
    ],
    "data_emissao": [
        "data emissao", "emissao", "data nota", "issue date", "date"
    ],
    "imagens": [
        "imagem", "imagens", "foto", "fotos", "image", "img", "url imagem"
    ],
    "deposito_id": [
        "deposito", "depósito", "warehouse", "local estoque", "almoxarifado"
    ],
    "origem": [
        "origem", "nacionalidade", "source"
    ],
}

ALIASES_DIRETOS: dict[str, str] = {}
for campo, sinonimos in CAMPO_SINONIMOS.items():
    for item in sinonimos:
        ALIASES_DIRETOS[_normalizar(item)] = campo
    ALIASES_DIRETOS[_normalizar(campo)] = campo


# ==========================================================
# HEURÍSTICAS
# ==========================================================
def _score_textos(texto_a: str, texto_b: str) -> float:
    a = _normalizar(texto_a)
    b = _normalizar(texto_b)

    if not a or not b:
        return 0.0

    if a == b:
        return 100.0

    score = 0.0

    alias_a = ALIASES_DIRETOS.get(a)
    alias_b = ALIASES_DIRETOS.get(b)
    if alias_a and alias_b and alias_a == alias_b:
        score += 90.0
    elif alias_a and alias_a == b:
        score += 95.0
    elif alias_b and alias_b == a:
        score += 95.0

    if a in b or b in a:
        score += 35.0

    ta = _tokens(a)
    tb = _tokens(b)
    if ta and tb:
        inter = len(ta & tb)
        union = len(ta | tb)
        score += (inter / max(union, 1)) * 40.0

    pesos = {
        "sku": 22.0,
        "codigo": 18.0,
        "ean": 22.0,
        "gtin": 22.0,
        "ncm": 22.0,
        "cest": 20.0,
        "cfop": 20.0,
        "marca": 18.0,
        "categoria": 18.0,
        "preco": 18.0,
        "custo": 18.0,
        "estoque": 20.0,
        "quantidade": 16.0,
        "unidade": 18.0,
        "descricao": 16.0,
        "titulo": 16.0,
        "imagem": 16.0,
        "fornecedor": 18.0,
        "cnpj": 22.0,
        "origem": 14.0,
        "deposito": 18.0,
        "nota": 14.0,
        "nfe": 20.0,
        "emissao": 18.0,
    }

    for token, peso in pesos.items():
        if token in ta and token in tb:
            score += peso

    return score


def _sugerir_campo_padrao(nome_coluna: str) -> str:
    nome = _normalizar(nome_coluna)
    if not nome:
        return ""

    if nome in ALIASES_DIRETOS:
        return ALIASES_DIRETOS[nome]

    melhor_campo = ""
    melhor_score = 0.0

    for campo, sinonimos in CAMPO_SINONIMOS.items():
        score_campo = _score_textos(nome, campo)

        for sinonimo in sinonimos:
            score_campo = max(score_campo, _score_textos(nome, sinonimo))

        if score_campo > melhor_score:
            melhor_score = score_campo
            melhor_campo = campo

    if melhor_score >= 26.0:
        return melhor_campo

    return ""


def _preparar_alvos(colunas_alvo: Iterable[str]) -> list[str]:
    vistos = set()
    saida = []
    for col in colunas_alvo or []:
        col_str = str(col).strip()
        if col_str and col_str not in vistos:
            vistos.add(col_str)
            saida.append(col_str)
    return saida


def _familia_semantica_de_alvo(alvo: str) -> str:
    alvo_norm = _normalizar(alvo)

    if alvo_norm in ALIASES_DIRETOS:
        return ALIASES_DIRETOS[alvo_norm]

    melhor_campo = ""
    melhor_score = 0.0

    for campo, sinonimos in CAMPO_SINONIMOS.items():
        score = _score_textos(alvo_norm, campo)

        for sinonimo in sinonimos:
            score = max(score, _score_textos(alvo_norm, sinonimo))

        if score > melhor_score:
            melhor_score = score
            melhor_campo = campo

    if melhor_score >= 18.0:
        return melhor_campo

    return ""


def _sugerir_para_alvos(nome_coluna: str, colunas_alvo: list[str]) -> str:
    if not colunas_alvo:
        return _sugerir_campo_padrao(nome_coluna)

    melhor_alvo = ""
    melhor_score = 0.0

    campo_padrao = _sugerir_campo_padrao(nome_coluna)

    for alvo in colunas_alvo:
        score = _score_textos(nome_coluna, alvo)
        alvo_norm = _normalizar(alvo)

        if campo_padrao:
            score = max(score, _score_textos(campo_padrao, alvo_norm) + 8.0)

            familia_alvo = _familia_semantica_de_alvo(alvo)
            if familia_alvo and familia_alvo == campo_padrao:
                score += 20.0

        if score > melhor_score:
            melhor_score = score
            melhor_alvo = alvo

    if melhor_score >= 18.0:
        return melhor_alvo

    return ""


# ==========================================================
# API PÚBLICA
# ==========================================================
def sugestao_automatica(entrada, colunas_alvo: list[str] | None = None):
    """
    Compatível com os dois usos do projeto:

    1) sugestao_automatica("nome da coluna") -> "campo_sugerido"
    2) sugestao_automatica(df_origem, colunas_alvo) -> {col_origem: col_alvo}
    """
    if isinstance(entrada, str):
        if colunas_alvo:
            return _sugerir_para_alvos(entrada, _preparar_alvos(colunas_alvo))
        return _sugerir_campo_padrao(entrada)

    if pd is not None and isinstance(entrada, pd.DataFrame):
        df_origem = entrada
        alvos = _preparar_alvos(colunas_alvo or [])

        if not alvos:
            sugestoes_padrao: dict[str, str] = {}
            for coluna in df_origem.columns:
                campo = _sugerir_campo_padrao(str(coluna))
                if campo:
                    sugestoes_padrao[str(coluna)] = campo
            return sugestoes_padrao

        sugestoes: dict[str, str] = {}
        alvos_usados: set[str] = set()

        for coluna in df_origem.columns:
            melhor = _sugerir_para_alvos(str(coluna), alvos)

            if melhor and melhor not in alvos_usados:
                sugestoes[str(coluna)] = melhor
                alvos_usados.add(melhor)
                continue

            candidatos_rank = []
            campo_padrao = _sugerir_campo_padrao(str(coluna))

            for alvo in alvos:
                if alvo in alvos_usados:
                    continue

                score = _score_textos(str(coluna), alvo)

                if campo_padrao:
                    score = max(score, _score_textos(campo_padrao, alvo) + 8.0)

                    familia_alvo = _familia_semantica_de_alvo(alvo)
                    if familia_alvo and familia_alvo == campo_padrao:
                        score += 20.0

                candidatos_rank.append((score, alvo))

            candidatos_rank.sort(reverse=True, key=lambda x: x[0])

            if candidatos_rank and candidatos_rank[0][0] >= 18.0:
                sugestoes[str(coluna)] = candidatos_rank[0][1]
                alvos_usados.add(candidatos_rank[0][1])

        return sugestoes

    return ""


# ==========================================================
# DEBUG OPCIONAL
# ==========================================================
def diagnostico_mapeamento(colunas_origem: list[str], colunas_alvo: list[str]) -> dict[str, list[dict[str, str]]]:
    """
    Função auxiliar opcional para debug local do mapeamento IA offline.
    Não interfere no layout.
    """
    alvos = _preparar_alvos(colunas_alvo)
    detalhes = []

    for col in colunas_origem or []:
        campo_padrao = _sugerir_campo_padrao(str(col))
        alvo = _sugerir_para_alvos(str(col), alvos)
        detalhes.append(
            {
                "origem": str(col),
                "campo_padrao": campo_padrao,
                "alvo_sugerido": alvo,
            }
        )

    agrupado = defaultdict(list)
    agrupado["itens"] = detalhes
    return dict(agrupado)
