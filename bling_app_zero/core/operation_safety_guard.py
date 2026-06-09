from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, MutableMapping

try:
    import pandas as pd
except Exception:  # pragma: no cover - pandas existe no app, mas o guard não pode quebrar o boot.
    pd = None  # type: ignore

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/core/operation_safety_guard.py'
SITE_CAPTURE_STUCK_SECONDS = 75
SITE_CAPTURE_HARD_STUCK_SECONDS = 180


@dataclass(frozen=True)
class OperationDecision:
    ok: bool
    message: str = ''
    reason: str = ''
    details: dict[str, Any] | None = None


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or '').strip().lower() in {'1', 'true', 'sim', 'yes', 'on'}


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value or default)
    except Exception:
        return default


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value or default))
    except Exception:
        return default


def _state_get(state: MutableMapping[str, Any], key: str, default: Any = None) -> Any:
    try:
        return state.get(key, default)
    except Exception:
        try:
            return state[key]
        except Exception:
            return default


def _state_pop(state: MutableMapping[str, Any], key: str) -> None:
    try:
        state.pop(key, None)
    except Exception:
        pass


def _state_set(state: MutableMapping[str, Any], key: str, value: Any) -> None:
    try:
        state[key] = value
    except Exception:
        pass


def _looks_like_dataframe_with_rows(value: Any) -> bool:
    if value is None:
        return False
    if pd is not None and isinstance(value, pd.DataFrame):
        return not value.empty
    try:
        return len(value) > 0
    except Exception:
        return False


def _site_has_rows(state: MutableMapping[str, Any], operation: str) -> bool:
    rows = _as_int(_state_get(state, 'site_capture_rows', 0))
    if rows > 0:
        return True
    for key in (
        f'df_site_bruto_{operation}',
        'df_site_bruto',
        'site_capture_df',
        'site_capture_result_df',
    ):
        if _looks_like_dataframe_with_rows(_state_get(state, key)):
            return True
    return False


def _current_operation(state: MutableMapping[str, Any]) -> str:
    for key in (
        'site_capture_operation',
        'direct_bling_operation_choice',
        'direct_bling_operation_applied',
        'active_feature_operation',
        'tipo_operacao_site',
        'operacao_final',
        'tipo_operacao_final',
    ):
        text = str(_state_get(state, key, '') or '').strip().lower()
        if text in {'cadastro', 'estoque', 'atualizacao_preco', 'atualização_preco'}:
            return 'atualizacao_preco' if 'preco' in text or 'preço' in text else text
    return 'site'


def _last_progress_has_real_work(state: MutableMapping[str, Any]) -> bool:
    payload = _state_get(state, 'site_progress_last', {})
    if not isinstance(payload, dict):
        return False
    numeric_keys = (
        'rows',
        'found',
        'urls_found',
        'deep_capture_found_products',
        'processed',
        'scanned_pages',
        'deep_capture_scanned_pages',
        'pages_scanned',
    )
    for key in numeric_keys:
        if _as_int(payload.get(key), 0) > 0:
            return True
    stage = str(payload.get('stage') or '').strip().lower()
    message = str(payload.get('message') or '').strip().lower()
    initial_terms = ('início', 'inicio', 'preparando', 'entrada validada')
    if any(term in stage or term in message for term in initial_terms):
        return False
    meaningful_terms = ('produto localizado', 'extraindo', 'validando', 'resultado salvo', 'leitura encerrada')
    return any(term in stage or term in message for term in meaningful_terms)


