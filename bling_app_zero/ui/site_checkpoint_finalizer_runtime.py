from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/site_checkpoint_finalizer_runtime.py'
_PATCH_KEY = 'site_checkpoint_finalizer_runtime_installed_v2'
MIN_ROWS_TO_FINALIZE_WITHOUT_EXACT_TOTAL = 1


@dataclass(frozen=True)
class CheckpointCompletion:
    action: str
    complete: bool
    rows: int
    expected_total: int
    pending_urls: int
    processed_urls: int
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            'action': self.action,
            'complete': self.complete,
            'rows': self.rows,
            'expected_total': self.expected_total,
            'pending_urls': self.pending_urls,
            'processed_urls': self.processed_urls,
            'reason': self.reason,
        }


def _normalize_operation(operation: object) -> str:
    text = str(operation or '').strip().lower()
    if text in {'cadastro', 'produto', 'produtos', 'cadastro_produto', 'cadastro_produtos'}:
        return 'cadastro'
    if text in {'estoque', 'stock', 'saldo', 'saldos', 'atualizacao_estoque', 'atualização de estoque'}:
        return 'estoque'
    if text in {'preco', 'preço', 'atualizacao_preco', 'atualização de preço'}:
        return 'atualizacao_preco'
    if text in {'universal', 'modelo', 'modelo_destino', 'planilha', 'wizard_cadastro_estoque'}:
        return 'universal'
    return text or 'universal'


def _as_dict(value: object) -> dict:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_int(value: object) -> int:
    try:
        return int(float(value or 0))
    except Exception:
        return 0


def _list_len(value: object) -> int:
    if isinstance(value, str):
        return 1 if value.strip() else 0
    if isinstance(value, list | tuple | set):
        return len([item for item in value if str(item or '').strip()])
    return 0


def _payload_expected_total(payload: Mapping[str, object], rows: int) -> int:
    candidates = (
        'partial_checkpoint_expected_total',
        'expected_total',
        'total_products',
        'total_produtos',
        'urls_found',
        'deep_capture_found_products',
        'partial_checkpoint_found',
        'found',
        'rows',
    )
    total = 0
    for key in candidates:
        total = max(total, _as_int(payload.get(key)))
    return max(total, rows)


def _payload_pending_count(payload: Mapping[str, object]) -> int:
    pending = 0
    for key in ('partial_checkpoint_pending_urls', 'pending_urls', 'site_checkpoint_pending_urls'):
        pending = max(pending, _list_len(payload.get(key)))
    return pending


def _payload_processed_count(payload: Mapping[str, object]) -> int:
    processed = 0
    for key in ('partial_checkpoint_processed_urls', 'processed_urls', 'site_checkpoint_processed_urls'):
        processed = max(processed, _list_len(payload.get(key)))
    return processed


def analyze_checkpoint_completion(operation: str, *, requested_columns: list[str] | None = None) -> tuple[CheckpointCompletion, pd.DataFrame | None]:
    operation = _normalize_operation(operation)
    try:
        from bling_app_zero.ui.site_resume_state import checkpoint_df, checkpoint_payload
        payload = _as_dict(checkpoint_payload(operation))
        df = checkpoint_df(operation, requested_columns=requested_columns)
    except Exception as exc:
        decision = CheckpointCompletion('retomar', False, 0, 0, 0, 0, f'checkpoint_indisponivel: {exc}')
        return decision, None

    rows = len(df) if isinstance(df, pd.DataFrame) else 0
    expected_total = _payload_expected_total(payload, rows)
    pending_urls = _payload_pending_count(payload)
    processed_urls = _payload_processed_count(payload)

    if rows <= 0:
        return CheckpointCompletion('retomar', False, rows, expected_total, pending_urls, processed_urls, 'sem_linhas_no_checkpoint'), df

    if pending_urls > 0 and rows < expected_total:
        return CheckpointCompletion('retomar', False, rows, expected_total, pending_urls, processed_urls, 'ainda_tem_urls_pendentes_e_quantidade_incompleta'), df

    if expected_total > 0 and rows >= expected_total:
        return CheckpointCompletion('montar_origem', True, rows, expected_total, pending_urls, processed_urls, 'quantidade_exata_atingida'), df

    if pending_urls == 0 and rows >= MIN_ROWS_TO_FINALIZE_WITHOUT_EXACT_TOTAL:
        return CheckpointCompletion('montar_origem', True, rows, expected_total, pending_urls, processed_urls, 'sem_pendencias_visiveis_checkpoint_suficiente'), df

    return CheckpointCompletion('retomar', False, rows, expected_total, pending_urls, processed_urls, 'quantidade_incompleta'), df


