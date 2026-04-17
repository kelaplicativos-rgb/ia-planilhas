
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


def _inicializar_estado_global() -> None:
    defaults = {
        "_boot_log_registrado": False,
        "site_auto_loop_ativo": False,
        "site_auto_intervalo_segundos": 60,
        "site_auto_status": "inativo",
        "site_auto_ultima_execucao": "",
        "site_auto_modo": "manual",
    }

    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


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


def _origem_site_disponivel() -> bool:
    modo_origem = str(st.session_state.get("modo_origem", "") or "").strip().lower()
    origem_tipo = str(st.session_state.get("origem_upload_tipo", "") or "").strip().lower()
    origem_nome = str(st.session_state.get("origem_upload_nome", "") or "").strip().lower()
    url_site = str(st.session_state.get("site_fornecedor_url", "") or "").strip()

    if not url_site:
        return False

    return (
        "site" in modo_origem
        or "site_gpt" in origem_tipo
        or "varredura_site_" in origem_nome
    )


def _executar_monitoramento_site_agora() -> None:
    url_site = str(st.session_state.get("site_fornecedor_url", "") or "").strip()
    if not url_site:
        st.warning("Nenhuma URL de fornecedor por site foi encontrada para monitoramento.")
        log_debug("Monitoramento do site solicitado sem URL válida.", nivel="ERRO")
        return

    try:
        from bling_app_zero.core.site_agent import buscar_produtos_site_com_gpt  # type: ignore
    except Exception as exc:
        st.error(f"Falha ao importar monitor do site: {exc}")
        log_debug(f"Falha ao importar monitor do site: {exc}", nivel="ERRO")
        return

    intervalo = int(st.session_state.get("site_auto_intervalo_segundos", 60) or 60)
    st.session_state["site_auto_status"] = "executando"
    st.session_state["site_auto_modo"] = "manual_disparo"
    log_debug(
        f"Disparo manual do monitoramento do site | url={url_site} | intervalo={intervalo}s",
        nivel="INFO",
    )

    try:
        df_site = buscar_produtos_site_com_gpt(
            base_url=url_site,
            diagnostico=True,
            modo_loop=False,
            intervalo_segundos=intervalo,
        )

        if isinstance(df_site, type(None)) or getattr(df_site, "empty", True):
            st.warning("A busca por site foi executada, mas não encontrou produtos válidos.")
            log_debug("Monitoramento manual executado sem produtos válidos.", nivel="ERRO")
        else:
            st.session_state["df_origem"] = df_site
            st.session_state["origem_upload_nome"] = f"varredura_site_{url_site}"
            st.session_state["origem_upload_tipo"] = "site_gpt"
            st.session_state["origem_upload_ext"] = "site_gpt"
            st.success(f"Monitoramento executado com sucesso. {len(df_site)} produto(s) encontrados.")
            log_debug(f"Monitoramento manual executado com {len(df_site)} produto(s).", nivel="INFO")

        from datetime import datetime
        st.session_state["site_auto_ultima_execucao"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.session_state["site_auto_status"] = "ativo" if st.session_state.get("site_auto_loop_ativo", False) else "inativo"
    except Exception as exc:
        st.session_state["site_auto_status"] = "erro"
        st.error(f"Falha ao executar monitoramento do site: {exc}")
        log_debug(f"Falha ao executar monitoramento do site: {exc}", nivel="ERRO")


def _render_painel_automacao_site() -> None:
    with st.expander("⚙️ Automação do site + envio Bling", expanded=False):
        site_disponivel = _origem_site_disponivel()
        url_site = str(st.session_state.get("site_fornecedor_url", "") or "").strip()
        status = str(st.session_state.get("site_auto_status", "inativo") or "inativo")
        ultima_execucao = str(st.session_state.get("site_auto_ultima_execucao", "") or "").strip()

        st.caption(
            "Painel de controle do monitoramento da busca por site para uso junto do fluxo final de conexão e envio ao Bling."
        )

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Origem por site", "OK" if site_disponivel else "Indisponível")
        with col2:
            st.metric("Loop automático", "Ativo" if st.session_state.get("site_auto_loop_ativo", False) else "Inativo")
        with col3:
            st.metric("Status", status.title())

        st.number_input(
            "Intervalo do monitoramento (segundos)",
            min_value=5,
            step=5,
            key="site_auto_intervalo_segundos",
            help="Define o intervalo base do monitoramento do site para fallback automático.",
        )

        if url_site:
            st.write(f"**URL monitorada:** {url_site}")
        else:
            st.write("**URL monitorada:** não definida")

        if ultima_execucao:
            st.write(f"**Última execução:** {ultima_execucao}")

        c1, c2, c3 = st.columns(3)

        with c1:
            if st.button(
                "▶️ Ativar loop",
                use_container_width=True,
                key="btn_ativar_loop_site",
                disabled=not site_disponivel,
            ):
                st.session_state["site_auto_loop_ativo"] = True
                st.session_state["site_auto_status"] = "ativo"
                st.session_state["site_auto_modo"] = "loop"
                log_debug(
                    f"Loop automático do site ativado | url={url_site} | intervalo={st.session_state.get('site_auto_intervalo_segundos', 60)}s",
                    nivel="INFO",
                )
                st.success("Loop automático ativado.")

        with c2:
            if st.button(
                "⏸️ Desativar loop",
                use_container_width=True,
                key="btn_desativar_loop_site",
            ):
                st.session_state["site_auto_loop_ativo"] = False
                st.session_state["site_auto_status"] = "inativo"
                st.session_state["site_auto_modo"] = "manual"
                log_debug("Loop automático do site desativado.", nivel="INFO")
                st.success("Loop automático desativado.")

        with c3:
            if st.button(
                "🔄 Executar agora",
                use_container_width=True,
                key="btn_executar_monitor_site_agora",
                disabled=not site_disponivel,
            ):
                _executar_monitoramento_site_agora()

        if not site_disponivel:
            st.info(
                "Para liberar esta automação, use a origem 'Buscar no site do fornecedor' e informe uma URL válida."
            )
        else:
            st.caption(
                "O loop automático fica preparado aqui no app. O envio real contínuo depende do serviço de sincronização e da infraestrutura ativa."
            )


st.set_page_config(
    page_title="IA Planilhas → Bling",
    layout="wide",
)

init_app()
_inicializar_estado_global()
sincronizar_etapa_da_url()
_registrar_boot_log()
_processar_callback_bling()

st.title("🚀 IA Planilhas → Bling")
render_topo_navegacao()
_render_painel_automacao_site()
_render_etapa_atual()

# Painel visual de log sempre no final da tela
render_log_debug()

