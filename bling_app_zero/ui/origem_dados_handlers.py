from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import log_debug, safe_df_dados, safe_df_estrutura
from bling_app_zero.ui.origem_dados_estado import (
    fingerprint_df,
    limpar_mapeamento_widgets,
    obter_origem_atual,
    safe_int,
    safe_str,
)


# ==========================================================
# NORMALIZAÇÃO
# ==========================================================
def aplicar_normalizacao_basica(df: pd.DataFrame) -> pd.DataFrame:
    try:
        if not isinstance(df, pd.DataFrame):
            return pd.DataFrame()

        df_out = df.copy()
        colunas_finais: list[str] = []

        for col in df_out.columns:
            nome = (
                safe_str(col)
                .replace("\ufeff", "")
                .replace("\n", " ")
                .replace("\r", " ")
                .strip()
            )
            colunas_finais.append(nome or "Coluna")

        df_out.columns = colunas_finais
        return df_out.replace({None: ""}).fillna("")
    except Exception as e:
        log_debug(f"[ORIGEM_DADOS] erro na normalização básica: {e}", "ERROR")
        return df if isinstance(df, pd.DataFrame) else pd.DataFrame()


# ==========================================================
# LEITURA ROBUSTA
# ==========================================================
def _ler_csv_robusto(upload) -> pd.DataFrame | None:
    try:
        conteudo = upload.read()
        if not conteudo:
            return None

        candidatos = [
            ("utf-8-sig", None),
            ("utf-8", None),
            ("latin1", None),
            ("cp1252", None),
            ("utf-8-sig", ";"),
            ("utf-8", ";"),
            ("latin1", ";"),
            ("cp1252", ";"),
        ]

        for encoding, sep in candidatos:
            try:
                buffer = io.BytesIO(conteudo)
                if sep is None:
                    return pd.read_csv(
                        buffer,
                        sep=None,
                        engine="python",
                        encoding=encoding,
                    )
                return pd.read_csv(buffer, sep=sep, encoding=encoding)
            except Exception:
                continue

        return None
    except Exception as e:
        log_debug(f"[ORIGEM_DADOS] erro ao ler CSV: {e}", "ERROR")
        return None


def _ler_excel_robusto(upload) -> pd.DataFrame | None:
    try:
        conteudo = upload.read()
        if not conteudo:
            return None

        for engine in [None, "openpyxl", "xlrd"]:
            try:
                buffer = io.BytesIO(conteudo)
                if engine:
                    return pd.read_excel(buffer, engine=engine)
                return pd.read_excel(buffer)
            except Exception:
                continue

        return None
    except Exception as e:
        log_debug(f"[ORIGEM_DADOS] erro ao ler Excel: {e}", "ERROR")
        return None


def _ler_xml_robusto(upload) -> pd.DataFrame | None:
    try:
        conteudo = upload.read()
        if not conteudo:
            return None

        for parser in [None, "lxml", "etree"]:
            try:
                buffer = io.BytesIO(conteudo)
                df = pd.read_xml(buffer, parser=parser) if parser else pd.read_xml(buffer)
                if isinstance(df, pd.DataFrame):
                    return df
            except Exception:
                continue

        return None
    except Exception as e:
        log_debug(f"[ORIGEM_DADOS] erro ao ler XML: {e}", "ERROR")
        return None


def ler_planilha(upload) -> pd.DataFrame | None:
    if upload is None:
        return None

    nome = safe_str(getattr(upload, "name", "")).lower()

    try:
        if nome.endswith(".csv"):
            return _ler_csv_robusto(upload)
        if nome.endswith((".xlsx", ".xls")):
            return _ler_excel_robusto(upload)
        if nome.endswith(".xml"):
            return _ler_xml_robusto(upload)
    except Exception as e:
        log_debug(f"[ORIGEM_DADOS] erro ao ler arquivo: {e}", "ERROR")

    return None


