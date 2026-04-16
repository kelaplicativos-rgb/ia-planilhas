
from __future__ import annotations

from typing import Dict, List

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import (
    garantir_colunas_modelo,
    log_debug,
    normalizar_coluna_busca,
    safe_df_dados,
    sincronizar_etapa_global,
)


# ============================================================
# HELPERS
# ============================================================

def _get_df_fonte() -> pd.DataFrame | None:
    for chave in [
        "df_saida",
        "df_precificado",
        "df_calc_precificado",
        "df_origem",
    ]:
        df = st.session_state.get(chave)
        if safe_df_dados(df):
            return df.copy()
    return None


def _get_df_modelo() -> pd.DataFrame:
    tipo_operacao_bling = st.session_state.get("tipo_operacao_bling", "cadastro")
    df_modelo = st.session_state.get("df_modelo_operacao")

    if safe_df_dados(df_modelo):
        return garantir_colunas_modelo(df_modelo.copy(), tipo_operacao_bling)

    return garantir_colunas_modelo(pd.DataFrame(), tipo_operacao_bling)


def _coluna_encontrada_por_aproximacao(colunas_fonte: List[str], candidatos: List[str]) -> str:
    mapa = {normalizar_coluna_busca(col): col for col in colunas_fonte}

    for candidato in candidatos:
        chave = normalizar_coluna_busca(candidato)
        if chave in mapa:
            return mapa[chave]

    for col in colunas_fonte:
        ncol = normalizar_coluna_busca(col)
        for candidato in candidatos:
            if normalizar_coluna_busca(candidato) in ncol:
                return col

    return ""


def _defaults_mapeamento(colunas_fonte: List[str], tipo_operacao_bling: str) -> Dict[str, str]:
    defaults: Dict[str, str] = {}

    defaults["Código"] = _coluna_encontrada_por_aproximacao(
        colunas_fonte,
        ["codigo", "codigo_fornecedor", "sku", "ref", "referencia", "gtin", "ean"],
    )
    defaults["Descrição"] = _coluna_encontrada_por_aproximacao(
        colunas_fonte,
        ["descricao", "descricao_fornecedor", "produto", "nome", "titulo"],
    )

    if tipo_operacao_bling == "estoque":
        defaults["Balanço (OBRIGATÓRIO)"] = _coluna_encontrada_por_aproximacao(
            colunas_fonte,
            ["quantidade_real", "quantidade", "estoque", "saldo", "balanco"],
        )
        defaults["Preço unitário (OBRIGATÓRIO)"] = _coluna_encontrada_por_aproximacao(
            colunas_fonte,
            [
                "preco unitario (obrigatorio)",
                "preco calculado",
                "preco_base",
                "preco",
                "valor",
            ],
        )
    else:
        defaults["Descrição Curta"] = defaults.get("Descrição", "")
        defaults["Preço de venda"] = _coluna_encontrada_por_aproximacao(
            colunas_fonte,
            [
                "preco de venda",
                "preco calculado",
                "preco_base",
                "preco",
                "valor",
            ],
        )
        defaults["GTIN/EAN"] = _coluna_encontrada_por_aproximacao(
            colunas_fonte,
            ["gtin", "ean", "codigo de barras"],
        )
        defaults["URL Imagens"] = _coluna_encontrada_por_aproximacao(
            colunas_fonte,
            ["url_imagens", "imagem", "imagens", "url imagem", "url imagens"],
        )
        defaults["Categoria"] = _coluna_encontrada_por_aproximacao(
            colunas_fonte,
            ["categoria", "departamento", "breadcrumb", "grupo"],
        )

    return defaults


def _obter_mapping_atual(colunas_modelo: List[str], colunas_fonte: List[str], tipo_operacao_bling: str) -> Dict[str, str]:
    defaults = _defaults_mapeamento(colunas_fonte, tipo_operacao_bling)
    mapping_salvo = st.session_state.get("mapping_origem", {}) or {}

    mapping_final: Dict[str, str] = {}
    for coluna_modelo in colunas_modelo:
        valor = mapping_salvo.get(coluna_modelo)
        if valor in colunas_fonte:
            mapping_final[coluna_modelo] = valor
        else:
            mapping_final[coluna_modelo] = defaults.get(coluna_modelo, "")

    return mapping_final


