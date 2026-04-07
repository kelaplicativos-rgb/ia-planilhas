from __future__ import annotations

import json
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.fornecedores_adaptativos import (
    atualizar_fornecedor,
    carregar_fornecedor,
    listar_fornecedores,
    salvar_fornecedor,
)


def _safe_dict(valor: Any) -> dict[str, Any]:
    return valor if isinstance(valor, dict) else {}


def _safe_list(valor: Any) -> list[str]:
    if isinstance(valor, list):
        return [str(v).strip() for v in valor if str(v).strip()]
    if isinstance(valor, str) and valor.strip():
        return [valor.strip()]
    return []


def _join_lines(valor: Any) -> str:
    return "\n".join(_safe_list(valor))


def _split_lines(valor: str) -> list[str]:
    linhas = []
    vistos = set()

    for item in str(valor or "").splitlines():
        item = item.strip()
        if not item:
            continue
        if item in vistos:
            continue
        vistos.add(item)
        linhas.append(item)

    return linhas


def _obter_dominio_selecionado() -> str:
    return str(st.session_state.get("fornecedor_dominio_selecionado", "") or "").strip()


def _set_dominio_selecionado(dominio: str) -> None:
    st.session_state["fornecedor_dominio_selecionado"] = str(dominio or "").strip()


def _promover_fornecedor_principal(dominio: str) -> bool:
    fornecedores = listar_fornecedores()
    if not isinstance(fornecedores, dict):
        return False

    alterou = False

    for dom, dados in fornecedores.items():
        if not isinstance(dados, dict):
            continue

        deve_ser_principal = dom == dominio
        if bool(dados.get("principal", False)) != deve_ser_principal:
            atualizar_fornecedor(dom, {"principal": deve_ser_principal})
            alterou = True

    return alterou


def _despromover_fornecedor_principal(dominio: str) -> bool:
    dados = carregar_fornecedor(dominio)
    if not dados:
        return False

    if not bool(dados.get("principal", False)):
        return False

    return atualizar_fornecedor(dominio, {"principal": False})


def _render_lista_fornecedores() -> str:
    fornecedores = listar_fornecedores()
    dominios = sorted(fornecedores.keys())

    st.subheader("Fornecedores aprendidos")

    if not dominios:
        st.info("Nenhum fornecedor adaptativo cadastrado ainda.")
        return ""

    opcoes = [""] + dominios
    dominio_atual = _obter_dominio_selecionado()
    indice = opcoes.index(dominio_atual) if dominio_atual in opcoes else 0

    dominio_escolhido = st.selectbox(
        "Selecione o fornecedor",
        options=opcoes,
        index=indice,
        key="fornecedor_selectbox",
    )

    if dominio_escolhido and dominio_escolhido != dominio_atual:
        _set_dominio_selecionado(dominio_escolhido)

    col1, col2, col3 = st.columns(3)

    with col1:
        total = len(dominios)
        st.metric("Total de fornecedores", total)

    with col2:
        principais = sum(
            1
            for item in fornecedores.values()
            if isinstance(item, dict) and bool(item.get("principal", False))
        )
        st.metric("Fornecedores principais", principais)

    with col3:
        adaptativos = sum(
            1
            for item in fornecedores.values()
            if isinstance(item, dict) and item.get("origem") == "ia_adaptativa"
        )
        st.metric("Aprendidos por IA", adaptativos)

    with st.expander("📋 Lista rápida", expanded=False):
        linhas = []
        for dom in dominios:
            item = _safe_dict(fornecedores.get(dom))
            tipo = str(item.get("tipo", "generico") or "generico").strip()
            confianca = item.get("confianca", 0.0)
            principal = "⭐ principal" if bool(item.get("principal", False)) else ""
            linhas.append(
                {
                    "Domínio": dom,
                    "Tipo": tipo,
                    "Confiança": confianca,
                    "Status": principal,
                }
            )

        st.dataframe(pd.DataFrame(linhas), use_container_width=True)

    return _obter_dominio_selecionado()


