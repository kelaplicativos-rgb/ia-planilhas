from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import log_debug
from bling_app_zero.ui.origem_dados_estado import safe_df_estrutura
from bling_app_zero.ui.origem_dados_validacao import obter_modelo_ativo


# ==========================================================
# HELPERS
# ==========================================================
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
        "preço unitário": [
            "preço unitário",
            "preco unitario",
            "preço unitário (obrigatório)",
            "preco unitario (obrigatorio)",
            "preço",
            "preco",
            "preço de venda",
            "preco de venda",
            "valor venda",
        ],
        "preço unitário (obrigatório)": [
            "preço unitário (obrigatório)",
            "preco unitario (obrigatorio)",
            "preço unitário",
            "preco unitario",
            "preço",
            "preco",
            "preço de venda",
            "preco de venda",
            "valor venda",
        ],
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


def _safe_float(valor) -> float | None:
    try:
        if valor is None:
            return None

        if isinstance(valor, bool):
            return None

        if pd.isna(valor):
            return None

        texto = str(valor).strip()
        if not texto:
            return None

        texto = texto.replace("R$", "").replace("r$", "")
        texto = texto.replace(".", "").replace(",", ".")
        texto = texto.strip()

        if not texto:
            return None

        return float(texto)
    except Exception:
        return None


def _valor_preco_invalido(valor) -> bool:
    numero = _safe_float(valor)
    if numero is None:
        return True
    return numero <= 0


def _detectar_coluna_preco_unitario(df: pd.DataFrame) -> str | None:
    if not isinstance(df, pd.DataFrame) or len(df.columns) == 0:
        return None

    prioridades = [
        "preço unitário (obrigatório)",
        "preco unitario (obrigatorio)",
        "preço unitário",
        "preco unitario",
        "preço",
        "preco",
    ]

    mapa = {normalizar_texto(col): col for col in df.columns}

    for nome in prioridades:
        if nome in mapa:
            return mapa[nome]

    for col in df.columns:
        nome = normalizar_texto(col)
        if "preço unitário" in nome or "preco unitario" in nome:
            return col

    return None


def _detectar_coluna_preco_precificado(df: pd.DataFrame) -> str | None:
    if not isinstance(df, pd.DataFrame) or len(df.columns) == 0:
        return None

    candidatos_sessao = [
        st.session_state.get("coluna_preco_unitario_destino"),
        st.session_state.get("coluna_preco_unitario_origem"),
    ]

    for candidato in candidatos_sessao:
        candidato = str(candidato or "").strip()
        if candidato and candidato in df.columns:
            return candidato

    prioridades = [
        "preço de venda",
        "preco de venda",
        "valor venda",
        "preço",
        "preco",
        "preço unitário",
        "preco unitario",
    ]

    mapa = {normalizar_texto(col): col for col in df.columns}

    for nome in prioridades:
        if nome in mapa:
            return mapa[nome]

    for col in df.columns:
        nome = normalizar_texto(col)
        if "venda" in nome:
            return col

    for col in df.columns:
        nome = normalizar_texto(col)
        if "preço" in nome or "preco" in nome:
            return col

    return None


def _obter_df_precificacao() -> pd.DataFrame | None:
    for chave in ["df_precificado", "df_calc_precificado"]:
        df = st.session_state.get(chave)
        if isinstance(df, pd.DataFrame) and len(df.columns) > 0 and len(df) > 0:
            return df.copy()
    return None


def _aplicar_fallback_preco_unitario(df_saida: pd.DataFrame) -> pd.DataFrame:
    try:
        if not isinstance(df_saida, pd.DataFrame) or len(df_saida.columns) == 0:
            return df_saida

        col_preco_unitario = _detectar_coluna_preco_unitario(df_saida)
        if not col_preco_unitario:
            log_debug("[DF_SAIDA] fallback de preço ignorado: coluna de preço unitário não encontrada no modelo.", "INFO")
            return df_saida

        df_prec = _obter_df_precificacao()
        if not isinstance(df_prec, pd.DataFrame):
            log_debug("[DF_SAIDA] fallback de preço ignorado: df_precificado indisponível.", "INFO")
            return df_saida

        col_preco_prec = _detectar_coluna_preco_precificado(df_prec)
        if not col_preco_prec:
            log_debug("[DF_SAIDA] fallback de preço ignorado: coluna de preço da precificação não encontrada.", "INFO")
            return df_saida

        total_preenchidos = 0
        limite = min(len(df_saida), len(df_prec))

        for idx in range(limite):
            valor_atual = df_saida.at[idx, col_preco_unitario]
            if not _valor_preco_invalido(valor_atual):
                continue

            valor_prec = df_prec.iloc[idx][col_preco_prec]
            if _valor_preco_invalido(valor_prec):
                continue

            df_saida.at[idx, col_preco_unitario] = valor_prec
            total_preenchidos += 1

        if total_preenchidos > 0:
            log_debug(
                f"[DF_SAIDA] fallback aplicado em '{col_preco_unitario}' usando '{col_preco_prec}' da precificação em {total_preenchidos} linha(s).",
                "INFO",
            )
        else:
            log_debug(
                f"[DF_SAIDA] fallback de preço não precisou preencher linhas em '{col_preco_unitario}'.",
                "INFO",
            )

        return df_saida

    except Exception as e:
        log_debug(f"[DF_SAIDA] erro ao aplicar fallback de preço unitário: {e}", "ERROR")
        return df_saida


# ==========================================================
# DF SAÍDA
# ==========================================================
def sincronizar_df_saida_base(df_origem: pd.DataFrame) -> pd.DataFrame:
    try:
        modelo = obter_modelo_ativo()

        if not isinstance(modelo, pd.DataFrame) or len(modelo.columns) == 0:
            df_saida = df_origem.copy()
            df_saida = _aplicar_fallback_preco_unitario(df_saida)

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

        df_saida = _aplicar_fallback_preco_unitario(df_saida)

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
        df_saida = _aplicar_fallback_preco_unitario(df_saida)

        st.session_state["df_saida"] = df_saida.copy()
        st.session_state["df_final"] = df_saida.copy()
        return df_saida


# ==========================================================
# PRIORIDADE DE BASE
# ==========================================================
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
            df_ref = _aplicar_fallback_preco_unitario(df_ref.copy())

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
