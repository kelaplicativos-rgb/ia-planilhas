

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import (
    garantir_estado_base,
    log_debug,
    render_debug_panel,
)
from bling_app_zero.ui.origem_dados import render_origem_dados
from bling_app_zero.ui.origem_mapeamento import render_origem_mapeamento
from bling_app_zero.ui.preview_final import render_preview_final
from bling_app_zero.utils.init_app import inicializar_app


st.set_page_config(
    page_title="IA Planilhas",
    layout="wide",
)

APP_VERSION = "1.0.36"
VERSION_JSON_PATH = Path(__file__).with_name("version.json")

ETAPAS_VALIDAS = {"origem", "mapeamento", "final"}
ETAPAS_CONFIG = [
    {"key": "origem", "ordem": 1, "titulo": "Origem"},
    {"key": "mapeamento", "ordem": 2, "titulo": "Mapeamento"},
    {"key": "final", "ordem": 3, "titulo": "Final"},
]


# =========================================================
# VERSIONAMENTO
# =========================================================
def _safe_now_str() -> str:
    try:
        return pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


def _ler_version_json() -> dict:
    try:
        if not VERSION_JSON_PATH.exists():
            return {}
        bruto = VERSION_JSON_PATH.read_text(encoding="utf-8")
        data = json.loads(bruto)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        try:
            log_debug(f"[VERSION] erro ao ler version.json: {e}", "ERROR")
        except Exception:
            pass
        return {}


def _salvar_version_json(data: dict) -> bool:
    try:
        VERSION_JSON_PATH.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return True
    except Exception as e:
        try:
            log_debug(f"[VERSION] erro ao salvar version.json: {e}", "ERROR")
        except Exception:
            pass
        return False


def _sincronizar_version_json_com_app() -> dict:
    atual = _ler_version_json()
    history = atual.get("history", [])
    if not isinstance(history, list):
        history = []

    version_json = str(atual.get("version") or "").strip()
    if version_json == APP_VERSION:
        return atual or {
            "version": APP_VERSION,
            "updated_at": _safe_now_str(),
            "last_title": "Layout mobile guiado",
            "last_description": "Fluxo simplificado em uma pergunta por vez.",
            "history": history,
        }

    novo_registro = {
        "version": APP_VERSION,
        "date": _safe_now_str(),
        "title": "Layout mobile guiado",
        "description": "Fluxo simplificado em uma pergunta por vez.",
    }

    if not any(
        isinstance(item, dict)
        and str(item.get("version") or "").strip() == APP_VERSION
        for item in history
    ):
        history.append(novo_registro)

    novo = {
        "version": APP_VERSION,
        "updated_at": _safe_now_str(),
        "last_title": "Layout mobile guiado",
        "last_description": "Fluxo simplificado em uma pergunta por vez.",
        "history": history,
    }

    salvou = _salvar_version_json(novo)
    if salvou:
        try:
            log_debug(f"[VERSION] version.json sincronizado para {APP_VERSION}", "INFO")
        except Exception:
            pass

    return novo if salvou else (atual or novo)


def _resolver_app_version_exibida(version_data: dict) -> str:
    try:
        version_json = str((version_data or {}).get("version") or "").strip()
        if version_json:
            return version_json
    except Exception:
        pass
    return APP_VERSION


def _garantir_estado_versionamento() -> None:
    if "_app_loaded_version" not in st.session_state:
        st.session_state["_app_loaded_version"] = APP_VERSION
    if "_app_last_seen_version" not in st.session_state:
        st.session_state["_app_last_seen_version"] = APP_VERSION


def _chaves_lixo_legado() -> set[str]:
    return {
        "_cache_log",
        "_cache_log_exibido",
        "_version_reload_requested",
        "_update_available",
        "_legacy_version_notice",
        "_toast_cache_version",
        "_build_notice",
        "_oauth_state",
        "_oauth_pending_user_key",
        "_bling_callback_status",
        "_bling_callback_message",
        "bling_conectado",
        "bling_conexao_ok",
        "bling_connection_message",
        "bling_connection_checked",
        "bling_ultimo_status",
        "bling_connection_source",
        "bling_primeiro_acesso_decidido",
        "bling_primeiro_acesso_escolha",
        "bling_user_key",
        "user_key",
        "bi",
        "df_envio",
    }


def _chaves_preservadas_na_limpeza() -> set[str]:
    return {
        "_app_loaded_version",
        "_app_last_seen_version",
        "etapa_origem",
        "etapa",
        "etapa_fluxo",
        "_debug_logs",
        "_debug_logs_text",
        "_debug_panel_open",
        "acesso_cliente_id",
        "acesso_liberado",
        "df_origem",
        "df_precificado",
        "df_calc_precificado",
        "df_saida",
        "df_final",
        "df_modelo",
        "df_modelo_estoque",
        "tipo_operacao",
        "operacao",
        "operacao_selecionada",
        "origem_dados_tipo",
        "origem_dados_radio",
        "mapeamento_fornecedor",
        "fornecedor_nome",
        "coluna_preco_origem",
        "deposito_padrao",
        "deposito_nome",
        "site_url",
    }