# ==========================================================
# ESTADO / TROCAS
# ==========================================================
def controlar_troca_origem(origem: str, log_fn=None) -> None:
    origem_atual = safe_str(origem).lower()
    origem_anterior = safe_str(st.session_state.get("_origem_anterior_origem_dados")).lower()

    st.session_state["origem_dados_tipo"] = origem_atual

    if not origem_anterior:
        st.session_state["_origem_anterior_origem_dados"] = origem_atual
        if callable(log_fn):
            log_fn(f"[ORIGEM_DADOS] origem inicial definida: {origem_atual}", "INFO")
        return

    if origem_anterior == origem_atual:
        return

    if callable(log_fn):
        log_fn(
            f"[ORIGEM_DADOS] origem alterada: {origem_anterior} → {origem_atual}. "
            f"Limpando saída e mapeamento.",
            "INFO",
        )

    for chave in ["df_origem", "df_saida", "df_final", "df_precificado", "df_calc_precificado"]:
        st.session_state.pop(chave, None)

    st.session_state.pop("origem_dados_fingerprint", None)
    st.session_state["site_processado"] = False
    limpar_mapeamento_widgets()
    st.session_state["_origem_anterior_origem_dados"] = origem_atual


def sincronizar_estado_com_origem(df_origem: pd.DataFrame, log_fn=None) -> None:
    try:
        df_limpo = aplicar_normalizacao_basica(df_origem)

        if not safe_df_dados(df_limpo):
            return

        fp_novo = fingerprint_df(df_limpo)
        fp_atual = safe_str(st.session_state.get("origem_dados_fingerprint"))

        if not fp_atual:
            st.session_state["origem_dados_fingerprint"] = fp_novo
            st.session_state["df_origem"] = df_limpo.copy()

            if not safe_df_estrutura(st.session_state.get("df_saida")):
                st.session_state["df_saida"] = df_limpo.copy()

            if not safe_df_estrutura(st.session_state.get("df_final")):
                st.session_state["df_final"] = df_limpo.copy()

            if callable(log_fn):
                log_fn(
                    f"[ORIGEM_DADOS] df_origem sincronizado com {len(df_limpo)} linha(s)",
                    "INFO",
                )
            return

        if fp_atual != fp_novo:
            if callable(log_fn):
                log_fn("[ORIGEM_DADOS] nova origem detectada. Limpando saída anterior.", "INFO")

            st.session_state["origem_dados_fingerprint"] = fp_novo
            st.session_state["df_origem"] = df_limpo.copy()

            for chave in ["df_saida", "df_final", "df_precificado", "df_calc_precificado"]:
                st.session_state.pop(chave, None)

            limpar_mapeamento_widgets()
    except Exception as e:
        if callable(log_fn):
            log_fn(f"[ORIGEM_DADOS] erro ao sincronizar origem: {e}", "ERROR")


# ==========================================================
# MODELO / BASE
# ==========================================================
def obter_modelo_ativo():
    if st.session_state.get("tipo_operacao_bling") == "estoque":
        return st.session_state.get("df_modelo_estoque")
    return st.session_state.get("df_modelo_cadastro")


def modelo_tem_estrutura(df_modelo) -> bool:
    return safe_df_estrutura(df_modelo)


def obter_df_base_prioritaria(df_origem: pd.DataFrame) -> pd.DataFrame:
    df_prec = st.session_state.get("df_precificado")
    df_calc = st.session_state.get("df_calc_precificado")

    if safe_df_estrutura(df_prec):
        return df_prec.copy()

    if safe_df_estrutura(df_calc):
        return df_calc.copy()

    return df_origem.copy()


# ==========================================================
# ESTOQUE
# ==========================================================
def aplicar_bloco_estoque(df_saida: pd.DataFrame, origem_atual: str) -> pd.DataFrame:
    try:
        df_out = df_saida.copy()

        qtd_padrao = 0 if "site" in safe_str(origem_atual).lower() else 1
        qtd_padrao = safe_int(st.session_state.get("site_estoque_padrao_disponivel"), qtd_padrao)

        if "Quantidade" not in df_out.columns:
            df_out["Quantidade"] = qtd_padrao
        else:
            serie = pd.to_numeric(df_out["Quantidade"], errors="coerce")
            df_out["Quantidade"] = serie.fillna(qtd_padrao)

        deposito_nome = safe_str(st.session_state.get("deposito_nome"))

        if deposito_nome:
            if "Depósito (OBRIGATÓRIO)" not in df_out.columns:
                df_out["Depósito (OBRIGATÓRIO)"] = deposito_nome
            else:
                coluna = (
                    df_out["Depósito (OBRIGATÓRIO)"]
