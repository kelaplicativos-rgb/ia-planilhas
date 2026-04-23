from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import (
    get_etapa,
    log_debug,
    safe_df_estrutura,
    sincronizar_etapa_global,
)


def garantir_etapa_preview_ativa() -> None:
    if get_etapa() != "preview_final":
        sincronizar_etapa_global("preview_final")
    st.session_state["_etapa_url_inicializada"] = True
    st.session_state["_ultima_etapa_sincronizada_url"] = "preview_final"


def inicializar_estado_preview() -> None:
    defaults = {
        "bling_sync_strategy": "inteligente",
        "bling_sync_auto_mode": "manual",
        "bling_sync_interval_value": 15,
        "bling_sync_interval_unit": "minutos",
        "bling_conectado": False,
        "bling_status_texto": "Desconectado",
        "bling_envio_resultado": None,
        "preview_download_realizado": False,
        "preview_validacao_ok": False,
        "preview_validacao_erros": [],
        "preview_hash_df_final": "",
        "preview_envio_em_execucao": False,
        "preview_envio_logs": [],
        "preview_envio_resumo": {},
        "gtin_logs_limpeza": [],
        "gtin_resumo_limpeza": {},
    }
    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


def obter_df_final_exclusivo() -> pd.DataFrame:
    df = st.session_state.get("df_final")
    if safe_df_estrutura(df):
        return df.copy()
    return pd.DataFrame()


def obter_deposito_nome_persistido() -> str:
    candidatos = [
        st.session_state.get("deposito_nome"),
        st.session_state.get("deposito_nome_widget"),
        st.session_state.get("deposito"),
    ]
    for valor in candidatos:
        texto = str(valor or "").strip()
        if texto:
            return texto
    return ""


def sincronizar_deposito_nome() -> str:
    deposito = obter_deposito_nome_persistido()
    st.session_state["deposito_nome"] = deposito
    st.session_state["deposito_nome_widget"] = deposito
    return deposito


def hash_df_visual(df: pd.DataFrame) -> str:
    try:
        if not isinstance(df, pd.DataFrame):
            return ""

        partes = ["|".join([str(c) for c in df.columns.tolist()])]
        amostra = df.head(30).fillna("").astype(str)
        for _, row in amostra.iterrows():
            partes.append("|".join(row.tolist()))
        return str(hash("\n".join(partes)))
    except Exception:
        return ""


def resetar_status_envio_visual() -> None:
    st.session_state["preview_envio_em_execucao"] = False
    st.session_state["preview_envio_logs"] = []
    st.session_state["preview_envio_resumo"] = {}


def sincronizar_estado_quando_df_mudar(df_final: pd.DataFrame) -> None:
    hash_atual = hash_df_visual(df_final)
    hash_anterior = str(st.session_state.get("preview_hash_df_final", "") or "")

    if hash_atual != hash_anterior:
        st.session_state["preview_download_realizado"] = False
        st.session_state["bling_envio_resultado"] = None
        st.session_state["preview_hash_df_final"] = hash_atual
        resetar_status_envio_visual()
        log_debug(
            "df_final alterado no preview; confirmação de download e resultado de envio foram resetados.",
            nivel="INFO",
        )


def origem_site_ativa() -> bool:
    modo_origem = str(st.session_state.get("modo_origem", "") or "").strip().lower()
    origem_tipo = str(st.session_state.get("origem_upload_tipo", "") or "").strip().lower()
    origem_nome = str(st.session_state.get("origem_upload_nome", "") or "").strip().lower()

    return (
        "site" in modo_origem
        or "site_gpt" in origem_tipo
        or "varredura_site_" in origem_nome
        or "site_" in origem_nome
    )


def url_site_atual() -> str:
    return str(st.session_state.get("site_fornecedor_url", "") or "").strip()


def varredura_site_concluida() -> bool:
    if not origem_site_ativa():
        return False

    df_origem = st.session_state.get("df_origem")
    return isinstance(df_origem, pd.DataFrame) and not df_origem.empty


def oauth_liberado(validacao_ok: bool) -> bool:
    return bool(
        validacao_ok
        and st.session_state.get("preview_download_realizado", False)
        and (not origem_site_ativa() or varredura_site_concluida())
    )


def fonte_descoberta_label(valor: str) -> str:
    valor_n = str(valor or "").strip().lower()
    mapa = {
        "sitemap": "Sitemap",
        "crawler_links": "Varredura de links",
        "http_direto": "Leitura direta do HTML",
        "produto_direto": "URL de produto",
        "": "-",
    }
    return mapa.get(valor_n, valor_n.replace("_", " ").title() or "-")


def resumo_rotina_site() -> dict[str, Any]:
    return {
        "origem_site_ativa": origem_site_ativa(),
        "url_site": url_site_atual(),
        "fonte_descoberta": fonte_descoberta_label(st.session_state.get("site_busca_fonte_descoberta", "")),
        "diagnostico_descobertos": int(st.session_state.get("site_busca_diagnostico_total_descobertos", 0) or 0),
        "diagnostico_validos": int(st.session_state.get("site_busca_diagnostico_total_validos", 0) or 0),
        "diagnostico_rejeitados": int(st.session_state.get("site_busca_diagnostico_total_rejeitados", 0) or 0),
        "auto_mode": st.session_state.get("bling_sync_auto_mode", "manual"),
        "interval_value": st.session_state.get("bling_sync_interval_value", 15),
        "interval_unit": st.session_state.get("bling_sync_interval_unit", "minutos"),
        "loop_ativo": bool(st.session_state.get("site_auto_loop_ativo", False)),
        "loop_status": str(st.session_state.get("site_auto_status", "inativo") or "inativo"),
        "ultima_execucao": str(st.session_state.get("site_auto_ultima_execucao", "") or ""),
    }


def safe_import_bling_auth():
    try:
        from bling_app_zero.core.bling_auth import (
            obter_resumo_conexao,
            render_conectar_bling,
            tem_token_valido,
            usuario_conectado_bling,
        )

        return {
            "obter_resumo_conexao": obter_resumo_conexao,
            "render_conectar_bling": render_conectar_bling,
            "tem_token_valido": tem_token_valido,
            "usuario_conectado_bling": usuario_conectado_bling,
        }
    except Exception:
        return None


def safe_import_bling_sync():
    try:
        from bling_app_zero.services.bling import bling_sync  # type: ignore

        return bling_sync
    except Exception:
        return None


def obter_status_conexao_bling() -> tuple[bool, str]:
    bling_auth = safe_import_bling_auth()
    if bling_auth is None:
        return False, "OAuth indisponível"

    try:
        obter_resumo_conexao = bling_auth.get("obter_resumo_conexao")
        if callable(obter_resumo_conexao):
            resumo = obter_resumo_conexao()
            conectado = bool(resumo.get("conectado", False))
            status = str(resumo.get("status", "Desconectado") or "Desconectado")
            return conectado, status

        usuario_conectado_bling = bling_auth.get("usuario_conectado_bling")
        tem_token_valido = bling_auth.get("tem_token_valido")
        if callable(usuario_conectado_bling) and callable(tem_token_valido):
            conectado = bool(usuario_conectado_bling()) and bool(tem_token_valido())
            return conectado, "Conectado" if conectado else "Desconectado"
    except Exception as exc:
        log_debug(f"Falha ao obter status da conexão Bling: {exc}", nivel="ERRO")

    return False, "Desconectado"
