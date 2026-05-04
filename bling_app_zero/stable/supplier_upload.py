from __future__ import annotations

from io import StringIO
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.file_reader import read_uploaded_table


COMPAT_EXTENSIONS = [
    "csv",
    "txt",
    "tsv",
    "tab",
    "xlsx",
    "xlsm",
    "xls",
    "xlsb",
    "ods",
    "html",
    "htm",
    "json",
    "xml",
]


def _clean_df(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    out = df.copy().fillna("")
    out.columns = [str(c).replace("\ufeff", "").replace("\x00", "").strip().strip('"').strip("'") for c in out.columns]
    out = out.loc[:, [str(c).strip() != "" for c in out.columns]]
    out = out.dropna(how="all")
    return out.fillna("")


def _read_upload(uploaded: Any) -> pd.DataFrame:
    result = read_uploaded_table(uploaded)
    df = _clean_df(result.dataframe)
    if df.empty or len(df.columns) == 0:
        raise ValueError("O arquivo foi lido, mas não gerou uma tabela válida.")
    return df


def _read_pasted_table(raw: str) -> pd.DataFrame:
    text = str(raw or "").strip()
    if not text:
        raise ValueError("Cole o conteúdo do CSV/TXT antes de continuar.")

    candidates: list[tuple[str, pd.DataFrame]] = []
    errors: list[str] = []
    for sep in [";", ",", "\t", "|"]:
        try:
            df = pd.read_csv(
                StringIO(text),
                sep=sep,
                dtype=str,
                keep_default_na=False,
                engine="python",
                on_bad_lines="skip",
            )
            df = _clean_df(df)
            if not df.empty and len(df.columns) > 1:
                candidates.append((sep, df))
        except Exception as exc:
            errors.append(f"{sep}: {exc}")

    if candidates:
        candidates.sort(key=lambda item: (len(item[1].columns), len(item[1].index)), reverse=True)
        return candidates[0][1]

    detalhe = " | ".join(errors[:4])
    raise ValueError(f"Não consegui transformar o conteúdo colado em tabela. Copie o CSV inteiro com cabeçalho. {detalhe}")


def _store_df(df: pd.DataFrame, state_key: str) -> pd.DataFrame:
    df = _clean_df(df)
    st.session_state[state_key] = df
    st.success(f"Tabela carregada: {len(df)} linhas × {len(df.columns)} colunas")
    return df


def render_supplier_upload(*, state_key: str = "stable_df_origem", key_prefix: str = "supplier") -> pd.DataFrame | None:
    """Módulo BLINGFIX para anexar planilha do fornecedor.

    Estratégia:
    1. Upload livre sem filtro, melhor para Android.
    2. Upload compatibilidade com extensões explícitas.
    3. Colagem direta do CSV/TXT quando o seletor deixa arquivo cinza.
    """

    st.subheader("📎 Planilha do fornecedor")
    st.caption("Use o modo livre primeiro. Se o Android deixar o arquivo cinza, use compatibilidade ou cole o CSV.")

    current = st.session_state.get(state_key)

    uploaded_free = st.file_uploader(
        "1) Anexar arquivo — modo livre Android",
        type=None,
        key=f"{key_prefix}_upload_free",
        help="Sem filtro de extensão. É o modo mais compatível com Android/Downloads.",
    )
    if uploaded_free is not None:
        try:
            return _store_df(_read_upload(uploaded_free), state_key)
        except Exception as exc:
            st.error("Não consegui ler esse arquivo no modo livre.")
            st.code(str(exc))

    with st.expander("2) Modo compatibilidade por extensão", expanded=False):
        uploaded_compat = st.file_uploader(
            "Anexar com filtro de compatibilidade",
            type=COMPAT_EXTENSIONS,
            key=f"{key_prefix}_upload_compat",
            help="Use se o primeiro botão não abrir corretamente.",
        )
        if uploaded_compat is not None:
            try:
                return _store_df(_read_upload(uploaded_compat), state_key)
            except Exception as exc:
                st.error("Não consegui ler esse arquivo no modo compatibilidade.")
                st.code(str(exc))

    with st.expander("3) Arquivo cinza/não clicável? Cole o CSV aqui", expanded=False):
        st.caption("Abra o arquivo no celular, selecione tudo, copie e cole aqui. Isso não depende do seletor Android.")
        pasted = st.text_area(
            "Colar CSV/TXT com cabeçalho",
            key=f"{key_prefix}_paste_text",
            height=180,
            placeholder="codigo;descricao;preco\n001;Produto Teste;10,90",
        )
        if st.button(
            "Usar conteúdo colado",
            key=f"{key_prefix}_paste_button",
            use_container_width=True,
            disabled=not bool(str(pasted or "").strip()),
        ):
            try:
                return _store_df(_read_pasted_table(pasted), state_key)
            except Exception as exc:
                st.error("Não consegui ler o conteúdo colado.")
                st.code(str(exc))

    if isinstance(current, pd.DataFrame) and not current.empty:
        st.info(f"Tabela já carregada: {len(current)} linhas × {len(current.columns)} colunas")
        return current

    return None
