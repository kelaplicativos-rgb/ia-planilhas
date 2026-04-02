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
from core.utils import detectar_marca, gerar_codigo_fallback, normalizar_url


def _pegar_codigo_seguro(row, mapa):
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
            "codigo",
            "código",
            "ref",
        ]):
            valor = limpar_texto(row.get(col))
            if valor:
                return valor

    return ""


def normalizar_planilha_entrada(df, url_base="", estoque_padrao=0):
    try:
        mapa_ia = mapear_colunas_com_ia(df)
        mapa = detectar_colunas_inteligente(df, mapa_ia=mapa_ia)
        log(f"MAPEAMENTO DETECTADO FINAL: {mapa}")

        dados = []

        for _, row in df.iterrows():
            item = {}

            codigo = _pegar_codigo_seguro(row, mapa)

            gtin = ""
            if mapa.get("gtin"):
                gtin = validar_gtin(row.get(mapa["gtin"]))

            produto = ""
            if mapa.get("produto"):
                produto = limpar_texto(row.get(mapa["produto"]))

            preco = "0.01"
            if mapa.get("preco"):
                preco = limpar_preco(row.get(mapa["preco"]))

            preco_custo = ""
            if mapa.get("preco_custo"):
                preco_custo = limpar_preco(row.get(mapa["preco_custo"]))

            descricao_curta = ""
            if mapa.get("descricao_curta"):
                descricao_curta = limpar_texto(row.get(mapa["descricao_curta"]))

            descricao_complementar = ""
            if mapa.get("descricao_complementar"):
                descricao_complementar = limpar_texto(row.get(mapa["descricao_complementar"]))

            imagem = ""
            if mapa.get("imagem"):
                imagem = limpar_texto(row.get(mapa["imagem"]))

            link = ""
            if mapa.get("link"):
                link = limpar_texto(row.get(mapa["link"]))

            marca = ""
            if mapa.get("marca"):
                marca = limpar_texto(row.get(mapa["marca"]))

            estoque = estoque_padrao
            if mapa.get("estoque"):
                estoque = limpar_estoque(row.get(mapa["estoque"]), estoque_padrao)

            ncm = ""
            if mapa.get("ncm"):
                ncm = limpar_texto(row.get(mapa["ncm"]))

            origem = ""
            if mapa.get("origem"):
                origem = limpar_texto(row.get(mapa["origem"]))

            peso_liquido = ""
            if mapa.get("peso_liquido"):
                peso_liquido = limpar_texto(row.get(mapa["peso_liquido"]))

            peso_bruto = ""
            if mapa.get("peso_bruto"):
                peso_bruto = limpar_texto(row.get(mapa["peso_bruto"]))

            estoque_minimo = ""
            if mapa.get("estoque_minimo"):
                estoque_minimo = limpar_texto(row.get(mapa["estoque_minimo"]))

            estoque_maximo = ""
            if mapa.get("estoque_maximo"):
                estoque_maximo = limpar_texto(row.get(mapa["estoque_maximo"]))

            unidade = ""
            if mapa.get("unidade"):
                unidade = limpar_texto(row.get(mapa["unidade"]))

            tipo = ""
            if mapa.get("tipo"):
                tipo = limpar_texto(row.get(mapa["tipo"]))

            situacao = ""
            if mapa.get("situacao"):
                situacao = limpar_texto(row.get(mapa["situacao"]))

            if not produto:
                produto = "Produto sem nome"

            if not descricao_curta:
                descricao_curta = produto

            if not codigo:
                base_fallback = link or imagem or produto
                codigo = gerar_codigo_fallback(base_fallback)
                log(f"SKU fallback gerado: {codigo}")

            if not marca:
                marca = detectar_marca(produto, descricao_curta)

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

            dados.append(item)

        df_final = pd.DataFrame(dados)

        if df_final.empty:
            return df_final

        df_final = df_final[
            ~(
                df_final["Código"].apply(valor_vazio)
                & df_final["Produto"].apply(valor_vazio)
            )
        ].copy()

        df_final = df_final.drop_duplicates(
            subset=["Código", "Produto"],
            keep="first"
        ).reset_index(drop=True)

        log(f"TOTAL NORMALIZADO: {len(df_final)} linhas")
        return df_final

    except Exception as e:
        log(f"ERRO normalizar_planilha_entrada: {e}")
        return pd.DataFrame()
