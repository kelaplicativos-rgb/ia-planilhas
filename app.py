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


# =========================================================
# CONFIG
# =========================================================
st.set_page_config(
    page_title="IA Planilhas",
    layout="wide",
)

APP_VERSION = "1.0.35"
VERSION_JSON_PATH = Path(__file__).with_name("version.json")


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
        log_debug(f"[VERSION] erro ao ler version.json: {e}", "ERROR")
        return {}


def _salvar_version_json(data: dict) -> bool:
    try:
        VERSION_JSON_PATH.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return True
    except Exception as e:
        log_debug(f"[VERSION] erro ao salvar version.json: {e}", "ERROR")
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
            "last_title": "Versionamento sincronizado",
            "last_description": "Version.json alinhado com APP_VERSION.",
            "history": history,
        }

    novo_registro = {
        "version": APP_VERSION,
        "date": _safe_now_str(),
        "title": "Reestruturação do layout principal",
        "description": "Novo layout com cabeçalho compacto, stepper visual e fluxo linear: origem, mapeamento e preview final.",
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
        "last_title": "Reestruturação do layout principal",
        "last_description": "Fluxo principal reorganizado em layout linear e mais limpo.",
        "history": history,
    }

    salvou = _salvar_version_json(novo)
    if salvou:
        log_debug(f"[VERSION] version.json sincronizado para {APP_VERSION}", "INFO")

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
        "origem_dados_tipo",
        "origem_dados_radio",
        "mapeamento_fornecedor",
        "fornecedor_nome",
        "coluna_preco_origem",
        "deposito_padrao",
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

    log_debug(
        f"[VERSION] mudança detectada: sessão {versao_sessao} -> código {APP_VERSION}. Limpando sessão antiga.",
        "INFO",
    )

    preservadas = _chaves_preservadas_na_limpeza()
    snapshot = {
        k: st.session_state.get(k)
        for k in preservadas
        if k in st.session_state
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
# INIT
# =========================================================
inicializar_app()
garantir_estado_base()
_garantir_estado_versionamento()

VERSION_DATA = _sincronizar_version_json_com_app()
houve_limpeza_versao = _limpar_sessao_por_versao()
if houve_limpeza_versao:
    st.rerun()


# =========================================================
# FLUXO
# =========================================================
ETAPAS_VALIDAS = {"origem", "mapeamento", "final"}

ETAPAS_CONFIG = [
    {
        "key": "origem",
        "ordem": 1,
        "titulo": "Origem dos dados",
        "descricao": "Entrada, operação e preparação",
        "icone": "📥",
    },
    {
        "key": "mapeamento",
        "ordem": 2,
        "titulo": "Mapeamento",
        "descricao": "Relacionar colunas e revisar regras",
        "icone": "🧩",
    },
    {
        "key": "final",
        "ordem": 3,
        "titulo": "Preview final",
        "descricao": "Validar e baixar arquivo final",
        "icone": "✅",
    },
]


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
    log_debug(f"[APP] navegação para etapa: {etapa_ok}", "INFO")
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
        log_debug("[APP] mapeamento bloqueado por ausência de dados. Retornando para origem.", "WARNING")
        return "origem"

    if etapa_atual == "final" and not _pode_ir_para_final():
        log_debug("[APP] final bloqueado por ausência de dados. Retornando para origem.", "WARNING")
        return "origem"

    return etapa_atual


def _indice_etapa(etapa: str) -> int:
    for item in ETAPAS_CONFIG:
        if item["key"] == etapa:
            return int(item["ordem"])
    return 1


def _rotulo_status_etapa(etapa_item: dict, etapa_atual: str) -> str:
    ordem_item = int(etapa_item["ordem"])
    ordem_atual = _indice_etapa(etapa_atual)

    if ordem_item < ordem_atual:
        return "done"
    if ordem_item == ordem_atual:
        return "active"
    return "todo"


# =========================================================
# LAYOUT
# =========================================================
def _inject_layout_css() -> None:
    st.markdown(
        """
        <style>
            .block-container {
                padding-top: 1rem;
                padding-bottom: 2rem;
            }

            .app-topbar {
                padding: 14px 16px;
                border: 1px solid rgba(120, 120, 120, 0.18);
                border-radius: 16px;
                background: rgba(255, 255, 255, 0.02);
                margin-bottom: 12px;
            }

            .app-topbar-title {
                font-size: 1.25rem;
                font-weight: 700;
                line-height: 1.2;
                margin: 0 0 4px 0;
            }

            .app-topbar-subtitle {
                font-size: 0.95rem;
                opacity: 0.85;
                margin: 0;
            }

            .step-card {
                border: 1px solid rgba(120, 120, 120, 0.18);
                border-radius: 16px;
                padding: 12px;
                min-height: 110px;
                background: rgba(255, 255, 255, 0.02);
            }

            .step-card.active {
                border-color: rgba(0, 122, 255, 0.55);
                box-shadow: 0 0 0 1px rgba(0, 122, 255, 0.18) inset;
            }

            .step-card.done {
                border-color: rgba(0, 180, 90, 0.45);
            }

            .step-kicker {
                font-size: 0.80rem;
                opacity: 0.75;
                margin-bottom: 4px;
            }

            .step-title {
                font-size: 1rem;
                font-weight: 700;
                margin-bottom: 4px;
            }

            .step-desc {
                font-size: 0.88rem;
                opacity: 0.82;
            }

            .hero-box {
                border: 1px solid rgba(120, 120, 120, 0.18);
                border-radius: 18px;
                padding: 16px;
                margin: 12px 0 14px 0;
                background: rgba(255, 255, 255, 0.02);
            }

            .hero-kicker {
                font-size: 0.82rem;
                opacity: 0.75;
                margin-bottom: 6px;
            }

            .hero-title {
                font-size: 1.25rem;
                font-weight: 700;
                margin-bottom: 4px;
            }

            .hero-desc {
                font-size: 0.94rem;
                opacity: 0.84;
                margin-bottom: 0;
            }

            .metric-card {
                border: 1px solid rgba(120, 120, 120, 0.16);
                border-radius: 14px;
                padding: 12px;
                background: rgba(255, 255, 255, 0.02);
            }

            .metric-label {
                font-size: 0.78rem;
                opacity: 0.72;
                margin-bottom: 4px;
            }

            .metric-value {
                font-size: 1rem;
                font-weight: 700;
            }

            .nav-box {
                border: 1px solid rgba(120, 120, 120, 0.16);
                border-radius: 14px;
                padding: 12px;
                margin: 14px 0 10px 0;
                background: rgba(255, 255, 255, 0.02);
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_topbar(version_data: dict, etapa_atual: str) -> None:
    versao_exibida = _resolver_app_version_exibida(version_data)
    indice = _indice_etapa(etapa_atual)
    total = len(ETAPAS_CONFIG)

    col1, col2 = st.columns([5, 1.25], vertical_alignment="center")

    with col1:
        st.markdown(
            f"""
            <div class="app-topbar">
                <div class="app-topbar-title">IA Planilhas</div>
                <div class="app-topbar-subtitle">
                    Fluxo principal reorganizado em etapas lineares e compactas. Etapa atual: {indice}/{total}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.caption(f"Versão: {versao_exibida}")
        updated_at = str((version_data or {}).get("updated_at") or "").strip()
        if updated_at:
            st.caption(f"Atualizado: {updated_at}")

        if st.button(
            "🔄 Recarregar app",
            use_container_width=True,
            key="btn_recarregar_app_topo",
        ):
            log_debug("[VERSION] recarga manual acionada pelo usuário", "INFO")
            _executar_reload_app()


def _render_stepper(etapa_atual: str) -> None:
    cols = st.columns(len(ETAPAS_CONFIG), gap="small")

    for idx, item in enumerate(ETAPAS_CONFIG):
        status = _rotulo_status_etapa(item, etapa_atual)
        with cols[idx]:
            st.markdown(
                f"""
                <div class="step-card {status}">
                    <div class="step-kicker">{item["icone"]} Etapa {item["ordem"]}</div>
                    <div class="step-title">{item["titulo"]}</div>
                    <div class="step-desc">{item["descricao"]}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _resolver_meta_etapa(etapa_atual: str) -> dict:
    mapa = {
        "origem": {
            "kicker": "Etapa 1",
            "titulo": "Origem dos dados",
            "descricao": "Escolha a operação, carregue os dados e prepare a base para o restante do fluxo.",
        },
        "mapeamento": {
            "kicker": "Etapa 2",
            "titulo": "Mapeamento",
            "descricao": "Relacione as colunas da origem com o modelo de saída e revise os campos obrigatórios.",
        },
        "final": {
            "kicker": "Etapa 3",
            "titulo": "Preview final",
            "descricao": "Valide a saída final, confira a estrutura e faça o download do arquivo pronto.",
        },
    }
    return mapa.get(etapa_atual, mapa["origem"])


def _render_resumo_superior(etapa_atual: str) -> None:
    df_fluxo = _obter_df_fluxo()
    total_linhas = 0
    total_colunas = 0

    if _safe_df(df_fluxo):
        try:
            total_linhas = int(len(df_fluxo))
            total_colunas = int(len(df_fluxo.columns))
        except Exception:
            total_linhas = 0
            total_colunas = 0

    operacao = str(
        st.session_state.get("tipo_operacao")
        or st.session_state.get("operacao")
        or st.session_state.get("operacao_selecionada")
        or ""
    ).strip()

    origem = str(
        st.session_state.get("origem_dados_tipo")
        or st.session_state.get("origem_dados_radio")
        or ""
    ).strip()

    meta = _resolver_meta_etapa(etapa_atual)

    st.markdown(
        f"""
        <div class="hero-box">
            <div class="hero-kicker">{meta["kicker"]}</div>
            <div class="hero-title">{meta["titulo"]}</div>
            <div class="hero-desc">{meta["descricao"]}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3, gap="small")

    with c1:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Operação</div>
                <div class="metric-value">{operacao or "Não definida"}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Origem</div>
                <div class="metric-value">{origem or "Não definida"}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c3:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Base atual</div>
                <div class="metric-value">{total_linhas} linha(s) • {total_colunas} coluna(s)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_navegacao(etapa_atual: str) -> None:
    pode_mapeamento = _pode_ir_para_mapeamento()
    pode_final = _pode_ir_para_final()

    col1, col2, col3 = st.columns([1, 1, 3], gap="small")

    with col1:
        if etapa_atual != "origem":
            if st.button("⬅️ Voltar", use_container_width=True, key=f"btn_voltar_{etapa_atual}"):
                if etapa_atual == "mapeamento":
                    _ir_para("origem")
                elif etapa_atual == "final":
                    _ir_para("mapeamento")

    with col2:
        if etapa_atual == "origem":
            if st.button(
                "Próximo ➡️",
                use_container_width=True,
                key="btn_avancar_origem",
                disabled=not pode_mapeamento,
            ):
                _ir_para("mapeamento")

        elif etapa_atual == "mapeamento":
            if st.button(
                "Próximo ➡️",
                use_container_width=True,
                key="btn_avancar_mapeamento",
                disabled=not pode_final,
            ):
                _ir_para("final")

    with col3:
        st.markdown(
            """
            <div class="nav-box">
                Use os botões de navegação sem perder os dados já carregados. O avanço só libera quando houver base suficiente para a próxima etapa.
            </div>
            """,
            unsafe_allow_html=True,
        )


# =========================================================
# RENDER PRINCIPAL
# =========================================================
def _render_origem() -> None:
    try:
        render_origem_dados()
    except TypeError:
        # fallback para versões antigas da função
        render_origem_dados


def _render_mapeamento() -> None:
    try:
        render_origem_mapeamento()
    except TypeError:
        render_origem_mapeamento


def _render_final() -> None:
    try:
        render_preview_final()
    except TypeError:
        render_preview_final


def _render_etapa(etapa_atual: str) -> None:
    if etapa_atual == "origem":
        _render_origem()
        return

    if etapa_atual == "mapeamento":
        _render_mapeamento()
        return

    _render_final()


# =========================================================
# EXECUÇÃO
# =========================================================
_inject_layout_css()

etapa_atual = _resolver_autoetapa()
_sincronizar_etapa_global(etapa_atual)

_render_topbar(VERSION_DATA, etapa_atual)
_render_stepper(etapa_atual)
_render_resumo_superior(etapa_atual)
_render_navegacao(etapa_atual)
_render_etapa(etapa_atual)

with st.expander("Registro de depuração", expanded=False):
    render_debug_panel()
    
