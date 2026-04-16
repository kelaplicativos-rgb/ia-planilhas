
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

import streamlit as st


SESSION_KEY_AGENT_STATE = "agent_run_state"


@dataclass
class AgentRunState:
    origem_tipo: Optional[str] = None
    fornecedor: Optional[str] = None
    operacao: Optional[str] = None
    deposito_nome: Optional[str] = None
    modelo_nome: Optional[str] = None

    df_origem_key: Optional[str] = "df_origem"
    df_normalizado_key: Optional[str] = "df_normalizado"
    df_mapeado_key: Optional[str] = "df_mapeado"
    df_precificado_key: Optional[str] = "df_precificado"
    df_final_key: Optional[str] = "df_final"

    etapa_atual: str = "origem"
    status_execucao: str = "idle"

    pendencias: List[str] = field(default_factory=list)
    avisos: List[str] = field(default_factory=list)
    erros: List[str] = field(default_factory=list)
    logs: List[str] = field(default_factory=list)

    mapping_salvo: Dict[str, str] = field(default_factory=dict)
    defaults_aplicados: Dict[str, Any] = field(default_factory=dict)
    metricas: Dict[str, Any] = field(default_factory=dict)

    arquivo_saida_nome: Optional[str] = None
    simulacao_aprovada: bool = False

    def add_log(self, mensagem: str) -> None:
        texto = (mensagem or "").strip()
        if not texto:
            return
        self.logs.append(texto)

    def add_pendencia(self, mensagem: str) -> None:
        texto = (mensagem or "").strip()
        if texto and texto not in self.pendencias:
            self.pendencias.append(texto)

    def add_aviso(self, mensagem: str) -> None:
        texto = (mensagem or "").strip()
        if texto and texto not in self.avisos:
            self.avisos.append(texto)

    def add_erro(self, mensagem: str) -> None:
        texto = (mensagem or "").strip()
        if texto and texto not in self.erros:
            self.erros.append(texto)

    def clear_erros(self) -> None:
        self.erros = []

    def clear_avisos(self) -> None:
        self.avisos = []

    def clear_pendencias(self) -> None:
        self.pendencias = []

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "AgentRunState":
        if not isinstance(payload, dict):
            return cls()
        campos_validos = {field_name for field_name in cls.__dataclass_fields__.keys()}
        filtrado = {k: v for k, v in payload.items() if k in campos_validos}
        return cls(**filtrado)


def _ensure_state() -> AgentRunState:
    payload = st.session_state.get(SESSION_KEY_AGENT_STATE)

    if isinstance(payload, AgentRunState):
        return payload

    if isinstance(payload, dict):
        state = AgentRunState.from_dict(payload)
        st.session_state[SESSION_KEY_AGENT_STATE] = state
        return state

    state = AgentRunState()
    st.session_state[SESSION_KEY_AGENT_STATE] = state
    return state


def get_agent_state() -> AgentRunState:
    return _ensure_state()


def save_agent_state(state: AgentRunState) -> None:
    st.session_state[SESSION_KEY_AGENT_STATE] = state


def reset_agent_state(
    preserve_dataframe_keys: bool = True,
    preserve_operacao: bool = True,
    preserve_deposito: bool = True,
) -> AgentRunState:
    atual = get_agent_state()

    novo = AgentRunState()

    if preserve_dataframe_keys:
        novo.df_origem_key = atual.df_origem_key
        novo.df_normalizado_key = atual.df_normalizado_key
        novo.df_mapeado_key = atual.df_mapeado_key
        novo.df_precificado_key = atual.df_precificado_key
        novo.df_final_key = atual.df_final_key

    if preserve_operacao:
        novo.operacao = atual.operacao
        novo.modelo_nome = atual.modelo_nome

    if preserve_deposito:
        novo.deposito_nome = atual.deposito_nome

    st.session_state[SESSION_KEY_AGENT_STATE] = novo
    return novo


def update_agent_state(**kwargs: Any) -> AgentRunState:
    state = get_agent_state()
    for chave, valor in kwargs.items():
        if hasattr(state, chave):
            setattr(state, chave, valor)
    save_agent_state(state)
    return state


def sync_agent_with_session() -> AgentRunState:
    """
    Faz a ponte entre o novo agente e as chaves históricas do projeto.
    """
    state = get_agent_state()

    operacao = st.session_state.get("tipo_operacao") or st.session_state.get("operacao")
    deposito = st.session_state.get("deposito_nome")
    fornecedor = st.session_state.get("fornecedor_nome") or st.session_state.get("fornecedor_detectado")

    if operacao:
        state.operacao = str(operacao).strip().lower()

    if deposito:
        state.deposito_nome = str(deposito).strip()

    if fornecedor:
        state.fornecedor = str(fornecedor).strip()

    for chave_df in [
        "df_origem",
        "df_normalizado",
        "df_mapeado",
        "df_precificado",
        "df_final",
    ]:
        if chave_df in st.session_state:
            setattr(state, f"{chave_df}_key", chave_df)

    save_agent_state(state)
    return state


def get_agent_snapshot() -> Dict[str, Any]:
    return get_agent_state().to_dict()
  
