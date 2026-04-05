from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from bling_app_zero.core.bling_auth import BlingAuthManager
from bling_app_zero.core.bling_sync import sync_products, sync_stocks
from bling_app_zero.core.bling_user_session import (
    ensure_current_user_defaults,
    get_current_user_key,
    get_current_user_label,
)
from bling_app_zero.utils.numeros import normalize_value, safe_float


def get_column_by_mapped_name(
    df: pd.DataFrame,
    mapeamento: Dict[str, str],
    nomes_mapeados: List[str],
) -> Optional[str]:
    for nome_mapeado in nomes_mapeados:
        for col_origem, destino in mapeamento.items():
            if destino == nome_mapeado and col_origem in df.columns:
                return col_origem
    return None


def _base_df() -> Optional[pd.DataFrame]:
    for key in ("df_saida", "df_origem"):
        df = st.session_state.get(key)
        if isinstance(df, pd.DataFrame) and not df.empty:
            return df
    return None


def build_product_rows(df: pd.DataFrame, mapeamento: Dict[str, str]) -> List[Dict]:
    sku_col = get_column_by_mapped_name(df, mapeamento, ["sku", "codigo"])
    nome_col = get_column_by_mapped_name(df, mapeamento, ["nome"])
    desc_col = get_column_by_mapped_name(df, mapeamento, ["descricao_curta", "descricao_html", "descricao"])
    preco_col = get_column_by_mapped_name(df, mapeamento, ["preco"])
    custo_col = get_column_by_mapped_name(df, mapeamento, ["custo", "preco_custo"])
    estoque_col = get_column_by_mapped_name(df, mapeamento, ["estoque"])
    gtin_col = get_column_by_mapped_name(df, mapeamento, ["gtin"])
    marca_col = get_column_by_mapped_name(df, mapeamento, ["marca"])
    categoria_col = get_column_by_mapped_name(df, mapeamento, ["categoria"])

    if not sku_col and "codigo" in df.columns:
        sku_col = "codigo"
    if not nome_col and "nome" in df.columns:
        nome_col = "nome"
    if not preco_col and "preco" in df.columns:
        preco_col = "preco"
    if not estoque_col and "estoque" in df.columns:
        estoque_col = "estoque"
    if not gtin_col and "gtin" in df.columns:
        gtin_col = "gtin"

    rows: List[Dict] = []
    for _, row in df.iterrows():
        payload = {
            "codigo": normalize_value(row[sku_col]) if sku_col else None,
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
    sku_col = get_column_by_mapped_name(df, mapeamento, ["sku", "codigo"])
    estoque_col = get_column_by_mapped_name(df, mapeamento, ["estoque"])
    preco_col = get_column_by_mapped_name(df, mapeamento, ["preco"])
    deposito_col = get_column_by_mapped_name(df, mapeamento, ["deposito_id", "deposito"])

    if not sku_col and "codigo" in df.columns:
        sku_col = "codigo"
    if not estoque_col and "estoque" in df.columns:
        estoque_col = "estoque"
    if not preco_col and "preco" in df.columns:
        preco_col = "preco"

    deposito_manual = str(st.session_state.get("deposito_nome_manual", "")).strip()

    rows: List[Dict] = []
    for _, row in df.iterrows():
        payload = {
            "codigo": normalize_value(row[sku_col]) if sku_col else None,
            "estoque": safe_float(row[estoque_col]) if estoque_col else None,
            "preco": safe_float(row[preco_col]) if preco_col else None,
            "deposito_id": normalize_value(row[deposito_col]) if deposito_col else deposito_manual or None,
        }
        rows.append(payload)
    return rows


def validar_produtos(rows: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    validos: List[Dict] = []
    invalidos: List[Dict] = []

    for indice, row in enumerate(rows, start=1):
        faltando: List[str] = []
        if not row.get("codigo"):
            faltando.append("codigo")
        if not row.get("nome"):
            faltando.append("nome")
        if row.get("preco") is None or float(row.get("preco") or 0) <= 0:
            faltando.append("preco")

        if faltando:
            invalidos.append(
                {
                    "linha": indice,
                    "codigo": row.get("codigo"),
                    "nome": row.get("nome"),
                    "faltando": ", ".join(faltando),
                    "payload": row,
                }
            )
        else:
            validos.append(row)

    return validos, invalidos


def validar_estoque(rows: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    validos: List[Dict] = []
    invalidos: List[Dict] = []

    for indice, row in enumerate(rows, start=1):
        faltando: List[str] = []
        if not row.get("codigo"):
            faltando.append("codigo")
        if row.get("estoque") is None:
            faltando.append("estoque")

        if faltando:
            invalidos.append(
                {
                    "linha": indice,
                    "codigo": row.get("codigo"),
                    "faltando": ", ".join(faltando),
                    "payload": row,
                }
            )
        else:
            validos.append(row)

    return validos, invalidos


def _mostrar_resumo_validacao(
    titulo_ok: str,
    titulo_erro: str,
    validos: List[Dict],
    invalidos: List[Dict],
) -> None:
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Linhas válidas", len(validos))
    with c2:
        st.metric("Linhas com pendência", len(invalidos))

    if invalidos:
        st.warning(
            f"{len(invalidos)} linha(s) estão com campos obrigatórios faltando e "
            f"precisam de conferência antes do envio."
        )
        df_invalidos = pd.DataFrame(invalidos)
        with st.expander(titulo_erro, expanded=False):
            st.dataframe(df_invalidos, use_container_width=True, height=220)

    if validos:
        st.success(f"{len(validos)} linha(s) prontas para uso.")
        with st.expander(titulo_ok, expanded=False):
            st.json(validos[:50])


def render_send_panel() -> None:
    st.subheader("Enviar dados")

    df = _base_df()
    mapeamento = st.session_state.get("mapeamento_manual") or {}

    if not isinstance(df, pd.DataFrame) or df.empty:
        st.info("Carregue primeiro uma origem de dados.")
        return

    ensure_current_user_defaults()
    user_key = get_current_user_key()
    user_label = get_current_user_label()

    auth = BlingAuthManager(user_key=user_key)
    conectado = bool(auth.get_connection_status().get("connected"))

    st.caption(f"Usuário atual do envio Bling: {user_label} ({user_key})")

    tab1, tab2 = st.tabs(["Preparar cadastro", "Preparar estoque"])

    with tab1:
        rows = build_product_rows(df, mapeamento)
        validos, invalidos = validar_produtos(rows)

        st.write(f"Linhas analisadas para cadastro: **{len(rows)}**")

        if st.button("Gerar preview de cadastro", use_container_width=True):
            st.session_state["ultimo_log_envio"] = {
                "tipo": "cadastro",
                "validos": validos[:50],
                "invalidos": invalidos[:50],
                "user_key": user_key,
            }

        _mostrar_resumo_validacao(
            "Preview de cadastro válido",
            "Linhas de cadastro com pendência",
            validos,
            invalidos,
        )

        if conectado:
            if st.button(
                "Enviar cadastro real para o Bling",
                use_container_width=True,
                disabled=not bool(validos),
            ):
                sucessos, erros = sync_products(validos, user_key=user_key)
                st.session_state["ultimo_log_envio"] = {
                    "tipo": "cadastro_real",
                    "sucessos": sucessos[:100],
                    "erros": erros[:100],
                    "user_key": user_key,
                }

                if sucessos:
                    st.success(f"{len(sucessos)} produto(s) enviado(s)/atualizado(s) no Bling.")
                if erros:
                    st.error(f"{len(erros)} produto(s) falharam no envio.")
                    st.dataframe(pd.DataFrame(erros), use_container_width=True, height=220)
        else:
            st.info("Conecte o Bling para liberar o envio real de cadastro.")

    with tab2:
        rows = build_stock_rows(df, mapeamento)
        validos, invalidos = validar_estoque(rows)

        st.write(f"Linhas analisadas para estoque: **{len(rows)}**")
        st.text_input(
            "Depósito / ID do depósito",
            key="deposito_nome_manual",
            help="Use este campo quando a planilha não possuir uma coluna de depósito.",
        )

        if st.button("Gerar preview de estoque", use_container_width=True):
            st.session_state["ultimo_log_envio"] = {
                "tipo": "estoque",
                "validos": validos[:50],
                "invalidos": invalidos[:50],
                "user_key": user_key,
            }

        _mostrar_resumo_validacao(
            "Preview de estoque válido",
            "Linhas de estoque com pendência",
            validos,
            invalidos,
        )

        if conectado:
            if st.button(
                "Enviar estoque real para o Bling",
                use_container_width=True,
                disabled=not bool(validos),
            ):
                sucessos, erros = sync_stocks(validos, user_key=user_key)
                st.session_state["ultimo_log_envio"] = {
                    "tipo": "estoque_real",
                    "sucessos": sucessos[:100],
                    "erros": erros[:100],
                    "user_key": user_key,
                }

                if sucessos:
                    st.success(f"{len(sucessos)} linha(s) de estoque enviada(s) ao Bling.")
                if erros:
                    st.error(f"{len(erros)} linha(s) falharam no envio do estoque.")
                    st.dataframe(pd.DataFrame(erros), use_container_width=True, height=220)
        else:
            st.info("Conecte o Bling para liberar o envio real de estoque.")
