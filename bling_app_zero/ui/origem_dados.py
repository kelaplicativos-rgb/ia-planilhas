

from __future__ import annotations

from collections.abc import Callable

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import (
    log_debug,
    safe_df_dados,
    safe_df_estrutura,
)
from bling_app_zero.ui.origem_dados_estado import (
    garantir_estado_origem,
    obter_origem_atual,
    safe_str,
    set_etapa_origem,
    sincronizar_tipo_operacao,
)
from bling_app_zero.ui.origem_dados_handlers import (
    aplicar_bloco_estoque,
    aplicar_normalizacao_basica,
    aplicar_precificacao,
    controlar_troca_origem,
    modelo_tem_estrutura,
    obter_df_base_prioritaria,
    obter_modelo_ativo,
    sincronizar_estado_com_origem,
    validar_antes_mapeamento,
)
from bling_app_zero.ui.origem_dados_ui import (
    render_modelo_bling,
    render_origem_entrada,
    render_precificacao,
    render_preview_origem,
)

NavCallback = Callable[[], None] | None


def _float_session(key: str, default: float = 0.0) -> float:
    try:
        return float(st.session_state.get(key, default) or default)
    except Exception:
        return default


def _navegar(destino: str, callback: NavCallback = None) -> None:
    if callable(callback):
        callback()
        return
    set_etapa_origem(destino)
    st.rerun()


def _resolver_df_origem_site() -> pd.DataFrame | None:
    candidatos = [
        "df_origem",
        "df_saida",
        "df_final",
        "df_precificado",
        "df_calc_precificado",
    ]

    for chave in candidatos:
        df = st.session_state.get(chave)
        if safe_df_dados(df):
            try:
                df_resolvido = df.copy()
            except Exception:
                df_resolvido = df

            if chave != "df_origem":
                try:
                    st.session_state["df_origem"] = df_resolvido.copy()
                except Exception:
                    st.session_state["df_origem"] = df_resolvido

            st.session_state["site_processado"] = True
            return df_resolvido

    return None


def _obter_df_origem_renderizado(df_origem_render: pd.DataFrame | None) -> pd.DataFrame | None:
    origem_atual = safe_str(obter_origem_atual()).lower()

    if safe_df_dados(df_origem_render):
        return df_origem_render

    if "site" in origem_atual:
        return _resolver_df_origem_site()

    return df_origem_render


def _site_configurada_minimamente() -> bool:
    origem_atual = safe_str(obter_origem_atual()).lower()
    if "site" not in origem_atual:
        return False

    url = safe_str(st.session_state.get("site_url")).strip()
    return bool(url)


