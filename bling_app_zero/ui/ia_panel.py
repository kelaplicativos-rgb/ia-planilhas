
from __future__ import annotations

import re
from typing import Any, Dict

import streamlit as st

from bling_app_zero.ui.app_helpers import ir_para_etapa


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
    if any(token in texto for token in ["estoque", "saldo", "deposito", "depósito"]):
        return "estoque"
    if any(token in texto for token in ["cadastro", "cadastrar", "anunciar", "publicar"]):
        return "cadastro"
    return operacao_ui


def _detectar_origem(prompt: str, origem_ui: str, url_site: str) -> str:
    if _normalizar_texto(url_site):
        return "site"

    texto = _normalizar_busca(prompt)

    if "xml" in texto:
        return "xml"
    if any(token in texto for token in ["site", "url", "categoria", "buscar no site", "buscar pelo site"]):
        return "site"
    if any(token in texto for token in ["planilha", "csv", "xlsx", "xls"]):
        return "planilha"

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
    proximas_acoes: list[str] = []

    if origem_tipo == "site":
        proximas_acoes.extend(
            [
                "Abrir etapa de origem",
                "Receber URL do site",
                "Executar coleta",
                "Preparar base para precificação",
            ]
        )
    elif origem_tipo == "xml":
        proximas_acoes.extend(
            [
                "Abrir etapa de origem",
                "Receber XML",
                "Normalizar base",
                "Preparar base para mapeamento",
            ]
        )
    else:
        proximas_acoes.extend(
            [
                "Abrir etapa de origem",
                "Receber planilha fornecedora",
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


def _pode_avancar(prompt: str, origem_final: str, url_site: str) -> bool:
    if _normalizar_texto(prompt):
        return True
    if origem_final == "site" and _normalizar_texto(url_site):
        return True
    return False


def _aplicar_estado_inicial(
    prompt: str,
    operacao_final: str,
    origem_final: str,
    deposito_final: str,
    url_site: str,
) -> None:
    st.session_state["ia_prompt_home"] = _normalizar_texto(prompt)

    st.session_state["tipo_operacao_bling"] = operacao_final
    st.session_state["tipo_operacao"] = (
        "Atualização de Estoque" if operacao_final == "estoque" else "Cadastro de Produtos"
    )
    st.session_state["tipo_operacao_radio"] = st.session_state["tipo_operacao"]

    mapa_origem_radio = {
        "site": "Buscar pelo site",
        "planilha": "Planilha fornecedora",
        "xml": "XML da nota fiscal",
    }
    st.session_state["origem_tipo"] = origem_final
    st.session_state["origem_tipo_radio"] = mapa_origem_radio.get(origem_final, "Planilha fornecedora")

    st.session_state["deposito_nome"] = deposito_final
    st.session_state["origem_site_url"] = _normalizar_texto(url_site)

    st.session_state["agent_plan"] = _montar_plano_inicial(
        prompt=prompt,
        operacao=operacao_final,
        origem_tipo=origem_final,
        deposito_nome=deposito_final,
        url_site=url_site,
    )


def _ir_para_proxima_etapa(
    prompt: str,
    operacao_final: str,
    origem_final: str,
    deposito_final: str,
    url_site: str,
) -> None:
    _aplicar_estado_inicial(
        prompt=prompt,
        operacao_final=operacao_final,
        origem_final=origem_final,
        deposito_final=deposito_final,
        url_site=url_site,
    )
    ir_para_etapa("origem")


def _limpar_tela_origem() -> None:
    for chave in [
        "ia_prompt_home",
        "deposito_nome_input",
        "url_site_origem",
        "agent_plan",
        "origem_tipo",
        "origem_tipo_radio",
        "origem_site_url",
        "deposito_nome",
    ]:
        if chave in st.session_state:
            if isinstance(st.session_state.get(chave), dict):
                st.session_state[chave] = {}
            else:
                st.session_state[chave] = ""

    st.session_state["tipo_operacao"] = "Cadastro de Produtos"
    st.session_state["tipo_operacao_radio"] = "Cadastro de Produtos"
    st.session_state["tipo_operacao_bling"] = "cadastro"


# ============================================================
# UI
# ============================================================

def render_ia_panel() -> None:
    st.markdown("### Origem dos dados")
    st.caption("Descreva o que deseja fazer e deixe a IA iniciar o fluxo corretamente.")

    prompt = st.text_area(
        "Comando da IA",
        key="ia_prompt_home",
        height=140,
        placeholder=(
            "Ex.: Quero buscar os produtos do site Mega Center Eletrônicos "
            "para atualizar o estoque do depósito iFood."
        ),
    )

    with st.container(border=True):
        st.markdown("#### Operação")

        operacao_atual = str(st.session_state.get("tipo_operacao_bling", "cadastro")).lower()
        operacao_label = st.radio(
            "Escolha a operação",
            options=["Cadastro de produtos", "Atualização de estoque"],
            index=0 if operacao_atual != "estoque" else 1,
            horizontal=False,
            key="ia_operacao_radio",
            label_visibility="collapsed",
        )
        operacao_ui = "cadastro" if "Cadastro" in operacao_label else "estoque"

    with st.container(border=True):
        st.markdown("#### Como deseja iniciar?")
        origem_atual = str(st.session_state.get("origem_tipo", "planilha")).lower()
        mapa_index = {"site": 0, "planilha": 1, "xml": 2}

        origem_label = st.radio(
            "Origem",
            options=[
                "Buscar pelo site",
                "Anexar planilha fornecedora",
                "Importar XML",
            ],
            index=mapa_index.get(origem_atual, 1),
            horizontal=False,
            key="ia_origem_radio",
            label_visibility="collapsed",
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

        deposito_digitado = ""
        if operacao_ui == "estoque":
            deposito_digitado = st.text_input(
                "Nome do depósito",
                key="deposito_nome_input",
                placeholder="Ex.: iFood, CD Principal, Loja 1",
            )

    operacao_final = _detectar_operacao(prompt, operacao_ui)
    origem_final = _detectar_origem(prompt, origem_ui, st.session_state.get("url_site_origem", ""))
    deposito_final = _extrair_deposito(prompt, deposito_digitado)

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

        url_resumo = _normalizar_texto(st.session_state.get("url_site_origem", ""))
        if url_resumo:
            st.caption(f"URL informada: **{url_resumo}**")

    with st.container(border=True):
        col1, col2 = st.columns(2)

        with col1:
            st.button(
                "Limpar",
                use_container_width=True,
                on_click=_limpar_tela_origem,
                key="ia_btn_limpar",
            )

        with col2:
            st.button(
                "Próximo →",
                use_container_width=True,
                disabled=not _pode_avancar(
                    prompt,
                    origem_final,
                    st.session_state.get("url_site_origem", ""),
                ),
                key="ia_btn_proximo",
                on_click=_ir_para_proxima_etapa,
                args=(
                    prompt,
                    operacao_final,
                    origem_final,
                    deposito_final,
                    st.session_state.get("url_site_origem", ""),
                ),
    )
