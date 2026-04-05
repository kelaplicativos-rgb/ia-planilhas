# bling_app_zero/core/mapeamento_ia.py

from typing import Dict, List, Tuple
import re
import unicodedata
from difflib import SequenceMatcher

# =========================
# NORMALIZAÇÃO
# =========================

def normalizar_texto(texto: str) -> str:
    if not texto:
        return ""

    texto = texto.lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ascii", "ignore").decode("utf-8")
    texto = re.sub(r"[^a-z0-9 ]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()

    return texto


# =========================
# DICIONÁRIO INTELIGENTE
# =========================

DICIONARIO_BASE = {
    "nome": ["descricao", "produto", "nome produto", "descricao produto", "xprod"],
    "preco": ["valor", "preco", "vlr", "valor unitario", "vprod", "valor venda"],
    "custo": ["custo", "valor custo", "vlr custo"],
    "sku": ["codigo", "referencia", "sku", "cod produto", "cprod"],
    "gtin": ["ean", "gtin", "codigo barras", "cean"],
    "ncm": ["ncm"],
    "marca": ["marca", "brand"],
    "estoque": ["estoque", "quantidade", "qtd", "qcom"],
    "categoria": ["categoria", "grupo"],
    "peso": ["peso", "peso liquido"],
}


# =========================
# SIMILARIDADE
# =========================

def similaridade(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


# =========================
# MATCH INTELIGENTE
# =========================

def match_coluna(coluna: str, campos_destino: List[str]) -> Tuple[str, float]:
    col_norm = normalizar_texto(coluna)

    melhor_match = None
    melhor_score = 0

    for campo in campos_destino:
        campo_norm = normalizar_texto(campo)

        # comparação direta
        score = similaridade(col_norm, campo_norm)

        # comparação com dicionário
        sinonimos = DICIONARIO_BASE.get(campo, [])
        for s in sinonimos:
            s_norm = normalizar_texto(s)
            score = max(score, similaridade(col_norm, s_norm))

        if score > melhor_score:
            melhor_score = score
            melhor_match = campo

    return melhor_match, melhor_score


# =========================
# REGRAS XML
# =========================

def aplicar_regras_xml(coluna: str) -> str:
    col = coluna.lower()

    if "xprod" in col:
        return "nome"
    if "vprod" in col:
        return "preco"
    if "cean" in col:
        return "gtin"
    if "ncm" in col:
        return "ncm"
    if "qcom" in col:
        return "estoque"
    if "cprod" in col:
        return "sku"

    return None


# =========================
# MOTOR PRINCIPAL
# =========================

def mapear_colunas_ia(
    colunas_origem: List[str],
    colunas_destino: List[str],
) -> Dict[str, Dict]:
    
    resultado = {}

    for col in colunas_origem:
        # 1. regra XML primeiro
        regra_xml = aplicar_regras_xml(col)

        if regra_xml:
            resultado[col] = {
                "destino": regra_xml,
                "score": 0.95,
                "origem": "xml_rule"
            }
            continue

        # 2. match inteligente
        destino, score = match_coluna(col, colunas_destino)

        resultado[col] = {
            "destino": destino if score > 0.5 else None,
            "score": round(score, 2),
            "origem": "ia_local"
        }

    return resultado


# =========================
# FALLBACK IA EXTERNA (OPCIONAL)
# =========================

def fallback_openai(colunas_origem, colunas_destino):
    """
    FUTURO:
    integrar com OpenAI para melhorar casos difíceis
    """
    # placeholder (não quebra nada)
    return {}
