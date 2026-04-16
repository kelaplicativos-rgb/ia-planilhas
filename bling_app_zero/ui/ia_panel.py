
from __future__ import annotations

import re
from typing import Any, Dict

import streamlit as st


# ============================================================
# HELPERS
# ============================================================


def _normalizar_texto(valor: Any) -> str:
    if valor is None:
        return ""
    texto = str(valor).strip()
    if texto.lower() in {"nan", "none", "nat"}:
        return ""
    return texto


def _normalizar_busca(valor: Any) -> str:
    texto = _normalizar_texto(valor).lower()
    trocas = {
        "á": "a",
        "à": "a",
        "ã": "a",
        "â": "a",
        "é": "e",
        "ê": "e",
        "í": "i",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "ú": "u",
        "ç": "c",
    }
    for antigo, novo in trocas.items():
        texto = texto.replace(antigo, novo)
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def _detectar_operacao(prompt: str, operacao_ui: str) -> str:
    texto = _normalizar_busca(prompt)

    if "estoque" in texto or "saldo" in texto or "deposito" in texto:
        return "estoque"

    if "cadastro" in texto or "cadastrar" in texto:
        return "cadastro"

    return operacao_ui


def _detectar_origem(prompt: str, origem_ui: str, url_site: str) -> str:
    if _normalizar_texto(url_site):
        return "site"

    texto = _normalizar_busca(prompt)

    if "xml" in texto:
        return "xml"

    if "site" in texto or "buscar no site" in texto or "url" in texto:
        return "site"

    return origem_ui


def _extrair_deposito(prompt: str, deposito_digitado: str) -> str:
    if _normalizar_texto(deposito_digitado):
        return _normalizar_texto(deposito_digitado)

    texto = _normalizar_texto(prompt)
    match = re.search(
        r"(?:deposito|depósito)\s*[:=-]?\s*([A-Za-z0-9 _\-/]+)",
        texto,
        flags=re.IGNORECASE,
    )
    if match:
        return _normalizar_texto(match.group(1))

    return ""


def _montar_plano_inicial(
    prompt: str,
    operacao: str,
    origem_tipo: str,
    deposito_nome: str,
    url_site: str,
) -> Dict[str, Any]:
    proximas_acoes = []

    if origem_tipo == "site":
        proximas_acoes.extend(
            [
                "Abrir tela de modelo Bling",
                "Receber modelo da operação selecionada",
                "Executar coleta do site",
                "Preparar base para precificação",
            ]
        )
    elif origem_tipo == "xml":
        proximas_acoes.extend(
            [
                "Abrir tela de modelo Bling",
                "Receber XML e modelo Bling",
                "Normalizar base do XML",
                "Preparar base para mapeamento",
            ]
        )
    else:
        proximas_acoes.extend(
            [
                "Abrir tela de modelo Bling",
                "Receber planilha fornecedora e modelo Bling",
                "Normalizar colunas",
                "Preparar base para mapeamento",
            ]
        )

    return {
        "prompt_usuario": _normalizar_texto(prompt),
        "operacao": operacao,
        "origem": origem_tipo,
        "deposito": deposito_nome,
        "url_site": _normalizar_texto(url_site),
        "proximas_acoes": proximas_acoes,
    }


def _pode_avancar(prompt: str, url_site: str) -> bool:
    return bool(_normalizar_texto(prompt) or _normalizar_texto(url_site))


def _ir_para_proxima_etapa() -> None:
    st.session_state["fluxo_etapa"] = "modelo"
    st.rerun()


# ============================================================
# UI
# ============================================================


def render_ia_panel() -> None:
    st.markdown("### Origem dos dados")
    st.caption("Descreva o que deseja fazer e escolha como a IA deve iniciar o fluxo.")

    with st.container(border=True):
        st.markdown("#### Comando da IA")

        prompt = st.text_area(
            "Descreva o pedido",
            key="ia_prompt_home",
            height=160,
            placeholder=(
                "Ex.: Quero buscar os produtos do site Mega Center Eletrônicos "
                "para atualizar o estoque do depósito iFood."
            ),
        )

        deposito_digitado = st.text_input(
            "Nome do depósito",
            key="deposito_nome_input",
            placeholder="Ex.: iFood, CD Principal, Loja 1",
        )

    with st.container(border=True):
        st.markdown("#### Operação")

        operacao_label = st.radio(
            "Escolha a operação",
            options=["Cadastro de produtos", "Atualização de estoque"],
            index=0 if st.session_state.get("tipo_operacao", "cadastro") != "estoque" else 1,
            horizontal=False,
            key="ia_operacao_radio",
        )

        operacao_ui = "cadastro" if "Cadastro" in operacao_label else "estoque"

    with st.container(border=True):
        st.markdown("#### Origem")

        origem_label = st.radio(
            "Como deseja iniciar?",
            options=[
                "Buscar pelo site",
                "Anexar planilha fornecedora",
                "Importar XML",
            ],
            index=0,
            horizontal=False,
            key="ia_origem_radio",
        )

        origem_ui_map = {
            "Buscar pelo site": "site",
            "Anexar planilha fornecedora": "planilha",
            "Importar XML": "xml",
        }
        origem_ui = origem_ui_map.get(origem_label, "planilha")

        url_site = ""
        if origem_ui == "site":
            url_site = st.text_input(
                "URL do site ou categoria",
                key="url_site_origem",
                placeholder="https://fornecedor.com/categoria",
            )

    operacao_final = _detectar_operacao(prompt, operacao_ui)
    origem_final = _detectar_origem(prompt, origem_ui, st.session_state.get("url_site_origem", ""))
    deposito_final = _extrair_deposito(prompt, deposito_digitado)

    st.session_state["tipo_operacao"] = operacao_final
    st.session_state["tipo_operacao_bling"] = operacao_final
    st.session_state["origem_tipo"] = origem_final
    st.session_state["deposito_nome"] = deposito_final

    plano_inicial = _montar_plano_inicial(
        prompt=prompt,
        operacao=operacao_final,
        origem_tipo=origem_final,
        deposito_nome=deposito_final,
        url_site=st.session_state.get("url_site_origem", ""),
    )
    st.session_state["agent_plan"] = plano_inicial

    with st.container(border=True):
        st.markdown("#### Resumo da IA")

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Operação", "Cadastro" if operacao_final == "cadastro" else "Estoque")
        with col2:
            mapa_origem = {
                "site": "Site",
                "planilha": "Planilha",
                "xml": "XML",
            }
            st.metric("Origem", mapa_origem.get(origem_final, "Planilha"))

        if deposito_final:
            st.caption(f"Depósito identificado: **{deposito_final}**")

        if _normalizar_texto(st.session_state.get("url_site_origem", "")):
            st.caption(f"URL informada: **{st.session_state['url_site_origem']}**")

    with st.container(border=True):
        col1, col2 = st.columns(2)

        with col1:
            st.button(
                "Limpar",
                use_container_width=True,
                on_click=lambda: _limpar_tela_origem(),
            )

        with col2:
            st.button(
                "Próximo →",
                use_container_width=True,
                disabled=not _pode_avancar(prompt, st.session_state.get("url_site_origem", "")),
                on_click=_ir_para_proxima_etapa,
            )


def _limpar_tela_origem() -> None:
    for chave in [
        "ia_prompt_home",
        "deposito_nome_input",
        "url_site_origem",
    ]:
        if chave in st.session_state:
            st.session_state[chave] = ""

    st.session_state["agent_plan"] = {}
    st.session_state["origem_tipo"] = ""
    st.session_state["deposito_nome"] = ""
