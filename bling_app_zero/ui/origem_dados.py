
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
    controlar_troca_origem,
    modelo_tem_estrutura,
    obter_df_base_prioritaria,
    obter_modelo_ativo,
    sincronizar_estado_com_origem,
)
from bling_app_zero.ui.origem_dados_ui import (
    render_modelo_bling,
    render_origem_entrada,
    render_entrada_origem_selecionada,
    render_preview_origem,
)

NavCallback = Callable[[], None] | None


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


def _reset_fluxo_origem() -> None:
    for chave in [
        "tipo_operacao",
        "tipo_operacao_bling",
        "tipo_operacao_radio",
        "origem_dados_tipo",
        "origem_dados_radio",
        "df_origem",
        "df_saida",
        "df_final",
        "df_precificado",
        "df_calc_precificado",
        "site_url",
        "site_processado",
        "site_autoavanco_realizado",
        "fluxo_origem_passo",
        "_origem_dados_tipo_anterior",
        "upload_origem_dados",
    ]:
        st.session_state.pop(chave, None)


def _definir_passo_origem(passo: int) -> None:
    st.session_state["fluxo_origem_passo"] = int(passo)


def _obter_passo_origem() -> int:
    try:
        return int(st.session_state.get("fluxo_origem_passo", 1) or 1)
    except Exception:
        return 1


