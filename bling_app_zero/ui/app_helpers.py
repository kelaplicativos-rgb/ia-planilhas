
from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st


# ============================================================
# LOG / DEBUG
# ============================================================
def _agora_str() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


def inicializar_debug() -> None:
    if "debug_logs" not in st.session_state:
        st.session_state["debug_logs"] = []


def log_debug(mensagem: str, nivel: str = "INFO") -> None:
    inicializar_debug()
    linha = f"[{_agora_str()}] [{str(nivel).upper()}] {mensagem}"
    st.session_state["debug_logs"].append(linha)


def obter_logs_texto() -> str:
    inicializar_debug()
    return "\n".join(st.session_state.get("debug_logs", []))


def limpar_logs() -> None:
    st.session_state["debug_logs"] = []


def render_debug_panel(titulo: str = "🐞 Debug do sistema") -> None:
    inicializar_debug()

    with st.expander(titulo, expanded=False):
        logs = st.session_state.get("debug_logs", [])

        if logs:
            st.text_area(
                "Logs",
                value="\n".join(logs[-500:]),
                height=250,
                key="debug_logs_area",
            )

            col1, col2 = st.columns(2)

            with col1:
                st.download_button(
                    "⬇️ Baixar log TXT",
                    data=obter_logs_texto().encode("utf-8"),
                    file_name="debug_ia_planilhas.txt",
                    mime="text/plain",
                    use_container_width=True,
                )

            with col2:
                if st.button("🗑️ Limpar log", use_container_width=True):
                    limpar_logs()
                    st.rerun()
        else:
            st.caption("Nenhum log registrado até agora.")


# ============================================================
# HELPERS DE TEXTO
# ============================================================
def _valor_vazio(valor: Any) -> bool:
    if valor is None:
        return True
    texto = str(valor).strip()
    return texto == "" or texto.lower() in {"nan", "none", "nat"}


def normalizar_texto(valor: Any) -> str:
    if _valor_vazio(valor):
        return ""
    return str(valor).strip()


def normalizar_coluna_busca(valor: Any) -> str:
    texto = normalizar_texto(valor).lower()
    trocas = {
        "ã": "a",
        "á": "a",
        "à": "a",
        "â": "a",
        "é": "e",
        "ê": "e",
        "í": "i",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "ú": "u",
        "ç": "c",
        "_": " ",
        "-": " ",
        "/": " ",
        ".": " ",
        "(": " ",
        ")": " ",
    }
    for origem, destino in trocas.items():
        texto = texto.replace(origem, destino)
    return " ".join(texto.split())


# ============================================================
# DATAFRAME / ESTADO
# ============================================================
def safe_df(df: Any) -> pd.DataFrame:
    if isinstance(df, pd.DataFrame):
        return df.copy()
    return pd.DataFrame()


def safe_df_dados(df: Any) -> bool:
    return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0


def garantir_dataframe(df: Any) -> pd.DataFrame:
    return safe_df(df) if safe_df_dados(df) else pd.DataFrame()


def _agent_state_disponivel() -> bool:
    try:
        import bling_app_zero.agent.agent_memory  # noqa: F401

        return True
    except Exception:
        return False


def _get_agent_state_safe():
    if not _agent_state_disponivel():
        return None

    try:
        from bling_app_zero.agent.agent_memory import get_agent_state

        return get_agent_state()
    except Exception:
        return None


def _safe_set_agent_stage(etapa: str) -> None:
    state = _get_agent_state_safe()
    if state is None:
        return

    etapa_limpa = normalizar_texto(etapa) or "ia_orquestrador"

    state.etapa_atual = etapa_limpa

    if etapa_limpa in {"final"}:
        state.status_execucao = "final_pronto"
    elif etapa_limpa in {"mapeamento"}:
        state.status_execucao = "mapeamento_pronto"
    elif etapa_limpa in {"validacao"}:
        state.status_execucao = "revisao"
    elif etapa_limpa in {"ia_orquestrador"}:
        if normalizar_texto(getattr(state, "status_execucao", "")) == "":
            state.status_execucao = "idle"

    try:
        from bling_app_zero.agent.agent_memory import save_agent_state

        save_agent_state(state)
    except Exception:
        pass


def sincronizar_etapa_global(etapa: str) -> None:
    """
    Centraliza a etapa no fluxo novo e mantém compatibilidade temporária
    com as chaves históricas do app.
    """
    etapa_limpa = normalizar_texto(etapa) or "ia_orquestrador"

    st.session_state["etapa"] = etapa_limpa
    st.session_state["etapa_origem"] = etapa_limpa
    st.session_state["etapa_fluxo"] = etapa_limpa

    if etapa_limpa == "ia_orquestrador":
        st.session_state["modo_execucao"] = "ia_orquestrador"

    _safe_set_agent_stage(etapa_limpa)


