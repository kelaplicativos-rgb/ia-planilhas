from __future__ import annotations

from io import StringIO
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.file_reader import read_uploaded_table


COMPAT_EXTENSIONS = ["csv", "txt", "tsv", "xlsx", "xlsm", "xls", "xlsb", "ods", "html", "json", "xml"]


def _clean_df(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    out = df.copy().fillna("")
    out.columns = [str(c).replace("\ufeff", "").strip().strip('"').strip("'") for c in out.columns]
    out = out.loc[:, [str(c).strip() != "" for c in out.columns]]
    return out.dropna(how="all").fillna("")


def _read_upload(uploaded: Any) -> pd.DataFrame:
    result = read_uploaded_table(uploaded)
    df = _clean_df(result.dataframe)
    if df.empty or len(df.columns) == 0:
        raise ValueError("O arquivo foi lido, mas não gerou uma tabela válida.")
    return df


def _read_text_table(text: str) -> pd.DataFrame:
    raw = str(text or "").strip()
    if not raw:
        raise ValueError("Cole o conteúdo antes de continuar.")

    best = pd.DataFrame()
    best_score = -1
    for sep in [";", ",", "\t", "|"]:
        try:
            df = pd.read_csv(StringIO(raw), sep=sep, dtype=str, keep_default_na=False, engine="python", on_bad_lines="skip")
            df = _clean_df(df)
            score = len(df.columns) * 100000 + len(df.index)
            if not df.empty and len(df.columns) > 1 and score > best_score:
                best = df
                best_score = score
        except Exception:
            pass

    if best.empty:
        raise ValueError("Não consegui reconhecer o texto colado como tabela. Verifique se a primeira linha possui os nomes das colunas.")
    return best


def _save(df: pd.DataFrame, state_key: str) -> pd.DataFrame:
    df = _clean_df(df)
    st.session_state[state_key] = df
    st.success(f"✅ Planilha carregada: {len(df)} linhas × {len(df.columns)} colunas")
    col1, col2 = st.columns(2)
    col1.metric("Linhas", len(df))
    col2.metric("Colunas", len(df.columns))
    with st.expander("Preview da planilha fornecedora", expanded=False):
        st.dataframe(df.head(25), use_container_width=True)
    return df


def render_supplier_upload_v2(*, state_key: str = "stable_df_origem", key_prefix: str = "supplier_v2") -> pd.DataFrame | None:
    st.subheader("📎 Planilha fornecedora")
    st.caption("Módulo BLINGFIX: anexo livre, anexo alternativo e colagem de CSV/TXT.")

    current = st.session_state.get(state_key)

    uploaded = st.file_uploader(
        "Anexar planilha",
        type=None,
        key=f"{key_prefix}_free",
        help="Modo livre sem filtro. É o mais indicado para Android e pasta Downloads.",
    )
    if uploaded is not None:
        try:
            return _save(_read_upload(uploaded), state_key)
        except Exception as exc:
            st.error("Não consegui ler o arquivo anexado.")
            st.code(str(exc))

    with st.expander("Anexo alternativo", expanded=False):
        uploaded_alt = st.file_uploader(
            "Anexar com filtro por extensão",
            type=COMPAT_EXTENSIONS,
            key=f"{key_prefix}_alt",
        )
        if uploaded_alt is not None:
            try:
                return _save(_read_upload(uploaded_alt), state_key)
            except Exception as exc:
                st.error("Não consegui ler o arquivo alternativo.")
                st.code(str(exc))

    st.markdown("#### Plano B: colar conteúdo")
    pasted = st.text_area(
        "Cole aqui o conteúdo CSV/TXT com cabeçalho",
        key=f"{key_prefix}_paste",
        height=160,
        placeholder="codigo;descricao;preco\n001;Produto teste;10,90",
    )
    if st.button("Usar conteúdo colado", key=f"{key_prefix}_paste_btn", use_container_width=True, disabled=not bool(str(pasted or "").strip())):
        try:
            return _save(_read_text_table(pasted), state_key)
        except Exception as exc:
            st.error("Não consegui ler o conteúdo colado.")
            st.code(str(exc))

    if isinstance(current, pd.DataFrame) and not current.empty:
        return _save(current, state_key)

    return None
