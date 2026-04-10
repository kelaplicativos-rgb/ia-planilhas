from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import log_debug


def _safe_df(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0
    except Exception:
        return False


def _ler_arquivo_tabela(uploaded_file) -> pd.DataFrame | None:
    if uploaded_file is None:
        return None

    nome = str(getattr(uploaded_file, "name", "") or "").lower()

    try:
        if nome.endswith(".csv"):
            try:
                return pd.read_csv(uploaded_file)
            except Exception:
                uploaded_file.seek(0)
                return pd.read_csv(uploaded_file, sep=";", encoding="utf-8")

        if nome.endswith(".xlsx") or nome.endswith(".xls"):
            return pd.read_excel(uploaded_file)

        if nome.endswith(".xlsb"):
            return pd.read_excel(uploaded_file, engine="pyxlsb")

        return None

    except Exception as e:
        log_debug(f"Erro ao ler arquivo {nome}: {e}", "ERRO")
        return None


def _normalizar_df(df: pd.DataFrame) -> pd.DataFrame:
    try:
        df = df.copy()
        df.columns = [str(col).strip() for col in df.columns]

        for col in df.columns:
            df[col] = df[col].replace({None: ""}).fillna("")

        return df
    except Exception:
        return df


def _resetar_modelo_mapeamento() -> None:
    try:
        tipo = str(st.session_state.get("tipo_operacao_bling") or "").strip().lower()

        if tipo == "cadastro":
            df_modelo = st.session_state.get("df_modelo_cadastro")
        elif tipo == "estoque":
            df_modelo = st.session_state.get("df_modelo_estoque")
        else:
            df_modelo = None

        if _safe_df(df_modelo):
            st.session_state["df_modelo_mapeamento"] = df_modelo.copy()
    except Exception as e:
        log_debug(f"Erro ao resetar modelo de mapeamento: {e}", "ERRO")


def render_modelo_bling() -> None:
    st.markdown("### 📌 Modelos Bling")

    col1, col2 = st.columns(2)

    with col1:
        arq_cadastro = st.file_uploader(
            "Modelo cadastro",
            type=["xlsx", "xls", "xlsb", "csv"],
            key="upload_modelo_cadastro",
        )

        if arq_cadastro is not None:
            df_cadastro = _ler_arquivo_tabela(arq_cadastro)
            if _safe_df(df_cadastro):
                df_cadastro = _normalizar_df(df_cadastro)
                st.session_state["df_modelo_cadastro"] = df_cadastro.copy()
                log_debug(
                    f"Modelo cadastro carregado com {len(df_cadastro.columns)} coluna(s)"
                )
                st.success("Modelo cadastro carregado com sucesso.")
            else:
                st.error("Não foi possível ler o modelo cadastro.")

    with col2:
        arq_estoque = st.file_uploader(
            "Modelo estoque",
            type=["xlsx", "xls", "xlsb", "csv"],
            key="upload_modelo_estoque",
        )

        if arq_estoque is not None:
            df_estoque = _ler_arquivo_tabela(arq_estoque)
            if _safe_df(df_estoque):
                df_estoque = _normalizar_df(df_estoque)
                st.session_state["df_modelo_estoque"] = df_estoque.copy()
                log_debug(
                    f"Modelo estoque carregado com {len(df_estoque.columns)} coluna(s)"
                )
                st.success("Modelo estoque carregado com sucesso.")
            else:
                st.error("Não foi possível ler o modelo estoque.")

    tipo_atual = str(st.session_state.get("tipo_operacao_bling") or "").strip().lower()
    if tipo_atual in {"cadastro", "estoque"}:
        _resetar_modelo_mapeamento()

    df_modelo_cadastro = st.session_state.get("df_modelo_cadastro")
    df_modelo_estoque = st.session_state.get("df_modelo_estoque")

    if _safe_df(df_modelo_cadastro) or _safe_df(df_modelo_estoque):
        with st.expander("📋 Prévia dos modelos carregados", expanded=False):
            if _safe_df(df_modelo_cadastro):
                st.markdown("**Modelo cadastro**")
                st.dataframe(df_modelo_cadastro.head(5), use_container_width=True)

            if _safe_df(df_modelo_estoque):
                st.markdown("**Modelo estoque**")
                st.dataframe(df_modelo_estoque.head(5), use_container_width=True)


def render_origem_entrada() -> None:
    st.markdown("### 📥 Planilha do fornecedor")

    uploaded_file = st.file_uploader(
        "Planilha fornecedor",
        type=["xlsx", "xls", "xlsb", "csv"],
        key="upload_planilha_fornecedor",
    )

    if uploaded_file is None:
        return

    df_origem = _ler_arquivo_tabela(uploaded_file)

    if not _safe_df(df_origem):
        st.error("Não foi possível ler a planilha do fornecedor.")
        return

    df_origem = _normalizar_df(df_origem)

    st.session_state["df_origem"] = df_origem.copy()
    st.session_state["df_dados"] = df_origem.copy()

    log_debug(
        f"Planilha do fornecedor carregada com {len(df_origem)} linha(s) e {len(df_origem.columns)} coluna(s)"
    )

    st.success("Planilha do fornecedor carregada com sucesso.")

    with st.expander("📋 Prévia da planilha do fornecedor", expanded=True):
        st.dataframe(df_origem.head(20), use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "🧠 Ir para mapeamento",
            key="btn_ir_para_mapeamento_uploads",
            use_container_width=True,
        ):
            try:
                _resetar_modelo_mapeamento()
                st.session_state["etapa_origem"] = "mapeamento"
                st.session_state["etapa"] = "mapeamento"
                st.session_state["etapa_fluxo"] = "mapeamento"
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao avançar para mapeamento: {e}")

    with col2:
        if st.button(
            "🧹 Limpar planilha carregada",
            key="btn_limpar_planilha_uploads",
            use_container_width=True,
        ):
            for chave in [
                "df_origem",
                "df_dados",
                "df_saida",
                "df_final",
                "df_precificado",
                "mapping_origem",
            ]:
                if chave in st.session_state:
                    del st.session_state[chave]
            st.rerun()
