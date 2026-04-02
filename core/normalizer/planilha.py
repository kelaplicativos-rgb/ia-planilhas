import pandas as pd

from core.ai_mapper import mapear_colunas_com_ia
from core.logger import log
from core.normalizer.cleaners import (
    limpar_estoque,
    limpar_preco,
    limpar_texto,
    validar_gtin,
    valor_vazio,
)
from core.normalizer.detector import detectar_colunas_inteligente
from core.utils import (
    detectar_marca,
    gerar_codigo_fallback,
    normalizar_url,
)


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


def _pegar_codigo_seguro(row, mapa):
    """
    Regra definitiva anti-ID:
    1. usa coluna mapeada, se não for ID genérico
    2. procura manualmente por nomes prioritários
    3. nunca usa 'ID' puro como SKU
    """
    col_codigo = mapa.get("codigo")
    if col_codigo and str(col_codigo).strip().lower() != "id":
        valor = limpar_texto(row.get(col_codigo))
        if valor:
            return valor

    prioridades = [
        "SKU",
        "sku",
        "Código do Produto",
        "CÓDIGO DO PRODUTO",
        "codigo do produto",
        "Código",
        "codigo",
        "Referência",
        "Referencia",
        "referência",
        "referencia",
        "Ref",
        "ref",
        "Código Interno",
        "codigo interno",
        "Codigo Interno",
        "Código SKU",
        "codigo sku",
    ]

    for nome in prioridades:
        if nome in row.index:
            valor = limpar_texto(row.get(nome))
            if valor:
                return valor

    for col in row.index:
        nome = str(col).strip().lower()
        if nome == "id":
            continue

        if any(chave in nome for chave in [
            "sku",
            "codigo do produto",
            "código do produto",
            "referencia",
            "referência",
            "codigo interno",
            "código interno",
            "codigo sku",
            "código sku",
            "codigo",
            "código",
            "ref",
        ]):
            valor = limpar_texto(row.get(col))
            if valor:
                return valor

    return ""


def _valor_coluna(row, mapa, chave):
    col = mapa.get(chave)
    if not col:
        return ""
    return row.get(col, "")


def _normalizar_linha(row, mapa, url_base="", estoque_padrao=0):
    item = {}

    codigo = _pegar_codigo_seguro(row, mapa)

    gtin = validar_gtin(_valor_coluna(row, mapa, "gtin"))

    produto = limpar_texto(_valor_coluna(row, mapa, "produto"))

    preco = "0.01"
    valor_preco = _valor_coluna(row, mapa, "preco")
    if not valor_vazio(valor_preco):
        preco = limpar_preco(valor_preco)

    preco_custo = ""
    valor_preco_custo = _valor_coluna(row, mapa, "preco_custo")
    if not valor_vazio(valor_preco_custo):
        preco_custo = limpar_preco(valor_preco_custo)

    descricao_curta = limpar_texto(_valor_coluna(row, mapa, "descricao_curta"))
    descricao_complementar = limpar_texto(_valor_coluna(row, mapa, "descricao_complementar"))

    imagem = limpar_texto(_valor_coluna(row, mapa, "imagem"))
    link = limpar_texto(_valor_coluna(row, mapa, "link"))
    marca = limpar_texto(_valor_coluna(row, mapa, "marca"))

    valor_estoque = _valor_coluna(row, mapa, "estoque")
    estoque = limpar_estoque(valor_estoque, estoque_padrao) if not valor_vazio(valor_estoque) else int(estoque_padrao)

    ncm = limpar_texto(_valor_coluna(row, mapa, "ncm"))
    origem = limpar_texto(_valor_coluna(row, mapa, "origem"))
    peso_liquido = limpar_texto(_valor_coluna(row, mapa, "peso_liquido"))
    peso_bruto = limpar_texto(_valor_coluna(row, mapa, "peso_bruto"))
    estoque_minimo = limpar_texto(_valor_coluna(row, mapa, "estoque_minimo"))
    estoque_maximo = limpar_texto(_valor_coluna(row, mapa, "estoque_maximo"))
    unidade = limpar_texto(_valor_coluna(row, mapa, "unidade"))
    tipo = limpar_texto(_valor_coluna(row, mapa, "tipo"))
    situacao = limpar_texto(_valor_coluna(row, mapa, "situacao"))

    # garantias
    if not produto:
        produto = "Produto sem nome"

    if not descricao_curta:
        descricao_curta = produto

    if not codigo:
        base_fallback = link or imagem or produto
        codigo = gerar_codigo_fallback(base_fallback)
        log(f"SKU fallback gerado: {codigo}")

    if not marca:
        marca = detectar_marca(produto, f"{descricao_curta} {descricao_complementar}")

    if not unidade:
        unidade = "UN"

    if not tipo:
        tipo = "Produto"

    if not situacao:
        situacao = "Ativo"

    if not origem:
        origem = "0"

    imagem = normalizar_url(imagem, url_base)
    link = normalizar_url(link, url_base)

    item["Código"] = codigo
    item["GTIN"] = gtin
    item["Produto"] = produto
    item["Preço"] = preco
    item["Preço Custo"] = preco_custo
    item["Descrição Curta"] = descricao_curta
    item["Descrição Complementar"] = descricao_complementar
    item["Imagem"] = imagem
    item["Link"] = link
    item["Marca"] = marca
    item["Estoque"] = estoque
    item["NCM"] = ncm
    item["Origem"] = origem
    item["Peso Líquido"] = peso_liquido
    item["Peso Bruto"] = peso_bruto
    item["Estoque Mínimo"] = estoque_minimo
    item["Estoque Máximo"] = estoque_maximo
    item["Unidade"] = unidade
    item["Tipo"] = tipo
    item["Situação"] = situacao

    return item