def recover_stuck_site_capture(state: MutableMapping[str, Any] | None = None, *, max_age_seconds: int = SITE_CAPTURE_STUCK_SECONDS) -> OperationDecision:
    """Destrava captura por site que ficou em running sem linhas.

    O diagnóstico 74 mostrou o estado clássico de falha:
    running=True, rows=0, finished=False, result_ready=False e apenas
    `site_panel_running_guard_rendered` nos reruns. Este guard corta esse loop
    automaticamente sem apagar dados válidos já capturados.
    """
    if state is None:
        try:
            import streamlit as st

            state = st.session_state
        except Exception:
            return OperationDecision(True, reason='sem_streamlit')

    if not _as_bool(_state_get(state, 'site_capture_running', False)):
        return OperationDecision(True, reason='sem_captura_rodando')

    operation = _current_operation(state)
    if _site_has_rows(state, operation):
        _state_set(state, 'site_capture_running', False)
        _state_set(state, 'site_capture_finished', True)
        _state_set(state, 'site_capture_result_ready', True)
        return OperationDecision(True, reason='resultado_existente_preservado')

    started_at = _as_float(_state_get(state, 'site_capture_started_at', 0.0))
    age = max(0.0, time.time() - started_at) if started_at > 0 else float(max_age_seconds + 1)
    rows = _as_int(_state_get(state, 'site_capture_rows', 0))
    finished = _as_bool(_state_get(state, 'site_capture_finished', False))
    result_ready = _as_bool(_state_get(state, 'site_capture_result_ready', False))
    has_real_progress = _last_progress_has_real_work(state)

    if age < max_age_seconds:
        return OperationDecision(True, reason='captura_dentro_da_janela', details={'age_seconds': round(age, 2)})

    if has_real_progress and age < SITE_CAPTURE_HARD_STUCK_SECONDS:
        return OperationDecision(True, reason='progresso_real_preservado', details={'age_seconds': round(age, 2)})

    if rows <= 0 and not finished and not result_ready:
        for key in (
            f'df_site_bruto_{operation}',
            'df_site_bruto',
            'site_capture_df',
            'site_capture_result_df',
            'direct_bling_api_contract_df',
        ):
            _state_pop(state, key)
        _state_set(state, 'site_capture_running', False)
        _state_set(state, 'site_capture_status', 'interrompida_preventivamente')
        _state_set(state, 'site_capture_finished', False)
        _state_set(state, 'site_capture_result_ready', False)
        _state_set(state, 'site_capture_rows', 0)
        _state_set(state, 'site_capture_columns', 0)
        _state_set(
            state,
            'site_capture_error',
            'A busca por site ficou sem resultado e foi destravada automaticamente. Rode novamente com lote menor ou use Site protegido/colagem manual.',
        )
        _state_set(state, 'site_capture_preventive_unlocked_at', time.time())
        add_audit_event(
            'operation_safety_guard_unlocked_stuck_site_capture',
            area='SITE',
            step='entrada',
            status='AVISO',
            details={
                'operation': operation,
                'age_seconds': round(age, 2),
                'rows': rows,
                'finished': finished,
                'result_ready': result_ready,
                'max_age_seconds': max_age_seconds,
                'hard_stuck_seconds': SITE_CAPTURE_HARD_STUCK_SECONDS,
                'reason': 'running_sem_linhas_sem_finalizacao',
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
        return OperationDecision(
            False,
            message='A busca anterior ficou presa e foi destravada automaticamente. Execute novamente; o sistema não enviará dados vazios ao Bling.',
            reason='site_capture_stuck_unlocked',
            details={'operation': operation, 'age_seconds': round(age, 2)},
        )

    return OperationDecision(True, reason='estado_nao_bloqueante')


def require_rows_before_api(state: MutableMapping[str, Any] | None = None, *, operation: str | None = None) -> OperationDecision:
    """Bloqueia envio API quando a origem site/contrato direto não tem linhas."""
    if state is None:
        try:
            import streamlit as st

            state = st.session_state
        except Exception:
            return OperationDecision(True, reason='sem_streamlit')

    op = operation or _current_operation(state)
    finish_mode = str(_state_get(state, 'bling_finish_mode', '') or '').strip().lower()
    direct_contract = _as_bool(_state_get(state, 'direct_bling_api_contract_active', False))
    is_api_flow = finish_mode == 'api_direct' or direct_contract or _as_bool(_state_get(state, 'send_to_bling', False))
    if not is_api_flow:
        return OperationDecision(True, reason='nao_api')
    if _site_has_rows(state, op):
        return OperationDecision(True, reason='linhas_ok')
    add_audit_event(
        'operation_safety_guard_blocked_empty_api_send',
        area='BLING_API',
        step='preflight',
        status='BLOQUEADO',
        details={'operation': op, 'reason': 'origem_sem_linhas', 'responsible_file': RESPONSIBLE_FILE},
    )
    return OperationDecision(
        False,
        message='Envio ao Bling bloqueado: a origem não tem produtos capturados. Faça a busca por site novamente antes de enviar.',
        reason='api_sem_linhas',
        details={'operation': op},
    )


def install_preventive_operation_guard(state: MutableMapping[str, Any] | None = None) -> OperationDecision:
    decision = recover_stuck_site_capture(state)
    return decision


__all__ = [
    'OperationDecision',
    'install_preventive_operation_guard',
    'recover_stuck_site_capture',
    'require_rows_before_api',
]
