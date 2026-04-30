from __future__ import annotations

import re
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
        log_debug(f"Blindagem final aplicada nas colunas de vídeo: {', '.join(colunas_video)}", nivel="INFO")
    return base.fillna("")


def remover_colunas_artificiais(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    base = df.copy().fillna("")
    remover = []
    for col in base.columns:
        nome = str(col).strip().lower()
        if nome.startswith("unnamed:") or nome in {"index", "level_0"}:
            remover.append(col)
    if remover:
        base = base.drop(columns=remover, errors="ignore")
        log_debug(f"Colunas artificiais removidas do preview final: {', '.join(map(str, remover))}", nivel="INFO")
    return base.fillna("")


def normalizar_df_visual(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    base = remover_colunas_artificiais(df.copy().fillna(""))
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
    parciais_norm = [normalizar_texto(p) for p in parciais]
    for col in df.columns:
        nome_col = normalizar_texto(col)
        if any(parcial and parcial in nome_col for parcial in parciais_norm):
            return str(col)
    return ""


def coluna_codigo(df: pd.DataFrame) -> str:
    return coluna_por_match_ou_parcial(
        df,
        ["Código", "codigo", "Código do produto", "Codigo produto *", "Código produto *", "SKU", "Sku", "sku"],
        ["codigo", "código", "cod", "sku", "referencia", "referência", "id produto"],
    )


def coluna_descricao(df: pd.DataFrame) -> str:
    return coluna_por_match_ou_parcial(
        df,
        ["Descrição", "descricao", "Descrição do produto", "Descrição Produto", "Nome", "nome", "Título", "titulo"],
        ["descricao", "descrição", "nome", "titulo", "título", "produto"],
    )


def coluna_preco(df: pd.DataFrame) -> str:
    return coluna_por_match_ou_parcial(
        df,
        ["Preço de venda", "Preço unitário (OBRIGATÓRIO)", "Preço unitário", "Preço calculado", "Preço", "preco", "preço", "Preço de Custo"],
        ["preco", "preço", "valor", "unitario", "unitário", "venda", "custo"],
    )


def coluna_gtin(df: pd.DataFrame) -> str:
    return coluna_por_match_ou_parcial(
        df,
        ["GTIN/EAN", "GTIN", "GTIN **", "EAN", "gtin", "ean"],
        ["gtin", "ean", "codigo de barras", "código de barras"],
    )


def coluna_estoque(df: pd.DataFrame) -> str:
    return coluna_por_match_ou_parcial(
        df,
        ["Balanço (OBRIGATÓRIO)", "Balanço", "Balanco", "Estoque", "estoque", "Quantidade", "quantidade", "quantidade_real", "stock"],
        ["balanco", "balanço", "estoque", "quantidade", "qtd", "stock", "saldo"],
    )


def coluna_deposito(df: pd.DataFrame) -> str:
    return coluna_por_match_ou_parcial(
        df,
        ["Depósito (OBRIGATÓRIO)", "Deposito (OBRIGATÓRIO)", "Depósito", "Deposito"],
        ["deposito", "depósito"],
    )


def serie_texto_limpa(df: pd.DataFrame, coluna: str) -> pd.Series:
    if not isinstance(df, pd.DataFrame) or not coluna or coluna not in df.columns:
        return pd.Series(dtype="object")
    return df[coluna].astype(str).str.strip().replace({"nan": "", "None": "", "none": ""})


def contar_preenchidos(df: pd.DataFrame, coluna: str) -> int:
    if not safe_df_estrutura(df) or not coluna or coluna not in df.columns:
        return 0
    return int(serie_texto_limpa(df, coluna).ne("").sum())


def _extrair_primeiro_preco_texto(texto: object) -> str:
    raw = str(texto or "")
    match = re.search(r"R\$\s*([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2}|[0-9]+,[0-9]{2}|[0-9]+\.[0-9]{2})", raw, flags=re.I)
    if not match:
        return ""
    valor = match.group(1).strip()
    if "," in valor:
        valor = valor.replace(".", "").replace(",", ".")
    return valor


def _valor_numerico_texto(valor: object) -> str:
    texto = str(valor or "").strip()
    if not texto:
        return ""
    if re.search(r"[a-zA-ZÀ-ÿ]", texto) and not re.search(r"R\$\s*\d", texto, flags=re.I):
        return ""
    match = re.search(r"-?\d+(?:[\.,]\d+)?", texto)
    if not match:
        return ""
    numero = match.group(0).replace(".", "").replace(",", ".") if "," in match.group(0) else match.group(0)
    return numero


def _estoque_por_texto(row: pd.Series) -> str:
    texto = " ".join(str(v or "") for v in row.tolist()).lower()
    if any(token in texto for token in ["esgotado", "sem estoque", "indisponivel", "indisponível", "fora de estoque", "zerado"]):
        return "0"
    # Se veio de site com produto/código/preço, mas sem quantidade real, usar 1 como disponível operacional.
    if any(token in texto for token in [" r$", "cód:", "cod:", "comprar", "no pix", "cartao", "cartão"]):
        return "1"
    return ""


def _preco_por_linha(row: pd.Series) -> str:
    for valor in row.tolist():
        preco = _extrair_primeiro_preco_texto(valor)
        if preco:
            return preco
    return ""


def garantir_coluna_codigo_canonica(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    base = df.copy().fillna("")
    coluna_origem = coluna_por_match_ou_parcial(
        base,
        ["Código", "codigo", "Codigo produto *", "Código produto *", "Código do produto", "SKU", "Sku", "sku", "ID Produto", "Id Produto", "ID do Produto", "Referencia", "Referência", "Ref"],
        ["codigo", "código", "sku", "referencia", "referência", "id produto", "id do produto"],
    )
    if "Código" not in base.columns:
        base["Código"] = ""
    serie_codigo = serie_texto_limpa(base, "Código")
    if (serie_codigo.empty or serie_codigo.eq("").all()) and coluna_origem and coluna_origem in base.columns:
        serie_origem = serie_texto_limpa(base, coluna_origem)
        if not serie_origem.empty and not serie_origem.eq("").all():
            base["Código"] = serie_origem
            log_debug(f"Coluna canônica Código criada a partir de: {coluna_origem}", nivel="INFO")
    if serie_texto_limpa(base, "Código").eq("").all():
        gtin_col = coluna_gtin(base)
        if gtin_col:
            gtin = serie_texto_limpa(base, gtin_col)
            if not gtin.eq("").all():
                base["Código"] = gtin
                log_debug(f"Código preenchido a partir do GTIN: {gtin_col}", nivel="INFO")
    if serie_texto_limpa(base, "Código").eq("").all():
        base["Código"] = [f"PROD_{i+1:05d}" for i in range(len(base.index))]
        log_debug("Código automático gerado no preview final por ausência de coluna válida.", nivel="INFO")
    return base.fillna("")


def garantir_coluna_descricao_canonica(df: pd.DataFrame, tipo_operacao: str) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    base = df.copy().fillna("")
    operacao = normalizar_texto(tipo_operacao) or "cadastro"
    coluna_desc = coluna_por_match_ou_parcial(
        base,
        ["Descrição", "descricao", "Descrição do produto", "Descrição Produto", "Nome", "nome", "Título", "titulo", "Descrição Curta", "Descricao Curta"],
        ["descricao", "descrição", "nome", "titulo", "título", "produto"],
    )
    coluna_cod = coluna_codigo(base)
    if "Descrição" not in base.columns:
        base["Descrição"] = ""
    serie_desc = serie_texto_limpa(base, "Descrição")
    if (serie_desc.empty or serie_desc.eq("").all()) and coluna_desc and coluna_desc in base.columns and coluna_desc != coluna_cod:
        serie_origem = serie_texto_limpa(base, coluna_desc)
        if not serie_origem.empty and not serie_origem.eq("").all():
            base["Descrição"] = serie_origem
            log_debug(f"Coluna canônica Descrição criada a partir de: {coluna_desc}", nivel="INFO")
    serie_desc = serie_texto_limpa(base, "Descrição")
    serie_codigo = serie_texto_limpa(base, "Código") if "Código" in base.columns else pd.Series(dtype="object")
    if operacao == "estoque":
        precisa_fallback = serie_desc.empty or serie_desc.eq("").all() or (not serie_codigo.empty and serie_desc.equals(serie_codigo))
        if precisa_fallback:
            base["Descrição"] = [f"Produto {codigo}" if str(codigo).strip() else f"Produto {i+1}" for i, codigo in enumerate(serie_codigo.tolist() or [""] * len(base.index))]
            log_debug("Descrição canônica gerada automaticamente no preview final para operação de estoque.", nivel="INFO")
    return base.fillna("")


def garantir_coluna_descricao_curta_canonica(df: pd.DataFrame, tipo_operacao: str) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    base = df.copy().fillna("")
    operacao = normalizar_texto(tipo_operacao) or "cadastro"
    coluna_curta = coluna_por_match_ou_parcial(base, ["Descrição Curta", "Descricao Curta"], ["descricao curta", "descrição curta"])
    coluna_desc = coluna_descricao(base)
    if "Descrição Curta" not in base.columns:
        base["Descrição Curta"] = ""
    if serie_texto_limpa(base, "Descrição Curta").eq("").all():
        origem = coluna_curta if coluna_curta and coluna_curta != "Descrição Curta" else coluna_desc
        if origem and origem in base.columns:
            base["Descrição Curta"] = serie_texto_limpa(base, origem)
            log_debug(f"Descrição Curta preenchida automaticamente a partir de: {origem}", nivel="INFO")
    if serie_texto_limpa(base, "Descrição Curta").eq("").all():
        col_cod = coluna_codigo(base)
        serie_codigo = serie_texto_limpa(base, col_cod) if col_cod else pd.Series(dtype="object")
        if operacao == "estoque":
            base["Descrição Curta"] = [f"Produto {codigo}" if str(codigo).strip() else f"Produto {i+1}" for i, codigo in enumerate(serie_codigo.tolist() or [""] * len(base.index))]
        else:
            base["Descrição Curta"] = [f"Produto {i+1}" for i in range(len(base.index))]
        log_debug("Descrição Curta gerada automaticamente no preview final por ausência de valor válido.", nivel="INFO")
    return base.fillna("")


def garantir_colunas_estoque_canonicas(df: pd.DataFrame, tipo_operacao: str, deposito_nome: str) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    base = df.copy().fillna("")
    operacao = normalizar_texto(tipo_operacao) or "cadastro"
    if operacao != "estoque":
        return base.fillna("")

    if "Balanço (OBRIGATÓRIO)" not in base.columns:
        base["Balanço (OBRIGATÓRIO)"] = ""
    if "Deposito (OBRIGATÓRIO)" not in base.columns and "Depósito (OBRIGATÓRIO)" not in base.columns:
        base["Deposito (OBRIGATÓRIO)"] = ""
    dep_col = coluna_deposito(base)
    if dep_col and deposito_nome:
        base[dep_col] = str(deposito_nome).strip()

    estoque_col = coluna_estoque(base)
    serie_balanco = serie_texto_limpa(base, "Balanço (OBRIGATÓRIO)")
    if serie_balanco.empty or serie_balanco.eq("").any():
        valores = []
        for idx, row in base.iterrows():
            atual = str(base.at[idx, "Balanço (OBRIGATÓRIO)"]).strip()
            if atual:
                valores.append(atual)
                continue
            origem = ""
            if estoque_col and estoque_col in base.columns and estoque_col != "Balanço (OBRIGATÓRIO)":
                origem = _valor_numerico_texto(row.get(estoque_col, ""))
            if not origem:
                origem = _estoque_por_texto(row)
            valores.append(origem if origem != "" else "0")
        base["Balanço (OBRIGATÓRIO)"] = valores
        log_debug("Balanço (OBRIGATÓRIO) preenchido automaticamente para atualização de estoque.", nivel="INFO")

    return base.fillna("")


def garantir_colunas_preco_canonicas(df: pd.DataFrame, tipo_operacao: str) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    base = df.copy().fillna("")
    alvo_preco = "Preço unitário (OBRIGATÓRIO)"
    if alvo_preco not in base.columns:
        base[alvo_preco] = ""
    if "Preço de Custo" not in base.columns:
        base["Preço de Custo"] = ""

    preco_col = coluna_preco(base)
    for alvo in [alvo_preco, "Preço de Custo"]:
        serie = serie_texto_limpa(base, alvo)
        if serie.empty or serie.eq("").any():
            novos = []
            for idx, row in base.iterrows():
                atual = str(base.at[idx, alvo]).strip()
                if atual:
                    novos.append(atual)
                    continue
                origem = ""
                if preco_col and preco_col in base.columns and preco_col != alvo:
                    origem = _valor_numerico_texto(row.get(preco_col, ""))
                if not origem:
                    origem = _preco_por_linha(row)
                novos.append(origem)
            base[alvo] = novos
    log_debug("Preço unitário/Preço de Custo preenchidos automaticamente quando possível.", nivel="INFO")
    return base.fillna("")


def garantir_df_final_canonico(df: pd.DataFrame, tipo_operacao: str, deposito_nome: str) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    base = normalizar_df_visual(df)
    base = blindar_df_para_bling(df=base, tipo_operacao_bling=tipo_operacao, deposito_nome=deposito_nome)
    base = garantir_coluna_codigo_canonica(base)
    base = garantir_coluna_descricao_canonica(base, tipo_operacao)
    base = garantir_coluna_descricao_curta_canonica(base, tipo_operacao)
    base = garantir_colunas_estoque_canonicas(base, tipo_operacao, deposito_nome)
    base = garantir_colunas_preco_canonicas(base, tipo_operacao)
    base = remover_colunas_artificiais(base)
    base = zerar_colunas_video(base)
    return base.fillna("")


def montar_resumo(df: pd.DataFrame) -> dict[str, Any]:
    codigo_col = coluna_codigo(df)
    descricao_col = coluna_descricao(df)
    preco_col = coluna_preco(df)
    gtin_col = coluna_gtin(df)
    estoque_col = coluna_estoque(df)
    return {
        "linhas": int(len(df.index)) if isinstance(df, pd.DataFrame) else 0,
        "colunas": int(len(df.columns)) if isinstance(df, pd.DataFrame) else 0,
        "codigo_col": codigo_col,
        "descricao_col": descricao_col,
        "preco_col": preco_col,
        "gtin_col": gtin_col,
        "estoque_col": estoque_col,
        "codigo_ok": contar_preenchidos(df, codigo_col),
        "descricao_ok": contar_preenchidos(df, descricao_col),
        "preco_ok": contar_preenchidos(df, preco_col),
        "gtin_ok": contar_preenchidos(df, gtin_col),
        "estoque_ok": contar_preenchidos(df, estoque_col),
    }