def normalizar_planilha_entrada(df, url_base="", estoque_padrao=0):
    try:
        if df is None or df.empty:
            log("Planilha vazia no normalizador")
            return pd.DataFrame(columns=COLUNAS_PADRAO)

        mapa_ia = mapear_colunas_com_ia(df)
        mapa = detectar_colunas_inteligente(df, mapa_ia=mapa_ia)

        log(f"IA mapper final: {mapa_ia}")
        log(f"MAPEAMENTO DETECTADO FINAL: {mapa}")

        dados = []

        for _, row in df.iterrows():
            item = _normalizar_linha(
                row=row,
                mapa=mapa,
                url_base=url_base,
                estoque_padrao=estoque_padrao,
            )
            dados.append(item)

        df_final = pd.DataFrame(dados)

        if df_final.empty:
            return pd.DataFrame(columns=COLUNAS_PADRAO)

        for col in COLUNAS_PADRAO:
            if col not in df_final.columns:
                df_final[col] = ""

        df_final = df_final[COLUNAS_PADRAO].copy()

        # remove linhas realmente vazias
        df_final = df_final[
            ~(
                df_final["Código"].apply(valor_vazio)
                & df_final["Produto"].apply(valor_vazio)
            )
        ].copy()

        if df_final.empty:
            return pd.DataFrame(columns=COLUNAS_PADRAO)

        # deduplicação inteligente
        df_final["_chave"] = df_final.apply(
            lambda r: (
                f"COD::{limpar_texto(r['Código'])}"
                if limpar_texto(r["Código"])
                else (
                    f"GTIN::{limpar_texto(r['GTIN'])}"
                    if limpar_texto(r["GTIN"])
                    else (
                        f"LINK::{limpar_texto(r['Link'])}"
                        if limpar_texto(r["Link"])
                        else f"PROD::{limpar_texto(r['Produto']).lower()}"
                    )
                )
            ),
            axis=1,
        )

        df_final = df_final.drop_duplicates(subset=["_chave"], keep="first").copy()
        df_final = df_final.drop(columns=["_chave"])

        df_final = df_final.fillna("")
        df_final = df_final.reset_index(drop=True)

        log(f"TOTAL NORMALIZADO: {len(df_final)} linhas")
        return df_final

    except Exception as e:
        log(f"ERRO normalizar_planilha_entrada: {e}")
        return pd.DataFrame(columns=COLUNAS_PADRAO)