def _limpar_lixos_de_sessao() -> None:
    for chave in _chaves_lixo_legado():
        st.session_state.pop(chave, None)


def _limpar_sessao_por_versao() -> bool:
    versao_sessao = str(st.session_state.get("_app_loaded_version") or "").strip()
    _limpar_lixos_de_sessao()

    if not versao_sessao:
        st.session_state["_app_loaded_version"] = APP_VERSION
        st.session_state["_app_last_seen_version"] = APP_VERSION
        return False

    if versao_sessao == APP_VERSION:
        st.session_state["_app_last_seen_version"] = APP_VERSION
        return False

    preservadas = _chaves_preservadas_na_limpeza()
    snapshot = {
        chave: st.session_state.get(chave)
        for chave in preservadas
        if chave in st.session_state
    }

    for chave in list(st.session_state.keys()):
        if chave not in preservadas:
            st.session_state.pop(chave, None)

    for chave, valor in snapshot.items():
        st.session_state[chave] = valor

    try:
        st.cache_data.clear()
    except Exception:
        pass

    try:
        st.cache_resource.clear()
    except Exception:
        pass

    st.session_state["_app_loaded_version"] = APP_VERSION
    st.session_state["_app_last_seen_version"] = APP_VERSION
    st.session_state["etapa_origem"] = "origem"
    st.session_state["etapa"] = "origem"
    st.session_state["etapa_fluxo"] = "origem"
    return True


def _executar_reload_app() -> None:
    try:
        st.cache_data.clear()
    except Exception:
        pass

    try:
        st.cache_resource.clear()
    except Exception:
        pass

    _limpar_lixos_de_sessao()
    st.session_state["_app_loaded_version"] = APP_VERSION
    st.session_state["_app_last_seen_version"] = APP_VERSION
    st.rerun()


