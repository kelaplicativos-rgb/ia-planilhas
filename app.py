
import streamlit as st

from bling_app_zero.utils.init_app import init_app
from bling_app_zero.ui.app_helpers import (
    get_etapa,
    log_debug,
    render_log_debug,
    render_topo_navegacao,
    sincronizar_etapa_da_url,
)
from bling_app_zero.ui.origem_dados import render_origem_dados
from bling_app_zero.ui.origem_precificacao import render_origem_precificacao
from bling_app_zero.ui.origem_mapeamento import render_origem_mapeamento
from bling_app_zero.ui.preview_final import render_preview_final


def _registrar_boot_log() -> None:
    """
    Gera uma entrada inicial de log uma única vez por sessão.
    Isso garante que o painel/botão de log não suma por ausência total de conteúdo.
    """
    if st.session_state.get("_boot_log_registrado", False):
        return

    etapa = str(st.session_state.get("etapa", "origem") or "origem").strip()
    log_debug(f"App iniciado com sucesso. Etapa atual: {etapa}")
    st.session_state["_boot_log_registrado"] = True


def _processar_callback_bling() -> None:
    """
    Processa automaticamente o retorno do OAuth do Bling.
    Não quebra o app se o módulo ainda não existir ou falhar.
    """
    try:
        from bling_app_zero.core import bling_auth  # type: ignore
    except Exception:
        return

    try:
        if not hasattr(bling_auth, "processar_callback_se_existir"):
            return

        resultado = bling_auth.processar_callback_se_existir()
        if not isinstance(resultado, dict):
            return

        executado = bool(resultado.get("executado", False))
        ok = bool(resultado.get("ok", False))
        mensagem = str(resultado.get("mensagem", "") or "").strip()

        if not executado:
            return

        if ok:
            st.success(mensagem or "Conexão com Bling concluída com sucesso.")
            log_debug(mensagem or "Conexão com Bling concluída com sucesso.", nivel="INFO")
        else:
            st.error(mensagem or "Falha ao processar retorno do Bling.")
            log_debug(mensagem or "Falha ao processar retorno do Bling.", nivel="ERRO")
    except Exception as exc:
        st.error(f"Falha ao processar callback do Bling: {exc}")
        log_debug(f"Falha ao processar callback do Bling: {exc}", nivel="ERRO")


def _render_etapa_atual() -> None:
    etapa = get_etapa()
    log_debug(f"Renderizando etapa: {etapa}")

    if etapa == "origem":
        render_origem_dados()
    elif etapa == "precificacao":
        render_origem_precificacao()
    elif etapa == "mapeamento":
        render_origem_mapeamento()
    elif etapa == "preview_final":
        render_preview_final()
    else:
        render_origem_dados()


st.set_page_config(
    page_title="IA Planilhas → Bling",
    layout="wide",
)

init_app()
sincronizar_etapa_da_url()
_registrar_boot_log()
_processar_callback_bling()

st.title("🚀 IA Planilhas → Bling")
render_topo_navegacao()
_render_etapa_atual()

# Painel visual de log sempre no final da tela
render_log_debug()

