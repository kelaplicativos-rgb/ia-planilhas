from __future__ import annotations

import io
import json
from datetime import datetime
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
    # Prioriza preview/final da API, depois saída final, por último origem.
    for key in ("df_saida_api", "df_saida", "df_origem"):
        df = st.session_state.get(key)
        if isinstance(df, pd.DataFrame) and not df.empty:
            return df.copy()
    return None


def _agora_str() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def _json_bytes(data: Dict) -> bytes:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str).encode("utf-8")


def _csv_bytes_from_records(records: List[Dict]) -> bytes:
    df = pd.DataFrame(records or [])
    if df.empty:
        df = pd.DataFrame([{"info": "sem_dados"}])

    output = io.StringIO()
    df.to_csv(output, index=False)
    return output.getvalue().encode("utf-8")


def _salvar_log_envio(log_data: Dict) -> None:
    st.session_state["ultimo_log_envio_api"] = log_data


def _render_exportacao_logs() -> None:
    log_data = st.session_state.get("ultimo_log_envio_api")
    if not isinstance(log_data, dict) or not log_data:
        return

    st.divider()
    st.subheader("Logs do último envio / preview")

    tipo = str(log_data.get("tipo", "envio")).strip() or "envio"
    timestamp = str(log_data.get("timestamp", _agora_str())).strip()

    resumo = {
        "tipo": tipo,
        "timestamp": timestamp,
        "modo": log_data.get("modo"),
        "usuario_bling": log_data.get("user_key"),
        "total_linhas": log_data.get("total_linhas", 0),
        "total_validos": log_data.get("total_validos", 0),
        "total_invalidos": log_data.get("total_invalidos", 0),
        "total_sucessos": log_data.get("total_sucessos", 0),
        "total_erros": log_data.get("total_erros", 0),
    }

    st.json(resumo)

    if log_data.get("invalidos"):
        with st.expander("Linhas com pendência", expanded=False):
            st.dataframe(pd.DataFrame(log_data["invalidos"]), use_container_width=True, height=220)

    if log_data.get("sucessos"):
        with st.expander("Sucessos", expanded=False):
            st.dataframe(pd.DataFrame(log_data["sucessos"]), use_container_width=True, height=220)

    if log_data.get("erros"):
        with st.expander("Erros", expanded=False):
            st.dataframe(pd.DataFrame(log_data["erros"]), use_container_width=True, height=220)

    nome_base = f"log_{tipo}_{timestamp}"

    c1, c2, c3 = st.columns(3)

    with c1:
        st.download_button(
            "Baixar log completo (JSON)",
            data=_json_bytes(log_data),
            file_name=f"{nome_base}.json",
            mime="application/json",
            use_container_width=True,
        )

    with c2:
        registros_csv = []

        for item in log_data.get("invalidos", []):
            registros_csv.append({"grupo": "invalidos", **item})

        for item in log_data.get("sucessos", []):
            registros_csv.append({"grupo": "sucessos", **item})

        for item in log_data.get("erros", []):
            registros_csv.append({"grupo": "erros", **item})

        if not registros_csv:
            registros_csv = [{"grupo": "resumo", **resumo}]

        st.download_button(
            "Baixar log resumido (CSV)",
            data=_csv_bytes_from_records(registros_csv),
            file_name=f"{nome_base}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with c3:
        if st.button("Limpar log atual", use_container_width=True):
            st.session_state.pop("ultimo_log_envio_api", None)
            st.rerun()


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

    deposito_manual = str(st.session_state.get("deposito_nome_manual_api", "")).strip()

    rows: List[Dict] = []

    for _, row in df.iterrows():
        payload = {
            "codigo": normalize_value(row[sku_col]) if sku_col else None,
            "estoque": safe_float(row[estoque_col]) if estoque_col else None,
            "preco": safe_float(row[preco_col]) if preco_col else None,
            "deposito_id": (
                normalize_value(row[deposito_col]) if deposito_col else deposito_manual or None
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


def _executar_envio_produtos(validos: List[Dict], user_key: str) -> None:
    total = len(validos)
    progresso = st.progress(0)
    status = st.empty()

    status.info("Iniciando envio de cadastro para o Bling...")
    progresso.progress(15)

    sucessos, erros = sync_products(validos, user_key=user_key)

    progresso.progress(100)
    status.success("Envio de cadastro concluído.")

    log_data = {
        "tipo": "cadastro_real",
        "timestamp": _agora_str(),
        "modo": "cadastro",
        "user_key": user_key,
        "total_linhas": total,
        "total_validos": total,
        "total_invalidos": 0,
        "total_sucessos": len(sucessos),
        "total_erros": len(erros),
        "invalidos": [],
        "sucessos": sucessos[:300],
        "erros": erros[:300],
    }
    _salvar_log_envio(log_data)

    if sucessos:
        st.success(f"{len(sucessos)} produto(s) enviado(s)/atualizado(s) com sucesso no Bling.")
    if erros:
        st.error(f"{len(erros)} produto(s) falharam no envio.")
        st.dataframe(pd.DataFrame(erros), use_container_width=True, height=220)


def _executar_envio_estoque(validos: List[Dict], user_key: str) -> None:
    total = len(validos)
    progresso = st.progress(0)
    status = st.empty()

    status.info("Iniciando envio de estoque para o Bling...")
    progresso.progress(15)

    sucessos, erros = sync_stocks(validos, user_key=user_key)

    progresso.progress(100)
    status.success("Envio de estoque concluído.")

    log_data = {
        "tipo": "estoque_real",
        "timestamp": _agora_str(),
        "modo": "estoque",
        "user_key": user_key,
        "total_linhas": total,
        "total_validos": total,
        "total_invalidos": 0,
        "total_sucessos": len(sucessos),
        "total_erros": len(erros),
        "invalidos": [],
        "sucessos": sucessos[:300],
        "erros": erros[:300],
    }
    _salvar_log_envio(log_data)

    if sucessos:
        st.success(f"{len(sucessos)} linha(s) de estoque enviada(s) com sucesso no Bling.")
    if erros:
        st.error(f"{len(erros)} linha(s) falharam no envio do estoque.")
        st.dataframe(pd.DataFrame(erros), use_container_width=True, height=220)


def render_send_panel() -> None:
    st.subheader("Envio por API")

    df = _base_df()
    modo = str(st.session_state.get("tipo_operacao_bling", "cadastro")).strip().lower()

    if not isinstance(df, pd.DataFrame) or df.empty:
        st.info(
            "Gere primeiro o preview final e o arquivo na aba 'Origem dos dados'."
        )
        _render_exportacao_logs()
        return

    user_key = _get_current_bling_user_key()
    auth = BlingAuthManager(user_key=user_key)
    conectado = bool(auth.get_connection_status().get("connected"))

    if conectado:
        st.success("Bling conectado. O envio real está liberado.")
    else:
        st.info("Conecte o Bling para liberar o envio real.")

    tab1, tab2 = st.tabs(["Preparar cadastro", "Preparar estoque"])

    with tab1:
        rows = build_product_rows(df)
        validos, invalidos = validar_produtos(rows)

        st.write(f"Linhas analisadas para cadastro: **{len(rows)}**")

        if st.button("Gerar preview de cadastro", use_container_width=True):
            log_data = {
                "tipo": "cadastro_preview",
                "timestamp": _agora_str(),
                "modo": "cadastro",
                "user_key": user_key,
                "total_linhas": len(rows),
                "total_validos": len(validos),
                "total_invalidos": len(invalidos),
                "total_sucessos": 0,
                "total_erros": 0,
                "validos": validos[:300],
                "invalidos": invalidos[:300],
                "sucessos": [],
                "erros": [],
            }
            _salvar_log_envio(log_data)

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
                _executar_envio_produtos(validos, user_key=user_key)

    with tab2:
        rows = build_stock_rows(df)
        validos, invalidos = validar_estoque(rows)

        st.write(f"Linhas analisadas para estoque: **{len(rows)}**")

        st.text_input(
            "Depósito / ID do depósito",
            key="deposito_nome_manual_api",
            help="Use este campo quando a planilha não possuir uma coluna de depósito.",
        )

        if st.button("Gerar preview de estoque", use_container_width=True):
            log_data = {
                "tipo": "estoque_preview",
                "timestamp": _agora_str(),
                "modo": "estoque",
                "user_key": user_key,
                "total_linhas": len(rows),
                "total_validos": len(validos),
                "total_invalidos": len(invalidos),
                "total_sucessos": 0,
                "total_erros": 0,
                "validos": validos[:300],
                "invalidos": invalidos[:300],
                "sucessos": [],
                "erros": [],
            }
            _salvar_log_envio(log_data)

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
                _executar_envio_estoque(validos, user_key=user_key)

    _render_exportacao_logs()