def _render_edicao_fornecedor(dominio: str) -> None:
    if not dominio:
        return

    dados = _safe_dict(carregar_fornecedor(dominio))
    if not dados:
        st.warning("Fornecedor não encontrado.")
        return

    st.divider()
    st.subheader(f"Editar fornecedor: {dominio}")

    seletores = _safe_dict(dados.get("seletores"))
    links = _safe_dict(dados.get("links"))

    col_top_1, col_top_2, col_top_3 = st.columns(3)

    with col_top_1:
        tipo = st.selectbox(
            "Tipo da loja",
            options=["generico", "woocommerce", "shopify", "vtex"],
            index=["generico", "woocommerce", "shopify", "vtex"].index(
                str(dados.get("tipo", "generico") or "generico")
                if str(dados.get("tipo", "generico") or "generico") in ["generico", "woocommerce", "shopify", "vtex"]
                else "generico"
            ),
            key="fornecedor_tipo_loja",
        )

    with col_top_2:
        confianca = st.number_input(
            "Confiança",
            min_value=0.0,
            max_value=1.0,
            value=float(dados.get("confianca", 0.0) or 0.0),
            step=0.01,
            key="fornecedor_confianca",
        )

    with col_top_3:
        imagens_multiplas = st.checkbox(
            "Permitir múltiplas imagens",
            value=bool(dados.get("imagens_multiplas", True)),
            key="fornecedor_imagens_multiplas",
        )

    principal_atual = bool(dados.get("principal", False))

    col_acoes_1, col_acoes_2 = st.columns(2)

    with col_acoes_1:
        if not principal_atual:
            if st.button("⭐ Tornar fornecedor principal", use_container_width=True, key="btn_promover_principal"):
                if _promover_fornecedor_principal(dominio):
                    st.success("Fornecedor promovido como principal.")
                else:
                    st.info("Nenhuma alteração foi necessária.")
                st.rerun()
        else:
            if st.button("✖️ Remover status de principal", use_container_width=True, key="btn_despromover_principal"):
                if _despromover_fornecedor_principal(dominio):
                    st.success("Fornecedor deixou de ser principal.")
                else:
                    st.info("Nenhuma alteração foi necessária.")
                st.rerun()

    with col_acoes_2:
        st.info("Fornecedor principal será priorizado na sua base adaptativa.")

    st.markdown("### Seletores do produto")

    nome_txt = st.text_area(
        "Seletores de nome (1 por linha)",
        value=_join_lines(seletores.get("nome", [])),
        key="fornecedor_sel_nome",
        height=120,
    )

    preco_txt = st.text_area(
        "Seletores de preço (1 por linha)",
        value=_join_lines(seletores.get("preco", [])),
        key="fornecedor_sel_preco",
        height=120,
    )

    descricao_txt = st.text_area(
        "Seletores de descrição (1 por linha)",
        value=_join_lines(seletores.get("descricao", [])),
        key="fornecedor_sel_descricao",
        height=120,
    )

    imagem_txt = st.text_area(
        "Seletores de imagem (1 por linha)",
        value=_join_lines(seletores.get("imagem", [])),
        key="fornecedor_sel_imagem",
        height=120,
    )

    st.markdown("### Seletores de navegação")

    produto_txt = st.text_area(
        "Seletores de links de produto (1 por linha)",
        value=_join_lines(links.get("produto", [])),
        key="fornecedor_links_produto",
        height=120,
    )

    paginacao_txt = st.text_area(
        "Seletores de paginação / carregar mais (1 por linha)",
        value=_join_lines(links.get("paginacao", [])),
        key="fornecedor_links_paginacao",
        height=120,
    )

    patch = {
        "tipo": tipo,
        "confianca": confianca,
        "imagens_multiplas": imagens_multiplas,
        "seletores": {
            "nome": _split_lines(nome_txt),
            "preco": _split_lines(preco_txt),
            "descricao": _split_lines(descricao_txt),
            "imagem": _split_lines(imagem_txt),
        },
        "links": {
            "produto": _split_lines(produto_txt),
            "paginacao": _split_lines(paginacao_txt),
        },
    }

    col_salvar_1, col_salvar_2 = st.columns(2)

    with col_salvar_1:
        if st.button("💾 Salvar ajustes do fornecedor", use_container_width=True, key="btn_salvar_fornecedor"):
            ok = atualizar_fornecedor(dominio, patch)
            if ok:
                st.success("Fornecedor atualizado com sucesso.")
            else:
                st.error("Não foi possível atualizar o fornecedor.")
            st.rerun()

    with col_salvar_2:
        with st.expander("🧾 JSON do fornecedor", expanded=False):
            preview = _safe_dict(carregar_fornecedor(dominio))
            st.code(json.dumps(preview, ensure_ascii=False, indent=2), language="json")


