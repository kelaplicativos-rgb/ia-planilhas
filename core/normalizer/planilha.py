import pandas as pd

from core.logger import log
from core.utils import detectar_marca, gerar_codigo_fallback, normalizar_url
from core.normalizer.detector import detectar_colunas_inteligente
from core.normalizer.cleaners import (
    limpar_texto,
    limpar_preco,
    limpar_estoque,
    valor_vazio,
)


def normalizar_planilha_entrada(df, url_base="", estoque_padrao=0):
    try:
        mapa = detectar_colunas_inteligente(df)
        log(f"MAPEAMENTO DETECTADO: {mapa}")

        dados = []

        for _, row in df.iterrows():
            item = {}

            codigo = ""
            if mapa.get("codigo"):
                codigo = limpar_texto(row.get(mapa["codigo"]))

            if not codigo:
                codigo = (
                    limpar_texto(row.get("SKU"))
                    or limpar_texto(row.get("Código"))
                    or limpar_texto(row.get("codigo"))
                    or limpar_texto(row.get("ID"))
                )

            produto = ""
            if mapa.get("produto"):
                produto = limpar_texto(row.get(mapa["produto"]))

            preco = "0.01"
            if mapa.get("preco"):
                preco = limpar_preco(row.get(mapa["preco"]))

            descricao_curta = ""
            if mapa.get("descricao_curta"):
                descricao_curta = limpar_texto(row.get(mapa["descricao_curta"]))

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
            else:
                estoque = int(estoque_padrao)

            if not produto:
                produto = "Produto sem nome"

            if not descricao_curta:
                descricao_curta = produto

            if not codigo:
                base_fallback = link or produto
                codigo = gerar_codigo_fallback(base_fallback)

            if not marca:
                marca = detectar_marca(produto, descricao_curta)

            imagem = normalizar_url(imagem, url_base)
            link = normalizar_url(link, url_base)

            item["Código"] = codigo
            item["Produto"] = produto
            item["Preço"] = preco
            item["Descrição Curta"] = descricao_curta
            item["Imagem"] = imagem
            item["Link"] = link
            item["Marca"] = marca
            item["Estoque"] = estoque

            dados.append(item)

        df_final = pd.DataFrame(dados)

        if df_final.empty:
            return df_final

        df_final = df_final[
            ~(
                df_final["Código"].apply(valor_vazio)
                & df_final["Produto"].apply(valor_vazio)
                & df_final["Link"].apply(valor_vazio)
            )
        ].copy()

        if not df_final.empty:
            df_final = df_final.drop_duplicates(
                subset=["Código", "Produto", "Link"],
                keep="first"
            ).reset_index(drop=True)

        log(f"TOTAL NORMALIZADO: {len(df_final)} linhas")
        return df_final

    except Exception as e:
        log(f"ERRO normalizar_planilha_entrada: {e}")
        return pd.DataFrame()
