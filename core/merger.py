import pandas as pd

from core.utils import (
    limpar,
    gerar_codigo_fallback,
    parse_preco,
    parse_estoque,
    normalizar_url,
    detectar_marca,
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


def _garantir_colunas(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=COLUNAS_PADRAO)

    df = df.copy()

    for col in COLUNAS_PADRAO:
        if col not in df.columns:
            df[col] = ""

    return df[COLUNAS_PADRAO]


def _valor_preenchido(valor) -> bool:
    return limpar(valor) != ""


def _normalizar_codigo(valor) -> str:
    return limpar(valor)


def _normalizar_gtin(valor) -> str:
    return limpar(valor)


def _normalizar_texto(valor) -> str:
    return limpar(valor)


def _escolher_texto(principal, secundario) -> str:
    principal = limpar(principal)
    secundario = limpar(secundario)
    return principal if principal else secundario


def _escolher_preco(principal, secundario) -> str:
    principal = limpar(principal)
    secundario = limpar(secundario)

    if principal:
        return parse_preco(principal)

    if secundario:
        return parse_preco(secundario)

    return "0.01"


def _escolher_estoque(principal, secundario, estoque_padrao=0) -> int:
    principal = limpar(principal)
    secundario = limpar(secundario)

    if principal:
        return parse_estoque(principal, estoque_padrao)

    if secundario:
        return parse_estoque(secundario, estoque_padrao)

    return int(estoque_padrao)


def _escolher_url(principal, secundario, base_url="") -> str:
    principal = normalizar_url(principal, base_url)
    secundario = normalizar_url(secundario, base_url)

    return principal if principal else secundario


def _construir_chave(row) -> str:
    """
    Prioridade:
    1. Código
    2. GTIN
    3. Link
    4. Produto
    """
    codigo = limpar(row.get("Código", ""))
    gtin = limpar(row.get("GTIN", ""))
    link = limpar(row.get("Link", ""))
    produto = limpar(row.get("Produto", "")).lower()

    if codigo:
        return f"COD::{codigo}"

    if gtin:
        return f"GTIN::{gtin}"

    if link:
        return f"LINK::{link}"

    if produto:
        return f"PROD::{produto}"

    return ""


def _consolidar_linha(row, estoque_padrao=0, base_url="") -> dict:
    """
    row contém campos com sufixos _plan e _site
    Regra:
    - planilha tem prioridade quando veio preenchida
    - site complementa o que estiver vazio
    - nunca aceita vazio sobrescrevendo valor bom
    """
    out = {}

    # CAMPOS BASE
    out["Código"] = _escolher_texto(row.get("Código_plan", ""), row.get("Código_site", ""))
    out["GTIN"] = _escolher_texto(row.get("GTIN_plan", ""), row.get("GTIN_site", ""))
    out["Produto"] = _escolher_texto(row.get("Produto_plan", ""), row.get("Produto_site", ""))
    out["Preço"] = _escolher_preco(row.get("Preço_plan", ""), row.get("Preço_site", ""))
    out["Preço Custo"] = _escolher_preco(row.get("Preço Custo_plan", ""), row.get("Preço Custo_site", "")) \
        if _valor_preenchido(row.get("Preço Custo_plan", "")) or _valor_preenchido(row.get("Preço Custo_site", "")) \
        else ""

    out["Descrição Curta"] = _escolher_texto(
        row.get("Descrição Curta_plan", ""),
        row.get("Descrição Curta_site", "")
    )

    out["Descrição Complementar"] = _escolher_texto(
        row.get("Descrição Complementar_plan", ""),
        row.get("Descrição Complementar_site", "")
    )

    out["Imagem"] = _escolher_url(row.get("Imagem_plan", ""), row.get("Imagem_site", ""), base_url)
    out["Link"] = _escolher_url(row.get("Link_plan", ""), row.get("Link_site", ""), base_url)
    out["Marca"] = _escolher_texto(row.get("Marca_plan", ""), row.get("Marca_site", ""))
    out["Estoque"] = _escolher_estoque(row.get("Estoque_plan", ""), row.get("Estoque_site", ""), estoque_padrao)

    out["NCM"] = _escolher_texto(row.get("NCM_plan", ""), row.get("NCM_site", ""))
    out["Origem"] = _escolher_texto(row.get("Origem_plan", ""), row.get("Origem_site", ""))
    out["Peso Líquido"] = _escolher_texto(row.get("Peso Líquido_plan", ""), row.get("Peso Líquido_site", ""))
    out["Peso Bruto"] = _escolher_texto(row.get("Peso Bruto_plan", ""), row.get("Peso Bruto_site", ""))
    out["Estoque Mínimo"] = _escolher_texto(row.get("Estoque Mínimo_plan", ""), row.get("Estoque Mínimo_site", ""))
    out["Estoque Máximo"] = _escolher_texto(row.get("Estoque Máximo_plan", ""), row.get("Estoque Máximo_site", ""))
    out["Unidade"] = _escolher_texto(row.get("Unidade_plan", ""), row.get("Unidade_site", ""))
    out["Tipo"] = _escolher_texto(row.get("Tipo_plan", ""), row.get("Tipo_site", ""))
    out["Situação"] = _escolher_texto(row.get("Situação_plan", ""), row.get("Situação_site", ""))

    # GARANTIAS FINAIS
    if not out["Produto"]:
        out["Produto"] = "Produto sem nome"

    if not out["Descrição Curta"]:
        out["Descrição Curta"] = out["Produto"]

    if not out["Código"]:
        base_codigo = out["Link"] or out["GTIN"] or out["Produto"]
        out["Código"] = gerar_codigo_fallback(base_codigo)

    if not out["Marca"]:
        out["Marca"] = detectar_marca(out["Produto"], out["Descrição Curta"])

    if not out["Origem"]:
        out["Origem"] = "0"

    if not out["Unidade"]:
        out["Unidade"] = "UN"

    if not out["Tipo"]:
        out["Tipo"] = "Produto"

    if not out["Situação"]:
        out["Situação"] = "Ativo"

    # preço garantido
    out["Preço"] = parse_preco(out["Preço"], "0.01")

    # preço custo só se existir
    if _valor_preenchido(out["Preço Custo"]):
        out["Preço Custo"] = parse_preco(out["Preço Custo"], "")
    else:
        out["Preço Custo"] = ""

    # estoque garantido
    out["Estoque"] = parse_estoque(out["Estoque"], estoque_padrao)

    return out


def merge_dados(df_planilha, df_site, url_base="", estoque_padrao=0):
    df_planilha = _garantir_colunas(df_planilha)
    df_site = _garantir_colunas(df_site)

    # casos simples
    if df_planilha.empty and df_site.empty:
        return pd.DataFrame(columns=COLUNAS_PADRAO)

    if df_planilha.empty:
        df = df_site.copy()
        for _, row in df.iterrows():
            pass
        # padronização final
        dados = []
        for _, row in df.iterrows():
            linha = _consolidar_linha(
                {f"{col}_plan": "" for col in COLUNAS_PADRAO} | {f"{col}_site": row.get(col, "") for col in COLUNAS_PADRAO},
                estoque_padrao=estoque_padrao,
                base_url=url_base,
            )
            dados.append(linha)
        return pd.DataFrame(dados, columns=COLUNAS_PADRAO)

    if df_site.empty:
        df = df_planilha.copy()
        dados = []
        for _, row in df.iterrows():
            linha = _consolidar_linha(
                {f"{col}_plan": row.get(col, "") for col in COLUNAS_PADRAO} | {f"{col}_site": "" for col in COLUNAS_PADRAO},
                estoque_padrao=estoque_padrao,
                base_url=url_base,
            )
            dados.append(linha)
        return pd.DataFrame(dados, columns=COLUNAS_PADRAO)

    # chaves inteligentes
    plan = df_planilha.copy()
    site = df_site.copy()

    plan["_chave"] = plan.apply(_construir_chave, axis=1)
    site["_chave"] = site.apply(_construir_chave, axis=1)

    # se alguma chave vier vazia, cria fallback
    plan["_chave"] = plan.apply(
        lambda r: r["_chave"] if limpar(r["_chave"]) else f"PLAN::{gerar_codigo_fallback(r.get('Produto', '') or r.get('Link', ''))}",
        axis=1
    )
    site["_chave"] = site.apply(
        lambda r: r["_chave"] if limpar(r["_chave"]) else f"SITE::{gerar_codigo_fallback(r.get('Produto', '') or r.get('Link', ''))}",
        axis=1
    )

    base = pd.merge(
        plan,
        site,
        on="_chave",
        how="outer",
        suffixes=("_plan", "_site")
    )

    dados_finais = []

    for _, row in base.iterrows():
        consolidado = _consolidar_linha(
            row,
            estoque_padrao=estoque_padrao,
            base_url=url_base,
        )
        dados_finais.append(consolidado)

    df_final = pd.DataFrame(dados_finais, columns=COLUNAS_PADRAO)

    # deduplicação final inteligente
    df_final["_dedupe"] = df_final.apply(_construir_chave, axis=1)

    # se ainda vier vazio, usa produto
    df_final["_dedupe"] = df_final.apply(
        lambda r: r["_dedupe"] if limpar(r["_dedupe"]) else f"FALLBACK::{limpar(r.get('Produto', '')).lower()}",
        axis=1
    )

    df_final = df_final.drop_duplicates(subset=["_dedupe"], keep="first").copy()
    df_final = df_final.drop(columns=["_dedupe"])

    # ordem e limpeza final
    df_final = df_final.fillna("")
    df_final = df_final[COLUNAS_PADRAO].reset_index(drop=True)

    return df_final
