from __future__ import annotations

from typing import Any
import hashlib

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

from bling_app_zero.utils.xml_nfe import (
    arquivo_parece_xml_nfe,
    ler_xml_nfe,
)


ETAPAS_VALIDAS_ORIGEM = {"origem", "mapeamento", "final"}


# ==========================================================
# HELPERS DE COMPATIBILIDADE
# ==========================================================
def arquivo_planilha_permitido(arquivo: Any) -> bool:
    try:
        nome = str(getattr(arquivo, "name", "") or "").strip().lower()
        return nome.endswith((".xlsx", ".xls", ".xlsm", ".xlsb", ".csv"))
    except Exception:
        return False


def hash_arquivo_upload(arquivo: Any) -> str:
    try:
        nome = str(getattr(arquivo, "name", "") or "")
        tamanho = str(getattr(arquivo, "size", "") or "")

        conteudo = b""
        if hasattr(arquivo, "getvalue"):
            try:
                conteudo = arquivo.getvalue() or b""
            except Exception:
                conteudo = b""
        elif hasattr(arquivo, "read"):
            try:
                pos = None
                if hasattr(arquivo, "tell"):
                    pos = arquivo.tell()
                conteudo = arquivo.read() or b""
                if pos is not None and hasattr(arquivo, "seek"):
                    arquivo.seek(pos)
            except Exception:
                conteudo = b""

        base = nome.encode("utf-8", errors="ignore") + b"|" + tamanho.encode(
            "utf-8", errors="ignore"
        ) + b"|" + conteudo
        return hashlib.md5(base).hexdigest()
    except Exception:
        return ""


def nome_arquivo(arquivo: Any) -> str:
    try:
        return str(getattr(arquivo, "name", "") or "").strip()
    except Exception:
        return ""


def texto_extensoes_planilha() -> str:
    return ".xlsx, .xls, .xlsm, .xlsb, .csv"


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


def _somente_cabecalho(df: pd.DataFrame | None) -> pd.DataFrame:
    try:
        if not isinstance(df, pd.DataFrame):
            return pd.DataFrame()
        return pd.DataFrame(columns=[str(c).strip() for c in df.columns])
    except Exception:
        return pd.DataFrame()


def _obter_chaves_modelo(operacao: str) -> tuple[str, str, str]:
    operacao_norm = str(operacao or "").strip().lower()

    if "estoque" in operacao_norm:
        return (
            "df_modelo_estoque",
            "modelo_estoque_nome",
            "modelo_estoque_hash",
        )

    return (
        "df_modelo_cadastro",
        "modelo_cadastro_nome",
        "modelo_cadastro_hash",
    )


def _salvar_modelo_bling(
    operacao: str,
    df_modelo: pd.DataFrame,
    nome_ref: str = "",
    hash_ref: str = "",
) -> pd.DataFrame:
    try:
        chave_df, chave_nome, chave_hash = _obter_chaves_modelo(operacao)

        df_limpo = _somente_cabecalho(df_modelo)

        st.session_state[chave_df] = df_limpo.copy()

        if nome_ref:
            st.session_state[chave_nome] = nome_ref

        if hash_ref:
            st.session_state[chave_hash] = hash_ref

        return df_limpo
    except Exception as e:
        log_debug(f"Erro ao salvar modelo Bling: {e}", "ERROR")
        return _somente_cabecalho(df_modelo)


def _ler_modelo_bling_upload(
    arquivo_modelo: Any, operacao: str
) -> pd.DataFrame | None:
    try:
        if arquivo_modelo is None:
            chave_df, _, _ = _obter_chaves_modelo(operacao)
            modelo_existente = st.session_state.get(chave_df)
            if _df_tem_estrutura(modelo_existente):
                return modelo_existente
            return None

        if not arquivo_planilha_permitido(arquivo_modelo):
            st.error(f"Formato inválido. Use: {texto_extensoes_planilha()}")
            return None

        nome_ref = nome_arquivo(arquivo_modelo)
        hash_ref = hash_arquivo_upload(arquivo_modelo)

        df_modelo = ler_planilha_segura(arquivo_modelo)

        if not isinstance(df_modelo, pd.DataFrame) or len(df_modelo.columns) == 0:
            st.error("Erro ao ler o modelo do Bling.")
            return None

        df_modelo.columns = [str(c).strip() for c in df_modelo.columns]

        return _salvar_modelo_bling(
            operacao=operacao,
            df_modelo=df_modelo,
            nome_ref=nome_ref,
            hash_ref=hash_ref,
        )

    except Exception as e:
        log_debug(f"Erro ao carregar modelo Bling: {e}", "ERROR")
        st.error("Erro ao carregar modelo do Bling.")
        return None


