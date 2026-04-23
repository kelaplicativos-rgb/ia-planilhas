import pandas as pd
import streamlit as st

from bling_app_zero.utils.init_app import init_app
from bling_app_zero.ui.app_helpers import (
    log_debug,
    render_botao_download_logs,
    render_log_debug,
    safe_df_dados,
    safe_df_estrutura,
    sincronizar_etapa_da_url,
)
from bling_app_zero.ui.origem_dados import render_origem_dados
from bling_app_zero.ui.origem_precificacao import render_origem_precificacao
from bling_app_zero.ui.origem_mapeamento import render_origem_mapeamento

try:
    from bling_app_zero.ui.preview_final import render_preview_final
except Exception:
    def render_preview_final():
        st.warning("⚠️ Módulo preview_final não encontrado.")
        st.info("Verifique se o arquivo bling_app_zero/ui/preview_final.py existe no repositório.")
        log_debug("preview_final.py não encontrado", nivel="ERRO")


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
        "mostrar_log_debug_ui": False,
        "_ultima_etapa_logada_render": "",
        "_flow_lock_preview_final": False,
        "_flow_lock_origem": "",
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


def _contar_linhas_df(df) -> int:
    return len(df) if isinstance(df, pd.DataFrame) else 0


def _query_param_etapa_atual() -> str:
    try:
        valor = st.query_params.get("etapa", "")
    except Exception:
        return ""

    if isinstance(valor, list):
        return _etapa_valida(valor[0] if valor else "")

    return _etapa_valida(valor)


def _definir_query_param_etapa(etapa: str) -> None:
    etapa = _etapa_valida(etapa)
    try:
        st.query_params["etapa"] = etapa
    except Exception:
        pass


def _preview_final_tem_df() -> bool:
    return safe_df_estrutura(st.session_state.get("df_final"))


def _flow_lock_preview_ativo() -> bool:
    """
    Trava inteligente do preview final.

    Corrige o bug:
    - IA/GTIN altera df_final;
    - Streamlit reroda;
    - URL/estado antigo tenta voltar para mapeamento;
    - app sai do preview final.

    Enquanto houver df_final e uma ação interna do preview estiver ativa,
    o wizard permanece em preview_final.
    """
    if not _preview_final_tem_df():
        return False

    gatilhos = [
        "_flow_lock_preview_final",
        "_preview_final_ia_ativa",
        "ia_descricao_aplicada",
        "df_final_manual_preservado",
        "df_final_gtin_atualizado",
    ]

    return any(bool(st.session_state.get(chave, False)) for chave in gatilhos)


def _ativar_flow_lock_preview_final(origem: str = "sistema") -> None:
    if not _preview_final_tem_df():
        return

    st.session_state["_flow_lock_preview_final"] = True
    st.session_state["_flow_lock_origem"] = origem
    st.session_state["wizard_etapa_atual"] = "preview_final"
    st.session_state["wizard_etapa_maxima"] = "preview_final"
    st.session_state["etapa"] = "preview_final"
    st.session_state["ultima_etapa_renderizada"] = "preview_final"
    st.session_state["_ultima_etapa_sincronizada_url"] = "preview_final"
    _definir_query_param_etapa("preview_final")


def _desativar_flow_lock_preview_final() -> None:
    st.session_state["_flow_lock_preview_final"] = False
    st.session_state["_preview_final_ia_ativa"] = False
    st.session_state["_flow_lock_origem"] = ""


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

    # Se o usuário clicou manualmente na navegação para sair do preview, libera.
    if origem in {"wizard_nav", "botao_preview", "usuario"} and nova_etapa != "preview_final":
        _desativar_flow_lock_preview_final()

    # Se foi rerun interno/URL/estado tentando sair do preview, bloqueia.
    if _flow_lock_preview_ativo() and nova_etapa != "preview_final" and origem not in {"wizard_nav", "botao_preview", "usuario"}:
        _ativar_flow_lock_preview_final(origem=f"bloqueio_saida_{origem}")
        log_debug(
            f"FLOW LOCK: tentativa automática bloqueada de sair do preview_final para {nova_etapa}.",
            nivel="INFO",
        )
        return

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

    _definir_query_param_etapa(nova_etapa)

    log_debug(f"Etapa alterada: {etapa_atual} → {nova_etapa} | origem={origem}", nivel="INFO")
    st.session_state["_troca_etapa_em_andamento"] = False


