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
from bling_app_zero.ui.origem_dados_estoque import (
    aplicar_bloco_estoque,
    persistir_estoque_em_todas_etapas,
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


# ==========================================================
# HELPERS
# ==========================================================
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


def _normalizar_texto(valor) -> str:
    try:
        if valor is None:
            return ""
        return str(valor).strip().lower()
    except Exception:
        return ""


def _sincronizar_tipo_operacao(operacao: str) -> None:
    try:
        controlar_troca_operacao(operacao, log_debug)
    except Exception:
        pass

    st.session_state["tipo_operacao_bling"] = (
        "cadastro" if operacao == "Cadastro de Produtos" else "estoque"
    )


def _mapa_colunas_equivalentes() -> dict[str, list[str]]:
    return {
        "id": ["id"],
        "código": ["código", "codigo", "sku", "ref", "referencia", "referência", "cód", "cod"],
        "descrição": ["descrição", "descricao", "nome", "título", "titulo", "produto"],
        "descrição curta": ["descrição curta", "descricao curta", "descrição", "descricao", "nome", "produto"],
        "preço": ["preço", "preco", "valor", "valor venda", "preço de venda", "preco de venda"],
        "preço de venda": ["preço de venda", "preco de venda", "preço", "preco", "valor", "valor venda"],
        "preço de custo": ["preço de custo", "preco de custo", "custo", "valor custo"],
        "marca": ["marca", "fabricante"],
        "ncm": ["ncm"],
        "gtin": ["gtin", "ean", "código de barras", "codigo de barras"],
        "gtin tributário": ["gtin tributário", "gtin tributario", "ean tributário", "ean tributario"],
        "unidade": ["unidade", "und", "ucom"],
        "estoque": ["estoque", "saldo", "quantidade", "qtd"],
        "quantidade": ["quantidade", "qtd", "estoque", "saldo"],
        "saldo": ["saldo", "estoque", "quantidade", "qtd"],
        "situação": ["situação", "situacao", "status"],
        "imagens": ["imagens", "imagem", "fotos", "foto", "url imagem", "url da imagem"],
        "link externo": ["link externo", "url", "link", "produto url"],
        "depósito": ["depósito", "deposito", "armazém", "armazem"],
    }


def _encontrar_coluna_origem(coluna_modelo: str, colunas_origem: list[str]) -> str | None:
    nome_modelo = _normalizar_texto(coluna_modelo)
    colunas_normalizadas = {_normalizar_texto(col): col for col in colunas_origem}

    if nome_modelo in colunas_normalizadas:
        return colunas_normalizadas[nome_modelo]

    equivalentes = _mapa_colunas_equivalentes().get(nome_modelo, [])

    for alias in equivalentes:
        alias_norm = _normalizar_texto(alias)
        if alias_norm in colunas_normalizadas:
            return colunas_normalizadas[alias_norm]

    for col in colunas_origem:
        nome_origem = _normalizar_texto(col)

        if nome_modelo and nome_modelo in nome_origem:
            return col

        if nome_origem and nome_origem in nome_modelo:
            return col

    return None


def _sincronizar_df_saida_base(df_origem: pd.DataFrame) -> pd.DataFrame:
    try:
        modelo = obter_modelo_ativo()

        if not isinstance(modelo, pd.DataFrame) or len(modelo.columns) == 0:
            df_saida = df_origem.copy()
            st.session_state["df_saida"] = df_saida.copy()
            st.session_state["df_final"] = df_saida.copy()

            log_debug(
                f"[DF_SAIDA] modelo indisponível; usando origem direta com {len(df_saida)} linha(s).",
                "INFO",
            )
            return df_saida

        colunas_modelo = list(modelo.columns)
        df_saida = pd.DataFrame(index=range(len(df_origem)), columns=colunas_modelo)
        colunas_preenchidas = 0

        for col_modelo in colunas_modelo:
            col_origem = _encontrar_coluna_origem(col_modelo, list(df_origem.columns))
            if col_origem is not None:
                try:
                    df_saida[col_modelo] = df_origem[col_origem].values
                    colunas_preenchidas += 1
                except Exception:
                    pass

        st.session_state["df_saida"] = df_saida.copy()
        st.session_state["df_final"] = df_saida.copy()

        log_debug(
            f"[DF_SAIDA] base preparada com {len(df_saida)} linha(s), "
            f"{len(df_saida.columns)} coluna(s) e {colunas_preenchidas} coluna(s) preenchida(s) automaticamente.",
            "INFO",
        )
        return df_saida

    except Exception as e:
        log_debug(f"[DF_SAIDA] erro ao sincronizar base de saída: {e}", "ERROR")
        df_saida = df_origem.copy()
        st.session_state["df_saida"] = df_saida.copy()
        st.session_state["df_final"] = df_saida.copy()
        return df_saida


def _obter_df_base_prioritaria(df_origem: pd.DataFrame, origem_atual: str) -> pd.DataFrame:
    """
    Prioriza a base já modelada do XML quando existir.
    Para as demais origens, mantém o comportamento padrão com df_origem.
    """
    try:
        origem_norm = str(origem_atual or "").strip().lower()

        if "xml" in origem_norm:
            df_xml_modelado = st.session_state.get("df_xml_mapeado_modelo")

            if safe_df_estrutura(df_xml_modelado):
                st.session_state["df_saida"] = df_xml_modelado.copy()
                st.session_state["df_final"] = df_xml_modelado.copy()

                log_debug(
                    f"[XML] priorizando df_xml_mapeado_modelo com {len(df_xml_modelado)} linha(s) "
                    f"e {len(df_xml_modelado.columns)} coluna(s).",
                    "INFO",
                )
                return df_xml_modelado.copy()

        return _sincronizar_df_saida_base(df_origem)

    except Exception as e:
        log_debug(f"[XML] erro ao priorizar base modelada do XML: {e}", "ERROR")
        return _sincronizar_df_saida_base(df_origem)


def _render_header_fluxo() -> None:
    st.subheader("Origem dos dados")
    st.caption(
        "Carregue a origem, escolha a operação e o sistema aplica automaticamente o modelo do Bling."
    )


# ==========================================================
# RENDER
# ==========================================================
def render_origem_dados() -> None:
    garantir_estado_origem()
    _render_header_fluxo()

    etapa = str(st.session_state.get("etapa_origem", "origem") or "origem").strip().lower()

    if etapa == "mapeamento":
        if st.button("⬅️ Voltar para origem", use_container_width=True):
            set_etapa_origem("origem")
            st.rerun()
        return

    df_origem = render_origem_entrada(
        lambda origem: controlar_troca_origem(origem, log_debug)
    )

    origem_atual = _obter_origem_atual()

    if "site" in origem_atual and not st.session_state.get("site_processado"):
        if not safe_df_dados(df_origem):
            st.info("Execute a busca do site para continuar.")
            return

    if not safe_df_dados(df_origem):
        st.info("Selecione a origem e carregue os dados para continuar.")
        return

    st.session_state["df_origem"] = df_origem.copy()
    sincronizar_estado_com_origem(df_origem, log_debug)

    st.markdown("---")

    operacao = st.radio(
        "Tipo de envio",
        ["Cadastro de Produtos", "Atualização de Estoque"],
        key="tipo_operacao",
        horizontal=True,
    )
    _sincronizar_tipo_operacao(operacao)

    st.markdown("---")

    render_modelo_bling(operacao)

    modelo_ativo = obter_modelo_ativo()
    if not _modelo_tem_estrutura(modelo_ativo):
        st.warning("⚠️ Modelo do Bling não encontrado.")
        return

    df_saida = _obter_df_base_prioritaria(df_origem, origem_atual)

    if st.session_state.get("tipo_operacao_bling") == "estoque":
        df_saida = aplicar_bloco_estoque(df_saida, origem_atual)

    st.session_state["df_saida"] = df_saida.copy()
    st.session_state["df_final"] = df_saida.copy()

    persistir_estoque_em_todas_etapas(origem_atual)

    st.markdown("---")

    render_precificacao(df_origem)

    df_prec = st.session_state.get("df_calc_precificado")
    if safe_df_estrutura(df_prec):
        st.session_state["df_precificado"] = df_prec.copy()

    persistir_estoque_em_todas_etapas(origem_atual)

    st.markdown("---")

    if st.button("➡️ Continuar para mapeamento", use_container_width=True, type="primary"):
        persistir_estoque_em_todas_etapas(origem_atual)

        valido, erros = validar_antes_mapeamento()

        if not valido:
            for erro in erros:
                st.warning(erro)
            return

        if safe_df_estrutura(st.session_state.get("df_saida")):
            st.session_state["df_final"] = st.session_state["df_saida"].copy()

        set_etapa_origem("mapeamento")
        st.rerun()
