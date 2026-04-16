
import io
from pathlib import Path

import pandas as pd
import streamlit as st
from bling_app_zero.ui.app_helpers import (
    ir_para_etapa,
    safe_df,
)


EXTENSOES_ORIGEM = {".csv", ".xlsx", ".xls", ".xml", ".pdf"}
EXTENSOES_MODELO = {".csv", ".xlsx", ".xls", ".xml", ".pdf"}


def _extensao(upload) -> str:
    nome = str(getattr(upload, "name", "") or "").strip().lower()
    return Path(nome).suffix.lower()


def _eh_excel_familia(ext: str) -> bool:
    return ext in {".csv", ".xlsx", ".xls"}


def _ler_tabular(upload):
    nome = str(upload.name).lower()

    if nome.endswith(".csv"):
        bruto = upload.getvalue()

        for sep in [";", ",", "\t", "|"]:
            try:
                df = pd.read_csv(io.BytesIO(bruto), sep=sep, dtype=str).fillna("")
                if isinstance(df, pd.DataFrame) and len(df.columns) > 0:
                    return df
            except Exception:
                continue

        raise ValueError("Não foi possível ler o CSV.")

    if nome.endswith(".xlsx") or nome.endswith(".xls"):
        try:
            return pd.read_excel(upload, dtype=str).fillna("")
        except Exception as e:
            raise ValueError(f"Não foi possível ler o Excel: {e}")

    raise ValueError("Arquivo tabular inválido.")


