from __future__ import annotations

from typing import Callable

import pandas as pd
import streamlit as st

from bling_app_zero.core.origem_processamento import (
    detectar_tipo_origem_por_arquivo,
    ler_modelo,
    normalizar_df,
    processar_upload_arquivo_unificado,
    safe_df_com_linhas,
    safe_df_estrutura,
)
from bling_app_zero.ui.app_helpers import limpar_gtin_invalido, log_debug
from bling_app_zero.ui.origem_dados_estado import (
    controlar_troca_origem,
    garantir_estado_origem,
    salvar_origem_no_estado,
)


def texto_extensoes_planilha() -> str:
    return ".xlsx, .xls, .xlsb, .csv"


def texto_extensoes_upload_origem() -> str:
    return ".xlsx, .xls, .xlsb, .csv, .xml, .pdf"


def tem_upload_ativo() -> bool:
    try:
        return safe_df_com_linhas(st.session_state.get("df_origem"))
    except Exception:
        return False


def _df_preview_seguro(df: pd.DataFrame) -> pd.DataFrame:
    try:
        df = normalizar_df(df).copy()
        for col in df.columns:
            df[col] = df[col].astype(str)
        return df
    except Exception:
        return df.copy()


def _df_preview_modelo(df: pd.DataFrame) -> pd.DataFrame:
    try:
        df = normalizar_df(df)

        if not safe_df_estrutura(df):
            return pd.DataFrame()

        if not df.empty:
            preview = df.head(5).copy()
            for col in preview.columns:
                preview[col] = preview[col].astype(str)
            return preview

        return pd.DataFrame([{col: "" for col in df.columns}])
    except Exception:
        return pd.DataFrame()


def _rotulo_tipo_detectado(tipo: str) -> str:
    mapa = {
        "planilha": "Planilha",
        "xml": "XML",
        "pdf": "PDF",
        "site": "Site",
        "arquivo": "Arquivo",
    }
    return mapa.get(str(tipo or "").strip().lower(), "Arquivo")


def _render_card_origem_site() -> pd.DataFrame | None:
    st.markdown("#### Buscar em site")
    st.caption("Use esta opção quando a origem vier da busca automática no site.")

    if st.session_state.get("site_processado") and safe_df_com_linhas(st.session_state.get("df_origem")):
        st.success("Dados do site já carregados no fluxo atual.")
        return st.session_state.get("df_origem")

    st.info("Origem por site disponível para integração.")
    return st.session_state.get("df_origem")


def _render_card_upload_arquivo() -> pd.DataFrame | None:
    st.markdown("#### Upload de arquivos")
    st.caption("Aceita planilha, XML e PDF em um único ponto de entrada.")

    arquivo_origem = st.file_uploader(
        "Anexar arquivo da origem",
        type=["xlsx", "xls", "xlsb", "csv", "xml", "pdf"],
        key="arquivo_origem_unificado",
        help=f"Formatos aceitos: {texto_extensoes_upload_origem()}",
    )

    if arquivo_origem is None:
        return st.session_state.get("df_origem")

    tipo_detectado = detectar_tipo_origem_por_arquivo(arquivo_origem)

    if not tipo_detectado:
        st.error("Não foi possível detectar o tipo do arquivo enviado.")
        return None

    st.caption(f"Tipo detectado: {_rotulo_tipo_detectado(tipo_detectado)}")

    origem_anterior = str(st.session_state.get("origem_dados", "") or "").strip().lower()
    if origem_anterior != tipo_detectado:
        controlar_troca_origem(tipo_detectado, log_debug)

    df_origem, info = processar_upload_arquivo_unificado(arquivo_origem)
    erro = str(info.get("erro", "") or "").strip()

    if erro:
        st.error(erro)
        log_debug(f"[ORIGEM_UPLOAD] {erro}", "ERRO")
        return None

    if not safe_df_estrutura(df_origem):
        st.error("A leitura do arquivo não retornou uma estrutura válida.")
        return None

    df_origem = limpar_gtin_invalido(df_origem)
    df_origem = normalizar_df(df_origem)

    salvar_origem_no_estado(
        df_origem,
        origem=str(info.get("tipo", "") or tipo_detectado),
        nome_ref=str(info.get("nome", "") or ""),
        hash_ref=str(info.get("hash", "") or ""),
        texto_bruto=str(info.get("texto_bruto", "") or ""),
    )

    log_debug(
        f"[ORIGEM_UPLOAD] arquivo carregado: {info.get('nome', '')} "
        f"tipo={info.get('tipo', '')} linhas={len(df_origem)} colunas={len(df_origem.columns)}",
        "INFO",
    )

    return df_origem