# =========================================================
# HELPERS DE FLUXO
# =========================================================
def _safe_df(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0
    except Exception:
        return False


def _safe_df_com_linhas(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0
    except Exception:
        return False


def _normalizar_etapa(valor: object) -> str:
    try:
        etapa_normalizada = str(valor or "origem").strip().lower()
    except Exception:
        etapa_normalizada = "origem"

    if etapa_normalizada not in ETAPAS_VALIDAS:
        return "origem"
    return etapa_normalizada


def _obter_etapa_atual() -> str:
    candidatos = [
        st.session_state.get("etapa_origem"),
        st.session_state.get("etapa"),
        st.session_state.get("etapa_fluxo"),
    ]
    for valor in candidatos:
        etapa_lida = _normalizar_etapa(valor)
        if etapa_lida in ETAPAS_VALIDAS:
            return etapa_lida
    return "origem"


def _sincronizar_etapa_global(etapa_destino: str) -> str:
    etapa_ok = _normalizar_etapa(etapa_destino)
    st.session_state["etapa_origem"] = etapa_ok
    st.session_state["etapa"] = etapa_ok
    st.session_state["etapa_fluxo"] = etapa_ok
    try:
        log_debug(f"[APP] navegação para etapa: {etapa_ok}", "INFO")
    except Exception:
        pass
    return etapa_ok


def _ir_para(etapa: str) -> None:
    _sincronizar_etapa_global(etapa)
    st.rerun()


def _obter_df_fluxo():
    for chave in ["df_final", "df_saida", "df_precificado", "df_calc_precificado", "df_origem"]:
        df = st.session_state.get(chave)
        if _safe_df(df):
            return df
    return None


def _sincronizar_df_fluxo() -> None:
    df_final = st.session_state.get("df_final")
    df_saida = st.session_state.get("df_saida")

    if _safe_df(df_final) and not _safe_df(df_saida):
        try:
            st.session_state["df_saida"] = df_final.copy()
        except Exception:
            st.session_state["df_saida"] = df_final
        return

    if _safe_df(df_saida) and not _safe_df(df_final):
        try:
            st.session_state["df_final"] = df_saida.copy()
        except Exception:
            st.session_state["df_final"] = df_saida


def _pode_ir_para_mapeamento() -> bool:
    for chave in ["df_saida", "df_final", "df_precificado", "df_calc_precificado", "df_origem"]:
        if _safe_df_com_linhas(st.session_state.get(chave)):
            return True
    return False


def _pode_ir_para_final() -> bool:
    return _safe_df_com_linhas(_obter_df_fluxo())


def _resolver_autoetapa() -> str:
    etapa_atual = _obter_etapa_atual()
    _sincronizar_df_fluxo()

    if etapa_atual == "mapeamento" and not _pode_ir_para_mapeamento():
        return "origem"

    if etapa_atual == "final" and not _pode_ir_para_final():
        return "origem"

    return etapa_atual


# =========================================================
# LAYOUT
# =========================================================
def _inject_layout_css() -> None:
    st.markdown(
        """
        <style>
            .block-container {
                max-width: 760px;
                padding-top: 0.75rem;
                padding-bottom: 2rem;
            }

            [data-testid="stHeader"] {
                background: transparent;
            }

            .ia-shell {
                padding-top: 0.25rem;
            }

            .ia-top {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 0.75rem;
            }

            .ia-logo {
                font-size: 0.90rem;
                font-weight: 700;
                color: #0A2259;
                opacity: 0.9;
            }

            .ia-version {
                font-size: 0.78rem;
                opacity: 0.7;
            }

            .ia-progress {
                display: flex;
                gap: 8px;
                margin: 0.5rem 0 1rem 0;
                flex-wrap: wrap;
            }

            .ia-progress-pill {
                flex: 1 1 120px;
                border-radius: 999px;
                padding: 8px 10px;
                text-align: center;
                font-size: 0.82rem;
                font-weight: 600;
                background: #F1F4F9;
                color: #667085;
                border: 1px solid #E4E7EC;
            }

            .ia-progress-pill.active {
                background: #0A2259;
                color: white;
                border-color: #0A2259;
            }

            .ia-question-wrap {
                margin: 1rem 0 1.25rem 0;
            }

            .ia-kicker {
                font-size: 0.85rem;
                color: #667085;
                margin-bottom: 0.25rem;
                font-weight: 600;
            }

            .ia-question {
                font-size: 2.05rem;
                line-height: 1.08;
                font-weight: 800;
                color: #0A2259;
                letter-spacing: -0.02em;
                margin: 0 0 0.35rem 0;
            }

            .ia-sub {
                font-size: 1rem;
                color: #667085;
                margin: 0;
            }

            .stButton > button,
            .stDownloadButton > button {
                min-height: 52px;
                border-radius: 18px;
                font-weight: 700;
            }

            @media (max-width: 640px) {
                .ia-question {
                    font-size: 1.85rem;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_topbar(version_data: dict) -> None:
    versao_exibida = _resolver_app_version_exibida(version_data)
    st.markdown('<div class="ia-shell">', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="ia-top">
            <div class="ia-logo">IA Planilhas</div>
            <div class="ia-version">v{versao_exibida}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_progress(etapa_atual: str) -> None:
    partes = []
    for item in ETAPAS_CONFIG:
        classe = "ia-progress-pill active" if item["key"] == etapa_atual else "ia-progress-pill"
        partes.append(f'<div class="{classe}">{item["ordem"]}. {item["titulo"]}</div>')

    st.markdown(
        f'<div class="ia-progress">{"".join(partes)}</div>',
        unsafe_allow_html=True,
    )


def _render_question_header(etapa_atual: str) -> None:
    mapa = {
        "origem": (
            "Começo",
            "O que você quer fazer?",
            "Responda o mínimo necessário para seguir.",
        ),
        "mapeamento": (
            "Próxima etapa",
            "Revise o mapeamento",
            "Ajuste só o que for necessário.",
        ),
        "final": (
            "Última etapa",
            "Seu arquivo está pronto?",
            "Valide e baixe a planilha final.",
        ),
    }
    kicker, titulo, subtitulo = mapa.get(etapa_atual, mapa["origem"])

    st.markdown(
        f"""
        <div class="ia-question-wrap">
            <div class="ia-kicker">{kicker}</div>
            <h1 class="ia-question">{titulo}</h1>
            <p class="ia-sub">{subtitulo}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_nav(etapa_atual: str) -> None:
    # A etapa "origem" já controla os próprios botões.
    if etapa_atual == "origem":
        return

    col1, col2 = st.columns(2, gap="small")

    with col1:
        if st.button(
            "⬅️ Voltar",
            use_container_width=True,
            key=f"app_btn_voltar_{etapa_atual}",
        ):
            if etapa_atual == "mapeamento":
                _ir_para("origem")
            elif etapa_atual == "final":
                _ir_para("mapeamento")

    with col2:
        if etapa_atual == "mapeamento":
            if st.button(
                "Continuar ➜",
                use_container_width=True,
                key="app_btn_continuar_mapeamento",
                disabled=not _pode_ir_para_final(),
            ):
                _ir_para("final")


def _render_etapa(etapa_atual: str) -> None:
    if etapa_atual == "origem":
        render_origem_dados()
        return
    if etapa_atual == "mapeamento":
        render_origem_mapeamento()
        return
    render_preview_final()


# =========================================================
# EXECUÇÃO
# =========================================================
inicializar_app()
garantir_estado_base()
_garantir_estado_versionamento()

VERSION_DATA = _sincronizar_version_json_com_app()
houve_limpeza_versao = _limpar_sessao_por_versao()
if houve_limpeza_versao:
    st.rerun()

_inject_layout_css()

etapa_atual = _resolver_autoetapa()
_sincronizar_etapa_global(etapa_atual)

_render_topbar(VERSION_DATA)
_render_progress(etapa_atual)
_render_question_header(etapa_atual)
_render_etapa(etapa_atual)
_render_nav(etapa_atual)

with st.expander("Debug", expanded=False):
    render_debug_panel()

st.markdown("</div>", unsafe_allow_html=True)

