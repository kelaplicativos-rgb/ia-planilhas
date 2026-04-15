
from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import log_debug, safe_df_dados, safe_df_estrutura
from bling_app_zero.ui.origem_dados_handlers import (
    autoavancar_se_origem_pronta,
    consolidar_saida_da_origem,
    obter_origem_atual,
    safe_int,
    safe_str,
    sincronizar_estado_com_origem,
    tratar_troca_origem,
)

try:
    from bling_app_zero.core.fetch_router import executar_crawler
except Exception:
    executar_crawler = None

try:
    from bling_app_zero.utils.excel import ler_planilha
except Exception:
    ler_planilha = None

try:
    from bling_app_zero.core.xml_nfe import ler_xml_nfe
except Exception:
    ler_xml_nfe = None

try:
    from bling_app_zero.core.pdf_parser import ler_pdf_para_dataframe
except Exception:
    ler_pdf_para_dataframe = None


TIPOS_ORIGEM = [
    "Planilha fornecedora",
    "Buscar em site",
    "XML da nota fiscal",
    "PDF",
]


def _safe_copy_df(df):
    try:
        return df.copy()
    except Exception:
        return df


def render_header_fluxo() -> None:
    st.markdown("### Origem dos dados")
    st.caption("Escolha a fonte dos dados e carregue a base antes de seguir para a precificação.")


def _render_selector_origem() -> str:
    origem_atual = safe_str(
        st.session_state.get("origem_dados_radio") or TIPOS_ORIGEM[0]
    )
    if origem_atual not in TIPOS_ORIGEM:
        origem_atual = TIPOS_ORIGEM[0]

    origem = st.radio(
        "De onde virão os dados?",
        options=TIPOS_ORIGEM,
        horizontal=False,
        key="origem_dados_radio",
    )

    st.session_state["origem_dados_tipo"] = origem
    tratar_troca_origem(origem)
    return origem


def _ler_arquivo_upload(arquivo) -> pd.DataFrame | None:
    if arquivo is None:
        return None

    nome = safe_str(getattr(arquivo, "name", "")).lower()

    try:
        if nome.endswith((".xlsx", ".xls", ".csv")):
            if ler_planilha is None:
                st.error("Leitura de planilha indisponível no ambiente atual.")
                return None
            df = ler_planilha(arquivo)
            return df if isinstance(df, pd.DataFrame) else None

        if nome.endswith(".xml"):
            if ler_xml_nfe is None:
                st.error("Leitura de XML indisponível no ambiente atual.")
                return None
            df = ler_xml_nfe(arquivo)
            return df if isinstance(df, pd.DataFrame) else None

        if nome.endswith(".pdf"):
            if ler_pdf_para_dataframe is None:
                st.error("Leitura de PDF indisponível no ambiente atual.")
                return None
            df = ler_pdf_para_dataframe(arquivo)
            return df if isinstance(df, pd.DataFrame) else None

        st.warning("Formato de arquivo não suportado.")
        return None
    except Exception as e:
        log_debug(f"[ORIGEM_UPLOAD] erro ao ler arquivo: {e}", "ERROR")
        st.error(f"Erro ao ler arquivo: {e}")
        return None


def _render_upload_generico() -> pd.DataFrame | None:
    arquivo = st.file_uploader(
        "Anexe sua base",
        type=["xlsx", "xls", "csv", "xml", "pdf"],
        key="upload_origem_generico",
        help="Aceita planilha, XML da nota fiscal ou PDF.",
    )

    if arquivo is None:
        return None

    df = _ler_arquivo_upload(arquivo)
    if not safe_df_dados(df):
        st.warning("O arquivo foi lido, mas não gerou uma base válida.")
        return None

    sincronizar_estado_com_origem(df, log_debug)
    consolidar_saida_da_origem(df)
    st.success(f"Base carregada com {len(df)} linha(s).")
    return _safe_copy_df(df)


