from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from bling_app_zero.core.bling_auth import BlingAuthManager
from bling_app_zero.ui.app_helpers import (
    garantir_estado_base,
    log_debug,
    render_debug_panel,
)
from bling_app_zero.ui.origem_dados import render_origem_dados
from bling_app_zero.ui.origem_mapeamento import render_origem_mapeamento
from bling_app_zero.ui.preview_final import render_preview_final
from bling_app_zero.ui.send_panel import (
    render_bling_primeiro_acesso,
    render_send_panel,
)
from bling_app_zero.utils.init_app import inicializar_app

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="IA Planilhas Bling", layout="wide")

APP_VERSION = "1.0.34"
VERSION_JSON_PATH = Path(__file__).with_name("version.json")


# =========================
# VERSIONAMENTO
# =========================
def _safe_now_str() -> str:
    try:
        return pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


def _ler_version_json() -> dict:
    try:
        if not VERSION_JSON_PATH.exists():
            return {}
        bruto = VERSION_JSON_PATH.read_text(encoding="utf-8")
        data = json.loads(bruto)
        if isinstance(data, dict):
            return data
        return {}
    except Exception as e:
        log_debug(f"[VERSION] erro ao ler version.json: {e}", "ERROR")
        return {}


def _salvar_version_json(data: dict) -> bool:
    try:
        VERSION_JSON_PATH.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return True
    except Exception as e:
        log_debug(f"[VERSION] erro ao salvar version.json: {e}", "ERROR")
        return False


def _sincronizar_version_json_com_app() -> dict:
    atual = _ler_version_json()
    history = atual.get("history", [])
    if not isinstance(history, list):
        history = []

    version_json = str(atual.get("version") or "").strip()
    if version_json == APP_VERSION:
        return atual if atual else {
            "version": APP_VERSION,
            "updated_at": _safe_now_str(),
            "last_title": "Versionamento sincronizado",
            "last_description": "Version.json alinhado com APP_VERSION.",
            "history": history,
        }

    novo_registro = {
        "version": APP_VERSION,
        "date": _safe_now_str(),
        "title": "Atualização automática de versão",
        "description": "Sincronizado automaticamente com APP_VERSION do app.py.",
    }

    if not any(
        isinstance(item, dict)
        and str(item.get("version") or "").strip() == APP_VERSION
        for item in history
    ):
        history.append(novo_registro)

    novo = {
        "version": APP_VERSION,
        "updated_at": _safe_now_str(),
        "last_title": "Atualização automática de versão",
        "last_description": "Version.json sincronizado automaticamente com APP_VERSION do app.py.",
        "history": history,
    }
    salvou = _salvar_version_json(novo)
    if salvou:
        log_debug(f"[VERSION] version.json sincronizado para {APP_VERSION}", "INFO")
        return novo
    return atual if atual else novo


def _resolver_app_version_exibida(version_data: dict) -> str:
    try:
        version_json = str((version_data or {}).get("version") or "").strip()
        if version_json:
            return version_json
    except Exception:
        pass
    return APP_VERSION


# =========================
# LIMPEZA DE SESSÃO POR VERSÃO
# =========================
def _garantir_estado_versionamento() -> None:
    if "_app_loaded_version" not in st.session_state:
        st.session_state["_app_loaded_version"] = APP_VERSION
    if "_app_last_seen_version" not in st.session_state:
        st.session_state["_app_last_seen_version"] = APP_VERSION


def _chaves_lixo_legado() -> set[str]:
    return {
        "_cache_log",
        "_cache_log_exibido",
        "_version_reload_requested",
        "_update_available",
        "_legacy_version_notice",
        "_toast_cache_version",
        "_build_notice",
    }


def _chaves_preservadas_na_limpeza() -> set[str]:
    return {
        "_app_loaded_version",
        "_app_last_seen_version",
        "etapa_origem",
        "etapa",
        "etapa_fluxo",
        "bling_primeiro_acesso_decidido",
        "bling_primeiro_acesso_escolha",
        "_debug_logs",
        "_debug_logs_text",
        "_debug_panel_open",
        "acesso_cliente_id",
        "acesso_liberado",
        "bling_user_key",
        "user_key",
        "bi",
        "_oauth_state",
        "_oauth_pending_user_key",
        "_bling_callback_status",
        "_bling_callback_message",
        "bling_conectado",
        "bling_conexao_ok",
        "bling_connection_message",
        "bling_connection_checked",
        "bling_ultimo_status",
        "bling_connection_source",
    }


def _limpar_lixos_de_sessao() -> None:
    for chave in _chaves_lixo_legado():
        st.session_state.pop(chave, None)


