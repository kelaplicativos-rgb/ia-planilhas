from __future__ import annotations

from collections.abc import Callable

import streamlit as st

from bling_app_zero.ui.app_helpers import log_debug, safe_df_dados, safe_df_estrutura
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
    render_header_fluxo,
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


def _render_botoes_origem(
    on_back: NavCallback = None,
    on_continue: NavCallback = None,
    *,
    mostrar_continuar: bool,
    continuar_habilitado: bool,
) -> None:
    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "⬅️ Voltar para conexão",
            use_container_width=True,
            key=f"origem_btn_voltar_{'ok' if mostrar_continuar else 'base'}",
        ):
            _navegar("conexao", on_back)

    with col2:
        if mostrar_continuar:
            if st.button(
                "➡️ Continuar para mapeamento",
                use_container_width=True,
                type="primary",
                disabled=not continuar_habilitado,
                key=f"origem_btn_continuar_{'ok' if continuar_habilitado else 'bloq'}",
            ):
                valido, erros = validar_antes_mapeamento()

                if not valido:
                    for erro in erros:
                        st.warning(erro)
                    return

                if safe_df_estrutura(st.session_state.get("df_saida")):
                    st.session_state["df_final"] = st.session_state["df_saida"].copy()

                _navegar("mapeamento", on_continue)
        else:
            st.caption("Carregue a origem para liberar o próximo passo.")


def render_origem_dados(
    on_back: NavCallback = None,
    on_continue: NavCallback = None,
) -> None:
    garantir_estado_origem()
    render_header_fluxo()

    col_topo_1, col_topo_2 = st.columns(2)

    with col_topo_1:
        if st.button("⬅️ Voltar para conexão", use_container_width=True, key="origem_btn_voltar_conexao_topo"):
            _navegar("conexao", on_back)

    with col_topo_2:
        st.caption("Fluxo atual: conexão → origem → mapeamento → final → envio")

    etapa = safe_str(st.session_state.get("etapa_origem", "origem") or "origem").lower()
    if etapa != "origem":
        set_etapa_origem("origem")

    labels_operacao = ["Cadastro de Produtos", "Atualização de Estoque"]
    valor_radio = safe_str(st.session_state.get("tipo_operacao_radio"))

    if valor_radio not in labels_operacao:
        st.session_state["tipo_operacao_radio"] = "Cadastro de Produtos"
        valor_radio = "Cadastro de Produtos"

    operacao = st.radio(
        "Você quer cadastrar produto ou atualizar o estoque?",
        labels_operacao,
        key="tipo_operacao_radio",
        horizontal=True,
        index=labels_operacao.index(valor_radio),
    )

    sincronizar_tipo_operacao(operacao)

    if st.session_state.get("tipo_operacao_bling") == "estoque":
        st.text_input(
            "Nome do depósito",
            key="deposito_nome",
            placeholder="Ex: Depósito principal",
            help="Este valor será propagado para a base de estoque quando necessário.",
        )

    st.markdown("---")

    df_origem = render_origem_entrada(
        lambda origem: controlar_troca_origem(origem, log_debug)
    )

    origem_atual = obter_origem_atual()

    if (
        "site" in origem_atual
        and not st.session_state.get("site_processado")
        and not safe_df_dados(df_origem)
    ):
        st.info("Configure o site e execute a busca para continuar.")
        st.markdown("---")
        _render_botoes_origem(
            on_back=on_back,
            on_continue=on_continue,
            mostrar_continuar=False,
            continuar_habilitado=False,
        )
        return

    if not safe_df_dados(df_origem):
        st.info("Selecione a origem e carregue os dados para continuar.")
        st.markdown("---")
        _render_botoes_origem(
            on_back=on_back,
            on_continue=on_continue,
            mostrar_continuar=False,
            continuar_habilitado=False,
        )
        return

    df_origem = aplicar_normalizacao_basica(df_origem)
    st.session_state["df_origem"] = df_origem.copy()
    sincronizar_estado_com_origem(df_origem, log_debug)

    st.markdown("---")
    render_modelo_bling(operacao)

    modelo_ativo = obter_modelo_ativo()
    if modelo_ativo is not None and not modelo_tem_estrutura(modelo_ativo):
        st.warning("⚠️ Modelo do Bling não encontrado.")
        st.markdown("---")
        _render_botoes_origem(
            on_back=on_back,
            on_continue=on_continue,
            mostrar_continuar=False,
            continuar_habilitado=False,
        )
        return

    df_saida = obter_df_base_prioritaria(df_origem)

    if st.session_state.get("tipo_operacao_bling") == "estoque":
        df_saida = aplicar_bloco_estoque(df_saida, origem_atual)

    st.session_state["df_saida"] = df_saida.copy()
    st.session_state["df_final"] = df_saida.copy()

    render_preview_origem(df_origem)

    st.markdown("---")
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

        st.session_state["df_saida"] = df_saida_prec.copy()
        st.session_state["df_final"] = df_saida_prec.copy()

    st.markdown("---")
    _render_botoes_origem(
        on_back=on_back,
        on_continue=on_continue,
        mostrar_continuar=True,
        continuar_habilitado=True,
    )
    
