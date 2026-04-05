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

    texto = str(texto).lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ascii", "ignore").decode("utf-8")
    texto = re.sub(r"[^a-z0-9 ]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


# =========================
# DICIONÁRIO INTELIGENTE
# =========================
DICIONARIO_BASE = {
    "nome": [
        "descricao",
        "produto",
        "nome produto",
        "descricao produto",
        "xprod",
        "titulo",
        "nome",
    ],
    "preco": [
        "valor",
        "preco",
        "vlr",
        "valor unitario",
        "vprod",
        "valor venda",
        "preco venda",
    ],
    "custo": [
        "custo",
        "valor custo",
        "vlr custo",
        "preco custo",
        "preco de custo",
        "custo compra",
    ],
    "sku": [
        "codigo",
        "referencia",
        "sku",
        "cod produto",
        "cprod",
        "codigo produto",
    ],
    "gtin": [
        "ean",
        "gtin",
        "codigo barras",
        "codigo de barras",
        "cean",
        "barcode",
    ],
    "ncm": [
        "ncm",
    ],
    "marca": [
        "marca",
        "brand",
        "fabricante",
    ],
    "estoque": [
        "estoque",
        "quantidade",
        "qtd",
        "qcom",
        "saldo",
    ],
    "categoria": [
        "categoria",
        "grupo",
        "departamento",
        "secao",
    ],
    "peso": [
        "peso",
        "peso liquido",
        "peso bruto",
    ],
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
    melhor_score = 0.0

    for campo in campos_destino:
        campo_norm = normalizar_texto(campo)

        score = similaridade(col_norm, campo_norm)

        sinonimos = DICIONARIO_BASE.get(campo, [])
        for sinonimo in sinonimos:
            s_norm = normalizar_texto(sinonimo)
            score = max(score, similaridade(col_norm, s_norm))

        if score > melhor_score:
            melhor_score = score
            melhor_match = campo

    return melhor_match, melhor_score


# =========================
# REGRAS XML
# =========================
def aplicar_regras_xml(coluna: str) -> str | None:
    col = normalizar_texto(coluna)

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
# PRIORIZAÇÃO POR NOME
# =========================
def _bonus_prioridade(coluna: str, destino: str) -> float:
    col = normalizar_texto(coluna)

    regras = {
        "nome": ["nome", "produto", "descricao", "xprod", "titulo"],
        "preco": ["preco", "valor", "vprod", "valor unitario"],
        "custo": ["custo", "preco custo", "valor custo"],
        "sku": ["sku", "codigo", "referencia", "cprod"],
        "gtin": ["gtin", "ean", "barcode", "cean", "codigo barras"],
        "ncm": ["ncm"],
        "marca": ["marca", "brand", "fabricante"],
        "estoque": ["estoque", "quantidade", "qtd", "qcom", "saldo"],
        "categoria": ["categoria", "grupo", "departamento", "secao"],
        "peso": ["peso"],
    }

    bonus = 0.0
    for termo in regras.get(destino, []):
        if termo in col:
            bonus += 0.08

    return min(bonus, 0.24)


# =========================
# DEDUPLICAÇÃO DE DESTINOS
# =========================
def _deduplicar_destinos(resultado: Dict[str, Dict]) -> Dict[str, Dict]:
    """
    Garante que apenas uma coluna fique responsável por cada destino.
    Se houver colisão, mantém a coluna com melhor score ajustado.
    """
    melhor_por_destino: Dict[str, Tuple[str, float]] = {}

    for coluna, dados in resultado.items():
        destino = dados.get("destino")
        score = float(dados.get("score", 0) or 0)

        if not destino:
            continue

        score_ajustado = score + _bonus_prioridade(coluna, destino)

        if destino not in melhor_por_destino:
            melhor_por_destino[destino] = (coluna, score_ajustado)
            continue

        coluna_atual, score_atual = melhor_por_destino[destino]
        if score_ajustado > score_atual:
            melhor_por_destino[destino] = (coluna, score_ajustado)

    colunas_vencedoras = {coluna for coluna, _ in melhor_por_destino.values()}

    resultado_final: Dict[str, Dict] = {}
    for coluna, dados in resultado.items():
        dados_novos = dict(dados)

        if dados_novos.get("destino") and coluna not in colunas_vencedoras:
            dados_novos["destino"] = None
            dados_novos["origem"] = "descartado_colisao"

        resultado_final[coluna] = dados_novos

    return resultado_final


# =========================
# MOTOR PRINCIPAL
# =========================
def mapear_colunas_ia(
    colunas_origem: List[str],
    colunas_destino: List[str],
) -> Dict[str, Dict]:
    resultado: Dict[str, Dict] = {}

    for col in colunas_origem:
        regra_xml = aplicar_regras_xml(col)
        if regra_xml:
            resultado[col] = {
                "destino": regra_xml,
                "score": 0.95,
                "origem": "xml_rule",
            }
            continue

        destino, score = match_coluna(col, colunas_destino)

        resultado[col] = {
            "destino": destino if score > 0.5 else None,
            "score": round(score, 2),
            "origem": "ia_local",
        }

    return _deduplicar_destinos(resultado)


# =========================
# FALLBACK IA EXTERNA (OPCIONAL)
# =========================
def fallback_openai(colunas_origem, colunas_destino):
    """
    FUTURO: integrar com OpenAI para melhorar casos difíceis.
    """
    return {}
