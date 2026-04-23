from __future__ import annotations

from typing import Any

import pandas as pd

from bling_app_zero.ui.app_helpers import (
    blindar_df_para_bling,
    log_debug,
    normalizar_imagens_pipe,
    normalizar_texto,
    safe_df_estrutura,
)


def normalizar_nome_coluna(valor: Any) -> str:
    return normalizar_texto(str(valor or ""))


def eh_coluna_video(nome_coluna: Any) -> bool:
    nome = normalizar_nome_coluna(nome_coluna)
    return bool(nome and any(token in nome for token in ["video", "vídeo", "youtube"]))


def zerar_colunas_video(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()

    base = df.copy().fillna("")
    colunas_video = [str(col) for col in base.columns if eh_coluna_video(col)]

    for coluna in colunas_video:
        base[coluna] = ""

    if colunas_video:
        log_debug(
            f"Blindagem final aplicada nas colunas de vídeo: {', '.join(colunas_video)}",
            nivel="INFO",
        )

    return base.fillna("")


def normalizar_df_visual(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()

    base = df.copy().fillna("")
    for col in base.columns:
        nome = str(col).strip().lower()
        if nome in {"url imagens", "url imagem", "imagens", "imagem"} or "imagem" in nome:
            base[col] = base[col].apply(normalizar_imagens_pipe)

    base = zerar_colunas_video(base)
    return base


def coluna_por_match_ou_parcial(df: pd.DataFrame, exatos: list[str], parciais: list[str]) -> str:
    if not isinstance(df, pd.DataFrame) or len(df.columns) == 0:
        return ""

    mapa = {normalizar_texto(c): str(c) for c in df.columns}

    for nome in exatos:
        achado = mapa.get(normalizar_texto(nome))
        if achado:
            return achado

    for col in df.columns:
        nome_col = normalizar_texto(col)
        if any(parcial in nome_col for parcial in parciais):
            return str(col)

    return ""


def coluna_codigo(df: pd.DataFrame) -> str:
    return coluna_por_match_ou_parcial(
        df,
        ["Código", "codigo", "Código do produto", "SKU", "Sku", "sku"],
        ["codigo", "código", "cod", "sku", "referencia", "referência", "id produto"],
    )


def coluna_descricao(df: pd.DataFrame) -> str:
    return coluna_por_match_ou_parcial(
        df,
        ["Descrição", "descricao", "Descrição do produto", "Nome", "nome", "Título", "titulo"],
        ["descricao", "descrição", "nome", "titulo", "título", "produto"],
    )


def coluna_preco(df: pd.DataFrame) -> str:
    return coluna_por_match_ou_parcial(
        df,
        [
            "Preço de venda",
            "Preço unitário (OBRIGATÓRIO)",
            "Preço calculado",
            "Preço",
            "preco",
            "preço",
        ],
        ["preco", "preço", "valor", "unitario", "unitário", "venda"],
    )


def coluna_gtin(df: pd.DataFrame) -> str:
    return coluna_por_match_ou_parcial(
        df,
        ["GTIN/EAN", "GTIN", "EAN", "gtin", "ean"],
        ["gtin", "ean", "codigo de barras", "código de barras"],
    )


def serie_texto_limpa(df: pd.DataFrame, coluna: str) -> pd.Series:
    if not isinstance(df, pd.DataFrame) or not coluna or coluna not in df.columns:
        return pd.Series(dtype="object")

    return (
        df[coluna]
        .astype(str)
        .str.strip()
        .replace({"nan": "", "None": "", "none": ""})
    )


def garantir_coluna_codigo_canonica(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()

    base = df.copy().fillna("")
    candidatos = [
        "Código",
        "codigo",
        "Código do produto",
        "SKU",
        "Sku",
        "sku",
        "ID Produto",
        "Id Produto",
        "ID do Produto",
        "Referencia",
        "Referência",
        "Ref",
    ]

    coluna_origem = coluna_por_match_ou_parcial(
        base,
        candidatos,
        ["codigo", "código", "sku", "referencia", "referência", "id produto", "id do produto"],
    )

    if "Código" not in base.columns:
        base["Código"] = ""

    serie_codigo = serie_texto_limpa(base, "Código")
    if serie_codigo.empty or serie_codigo.eq("").all():
        if coluna_origem and coluna_origem in base.columns:
            serie_origem = serie_texto_limpa(base, coluna_origem)
            if not serie_origem.empty and not serie_origem.eq("").all():
                base["Código"] = serie_origem
                log_debug(f"Coluna canônica Código criada a partir de: {coluna_origem}", nivel="INFO")

    serie_codigo = serie_texto_limpa(base, "Código")
    if serie_codigo.empty or serie_codigo.eq("").all():
        base["Código"] = [f"PROD_{i+1:05d}" for i in range(len(base.index))]
        log_debug("Código automático gerado no preview final por ausência de coluna válida.", nivel="INFO")

    return base.fillna("")


def garantir_coluna_descricao_canonica(df: pd.DataFrame, tipo_operacao: str) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()

    base = df.copy().fillna("")
    operacao = normalizar_texto(tipo_operacao) or "cadastro"

    candidatos_exatos = [
        "Descrição",
        "descricao",
        "Descrição do produto",
        "Nome",
        "nome",
        "Título",
        "titulo",
        "Descrição Curta",
        "Descricao Curta",
    ]
    coluna_desc = coluna_por_match_ou_parcial(
        base,
        candidatos_exatos,
        ["descricao", "descrição", "nome", "titulo", "título"],
    )
    coluna_cod = coluna_por_match_ou_parcial(
        base,
        ["Código", "codigo", "Código do produto", "SKU", "Sku", "sku", "ID Produto", "Id Produto"],
        ["codigo", "código", "sku", "referencia", "referência", "id produto"],
    )

    if "Descrição" not in base.columns:
        base["Descrição"] = ""

    serie_desc = serie_texto_limpa(base, "Descrição")
    if serie_desc.empty or serie_desc.eq("").all():
        if coluna_desc and coluna_desc in base.columns and coluna_desc != coluna_cod:
            serie_origem = serie_texto_limpa(base, coluna_desc)
            if not serie_origem.empty and not serie_origem.eq("").all():
                base["Descrição"] = serie_origem
                log_debug(f"Coluna canônica Descrição criada a partir de: {coluna_desc}", nivel="INFO")

    serie_desc = serie_texto_limpa(base, "Descrição")
    serie_codigo = serie_texto_limpa(base, "Código") if "Código" in base.columns else pd.Series(dtype="object")

    if operacao == "estoque":
        precisa_fallback = serie_desc.empty or serie_desc.eq("").all() or (
            not serie_codigo.empty and serie_desc.equals(serie_codigo)
        )
        if precisa_fallback:
            base["Descrição"] = [
                f"Produto {codigo}" if str(codigo).strip() else f"Produto {i+1}"
                for i, codigo in enumerate(serie_codigo.tolist() or [""] * len(base.index))
            ]
            log_debug(
                "Descrição canônica gerada automaticamente no preview final para operação de estoque.",
                nivel="INFO",
            )

    return base.fillna("")


def garantir_coluna_descricao_curta_canonica(df: pd.DataFrame, tipo_operacao: str) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()

    base = df.copy().fillna("")
    operacao = normalizar_texto(tipo_operacao) or "cadastro"

    coluna_curta = coluna_por_match_ou_parcial(
        base,
        ["Descrição Curta", "Descricao Curta"],
        ["descricao curta", "descrição curta"],
    )
    coluna_desc = coluna_por_match_ou_parcial(
        base,
        ["Descrição", "descricao", "Descrição do produto", "Nome", "nome", "Título", "titulo"],
        ["descricao", "descrição", "nome", "titulo", "título"],
    )

    if "Descrição Curta" not in base.columns:
        base["Descrição Curta"] = ""

    serie_curta = serie_texto_limpa(base, "Descrição Curta")
    if serie_curta.empty or serie_curta.eq("").all():
        if coluna_curta and coluna_curta in base.columns and coluna_curta != "Descrição Curta":
            serie_origem = serie_texto_limpa(base, coluna_curta)
            if not serie_origem.empty and not serie_origem.eq("").all():
                base["Descrição Curta"] = serie_origem
                log_debug(f"Coluna canônica Descrição Curta criada a partir de: {coluna_curta}", nivel="INFO")

    serie_curta = serie_texto_limpa(base, "Descrição Curta")
    if serie_curta.empty or serie_curta.eq("").all():
        if coluna_desc and coluna_desc in base.columns:
            serie_desc = serie_texto_limpa(base, coluna_desc)
            if not serie_desc.empty and not serie_desc.eq("").all():
                base["Descrição Curta"] = serie_desc
                log_debug("Descrição Curta preenchida automaticamente a partir da Descrição.", nivel="INFO")

    serie_curta = serie_texto_limpa(base, "Descrição Curta")
    if serie_curta.empty or serie_curta.eq("").all():
        col_cod = coluna_codigo(base)
        serie_codigo = serie_texto_limpa(base, col_cod) if col_cod else pd.Series(dtype="object")

        if operacao == "estoque":
            base["Descrição Curta"] = [
                f"Produto {codigo}" if str(codigo).strip() else f"Produto {i+1}"
                for i, codigo in enumerate(serie_codigo.tolist() or [""] * len(base.index))
            ]
        else:
            base["Descrição Curta"] = [f"Produto {i+1}" for i in range(len(base.index))]

        log_debug(
            "Descrição Curta gerada automaticamente no preview final por ausência de valor válido.",
            nivel="INFO",
        )

    return base.fillna("")


def garantir_df_final_canonico(df: pd.DataFrame, tipo_operacao: str, deposito_nome: str) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()

    base = normalizar_df_visual(df)
    base = blindar_df_para_bling(
        df=base,
        tipo_operacao_bling=tipo_operacao,
        deposito_nome=deposito_nome,
    )
    base = garantir_coluna_codigo_canonica(base)
    base = garantir_coluna_descricao_canonica(base, tipo_operacao)
    base = garantir_coluna_descricao_curta_canonica(base, tipo_operacao)
    base = zerar_colunas_video(base)

    return base.fillna("")


def contar_preenchidos(df: pd.DataFrame, coluna: str) -> int:
    if not safe_df_estrutura(df) or not coluna or coluna not in df.columns:
        return 0

    return int(
        df[coluna]
        .astype(str)
        .str.strip()
        .replace({"nan": "", "None": "", "none": ""})
        .ne("")
        .sum()
    )


def montar_resumo(df: pd.DataFrame) -> dict[str, Any]:
    codigo_col = coluna_codigo(df)
    descricao_col = coluna_descricao(df)
    preco_col = coluna_preco(df)
    gtin_col = coluna_gtin(df)

    return {
        "linhas": int(len(df.index)) if isinstance(df, pd.DataFrame) else 0,
        "colunas": int(len(df.columns)) if isinstance(df, pd.DataFrame) else 0,
        "codigo_col": codigo_col,
        "descricao_col": descricao_col,
        "preco_col": preco_col,
        "gtin_col": gtin_col,
        "codigo_ok": contar_preenchidos(df, codigo_col),
        "descricao_ok": contar_preenchidos(df, descricao_col),
        "preco_ok": contar_preenchidos(df, preco_col),
        "gtin_ok": contar_preenchidos(df, gtin_col),
    }
