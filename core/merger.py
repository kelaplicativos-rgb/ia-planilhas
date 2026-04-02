import pandas as pd

from core.logger import log
from core.utils import limpar, parse_preco


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


def _garantir_dataframe(df):
    if df is None:
        return pd.DataFrame(columns=COLUNAS_PADRAO)
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame(columns=COLUNAS_PADRAO)
    return df.copy()


def _garantir_colunas(df):
    df = _garantir_dataframe(df)

    for col in COLUNAS_PADRAO:
        if col not in df.columns:
            df[col] = ""

    df = df[COLUNAS_PADRAO].copy()
    df = df.fillna("")
    return df


def _txt(v):
    return limpar(v)


def _normalizar_codigo(v):
    return _txt(v)


def _normalizar_gtin(v):
    return _txt(v)


def _normalizar_link(v):
    return _txt(v).replace("\\", "")


def _normalizar_imagem(v):
    return _txt(v).replace("\\", "")


def _normalizar_situacao(v):
    txt = _txt(v).lower()

    if txt in ["inativo", "esgotado", "indisponível", "indisponivel", "sem estoque", "0"]:
        return "Inativo"

    if txt in ["ativo", "em estoque", "disponível", "disponivel", "1"]:
        return "Ativo"

    return ""


def _site_indisponivel(v):
    txt = _txt(v).lower()
    return txt in ["inativo", "esgotado", "indisponível", "indisponivel", "sem estoque", "0"]


def _site_disponivel(v):
    txt = _txt(v).lower()
    return txt in ["ativo", "em estoque", "disponível", "disponivel", "1"]


def _normalizar_estoque(v):
    txt = _txt(v)

    if txt == "":
        return ""

    txt_low = txt.lower()

    if txt_low in ["esgotado", "indisponível", "indisponivel", "sem estoque"]:
        return 0

    if txt_low in ["em estoque", "disponível", "disponivel"]:
        return 1

    try:
        return int(float(str(txt).replace(",", ".")))
    except Exception:
        return ""


def _chave_merge(row):
    codigo = _normalizar_codigo(row.get("Código", ""))
    gtin = _normalizar_gtin(row.get("GTIN", ""))
    link = _normalizar_link(row.get("Link", ""))
    produto = _txt(row.get("Produto", "")).lower()

    if codigo:
        return f"COD::{codigo}"

    if gtin:
        return f"GTIN::{gtin}"

    if link:
        return f"LINK::{link}"

    if produto:
        return f"PROD::{produto}"

    return ""


def _escolher_texto(plan, site):
    site = _txt(site)
    plan = _txt(plan)
    return site or plan


def _escolher_catalogo(plan, site, campo):
    """
    Regra geral de catálogo:
    site > planilha
    """
    if campo == "Imagem":
        return _normalizar_imagem(site) or _normalizar_imagem(plan)

    if campo == "Link":
        return _normalizar_link(site) or _normalizar_link(plan)

    if campo in ["Preço", "Preço Custo"]:
        default = "" if campo == "Preço Custo" else "0.01"
        site_v = _txt(site)
        plan_v = _txt(plan)

        if site_v:
            return parse_preco(site_v, default)
        if plan_v:
            return parse_preco(plan_v, default)
        return default

    return _escolher_texto(plan, site)


def _resolver_estoque(
    plan_estoque,
    site_estoque,
    site_situacao,
    estoque_padrao,
    tem_planilha,
    tem_site,
):
    """
    REGRA FINAL:

    Só Planilha:
      - usa planilha

    Só Site:
      - site esgotado -> 0
      - site com número -> usa número do site
      - site disponível sem número -> estoque_padrao
      - senão -> 0

    Planilha + Site:
      - site vence
      - site esgotado -> 0
      - site com número -> usa número do site
      - site disponível sem número -> estoque_padrao
      - se não houver dado útil do site -> cai para planilha
    """
    plan_v = _normalizar_estoque(plan_estoque)
    site_v = _normalizar_estoque(site_estoque)
    site_sit = _normalizar_situacao(site_situacao)

    # Só Planilha
    if tem_planilha and not tem_site:
        if plan_v != "":
            return int(plan_v)
        return 0

    # Só Site
    if tem_site and not tem_planilha:
        if _site_indisponivel(site_sit) or _site_indisponivel(site_estoque):
            return 0

        if site_v != "":
            if isinstance(site_v, int) and site_v > 1:
                return site_v

        if _site_disponivel(site_sit) or _site_disponivel(site_estoque):
            try:
                return int(float(str(estoque_padrao).replace(",", ".")))
            except Exception:
                return 0

        return 0

    # Planilha + Site
    if tem_planilha and tem_site:
        if _site_indisponivel(site_sit) or _site_indisponivel(site_estoque):
            return 0

        if site_v != "":
            if isinstance(site_v, int) and site_v > 1:
                return site_v

        if _site_disponivel(site_sit) or _site_disponivel(site_estoque):
            try:
                return int(float(str(estoque_padrao).replace(",", ".")))
            except Exception:
                return 0

        if plan_v != "":
            return int(plan_v)

        return 0

    return 0


def _resolver_situacao(plan_situacao, site_situacao, estoque_final, tem_site):
    """
    Se houver site:
      - site indisponível -> Inativo
      - senão estoque > 0 -> Ativo
      - senão -> Inativo

    Se não houver site:
      - estoque > 0 -> Ativo
      - senão -> Inativo
    """
    site_sit = _normalizar_situacao(site_situacao)

    if tem_site and _site_indisponivel(site_sit):
        return "Inativo"

    try:
        est = int(estoque_final)
        return "Ativo" if est > 0 else "Inativo"
    except Exception:
        return "Inativo"


