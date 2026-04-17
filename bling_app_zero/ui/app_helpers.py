
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import unicodedata

import pandas as pd
import streamlit as st


# ============================================================
# CONFIG DE LOG
# ============================================================

LOG_PATH = Path("bling_app_zero/output/debug_log.txt")
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

ETAPAS_VALIDAS = ("origem", "precificacao", "mapeamento", "preview_final")


# ============================================================
# HELPERS GERAIS
# ============================================================

def normalizar_texto(valor: object) -> str:
    """Normaliza texto para comparações internas."""
    texto = str(valor or "").strip()
    if not texto:
        return ""

    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    return texto.strip().lower()


def safe_df(df: object) -> bool:
    """Retorna True quando existe DataFrame com colunas e pelo menos 1 linha."""
    return isinstance(df, pd.DataFrame) and len(df.columns) > 0 and not df.empty


def safe_df_estrutura(df: object) -> bool:
    """Retorna True quando existe DataFrame com estrutura mínima de colunas."""
    return isinstance(df, pd.DataFrame) and len(df.columns) > 0


def obter_df_sessao(*chaves: str) -> pd.DataFrame:
    """Retorna o primeiro DataFrame válido encontrado no session_state."""
    for chave in chaves:
        valor = st.session_state.get(chave)
        if isinstance(valor, pd.DataFrame):
            return valor
    return pd.DataFrame()


def limpar_chaves_sessao(*chaves: str) -> None:
    """Remove chaves do session_state sem gerar erro."""
    for chave in chaves:
        st.session_state.pop(chave, None)


# ============================================================
# LOG DEBUG
# ============================================================

def log_debug(msg: object, nivel: str = "INFO") -> None:
    """Registra log em memória e em arquivo."""
    if "logs_debug" not in st.session_state:
        st.session_state["logs_debug"] = []

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linha = f"[{timestamp}] [{str(nivel).upper()}] {msg}"

    st.session_state["logs_debug"].append(linha)

    try:
        with open(LOG_PATH, "a", encoding="utf-8") as arquivo:
            arquivo.write(linha + "\n")
    except Exception as exc:
        st.session_state["logs_debug"].append(
            f"[{timestamp}] [ERRO] Falha ao gravar log em arquivo: {exc}"
        )


def obter_logs() -> str:
    """Lê o log persistido; se falhar, usa memória da sessão."""
    try:
        if LOG_PATH.exists():
            return LOG_PATH.read_text(encoding="utf-8")
    except Exception:
        pass

    if "logs_debug" in st.session_state:
        return "\n".join(st.session_state["logs_debug"])

    return ""


def limpar_logs() -> None:
    """Limpa logs da sessão e do arquivo persistido."""
    st.session_state["logs_debug"] = []

    try:
        if LOG_PATH.exists():
            LOG_PATH.unlink()
    except Exception:
        pass


def render_botao_download_logs() -> None:
    """Renderiza apenas o botão de download do log quando houver conteúdo."""
    logs_txt = obter_logs()
    if not logs_txt.strip():
        return

    st.download_button(
        label="📥 Baixar log debug",
        data=logs_txt,
        file_name="debug_log.txt",
        mime="text/plain",
        use_container_width=True,
        key="btn_download_log_debug",
    )


# ============================================================
# NAVEGAÇÃO / ETAPAS
# ============================================================

def _coletar_query_param(nome: str) -> str:
    """Lê query param compatível com diferentes formatos do Streamlit."""
    try:
        valor = st.query_params.get(nome, "")
    except Exception:
        return ""

    if isinstance(valor, list):
        return str(valor[0]).strip() if valor else ""
    return str(valor or "").strip()


def _definir_query_param(nome: str, valor: str) -> None:
    """Define query param com fallback seguro."""
    try:
        st.query_params[nome] = valor
    except Exception:
        pass


def get_etapa() -> str:
    """Retorna a etapa válida atual do fluxo."""
    etapa = normalizar_texto(st.session_state.get("etapa", "origem"))
    if etapa not in ETAPAS_VALIDAS:
        etapa = "origem"
        st.session_state["etapa"] = etapa
    return etapa


