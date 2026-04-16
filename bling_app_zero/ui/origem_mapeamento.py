
from __future__ import annotations

from typing import Dict, List

import pandas as pd
import streamlit as st

from bling_app_zero.agent.agent_memory import get_agent_state, save_agent_state
from bling_app_zero.ui.app_helpers import (
    blindar_df_para_bling,
    garantir_colunas_modelo,
    log_debug,
    normalizar_coluna_busca,
    safe_df_dados,
    sincronizar_etapa_global,
    validar_df_para_download,
)


# ============================================================
# HELPERS DE LEITURA DO NOVO AGENTE
# ============================================================
def _safe_str(valor) -> str:
    if valor is None:
        return ""
    texto = str(valor).strip()
    if texto.lower() in {"none", "nan", "nat"}:
        return ""
    return texto


def _get_df_by_key(chave: str) -> pd.DataFrame | None:
    if not chave:
        return None
    df = st.session_state.get(chave)
    if safe_df_dados(df):
        return df.copy()
    return None


def _get_df_fonte() -> pd.DataFrame | None:
    """
    Fonte principal do mapeamento agora vem primeiro do estado do agente.
    Só usa session_state nas chaves do próprio fluxo novo.
    """
    state = get_agent_state()

    for chave in [
        state.df_final_key,
        state.df_mapeado_key,
        state.df_normalizado_key,
        state.df_origem_key,
        "df_final",
        "df_mapeado",
        "df_normalizado",
        "df_origem",
    ]:
        df = _get_df_by_key(_safe_str(chave))
        if safe_df_dados(df):
            return df

    return None