def _consolidar_linha(row, estoque_padrao, tem_planilha, tem_site):
    out = {}

    for campo in [
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
        "NCM",
        "Origem",
        "Peso Líquido",
        "Peso Bruto",
        "Estoque Mínimo",
        "Estoque Máximo",
        "Unidade",
        "Tipo",
    ]:
        out[campo] = _escolher_catalogo(
            row.get(f"{campo}_plan", ""),
            row.get(f"{campo}_site", ""),
            campo,
        )

    out["Estoque"] = _resolver_estoque(
        row.get("Estoque_plan", ""),
        row.get("Estoque_site", ""),
        row.get("Situação_site", ""),
        estoque_padrao,
        tem_planilha=tem_planilha,
        tem_site=tem_site,
    )

    out["Situação"] = _resolver_situacao(
        row.get("Situação_plan", ""),
        row.get("Situação_site", ""),
        out["Estoque"],
        tem_site=tem_site,
    )

    if not _txt(out["Descrição Curta"]):
        out["Descrição Curta"] = _txt(out["Produto"])

    if not _txt(out["Origem"]):
        out["Origem"] = "0"

    if not _txt(out["Unidade"]):
        out["Unidade"] = "UN"

    if not _txt(out["Tipo"]):
        out["Tipo"] = "Produto"

    if not _txt(out["Preço"]):
        out["Preço"] = "0.01"

    if not _txt(out["Código"]):
        out["Código"] = _normalizar_codigo(row.get("Código_site", "")) or _normalizar_codigo(row.get("Código_plan", ""))

    return out


def merge_dados(df_planilha, df_site, url_base="", estoque_padrao=0):
    df_planilha = _garantir_colunas(df_planilha)
    df_site = _garantir_colunas(df_site)

    tem_planilha = not df_planilha.empty
    tem_site = not df_site.empty

    if not tem_planilha and not tem_site:
        log("merge_dados: planilha e site vazios")
        return pd.DataFrame(columns=COLUNAS_PADRAO)

    df_planilha["_merge_key"] = df_planilha.apply(_chave_merge, axis=1)
    df_site["_merge_key"] = df_site.apply(_chave_merge, axis=1)

    df_planilha = df_planilha[df_planilha["_merge_key"] != ""].copy()
    df_site = df_site[df_site["_merge_key"] != ""].copy()

    df_planilha = df_planilha.drop_duplicates(subset=["_merge_key"], keep="first")
    df_site = df_site.drop_duplicates(subset=["_merge_key"], keep="first")

    if df_planilha.empty and not df_site.empty:
        linhas = []
        for _, row in df_site.iterrows():
            linha = _consolidar_linha(
                {f"{col}_plan": "" for col in COLUNAS_PADRAO}
                | {f"{col}_site": row.get(col, "") for col in COLUNAS_PADRAO},
                estoque_padrao,
                tem_planilha=False,
                tem_site=True,
            )
            linhas.append(linha)

        base = pd.DataFrame(linhas)
        return _garantir_colunas(base)

    if df_site.empty and not df_planilha.empty:
        linhas = []
        for _, row in df_planilha.iterrows():
            linha = _consolidar_linha(
                {f"{col}_plan": row.get(col, "") for col in COLUNAS_PADRAO}
                | {f"{col}_site": "" for col in COLUNAS_PADRAO},
                estoque_padrao,
                tem_planilha=True,
                tem_site=False,
            )
            linhas.append(linha)

        base = pd.DataFrame(linhas)
        return _garantir_colunas(base)

    plan_cols = {col: f"{col}_plan" for col in COLUNAS_PADRAO}
    site_cols = {col: f"{col}_site" for col in COLUNAS_PADRAO}

    df_plan = df_planilha.rename(columns=plan_cols)
    df_site2 = df_site.rename(columns=site_cols)

    merged = df_plan.merge(
        df_site2,
        left_on="_merge_key",
        right_on="_merge_key",
        how="outer",
    )

    linhas = []
    for _, row in merged.iterrows():
        linhas.append(
            _consolidar_linha(
                row,
                estoque_padrao,
                tem_planilha=True,
                tem_site=True,
            )
        )

    df_final = pd.DataFrame(linhas)

    if df_final.empty:
        return pd.DataFrame(columns=COLUNAS_PADRAO)

    df_final["Código"] = df_final["Código"].apply(_normalizar_codigo)
    df_final["GTIN"] = df_final["GTIN"].apply(_normalizar_gtin)
    df_final["Link"] = df_final["Link"].apply(_normalizar_link)
    df_final["Imagem"] = df_final["Imagem"].apply(_normalizar_imagem)

    df_final = df_final[df_final["Produto"].astype(str).str.strip() != ""].copy()

    codigos_validos = df_final["Código"].astype(str).str.strip() != ""
    df_com_codigo = df_final[codigos_validos].drop_duplicates(subset=["Código"], keep="first")
    df_sem_codigo = df_final[~codigos_validos].copy()

    if not df_sem_codigo.empty:
        gtin_validos = df_sem_codigo["GTIN"].astype(str).str.strip() != ""
        df_sem_codigo_gtin = df_sem_codigo[gtin_validos].drop_duplicates(subset=["GTIN"], keep="first")
        df_sem_codigo_sem_gtin = df_sem_codigo[~gtin_validos].drop_duplicates(subset=["Produto"], keep="first")
        df_final = pd.concat([df_com_codigo, df_sem_codigo_gtin, df_sem_codigo_sem_gtin], ignore_index=True)
    else:
        df_final = df_com_codigo

    df_final = _garantir_colunas(df_final)

    log(
        f"merge_dados finalizado | "
        f"planilha={len(df_planilha)} | site={len(df_site)} | final={len(df_final)}"
    )

    return df_final.reset_index(drop=True)