def _render_mobile_css() -> None:
    st.markdown(
        """
        <style>
            .od-card {
                background: #F5F7FA;
                border: 1px solid #EAECF0;
                border-radius: 28px;
                padding: 1rem;
                margin-bottom: 1rem;
            }

            .od-kicker {
                font-size: 0.82rem;
                color: #667085;
                font-weight: 700;
                margin-bottom: 0.35rem;
            }

            .od-title {
                font-size: 1.6rem;
                line-height: 1.1;
                color: #0A2259;
                font-weight: 800;
                margin: 0 0 0.25rem 0;
                letter-spacing: -0.02em;
            }

            .od-sub {
                font-size: 0.96rem;
                color: #667085;
                margin: 0;
            }

            .od-mini {
                font-size: 0.86rem;
                color: #667085;
            }

            .od-summary {
                background: #FFFFFF;
                border: 1px solid #EAECF0;
                border-radius: 20px;
                padding: 0.9rem;
                margin-top: 0.75rem;
            }

            .od-summary strong {
                color: #0A2259;
            }

            .od-space {
                height: 8px;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_question_block(kicker: str, titulo: str, subtitulo: str) -> None:
    st.markdown(
        f"""
        <div class="od-card">
            <div class="od-kicker">{kicker}</div>
            <div class="od-title">{titulo}</div>
            <p class="od-sub">{subtitulo}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_resumo_curto(df_origem: pd.DataFrame | None = None) -> None:
    operacao = safe_str(
        st.session_state.get("tipo_operacao")
        or st.session_state.get("tipo_operacao_bling")
        or st.session_state.get("tipo_operacao_radio")
    ).strip()

    origem = safe_str(
        st.session_state.get("origem_dados_tipo")
        or st.session_state.get("origem_dados_radio")
        or obter_origem_atual()
    ).strip()

    linhas = 0
    if safe_df_dados(df_origem):
        try:
            linhas = int(len(df_origem))
        except Exception:
            linhas = 0

    st.markdown(
        f"""
        <div class="od-summary">
            <div class="od-mini"><strong>Operação:</strong> {operacao or "Não definida"}</div>
            <div class="od-mini"><strong>Origem:</strong> {origem or "Não definida"}</div>
            <div class="od-mini"><strong>Linhas carregadas:</strong> {linhas}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_botoes_origem(
    on_back: NavCallback = None,
    on_continue: NavCallback = None,
    *,
    continuar_habilitado: bool,
) -> None:
    col1, col2 = st.columns(2, gap="small")

    with col1:
        if st.button(
            "⬅️ Voltar",
            use_container_width=True,
            key="origem_btn_voltar_mobile",
        ):
            _navegar("origem", on_back)

    with col2:
        if st.button(
            "Continuar ➜",
            use_container_width=True,
            type="primary",
            disabled=not continuar_habilitado,
            key="origem_btn_continuar_mobile",
        ):
            valido, erros = validar_antes_mapeamento()
            if not valido:
                for erro in erros:
                    st.warning(erro)
                return

            if safe_df_estrutura(st.session_state.get("df_saida")):
                try:
                    st.session_state["df_final"] = st.session_state["df_saida"].copy()
                except Exception:
                    st.session_state["df_final"] = st.session_state["df_saida"]

            _navegar("mapeamento", on_continue)


def render_origem_dados(
    on_back: NavCallback = None,
    on_continue: NavCallback = None,
) -> None:
    garantir_estado_origem()
    _render_mobile_css()

    if "site_autoavanco_realizado" not in st.session_state:
        st.session_state["site_autoavanco_realizado"] = False

    labels_operacao = [
        "Cadastro de Produtos",
        "Atualização de Estoque",
    ]

    valor_radio = safe_str(st.session_state.get("tipo_operacao_radio"))
    if valor_radio not in labels_operacao:
        st.session_state["tipo_operacao_radio"] = "Cadastro de Produtos"
        valor_radio = "Cadastro de Produtos"

    _render_question_block(
        "Pergunta 1",
        "O que você quer fazer?",
        "Escolha só uma opção para seguir.",
    )

    operacao = st.radio(
        "Operação",
        labels_operacao,
        key="tipo_operacao_radio",
        horizontal=False,
        index=labels_operacao.index(valor_radio),
        label_visibility="collapsed",
    )
    sincronizar_tipo_operacao(operacao)

    if st.session_state.get("tipo_operacao_bling") == "estoque":
        st.text_input(
            "Nome do depósito",
            key="deposito_nome",
            placeholder="Ex: Depósito principal",
        )

    st.markdown('<div class="od-space"></div>', unsafe_allow_html=True)

    _render_question_block(
        "Pergunta 2",
        "De onde virão os dados?",
        "Selecione a origem e carregue a base.",
    )

    df_origem_render = render_origem_entrada(
        lambda origem: controlar_troca_origem(origem, log_debug)
    )
    df_origem = _obter_df_origem_renderizado(df_origem_render)

    origem_atual = safe_str(obter_origem_atual()).lower()

    if "site" in origem_atual and safe_df_dados(df_origem):
        st.session_state["site_processado"] = True

    _render_resumo_curto(df_origem)

    if "site" in origem_atual and not safe_df_dados(df_origem):
        if _site_configurada_minimamente():
            st.info("A URL já foi preenchida. Assim que os dados forem carregados, o sistema libera o próximo passo.")
        else:
            st.info("Informe a URL do site para continuar.")

    if not safe_df_dados(df_origem):
        st.markdown('<div class="od-space"></div>', unsafe_allow_html=True)
        _render_botoes_origem(
            on_back=on_back,
            on_continue=on_continue,
            continuar_habilitado=False,
        )
        return

    df_origem = aplicar_normalizacao_basica(df_origem)

    try:
        st.session_state["df_origem"] = df_origem.copy()
    except Exception:
        st.session_state["df_origem"] = df_origem

    sincronizar_estado_com_origem(df_origem, log_debug)

    modelo_ativo = obter_modelo_ativo()
    if modelo_ativo is None or not modelo_tem_estrutura(modelo_ativo):
        _render_question_block(
            "Modelo",
            "O modelo do sistema não foi encontrado",
            "Corrija isso antes de seguir.",
        )
        _render_botoes_origem(
            on_back=on_back,
            on_continue=on_continue,
            continuar_habilitado=False,
        )
        return

    _render_question_block(
        "Pergunta 3",
        "Quer revisar o modelo?",
        "Deixe fechado se não precisar mexer agora.",
    )
    with st.expander("Ver modelo ativo", expanded=False):
        render_modelo_bling(operacao)

    df_saida = obter_df_base_prioritaria(df_origem)

    if st.session_state.get("tipo_operacao_bling") == "estoque":
        df_saida = aplicar_bloco_estoque(df_saida, origem_atual)

    try:
        st.session_state["df_saida"] = df_saida.copy()
    except Exception:
        st.session_state["df_saida"] = df_saida

    try:
        st.session_state["df_final"] = df_saida.copy()
    except Exception:
        st.session_state["df_final"] = df_saida

    _render_question_block(
        "Pergunta 4",
        "Quer aplicar precificação?",
        "Use só se quiser gerar o preço automaticamente.",
    )

    with st.expander("Abrir precificação", expanded=False):
        render_precificacao(df_origem)

    df_prec = aplicar_precificacao(
        df_origem=df_origem,
        coluna_custo=safe_str(st.session_state.get("coluna_precificacao_resultado")),
        margem=_float_session("margem_bling"),
        impostos=_float_session("impostos_bling"),
        custo_fixo=_float_session("custofixo_bling"),
        taxa_extra=_float_session("taxaextra_bling"),
    )

    if safe_df_estrutura(df_prec):
        df_saida_prec = df_prec.copy()

        if st.session_state.get("tipo_operacao_bling") == "estoque":
            df_saida_prec = aplicar_bloco_estoque(df_saida_prec, origem_atual)

        try:
            st.session_state["df_saida"] = df_saida_prec.copy()
        except Exception:
            st.session_state["df_saida"] = df_saida_prec

        try:
            st.session_state["df_final"] = df_saida_prec.copy()
        except Exception:
            st.session_state["df_final"] = df_saida_prec

    _render_question_block(
        "Pergunta 5",
        "Quer ver um resumo da base?",
        "O preview fica recolhido para não poluir a tela.",
    )
    with st.expander("Abrir preview da origem", expanded=False):
        render_preview_origem(df_origem)

    st.markdown('<div class="od-space"></div>', unsafe_allow_html=True)

    _render_botoes_origem(
        on_back=on_back,
        on_continue=on_continue,
        continuar_habilitado=True,
    )

