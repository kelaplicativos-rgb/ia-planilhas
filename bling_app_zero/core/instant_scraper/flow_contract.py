from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


FlowStatus = Literal[
    "idle",
    "carregando_html",
    "html_carregado",
    "detectando_estruturas",
    "estruturas_detectadas",
    "extraindo",
    "concluido",
    "erro",
]


@dataclass
class InstantFlowState:
    url: str = ""
    status: FlowStatus = "idle"
    erro: str = ""

    total_paginas: int = 0
    total_produtos: int = 0

    modo_runtime: str = "http_only"
    browser_disponivel: bool = False

    candidatos_detectados: int = 0
    candidato_selecionado: int | None = None

    html_chars: int = 0

    def to_dict(self) -> dict:
        return self.__dict__


DEFAULT_STATE = InstantFlowState()


def criar_estado_inicial(url: str) -> InstantFlowState:
    return InstantFlowState(url=url, status="idle")


def atualizar_status(state: InstantFlowState, status: FlowStatus, erro: str = "") -> InstantFlowState:
    state.status = status
    if erro:
        state.erro = erro
    return state


def registrar_html(state: InstantFlowState, html: str) -> InstantFlowState:
    state.html_chars = len(html or "")
    return state


def registrar_candidatos(state: InstantFlowState, total: int) -> InstantFlowState:
    state.candidatos_detectados = total
    return state


def registrar_produtos(state: InstantFlowState, total: int) -> InstantFlowState:
    state.total_produtos = total
    return state