def render_origem_entrada(on_change: Callable[[str], None] | None = None) -> pd.DataFrame | None:
    garantir_estado_origem()

    st.markdown("### Entrada dos dados")

    escolha = st.radio(
        "Como você quer carregar os dados?",
        ["Buscar em site", "Upload de arquivos"],
        key="origem_dados_radio",
        horizontal=True,
    )

    df_origem: pd.DataFrame | None = None

    if escolha == "Buscar em site":
        houve_troca = controlar_troca_origem("site", log_debug)

        if houve_troca and callable(on_change):
            try:
                on_change("site")
            except Exception as e:
                log_debug(f"[ORIGEM_UPLOAD] erro callback origem site: {e}", "ERRO")

        df_origem = _render_card_origem_site()

    else:
        df_origem = _render_card_upload_arquivo()

        if safe_df_estrutura(df_origem) and callable(on_change):
            try:
                on_change(str(st.session_state.get("origem_dados", "") or ""))
            except Exception as e:
                log_debug(f"[ORIGEM_UPLOAD] erro callback upload: {e}", "ERRO")

    if not safe_df_com_linhas(df_origem):
        df_origem = st.session_state.get("df_origem")

    if safe_df_com_linhas(df_origem):
        with st.expander("Prévia rápida da origem", expanded=False):
            preview = _df_preview_seguro(df_origem).head(5)
            try:
                st.dataframe(
                    preview,
                    use_container_width=True,
                    hide_index=True,
                )
            except Exception:
                st.write(preview)

    return df_origem


def render_modelo_bling(operacao: str | None = None) -> None:
    st.markdown("### Modelo oficial do Bling")

    operacao_normalizada = str(operacao or "").strip().lower()

    if "cadastro" in operacao_normalizada:
        titulo = "Anexar modelo oficial do cadastro"
        key = "upload_modelo_cadastro"
        state_key = "df_modelo_cadastro"
        sucesso = "Modelo de cadastro carregado com sucesso."
        erro = "Não foi possível ler o modelo de cadastro."
        preview_titulo = "Prévia do modelo de cadastro"
    else:
        titulo = "Anexar modelo oficial do estoque"
        key = "upload_modelo_estoque"
        state_key = "df_modelo_estoque"
        sucesso = "Modelo de estoque carregado com sucesso."
        erro = "Não foi possível ler o modelo de estoque."
        preview_titulo = "Prévia do modelo de estoque"

    arquivo_modelo = st.file_uploader(
        titulo,
        type=["xlsx", "xls", "xlsb", "csv"],
        key=key,
        help=f"Formatos aceitos: {texto_extensoes_planilha()}",
    )

    if arquivo_modelo is None:
        modelo_existente = st.session_state.get(state_key)

        if safe_df_estrutura(modelo_existente):
            with st.expander(preview_titulo, expanded=False):
                st.dataframe(
                    _df_preview_modelo(modelo_existente),
                    use_container_width=True,
                    hide_index=True,
                )
        return

    df_modelo = ler_modelo(arquivo_modelo)

    if not safe_df_estrutura(df_modelo):
        st.error(erro)
        return

    st.session_state[state_key] = df_modelo.copy()
    st.session_state["df_modelo_mapeamento"] = df_modelo.copy()

    st.success(sucesso)
    log_debug(f"[ORIGEM_UPLOAD] modelo carregado: {arquivo_modelo.name}", "INFO")

    with st.expander(preview_titulo, expanded=False):
        st.dataframe(
            _df_preview_modelo(df_modelo),
            use_container_width=True,
            hide_index=True,
        )
