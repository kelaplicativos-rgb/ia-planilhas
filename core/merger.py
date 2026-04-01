import pandas as pd

from core.utils import (
    limpar,
    gerar_codigo_fallback,
    parse_preco,
    parse_estoque,
    normalizar_url,
    detectar_marca,
)


def merge_dados(planilha_df, site_df, url_base, estoque_padrao):
    # casos simples
    if planilha_df.empty and site_df.empty:
        return pd.DataFrame()

    if planilha_df.empty:
        out = site_df.copy()
        return _finalizar_base(out, url_base, estoque_padrao)

    if site_df.empty:
        out = planilha_df.copy()
        return _finalizar_base(out, url_base, estoque_padrao)

    plan = planilha_df.copy()
    site = site_df.copy()

    # cria chave inteligente
    plan["_chave"] = plan.apply(
        lambda r: limpar(r.get("Link", "")) or limpar(r.get("Código", "")) or limpar(r.get("Produto", "")).lower(),
        axis=1,
    )

    site["_chave"] = site.apply(
        lambda r: limpar(r.get("Link", "")) or limpar(r.get("Código", "")) or limpar(r.get("Produto", "")).lower(),
        axis=1,
    )

    base = pd.merge(
        plan,
        site,
        on="_chave",
        how="outer",
        suffixes=("_plan", "_site"),
    )

    out = pd.DataFrame()

    def escolher_texto(row, campo):
        plan_v = limpar(row.get(f"{campo}_plan", ""))
        site_v = limpar(row.get(f"{campo}_site", ""))

        # prioriza site para enriquecer cadastro
        return site_v or plan_v

    def escolher_estoque(row):
        plan_v = row.get("Estoque_plan", "")
        site_v = row.get("Estoque_site", "")
        if limpar(plan_v):
            return parse_estoque(plan_v, estoque_padrao)
        return parse_estoque(site_v, estoque_padrao)

    def escolher_codigo(row):
        plan_v = limpar(row.get("Código_plan", ""))
        site_v = limpar(row.get("Código_site", ""))
        codigo = site_v or plan_v
        if codigo:
            return codigo

        link = limpar(row.get("Link_site", "")) or limpar(row.get("Link_plan", ""))
        produto = limpar(row.get("Produto_site", "")) or limpar(row.get("Produto_plan", ""))
        return gerar_codigo_fallback(link or produto)

    # campos principais
    out["Código"] = base.apply(escolher_codigo, axis=1)
    out["Produto"] = base.apply(lambda r: escolher_texto(r, "Produto"), axis=1)
    out["Preço"] = base.apply(lambda r: escolher_texto(r, "Preço"), axis=1)
    out["Descrição Curta"] = base.apply(lambda r: escolher_texto(r, "Descrição Curta"), axis=1)
    out["Imagem"] = base.apply(lambda r: escolher_texto(r, "Imagem"), axis=1)
    out["Link"] = base.apply(lambda r: escolher_texto(r, "Link"), axis=1)
    out["Marca"] = base.apply(lambda r: escolher_texto(r, "Marca"), axis=1)
    out["Estoque"] = base.apply(escolher_estoque, axis=1)

    return _finalizar_base(out, url_base, estoque_padrao)


def _finalizar_base(out, url_base, estoque_padrao):
    # produto
    out["Produto"] = out["Produto"].apply(limpar)
    out["Produto"] = out["Produto"].replace("", pd.NA).fillna("Produto sem nome")

    # código
    out["Código"] = out.apply(
        lambda r: limpar(r["Código"]) if limpar(r["Código"]) else gerar_codigo_fallback(r["Link"] or r["Produto"]),
        axis=1,
    )

    # preço
    out["Preço"] = out["Preço"].apply(parse_preco)

    # descrição curta
    out["Descrição Curta"] = out.apply(
        lambda r: limpar(r["Descrição Curta"]) if limpar(r["Descrição Curta"]) else r["Produto"],
        axis=1,
    )

    # marca
    out["Marca"] = out.apply(
        lambda r: limpar(r["Marca"]) if limpar(r["Marca"]) else detectar_marca(r["Produto"], r["Descrição Curta"]),
        axis=1,
    )

    # imagem e link
    out["Imagem"] = out["Imagem"].apply(lambda x: normalizar_url(x, url_base))
    out["Link"] = out["Link"].apply(lambda x: normalizar_url(x, url_base))

    # estoque
    out["Estoque"] = out["Estoque"].apply(lambda x: parse_estoque(x, estoque_padrao))

    # remove linhas totalmente inúteis
    out = out[
        ~(
            (out["Produto"].fillna("").astype(str).str.strip() == "")
            & (out["Código"].fillna("").astype(str).str.strip() == "")
            & (out["Link"].fillna("").astype(str).str.strip() == "")
        )
    ].copy()

    # remove duplicados
    out = out.drop_duplicates(subset=["Código", "Produto", "Link"], keep="first").reset_index(drop=True)

    return out
