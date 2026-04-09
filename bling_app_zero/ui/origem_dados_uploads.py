from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.ui.origem_dados_estado import (
    safe_df_dados,
    tem_upload_ativo,
)
from bling_app_zero.ui.origem_dados_site import render_origem_site

# 🔥 PADRÃO: usar tudo do utils (fonte única de verdade)
from bling_app_zero.utils import (
    ler_planilha_segura,
    limpar_gtin_invalido,
    log_debug,
)

from bling_app_zero.utils.excel_helpers import (
    arquivo_planilha_permitido,
    hash_arquivo_upload,
    nome_arquivo,
    texto_extensoes_planilha,
)

from bling_app_zero.utils.xml_nfe import (
    arquivo_parece_xml_nfe,
    ler_xml_nfe,
)


ETAPAS_VALIDAS_ORIGEM = {"origem", "mapeamento", "final"}


# ==========================================================
# HELPERS
# ==========================================================
def _safe_str(valor: Any) -> str:
    try:
        if pd.isna(valor):
            return ""
        return str(valor).strip()
    except Exception:
        return ""


def _safe_float(valor: Any, default: float = 0.0) -> float:
    try:
        texto = str(valor or "").strip()
        if not texto:
            return default

        texto = texto.replace("R$", "").replace("r$", "").strip()
        texto = texto.replace(" ", "")

        if "," in texto and "." in texto:
            if texto.rfind(",") > texto.rfind("."):
                texto = texto.replace(".", "").replace(",", ".")
            else:
                texto = texto.replace(",", "")
        else:
            texto = texto.replace(",", ".")

        return float(texto)
    except Exception:
        return default


def _set_if_changed(key: str, value: Any) -> None:
    try:
        if st.session_state.get(key) != value:
            st.session_state[key] = value
    except Exception:
        pass


def _df_tem_estrutura(df: pd.DataFrame | None) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0
    except Exception:
        return False


# ==========================================================
# FLUXO
# ==========================================================
def _garantir_etapa_origem_valida() -> None:
    try:
        etapa = str(st.session_state.get("etapa_origem", "origem") or "origem").strip().lower()
        if etapa not in ETAPAS_VALIDAS_ORIGEM:
            log_debug(f"Etapa inválida: {etapa}", "ERROR")
            st.session_state["etapa_origem"] = "origem"
    except Exception:
        st.session_state["etapa_origem"] = "origem"


def _resetar_fluxo_para_origem() -> None:
    try:
        st.session_state["etapa_origem"] = "origem"
        st.session_state.pop("coluna_em_mapeamento", None)
        st.session_state.pop("campo_destino_mapeamento", None)
        st.session_state.pop("preview_mapeamento_coluna", None)
    except Exception:
        st.session_state["etapa_origem"] = "origem"


# ==========================================================
# SALVAR DF
# ==========================================================
def _salvar_df_origem(
    df: pd.DataFrame,
    origem: str,
    nome_ref: str = "",
    hash_ref: str = "",
) -> pd.DataFrame:
    try:
        df_salvo = df.copy()

        st.session_state["df_origem"] = df_salvo
        st.session_state["df_saida"] = df_salvo.copy()
        st.session_state["df_final"] = df_salvo.copy()

        if origem == "xml":
            st.session_state["df_origem_xml"] = df_salvo.copy()

        if nome_ref:
            st.session_state["origem_arquivo_nome"] = nome_ref

        if hash_ref:
            st.session_state["origem_arquivo_hash"] = hash_ref

        _resetar_fluxo_para_origem()
        return df_salvo

    except Exception:
        _resetar_fluxo_para_origem()
        return df


# ==========================================================
# PLANILHA
# ==========================================================
def _processar_upload_planilha(arquivo_planilha: Any) -> pd.DataFrame | None:
    try:
        if arquivo_planilha is None:
            return st.session_state.get("df_origem")

        if not arquivo_planilha_permitido(arquivo_planilha):
            st.error(f"Formato inválido. Use: {texto_extensoes_planilha()}")
            return None

        df = ler_planilha_segura(arquivo_planilha)

        if not safe_df_dados(df):
            st.error("Erro ao ler planilha.")
            return None

        df.columns = [str(c).strip() for c in df.columns]

        # 🔥 padrão único
        df = limpar_gtin_invalido(df)

        return _salvar_df_origem(df, "planilha")

    except Exception as e:
        st.error("Erro no upload.")
        log_debug(str(e), "ERROR")
        return None


# ==========================================================
# XML
# ==========================================================
def _processar_upload_xml(arquivo_xml: Any) -> pd.DataFrame | None:
    try:
        if arquivo_xml is None:
            return st.session_state.get("df_origem")

        if not arquivo_parece_xml_nfe(arquivo_xml):
            st.warning("XML pode ser inválido.")

        df = ler_xml_nfe(arquivo_xml)

        if not safe_df_dados(df):
            st.error("Erro ao ler XML.")
            return None

        df = limpar_gtin_invalido(df)

        return _salvar_df_origem(df, "xml")

    except Exception as e:
        st.error("Erro no XML.")
        log_debug(str(e), "ERROR")
        return None


# ==========================================================
# UI PRINCIPAL
# ==========================================================
def render_origem_entrada(on_change=None) -> pd.DataFrame | None:
    _garantir_etapa_origem_valida()

    st.markdown("### Entrada dos dados")

    opcoes = [
        "Buscar em site",
        "Anexar planilha",
        "Anexar XML da nota fiscal",
    ]

    escolha = st.radio("Selecione a origem", opcoes)

    mapa = {
        "Buscar em site": "site",
        "Anexar planilha": "planilha",
        "Anexar XML da nota fiscal": "xml",
    }

    origem = mapa.get(escolha, "")

    _set_if_changed("origem_dados", origem)

    df = None

    if origem == "site":
        df = render_origem_site()

    elif origem == "planilha":
        arq = st.file_uploader("Planilha fornecedor")
        df = _processar_upload_planilha(arq)

    elif origem == "xml":
        arq = st.file_uploader("XML NF", type=["xml"])
        df = _processar_upload_xml(arq)

    if not safe_df_dados(df):
        df = st.session_state.get("df_origem")

    if tem_upload_ativo() and safe_df_dados(df):
        with st.expander("Prévia"):
            st.dataframe(df.head(5), use_container_width=True)

    return df