def _capture_context(raw_urls: str, operation: str) -> dict[str, object]:
    return {
        'url': str(raw_urls or ''),
        'operation': operation,
        'mode': operation,
        'api_mode': bool(st.session_state.get('api_flow_active')),
        'send_to_bling': bool(st.session_state.get('api_flow_active')),
        'source': 'checkpoint_finalizer',
    }


def _mirror_origin_keys(operation: str, df: pd.DataFrame) -> None:
    clean = df.copy().fillna('')
    st.session_state['df_site_bruto'] = clean
    st.session_state[f'df_site_bruto_{operation}'] = clean
    st.session_state['df_origem_unificada'] = clean
    st.session_state['df_origem_site'] = clean
    st.session_state['df_origem_site_como_planilha'] = clean
    st.session_state[f'df_origem_site_como_planilha_{operation}'] = clean
    st.session_state['origem_final'] = 'site'
    st.session_state['origem_dados'] = 'site'
    st.session_state['origem_tipo'] = 'site'
    st.session_state['origem_planilha_via_site'] = True
    st.session_state['site_gerou_origem_planilha'] = True
    st.session_state['operation_site'] = operation
    st.session_state['tipo_operacao_site'] = operation
    st.session_state['operacao_final'] = operation
    st.session_state['tipo_operacao_final'] = operation
    st.session_state['home_slim_flow_origin'] = 'site'
    st.session_state['home_slim_flow_operation'] = operation
    if operation == 'universal':
        st.session_state['mapeiaai_universal_source_df'] = clean
        st.session_state['mapeiaai_universal_source_kind'] = 'site'