def _limpar_sessao_por_versao() -> bool:
    """
    Quando APP_VERSION mudar, limpa estados antigos/lixos de sessão sem destruir
    todo o fluxo do usuário de forma cega.
    """
    versao_sessao = str(st.session_state.get("_app_loaded_version") or "").strip()

    _limpar_lixos_de_sessao()

    if not versao_sessao:
        st.session_state["_app_loaded_version"] = APP_VERSION
        st.session_state["_app_last_seen_version"] = APP_VERSION
        return False

    if versao_sessao == APP_VERSION:
        st.session_state["_app_last_seen_version"] = APP_VERSION
        return False

    log_debug(
        f"[VERSION] mudança detectada: sessão {versao_sessao} -> código {APP_VERSION}. Limpando sessão antiga.",
        "INFO",
    )
    preservadas = _chaves_preservadas_na_limpeza()
    snapshot = {k: st.session_state.get(k) for k in preservadas if k in st.session_state}

    for chave in list(st.session_state.keys()):
        if chave not in preservadas:
            st.session_state.pop(chave, None)

    for chave, valor in snapshot.items():
        st.session_state[chave] = valor

    try:
        st.cache_data.clear()
    except Exception:
        pass

    try:
        st.cache_resource.clear()
    except Exception:
        pass

    st.session_state["_app_loaded_version"] = APP_VERSION
    st.session_state["_app_last_seen_version"] = APP_VERSION
    st.session_state["etapa_origem"] = "conexao"
    st.session_state["etapa"] = "conexao"
    st.session_state["etapa_fluxo"] = "conexao"
    return True


def _executar_reload_app() -> None:
    try:
        st.cache_data.clear()
    except Exception:
        pass

    try:
        st.cache_resource.clear()
    except Exception:
        pass

    _limpar_lixos_de_sessao()
    st.session_state["_app_loaded_version"] = APP_VERSION
    st.session_state["_app_last_seen_version"] = APP_VERSION
    st.rerun()


def _render_controle_versao(version_data: dict) -> None:
    versao_exibida = _resolver_app_version_exibida(version_data)

    with st.container():
        col1, col2 = st.columns([3, 1])

        with col1:
            st.caption(f"Versão: {versao_exibida}")
            updated_at = str((version_data or {}).get("updated_at") or "").strip()
            if updated_at:
                st.caption(f"Última atualização registrada: {updated_at}")

        with col2:
            if st.button(" Recarregar app", use_container_width=True, key="btn_recarregar_app_topo"):
                log_debug("[VERSION] recarga manual acionada pelo usuário", "INFO")
                _executar_reload_app()

    last_title = str((version_data or {}).get("last_title") or "").strip()
    last_description = str((version_data or {}).get("last_description") or "").strip()

    if last_title or last_description:
        with st.expander(" Controle de versão", expanded=False):
            if last_title:
                st.write(f"**Última mudança:** {last_title}")
            if last_description:
                st.write(last_description)

            history = (version_data or {}).get("history", [])
            if isinstance(history, list) and history:
                st.markdown("**Histórico recente**")
                for item in reversed(history[-5:]):
                    if not isinstance(item, dict):
                        continue
                    versao = str(item.get("version") or "").strip()
                    data = str(item.get("date") or "").strip()
                    titulo = str(item.get("title") or "").strip()
                    descricao = str(item.get("description") or "").strip()

                    linha = f"- **{versao}**"
                    if data:
                        linha += f" · {data}"
                    if titulo:
                        linha += f" · {titulo}"
                    if descricao:
                        linha += f" — {descricao}"

                    st.markdown(linha)


# =========================
# INIT
# =========================
inicializar_app()
garantir_estado_base()
_garantir_estado_versionamento()

VERSION_DATA = _sincronizar_version_json_com_app()

houve_limpeza_versao = _limpar_sessao_por_versao()
if houve_limpeza_versao:
    st.rerun()


# =========================
# HELPERS
# =========================
ETAPAS_VALIDAS = {"conexao", "origem", "mapeamento", "final", "envio"}


