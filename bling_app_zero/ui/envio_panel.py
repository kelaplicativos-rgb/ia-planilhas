from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from bling_app_zero.core.bling_auth import BlingAuthManager
from bling_app_zero.core.bling_sync import sync_products, sync_stocks
from bling_app_zero.utils.numeros import normalize_value, safe_float


def _get_current_bling_user_key() -> str:
    session_key = str(st.session_state.get("bling_user_key", "")).strip()
    query_key_raw = st.query_params.get("bi", "")

    if isinstance(query_key_raw, list):
        query_key = str(query_key_raw[0]).strip() if query_key_raw else ""
    else:
        query_key = str(query_key_raw).strip()

    final_key = session_key or query_key or "default"
    st.session_state["bling_user_key"] = final_key

    try:
        st.query_params["bi"] = final_key
    except Exception:
        pass

    return final_key


def _normalizar_nome_coluna(nome: str) -> str:
    return (
        str(nome or "")
        .strip()
        .lower()
        .replace("ç", "c")
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
    )


def _find_column(df: pd.DataFrame, aliases: List[str]) -> Optional[str]:
    normalized = {_normalizar_nome_coluna(col): col for col in df.columns}

    for alias in aliases:
        alias_norm = _normalizar_nome_coluna(alias)
        if alias_norm in normalized:
            return normalized[alias_norm]

    for col in df.columns:
        col_norm = _normalizar_nome_coluna(col)
        for alias in aliases:
            if _normalizar_nome_coluna(alias) in col_norm:
                return col

    return None


def _base_df() -> Optional[pd.DataFrame]:
    df = st.session_state.get("df_saida_api")
    if not isinstance(df, pd.DataFrame) or df.empty:
        df = st.session_state.get("df_saida")
    if isinstance(df, pd.DataFrame) and not df.empty:
        return df.copy()
    return None


# =========================
# PRODUTOS
# =========================
def build_product_rows(df: pd.DataFrame) -> List[Dict]:
    sku_col = _find_column(df, ["codigo", "sku", "referencia", "ref"])
    nome_col = _find_column(df, ["nome", "descricao", "produto"])
    preco_col = _find_column(df, ["preco", "valor"])

    rows: List[Dict] = []

    for _, row in df.iterrows():
        payload = {
            "codigo": normalize_value(row[sku_col]) if sku_col else None,
            "nome": normalize_value(row[nome_col]) if nome_col else None,
            "preco": safe_float(row[preco_col]) if preco_col else None,
        }
        rows.append(payload)

    return rows


# =========================
# ESTOQUE (CORRIGIDO)
# =========================
def build_stock_rows(df: pd.DataFrame) -> List[Dict]:
    sku_col = _find_column(df, ["codigo", "sku", "referencia"])
    estoque_col = _find_column(df, ["estoque", "saldo", "quantidade"])
    deposito_col = _find_column(df, ["deposito"])

    deposito_manual = str(st.session_state.get("deposito_nome_manual_api", "")).strip()

    rows: List[Dict] = []

    for _, row in df.iterrows():
        estoque = safe_float(row[estoque_col]) if estoque_col else 0

        if estoque is None or estoque < 0:
            estoque = 0

        deposito = (
            normalize_value(row[deposito_col])
            if deposito_col
            else deposito_manual or "Geral"
        )

        payload = {
            "codigo": normalize_value(row[sku_col]) if sku_col else None,
            "estoque": int(estoque),
            "deposito_id": deposito,
        }

        rows.append(payload)

    return rows


# =========================
# UI
# =========================
def render_send_panel() -> None:
    st.subheader("Envio por API")

    df = _base_df()
    modo = str(st.session_state.get("tipo_operacao_bling", "cadastro")).lower()

    if df is None or df.empty:
        st.info("Gere primeiro o preview.")
        return

    user_key = _get_current_bling_user_key()
    auth = BlingAuthManager(user_key=user_key)
    conectado = bool(auth.get_connection_status().get("connected"))

    if modo == "cadastro":

        rows = build_product_rows(df)

        if conectado:
            if st.button("Enviar cadastro", width="stretch"):

                progress = st.progress(0, text="Preparando envio...")

                try:
                    total = len(rows)
                    enviados = 0

                    sucessos = []
                    erros = []

                    for r in rows:
                        enviados += 1

                        p = int((enviados / total) * 100)
                        progress.progress(p, text=f"Enviando {enviados}/{total}")

                        ok, msg = sync_products([r], user_key=user_key)

                        if ok:
                            sucessos.append(r)
                        else:
                            erros.append({"row": r, "erro": msg})

                    progress.progress(100, text="Concluído")

                    st.success(f"{len(sucessos)} enviados")
                    if erros:
                        st.error(f"{len(erros)} erros")
                        st.dataframe(pd.DataFrame(erros))

                except Exception as e:
                    st.error(e)

    else:

        rows = build_stock_rows(df)

        st.text_input("Depósito", key="deposito_nome_manual_api")

        if conectado:
            if st.button("Enviar estoque", width="stretch"):

                progress = st.progress(0, text="Preparando envio...")

                try:
                    total = len(rows)
                    enviados = 0

                    sucessos = []
                    erros = []

                    for r in rows:
                        enviados += 1

                        p = int((enviados / total) * 100)
                        progress.progress(p, text=f"Enviando {enviados}/{total}")

                        ok, msg = sync_stocks([r], user_key=user_key)

                        if ok:
                            sucessos.append(r)
                        else:
                            erros.append({"row": r, "erro": msg})

                    progress.progress(100, text="Concluído")

                    st.success(f"{len(sucessos)} enviados")
                    if erros:
                        st.error(f"{len(erros)} erros")
                        st.dataframe(pd.DataFrame(erros))

                except Exception as e:
                    st.error(e)