def _render_css_local() -> None:
    st.markdown(
        """
        <style>
            .od-kicker {
                font-size: 0.84rem;
                color: #667085;
                font-weight: 700;
                margin-bottom: 0.30rem;
            }

            .od-title {
                font-size: 2rem;
                line-height: 1.05;
                color: #0A2259;
                font-weight: 800;
                margin: 0 0 0.40rem 0;
                letter-spacing: -0.02em;
            }

            .od-sub {
                font-size: 1rem;
                color: #667085;
                margin: 0 0 1rem 0;
            }

            .od-summary {
                background: #FFFFFF;
                border: 1px solid #EAECF0;
                border-radius: 20px;
                padding: 0.9rem 1rem;
                margin: 0.75rem 0 1rem 0;
            }

            .od-summary-line {
                font-size: 0.94rem;
                color: #344054;
                margin-bottom: 0.25rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_question(titulo: str, subtitulo: str, kicker: str = "Começo") -> None:
    st.markdown(f'<div class="od-kicker">{kicker}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="od-title">{titulo}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="od-sub">{subtitulo}</div>', unsafe_allow_html=True)


def _render_operacao_clickable() -> None:
    atual = safe_str(st.session_state.get("tipo_operacao_radio"))

    col1, col2 = st.columns(2, gap="small")

    with col1:
        if st.button(
            "📦 Cadastro de Produtos",
            use_container_width=True,
            key="btn_operacao_cadastro_origem",
            type="primary" if atual == "Cadastro de Produtos" else "secondary",
        ):
            atual = "Cadastro de Produtos"
            st.session_state["tipo_operacao_radio"] = atual
            sincronizar_tipo_operacao(atual)
            _definir_passo_origem(2)
            st.rerun()

    with col2:
        if st.button(
            "📊 Atualização de Estoque",
            use_container_width=True,
            key="btn_operacao_estoque_origem",
            type="primary" if atual == "Atualização de Estoque" else "secondary",
        ):
            atual = "Atualização de Estoque"
            st.session_state["tipo_operacao_radio"] = atual
            sincronizar_tipo_operacao(atual)
            _definir_passo_origem(2)
            st.rerun()


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
            <div class="od-summary-line"><strong>Operação:</strong> {operacao or "Não definida"}</div>
            <div class="od-summary-line"><strong>Origem:</strong> {origem or "Não definida"}</div>
            <div class="od-summary-line"><strong>Linhas carregadas:</strong> {linhas}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _origem_foi_escolhida() -> bool:
    origem_atual = safe_str(obter_origem_atual()).lower()
    origem_sessao = safe_str(st.session_state.get("origem_dados_tipo")).lower()
    return bool(origem_atual or origem_sessao)


def _render_entrada_somente_da_origem_escolhida() -> pd.DataFrame | None:
    origem_atual = safe_str(obter_origem_atual()).lower()
    origem_sessao = safe_str(st.session_state.get("origem_dados_tipo")).lower()
    origem_resolvida = origem_atual or origem_sessao

    return render_entrada_origem_selecionada(
        origem_resolvida,
        lambda origem: controlar_troca_origem(origem, log_debug),
    )


def _deve_exibir_deposito() -> bool:
    return safe_str(st.session_state.get("tipo_operacao_bling")).lower() == "estoque"


def _resolve_operacao_label() -> str:
    return safe_str(
        st.session_state.get("tipo_operacao_radio")
        or st.session_state.get("tipo_operacao")
        or st.session_state.get("tipo_operacao_bling")
    )


def _persistir_df_saida(df_saida: pd.DataFrame) -> None:
    try:
        st.session_state["df_saida"] = df_saida.copy()
    except Exception:
        st.session_state["df_saida"] = df_saida

    try:
        st.session_state["df_final"] = df_saida.copy()
    except Exception:
        st.session_state["df_final"] = df_saida


def render_origem_dados(
    on_back: NavCallback = None,
    on_continue: NavCallback = None,
) -> None:
    garantir_estado_origem()
    _render_css_local()

    if "fluxo_origem_passo" not in st.session_state:
        _definir_passo_origem(1)

    passo = _obter_passo_origem()

    if passo <= 1:
        _render_question(
            "O que você quer fazer?",
            "Toque em uma opção grande para continuar.",
            kicker="Começo",
        )
        _render_operacao_clickable()
        return

    operacao = _resolve_operacao_label()
    if not operacao:
        _definir_passo_origem(1)
        st.rerun()
        return

    if passo == 2:
        _render_question(
            "De onde virão os dados?",
            "Escolha a origem para liberar a próxima etapa.",
            kicker="Pergunta 2",
        )

        render_origem_entrada(
            lambda origem: controlar_troca_origem(origem, log_debug)
        )

        if _origem_foi_escolhida():
            _definir_passo_origem(3)
            st.rerun()

        if st.button(
            "⬅️ Voltar",
            use_container_width=True,
            key="origem_btn_voltar_passo_2",
        ):
            for chave in [
                "origem_dados_tipo",
                "origem_dados_radio",
                "df_origem",
                "df_saida",
                "df_final",
                "df_precificado",
                "df_calc_precificado",
                "upload_origem_dados",
            ]:
                st.session_state.pop(chave, None)
            _definir_passo_origem(1)
            st.rerun()

        return

    _render_question(
        "Carregue uma base",
        "Agora complete somente a origem escolhida.",
        kicker="Pergunta 3",
    )

    if _deve_exibir_deposito():
        st.text_input(
            "Nome do depósito",
            key="deposito_nome",
            placeholder="Ex: Depósito principal",
        )

    df_origem_render = _render_entrada_somente_da_origem_escolhida()
    df_origem = _obter_df_origem_renderizado(df_origem_render)

    origem_atual = safe_str(obter_origem_atual()).lower()

    if "site" in origem_atual and safe_df_dados(df_origem):
        st.session_state["site_processado"] = True

    _render_resumo_curto(df_origem)

    if not safe_df_dados(df_origem):
        col1, col2 = st.columns(2, gap="small")

        with col1:
            if st.button(
                "⬅️ Voltar",
                use_container_width=True,
                key="origem_btn_voltar_final",
            ):
                for chave in [
                    "df_origem",
                    "df_saida",
                    "df_final",
                    "df_precificado",
                    "df_calc_precificado",
                    "upload_origem_dados",
                ]:
                    st.session_state.pop(chave, None)
                _definir_passo_origem(2)
                st.rerun()

        with col2:
            st.button(
                "Continuar ➜",
                use_container_width=True,
                disabled=True,
                key="origem_btn_continuar_final_disabled",
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
        st.warning("O modelo do sistema não foi encontrado.")
        return

    with st.expander("Ver modelo ativo", expanded=False):
        render_modelo_bling(operacao)

    df_saida = obter_df_base_prioritaria(df_origem)

    if _deve_exibir_deposito():
        df_saida = aplicar_bloco_estoque(df_saida, origem_atual)

    _persistir_df_saida(df_saida)

    with st.expander("Abrir preview da origem", expanded=False):
        render_preview_origem(df_origem)

    col1, col2 = st.columns(2, gap="small")

    with col1:
        if st.button(
            "⬅️ Voltar",
            use_container_width=True,
            key="origem_btn_voltar_base_carregada",
        ):
            for chave in [
                "df_origem",
                "df_saida",
                "df_final",
                "df_precificado",
                "df_calc_precificado",
                "upload_origem_dados",
            ]:
                st.session_state.pop(chave, None)
            _definir_passo_origem(2)
            st.rerun()

    with col2:
        if st.button(
            "Continuar ➜",
            use_container_width=True,
            type="primary",
            key="origem_btn_continuar_para_precificacao",
        ):
            _navegar("precificacao", on_continue)
            