def _safe_df(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0
    except Exception:
        return False


def _safe_df_com_linhas(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0
    except Exception:
        return False


def _normalizar_etapa(valor: object) -> str:
    try:
        etapa_normalizada = str(valor or "conexao").strip().lower()
    except Exception:
        etapa_normalizada = "conexao"

    if etapa_normalizada not in ETAPAS_VALIDAS:
        return "conexao"
    return etapa_normalizada


def _obter_etapa_atual() -> str:
    candidatos = [
        st.session_state.get("etapa_origem"),
        st.session_state.get("etapa"),
        st.session_state.get("etapa_fluxo"),
    ]
    for valor in candidatos:
        etapa_lida = _normalizar_etapa(valor)
        if etapa_lida in ETAPAS_VALIDAS:
            return etapa_lida
    return "conexao"


def _sincronizar_etapa_global(etapa_destino: str) -> str:
    etapa_ok = _normalizar_etapa(etapa_destino)
    st.session_state["etapa_origem"] = etapa_ok
    st.session_state["etapa"] = etapa_ok
    st.session_state["etapa_fluxo"] = etapa_ok
    log_debug(f"[APP] navegação para etapa: {etapa_ok}", "INFO")
    return etapa_ok


def _ir_para(etapa: str) -> None:
    _sincronizar_etapa_global(etapa)
    st.rerun()


def _obter_df_fluxo():
    candidatos = [
        "df_final",
        "df_saida",
        "df_precificado",
        "df_calc_precificado",
        "df_origem",
    ]
    for chave in candidatos:
        df = st.session_state.get(chave)
        if _safe_df(df):
            return df
    return None


def _sincronizar_df_fluxo() -> None:
    df_final = st.session_state.get("df_final")
    df_saida = st.session_state.get("df_saida")

    if _safe_df(df_final) and not _safe_df(df_saida):
        try:
            st.session_state["df_saida"] = df_final.copy()
        except Exception:
            st.session_state["df_saida"] = df_final
        return

    if _safe_df(df_saida) and not _safe_df(df_final):
        try:
            st.session_state["df_final"] = df_saida.copy()
        except Exception:
            st.session_state["df_final"] = df_saida
        return


def _garantir_estado_fluxo_inicial() -> None:
    if "bling_primeiro_acesso_decidido" not in st.session_state:
        st.session_state["bling_primeiro_acesso_decidido"] = False
    if "bling_primeiro_acesso_escolha" not in st.session_state:
        st.session_state["bling_primeiro_acesso_escolha"] = ""


def _pode_ir_para_mapeamento() -> bool:
    for chave in ["df_saida", "df_final", "df_precificado", "df_calc_precificado", "df_origem"]:
        if _safe_df_com_linhas(st.session_state.get(chave)):
            return True
    return False


def _pode_ir_para_final() -> bool:
    return _safe_df_com_linhas(_obter_df_fluxo())


def _resolver_bling_user_key() -> str:
    for chave in ["bling_user_key", "user_key", "bi"]:
        valor = str(st.session_state.get(chave) or "").strip()
        if valor:
            return valor
    return "default"


def _sanear_estado_bling_invalido(motivo: str = "") -> None:
    if motivo:
        log_debug(f"[APP] limpando estado Bling inválido: {motivo}", "WARNING")

    for chave in [
        "bling_conectado",
        "bling_conexao_ok",
        "bling_connection_checked",
        "bling_connection_source",
        "bling_ultimo_status",
    ]:
        st.session_state[chave] = False

    if motivo:
        st.session_state["bling_connection_message"] = motivo


def _token_bling_valido_real() -> bool:
    try:
        auth = BlingAuthManager(user_key=_resolver_bling_user_key())
        ok, token = auth.get_token()
        token = str(token or "").strip()

        if ok and token:
            return True

        _sanear_estado_bling_invalido("Sem token real salvo para este usuário.")
        return False
    except Exception as e:
        _sanear_estado_bling_invalido(f"Falha ao validar token real: {e}")
        log_debug(f"[APP] erro ao validar token Bling real: {e}", "ERROR")
        return False


def _esta_conectado_real() -> bool:
    return _token_bling_valido_real()


def _resolver_autoetapa() -> str:
    etapa_atual = _obter_etapa_atual()
    _sincronizar_df_fluxo()

    if etapa_atual == "conexao":
        if _esta_conectado_real():
            st.session_state["bling_conectado"] = True
            st.session_state["bling_conexao_ok"] = True
            st.session_state["bling_connection_checked"] = True
            st.session_state["bling_connection_source"] = "token_real"
            log_debug("[APP] token real detectado. Autoavançando para origem.", "INFO")
            return "origem"

        _sanear_estado_bling_invalido("Conexão real não encontrada. Permanecendo na etapa de conexão.")
        return "conexao"

    if etapa_atual == "mapeamento" and not _pode_ir_para_mapeamento():
        log_debug(
            "[APP] mapeamento bloqueado por ausência de dados. Retornando para origem.",
            "WARNING",
        )
        return "origem"

    if etapa_atual in {"final", "envio"} and not _pode_ir_para_final():
        log_debug(
            "[APP] final/envio bloqueado por ausência de dados. Retornando para origem.",
            "WARNING",
        )
        return "origem"

    return etapa_atual


def _processar_callback_bling() -> None:
    try:
        auth = BlingAuthManager(user_key=_resolver_bling_user_key())
        resultado = auth.handle_oauth_callback()

        status = str(resultado.get("status") or "").strip().lower()
        mensagem = str(resultado.get("message") or "").strip()

        if status == "idle":
            return

        st.session_state["_bling_callback_status"] = status
        st.session_state["_bling_callback_message"] = mensagem

        if status == "success":
            if _token_bling_valido_real():
                st.session_state["bling_conectado"] = True
                st.session_state["bling_conexao_ok"] = True
                st.session_state["bling_connection_checked"] = True
                st.session_state["bling_ultimo_status"] = "success"
                st.session_state["bling_connection_source"] = "oauth_callback"
                st.session_state["bling_connection_message"] = (
                    mensagem or "Conectado com sucesso."
                )
                _sincronizar_etapa_global("origem")
                log_debug("[APP] callback OAuth concluído com token real válido.", "INFO")
                st.rerun()

            _sanear_estado_bling_invalido(
                "OAuth retornou sucesso, mas o token real não foi encontrado."
            )
            st.session_state["bling_ultimo_status"] = "error"
            st.session_state["bling_connection_message"] = (
                "OAuth retornou sucesso, mas não foi possível validar o token salvo."
            )
            _sincronizar_etapa_global("conexao")
            st.rerun()

        st.session_state["bling_ultimo_status"] = "error"
        st.session_state["bling_connection_message"] = mensagem or "Falha ao conectar com o Bling."
        _sanear_estado_bling_invalido(mensagem or "Falha ao conectar com o Bling.")
        _sincronizar_etapa_global("conexao")
        log_debug(f"[APP] callback OAuth retornou erro: {mensagem}", "ERROR")
        st.rerun()

    except Exception as e:
        _sanear_estado_bling_invalido(f"Erro ao processar callback do Bling: {e}")
        st.session_state["bling_ultimo_status"] = "error"
        st.session_state["bling_connection_message"] = f"Erro ao processar callback: {e}"
        _sincronizar_etapa_global("conexao")
        log_debug(f"[APP] erro no callback do Bling: {e}", "ERROR")


# =========================
# CALLBACK OAUTH
# =========================
_processar_callback_bling()


# =========================
# UI BASE
# =========================
st.title("IA Planilhas → Bling")
_render_controle_versao(VERSION_DATA)
render_debug_panel()
_garantir_estado_fluxo_inicial()


# =========================
# CONTROLE DE ETAPA
# =========================
etapa = _sincronizar_etapa_global(_resolver_autoetapa())

if etapa not in ETAPAS_VALIDAS:
    log_debug(f"Etapa inválida detectada no app.py: {etapa}", "ERROR")
    _ir_para("conexao")


# =========================
# ETAPA 0 — CONEXÃO
# =========================
if etapa == "conexao":
    render_bling_primeiro_acesso(
        on_skip=lambda: _ir_para("origem"),
        on_continue=lambda: _ir_para("origem"),
    )

# =========================
# ETAPA 1 — ORIGEM
# =========================
elif etapa == "origem":
    render_origem_dados()

# =========================
# ETAPA 2 — MAPEAMENTO
# =========================
elif etapa == "mapeamento":
    if not _pode_ir_para_mapeamento():
        st.warning("⚠️ Carregue os dados na origem antes de acessar o mapeamento.")
        if st.button("⬅️ Voltar para origem", use_container_width=True):
            _ir_para("origem")
        st.stop()

    render_origem_mapeamento()

# =========================
# ETAPA 3 — FINAL
# =========================
elif etapa == "final":
    df_fluxo = _obter_df_fluxo()
    if not _safe_df(df_fluxo):
        log_debug("FINAL sem dados válidos", "ERROR")
        st.warning("⚠️ Nenhum dado disponível.\nVolte para o mapeamento.")
        if st.button("⬅️ Voltar", use_container_width=True):
            _ir_para("mapeamento")
        st.stop()

    render_preview_final()
    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ Voltar para mapeamento", use_container_width=True):
            _ir_para("mapeamento")
    with col2:
        if st.button("Ir para envio", use_container_width=True, type="primary"):
            _ir_para("envio")

# =========================
# ETAPA 4 — ENVIO
# =========================
elif etapa == "envio":
    df_fluxo = _obter_df_fluxo()
    if not _safe_df(df_fluxo):
        log_debug("ENVIO sem dados válidos", "ERROR")
        st.warning("⚠️ Nenhum dado disponível para envio.")
        if st.button("⬅️ Voltar para final", use_container_width=True):
            _ir_para("final")
        st.stop()

    st.markdown("---")
    if st.button("⬅️ Voltar para final", use_container_width=True):
        _ir_para("final")

    st.markdown("---")
    render_send_panel()

# =========================
# FALLBACK
# =========================
else:
    log_debug(f"Fallback etapa inesperada: {etapa}", "ERROR")
    _ir_para("conexao")
    
