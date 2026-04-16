
from __future__ import annotations

from typing import Any, Dict, List

import streamlit as st

from bling_app_zero.agent.agent_memory import get_agent_state
from bling_app_zero.core.ia_orchestrator import (
    executar_fluxo_gpt,
    limpar_fluxo_gpt,
    obter_plano_corrente,
    sincronizar_agent_memory_com_resultado,
)


# ============================================================
# HELPERS
# ============================================================

def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"none", "nan", "nat"}:
        return ""
    return text


def _map_origem_label_to_key(label: str) -> str:
    mapa = {
        "Buscar pelo site": "site",
        "Anexar planilha fornecedora": "planilha",
        "Importar XML": "xml",
        "Importar PDF": "pdf",
    }
    return mapa.get(label, "planilha")


def _map_origem_key_to_label(key: str) -> str:
    mapa = {
        "site": "Buscar pelo site",
        "planilha": "Anexar planilha fornecedora",
        "xml": "Importar XML",
        "pdf": "Importar PDF",
    }
    return mapa.get(key, "Anexar planilha fornecedora")


def _label_operacao_to_key(label: str) -> str:
    return "estoque" if "estoque" in _safe_str(label).lower() else "cadastro"


def _key_operacao_to_label(key: str) -> str:
    return "Atualização de estoque" if _safe_str(key).lower() == "estoque" else "Cadastro de produtos"


def _render_status_box(plan: Dict[str, Any]) -> None:
    status = _safe_str(plan.get("status")) or "idle"
    provider = _safe_str(plan.get("provider")) or "fallback"
    confidence = plan.get("confidence", 0.0)

    try:
        confidence_pct = f"{float(confidence) * 100:.0f}%"
    except Exception:
        confidence_pct = "0%"

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Status", status.replace("_", " ").title())
    with col2:
        st.metric("Motor", "GPT" if provider == "openai" else "Fallback")
    with col3:
        st.metric("Confiança", confidence_pct)


def _render_plan_summary(plan: Dict[str, Any]) -> None:
    operacao = _safe_str(plan.get("operacao")) or "cadastro"
    origem = _safe_str(plan.get("origem")) or "planilha"
    deposito = _safe_str(plan.get("deposito_nome"))
    fornecedor = _safe_str(plan.get("fornecedor"))
    url_site = _safe_str(plan.get("url_site"))

    with st.container(border=True):
        st.markdown("#### Leitura da IA")

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Operação", "Estoque" if operacao == "estoque" else "Cadastro")
        with col2:
            st.metric("Origem", origem.title())

        if fornecedor:
            st.caption(f"Fornecedor detectado: **{fornecedor}**")
        if deposito:
            st.caption(f"Depósito detectado: **{deposito}**")
        if url_site:
            st.caption(f"URL detectada: **{url_site}**")

        resumo = _safe_str(plan.get("resumo"))
        if resumo:
            st.info(resumo)

        proxima_pergunta = _safe_str(plan.get("proxima_pergunta"))
        if proxima_pergunta:
            st.warning(proxima_pergunta)


def _render_list_block(title: str, values: List[str], kind: str = "info") -> None:
    if not values:
        return

    with st.container(border=True):
        st.markdown(f"#### {title}")
        for item in values:
            text = _safe_str(item)
            if not text:
                continue
            if kind == "error":
                st.error(text)
            elif kind == "warning":
                st.warning(text)
            elif kind == "success":
                st.success(text)
            else:
                st.write(f"• {text}")


def _executar_ia() -> None:
    prompt = _safe_str(st.session_state.get("ia_prompt_home"))
    deposito_digitado = _safe_str(st.session_state.get("deposito_nome_input"))
    url_site = _safe_str(st.session_state.get("url_site_origem"))
    operacao_label = _safe_str(st.session_state.get("ia_operacao_radio"))
    origem_label = _safe_str(st.session_state.get("ia_origem_radio"))

    operacao_ui = _label_operacao_to_key(operacao_label)
    origem_ui = _map_origem_label_to_key(origem_label)

    executar_fluxo_gpt(
        prompt_usuario=prompt,
        operacao_ui=operacao_ui,
        origem_ui=origem_ui,
        deposito_nome_ui=deposito_digitado,
        url_site_ui=url_site,
    )
    sincronizar_agent_memory_com_resultado()


