from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import log_debug
from bling_app_zero.ui.origem_dados_estado import safe_df_estrutura
from bling_app_zero.ui.origem_dados_validacao import obter_modelo_ativo


def normalizar_texto(valor) -> str:
    try:
        if valor is None:
            return ""
        return str(valor).strip().lower()
    except Exception:
        return ""


def mapa_colunas_equivalentes() -> dict[str, list[str]]:
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


def encontrar_coluna_origem(coluna_modelo: str, colunas_origem: list[str]) -> str | None:
    nome_modelo = normalizar_texto(coluna_modelo)
    colunas_normalizadas = {normalizar_texto(col): col for col in colunas_origem}

    if nome_modelo in colunas_normalizadas:
        return colunas_normalizadas[nome_modelo]

    equivalentes = mapa_colunas_equivalentes().get(nome_modelo, [])

    for alias in equivalentes:
        alias_norm = normalizar_texto(alias)
        if alias_norm in colunas_normalizadas:
            return colunas_normalizadas[alias_norm]

    for col in colunas_origem:
        nome_origem = normalizar_texto(col)

        if nome_modelo and nome_modelo in nome_origem:
            return col

        if nome_origem and nome_origem in nome_modelo:
            return col

    return None


def sincronizar_df_saida_base(df_origem: pd.DataFrame) -> pd.DataFrame:
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
            col_origem = encontrar_coluna_origem(col_modelo, list(df_origem.columns))
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


def _arquivo_origem_eh_pdf() -> bool:
    try:
        nome = str(st.session_state.get("arquivo_origem_nome") or "").strip().lower()
        return nome.endswith(".pdf")
    except Exception:
        return False


def _usar_base_modelada(chave: str, rotulo: str) -> pd.DataFrame | None:
    try:
        df_ref = st.session_state.get(chave)
        if safe_df_estrutura(df_ref):
            st.session_state["df_saida"] = df_ref.copy()
            st.session_state["df_final"] = df_ref.copy()

            log_debug(
                f"[BASE] priorizando {rotulo} com {len(df_ref)} linha(s) e {len(df_ref.columns)} coluna(s).",
                "INFO",
            )
            return df_ref.copy()
        return None
    except Exception as e:
        log_debug(f"[BASE] erro ao priorizar {rotulo}: {e}", "ERROR")
        return None


def obter_df_base_prioritaria(df_origem: pd.DataFrame, origem_atual: str) -> pd.DataFrame:
    """
    Prioriza bases já modeladas quando existirem.
    Ordem:
    1) XML modelado
    2) PDF modelado
    3) base genérica modelada
    4) sincronização padrão a partir de df_origem
    """
    try:
        origem_norm = str(origem_atual or "").strip().lower()

        if "xml" in origem_norm:
            df_xml = _usar_base_modelada("df_xml_mapeado_modelo", "df_xml_mapeado_modelo")
            if isinstance(df_xml, pd.DataFrame):
                return df_xml

        if _arquivo_origem_eh_pdf():
            df_pdf = _usar_base_modelada("df_pdf_mapeado_modelo", "df_pdf_mapeado_modelo")
            if isinstance(df_pdf, pd.DataFrame):
                return df_pdf

        df_generico = _usar_base_modelada("df_origem_modelado", "df_origem_modelado")
        if isinstance(df_generico, pd.DataFrame):
            return df_generico

        return sincronizar_df_saida_base(df_origem)

    except Exception as e:
        log_debug(f"[BASE] erro ao obter base prioritária: {e}", "ERROR")
        return sincronizar_df_saida_base(df_origem)
