from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import log_debug
from bling_app_zero.ui.origem_dados_estado import (
    controlar_troca_operacao,
    controlar_troca_origem,
    garantir_estado_origem,
    safe_df_dados,
    safe_df_estrutura,
    set_etapa_origem,
    sincronizar_estado_com_origem,
)
from bling_app_zero.ui.origem_dados_precificacao import render_precificacao
from bling_app_zero.ui.origem_dados_uploads import (
    render_modelo_bling,
    render_origem_entrada,
)
from bling_app_zero.ui.origem_dados_validacao import (
    obter_modelo_ativo,
    validar_antes_mapeamento,
)
from bling_app_zero.ui.origem_saida import obter_df_base_prioritaria


WIZARD_STEPS = {
    "operacao",
    "origem",
    "modelo",
    "configuracoes",
    "revisao",
}


def _obter_origem_atual() -> str:
    try:
        for key in ["origem_dados", "origem_selecionada", "tipo_origem", "origem"]:
            val = str(st.session_state.get(key) or "").strip().lower()
            if val:
                return val
        return ""
    except Exception:
        return ""


def _modelo_tem_estrutura(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0
    except Exception:
        return False


def _normalizar_quantidade(valor, fallback: int) -> int:
    try:
        texto = str(valor or "").strip().lower()
        if texto in {"", "nan", "none"}:
            return int(fallback)
        if texto in {"sem estoque", "indisponível", "indisponivel", "zerado"}:
            return 0
        numero = int(float(str(valor).replace(",", ".")))
        return max(numero, 0)
    except Exception:
        return int(fallback)


def _sincronizar_tipo_operacao(operacao: str) -> None:
    try:
        controlar_troca_operacao(operacao, log_debug)
    except Exception:
        pass

    st.session_state["tipo_operacao_bling"] = (
        "cadastro" if operacao == "Cadastro de Produtos" else "estoque"
    )


def _garantir_coluna(df: pd.DataFrame, nome: str, valor_padrao="") -> pd.DataFrame:
    try:
        if nome not in df.columns:
            df[nome] = valor_padrao
        return df
    except Exception:
        return df


def _aplicar_bloco_estoque(df_saida: pd.DataFrame, origem_atual: str) -> pd.DataFrame:
    try:
        df_saida = df_saida.copy()

        st.markdown("#### Dados de estoque")

        deposito = st.text_input(
            "Nome do depósito",
            value=str(st.session_state.get("deposito_nome", "") or ""),
            key="deposito_nome",
            placeholder="Ex.: ifood",
        )

        qtd = st.number_input(
            "Quantidade padrão",
            min_value=0,
            value=int(st.session_state.get("quantidade_fallback", 0) or 0),
            step=1,
            key="quantidade_fallback",
            help="Usado como fallback quando não houver quantidade válida.",
        )

        if deposito:
            df_saida = _garantir_coluna(df_saida, "Depósito", "")
            df_saida["Depósito"] = deposito

        df_saida = _garantir_coluna(df_saida, "Quantidade", qtd)

        if "site" in origem_atual:
            df_saida["Quantidade"] = df_saida["Quantidade"].apply(
                lambda v: _normalizar_quantidade(v, qtd)
            )
        else:
            df_saida["Quantidade"] = df_saida["Quantidade"].fillna(qtd)

        return df_saida
    except Exception as e:
        log_debug(f"[ORIGEM_DADOS] erro bloco estoque: {e}", "ERROR")
        return df_saida


def _obter_wizard_step() -> str:
    try:
        step = str(st.session_state.get("wizard_origem_step") or "operacao").strip().lower()
    except Exception:
        step = "operacao"

    if step not in WIZARD_STEPS:
        return "operacao"
    return step


def _set_wizard_step(step: str) -> None:
    step = str(step or "").strip().lower()
    if step not in WIZARD_STEPS:
        step = "operacao"
    st.session_state["wizard_origem_step"] = step


def _reset_precificacao_se_desativada() -> None:
    try:
        usar = bool(st.session_state.get("usar_calculadora_precificacao", False))
        if usar:
            return

        for chave in [
            "df_calc_precificado",
            "df_precificado",
            "coluna_preco_unitario_origem",
            "coluna_preco_unitario_destino",
        ]:
            if chave in st.session_state:
                del st.session_state[chave]
    except Exception:
        pass


def _render_topo_etapa(titulo: str, descricao: str, numero: int) -> None:
    st.title("IA Planilhas → Bling")
    st.caption(f"Etapa {numero} de 5")
    st.subheader(titulo)
    st.caption(descricao)
    st.markdown("---")


def _render_botoes_navegacao(
    voltar_para: str | None,
    continuar_para: str | None,
    continuar_label: str = "Continuar",
    continuar_tipo: str = "primary",
    bloquear_continuar: bool = False,
    on_before_continue=None,
    on_before_back=None,
) -> None:
    if voltar_para and continuar_para:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("⬅️ Voltar", use_container_width=True):
                if callable(on_before_back):
                    on_before_back()
                _set_wizard_step(voltar_para)
                st.rerun()
        with col2:
            if st.button(
                continuar_label,
                use_container_width=True,
                type=continuar_tipo,
                disabled=bloquear_continuar,
            ):
                if callable(on_before_continue):
                    on_before_continue()
                _set_wizard_step(continuar_para)
                st.rerun()
        return

    if continuar_para:
        if st.button(
            continuar_label,
            use_container_width=True,
            type=continuar_tipo,
            disabled=bloquear_continuar,
        ):
            if callable(on_before_continue):
                on_before_continue()
            _set_wizard_step(continuar_para)
            st.rerun()
        return

    if voltar_para:
        if st.button("⬅️ Voltar", use_container_width=True):
            if callable(on_before_back):
                on_before_back()
            _set_wizard_step(voltar_para)
            st.rerun()


def _preparar_df_saida_base(df_origem: pd.DataFrame, origem_atual: str) -> pd.DataFrame:
    df_saida = obter_df_base_prioritaria(df_origem, origem_atual)

    if st.session_state.get("tipo_operacao_bling") == "estoque":
        df_saida = _aplicar_bloco_estoque(df_saida, origem_atual)

    st.session_state["df_saida"] = df_saida.copy()
    st.session_state["df_final"] = df_saida.copy()
    return df_saida


def _voltar_para_home() -> None:
    st.session_state["_home_fluxo_iniciado"] = False
    st.session_state["wizard_origem_step"] = "operacao"
    set_etapa_origem("origem")


def render_origem_dados() -> None:
    garantir_estado_origem()

    etapa = str(st.session_state.get("etapa_origem", "origem") or "origem").strip().lower()
    if etapa == "mapeamento":
        return

    step = _obter_wizard_step()
    origem_atual = _obter_origem_atual()
    df_origem_atual = st.session_state.get("df_origem")

    # ======================================================
    # PASSO 1 — OPERAÇÃO
    # ======================================================
    if step == "operacao":
        _render_topo_etapa(
            "O que você quer fazer?",
            "Escolha se você quer cadastrar produto ou atualizar o estoque.",
            1,
        )

        operacao_atual = str(
            st.session_state.get("tipo_operacao") or "Cadastro de Produtos"
        ).strip()

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Cadastro de Produtos", use_container_width=True):
                operacao_atual = "Cadastro de Produtos"
                st.session_state["tipo_operacao"] = operacao_atual
                _sincronizar_tipo_operacao(operacao_atual)

        with col2:
            if st.button("Atualização de Estoque", use_container_width=True):
                operacao_atual = "Atualização de Estoque"
                st.session_state["tipo_operacao"] = operacao_atual
                _sincronizar_tipo_operacao(operacao_atual)

        if operacao_atual not in {"Cadastro de Produtos", "Atualização de Estoque"}:
            operacao_atual = "Cadastro de Produtos"
            st.session_state["tipo_operacao"] = operacao_atual
            _sincronizar_tipo_operacao(operacao_atual)

        st.info(f"Fluxo selecionado: **{operacao_atual}**")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("⟵ Início", use_container_width=True):
                _voltar_para_home()
                st.rerun()
        with col2:
            if st.button("Continuar", use_container_width=True, type="primary"):
                _sincronizar_tipo_operacao(operacao_atual)
                _set_wizard_step("origem")
                st.rerun()
        return

    # ======================================================
    # PASSO 2 — ORIGEM
    # ======================================================
    if step == "origem":
        _render_topo_etapa(
            "De onde virão os dados?",
            "Escolha a origem e carregue os dados antes de seguir.",
            2,
        )

        df_origem = render_origem_entrada(
            lambda origem: controlar_troca_origem(origem, log_debug)
        )

        origem_atual = _obter_origem_atual()

        if safe_df_dados(df_origem):
            try:
                st.session_state["df_origem"] = df_origem.copy()
            except Exception:
                st.session_state["df_origem"] = df_origem

            sincronizar_estado_com_origem(df_origem, log_debug)

            st.success("Origem carregada com sucesso.")
            try:
                st.dataframe(df_origem.head(3), use_container_width=True, height=180)
            except Exception:
                pass

        elif "site" in origem_atual and not st.session_state.get("site_processado"):
            st.info("Execute a busca do site para continuar.")
        else:
            st.info("Selecione a origem e carregue os dados para continuar.")

        _render_botoes_navegacao(
            voltar_para="operacao",
            continuar_para="modelo",
            bloquear_continuar=not safe_df_dados(st.session_state.get("df_origem")),
        )
        return

    # segurança
    if not safe_df_dados(df_origem_atual):
        _set_wizard_step("origem")
        st.rerun()
        return

    # ======================================================
    # PASSO 3 — MODELO
    # ======================================================
    if step == "modelo":
        operacao = str(st.session_state.get("tipo_operacao") or "Cadastro de Produtos")
        _sincronizar_tipo_operacao(operacao)

        _render_topo_etapa(
            "Qual modelo será usado?",
            "O sistema aplica automaticamente o modelo do Bling para o fluxo escolhido.",
            3,
        )

        render_modelo_bling(operacao)

        modelo_ativo = obter_modelo_ativo()
        modelo_ok = _modelo_tem_estrutura(modelo_ativo)

        if modelo_ok:
            st.success("Modelo identificado com sucesso.")
            try:
                st.dataframe(modelo_ativo.head(3), use_container_width=True, height=180)
            except Exception:
                pass
        else:
            st.warning("⚠️ Modelo do Bling não encontrado.")

        st.caption(
            "A seleção das colunas do modelo será feita no mapeamento, sem poluir esta etapa."
        )

        _render_botoes_navegacao(
            voltar_para="origem",
            continuar_para="configuracoes",
            bloquear_continuar=not modelo_ok,
        )
        return

    # ======================================================
    # PASSO 4 — CONFIGURAÇÕES
    # ======================================================
    if step == "configuracoes":
        _render_topo_etapa(
            "Configurações do fluxo",
            "Defina só o necessário antes do mapeamento.",
            4,
        )

        modelo_ativo = obter_modelo_ativo()
        if not _modelo_tem_estrutura(modelo_ativo):
            st.warning("⚠️ Modelo do Bling não encontrado.")
            _render_botoes_navegacao(
                voltar_para="modelo",
                continuar_para=None,
            )
            return

        _preparar_df_saida_base(df_origem_atual, origem_atual)

        usar_calculadora = st.radio(
            "Vai usar a calculadora de precificação?",
            options=["Não", "Sim"],
            index=1 if bool(st.session_state.get("usar_calculadora_precificacao", False)) else 0,
            horizontal=True,
            key="usar_calculadora_precificacao_radio",
        )

        st.session_state["usar_calculadora_precificacao"] = usar_calculadora == "Sim"

        if st.session_state.get("usar_calculadora_precificacao", False):
            st.markdown("#### Precificação")
            render_precificacao(df_origem_atual)

            df_prec = st.session_state.get("df_calc_precificado")
            if safe_df_estrutura(df_prec):
                try:
                    st.session_state["df_precificado"] = df_prec.copy()
                except Exception:
                    st.session_state["df_precificado"] = df_prec

            col_auto = str(
                st.session_state.get("coluna_preco_unitario_destino")
                or st.session_state.get("coluna_preco_unitario_origem")
                or ""
            ).strip()

            if col_auto:
                st.success(f"Coluna marcada como precificada automaticamente: **{col_auto}**")
            else:
                st.info(
                    "A calculadora foi aplicada, mas sem coluna automática válida. "
                    "Nesse caso, o mapeamento seguirá manualmente."
                )
        else:
            _reset_precificacao_se_desativada()
            st.info("Sem calculadora: o mapeamento seguirá com as colunas originais.")

        _render_botoes_navegacao(
            voltar_para="modelo",
            continuar_para="revisao",
        )
        return

    # ======================================================
    # PASSO 5 — REVISÃO
    # ======================================================
    if step == "revisao":
        _render_topo_etapa(
            "Revisão rápida",
            "Confira o básico e siga para o mapeamento.",
            5,
        )

        df_saida = _preparar_df_saida_base(df_origem_atual, origem_atual)

        try:
            st.dataframe(df_saida.head(5), use_container_width=True, height=220)
        except Exception:
            pass

        if st.session_state.get("usar_calculadora_precificacao", False):
            col_auto = str(
                st.session_state.get("coluna_preco_unitario_destino")
                or st.session_state.get("coluna_preco_unitario_origem")
                or ""
            ).strip()
            if col_auto:
                st.success(f"Precificação automática pronta com a coluna **{col_auto}**.")
            else:
                st.info("Precificação ligada, mas sem coluna automática válida.")
        else:
            st.info("Precificação manual: o mapeamento seguirá com as colunas originais.")

        valido, erros = validar_antes_mapeamento()
        if not valido:
            for erro in erros:
                st.warning(erro)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("⬅️ Voltar", use_container_width=True):
                _set_wizard_step("configuracoes")
                st.rerun()
        with col2:
            if st.button(
                "Ir para mapeamento",
                use_container_width=True,
                type="primary",
                disabled=not valido,
            ):
                if safe_df_estrutura(st.session_state.get("df_saida")):
                    try:
                        st.session_state["df_final"] = st.session_state["df_saida"].copy()
                    except Exception:
                        st.session_state["df_final"] = st.session_state["df_saida"]

                set_etapa_origem("mapeamento")
                st.rerun()
        return

    _set_wizard_step("operacao")
    st.rerun()
