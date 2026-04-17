
import inspect
from datetime import datetime

import pandas as pd
import streamlit as st

from bling_app_zero.utils.init_app import init_app
from bling_app_zero.ui.app_helpers import (
    get_etapa,
    log_debug,
    render_log_debug,
    render_topo_navegacao,
    safe_df_dados,
    safe_df_estrutura,
    sincronizar_etapa_da_url,
)
from bling_app_zero.ui.origem_dados import render_origem_dados
from bling_app_zero.ui.origem_precificacao import render_origem_precificacao
from bling_app_zero.ui.origem_mapeamento import render_origem_mapeamento
from bling_app_zero.ui.preview_final import render_preview_final


ETAPAS_ORDEM = ["origem", "precificacao", "mapeamento", "preview_final"]


def _inicializar_estado_global() -> None:
    defaults = {
        "_boot_log_registrado": False,
        "site_auto_loop_ativo": False,
        "site_auto_intervalo_segundos": 60,
        "site_auto_status": "inativo",
        "site_auto_ultima_execucao": "",
        "site_auto_modo": "manual",
        "site_auto_ultima_url": "",
        "site_auto_ultimo_total_produtos": 0,
        "wizard_etapa_atual": "origem",
        "wizard_etapa_maxima": "origem",
        "ultima_etapa_renderizada": "",
        "_troca_etapa_em_andamento": False,
    }

    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


def _registrar_boot_log() -> None:
    if st.session_state.get("_boot_log_registrado", False):
        return

    etapa = str(st.session_state.get("etapa", "origem") or "origem").strip()
    log_debug(f"App iniciado com sucesso. Etapa atual: {etapa}")
    st.session_state["_boot_log_registrado"] = True


def _indice_etapa(etapa: str) -> int:
    try:
        return ETAPAS_ORDEM.index(str(etapa))
    except ValueError:
        return 0


def _etapa_valida(etapa: str) -> str:
    etapa = str(etapa or "").strip()
    return etapa if etapa in ETAPAS_ORDEM else "origem"


def _wizard_maximo(etapa_a: str, etapa_b: str) -> str:
    return etapa_a if _indice_etapa(etapa_a) >= _indice_etapa(etapa_b) else etapa_b


def _pode_abrir_etapa(etapa: str) -> bool:
    etapa = _etapa_valida(etapa)
    etapa_maxima = _etapa_valida(st.session_state.get("wizard_etapa_maxima", "origem"))
    return _indice_etapa(etapa) <= _indice_etapa(etapa_maxima)


def _pre_requisitos_etapa(etapa: str) -> tuple[bool, str]:
    etapa = _etapa_valida(etapa)

    if etapa == "origem":
        return True, ""

    if etapa == "precificacao":
        df_origem = st.session_state.get("df_origem")
        if safe_df_dados(df_origem):
            return True, ""
        return False, "Carregue uma origem de dados válida antes de seguir para a precificação."

    if etapa == "mapeamento":
        df_precificado = st.session_state.get("df_precificado")
        df_modelo = st.session_state.get("df_modelo")

        if not safe_df_dados(df_precificado):
            return False, "Conclua a precificação antes de seguir para o mapeamento."

        if not safe_df_estrutura(df_modelo):
            return False, "Carregue o modelo padrão antes de seguir para o mapeamento."

        return True, ""

    if etapa == "preview_final":
        df_final = st.session_state.get("df_final")
        if safe_df_estrutura(df_final):
            return True, ""
        return False, "Aplique o mapeamento e gere o resultado final antes de abrir o preview."

    return False, "Etapa inválida."


