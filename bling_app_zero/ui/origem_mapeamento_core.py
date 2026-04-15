
from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import log_debug, safe_df_dados, safe_df_estrutura
from bling_app_zero.ui.origem_dados_handlers import (
    criar_modelo_vazio_para_operacao,
    nome_coluna_preco_saida,
    safe_float,
    safe_int,
    safe_str,
)


def _normalizar_nome(nome) -> str:
    return (
        safe_str(nome)
        .lower()
        .replace("ã", "a")
        .replace("á", "a")
        .replace("à", "a")
        .replace("â", "a")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ô", "o")
        .replace("õ", "o")
        .replace("ú", "u")
        .replace("ç", "c")
        .strip()
    )


def obter_df_base_para_mapeamento() -> pd.DataFrame:
    for chave in ["df_saida", "df_final", "df_precificado", "df_origem"]:
        df = st.session_state.get(chave)
        if safe_df_dados(df):
            return df.copy()
    return pd.DataFrame()


def obter_modelo_destino() -> pd.DataFrame:
    for chave in ["df_modelo_cadastro", "df_modelo_estoque", "df_modelo"]:
        df = st.session_state.get(chave)
        if safe_df_estrutura(df):
            return df.copy()
    return criar_modelo_vazio_para_operacao()


def _sugestoes_automaticas(df_origem: pd.DataFrame, df_modelo: pd.DataFrame) -> dict[str, str]:
    origem_norm = {_normalizar_nome(col): col for col in df_origem.columns}
    mapeamento: dict[str, str] = {}

    aliases = {
        "Código": ["codigo", "sku", "referencia", "código"],
        "Descrição": ["titulo", "descricao", "descrição", "nome"],
        "Descrição Curta": ["descricao", "descrição", "nome", "titulo"],
        "Preço de venda": ["preco de venda", "preco", "valor", "preço"],
        "GTIN/EAN": ["gtin", "ean", "codigo de barras"],
        "Marca": ["marca"],
        "Categoria": ["categoria", "departamento"],
        "Imagens": ["imagem", "imagens", "url imagem", "foto"],
        "ID Produto": ["id", "id produto"],
        "Codigo produto *": ["codigo", "sku", "referencia"],
        "GTIN **": ["gtin", "ean", "codigo de barras"],
        "Descrição Produto": ["descricao", "descrição", "nome", "titulo"],
        "Balanço (OBRIGATÓRIO)": ["estoque", "saldo", "quantidade"],
        "Preço unitário (OBRIGATÓRIO)": ["preco", "valor", "preço"],
        "Preço de Custo": ["custo", "preco custo", "preço de custo"],
        "Observação": ["observacao", "observação"],
        "Data": ["data"],
    }

    for destino in df_modelo.columns:
        for alias in aliases.get(destino, []):
            alias_norm = _normalizar_nome(alias)
            for origem_norm_nome, origem_real in origem_norm.items():
                if alias_norm in origem_norm_nome:
                    mapeamento[destino] = origem_real
                    break
            if destino in mapeamento:
                break

    coluna_preco_calc = safe_str(st.session_state.get("precificacao_coluna_resultado"))
    if coluna_preco_calc and coluna_preco_calc in df_origem.columns:
        nome_preco = nome_coluna_preco_saida()
        if nome_preco in df_modelo.columns:
            mapeamento[nome_preco] = coluna_preco_calc

    return mapeamento


def inicializar_mapeamento(df_origem: pd.DataFrame, df_modelo: pd.DataFrame) -> dict[str, str]:
    mapping = st.session_state.get("mapping_origem")
    if isinstance(mapping, dict) and mapping:
        return mapping

    mapping_auto = _sugestoes_automaticas(df_origem, df_modelo)
    st.session_state["mapping_origem"] = mapping_auto.copy()
    st.session_state["mapping_origem_rascunho"] = mapping_auto.copy()
    return mapping_auto


def colunas_bloqueadas() -> set[str]:
    bloqueadas = {"ID"}
    deposito_nome = safe_str(st.session_state.get("deposito_nome"))
    if deposito_nome:
        bloqueadas.add("Deposito (OBRIGATÓRIO)")
    return bloqueadas


def construir_df_mapeado(
    df_origem: pd.DataFrame,
    df_modelo: pd.DataFrame,
    mapping: dict[str, str],
    defaults: dict[str, str] | None = None,
) -> pd.DataFrame:
    defaults = defaults or {}
    df_final = pd.DataFrame(index=df_origem.index)

    for coluna_destino in df_modelo.columns:
        origem = safe_str(mapping.get(coluna_destino))
        valor_default = safe_str(defaults.get(coluna_destino))

        if origem and origem in df_origem.columns:
            df_final[coluna_destino] = df_origem[origem]
        else:
            df_final[coluna_destino] = valor_default

    return aplicar_regras_finais(df_final)


def aplicar_regras_finais(df_final: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df_final, pd.DataFrame):
        return pd.DataFrame()

    df_out = df_final.copy()

    if "Situação" in df_out.columns:
        df_out["Situação"] = "Ativo"

    if "Descrição Curta" in df_out.columns and "Descrição" in df_out.columns:
        vazios = df_out["Descrição Curta"].astype(str).str.strip().eq("")
        df_out.loc[vazios, "Descrição Curta"] = df_out.loc[vazios, "Descrição"]

    if "Deposito (OBRIGATÓRIO)" in df_out.columns:
        deposito_nome = safe_str(st.session_state.get("deposito_nome"))
        if deposito_nome:
            df_out["Deposito (OBRIGATÓRIO)"] = deposito_nome

    if "Balanço (OBRIGATÓRIO)" in df_out.columns:
        serie = df_out["Balanço (OBRIGATÓRIO)"].astype(str).str.strip()
        vazio = serie.eq("")
        valor_padrao = safe_int(st.session_state.get("estoque_padrao_manual"), 0)
        df_out.loc[vazio, "Balanço (OBRIGATÓRIO)"] = valor_padrao

    if "Preço unitário (OBRIGATÓRIO)" in df_out.columns:
        df_out["Preço unitário (OBRIGATÓRIO)"] = df_out["Preço unitário (OBRIGATÓRIO)"].apply(
            lambda v: round(safe_float(v, 0.0), 2)
        )

    if "Preço de venda" in df_out.columns:
        df_out["Preço de venda"] = df_out["Preço de venda"].apply(
            lambda v: round(safe_float(v, 0.0), 2)
        )

    return df_out.replace({None: ""}).fillna("")


def salvar_resultado_mapeamento(df_final: pd.DataFrame) -> None:
    st.session_state["df_preview_mapeamento"] = df_final.copy()
    st.session_state["df_saida"] = df_final.copy()
    st.session_state["df_final"] = df_final.copy()
    st.session_state["mapeamento_validado"] = True
    log_debug(f"[MAPEAMENTO] df_final atualizado com {len(df_final)} linha(s).", "INFO")