def finalize_checkpoint_as_site_origin(
    operation: str = 'universal',
    *,
    requested_columns: list[str] | None = None,
    raw_urls: str = '',
    df_modelo_cadastro: pd.DataFrame | None = None,
    df_modelo_estoque: pd.DataFrame | None = None,
    df_modelo: pd.DataFrame | None = None,
    reason: str = 'checkpoint_finalizer',
    show_message: bool = False,
    require_complete: bool = True,
) -> pd.DataFrame | None:
    """Transforma checkpoint em Origem dos dados somente quando a busca está completa.

    Primeiro compara linhas capturadas, total esperado e URLs pendentes. Se ainda
    faltarem produtos, agenda retomada. O modelo anexado não decide se a origem
    existe; ele só orienta o mapeamento final.
    """
    operation = _normalize_operation(operation)
    completion, df = analyze_checkpoint_completion(operation, requested_columns=requested_columns)
    st.session_state[f'site_checkpoint_completion_{operation}'] = completion.to_dict()

    add_audit_event(
        'site_checkpoint_completion_analyzed',
        area='SITE',
        step='entrada',
        status='OK' if completion.complete else 'AVISO',
        details={'operation': operation, 'analysis': completion.to_dict(), 'reason': reason, 'responsible_file': RESPONSIBLE_FILE},
    )

    if require_complete and not completion.complete:
        try:
            from bling_app_zero.ui.site_resume_state import request_resume
            request_resume(operation, f'Checkpoint incompleto: {completion.reason}. Retomar antes de montar origem.')
        except Exception:
            pass
        st.session_state['site_capture_running'] = False
        st.session_state['site_capture_finished'] = False
        st.session_state['site_capture_result_ready'] = False
        st.session_state['site_capture_error'] = ''
        if show_message:
            st.info(f'Checkpoint parcial: {completion.rows}/{completion.expected_total or "?"} produto(s). Ainda faltam produtos; retomando a busca antes de montar a origem.')
        return None

    if not isinstance(df, pd.DataFrame) or df.empty:
        add_audit_event(
            'site_checkpoint_finalizer_empty_checkpoint',
            area='SITE',
            step='entrada',
            status='AVISO',
            details={'operation': operation, 'analysis': completion.to_dict(), 'reason': reason, 'responsible_file': RESPONSIBLE_FILE},
        )
        return None

    clean = df.copy().fillna('')
    raw_urls = str(raw_urls or st.session_state.get(f'site_capture_raw_urls_{operation}') or st.session_state.get('site_capture_raw_urls') or '').strip()

    try:
        from bling_app_zero.ui.site_outputs import save_site_source
        save_site_source(clean, raw_urls, requested_columns, df_modelo_cadastro, df_modelo_estoque, df_modelo, operation)
    except Exception as exc:
        add_audit_event(
            'site_checkpoint_finalizer_save_site_source_failed_but_mirrored',
            area='SITE',
            step='entrada',
            status='AVISO',
            details={'operation': operation, 'error': str(exc)[:240], 'reason': reason, 'responsible_file': RESPONSIBLE_FILE},
        )

    try:
        from bling_app_zero.ui.site_panel_state import set_capture_state, store_site_df
        store_site_df(operation, clean)
        set_capture_state(operation=operation, running=False, finished=True, error='', rows=len(clean), columns=len(clean.columns))
    except Exception:
        st.session_state['site_capture_running'] = False
        st.session_state['site_capture_finished'] = True
        st.session_state['site_capture_error'] = ''
        st.session_state['site_capture_result_ready'] = True
        st.session_state['site_capture_operation'] = operation
        st.session_state['site_capture_rows'] = len(clean)
        st.session_state['site_capture_columns'] = len(clean.columns)

    _mirror_origin_keys(operation, clean)

    try:
        from bling_app_zero.adapters.streamlit_site_capture_adapter import finish_site_capture
        finish_site_capture(
            clean,
            _capture_context(raw_urls, operation),
            report_key=f'blingsmartscan_checkpoint_report_{operation}',
            message=f'Origem montada automaticamente a partir do checkpoint completo: {len(clean)} produto(s).',
        )
    except Exception:
        pass

    try:
        from bling_app_zero.ui.site_resume_state import clear_checkpoint, clear_resume_request
        clear_resume_request(reset_attempts=True)
        clear_checkpoint(operation)
    except Exception:
        pass

    st.session_state['blingsmartscan_manual_continue_required'] = True
    st.session_state['blingsmartscan_ready_to_continue'] = True
    st.session_state['blingsmartscan_finished_operation'] = operation
    st.session_state['blingsmartscan_finished_rows'] = int(len(clean))
    st.session_state['blingsmartscan_finished_columns'] = int(len(clean.columns))
    st.session_state['blingsmartscan_last_notice'] = {
        'title': 'Origem montada do checkpoint completo.',
        'rows': int(len(clean)),
        'warnings': ['A busca caiu/pausou, mas o checkpoint completo foi preservado como origem de dados.'],
        'analysis': completion.to_dict(),
    }
    st.session_state[f'blingsmartscan_notice_{operation}'] = st.session_state['blingsmartscan_last_notice']

    add_audit_event(
        'site_checkpoint_finalized_as_origin',
        area='SITE',
        step='entrada',
        status='CORRIGIDO',
        details={
            'operation': operation,
            'rows': int(len(clean)),
            'columns': int(len(clean.columns)),
            'analysis': completion.to_dict(),
            'reason': reason,
            'raw_urls_present': bool(raw_urls),
            'independent_of_model': True,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    if show_message:
        st.success(f'Origem montada automaticamente com {len(clean)} produto(s), após confirmar que a quantidade capturada estava completa.')
    return clean


def _should_try_finalize_before_render(operation: str) -> bool:
    try:
        from bling_app_zero.ui.site_panel_state import get_site_df
        current = get_site_df(operation)
        if isinstance(current, pd.DataFrame) and not current.empty:
            return False
    except Exception:
        pass
    try:
        from bling_app_zero.ui.site_resume_state import checkpoint_count, resume_requested
        count = int(checkpoint_count(operation) or 0)
        if count <= 0:
            return False
        return bool(
            st.session_state.get('site_capture_running')
            or st.session_state.get('site_capture_error')
            or st.session_state.get('site_capture_result_ready') is False
            or resume_requested(operation)
        )
    except Exception:
        return False


def install_site_checkpoint_finalizer_runtime() -> bool:
    if st.session_state.get(_PATCH_KEY):
        return False
    try:
        from bling_app_zero.ui import site_panel
        original = getattr(site_panel, '_blingfix_original_render_site_panel_checkpoint_finalizer', None)
        if original is None:
            original = site_panel.render_site_panel
            setattr(site_panel, '_blingfix_original_render_site_panel_checkpoint_finalizer', original)

        def guarded_render_site_panel() -> None:
            try:
                operation = _normalize_operation(site_panel._site_operation())
            except Exception:
                operation = _normalize_operation(st.session_state.get('site_capture_operation') or st.session_state.get('operacao_final') or 'universal')
            if _should_try_finalize_before_render(operation):
                finalized = finalize_checkpoint_as_site_origin(operation, reason='runtime_before_site_panel_render', show_message=True, require_complete=True)
                if isinstance(finalized, pd.DataFrame) and not finalized.empty:
                    return original()
            return original()

        site_panel.render_site_panel = guarded_render_site_panel
        st.session_state[_PATCH_KEY] = True
        add_audit_event(
            'site_checkpoint_finalizer_runtime_installed',
            area='SITE',
            step='startup',
            status='OK',
            details={'target': 'site_panel.render_site_panel', 'completion_analysis': True, 'responsible_file': RESPONSIBLE_FILE},
        )
        return True
    except Exception as exc:
        add_audit_event(
            'site_checkpoint_finalizer_runtime_failed',
            area='SITE',
            step='startup',
            status='ERRO',
            details={'error': str(exc)[:240], 'responsible_file': RESPONSIBLE_FILE},
        )
        return False


__all__ = ['analyze_checkpoint_completion', 'finalize_checkpoint_as_site_origin', 'install_site_checkpoint_finalizer_runtime']