def _set_etapa_segura(nova_etapa: str, origem: str = "sistema") -> None:
    nova_etapa = _etapa_valida(nova_etapa)
    etapa_atual = _etapa_valida(st.session_state.get("wizard_etapa_atual", "origem"))

    if etapa_atual == nova_etapa:
        return

    if not _pode_abrir_etapa(nova_etapa):
        log_debug(
            f"Tentativa bloqueada de abrir etapa {nova_etapa} acima da etapa máxima liberada.",
            nivel="ERRO",
        )
        return

    ok, motivo = _pre_requisitos_etapa(nova_etapa)
    if not ok:
        log_debug(
            f"Troca de etapa bloqueada ({etapa_atual} -> {nova_etapa}) | motivo: {motivo}",
            nivel="ERRO",
        )
        return

    st.session_state["_troca_etapa_em_andamento"] = True
    st.session_state["wizard_etapa_atual"] = nova_etapa
    st.session_state["etapa"] = nova_etapa
    st.session_state["wizard_etapa_maxima"] = _wizard_maximo(
        _etapa_valida(st.session_state.get("wizard_etapa_maxima", "origem")),
        nova_etapa,
    )
    st.session_state["ultima_etapa_renderizada"] = nova_etapa

    try:
        st.query_params["etapa"] = nova_etapa
    except Exception:
        pass

    log_debug(f"Etapa alterada: {etapa_atual} → {nova_etapa} | origem={origem}", nivel="INFO")
    st.session_state["_troca_etapa_em_andamento"] = False


def _sincronizar_wizard_com_estado() -> None:
    etapa_url = _etapa_valida(st.session_state.get("etapa", "origem"))
    etapa_wizard = _etapa_valida(st.session_state.get("wizard_etapa_atual", "origem"))

    if etapa_wizard not in ETAPAS_ORDEM:
        etapa_wizard = "origem"

    if etapa_url != etapa_wizard:
        if _pode_abrir_etapa(etapa_url):
            ok, _ = _pre_requisitos_etapa(etapa_url)
            if ok:
                st.session_state["wizard_etapa_atual"] = etapa_url
            else:
                st.session_state["etapa"] = etapa_wizard
        else:
            st.session_state["etapa"] = etapa_wizard

    st.session_state["wizard_etapa_atual"] = _etapa_valida(
        st.session_state.get("wizard_etapa_atual", "origem")
    )
    st.session_state["wizard_etapa_maxima"] = _wizard_maximo(
        _etapa_valida(st.session_state.get("wizard_etapa_maxima", "origem")),
        st.session_state["wizard_etapa_atual"],
    )


def _atualizar_etapa_maxima_por_progresso() -> None:
    etapa_maxima = _etapa_valida(st.session_state.get("wizard_etapa_maxima", "origem"))

    df_origem = st.session_state.get("df_origem")
    df_precificado = st.session_state.get("df_precificado")
    df_modelo = st.session_state.get("df_modelo")
    df_final = st.session_state.get("df_final")

    if safe_df_dados(df_origem):
        etapa_maxima = _wizard_maximo(etapa_maxima, "precificacao")

    if safe_df_dados(df_precificado) and safe_df_estrutura(df_modelo):
        etapa_maxima = _wizard_maximo(etapa_maxima, "mapeamento")

    if safe_df_estrutura(df_final):
        etapa_maxima = _wizard_maximo(etapa_maxima, "preview_final")

    st.session_state["wizard_etapa_maxima"] = etapa_maxima


def _processar_callback_bling() -> None:
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


def _render_navegacao_travada() -> None:
    etapa_atual = _etapa_valida(st.session_state.get("wizard_etapa_atual", "origem"))
    etapa_maxima = _etapa_valida(st.session_state.get("wizard_etapa_maxima", "origem"))

    st.markdown("### Etapas do fluxo")
    colunas = st.columns(len(ETAPAS_ORDEM))

    labels = {
        "origem": "1. Origem",
        "precificacao": "2. Precificação",
        "mapeamento": "3. Mapeamento",
        "preview_final": "4. Preview final",
    }

    for coluna, etapa in zip(colunas, ETAPAS_ORDEM):
        liberada = _indice_etapa(etapa) <= _indice_etapa(etapa_maxima)
        atual = etapa == etapa_atual

        with coluna:
            clicou = st.button(
                labels.get(etapa, etapa.title()),
                use_container_width=True,
                disabled=not liberada,
                type="primary" if atual else "secondary",
                key=f"wizard_nav_{etapa}",
            )
            if clicou and liberada and etapa != etapa_atual:
                _set_etapa_segura(etapa, origem="wizard_nav")
                st.rerun()


