from core.utils import (
    limpar,
    gerar_codigo_fallback,
    normalizar_url,
    detectar_marca,
    validar_gtin,
    parse_preco,
    parse_estoque,
    valor_vazio,
)

from core.normalizer.detector import detectar_colunas_inteligente


def normalizar_planilha_entrada(df, url_base, estoque_padrao):
    if df is None or df.empty:
        return df

    mapa = detectar_colunas_inteligente(df)

    dados = []

    for _, row in df.iterrows():

        def get(campo):
            col = mapa.get(campo)
            if not col:
                return ""
            return limpar(row.get(col, ""))

        nome = get("produto")

        descricao = get("descricao_complementar")

        # 🔥 CORREÇÃO DESCRIÇÃO CURTA
        descricao_curta = get("descricao_curta")

        if not descricao_curta:
            descricao_curta = nome or descricao

        # 🔥 SKU 100% (TRAVADO)
        codigo = get("codigo")
        if not codigo:
            codigo = gerar_codigo_fallback(nome)

        # 🔥 PREÇO
        preco = parse_preco(get("preco"))

        # 🔥 ESTOQUE
        estoque = parse_estoque(get("estoque"), estoque_padrao)

        # 🔥 IMAGEM
        imagem = normalizar_url(get("imagem"), url_base)

        # 🔥 LINK (CORRIGIDO)
        link = get("link")

        if "youtube" in link.lower() or "video" in link.lower():
            link = ""

        link = normalizar_url(link, url_base)

        # 🔥 MARCA
        marca = get("marca")
        if not marca:
            marca = detectar_marca(nome, descricao)

        # 🔥 GTIN
        gtin = validar_gtin(get("gtin"))

        dados.append({
            "Código": codigo,
            "Produto": nome,
            "Descrição Curta": descricao_curta,
            "Preço": preco,
            "Estoque": estoque,
            "Imagem": imagem,
            "Link": link,
            "Marca": marca,
            "GTIN": gtin,
            "NCM": get("ncm"),
            "Origem": get("origem"),
            "Peso Líquido": get("peso_liquido"),
            "Peso Bruto": get("peso_bruto"),
        })

    return dados