def _limpar_modelo_bling_salvo(operacao: str) -> None:
    try:
        chave_df, chave_nome, chave_hash = _obter_chaves_modelo(operacao)
        st.session_state.pop(chave_df, None)
        st.session_state.pop(chave_nome, None)
        st.session_state.pop(chave_hash, None)
    except Exception:
        pass


# ==========================================================
# FLUXO
# ==========================================================
def _garantir_etapa_origem_valida() -> None:
    try:
        etapa = str(st.session_state.get("etapa_origem", "origem") or "").strip().lower()
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

        nome_ref = nome_arquivo(arquivo_planilha)
        hash_ref = hash_arquivo_upload(arquivo_planilha)

        df = ler_planilha_segura(arquivo_planilha)

        if not safe_df_dados(df):
            st.error("Erro ao ler planilha.")
            return None

        df.columns = [str(c).strip() for c in df.columns]

        # 🔥 padrão único
        df = limpar_gtin_invalido(df)

        return _salvar_df_origem(
            df=df,
            origem="planilha",
            nome_ref=nome_ref,
            hash_ref=hash_ref,
        )

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

        nome_ref = nome_arquivo(arquivo_xml)
        hash_ref = hash_arquivo_upload(arquivo_xml)

        df = ler_xml_nfe(arquivo_xml)

        if not safe_df_dados(df):
            st.error("Erro ao ler XML.")
            return None

        df = limpar_gtin_invalido(df)

        return _salvar_df_origem(
            df=df,
            origem="xml",
            nome_ref=nome_ref,
            hash_ref=hash_ref,
        )

    except Exception as e:
        st.error("Erro no XML.")
        log_debug(str(e), "ERROR")
        return None


# ==========================================================
# MODELO BLING
# ==========================================================
def render_modelo_bling(operacao: str) -> pd.DataFrame | None:
    try:
        st.markdown("### Modelo oficial do Bling")

        chave_df, chave_nome, chave_hash = _obter_chaves_modelo(operacao)
        modelo_existente = st.session_state.get(chave_df)
        nome_existente = str(st.session_state.get(chave_nome) or "").strip()
        hash_existente = str(st.session_state.get(chave_hash) or "").strip()

        label_upload = (
            "Modelo do Bling - Cadastro"
            if "cadastro" in str(operacao or "").strip().lower()
            else "Modelo do Bling - Estoque"
        )

        uploader_key = (
            "upload_modelo_bling_cadastro"
            if "cadastro" in str(operacao or "").strip().lower()
            else "upload_modelo_bling_estoque"
        )

        arquivo_modelo = st.file_uploader(label_upload, key=uploader_key)

        modelo_ativo = _ler_modelo_bling_upload(arquivo_modelo, operacao)

        if _df_tem_estrutura(modelo_ativo):
            if arquivo_modelo is None and _df_tem_estrutura(modelo_existente):
                st.success("Modelo reutilizado automaticamente.")
            elif arquivo_modelo is not None:
                st.success("Modelo do Bling carregado com sucesso.")

            if nome_existente:
                st.caption(f"Arquivo do modelo: {nome_existente}")

            with st.expander("Prévia do cabeçalho do modelo", expanded=False):
                st.dataframe(modelo_ativo.head(0), use_container_width=True)

            col1, col2 = st.columns([1, 1])

            with col1:
                st.caption(f"Colunas detectadas: {len(modelo_ativo.columns)}")

            with col2:
                if st.button(
                    "Limpar modelo salvo",
                    key=f"btn_limpar_modelo_{uploader_key}",
                    use_container_width=True,
                ):
                    _limpar_modelo_bling_salvo(operacao)
                    st.rerun()

            return modelo_ativo

        if hash_existente and _df_tem_estrutura(modelo_existente):
            return modelo_existente

        st.info("Anexe o modelo oficial do Bling. Depois ele será reutilizado automaticamente.")
        return None

    except Exception as e:
        log_debug(f"Erro ao renderizar modelo Bling: {e}", "ERROR")
        st.error("Erro ao carregar modelo Bling.")
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

    if callable(on_change):
        try:
            on_change(origem)
        except Exception:
            pass

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