def _montar_df_saida(
    df_fonte: pd.DataFrame,
    colunas_modelo: List[str],
    mapping: Dict[str, str],
    tipo_operacao_bling: str,
    deposito_nome: str,
) -> pd.DataFrame:
    df_saida = pd.DataFrame(index=df_fonte.index)

    for coluna_modelo in colunas_modelo:
        origem = mapping.get(coluna_modelo, "")
        if origem and origem in df_fonte.columns:
            df_saida[coluna_modelo] = df_fonte[origem]
        else:
            df_saida[coluna_modelo] = ""

    if "Situação" in df_saida.columns:
        df_saida["Situação"] = df_saida["Situação"].replace("", "Ativo").fillna("Ativo")

    if tipo_operacao_bling == "estoque":
        if "Depósito (OBRIGATÓRIO)" in df_saida.columns:
            df_saida["Depósito (OBRIGATÓRIO)"] = str(deposito_nome or "").strip()

    if tipo_operacao_bling != "estoque":
        if "Descrição Curta" in df_saida.columns:
            vazios = df_saida["Descrição Curta"].astype(str).str.strip().isin(["", "nan", "None"])
            if "Descrição" in df_saida.columns:
                df_saida.loc[vazios, "Descrição Curta"] = df_saida.loc[vazios, "Descrição"]

    return df_saida.fillna("")


# ============================================================
# RENDER
# ============================================================

def render_origem_mapeamento() -> None:
    st.markdown("### Mapeamento de colunas")
    st.caption("Confirme a origem de cada campo do modelo final antes do download.")

    df_fonte = _get_df_fonte()
    if not safe_df_dados(df_fonte):
        st.warning("Nenhum dado disponível para mapear.")
        if st.button("⬅️ Voltar para precificação", use_container_width=True):
            sincronizar_etapa_global("precificacao")
            st.rerun()
        return

    tipo_operacao_bling = st.session_state.get("tipo_operacao_bling", "cadastro")
    df_modelo = _get_df_modelo()
    colunas_modelo = list(df_modelo.columns)
    colunas_fonte = list(df_fonte.columns)
    deposito_nome = st.session_state.get("deposito_nome", "")

    mapping_atual = _obter_mapping_atual(colunas_modelo, colunas_fonte, tipo_operacao_bling)

    st.markdown("#### Defina o mapeamento")
    opcoes_select = [""] + colunas_fonte
    mapping_novo: Dict[str, str] = {}

    usados = set()

    for coluna_modelo in colunas_modelo:
        bloqueado = False
        ajuda = ""

        if tipo_operacao_bling == "estoque" and coluna_modelo == "Depósito (OBRIGATÓRIO)":
            bloqueado = True
            ajuda = "Preenchido automaticamente pelo campo Nome do depósito."
        elif coluna_modelo == "Situação":
            bloqueado = True
            ajuda = "Preenchido automaticamente como Ativo."

        if bloqueado:
            valor_exibido = ""
            if coluna_modelo == "Depósito (OBRIGATÓRIO)":
                valor_exibido = str(deposito_nome or "")
            elif coluna_modelo == "Situação":
                valor_exibido = "Ativo"

            st.text_input(
                f"{coluna_modelo}",
                value=valor_exibido,
                disabled=True,
                help=ajuda,
                key=f"map_lock_{coluna_modelo}",
            )
            mapping_novo[coluna_modelo] = ""
            continue

        sugestao = mapping_atual.get(coluna_modelo, "")
        if sugestao not in opcoes_select:
            sugestao = ""

        idx = opcoes_select.index(sugestao) if sugestao in opcoes_select else 0

        escolha = st.selectbox(
            coluna_modelo,
            options=opcoes_select,
            index=idx,
            key=f"map_{coluna_modelo}",
        )

        if escolha and escolha in usados:
            st.warning(f"A coluna '{escolha}' já foi usada em outro campo.")
        elif escolha:
            usados.add(escolha)

        mapping_novo[coluna_modelo] = escolha

    st.session_state["mapping_origem"] = mapping_novo.copy()

    df_preview = _montar_df_saida(
        df_fonte=df_fonte,
        colunas_modelo=colunas_modelo,
        mapping=mapping_novo,
        tipo_operacao_bling=tipo_operacao_bling,
        deposito_nome=deposito_nome,
    )

    st.session_state["df_preview_mapeamento"] = df_preview.copy()
    st.session_state["df_mapeado"] = df_preview.copy()
    st.session_state["df_saida"] = df_preview.copy()

    with st.expander("Preview do mapeamento", expanded=False):
        st.dataframe(df_preview.head(50), use_container_width=True)

    st.markdown("---")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("⬅️ Voltar", use_container_width=True):
            sincronizar_etapa_global("precificacao")
            st.rerun()

    with col2:
        if st.button("Zerar mapeamento", use_container_width=True):
            st.session_state["mapping_origem"] = {}
            st.rerun()

    with col3:
        pode_avancar = safe_df_dados(df_preview)
        if st.button("Continuar ➜", use_container_width=True, disabled=not pode_avancar):
            log_debug("Mapeamento concluído com sucesso", "INFO")
            st.session_state["df_final"] = df_preview.copy()
            sincronizar_etapa_global("final")
            st.rerun()
