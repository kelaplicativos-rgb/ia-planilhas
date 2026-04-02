from core.utils import limpar


MAPA_FIXO = {
    "codigo": [
        "codigo",
        "código",
        "codigo do produto",
        "código do produto",
        "sku",
        "referencia",
        "referência",
        "ref",
    ],
    "produto": [
        "descricao",
        "descrição",
        "descricao do produto",
        "descrição do produto",
        "produto",
        "nome",
        "titulo",
        "title",
    ],
    "preco": [
        "preco",
        "preço",
        "valor",
        "preco de venda",
        "preço de venda",
    ],
    "preco_custo": [
        "preco de custo",
        "preço de custo",
        "preco de compra",
        "preço de compra",
        "custo",
        "compra",
    ],
    "estoque": [
        "estoque",
        "saldo",
        "quantidade",
        "qtd",
    ],
    "gtin": [
        "gtin",
        "ean",
        "gtin/ean",
        "codigo de barras",
        "código de barras",
    ],
    "marca": [
        "marca",
        "fabricante",
        "brand",
    ],
    "imagem": [
        "imagem",
        "foto",
        "url imagem",
        "url imagens externas",
        "imagem principal",
        "foto principal",
    ],
    "descricao_complementar": [
        "descricao complementar",
        "descrição complementar",
        "descricao longa",
        "descrição longa",
        "descricao completa",
        "descrição completa",
    ],
    "descricao_curta": [
        "descricao curta",
        "descrição curta",
        "resumo",
    ],
    "ncm": ["ncm"],
    "origem": ["origem"],
    "peso_liquido": ["peso liquido", "peso líquido", "peso líquido (kg)", "peso liquido (kg)"],
    "peso_bruto": ["peso bruto", "peso bruto (kg)"],
    "estoque_minimo": ["estoque minimo", "estoque mínimo"],
    "estoque_maximo": ["estoque maximo", "estoque máximo"],
    "unidade": ["unidade", "unidade de medida", "un"],
    "tipo": ["tipo", "tipo produção", "tipo producao"],
    "situacao": ["situacao", "situação", "status"],
}

TERMOS_PROIBIDOS_LINK = [
    "video",
    "vídeo",
    "youtube",
    "canal",
    "whatsapp",
    "instagram",
    "facebook",
    "telegram",
    "tiktok",
    "propaganda",
    "promo",
    "cupom",
]


def _nome_normalizado(col):
    return limpar(col).lower()


def _buscar_coluna(colunas, aliases):
    for col in colunas:
        nome = _nome_normalizado(col)
        for alias in aliases:
            if alias in nome:
                return col
    return None


def _resolver_link(colunas):
    candidatas = []

    for col in colunas:
        nome = _nome_normalizado(col)

        if any(t in nome for t in TERMOS_PROIBIDOS_LINK):
            continue

        if any(x in nome for x in ["link", "url", "produto url", "url produto", "link externo", "site produto"]):
            candidatas.append(col)

    if candidatas:
        return candidatas[0]

    return None


def detectar_colunas_inteligente(df, mapa_ia=None):
    colunas = list(df.columns)
    resultado = {}

    if mapa_ia:
        for campo, coluna in mapa_ia.items():
            if campo == "link":
                continue
            if coluna in colunas:
                resultado[campo] = coluna

    for campo, aliases in MAPA_FIXO.items():
        if campo not in resultado or not resultado[campo]:
            resultado[campo] = _buscar_coluna(colunas, aliases)

    resultado["link"] = _resolver_link(colunas)

    if not resultado.get("descricao_curta") and resultado.get("produto"):
        resultado["descricao_curta"] = resultado["produto"]

    return resultado