def _sincronizar_wizard_com_estado() -> None:
    if _flow_lock_preview_ativo():
        _ativar_flow_lock_preview_final(origem="sincronizar_wizard")
        return

    etapa_url = _query_param_etapa_atual()
    etapa_state = _etapa_valida(st.session_state.get("etapa", "origem"))
    etapa_wizard = _etapa_valida(st.session_state.get("wizard_etapa_atual", "origem"))

    etapa_referencia = etapa_url if etapa_url in ETAPAS_ORDEM else etapa_state

    if etapa_wizard not in ETAPAS_ORDEM:
        etapa_wizard = "origem"

    if etapa_referencia != etapa_wizard:
        if _pode_abrir_etapa(etapa_referencia):
            ok, _ = _pre_requisitos_etapa(etapa_referencia)
            if ok:
                st.session_state["wizard_etapa_atual"] = etapa_referencia
                st.session_state["etapa"] = etapa_referencia
            else:
                st.session_state["etapa"] = etapa_wizard
                _definir_query_param_etapa(etapa_wizard)
        else:
            st.session_state["etapa"] = etapa_wizard
            _definir_query_param_etapa(etapa_wizard)

    st.session_state["wizard_etapa_atual"] = _etapa_valida(
        st.session_state.get("wizard_etapa_atual", "origem")
    )
    st.session_state["wizard_etapa_maxima"] = _wizard_maximo(
        _etapa_valida(st.session_state.get("wizard_etapa_maxima", "origem")),
        st.session_state["wizard_etapa_atual"],
    )


def _atualizar_etapa_maxima_por_progresso() -> None:
    if _flow_lock_preview_ativo():
        _ativar_flow_lock_preview_final(origem="atualizar_etapa_maxima")
        return

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

    st.markdown("### Etapas")
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
    if _flow_lock_preview_ativo():
        _ativar_flow_lock_preview_final(origem="render_etapa_atual")

    etapa = _etapa_valida(st.session_state.get("wizard_etapa_atual", "origem"))
    etapa_logada = str(st.session_state.get("_ultima_etapa_logada_render", "") or "").strip()

    if st.session_state.get("ultima_etapa_renderizada", "") != etapa:
        st.session_state["ultima_etapa_renderizada"] = etapa

    if etapa_logada != etapa:
        log_debug(f"Renderizando etapa: {etapa}")
        st.session_state["_ultima_etapa_logada_render"] = etapa

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
        st.session_state["_ultima_etapa_logada_render"] = "origem"
        render_origem_dados()


def _render_header() -> None:
    st.title("🚀 IA Planilhas → Bling")
    st.caption("Fluxo limpo: origem → precificação → mapeamento → preview final")


def _render_resumo_topo() -> None:
    df_origem = st.session_state.get("df_origem")
    df_precificado = st.session_state.get("df_precificado")
    df_final = st.session_state.get("df_final")
    etapa = _etapa_valida(st.session_state.get("wizard_etapa_atual", "origem")).replace("_", " ").title()

    c1, c2, c3, c4 = st.columns([1, 1, 1, 1.2])
    with c1:
        st.metric("Origem", _contar_linhas_df(df_origem))
    with c2:
        st.metric("Precificado", _contar_linhas_df(df_precificado))
    with c3:
        st.metric("Final", _contar_linhas_df(df_final))
    with c4:
        st.metric("Etapa", etapa)


def _render_atalhos_tecnicos() -> None:
    with st.expander("Opções técnicas", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            render_botao_download_logs(
                key_sufixo="app_topo",
                label="📥 Baixar log debug",
            )

        with col2:
            mostrar = bool(st.session_state.get("mostrar_log_debug_ui", False))
            if st.button(
                "Mostrar/ocultar log",
                use_container_width=True,
                key="btn_toggle_log_debug_app",
            ):
                st.session_state["mostrar_log_debug_ui"] = not mostrar
                st.rerun()

        if st.session_state.get("mostrar_log_debug_ui", False):
            render_log_debug(modo="compacto")


def _render_layout_principal() -> None:
    _render_header()
    _render_resumo_topo()
    st.markdown("---")
    _render_navegacao_travada()
    st.markdown("---")
    _render_etapa_atual()
    st.markdown("---")
    _render_atalhos_tecnicos()


def main() -> None:
    st.set_page_config(
        page_title="IA Planilhas → Bling",
        page_icon="🚀",
        layout="wide",
    )

    init_app()
    _inicializar_estado_global()

    # Primeiro sincroniza a URL normalmente.
    sincronizar_etapa_da_url()

    # Depois o FLOW LOCK corrige qualquer tentativa automática de sair do preview.
    if _flow_lock_preview_ativo():
        _ativar_flow_lock_preview_final(origem="main_inicio")

    _sincronizar_wizard_com_estado()
    _atualizar_etapa_maxima_por_progresso()

    if _flow_lock_preview_ativo():
        _ativar_flow_lock_preview_final(origem="main_pos_sync")

    _processar_callback_bling()
    _registrar_boot_log()
    _render_layout_principal()


if __name__ == "__main__":
    main()
