from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from bling_app_zero.ui.alerts import render_alert

RESPONSIBLE_FILE = 'bling_app_zero/ui/flow_guard.py'


@dataclass(frozen=True)
class FlowGate:
    """Resultado padronizado de liberação/bloqueio de uma etapa do fluxo."""

    allowed: bool
    message: str = ''
    action_label: str = 'Continuar'


def build_flow_gate(allowed: bool, message: str = '', *, action_label: str = 'Continuar') -> FlowGate:
    return FlowGate(
        allowed=bool(allowed),
        message=str(message or '').strip(),
        action_label=str(action_label or 'Continuar').strip() or 'Continuar',
    )


def render_flow_blocker(message: str, *, title: str = 'Atenção', action_label: str = 'Continuar') -> None:
    """Mostra um bloqueio claro e evita que o usuário veja ação normal liberada."""
    text = str(message or '').strip() or 'Conclua o pré-requisito desta etapa para continuar.'
    render_alert(text, title=title, variant='warning')
    st.caption(f'🔒 {action_label} bloqueado até resolver esta pendência.')


def render_flow_gate(gate: FlowGate, *, title: str = 'Atenção') -> bool:
    """Renderiza o estado da etapa e retorna True quando a ação pode ser exibida."""
    if gate.allowed:
        return True
    render_flow_blocker(gate.message, title=title, action_label=gate.action_label)
    return False


def render_guarded_next_button(
    label: str,
    *,
    allowed: bool,
    pending_message: str,
    key: str,
    use_container_width: bool = True,
) -> bool:
    """Botão de avanço com regra global: se está bloqueado, o botão normal não aparece."""
    gate = build_flow_gate(allowed, pending_message, action_label=label)
    if not render_flow_gate(gate):
        return False
    return bool(st.button(label, use_container_width=use_container_width, key=key))


__all__ = [
    'FlowGate',
    'build_flow_gate',
    'render_flow_blocker',
    'render_flow_gate',
    'render_guarded_next_button',
]
