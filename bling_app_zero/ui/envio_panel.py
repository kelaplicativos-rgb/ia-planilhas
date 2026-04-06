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
            alias_norm = _normalizar_nome_coluna(alias)
            if alias_norm in col_norm:
                return col

    return None


def _base_df() -> Optional[pd.DataFrame]:
    df = st.session_state.get("df_saida")
    if isinstance(df, pd.DataFrame) and not df.empty:
        return df.copy()
    return None


def build_product_rows(df: pd.DataFrame) -> List[Dict]:
    sku_col = _find_column(df, ["codigo", "sku", "referencia", "ref"])
    nome_col = _find_column(df, ["nome", "descricao", "descrição", "produto", "titulo"])
    desc_col = _find_column(
        df,
        ["descricao_curta", "descricao_html", "descricao", "descrição", "complemento"],
    )
    preco_col = _find_column(
        df,
        ["preco", "preço", "preco venda", "preço venda", "valor de venda"],
    )
    custo_col = _find_column(
        df,
        ["preco de custo", "preço de custo", "custo", "preco_custo"],
    )
    estoque_col = _find_column(df, ["estoque", "saldo", "quantidade", "balanco", "balanço"])
    gtin_col = _find_column(df, ["gtin", "ean", "codigo de barras", "código de barras", "cean"])
    marca_col = _find_column(df, ["marca", "fabricante"])
    categoria_col = _find_column(df, ["categoria", "departamento", "grupo"])
    ncm_col = _find_column(df, ["ncm"])

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
            "ncm": normalize_value(row[ncm_col]) if ncm_col else None,
        }
        rows.append(payload)

    return rows


def build_stock_rows(df: pd.DataFrame) -> List[Dict]:
    sku_col = _find_column(df, ["codigo", "sku", "referencia", "ref"])
    estoque_col = _find_column(df, ["estoque", "saldo", "quantidade", "balanco", "balanço"])
    preco_col = _find_column(
        df,
        ["preco unitario", "preço unitário", "preco", "preço", "valor"],
    )
    deposito_col = _find_column(df, ["deposito", "depósito", "deposito id", "depósito id"])

    deposito_manual = str(st.session_state.get("deposito_nome_manual", "")).strip()
    rows: List[Dict] = []

    for _, row in df.iterrows():
        payload = {
            "codigo": normalize_value(row[sku_col]) if sku_col else None,
            "estoque": safe_float(row[estoque_col]) if estoque_col else None,
            "preco": safe_float(row[preco_col]) if preco_col else None,
            "deposito_id": (
                normalize_value(row[deposito_col])
                if deposito_col
                else deposito_manual or None
            ),
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
    st.subheader("Envio por API")

    df = _base_df()
    modo = str(st.session_state.get("tipo_operacao_bling", "cadastro")).strip().lower()

    if not isinstance(df, pd.DataFrame) or df.empty:
        st.info(
            "Gere primeiro o preview final e o arquivo na aba 'Origem dos dados'. "
            "A aba Envio usa apenas o DataFrame final já preparado para API."
        )
        return

    user_key = _get_current_bling_user_key()
    auth = BlingAuthManager(user_key=user_key)
    conectado = bool(auth.get_connection_status().get("connected"))

    st.caption(
        f"Operação atual: **{'Cadastro / atualização de produtos' if modo == 'cadastro' else 'Atualização de estoque'}**"
    )
    st.caption(
        "Esta aba não recalcula o arquivo final e não altera o DataFrame usado no download."
    )

    if modo == "cadastro":
        rows = build_product_rows(df)
        validos, invalidos = validar_produtos(rows)

        st.write(f"Linhas analisadas para cadastro: **{len(rows)}**")

        if st.button("Gerar preview da API de cadastro", use_container_width=True):
            st.session_state["ultimo_log_envio"] = {
                "tipo": "cadastro",
                "validos": validos[:50],
                "invalidos": invalidos[:50],
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
                }

                if sucessos:
                    st.success(
                        f"{len(sucessos)} produto(s) enviado(s)/atualizado(s) no Bling."
                    )
                if erros:
                    st.error(f"{len(erros)} produto(s) falharam no envio.")
                    st.dataframe(pd.DataFrame(erros), use_container_width=True, height=220)
        else:
            st.info("Conecte o Bling para liberar o envio real de cadastro.")

    else:
        rows = build_stock_rows(df)
        validos, invalidos = validar_estoque(rows)

        st.write(f"Linhas analisadas para estoque: **{len(rows)}**")

        st.text_input(
            "Depósito / ID do depósito",
            key="deposito_nome_manual",
            help="Use este campo somente para o envio por API quando a planilha final não possuir coluna de depósito.",
        )

        if st.button("Gerar preview da API de estoque", use_container_width=True):
            st.session_state["ultimo_log_envio"] = {
                "tipo": "estoque",
                "validos": validos[:50],
                "invalidos": invalidos[:50],
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
                }

                if sucessos:
                    st.success(f"{len(sucessos)} linha(s) de estoque enviada(s) ao Bling.")
                if erros:
                    st.error(f"{len(erros)} linha(s) falharam no envio do estoque.")
                    st.dataframe(pd.DataFrame(erros), use_container_width=True, height=220)
        else:
            st.info("Conecte o Bling para liberar o envio real de estoque.")
