from __future__ import annotations

import pandas as pd
import streamlit as st

from . import CLEAN_CORE_VERSION
from .export import sanitize_for_export, to_bling_csv_bytes
from .io import empty_like_model, read_table
from .operations import Operation, detect_operation_from_columns, normalize_operation, operation_label


def _select_operation(model_df: pd.DataFrame) -> Operation:
    detected = detect_operation_from_columns(model_df.columns)
    options = {
        "Detectar pela planilha": detected,
        "Cadastro de produtos": Operation.CADASTRO,
        "Atualização de estoque": Operation.ESTOQUE,
    }
    choice = st.radio(
        "Operação",
        list(options.keys()),
        index=0,
        horizontal=True,
        help="Nesta fase limpa, a operação só separa o fluxo. Nenhum motor automático é misturado.",
    )
    return normalize_operation(options[choice].value)


def run_clean_app() -> None:
    st.title("IA Planilhas Bling")
    st.caption(f"Clean Core {CLEAN_CORE_VERSION}")
    st.info(
        "Fase segura: anexe o modelo do Bling, valide as colunas e baixe um CSV com a mesma estrutura. "
        "Motores de site/cadastro/estoque serão adicionados depois, um por vez."
    )

    st.subheader("1. Modelo Bling validado")
    uploaded_model = st.file_uploader(
        "Anexe a planilha modelo",
        type=("csv", "xlsx", "xls", "xlsm", "xlsb"),
    )

    if uploaded_model is None:
        st.warning("Anexe o modelo para iniciar o fluxo seguro.")
        return

    try:
        model_df = read_table(uploaded_model)
    except Exception as exc:
        st.error(f"Não consegui ler o modelo: {exc}")
        return

    if model_df.empty and len(model_df.columns) == 0:
        st.error("O modelo não possui colunas válidas.")
        return

    operation = _select_operation(model_df)
    st.success(f"Operação ativa: {operation_label(operation)}")

    with st.expander("Colunas do modelo", expanded=True):
        st.write(list(model_df.columns))
        st.dataframe(model_df.head(20), use_container_width=True)

    st.subheader("2. Estrutura final controlada")
    rows = st.number_input("Quantidade de linhas vazias para gerar", min_value=1, max_value=500, value=1, step=1)
    output_df = empty_like_model(model_df, rows=int(rows))

    if operation == Operation.ESTOQUE:
        deposit_cols = [col for col in output_df.columns if "depósito" in col.lower() or "deposito" in col.lower()]
        if deposit_cols:
            deposit_name = st.text_input("Nome do depósito", value="")
            if deposit_name:
                for col in deposit_cols:
                    output_df[col] = deposit_name

    clean_df = sanitize_for_export(output_df)
    st.dataframe(clean_df, use_container_width=True)

    st.subheader("3. Download CSV")
    st.download_button(
        "Baixar CSV seguro",
        data=to_bling_csv_bytes(clean_df),
        file_name="bling_modelo_validado.csv",
        mime="text/csv",
        type="primary",
        use_container_width=True,
    )
