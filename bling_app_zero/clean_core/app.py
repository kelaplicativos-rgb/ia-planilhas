from __future__ import annotations

import pandas as pd
import streamlit as st

from . import CLEAN_CORE_VERSION
from .engines import get_engine
from .export import sanitize_for_export, to_bling_csv_bytes
from .io import empty_like_model, read_table
from .operations import Operation, detect_operation_from_columns, normalize_operation, operation_label
from .schema import RequestedField, build_requested_schema


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
        help="A operação define qual motor independente será usado. Cadastro e estoque não compartilham o mesmo motor.",
    )
    return normalize_operation(options[choice].value)


def _show_requested_schema(schema: list[RequestedField]) -> None:
    schema_df = pd.DataFrame(
        [
            {
                "Coluna do modelo": field.column,
                "Intenção detectada": field.intent.value,
                "Obrigatória": "sim" if field.required else "não",
            }
            for field in schema
        ]
    )
    st.dataframe(schema_df, use_container_width=True, hide_index=True)


def _parse_urls(raw_urls: str) -> list[str]:
    urls: list[str] = []
    for line in str(raw_urls or "").splitlines():
        line = line.strip()
        if line:
            urls.append(line)
    return urls


def run_clean_app() -> None:
    st.title("IA Planilhas Bling")
    st.caption(f"Clean Core {CLEAN_CORE_VERSION}")
    st.info(
        "Fluxo reiniciado: a planilha modelo manda no sistema. "
        "Cada operação chama seu próprio motor e cada motor busca somente as colunas solicitadas pelo modelo."
    )

    st.subheader("1. Modelo Bling")
    uploaded_model = st.file_uploader(
        "Anexe a planilha modelo do Bling",
        type=("csv", "xlsx", "xls", "xlsm", "xlsb"),
        help="O modelo define a operação, as colunas finais e o que os motores podem tentar capturar.",
    )

    if uploaded_model is None:
        st.warning("Anexe o modelo para iniciar.")
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
    requested_schema = build_requested_schema(model_df.columns)
    engine = get_engine(operation)

    st.success(f"Operação ativa: {operation_label(operation)}")
    st.caption(f"Motor conectado: {engine.name}")

    with st.expander("Colunas solicitadas pelo modelo", expanded=True):
        _show_requested_schema(requested_schema)

    st.subheader("2. Origem dos dados")
    source = st.radio(
        "Escolha a origem",
        ["Busca por site", "Gerar estrutura vazia"],
        horizontal=True,
        help="Nesta versão limpa, busca por site já respeita cadastro e estoque como motores separados.",
    )

    deposit_name = ""
    if operation == Operation.ESTOQUE:
        deposit_name = st.text_input("Nome do depósito", value="", help="Preenche apenas colunas de depósito quando existirem no modelo.")

    output_df: pd.DataFrame

    if source == "Busca por site":
        raw_urls = st.text_area(
            "Links dos produtos",
            height=160,
            placeholder="Cole um link por linha",
        )
        urls = _parse_urls(raw_urls)
        st.caption(f"Links informados: {len(urls)}")

        if st.button("Capturar usando o motor correto", type="primary", use_container_width=True):
            with st.spinner("Capturando somente o que o modelo solicitou..."):
                result = engine.run(
                    model_df=model_df,
                    requested_schema=requested_schema,
                    urls=urls,
                    deposit_name=deposit_name,
                )
            st.session_state["clean_core_output_df"] = result.dataframe
            st.session_state["clean_core_logs"] = result.logs
            st.session_state["clean_core_warnings"] = result.warnings

        output_df = st.session_state.get("clean_core_output_df", empty_like_model(model_df, rows=max(len(urls), 1)))
    else:
        rows = st.number_input("Quantidade de linhas vazias para gerar", min_value=1, max_value=500, value=1, step=1)
        output_df = empty_like_model(model_df, rows=int(rows))

    if operation == Operation.ESTOQUE and deposit_name:
        for col in output_df.columns:
            if "depósito" in col.lower() or "deposito" in col.lower():
                output_df[col] = deposit_name

    st.subheader("3. Preview final")
    warnings = st.session_state.get("clean_core_warnings", [])
    logs = st.session_state.get("clean_core_logs", [])
    for warning in warnings:
        st.warning(warning)
    if logs:
        with st.expander("Log do motor", expanded=False):
            for log in logs:
                st.write(f"- {log}")

    clean_df = sanitize_for_export(output_df)
    st.dataframe(clean_df, use_container_width=True)

    st.subheader("4. Download CSV Bling")
    st.download_button(
        "Baixar CSV final",
        data=to_bling_csv_bytes(clean_df),
        file_name=f"bling_{operation.value}_clean_core.csv",
        mime="text/csv",
        type="primary",
        use_container_width=True,
    )