def _limpar() -> None:
    limpar_fluxo_gpt()


# ============================================================
# UI
# ============================================================

def render_ia_panel() -> None:
    state = get_agent_state()
    plan = obter_plano_corrente()

    st.markdown("### Origem dos dados")
    st.caption("Descreva o que deseja fazer. A IA interpreta o pedido e monta o próximo fluxo.")

    with st.container(border=True):
        st.markdown("#### Comando da IA")

        prompt_default = _safe_str(st.session_state.get("ia_prompt_home"))
        st.text_area(
            "Descreva o pedido",
            key="ia_prompt_home",
            height=160,
            placeholder=(
                "Ex.: Quero buscar os produtos do site Mega Center Eletrônicos "
                "para atualizar o estoque do depósito iFood."
            ),
            value=prompt_default if prompt_default else None,
        )

        st.text_input(
            "Nome do depósito",
            key="deposito_nome_input",
            placeholder="Ex.: iFood, CD Principal, Loja 1",
        )

    operacao_atual = _key_operacao_to_label(
        _safe_str(plan.get("operacao")) or _safe_str(state.operacao) or _safe_str(st.session_state.get("tipo_operacao")) or "cadastro"
    )
    origem_atual = _map_origem_key_to_label(
        _safe_str(plan.get("origem")) or _safe_str(state.origem_tipo) or _safe_str(st.session_state.get("origem_tipo")) or "planilha"
    )

    with st.container(border=True):
        st.markdown("#### Operação")
        st.radio(
            "Escolha a operação",
            options=["Cadastro de produtos", "Atualização de estoque"],
            index=0 if operacao_atual == "Cadastro de produtos" else 1,
            horizontal=False,
            key="ia_operacao_radio",
        )

    with st.container(border=True):
        st.markdown("#### Origem")
        origem_options = [
            "Buscar pelo site",
            "Anexar planilha fornecedora",
            "Importar XML",
            "Importar PDF",
        ]
        origem_index = origem_options.index(origem_atual) if origem_atual in origem_options else 1

        st.radio(
            "Como deseja iniciar?",
            options=origem_options,
            index=origem_index,
            horizontal=False,
            key="ia_origem_radio",
        )

        origem_key = _map_origem_label_to_key(_safe_str(st.session_state.get("ia_origem_radio")))
        if origem_key == "site":
            st.text_input(
                "URL do site ou categoria",
                key="url_site_origem",
                placeholder="https://fornecedor.com/categoria",
            )

    with st.container(border=True):
        col1, col2 = st.columns(2)

        with col1:
            st.button(
                "Executar com GPT",
                use_container_width=True,
                type="primary",
                on_click=_executar_ia,
            )

        with col2:
            st.button(
                "Limpar",
                use_container_width=True,
                on_click=_limpar,
            )

    plan = obter_plano_corrente()
    if plan:
        _render_status_box(plan)
        _render_plan_summary(plan)

        pendencias = plan.get("pendencias", [])
        if isinstance(pendencias, list):
            _render_list_block("Pendências", [str(item) for item in pendencias], kind="warning")

        proximas_acoes = plan.get("proximas_acoes", [])
        if isinstance(proximas_acoes, list):
            _render_list_block("Próximas ações", [str(item) for item in proximas_acoes], kind="info")

        avisos = plan.get("avisos", [])
        if isinstance(avisos, list):
            _render_list_block("Avisos", [str(item) for item in avisos], kind="warning")

        erros = plan.get("erros", [])
        if isinstance(erros, list):
            _render_list_block("Erros", [str(item) for item in erros], kind="error")

        if _safe_str(plan.get("status")) == "pronto_para_proximo_fluxo":
            st.success("Fluxo inicial montado. Pode seguir para a próxima etapa.")

    with st.expander("Debug do agente", expanded=False):
        st.json(
            {
                "agent_state": state.to_dict(),
                "agent_plan": plan,
                "session_tipo_operacao": st.session_state.get("tipo_operacao"),
                "session_origem_tipo": st.session_state.get("origem_tipo"),
                "session_fluxo_etapa": st.session_state.get("fluxo_etapa"),
            }
        )