def voltar_para_etapa(etapa: str) -> None:
    sincronizar_etapa_global(etapa)


def limpar_estado_fluxo() -> None:
    for chave in [
        "df_origem",
        "df_normalizado",
        "df_precificado",
        "df_mapeado",
        "df_saida",
        "df_final",
        "df_calc_precificado",
        "df_preview_mapeamento",
    ]:
        if chave in st.session_state:
            st.session_state[chave] = None

    for chave in [
        "mapping_origem",
        "mapping_origem_rascunho",
        "mapping_origem_defaults",
        "ia_plano_preview",
        "ia_erro_execucao",
    ]:
        if chave in st.session_state:
            st.session_state[chave] = {} if "mapping" in chave else ""

    if _agent_state_disponivel():
        try:
            from bling_app_zero.agent.agent_memory import reset_agent_state

            reset_agent_state(
                preserve_dataframe_keys=False,
                preserve_operacao=False,
                preserve_deposito=False,
            )
        except Exception:
            pass

    sincronizar_etapa_global("ia_orquestrador")


def obter_df_fluxo_preferencial() -> pd.DataFrame:
    state = _get_agent_state_safe()

    if state is not None:
        for chave in [
            getattr(state, "df_final_key", ""),
            getattr(state, "df_mapeado_key", ""),
            getattr(state, "df_normalizado_key", ""),
            getattr(state, "df_origem_key", ""),
        ]:
            if normalizar_texto(chave):
                df = st.session_state.get(chave)
                if safe_df_dados(df):
                    return df.copy()

    for chave in [
        "df_final",
        "df_saida",
        "df_mapeado",
        "df_precificado",
        "df_calc_precificado",
        "df_normalizado",
        "df_origem",
    ]:
        df = st.session_state.get(chave)
        if safe_df_dados(df):
            return df.copy()

    return pd.DataFrame()


# ============================================================
# FORMATAÇÃO NUMÉRICA
# ============================================================
def to_float_brasil(valor: Any, default: float = 0.0) -> float:
    if valor is None:
        return default

    texto = str(valor).strip()
    if not texto:
        return default

    texto = texto.replace("R$", "").replace(" ", "")

    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(",", ".")

    try:
        return float(texto)
    except Exception:
        return default


def formatar_numero_bling(valor: Any) -> str:
    numero = to_float_brasil(valor, 0.0)
    return f"{numero:.2f}".replace(".", ",")


def formatar_inteiro_seguro(valor: Any, default: int = 0) -> int:
    try:
        numero = to_float_brasil(valor, float(default))
        return int(round(numero))
    except Exception:
        return default


# ============================================================
# MODELO / COLUNAS
# ============================================================
def colunas_modelo_estoque() -> list[str]:
    return [
        "Código",
        "Descrição",
        "Depósito (OBRIGATÓRIO)",
        "Balanço (OBRIGATÓRIO)",
        "Preço unitário (OBRIGATÓRIO)",
        "Situação",
    ]


def colunas_modelo_cadastro() -> list[str]:
    return [
        "Código",
        "Descrição",
        "Descrição Curta",
        "Preço de venda",
        "GTIN/EAN",
        "Situação",
        "URL Imagens",
        "Categoria",
    ]


def obter_colunas_modelo_por_tipo(tipo_operacao_bling: str) -> list[str]:
    if str(tipo_operacao_bling).strip().lower() == "estoque":
        return colunas_modelo_estoque()
    return colunas_modelo_cadastro()


def garantir_colunas_modelo(
    df: pd.DataFrame,
    tipo_operacao_bling: str,
) -> pd.DataFrame:
    base = garantir_dataframe(df)
    colunas = obter_colunas_modelo_por_tipo(tipo_operacao_bling)

    for coluna in colunas:
        if coluna not in base.columns:
            base[coluna] = ""

    base = base[colunas].copy()
    return base.fillna("")