def set_etapa(etapa: str) -> str:
    """Define a etapa atual com sanitização."""
    etapa_limpa = normalizar_texto(etapa)
    if etapa_limpa not in ETAPAS_VALIDAS:
        etapa_limpa = "origem"

    st.session_state["etapa"] = etapa_limpa
    _definir_query_param("etapa", etapa_limpa)
    return etapa_limpa


def ir_para_etapa(etapa: str) -> None:
    """Navega para uma etapa válida."""
    set_etapa(etapa)


def voltar_para_etapa(etapa: str) -> None:
    """Alias de compatibilidade com fluxo antigo."""
    set_etapa(etapa)


def sincronizar_etapa_da_url() -> None:
    """Sincroniza session_state com a etapa presente na URL."""
    etapa_url = normalizar_texto(_coletar_query_param("etapa"))
    etapa_state = normalizar_texto(st.session_state.get("etapa", ""))

    if etapa_url in ETAPAS_VALIDAS:
        st.session_state["etapa"] = etapa_url
        return

    if etapa_state in ETAPAS_VALIDAS:
        _definir_query_param("etapa", etapa_state)
        return

    st.session_state["etapa"] = "origem"
    _definir_query_param("etapa", "origem")


def sincronizar_etapa_global() -> None:
    """Compatibilidade com chamadas antigas."""
    sincronizar_etapa_da_url()


def avancar_etapa() -> str:
    """Avança para a próxima etapa do fluxo principal."""
    etapa_atual = get_etapa()
    ordem = list(ETAPAS_VALIDAS)

    try:
        indice = ordem.index(etapa_atual)
    except ValueError:
        indice = 0

    proxima = ordem[min(indice + 1, len(ordem) - 1)]
    set_etapa(proxima)
    return proxima


def voltar_etapa() -> str:
    """Volta para a etapa anterior do fluxo principal."""
    etapa_atual = get_etapa()
    ordem = list(ETAPAS_VALIDAS)

    try:
        indice = ordem.index(etapa_atual)
    except ValueError:
        indice = 0

    anterior = ordem[max(indice - 1, 0)]
    set_etapa(anterior)
    return anterior


def _label_etapa(etapa: str) -> str:
    mapa = {
        "origem": "➡️ Origem",
        "precificacao": "Precificação",
        "mapeamento": "Mapeamento",
        "preview_final": "Preview final",
    }
    return mapa.get(etapa, etapa.title())


def render_topo_navegacao() -> None:
    """Renderiza o topo simples de navegação do app."""
    etapa_atual = get_etapa()
    colunas = st.columns(len(ETAPAS_VALIDAS))

    for coluna, etapa in zip(colunas, ETAPAS_VALIDAS):
        with coluna:
            clicou = st.button(
                _label_etapa(etapa),
                use_container_width=True,
                type="primary" if etapa_atual == etapa else "secondary",
                key=f"nav_topo_{etapa}",
            )
            if clicou and etapa != etapa_atual:
                set_etapa(etapa)
                st.rerun()


# ============================================================
# RESUMO DE FLUXO
# ============================================================

def montar_resumo_fluxo() -> dict:
    """Monta um resumo simples do andamento do fluxo."""
    df_origem = st.session_state.get("df_origem")
    df_precificado = st.session_state.get("df_origem_precificado")
    df_mapeado = st.session_state.get("df_mapeado")
    df_final = st.session_state.get("df_final")

    return {
        "etapa": get_etapa(),
        "origem_linhas": len(df_origem) if isinstance(df_origem, pd.DataFrame) else 0,
        "precificado_linhas": len(df_precificado) if isinstance(df_precificado, pd.DataFrame) else 0,
        "mapeado_linhas": len(df_mapeado) if isinstance(df_mapeado, pd.DataFrame) else 0,
        "final_linhas": len(df_final) if isinstance(df_final, pd.DataFrame) else 0,
    }


def render_resumo_fluxo() -> None:
    """Renderiza um resumo compacto do fluxo."""
    resumo = montar_resumo_fluxo()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Origem", resumo["origem_linhas"])
    with c2:
        st.metric("Precisificado", resumo["precificado_linhas"])
    with c3:
        st.metric("Mapeado", resumo["mapeado_linhas"])
    with c4:
        st.metric("Final", resumo["final_linhas"])
        
