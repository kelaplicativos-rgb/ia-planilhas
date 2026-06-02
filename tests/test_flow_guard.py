from __future__ import annotations

import importlib


def test_flow_guard_builds_blocked_gate() -> None:
    flow_guard = importlib.import_module('bling_app_zero.ui.flow_guard')

    gate = flow_guard.build_flow_gate(False, 'Falta anexar a planilha.', action_label='Continuar')

    assert gate.allowed is False
    assert gate.message == 'Falta anexar a planilha.'
    assert gate.action_label == 'Continuar'


def test_flow_guard_builds_allowed_gate() -> None:
    flow_guard = importlib.import_module('bling_app_zero.ui.flow_guard')

    gate = flow_guard.build_flow_gate(True, '', action_label='Download')

    assert gate.allowed is True
    assert gate.message == ''
    assert gate.action_label == 'Download'
