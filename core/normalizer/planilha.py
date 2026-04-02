import pandas as pd

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
from core.ai_mapper import mapear_colunas_com_ia


COLUNAS_PADRAO = [
    "Código",
    "GTIN",
    "Produto",
    "Preço",
    "Preço Custo",
    "Descrição Curta",
    "Descrição Complementar",
    "Imagem",
    "Link",
    "Marca",
    "Estoque",
    "NCM",
    "Origem",
    "Peso Líquido",
    "Peso Bruto",
    "Estoque Mínimo",
    "Estoque Máximo",
    "Unidade",
    "Tipo",
    "Situação",
]


def normalizar_planilha_entrada(df, url_base="", estoque_padrao=0):
    if df is None or df.empty:
        return pd.DataFrame(columns=COLUNAS_PADRAO)

    mapa_ia = mapear_colunas_com_ia(df)
    mapa = detectar_colunas_inteligente(df, mapa_ia=mapa_ia)

    dados = []

    for _, row in df.iterrows():

        def get(campo):
            col = mapa.get(campo)
            if not col:
                return ""
            return limpar(row.get(col, ""))

        nome = get("produto")
        descricao_complementar = get("descricao_complementar")
        descricao_curta = get("descricao_curta")

        # descrição curta nunca fica vazia
        if not descricao_curta:
            descricao_curta = nome or descricao_complementar

        codigo = get("codigo")
        if not codigo:
            codigo = gerar_codigo_fallback(nome or descricao_curta)

        preco = parse_preco(get("preco"), "0.01")

        preco_custo = ""
        valor_preco_custo = get("preco_custo")
        if not valor_vazio(valor_preco_custo):
            preco_custo = parse_preco(valor_preco_custo, "")

        estoque = parse_estoque(get("estoque"), estoque_padrao)

        imagem = normalizar_url(get("imagem"), url_base)

        link = get("link")
        if "youtube" in link.lower() or "video" in link.lower() or "vídeo" in link.lower():
            link = ""
        link = normalizar_url(link, url_base)

        marca = get("marca")
        if not marca:
            marca = detectar_marca(nome, descricao_complementar)

        gtin = validar_gtin(get("gtin"))

        unidade = get("unidade") or "UN"
        tipo = get("tipo") or "Produto"
        situacao = get("situacao") or "Ativo"
        origem = get("origem") or "0"

        item = {
            "Código": codigo,
            "GTIN": gtin,
            "Produto": nome or "Produto sem nome",
            "Preço": preco,
            "Preço Custo": preco_custo,
            "Descrição Curta": descricao_curta or (nome or "Produto sem nome"),
            "Descrição Complementar": descricao_complementar,
            "Imagem": imagem,
            "Link": link,
            "Marca": marca,
            "Estoque": estoque,
            "NCM": get("ncm"),
            "Origem": origem,
            "Peso Líquido": get("peso_liquido"),
            "Peso Bruto": get("peso_bruto"),
            "Estoque Mínimo": get("estoque_minimo"),
            "Estoque Máximo": get("estoque_maximo"),
            "Unidade": unidade,
            "Tipo": tipo,
            "Situação": situacao,
        }

        dados.append(item)

    df_final = pd.DataFrame(dados)

    # garante colunas
    for col in COLUNAS_PADRAO:
        if col not in df_final.columns:
            df_final[col] = ""

    df_final = df_final[COLUNAS_PADRAO].copy()

    # remove linhas totalmente inúteis
    df_final = df_final[
        ~(
            df_final["Código"].apply(valor_vazio)
            & df_final["Produto"].apply(valor_vazio)
        )
    ].copy()

    # deduplicação inteligente
    def chave(row):
        if not valor_vazio(row["Código"]):
            return f"COD::{limpar(row['Código'])}"
        if not valor_vazio(row["GTIN"]):
            return f"GTIN::{limpar(row['GTIN'])}"
        if not valor_vazio(row["Link"]):
            return f"LINK::{limpar(row['Link'])}"
        return f"PROD::{limpar(row['Produto']).lower()}"

    if not df_final.empty:
        df_final["_chave"] = df_final.apply(chave, axis=1)
        df_final = df_final.drop_duplicates(subset=["_chave"], keep="first").copy()
        df_final = df_final.drop(columns=["_chave"])

    df_final = df_final.fillna("").reset_index(drop=True)

    return df_final
