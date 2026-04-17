
from __future__ import annotations

from datetime import datetime
import re
import unicodedata
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


def render_debug_panel(titulo: str = "Debug do sistema") -> None:
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
                if st.button("Limpar log", use_container_width=True):
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
    return texto == "" or texto.lower() in {"nan", "none", "nat", ""}


def normalizar_texto(valor: Any) -> str:
    if _valor_vazio(valor):
        return ""
    return str(valor).strip()


def _remover_acentos(texto: str) -> str:
    texto_nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(ch for ch in texto_nfkd if not unicodedata.combining(ch))


def normalizar_coluna_busca(valor: Any) -> str:
    texto = normalizar_texto(valor).lower()
    texto = _remover_acentos(texto)
    texto = re.sub(r"[_\-/().]+", " ", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def safe_lower(valor: Any) -> str:
    return normalizar_texto(valor).lower()


# ============================================================
# DATAFRAME / ESTADO
# ============================================================

def safe_df(df: Any) -> pd.DataFrame:
    if isinstance(df, pd.DataFrame):
        return df.copy()
    return pd.DataFrame()


def safe_df_dados(df: Any) -> bool:
    return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0


def safe_df_estrutura(df: Any) -> bool:
    return isinstance(df, pd.DataFrame) and len(df.columns) > 0


def garantir_dataframe(df: Any) -> pd.DataFrame:
    if isinstance(df, pd.DataFrame):
        return df.copy()
    return pd.DataFrame()


# ============================================================
# AGENT MEMORY SAFE
# ============================================================

def _agent_state_disponivel() -> bool:
    try:
        import bling_app_zero.agent.agent_memory  # noqa: F401
        return True
    except Exception:
        return False


def get_agent_state_safe():
    if not _agent_state_disponivel():
        return None

    try:
        from bling_app_zero.agent.agent_memory import get_agent_state
        return get_agent_state()
    except Exception:
        return None


def _safe_save_agent_state(state) -> None:
    if state is None:
        return

    try:
        from bling_app_zero.agent.agent_memory import save_agent_state
        save_agent_state(state)
    except Exception:
        pass


def _safe_set_agent_stage(etapa: str) -> None:
    state = get_agent_state_safe()
    if state is None:
        return

    etapa_limpa = normalizar_texto(etapa) or "origem"
    state.etapa_atual = etapa_limpa

    if etapa_limpa == "preview_final":
        state.status_execucao = "final_pronto"
    elif etapa_limpa == "mapeamento":
        state.status_execucao = "mapeamento_pronto"
    elif etapa_limpa == "precificacao":
        if normalizar_texto(getattr(state, "status_execucao", "")) == "":
            state.status_execucao = "base_pronta"
    elif etapa_limpa == "origem":
        if normalizar_texto(getattr(state, "status_execucao", "")) == "":
            state.status_execucao = "idle"

    _safe_save_agent_state(state)


# ============================================================
# NAVEGAÇÃO / ETAPAS
# ============================================================

ETAPAS_VALIDAS = [
    "origem",
    "precificacao",
    "mapeamento",
    "preview_final",
]

MAPA_ETAPA_ANTERIOR = {
    "origem": "origem",
    "precificacao": "origem",
    "mapeamento": "precificacao",
    "preview_final": "mapeamento",
}

MAPA_LABEL_ETAPA = {
    "origem": "Origem",
    "precificacao": "Precificação",
    "mapeamento": "Mapeamento",
    "preview_final": "Preview final",
}


def _normalizar_etapa_fluxo(etapa: str | None) -> str:
    etapa_limpa = normalizar_texto(etapa).lower()
    if etapa_limpa in ETAPAS_VALIDAS:
        return etapa_limpa
    return "origem"


def _set_query_param_etapa(etapa: str) -> None:
    etapa = _normalizar_etapa_fluxo(etapa)

    try:
        st.query_params["etapa"] = etapa
        return
    except Exception:
        pass

    try:
        st.experimental_set_query_params(etapa=etapa)
    except Exception:
        pass


def _get_query_param_etapa() -> str:
    try:
        valor = st.query_params.get("etapa", "")
        if isinstance(valor, list):
            valor = valor[0] if valor else ""
        return _normalizar_etapa_fluxo(str(valor))
    except Exception:
        pass

    try:
        params = st.experimental_get_query_params()
        valor = params.get("etapa", [""])
        if isinstance(valor, list):
            valor = valor[0] if valor else ""
        return _normalizar_etapa_fluxo(str(valor))
    except Exception:
        return "origem"


def _garantir_etapa_historico() -> None:
    if "etapa_historico" not in st.session_state or not isinstance(
        st.session_state.get("etapa_historico"),
        list,
    ):
        st.session_state["etapa_historico"] = []


def _registrar_historico_etapa(etapa_anterior: str, etapa_nova: str) -> None:
    _garantir_etapa_historico()

    etapa_anterior = _normalizar_etapa_fluxo(etapa_anterior)
    etapa_nova = _normalizar_etapa_fluxo(etapa_nova)

    if etapa_anterior == etapa_nova:
        return

    historico = st.session_state["etapa_historico"]

    if not historico or historico[-1] != etapa_anterior:
        historico.append(etapa_anterior)

    st.session_state["etapa_historico"] = historico[-20:]


def sincronizar_etapa_global(etapa: str) -> None:
    etapa_limpa = _normalizar_etapa_fluxo(etapa)

    st.session_state["etapa"] = etapa_limpa
    st.session_state["etapa_origem"] = etapa_limpa
    st.session_state["etapa_fluxo"] = etapa_limpa

    _safe_set_agent_stage(etapa_limpa)


def get_etapa() -> str:
    etapa = st.session_state.get("etapa", "")
    return _normalizar_etapa_fluxo(str(etapa))


def set_etapa(etapa: str, registrar_historico: bool = True) -> None:
    etapa_nova = _normalizar_etapa_fluxo(etapa)
    etapa_atual = get_etapa()

    if registrar_historico:
        _registrar_historico_etapa(etapa_atual, etapa_nova)

    sincronizar_etapa_global(etapa_nova)
    _set_query_param_etapa(etapa_nova)
    st.session_state["_etapa_url_inicializada"] = True
    st.session_state["_ultima_etapa_sincronizada_url"] = etapa_nova


def sincronizar_etapa_da_url() -> None:
    """
    Regra importante:
    - na primeira carga, se vier ?etapa=... pela URL, respeita
    - depois disso, em reruns normais do Streamlit (number_input, selectbox etc),
      nunca deixar a URL antiga derrubar a etapa atual do session_state
    - se não houver etapa definida ainda, inicializa com a URL ou com 'origem'
    """
    etapa_state = get_etapa()
    etapa_url = _get_query_param_etapa()

    if "_etapa_url_inicializada" not in st.session_state:
        st.session_state["_etapa_url_inicializada"] = False

    if "_ultima_etapa_sincronizada_url" not in st.session_state:
        st.session_state["_ultima_etapa_sincronizada_url"] = etapa_state or "origem"

    primeira_carga = not bool(st.session_state.get("_etapa_url_inicializada", False))

    if primeira_carga:
        etapa_inicial = etapa_url if etapa_url in ETAPAS_VALIDAS else etapa_state
        etapa_inicial = _normalizar_etapa_fluxo(etapa_inicial or "origem")

        sincronizar_etapa_global(etapa_inicial)
        _set_query_param_etapa(etapa_inicial)

        st.session_state["_etapa_url_inicializada"] = True
        st.session_state["_ultima_etapa_sincronizada_url"] = etapa_inicial
        return

    if etapa_state not in ETAPAS_VALIDAS:
        etapa_state = "origem"
        sincronizar_etapa_global(etapa_state)

    ultima_url_sync = _normalizar_etapa_fluxo(
        st.session_state.get("_ultima_etapa_sincronizada_url", etapa_state)
    )

    if etapa_url != etapa_state:
        if etapa_url != ultima_url_sync:
            sincronizar_etapa_global(etapa_url)
            st.session_state["_ultima_etapa_sincronizada_url"] = etapa_url
            return

        _set_query_param_etapa(etapa_state)
        st.session_state["_ultima_etapa_sincronizada_url"] = etapa_state
        return

    st.session_state["_ultima_etapa_sincronizada_url"] = etapa_state


def ir_para_etapa(etapa: str) -> None:
    etapa_nova = _normalizar_etapa_fluxo(etapa)
    set_etapa(etapa_nova, registrar_historico=True)
    st.rerun()


def voltar_para_etapa(etapa: str) -> None:
    etapa_nova = _normalizar_etapa_fluxo(etapa)
    set_etapa(etapa_nova, registrar_historico=False)
    st.rerun()


def voltar_etapa_anterior() -> None:
    _garantir_etapa_historico()

    historico = st.session_state.get("etapa_historico", [])
    etapa_atual = get_etapa()

    if historico:
        etapa_destino = _normalizar_etapa_fluxo(historico.pop())
        st.session_state["etapa_historico"] = historico
    else:
        etapa_destino = MAPA_ETAPA_ANTERIOR.get(etapa_atual, "origem")

    set_etapa(etapa_destino, registrar_historico=False)
    st.rerun()


def render_topo_navegacao() -> None:
    etapa_atual = get_etapa()

    colunas = st.columns(len(ETAPAS_VALIDAS))
    for idx, etapa in enumerate(ETAPAS_VALIDAS):
        label = MAPA_LABEL_ETAPA.get(etapa, etapa.title())
        ativo = etapa == etapa_atual
        texto = f"➡️ {label}" if ativo else label

        with colunas[idx]:
            if st.button(
                texto,
                key=f"topo_nav_{etapa}",
                use_container_width=True,
                disabled=False,
            ):
                ir_para_etapa(etapa)


def render_topo_status_fluxo() -> None:
    etapa = get_etapa()
    operacao = normalizar_texto(st.session_state.get("tipo_operacao", "")) or "-"
    origem_ok = "Sim" if safe_df_dados(st.session_state.get("df_origem")) else "Não"
    modelo_ok = "Sim" if safe_df_estrutura(st.session_state.get("df_modelo")) else "Não"
    final_ok = "Sim" if safe_df_estrutura(st.session_state.get("df_final")) else "Não"

    st.caption(
        " | ".join(
            [
                f"Etapa: {MAPA_LABEL_ETAPA.get(etapa, etapa)}",
                f"Operação: {operacao}",
                f"Origem: {origem_ok}",
                f"Modelo: {modelo_ok}",
                f"Final: {final_ok}",
            ]
        )
    )


# ============================================================
# LIMPEZA DE FLUXO
# ============================================================

def _limpar_chaves_estado(chaves: list[str]) -> None:
    for chave in chaves:
        st.session_state.pop(chave, None)


def limpar_estado_fluxo() -> None:
    _limpar_chaves_estado(
        [
            "df_origem",
            "df_normalizado",
            "df_precificado",
            "df_mapeado",
            "df_saida",
            "df_final",
            "df_calc_precificado",
            "df_preview_mapeamento",
            "df_modelo",
            "origem_upload_nome",
            "origem_upload_bytes",
            "origem_upload_tipo",
            "origem_upload_ext",
            "modelo_upload_nome",
            "modelo_upload_bytes",
            "modelo_upload_tipo",
            "modelo_upload_ext",
            "site_fornecedor_url",
            "site_fornecedor_diagnostico",
            "site_busca_diagnostico_df",
            "site_busca_diagnostico_total_descobertos",
            "site_busca_diagnostico_total_validos",
            "site_busca_diagnostico_total_rejeitados",
            "pricing_df_preview",
            "mapping_manual",
            "mapping_sugerido",
            "etapa_historico",
            "_etapa_url_inicializada",
            "_ultima_etapa_sincronizada_url",
        ]
    )

    for chave in [
        "mapping_origem",
        "mapping_origem_rascunho",
        "mapping_origem_defaults",
    ]:
        st.session_state[chave] = {}

    for chave in [
        "ia_plano_preview",
        "ia_erro_execucao",
    ]:
        st.session_state[chave] = ""

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

    sincronizar_etapa_global("origem")
    _set_query_param_etapa("origem")


def obter_df_fluxo_preferencial() -> pd.DataFrame:
    state = get_agent_state_safe()

    if state is not None:
        for chave in [
            getattr(state, "df_final_key", ""),
            getattr(state, "df_mapeado_key", ""),
            getattr(state, "df_normalizado_key", ""),
            getattr(state, "df_origem_key", ""),
        ]:
            chave_limpa = normalizar_texto(chave)
            if not chave_limpa:
                continue

            df = st.session_state.get(chave_limpa)
            if safe_df_dados(df):
                return garantir_dataframe(df)

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
            return garantir_dataframe(df)

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

    texto = re.sub(r"[^0-9.\-]", "", texto)

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
# GTIN / IMAGENS / LIMPEZAS FINAIS
# ============================================================

def _somente_digitos(valor: Any) -> str:
    return re.sub(r"\D+", "", normalizar_texto(valor))


def _gtin_checksum_valido(gtin: str) -> bool:
    if not gtin.isdigit() or len(gtin) not in {8, 12, 13, 14}:
        return False

    digitos = [int(d) for d in gtin]
    digito_verificador = digitos[-1]
    corpo = digitos[:-1][::-1]

    total = 0
    for indice, digito in enumerate(corpo, start=1):
        peso = 3 if indice % 2 == 1 else 1
        total += digito * peso

    calculado = (10 - (total % 10)) % 10
    return calculado == digito_verificador


def limpar_gtin_invalido(valor: Any) -> str:
    gtin = _somente_digitos(valor)
    if _gtin_checksum_valido(gtin):
        return gtin
    return ""


def normalizar_imagens_pipe(valor: Any) -> str:
    texto = normalizar_texto(valor)
    if not texto:
        return ""

    texto = texto.replace("\n", "|").replace(";", "|")
    texto = re.sub(r"\s*\|\s*", "|", texto)
    texto = re.sub(r",(?=https?://)", "|", texto)
    texto = re.sub(r"\|+", "|", texto)

    partes = [p.strip() for p in texto.strip("| ").split("|") if p.strip()]
    vistos = set()
    saida = []

    for parte in partes:
        if parte not in vistos:
            vistos.add(parte)
            saida.append(parte)

    return "|".join(saida)


def normalizar_situacao(valor: Any, default: str = "Ativo") -> str:
    texto = normalizar_texto(valor)
    return texto if texto else default


# ============================================================
# MODELO / COLUNAS
# ============================================================

def _label_etapa(etapa: str) -> str:
    return MAPA_LABEL_ETAPA.get(_normalizar_etapa_fluxo(etapa), normalizar_texto(etapa) or "-")


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
    state = get_agent_state_safe()

    if state is not None:
        etapa = _label_etapa(getattr(state, "etapa_atual", "origem"))
        operacao = normalizar_texto(getattr(state, "operacao", "")) or "-"
        status = _status_legivel(getattr(state, "status_execucao", "idle"))
        simulacao = "Aprovada" if bool(getattr(state, "simulacao_aprovada", False)) else "Pendente"

        st.caption(
            f"Etapa atual: {etapa} | Operação: {operacao} | Status: {status} | Simulação: {simulacao}"
        )
        return

    etapa = get_etapa()
    tipo_operacao = st.session_state.get("tipo_operacao", "")

    st.caption(
        f"Etapa atual: {_label_etapa(str(etapa))} | Operação: {tipo_operacao if tipo_operacao else '-'}"
    )
    
