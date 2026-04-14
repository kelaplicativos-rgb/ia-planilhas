from __future__ import annotations

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


def render_origem_dados() -> None:
    garantir_estado_origem()
    render_header_fluxo()

    etapa = safe_str(st.session_state.get("etapa_origem", "origem") or "origem").lower()

    if etapa == "mapeamento":
        if st.button("⬅️ Voltar para origem", use_container_width=True):
            set_etapa_origem("origem")
            st.rerun()
        return

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
        return

    if not safe_df_dados(df_origem):
        st.info("Selecione a origem e carregue os dados para continuar.")
        return

    df_origem = aplicar_normalizacao_basica(df_origem)
    st.session_state["df_origem"] = df_origem.copy()
    sincronizar_estado_com_origem(df_origem, log_debug)

    st.markdown("---")
    render_modelo_bling(operacao)

    modelo_ativo = obter_modelo_ativo()
    if modelo_ativo is not None and not modelo_tem_estrutura(modelo_ativo):
        st.warning("⚠️ Modelo do Bling não encontrado.")
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
        margem=float(st.session_state.get("margem_bling", 0.0) or 0.0),
        impostos=float(st.session_state.get("impostos_bling", 0.0) or 0.0),
        custo_fixo=float(st.session_state.get("custofixo_bling", 0.0) or 0.0),
        taxa_extra=float(st.session_state.get("taxaextra_bling", 0.0) or 0.0),
    )

    if safe_df_estrutura(df_prec):
        df_saida_prec = df_prec.copy()

        if st.session_state.get("tipo_operacao_bling") == "estoque":
            df_saida_prec = aplicar_bloco_estoque(df_saida_prec, origem_atual)

        st.session_state["df_saida"] = df_saida_prec.copy()
        st.session_state["df_final"] = df_saida_prec.copy()

    st.markdown("---")

    if st.button("➡️ Continuar para mapeamento", use_container_width=True, type="primary"):
        valido, erros = validar_antes_mapeamento()

        if not valido:
            for erro in erros:
                st.warning(erro)
            return

        if safe_df_estrutura(st.session_state.get("df_saida")):
            st.session_state["df_final"] = st.session_state["df_saida"].copy()

        set_etapa_origem("mapeamento")
        st.rerun()