def _render_etapa_atual() -> None:
    etapa = _etapa_valida(st.session_state.get("wizard_etapa_atual", "origem"))

    if st.session_state.get("ultima_etapa_renderizada", "") != etapa:
        st.session_state["ultima_etapa_renderizada"] = etapa

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
        log_debug(f"Etapa inválida detectada: {etapa}", nivel="ERRO")
        st.session_state["wizard_etapa_atual"] = "origem"
        st.session_state["etapa"] = "origem"
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


def _carimbar_execucao_site(total_produtos: int, url_site: str) -> None:
    st.session_state["site_auto_ultima_execucao"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state["site_auto_ultima_url"] = url_site
    st.session_state["site_auto_ultimo_total_produtos"] = int(total_produtos)
    st.session_state["site_auto_status"] = (
        "ativo" if st.session_state.get("site_auto_loop_ativo", False) else "inativo"
    )


def _chamar_busca_site_compativel(url_site: str, intervalo: int):
    from bling_app_zero.core.site_agent import buscar_produtos_site_com_gpt  # type: ignore

    kwargs = {
        "base_url": url_site,
        "diagnostico": True,
    }

    try:
        assinatura = inspect.signature(buscar_produtos_site_com_gpt)
        parametros = assinatura.parameters

        if "termo" in parametros:
            kwargs["termo"] = ""
        if "limite_links" in parametros:
            kwargs["limite_links"] = None
        if "modo_loop" in parametros:
            kwargs["modo_loop"] = False
        if "intervalo_segundos" in parametros:
            kwargs["intervalo_segundos"] = intervalo
    except Exception:
        pass

    return buscar_produtos_site_com_gpt(**kwargs)


def _executar_monitoramento_site_agora() -> None:
    url_site = str(st.session_state.get("site_fornecedor_url", "") or "").strip()
    if not url_site:
        st.warning("Nenhuma URL de fornecedor por site foi encontrada para monitoramento.")
        log_debug("Monitoramento do site solicitado sem URL válida.", nivel="ERRO")
        return

    try:
        from bling_app_zero.core.site_agent import buscar_produtos_site_com_gpt  # noqa: F401
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
        df_site = _chamar_busca_site_compativel(url_site, intervalo)

        if not isinstance(df_site, pd.DataFrame):
            df_site = None

        if df_site is None or getattr(df_site, "empty", True):
            st.warning("A busca por site foi executada, mas não encontrou produtos válidos.")
            log_debug("Monitoramento manual executado sem produtos válidos.", nivel="ERRO")
            _carimbar_execucao_site(0, url_site)
            return

        st.session_state["df_origem"] = df_site
        st.session_state["origem_upload_nome"] = f"varredura_site_{url_site}"
        st.session_state["origem_upload_tipo"] = "site_gpt"
        st.session_state["origem_upload_ext"] = "site_gpt"

        total = int(len(df_site))
        _carimbar_execucao_site(total, url_site)
        _atualizar_etapa_maxima_por_progresso()

        st.success(f"Monitoramento executado com sucesso. {total} produto(s) encontrados.")
        log_debug(f"Monitoramento manual executado com {total} produto(s).", nivel="INFO")

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
        ultimo_total = int(st.session_state.get("site_auto_ultimo_total_produtos", 0) or 0)

        st.caption(
            "Painel de controle do monitoramento da busca por site para uso junto do fluxo final de conexão e envio ao Bling."
        )

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Origem por site", "OK" if site_disponivel else "Indisponível")
        with col2:
            st.metric(
                "Loop automático",
                "Ativo" if st.session_state.get("site_auto_loop_ativo", False) else "Inativo",
            )
        with col3:
            st.metric("Status", status.title())
        with col4:
            st.metric("Último total", ultimo_total)

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
                    f"Loop automático do site ativado | url={url_site} | "
                    f"intervalo={st.session_state.get('site_auto_intervalo_segundos', 60)}s",
                    nivel="INFO",
                )
                st.success("Loop automático ativado.")
                st.info("O loop ficou armado no sistema. A execução recorrente real depende da infraestrutura ativa.")

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
_sincronizar_wizard_com_estado()
_atualizar_etapa_maxima_por_progresso()
_registrar_boot_log()
_processar_callback_bling()

st.title("🚀 IA Planilhas → Bling")
_render_navegacao_travada()
_render_painel_automacao_site()
_render_etapa_atual()

# Painel visual de log sempre no final da tela
render_log_debug()