def _get_df_modelo() -> pd.DataFrame:
    state = get_agent_state()
    tipo_operacao_bling = _safe_str(state.operacao or st.session_state.get("tipo_operacao_bling") or "cadastro").lower()

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
            ["preco unitario", "preco calculado", "preco_base", "preco", "valor"],
        )
        defaults["Descrição"] = defaults["Descrição"] or _coluna_encontrada_por_aproximacao(
            colunas_fonte,
            ["descricao curta", "descricao_curta", "nome", "titulo"],
        )
    else:
        defaults["Descrição Curta"] = defaults.get("Descrição", "")
        defaults["Preço de venda"] = _coluna_encontrada_por_aproximacao(
            colunas_fonte,
            ["preco de venda", "preco calculado", "preco_base", "preco", "valor"],
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

    state = get_agent_state()
    mapping_salvo = state.mapping_salvo or st.session_state.get("mapping_origem", {}) or {}

    mapping_final: Dict[str, str] = {}
    for coluna_modelo in colunas_modelo:
        valor = mapping_salvo.get(coluna_modelo)
        if valor in colunas_fonte:
            mapping_final[coluna_modelo] = valor
        else:
            mapping_final[coluna_modelo] = defaults.get(coluna_modelo, "")

    return mapping_final


def _serie_vazia(df_fonte: pd.DataFrame) -> pd.Series:
    return pd.Series([""] * len(df_fonte), index=df_fonte.index, dtype="object")


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
            df_saida[coluna_modelo] = _serie_vazia(df_fonte)

    if "Situação" in df_saida.columns:
        df_saida["Situação"] = df_saida["Situação"].replace("", "Ativo").fillna("Ativo")

    if tipo_operacao_bling == "estoque":
        if "Depósito (OBRIGATÓRIO)" in df_saida.columns:
            df_saida["Depósito (OBRIGATÓRIO)"] = _safe_str(deposito_nome)

    else:
        if "Descrição Curta" in df_saida.columns and "Descrição" in df_saida.columns:
            vazios = df_saida["Descrição Curta"].astype(str).str.strip().isin(["", "nan", "None"])
            df_saida.loc[vazios, "Descrição Curta"] = df_saida.loc[vazios, "Descrição"]

    df_saida = blindar_df_para_bling(
        df=df_saida,
        tipo_operacao_bling=tipo_operacao_bling,
        deposito_nome=deposito_nome,
    )

    return df_saida.fillna("")


def _salvar_estado_mapeamento(df_preview: pd.DataFrame, mapping: Dict[str, str], tipo_operacao_bling: str) -> None:
    st.session_state["mapping_origem"] = mapping.copy()
    st.session_state["df_preview_mapeamento"] = df_preview.copy()
    st.session_state["df_mapeado"] = df_preview.copy()
    st.session_state["df_final"] = df_preview.copy()

    state = get_agent_state()
    state.mapping_salvo = mapping.copy()
    state.df_mapeado_key = "df_mapeado"
    state.df_final_key = "df_final"
    state.operacao = _safe_str(tipo_operacao_bling or state.operacao or "cadastro").lower()
    state.etapa_atual = "mapeamento"
    state.status_execucao = "mapeamento_pronto"
    save_agent_state(state)


def _render_modo_ajuste_ia(df_fonte: pd.DataFrame) -> None:
    st.info(
        "A IA já preparou uma base para o Bling. "
        "Você pode revisar o mapeamento manualmente abaixo antes de confirmar."
    )

    with st.expander("Preview da base trazida pelo agente", expanded=False):
        st.dataframe(df_fonte.head(50), use_container_width=True)


# ============================================================
# RENDER
# ============================================================
def render_origem_mapeamento() -> None:
    st.markdown("### Mapeamento de colunas")
    st.caption("Confirme a origem de cada campo do modelo final antes do download.")

    state = get_agent_state()
    df_fonte = _get_df_fonte()

    if not safe_df_dados(df_fonte):
        st.warning("Nenhum dado disponível para mapear.")
        if st.button("⬅️ Voltar para IA", use_container_width=True):
            sincronizar_etapa_global("ia_orquestrador")
            st.rerun()
        return

    tipo_operacao_bling = _safe_str(state.operacao or st.session_state.get("tipo_operacao_bling") or "cadastro").lower()
    deposito_nome = _safe_str(state.deposito_nome or st.session_state.get("deposito_nome"))
    df_modelo = _get_df_modelo()

    colunas_modelo = list(df_modelo.columns)
    colunas_fonte = list(df_fonte.columns)

    _render_modo_ajuste_ia(df_fonte)

    st.markdown("#### Defina o mapeamento")

    mapping_atual = _obter_mapping_atual(colunas_modelo, colunas_fonte, tipo_operacao_bling)
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
                valor_exibido = deposito_nome
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

    df_preview = _montar_df_saida(
        df_fonte=df_fonte,
        colunas_modelo=colunas_modelo,
        mapping=mapping_novo,
        tipo_operacao_bling=tipo_operacao_bling,
        deposito_nome=deposito_nome,
    )

    _salvar_estado_mapeamento(
        df_preview=df_preview,
        mapping=mapping_novo,
        tipo_operacao_bling=tipo_operacao_bling,
    )

    with st.expander("Preview do mapeamento", expanded=False):
        st.dataframe(df_preview.head(50), use_container_width=True)

    ok_download, erros_download = validar_df_para_download(
        df=df_preview,
        tipo_operacao_bling=tipo_operacao_bling,
    )

    if erros_download:
        with st.expander("Validação do mapeamento", expanded=False):
            for erro in erros_download:
                st.error(erro)

    st.markdown("---")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("⬅️ Voltar", use_container_width=True):
            sincronizar_etapa_global("ia_orquestrador")
            st.rerun()

    with col2:
        if st.button("Zerar mapeamento", use_container_width=True):
            st.session_state["mapping_origem"] = {}
            state = get_agent_state()
            state.mapping_salvo = {}
            save_agent_state(state)
            st.rerun()

    with col3:
        pode_avancar = safe_df_dados(df_preview) and ok_download
        if st.button("Continuar ➜", use_container_width=True, disabled=not pode_avancar):
            log_debug("Mapeamento concluído com sucesso pelo fluxo do agente", "INFO")
            state = get_agent_state()
            state.df_final_key = "df_final"
            state.etapa_atual = "final"
            state.status_execucao = "final_pronto"
            save_agent_state(state)
            sincronizar_etapa_global("final")
            st.rerun()