def _normalizar_df(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()

    if df.empty:
        return pd.DataFrame()

    base = df.copy().fillna("")
    base.columns = [str(c).strip() for c in base.columns]
    return base


def _guardar_upload_bruto(chave_prefixo: str, upload, tipo: str) -> None:
    st.session_state[f"{chave_prefixo}_nome"] = str(upload.name)
    st.session_state[f"{chave_prefixo}_bytes"] = upload.getvalue()
    st.session_state[f"{chave_prefixo}_tipo"] = tipo
    st.session_state[f"{chave_prefixo}_ext"] = _extensao(upload)


def _processar_upload_origem(upload):
    if upload is None:
        return

    ext = _extensao(upload)

    if ext not in EXTENSOES_ORIGEM:
        st.error("Arquivo de origem inválido. Envie CSV, XLSX, XLS, XML ou PDF.")
        return

    if _eh_excel_familia(ext):
        try:
            df = _normalizar_df(_ler_tabular(upload))
        except Exception as e:
            st.error(str(e))
            return

        if not safe_df(df):
            st.error("A planilha de origem foi lida, mas está vazia.")
            return

        st.session_state["df_origem"] = df
        _guardar_upload_bruto("origem_upload", upload, "tabular")

        st.success(f"Arquivo de origem carregado: {upload.name}")
        st.dataframe(df.head(10), use_container_width=True)
        return

    _guardar_upload_bruto("origem_upload", upload, "documento")
    st.session_state["df_origem"] = None

    if ext == ".xml":
        st.success(f"XML de origem anexado: {upload.name}")
        st.info("XML aceito no fluxo.")
    elif ext == ".pdf":
        st.success(f"PDF de origem anexado: {upload.name}")
        st.info("PDF aceito no fluxo.")


def _processar_upload_modelo(upload):
    if upload is None:
        return

    ext = _extensao(upload)

    if ext not in EXTENSOES_MODELO:
        st.error("Arquivo modelo inválido. Envie CSV, XLSX, XLS, XML ou PDF.")
        return

    if _eh_excel_familia(ext):
        try:
            df = _normalizar_df(_ler_tabular(upload))
        except Exception as e:
            st.error(str(e))
            return

        st.session_state["df_modelo"] = df
        _guardar_upload_bruto("modelo_upload", upload, "tabular")

        st.success(f"Modelo carregado: {upload.name}")
        st.dataframe(df.head(10), use_container_width=True)
        return

    _guardar_upload_bruto("modelo_upload", upload, "documento")
    st.session_state["df_modelo"] = None

    if ext == ".xml":
        st.success(f"Modelo XML anexado: {upload.name}")
        st.info("Modelo XML aceito no fluxo.")
    elif ext == ".pdf":
        st.success(f"Modelo PDF anexado: {upload.name}")
        st.info("Modelo PDF aceito no fluxo.")


def _origem_pronta() -> bool:
    if safe_df(st.session_state.get("df_origem")):
        return True

    ext = st.session_state.get("origem_upload_ext")
    return ext in {".xml", ".pdf"}


def _modelo_pronto() -> bool:
    if safe_df(st.session_state.get("df_modelo")):
        return True

    ext = st.session_state.get("modelo_upload_ext")
    return ext in {".xml", ".pdf"}


def render_origem_dados():
    st.subheader("1. Origem dos dados")

    st.markdown("### O que você quer fazer?")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Cadastro de Produtos", use_container_width=True):
            st.session_state["tipo_operacao"] = "cadastro"
            st.session_state["tipo_operacao_bling"] = "cadastro"

    with col2:
        if st.button("Atualização de Estoque", use_container_width=True):
            st.session_state["tipo_operacao"] = "estoque"
            st.session_state["tipo_operacao_bling"] = "estoque"

    if not st.session_state.get("tipo_operacao"):
        st.info("Escolha uma operação para continuar.")
        return

    st.success(f"Operação: {st.session_state['tipo_operacao']}")

    if st.session_state["tipo_operacao"] == "estoque":
        deposito = st.text_input(
            "Nome do depósito",
            value=st.session_state.get("deposito_nome", ""),
            placeholder="Digite o nome do depósito"
        )
        st.session_state["deposito_nome"] = deposito

    st.markdown("### Arquivo do fornecedor")
    st.caption("No celular, o seletor foi deixado sem filtro rígido para ficar clicável. Aceita XML, PDF e família Excel.")

    upload_origem = st.file_uploader(
        "Toque para selecionar o arquivo do fornecedor",
        key="upload_origem",
        help="Aceita CSV, XLSX, XLS, XML e PDF"
    )

    if upload_origem is not None:
        _processar_upload_origem(upload_origem)

    st.markdown("### Arquivo modelo")
    st.caption("Envie o modelo que deve voltar idêntico no download final.")

    upload_modelo = st.file_uploader(
        "Toque para selecionar o arquivo modelo",
        key="upload_modelo",
        help="Aceita CSV, XLSX, XLS, XML e PDF"
    )

    if upload_modelo is not None:
        _processar_upload_modelo(upload_modelo)

    st.markdown("### Resumo")

    origem_ext = st.session_state.get("origem_upload_ext", "")
    modelo_ext = st.session_state.get("modelo_upload_ext", "")

    st.write(f"**Origem anexada:** {st.session_state.get('origem_upload_nome', 'não enviada')}")
    st.write(f"**Tipo origem:** {origem_ext or '-'}")
    st.write(f"**Modelo anexado:** {st.session_state.get('modelo_upload_nome', 'não enviado')}")
    st.write(f"**Tipo modelo:** {modelo_ext or '-'}")

    if safe_df(st.session_state.get("df_origem")):
        st.write(f"**Linhas origem:** {len(st.session_state['df_origem'])}")
        st.write(f"**Colunas origem:** {len(st.session_state['df_origem'].columns)}")

    if safe_df(st.session_state.get("df_modelo")):
        st.write(f"**Linhas modelo:** {len(st.session_state['df_modelo'])}")
        st.write(f"**Colunas modelo:** {len(st.session_state['df_modelo'].columns)}")

    pode_continuar = _origem_pronta() and _modelo_pronto()

    if pode_continuar:
        if st.button("Continuar ➜", use_container_width=True):
            ir_para_etapa("precificacao")
    else:
        st.info("Envie o arquivo do fornecedor e o arquivo modelo para continuar.")

