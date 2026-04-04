from typing import Dict, List, Optional

import pandas as pd
import streamlit as st

from bling_app_zero.utils.numeros import normalize_value, safe_float
from bling_app_zero.core.bling_auth import BlingAuthManager
from bling_app_zero.core.bling_sync import BlingSyncService


def get_column_by_mapped_name(
    df: pd.DataFrame,
    mapeamento: Dict[str, str],
    nome_mapeado: str,
) -> Optional[str]:
    for col_origem, destino in mapeamento.items():
        if destino == nome_mapeado and col_origem in df.columns:
            return col_origem
    return None


def build_product_rows(df: pd.DataFrame, mapeamento: Dict[str, str]) -> List[Dict]:
    codigo_col = get_column_by_mapped_name(df, mapeamento, "codigo")
    nome_col = get_column_by_mapped_name(df, mapeamento, "nome")
    desc_col = get_column_by_mapped_name(df, mapeamento, "descricao_curta")
    preco_col = get_column_by_mapped_name(df, mapeamento, "preco")
    custo_col = get_column_by_mapped_name(df, mapeamento, "preco_custo")
    estoque_col = get_column_by_mapped_name(df, mapeamento, "estoque")
    gtin_col = get_column_by_mapped_name(df, mapeamento, "gtin")
    marca_col = get_column_by_mapped_name(df, mapeamento, "marca")
    categoria_col = get_column_by_mapped_name(df, mapeamento, "categoria")

    rows = []

    for _, row in df.iterrows():
        payload = {
            "codigo": normalize_value(row[codigo_col]) if codigo_col else None,
            "nome": normalize_value(row[nome_col]) if nome_col else None,
            "descricao_curta": normalize_value(row[desc_col]) if desc_col else None,
            "preco": safe_float(row[preco_col]) if preco_col else None,
            "preco_custo": safe_float(row[custo_col]) if custo_col else None,
            "estoque": safe_float(row[estoque_col]) if estoque_col else None,
            "gtin": normalize_value(row[gtin_col]) if gtin_col else None,
            "marca": normalize_value(row[marca_col]) if marca_col else None,
            "categoria": normalize_value(row[categoria_col]) if categoria_col else None,
        }
        rows.append(payload)

    return rows


def build_stock_rows(df: pd.DataFrame, mapeamento: Dict[str, str]) -> List[Dict]:
    codigo_col = get_column_by_mapped_name(df, mapeamento, "codigo")
    estoque_col = get_column_by_mapped_name(df, mapeamento, "estoque")
    preco_col = get_column_by_mapped_name(df, mapeamento, "preco")
    deposito_col = get_column_by_mapped_name(df, mapeamento, "deposito_id")

    rows = []

    for _, row in df.iterrows():
        payload = {
            "codigo": normalize_value(row[codigo_col]) if codigo_col else None,
            "estoque": safe_float(row[estoque_col]) if estoque_col else None,
            "preco": safe_float(row[preco_col]) if preco_col else None,
            "deposito_id": normalize_value(row[deposito_col]) if deposito_col else None,
        }
        rows.append(payload)

    return rows


def render_send_panel() -> None:
    st.subheader("Enviar dados para o Bling")

    auth = BlingAuthManager()

    if not auth.is_configured():
        st.info("Configure o Bling para liberar o envio.")
        return

    if not auth.get_connection_status()["connected"]:
        st.info("Conecte sua conta do Bling para enviar dados.")
        return

    df = st.session_state.get("df_origem")
    mapeamento = st.session_state.get("mapeamento_manual") or {}

    if not isinstance(df, pd.DataFrame) or df.empty:
        st.info("Carregue primeiro uma origem de dados.")
        return

    service = BlingSyncService()
    tab1, tab2 = st.tabs(["Enviar cadastro", "Enviar estoque"])

    with tab1:
        rows = build_product_rows(df, mapeamento)
        st.write(f"Linhas preparadas para cadastro: **{len(rows)}**")

        somente_validar = st.checkbox("Somente validar cadastro", value=True)

        if st.button("Enviar cadastro ao Bling", use_container_width=True):
            ok, resultado = service.enviar_cadastros(rows, dry_run=somente_validar)
            st.session_state.ultimo_log_envio = resultado if isinstance(resultado, list) else []

            if ok:
                st.success("Processo de cadastro concluído.")
            else:
                st.error("O envio teve falhas.")

            if resultado:
                st.json(resultado)

    with tab2:
        rows = build_stock_rows(df, mapeamento)
        st.write(f"Linhas preparadas para estoque: **{len(rows)}**")

        somente_validar = st.checkbox("Somente validar estoque", value=True)

        if st.button("Enviar estoque ao Bling", use_container_width=True):
            ok, resultado = service.enviar_estoques(rows, dry_run=somente_validar)
            st.session_state.ultimo_log_envio = resultado if isinstance(resultado, list) else []

            if ok:
                st.success("Processo de estoque concluído.")
            else:
                st.error("O envio teve falhas.")

            if resultado:
                st.json(resultado)
