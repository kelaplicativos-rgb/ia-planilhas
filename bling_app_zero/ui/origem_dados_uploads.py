from __future__ import annotations

from typing import Callable

import pandas as pd
import streamlit as st
import xml.etree.ElementTree as ET

from bling_app_zero.core.xml_bling_mapper import mapear_xml_para_modelo_bling
from bling_app_zero.core.xml_nfe import converter_upload_xml_para_dataframe
from bling_app_zero.ui.app_helpers import log_debug, limpar_gtin_invalido
from bling_app_zero.ui.origem_dados_site import render_origem_site as render_origem_site_real


# ==========================================================
# HELPERS
# ==========================================================
def _safe_df_com_linhas(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0
    except Exception:
        return False


def _safe_df_estrutura(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0
    except Exception:
        return False


def _normalizar_df(df: pd.DataFrame) -> pd.DataFrame:
    try:
        df = df.copy()
        df.columns = [str(col).strip() for col in df.columns]

        for col in df.columns:
            df[col] = df[col].replace({None: ""}).fillna("")

        return df
    except Exception:
        return df


def _set_if_changed(chave: str, valor) -> None:
    try:
        atual = st.session_state.get(chave)
        if atual != valor:
            st.session_state[chave] = valor
    except Exception:
        st.session_state[chave] = valor


def _garantir_etapa_origem_valida() -> None:
    try:
        etapa = str(st.session_state.get("etapa_origem") or "").strip().lower()
        if etapa not in {"origem", "mapeamento", "final"}:
            st.session_state["etapa_origem"] = "origem"
    except Exception:
        st.session_state["etapa_origem"] = "origem"


def _limpar_estado_origem() -> None:
    for chave in [
        "df_origem",
        "df_dados",
        "df_saida",
        "df_final",
        "df_precificado",
        "mapping_origem",
        "arquivo_origem_nome",
        "arquivo_origem_hash",
        "df_origem_site",
        "site_processado",
        "crawler_rodando",
        "df_origem_xml_bruto",
        "df_xml_mapeado_modelo",
    ]:
        if chave in st.session_state:
            del st.session_state[chave]


def _resetar_fluxo_para_origem() -> None:
    try:
        for chave in ["df_saida", "df_final", "df_precificado", "mapping_origem", "df_xml_mapeado_modelo"]:
            if chave in st.session_state:
                del st.session_state[chave]

        st.session_state["etapa_origem"] = "origem"
        st.session_state["etapa"] = "origem"
        st.session_state["etapa_fluxo"] = "origem"
    except Exception:
        pass


def _salvar_df_origem(
    df: pd.DataFrame,
    origem: str = "",
    nome_ref: str = "",
    hash_ref: str = "",
) -> None:
    try:
        st.session_state["df_origem"] = df.copy()
        st.session_state["df_dados"] = df.copy()
        st.session_state["origem_dados"] = str(origem or "").strip().lower()
        st.session_state["arquivo_origem_nome"] = str(nome_ref or "")
        st.session_state["arquivo_origem_hash"] = str(hash_ref or "")
    except Exception:
        st.session_state["df_origem"] = df
        st.session_state["df_dados"] = df
        st.session_state["origem_dados"] = str(origem or "").strip().lower()
        st.session_state["arquivo_origem_nome"] = str(nome_ref or "")
        st.session_state["arquivo_origem_hash"] = str(hash_ref or "")


def _hash_arquivo_upload(uploaded_file) -> str:
    try:
        if uploaded_file is None:
            return ""

        pos = uploaded_file.tell()
        uploaded_file.seek(0)
        conteudo = uploaded_file.read()
        uploaded_file.seek(pos)
        return str(hash(conteudo))
    except Exception:
        return ""


def _nome_arquivo(uploaded_file) -> str:
    try:
        return str(getattr(uploaded_file, "name", "") or "").strip()
    except Exception:
        return ""


def texto_extensoes_planilha() -> str:
    return ".xlsx, .xls, .xlsb, .csv"


def tem_upload_ativo() -> bool:
    try:
        return _safe_df_com_linhas(st.session_state.get("df_origem"))
    except Exception:
        return False


def _df_preview_seguro(df: pd.DataFrame) -> pd.DataFrame:
    try:
        return _normalizar_df(df).copy()
    except Exception:
        return df.copy()


def _df_preview_modelo(df: pd.DataFrame) -> pd.DataFrame:
    try:
        df = _normalizar_df(df)

        if not _safe_df_estrutura(df):
            return pd.DataFrame()

        if not df.empty:
            return df.head(5).copy()

        linha_vazia = {col: "" for col in df.columns}
        return pd.DataFrame([linha_vazia])
    except Exception:
        try:
            return df.head(5).copy()
        except Exception:
            return pd.DataFrame()


def _ler_planilha(uploaded_file) -> pd.DataFrame | None:
    if uploaded_file is None:
        return None

    nome = _nome_arquivo(uploaded_file).lower()

    try:
        if nome.endswith(".csv"):
            try:
                uploaded_file.seek(0)
                return pd.read_csv(uploaded_file)
            except Exception:
                uploaded_file.seek(0)
                return pd.read_csv(uploaded_file, sep=";", encoding="utf-8")

        if nome.endswith(".xlsb"):
            uploaded_file.seek(0)
            return pd.read_excel(uploaded_file, engine="pyxlsb")

        if nome.endswith(".xlsx") or nome.endswith(".xls"):
            uploaded_file.seek(0)
            return pd.read_excel(uploaded_file)

        return None
    except Exception as e:
        log_debug(f"Erro ao ler planilha {nome}: {e}", "ERRO")
        return None


def _processar_upload_planilha(arquivo_planilha) -> pd.DataFrame | None:
    try:
        if arquivo_planilha is None:
            return None

        nome_planilha = _nome_arquivo(arquivo_planilha)
        hash_planilha = _hash_arquivo_upload(arquivo_planilha)

        hash_anterior = st.session_state.get("arquivo_origem_hash", "")
        nome_anterior = st.session_state.get("arquivo_origem_nome", "")

        if hash_planilha != hash_anterior or nome_planilha != nome_anterior:
            _limpar_estado_origem()

        df_planilha = _ler_planilha(arquivo_planilha)

        if not _safe_df_com_linhas(df_planilha):
            st.error("Não foi possível ler a planilha do fornecedor.")
            return None

        df_planilha = _normalizar_df(df_planilha)
        df_planilha = limpar_gtin_invalido(df_planilha)

        _salvar_df_origem(
            df_planilha,
            origem="planilha",
            nome_ref=nome_planilha,
            hash_ref=hash_planilha,
        )

        log_debug(
            f"Planilha de origem carregada: {nome_planilha} "
            f"({len(df_planilha)} linha(s), {len(df_planilha.columns)} coluna(s))"
        )

        return df_planilha

    except Exception as e:
        st.error("Erro ao carregar a planilha do fornecedor.")
        log_debug(f"Erro ao carregar planilha de origem: {e}", "ERRO")
        return None


def _obter_modelo_ativo_para_xml() -> pd.DataFrame | None:
    try:
        tipo = str(st.session_state.get("tipo_operacao_bling") or "").strip().lower()
        if tipo == "estoque":
            return st.session_state.get("df_modelo_estoque")
        return st.session_state.get("df_modelo_cadastro")
    except Exception:
        return None


def _obter_deposito_padrao_xml() -> str:
    chaves = [
        "deposito_padrao",
        "nome_deposito",
        "deposito_nome",
        "deposito_manual",
        "deposito_estoque_manual",
    ]
    for chave in chaves:
        try:
            valor = str(st.session_state.get(chave) or "").strip()
            if valor:
                return valor
        except Exception:
            continue
    return ""


def _processar_upload_xml(arquivo_xml) -> pd.DataFrame | None:
    try:
        if arquivo_xml is None:
            return None

        nome_xml = _nome_arquivo(arquivo_xml)
        hash_xml = _hash_arquivo_upload(arquivo_xml)

        hash_anterior = st.session_state.get("arquivo_origem_hash", "")
        nome_anterior = st.session_state.get("arquivo_origem_nome", "")

        if hash_xml != hash_anterior or nome_xml != nome_anterior:
            _limpar_estado_origem()

        df_xml = converter_upload_xml_para_dataframe(arquivo_xml)

        if not _safe_df_com_linhas(df_xml):
            st.error("Não foi possível converter o XML da nota fiscal em planilha.")
            return None

        df_xml = _normalizar_df(df_xml)
        df_xml = limpar_gtin_invalido(df_xml)

        st.session_state["df_origem_xml_bruto"] = df_xml.copy()

        _salvar_df_origem(
            df_xml,
            origem="xml",
            nome_ref=nome_xml,
            hash_ref=hash_xml,
        )

        modelo_ativo = _obter_modelo_ativo_para_xml()
        tipo_operacao = str(st.session_state.get("tipo_operacao_bling") or "cadastro").strip().lower()
        deposito_padrao = _obter_deposito_padrao_xml()

        if _safe_df_estrutura(modelo_ativo):
            df_xml_modelado = mapear_xml_para_modelo_bling(
                df_xml=df_xml,
                df_modelo=modelo_ativo,
                tipo_operacao=tipo_operacao,
                deposito_padrao=deposito_padrao,
            )

            if _safe_df_com_linhas(df_xml_modelado):
                st.session_state["df_xml_mapeado_modelo"] = df_xml_modelado.copy()
                st.session_state["df_saida"] = df_xml_modelado.copy()
                st.session_state["df_final"] = df_xml_modelado.copy()

        log_debug(
            f"XML convertido para planilha: {nome_xml} "
            f"({len(df_xml)} item(ns), {len(df_xml.columns)} coluna(s))"
        )

        st.success(f"XML convertido com sucesso: {len(df_xml)} item(ns) encontrado(s).")
        return df_xml

    except ET.ParseError as e:
        st.error("O XML enviado é inválido ou está mal formatado.")
        log_debug(f"XML inválido ao processar origem: {e}", "ERRO")
        return None
    except Exception as e:
        st.error("Erro ao converter o XML da nota fiscal em planilha.")
        log_debug(f"Erro ao carregar XML de origem: {e}", "ERRO")
        return None


# ==========================================================
# MODELO BLING
# ==========================================================
def _carregar_modelo(uploaded_file) -> pd.DataFrame | None:
    try:
        df = _ler_planilha(uploaded_file)
        if not _safe_df_estrutura(df):
            return None
        return _normalizar_df(df)
    except Exception as e:
        log_debug(f"Erro ao carregar modelo Bling: {e}", "ERRO")
        return None


def render_modelo_bling(operacao: str | None = None) -> None:
    st.markdown("### Modelo oficial do Bling")

    operacao_normalizada = str(operacao or "").strip().lower()

    if "cadastro" in operacao_normalizada:
        tipo = "cadastro"
    elif "estoque" in operacao_normalizada:
        tipo = "estoque"
    else:
        tipo = str(st.session_state.get("tipo_operacao_bling") or "").strip().lower()

    if tipo == "estoque":
        arquivo_modelo = st.file_uploader(
            "Anexar modelo oficial do estoque",
            type=["xlsx", "xls", "xlsb", "csv"],
            key="upload_modelo_estoque",
        )

        if arquivo_modelo is not None:
            df_modelo = _carregar_modelo(arquivo_modelo)

            if _safe_df_estrutura(df_modelo):
                st.session_state["df_modelo_estoque"] = df_modelo.copy()
                st.session_state["df_modelo_mapeamento"] = df_modelo.copy()

                st.success("Modelo de estoque carregado com sucesso.")

                with st.expander("Prévia do modelo de estoque", expanded=False):
                    st.dataframe(
                        _df_preview_modelo(df_modelo),
                        use_container_width=True,
                        hide_index=True,
                    )
            else:
                st.error("Não foi possível ler o modelo de estoque.")

    else:
        arquivo_modelo = st.file_uploader(
            "Anexar modelo oficial do cadastro",
            type=["xlsx", "xls", "xlsb", "csv"],
            key="upload_modelo_cadastro",
        )

        if arquivo_modelo is not None:
            df_modelo = _carregar_modelo(arquivo_modelo)

            if _safe_df_estrutura(df_modelo):
                st.session_state["df_modelo_cadastro"] = df_modelo.copy()
                st.session_state["df_modelo_mapeamento"] = df_modelo.copy()

                st.success("Modelo de cadastro carregado com sucesso.")

                with st.expander("Prévia do modelo de cadastro", expanded=False):
                    st.dataframe(
                        _df_preview_modelo(df_modelo),
                        use_container_width=True,
                        hide_index=True,
                    )
            else:
                st.error("Não foi possível ler o modelo de cadastro.")


# ==========================================================
# ORIGEM ENTRADA
# ==========================================================
def render_origem_entrada(
    on_change: Callable[[str], None] | None = None,
) -> pd.DataFrame | None:
    _garantir_etapa_origem_valida()

    opcoes = [
        "Buscar em site",
        "Anexar planilha",
        "Anexar XML da nota fiscal",
    ]

    origem_escolhida = st.radio(
        "Selecione a origem dos dados",
        opcoes,
        key="origem_dados_radio",
        horizontal=False,
    )

    mapa_origem = {
        "Buscar em site": "site",
        "Anexar planilha": "planilha",
        "Anexar XML da nota fiscal": "xml",
    }

    origem_atual = mapa_origem.get(origem_escolhida, "")
    origem_anterior = str(st.session_state.get("origem_dados", "") or "").strip().lower()

    _set_if_changed("origem_dados", origem_atual)

    if origem_atual != origem_anterior:
        _resetar_fluxo_para_origem()

        if callable(on_change):
            try:
                on_change(origem_atual)
            except Exception as e:
                log_debug(f"Erro no callback de troca de origem: {e}", "ERRO")

    df_origem: pd.DataFrame | None = None

    if origem_atual == "site":
        df_site = render_origem_site_real()

        if _safe_df_com_linhas(df_site):
            df_site = limpar_gtin_invalido(df_site)
            _salvar_df_origem(df_site, origem="site")
            df_origem = df_site

    elif origem_atual == "planilha":
        arquivo_planilha = st.file_uploader(
            "Anexar planilha do fornecedor",
            type=["xlsx", "xls", "xlsb", "csv"],
            key="arquivo_origem_planilha",
            help=f"Formatos aceitos: {texto_extensoes_planilha()}.",
        )
        df_origem = _processar_upload_planilha(arquivo_planilha)

    elif origem_atual == "xml":
        arquivo_xml = st.file_uploader(
            "Anexar XML da nota fiscal",
            type=["xml"],
            key="arquivo_origem_xml",
        )
        df_origem = _processar_upload_xml(arquivo_xml)

    if not _safe_df_com_linhas(df_origem):
        if origem_atual == "site":
            df_origem = st.session_state.get("df_origem_site")
        else:
            df_origem = st.session_state.get("df_origem")

    if tem_upload_ativo() and _safe_df_com_linhas(df_origem):
        with st.expander("Prévia rápida da origem", expanded=False):
            try:
                st.dataframe(
                    _df_preview_seguro(df_origem).head(5),
                    use_container_width=True,
                    hide_index=True,
                )
            except Exception:
                st.write(_df_preview_seguro(df_origem).head(5))

    return df_origem