# ============================================================
# VALIDAÇÃO FINAL
# ============================================================
def validar_df_para_download(
    df: pd.DataFrame,
    tipo_operacao_bling: str,
) -> tuple[bool, list[str]]:
    base = garantir_dataframe(df)
    erros: list[str] = []

    if not safe_df_dados(base):
        erros.append("A planilha final está vazia.")
        return False, erros

    tipo = str(tipo_operacao_bling).strip().lower()

    if tipo == "estoque":
        obrigatorias = [
            "Código",
            "Descrição",
            "Depósito (OBRIGATÓRIO)",
            "Balanço (OBRIGATÓRIO)",
            "Preço unitário (OBRIGATÓRIO)",
        ]
    else:
        obrigatorias = [
            "Código",
            "Descrição",
            "Preço de venda",
        ]

    for coluna in obrigatorias:
        if coluna not in base.columns:
            erros.append(f"Coluna obrigatória ausente: {coluna}")
            continue

        vazios = base[coluna].astype(str).str.strip().isin(["", "nan", "None"]).sum()
        if vazios > 0:
            erros.append(f"Coluna obrigatória com valores vazios: {coluna} ({vazios})")

    return len(erros) == 0, erros


# ============================================================
# BLINDAGEM FINAL
# ============================================================
def blindar_df_para_bling(
    df: pd.DataFrame,
    tipo_operacao_bling: str,
    deposito_nome: str = "",
) -> pd.DataFrame:
    base = garantir_dataframe(df)
    tipo = str(tipo_operacao_bling).strip().lower()

    if tipo == "estoque":
        base = garantir_colunas_modelo(base, "estoque")

        if deposito_nome:
            base["Depósito (OBRIGATÓRIO)"] = str(deposito_nome).strip()

        base["Balanço (OBRIGATÓRIO)"] = base["Balanço (OBRIGATÓRIO)"].apply(formatar_inteiro_seguro)
        base["Preço unitário (OBRIGATÓRIO)"] = base["Preço unitário (OBRIGATÓRIO)"].apply(
            formatar_numero_bling
        )

        if "Situação" in base.columns:
            base["Situação"] = base["Situação"].replace("", "Ativo")
            base["Situação"] = base["Situação"].fillna("Ativo")

    else:
        base = garantir_colunas_modelo(base, "cadastro")
        base["Preço de venda"] = base["Preço de venda"].apply(formatar_numero_bling)

        if "Situação" in base.columns:
            base["Situação"] = base["Situação"].replace("", "Ativo")
            base["Situação"] = base["Situação"].fillna("Ativo")

        if "URL Imagens" in base.columns:
            base["URL Imagens"] = (
                base["URL Imagens"]
                .astype(str)
                .str.replace(",", "|", regex=False)
                .str.replace("||", "|", regex=False)
            )

    return base.fillna("")


# ============================================================
# EXPORTAÇÃO
# ============================================================
def dataframe_para_csv_bytes(df: pd.DataFrame) -> bytes:
    base = garantir_dataframe(df).fillna("")
    csv_texto = base.to_csv(index=False, sep=";")
    return csv_texto.encode("utf-8-sig")


# ============================================================
# RESUMO VISUAL
# ============================================================
def _label_etapa(etapa: str) -> str:
    mapa = {
        "ia_orquestrador": "IA Orquestrador",
        "origem": "Origem",
        "normalizacao": "Normalização",
        "precificacao": "Precificação",
        "mapeamento": "Mapeamento",
        "validacao": "Validação",
        "final": "Final",
    }
    return mapa.get(normalizar_texto(etapa).lower(), normalizar_texto(etapa) or "-")


def _status_legivel(status: str) -> str:
    mapa = {
        "idle": "Aguardando",
        "base_pronta": "Base pronta",
        "mapeamento_pronto": "Mapeamento pronto",
        "final_pronto": "Final pronto",
        "revisao": "Em revisão",
        "revisao_final": "Revisão final",
        "sucesso": "Concluído",
        "erro": "Erro",
        "validacao_pendente": "Validação pendente",
    }
    return mapa.get(normalizar_texto(status).lower(), normalizar_texto(status) or "-")


def render_resumo_fluxo() -> None:
    state = _get_agent_state_safe()

    if state is not None:
        etapa = _label_etapa(getattr(state, "etapa_atual", "ia_orquestrador"))
        operacao = normalizar_texto(getattr(state, "operacao", "")) or "-"
        status = _status_legivel(getattr(state, "status_execucao", "idle"))
        simulacao = "Aprovada" if bool(getattr(state, "simulacao_aprovada", False)) else "Pendente"

        st.caption(
            f"Etapa atual: {etapa} | Operação: {operacao} | Status: {status} | Simulação: {simulacao}"
        )
        return

    etapa = st.session_state.get("etapa", "ia_orquestrador")
    tipo_operacao = st.session_state.get("tipo_operacao", "")
    st.caption(
        f"Etapa atual: {_label_etapa(str(etapa))} | Operação: {tipo_operacao if tipo_operacao else '-'}"
        )
    
