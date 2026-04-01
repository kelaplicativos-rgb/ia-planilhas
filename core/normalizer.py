import pandas as pd
import random

from core.logger import log
from core.utils import (
    limpar,
    normalizar_url,
    gerar_codigo_fallback,
    parse_preco,
    parse_estoque,
    detectar_marca,
)


def detectar_colunas_inteligente(df: pd.DataFrame):
    mapa = {}

    for col in df.columns:
        c = limpar(col).lower()

        if (
            "codigo produto" in c
            or c == "codigo"
            or c == "código"
            or "sku" in c
            or "cod" in c
            or c == "id"
        ):
            mapa.setdefault("codigo", col)

        elif (
            "nome" in c
            or "produto" in c
            or c == "descrição"
            or c == "descricao"
            or "titulo" in c
            or "title" in c
        ):
            mapa.setdefault("produto", col)

        elif "preço" in c or "preco" in c or "valor" in c or "price" in c:
            mapa.setdefault("preco", col)

        elif (
            "estoque" in c
            or "saldo" in c
            or "qtd" in c
            or "quantidade" in c
            or "balan" in c
        ):
            mapa.setdefault("estoque", col)

        elif (
            "descrição curta" in c
            or "descricao curta" in c
            or "descrição" in c
            or "descricao" in c
            or "resumo" in c
        ):
            mapa.setdefault("descricao_curta", col)

        elif "imagem" in c or "foto" in c or "image" in c:
            mapa.setdefault("imagem", col)

        elif "link externo" in c or c == "link" or c == "url" or "site" in c:
            mapa.setdefault("link", col)

        elif "marca" in c:
            mapa.setdefault("marca", col)

    return mapa


def valor_texto_seguro(x):
    txt = str(x).strip()
    if txt.lower() in ["", "nan", "none", "nat"]:
        return ""
    return txt


def normalizar_planilha_entrada(df: pd.DataFrame, base_url: str, padrao_estoque: int):
    mapa = detectar_colunas_inteligente(df)
    log(f"Mapa detectado planilha entrada: {mapa}")

    out = pd.DataFrame(index=df.index)

    # CÓDIGO
    if "codigo" in mapa:
        out["Código"] = df[mapa["codigo"]].apply(valor_texto_seguro)
    else:
        out["Código"] = [""] * len(df)

    # PRODUTO
    if "produto" in mapa:
        out["Produto"] = df[mapa["produto"]].apply(lambda x: limpar(valor_texto_seguro(x)))
    else:
        out["Produto"] = [""] * len(df)

    # PREÇO
    if "preco" in mapa:
        out["Preço"] = df[mapa["preco"]].apply(parse_preco)
    else:
        out["Preço"] = ["0.01"] * len(df)

    # ESTOQUE
    if "estoque" in mapa:
        out["Estoque"] = df[mapa["estoque"]].apply(lambda x: parse_estoque(x, padrao_estoque))
    else:
        out["Estoque"] = [padrao_estoque] * len(df)

    # DESCRIÇÃO CURTA
    if "descricao_curta" in mapa:
        out["Descrição Curta"] = df[mapa["descricao_curta"]].apply(lambda x: limpar(valor_texto_seguro(x)))
    else:
        out["Descrição Curta"] = [""] * len(df)

    # IMAGEM
    if "imagem" in mapa:
        out["Imagem"] = df[mapa["imagem"]].apply(lambda x: normalizar_url(valor_texto_seguro(x), base_url))
    else:
        out["Imagem"] = [""] * len(df)

    # LINK
    if "link" in mapa:
        out["Link"] = df[mapa["link"]].apply(lambda x: normalizar_url(valor_texto_seguro(x), base_url))
    else:
        out["Link"] = [""] * len(df)

    # MARCA
    if "marca" in mapa:
        out["Marca"] = df[mapa["marca"]].apply(lambda x: limpar(valor_texto_seguro(x)))
    else:
        out["Marca"] = [""] * len(df)

    # =========================
    # CORREÇÕES FINAIS
    # =========================
    out["Produto"] = out["Produto"].apply(
        lambda x: x if valor_texto_seguro(x) else "Produto sem nome"
    )

    out["Código"] = out.apply(
        lambda r: valor_texto_seguro(r["Código"])
        if valor_texto_seguro(r["Código"])
        else gerar_codigo_fallback(r["Link"] or r["Produto"]),
        axis=1,
    )

    out["Descrição Curta"] = out.apply(
        lambda r: r["Descrição Curta"]
        if valor_texto_seguro(r["Descrição Curta"])
        else r["Produto"],
        axis=1,
    )

    out["Marca"] = out.apply(
        lambda r: r["Marca"]
        if valor_texto_seguro(r["Marca"])
        else detectar_marca(r["Produto"], r["Descrição Curta"]),
        axis=1,
    )

    # remove linhas totalmente vazias
    out = out[
        ~(
            (out["Produto"].fillna("").astype(str).str.strip() == "")
            & (out["Código"].fillna("").astype(str).str.strip() == "")
            & (out["Link"].fillna("").astype(str).str.strip() == "")
        )
    ].copy()

    # remove duplicados principais
    out = out.drop_duplicates(subset=["Código", "Produto", "Link"], keep="first").reset_index(drop=True)

    log(f"Planilha normalizada final com {len(out)} linhas")

    return out