def _executar_busca_site() -> pd.DataFrame | None:
    url = safe_str(st.session_state.get("site_url"))
    if not url:
        st.warning("Informe a URL do site antes de executar a busca.")
        return None

    if executar_crawler is None:
        log_debug("[ORIGEM_SITE] executar_crawler indisponível no ambiente atual.", "ERROR")
        st.error("O módulo de busca do site não está disponível no momento.")
        return None

    estoque_padrao = safe_int(
        st.session_state.get("site_estoque_padrao_disponivel"),
        1,
    )

    try:
        log_debug(f"[ORIGEM_SITE] iniciando busca no site: {url}", "INFO")
        with st.spinner("Buscando produtos no site..."):
            df_site = executar_crawler(
                url=url,
                padrao_disponivel=estoque_padrao,
            )

        if not isinstance(df_site, pd.DataFrame) or df_site.empty or len(df_site.columns) == 0:
            st.session_state["site_processado"] = False
            st.session_state["_origem_site_autoavancar"] = False
            log_debug(f"[ORIGEM_SITE] busca concluída sem dados: {url}", "WARNING")
            st.warning("A busca foi executada, mas o site não retornou produtos válidos.")
            return None

        st.session_state["df_origem"] = df_site.copy()
        st.session_state["site_processado"] = True
        st.session_state["site_ultimo_url_processado"] = url
        st.session_state["_origem_site_autoavancar"] = True

        sincronizar_estado_com_origem(df_site, log_debug)
        consolidar_saida_da_origem(df_site)

        log_debug(
            f"[ORIGEM_SITE] busca concluída com {len(df_site)} linha(s) e "
            f"{len(df_site.columns)} coluna(s)",
            "INFO",
        )
        st.success(f"Busca concluída com {len(df_site)} item(ns).")
        return df_site

    except Exception as e:
        st.session_state["site_processado"] = False
        st.session_state["_origem_site_autoavancar"] = False
        log_debug(f"[ORIGEM_SITE] erro ao executar crawler: {e}", "ERROR")
        st.error(f"Erro ao buscar dados do site: {e}")
        return None


def render_config_site() -> pd.DataFrame | None:
    st.markdown("#### Buscar em site")
    st.text_input(
        "URL do site",
        key="site_url",
        placeholder="https://exemplo.com.br/categoria-ou-produtos",
    )
    st.number_input(
        "Estoque padrão para itens disponíveis",
        min_value=0,
        step=1,
        key="site_estoque_padrao_disponivel",
    )

    if st.button("Buscar dados do site", key="btn_buscar_site", type="primary", use_container_width=True):
        return _executar_busca_site()

    return None


def _render_preview_origem(df_origem: pd.DataFrame | None) -> None:
    if not safe_df_estrutura(df_origem):
        return

    with st.expander("Preview da origem", expanded=False):
        st.dataframe(df_origem.head(5), use_container_width=True, hide_index=True)
        st.caption(f"{len(df_origem)} linha(s) | {len(df_origem.columns)} coluna(s)")


def render_entrada_origem_selecionada(origem: str) -> pd.DataFrame | None:
    origem_norm = safe_str(origem).lower()

    if "site" in origem_norm:
        return render_config_site()

    return _render_upload_generico()


def render_origem_entrada() -> pd.DataFrame | None:
    render_header_fluxo()
    origem = _render_selector_origem()
    df_origem = render_entrada_origem_selecionada(origem)

    if safe_df_dados(df_origem):
        _render_preview_origem(df_origem)

    if safe_df_dados(df_origem) and st.session_state.get("_origem_site_autoavancar"):
        st.session_state["_origem_site_autoavancar"] = False
        autoavancar_se_origem_pronta(df_origem)

    return df_origem


def render_bloco_acoes_origem(df_origem: pd.DataFrame | None) -> None:
    col1, col2 = st.columns(2)

    with col1:
        if st.button("Limpar origem", use_container_width=True, key="btn_limpar_origem"):
            for chave in [
                "df_origem",
                "df_saida",
                "df_final",
                "df_precificado",
                "df_calc_precificado",
            ]:
                st.session_state.pop(chave, None)
            st.session_state["site_processado"] = False
            st.rerun()

    with col2:
        habilitar = safe_df_dados(df_origem) or safe_df_dados(st.session_state.get("df_origem"))
        if st.button(
            "Continuar para precificação",
            use_container_width=True,
            key="btn_continuar_origem",
            type="primary",
            disabled=not habilitar,
        ):
            df_ok = df_origem if safe_df_dados(df_origem) else st.session_state.get("df_origem")
            autoavancar_se_origem_pronta(df_ok)