def _render_cadastro_manual() -> None:
    st.divider()
    st.subheader("Cadastrar fornecedor manualmente")

    dominio_manual = st.text_input(
        "Domínio do fornecedor",
        value="",
        key="novo_fornecedor_dominio",
        placeholder="ex.: lojaexemplo.com.br",
    ).strip().lower()

    tipo_manual = st.selectbox(
        "Tipo da loja",
        options=["generico", "woocommerce", "shopify", "vtex"],
        key="novo_fornecedor_tipo",
    )

    confianca_manual = st.number_input(
        "Confiança inicial",
        min_value=0.0,
        max_value=1.0,
        value=0.8,
        step=0.01,
        key="novo_fornecedor_confianca",
    )

    principal_manual = st.checkbox(
        "Cadastrar já como fornecedor principal",
        value=False,
        key="novo_fornecedor_principal",
    )

    col1, col2 = st.columns(2)

    with col1:
        nome_manual = st.text_area(
            "Seletores de nome (1 por linha)",
            value="h1\n.product-title",
            key="novo_fornecedor_sel_nome",
            height=100,
        )
        descricao_manual = st.text_area(
            "Seletores de descrição (1 por linha)",
            value=".description\n.product-description",
            key="novo_fornecedor_sel_descricao",
            height=100,
        )
        produto_manual = st.text_area(
            "Seletores de links de produto (1 por linha)",
            value="a[href*='produto']\na[href*='product']",
            key="novo_fornecedor_links_produto",
            height=100,
        )

    with col2:
        preco_manual = st.text_area(
            "Seletores de preço (1 por linha)",
            value=".price\n.valor",
            key="novo_fornecedor_sel_preco",
            height=100,
        )
        imagem_manual = st.text_area(
            "Seletores de imagem (1 por linha)",
            value="meta[property='og:image']\n.product-gallery img",
            key="novo_fornecedor_sel_imagem",
            height=100,
        )
        paginacao_manual = st.text_area(
            "Seletores de paginação (1 por linha)",
            value="a[rel='next']\na[href*='page=']",
            key="novo_fornecedor_links_paginacao",
            height=100,
        )

    if st.button("➕ Cadastrar fornecedor manualmente", use_container_width=True, key="btn_cadastrar_fornecedor"):
        if not dominio_manual:
            st.error("Informe o domínio do fornecedor.")
            return

        config = {
            "tipo": tipo_manual,
            "confianca": confianca_manual,
            "origem": "cadastro_manual",
            "principal": principal_manual,
            "imagens_multiplas": True,
            "seletores": {
                "nome": _split_lines(nome_manual),
                "preco": _split_lines(preco_manual),
                "descricao": _split_lines(descricao_manual),
                "imagem": _split_lines(imagem_manual),
            },
            "links": {
                "produto": _split_lines(produto_manual),
                "paginacao": _split_lines(paginacao_manual),
            },
        }

        ok = salvar_fornecedor(dominio_manual, config, sobrescrever=False)
        if not ok:
            st.warning("Esse fornecedor já existe. Edite o existente ou altere o domínio.")
            return

        if principal_manual:
            _promover_fornecedor_principal(dominio_manual)

        _set_dominio_selecionado(dominio_manual)
        st.success("Fornecedor cadastrado com sucesso.")
        st.rerun()


def render_fornecedores_panel() -> None:
    st.subheader("Fornecedores adaptativos")

    st.caption(
        "Aqui você pode revisar os fornecedores aprendidos pela IA, ajustar seletores "
        "manualmente e definir qual domínio deve ser tratado como fornecedor principal."
    )

    dominio = _render_lista_fornecedores()

    if dominio:
        _render_edicao_fornecedor(dominio)

    _render_cadastro_manual()
