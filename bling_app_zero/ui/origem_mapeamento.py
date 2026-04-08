from __future__ import annotations

import pandas as pd
import streamlit as st


# =========================================================
# SAFE
# =========================================================
def _safe_df(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0
    except Exception:
        return False


# =========================================================
# NORMALIZAÇÃO
# =========================================================
def _normalizar_texto_coluna(valor) -> str:
    try:
        texto = str(valor if valor is not None else "").strip()
        texto = texto.replace("\n", " ").replace("\r", " ")
        while "  " in texto:
            texto = texto.replace("  ", " ")
        return texto
    except Exception:
        return ""


def _normalizar_df(df: pd.DataFrame) -> pd.DataFrame:
    try:
        df = df.copy()
        df = df.reset_index(drop=True)

        for col in df.columns:
            df[col] = df[col].astype(str)

        return df
    except Exception:
        return df


# =========================================================
# DETECÇÕES
# =========================================================
def _is_coluna_preco(nome) -> bool:
    nome = str(nome).lower()
    return any(
        p in nome
        for p in ["preço", "preco", "valor venda", "preco venda", "price"]
    )


def _is_coluna_deposito(nome) -> bool:
    nome = str(nome).lower()
    return "deposit" in nome or "depós" in nome or "deposito" in nome


# =========================================================
# PREVIEW
# =========================================================
def _preview_coluna(df, coluna):
    try:
        if coluna in df.columns:
            return df[coluna].astype(str).head(5).tolist()
    except Exception:
        pass
    return []


# =========================================================
# PRECIFICAÇÃO
# =========================================================
def _get_df_precificado():
    df = st.session_state.get("df_precificado")
    if _safe_df(df):
        return df.copy()
    return None


def _get_coluna_preco_base(df_origem):
    col = str(st.session_state.get("coluna_preco_base", "") or "").strip()
    if col in df_origem.columns:
        return col
    return ""


def _obter_serie_preco(df_origem):
    try:
        col = _get_coluna_preco_base(df_origem)
        if not col:
            return pd.Series([""] * len(df_origem))

        df_prec = _get_df_precificado()
        if df_prec is not None and col in df_prec.columns:
            return df_prec[col].reset_index(drop=True)

        return df_origem[col].reset_index(drop=True)
    except Exception:
        return pd.Series([""] * len(df_origem))


# =========================================================
# MONTAGEM FINAL (CORRIGIDO)
# =========================================================
def _montar_df_saida(df_origem, df_modelo, mapping):
    try:
        df_origem = _normalizar_df(df_origem)
        df_modelo = _normalizar_df(df_modelo)

        serie_preco = _obter_serie_preco(df_origem)

        df_saida = pd.DataFrame(index=range(len(df_origem)))

        for col in df_modelo.columns:
            origem = mapping.get(col, "")

            # PREÇO
            if _is_coluna_preco(col):
                df_saida[col] = serie_preco.astype(str)
                continue

            # DEPÓSITO
            if _is_coluna_deposito(col):
                deposito = str(st.session_state.get("deposito_nome", "") or "")
                df_saida[col] = deposito
                continue

            # MAPEAMENTO NORMAL
            if origem in df_origem.columns:
                try:
                    df_saida[col] = df_origem[origem].astype(str).reset_index(drop=True)
                except Exception:
                    df_saida[col] = ""
            else:
                df_saida[col] = ""

        return df_saida.fillna("")

    except Exception as e:
        st.error(f"Erro ao montar saída: {e}")
        return pd.DataFrame()


# =========================================================
# RENDER
# =========================================================
def render_origem_mapeamento():
    df_origem = st.session_state.get("df_origem")
    df_modelo = (
        st.session_state.get("df_modelo_cadastro")
        if st.session_state.get("tipo_operacao_bling") == "cadastro"
        else st.session_state.get("df_modelo_estoque")
    )

    if not _safe_df(df_origem) or not _safe_df(df_modelo):
        return

    df_origem = _normalizar_df(df_origem)
    df_modelo = _normalizar_df(df_modelo)

    st.markdown("## 🔗 Mapeamento de colunas")

    st.dataframe(df_origem.head(5), use_container_width=True)

    colunas_modelo = list(df_modelo.columns)
    colunas_origem = list(df_origem.columns)

    mapping = {}

    for col_modelo in colunas_modelo:

        if _is_coluna_preco(col_modelo):
            st.text_input(col_modelo, value="Calculado automaticamente", disabled=True)
            mapping[col_modelo] = ""
            continue

        if _is_coluna_deposito(col_modelo):
            deposito = st.session_state.get("deposito_nome", "")
            st.text_input(col_modelo, value=deposito or "Depósito automático", disabled=True)
            mapping[col_modelo] = ""
            continue

        escolhido = st.selectbox(
            col_modelo,
            [""] + colunas_origem,
            key=f"map_{col_modelo}",
        )

        mapping[col_modelo] = escolhido

        if escolhido:
            st.caption(_preview_coluna(df_origem, escolhido))

    df_saida = _montar_df_saida(df_origem, df_modelo, mapping)

    st.session_state["df_saida"] = df_saida.copy()
    st.session_state["df_final"] = df_saida.copy()

    st.dataframe(df_saida.head(10), use_container_width=True)
