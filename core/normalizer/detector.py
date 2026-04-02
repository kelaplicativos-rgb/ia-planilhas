from core.utils import limpar


MAPA_FIXO = {
    "codigo": ["codigo", "sku", "id"],
    "produto": ["descricao", "produto", "nome"],
    "preco": ["preco", "valor"],
    "preco_custo": ["custo", "compra"],
    "estoque": ["estoque", "saldo"],
    "gtin": ["gtin", "ean", "codigo de barras"],
    "marca": ["marca"],
    "imagem": ["imagem", "foto", "url imagem"],
    "link": ["link", "produto_url", "url"],
    "descricao_complementar": ["descricao complementar", "descricao longa"],
    "descricao_curta": ["descricao curta", "resumo"],
}


def detectar_colunas_inteligente(df, mapa_ia=None):
    colunas = list(df.columns)

    resultado = {}

    # =========================
    # 1. IA
    # =========================
    if mapa_ia:
        for k, v in mapa_ia.items():
            if v in colunas:
                resultado[k] = v

    # =========================
    # 2. FIXO (fallback)
    # =========================
    for campo, palavras in MAPA_FIXO.items():

        if campo in resultado:
            continue

        for col in colunas:
            nome = limpar(col).lower()

            for p in palavras:
                if p in nome:
                    resultado[campo] = col
                    break

    # =========================
    # 3. CORREÇÕES CRÍTICAS
    # =========================

    # ❌ remover link errado (vídeo)
    if "link" in resultado:
        col = resultado["link"].lower()
        if "video" in col or "youtube" in col:
            resultado["link"] = None

    # 🔥 garantir descrição curta
    if not resultado.get("descricao_curta"):
        if resultado.get("produto"):
            resultado["descricao_curta"] = resultado["produto"]

    return resultado
