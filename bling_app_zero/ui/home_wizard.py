from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.cadastro_wizard_state import (
    CADASTRO_MODELO_KEY,
    CADASTRO_ORIGEM_KEY,
    CADASTRO_ORIGEM_PRICED_KEY,
)
from bling_app_zero.ui.cadastro_wizard_steps import (
    cadastro_context_ready,
    cadastro_mapping_ready,
    render_cadastro_download_step,
    render_cadastro_entrada_step,
    render_cadastro_mapeamento_step,
    render_cadastro_preview_step,
)
from bling_app_zero.ui.home_pricing_config import (
    disable_home_pricing,
    get_home_pricing_config,
    render_home_pricing_config_form,
    set_home_pricing_config,
)
from bling_app_zero.ui.home_wizard_constants import (
    CADASTRO_STEPS,
    ESTOQUE_STEPS,
    FLOW_OPERATION_KEY,
    FLOW_ORIGIN_KEY,
    GLOBAL_CADASTRO_MODEL_KEYS,
    GLOBAL_ESTOQUE_MODEL_KEYS,
    HOME_CADASTRO_MODEL_KEY,
    HOME_ESTOQUE_MODEL_KEY,
    RESET_OUTPUT_KEYS,
    STEP_DOWNLOAD,
    STEP_ENTRADA,
    STEP_GERAR_ESTOQUE,
    STEP_MAPEAMENTO,
    STEP_MODELO,
    STEP_OPERACAO,
    STEP_ORIGEM,
    STEP_PRECIFICACAO,
    STEP_PREVIEW,
    STEP_REGRAS,
    WIZARD_STEP_KEY,
)
from bling_app_zero.ui.home_wizard_ui import render_pending_notice
from bling_app_zero.ui.mapping_review_panel import render_mapping_review_panel
from bling_app_zero.ui.rules_center_step import render_rules_center_step
from bling_app_zero.ui.scroll_guard import inject_scroll_guard

RESPONSIBLE_FILE = 'bling_app_zero/ui/home_wizard.py'
SINGLE_PAGE_FLOW = True
SCROLL_TARGET_KEY = 'home_wizard_scroll_target_step'
ORIGIN_RADIO_KEY = 'frontpage_origin_radio_universal'
VALID_OPERATIONS = {'cadastro', 'estoque'}
UNIVERSAL_STEPS = [step for step in CADASTRO_STEPS if step != STEP_OPERACAO]


def _looks_like_loaded_df(value: object) -> bool:
    if value is None or not hasattr(value, 'columns'):
        return False
    try:
        return len(getattr(value, 'columns', [])) > 0
    except Exception:
        return False


def _has_any_model(keys: list[str]) -> bool:
    return any(_looks_like_loaded_df(st.session_state.get(key)) for key in keys)


def _has_cadastro_model() -> bool:
    return _has_any_model([HOME_CADASTRO_MODEL_KEY, *GLOBAL_CADASTRO_MODEL_KEYS])


def _has_estoque_model() -> bool:
    return _has_any_model([HOME_ESTOQUE_MODEL_KEY, *GLOBAL_ESTOQUE_MODEL_KEYS])


def _has_home_models() -> bool:
    return _has_cadastro_model() or _has_estoque_model()


def _query_param(name: str) -> str:
    try:
        value = st.query_params.get(name, '')
        if isinstance(value, list):
            return str(value[0] if value else '')
        return str(value or '')
    except Exception:
        return ''


def _normalize_operation(value: object) -> str:
    text = str(value or '').strip().lower()
    if text in {'cadastro', 'cadastro_site'} or 'cadastro' in text:
        return 'cadastro'
    if text in {'estoque', 'estoque_site', 'atualizacao_estoque', 'atualização de estoque'} or 'estoque' in text:
        return 'estoque'
    return ''


def _operation_from_runtime() -> str:
    for value in (
        _query_param('operacao'),
        _query_param('operation'),
        st.session_state.get('home_detected_operation'),
        st.session_state.get(FLOW_OPERATION_KEY),
        st.session_state.get('operacao_final'),
        st.session_state.get('tipo_operacao_final'),
        st.session_state.get('tipo_operacao_site'),
        st.session_state.get('home_slim_flow_operation'),
    ):
        operation = _normalize_operation(value)
        if operation in VALID_OPERATIONS:
            return operation
    if _has_estoque_model() and not _has_cadastro_model():
        return 'estoque'
    return 'cadastro'


def _ensure_universal_operation_state() -> str:
    if not _has_home_models():
        return ''
    operation = _operation_from_runtime()
    st.session_state[FLOW_OPERATION_KEY] = operation
    st.session_state['operacao_final'] = operation
    st.session_state['tipo_operacao_final'] = operation
    st.session_state['home_detected_operation'] = operation
    return operation


def _selected_operation() -> str:
    return _ensure_universal_operation_state()


def wizard_steps_for_operation(operation: str | None = None) -> list[str]:
    _ = operation
    return list(UNIVERSAL_STEPS) if _has_home_models() else [STEP_MODELO]


def _target_by_delta(current_step: str, operation: str, delta: int) -> str:
    steps = wizard_steps_for_operation(operation)
    current = str(current_step or '').strip().lower()
    if current == STEP_OPERACAO:
        current = STEP_ORIGEM
    if current not in steps:
        return steps[0]
    index = steps.index(current)
    return steps[max(0, min(len(steps) - 1, index + delta))]


def wizard_previous_target(current_step: str, operation: str) -> str:
    return _target_by_delta(current_step, operation, -1)


def wizard_next_target(current_step: str, operation: str) -> str:
    return _target_by_delta(current_step, operation, 1)


def _normalize_origin_value(value: object) -> str:
    text = str(value or '').strip().lower()
    if text in {'arquivo', 'site'}:
        return text
    if any(item in text for item in ('arquivo', 'planilha', 'xml', 'pdf')):
        return 'arquivo'
    if 'site' in text:
        return 'site'
    return ''


def _current_origin_choice() -> str:
    current = _normalize_origin_value(st.session_state.get(FLOW_ORIGIN_KEY))
    if current:
        return current
    radio_origin = _normalize_origin_value(st.session_state.get(ORIGIN_RADIO_KEY))
    if radio_origin:
        return radio_origin
    origem = _normalize_origin_value(_query_param('origem') or _query_param('flow'))
    return origem


def _set_scroll_target(step: str) -> None:
    if step == STEP_OPERACAO:
        step = STEP_ORIGEM
    if step:
        st.session_state[SCROLL_TARGET_KEY] = step


def _render_step_anchor(step: str) -> None:
    safe_step = ''.join(ch for ch in str(step or '') if ch.isalnum() or ch in {'_', '-'})
    if safe_step:
        st.markdown(
            f'<div id="bling-step-{safe_step}" data-bling-step="{safe_step}" style="position:relative; top:-84px; height:1px;"></div>',
            unsafe_allow_html=True,
        )


def _inject_scroll_to_target() -> None:
    target = str(st.session_state.pop(SCROLL_TARGET_KEY, '') or '').strip().lower()
    if not target:
        return
    safe_target = ''.join(ch for ch in target if ch.isalnum() or ch in {'_', '-'})
    if not safe_target:
        return
    components.html(
        f"""
<script>
(function () {{
  const w = window.parent;
  const d = w.document;
  const targetId = 'bling-step-{safe_target}';
  function findTarget() {{ return d.getElementById(targetId) || d.querySelector('[data-bling-step="{safe_target}"]'); }}
  function scrollToTarget() {{
    const target = findTarget();
    if (!target) return false;
    const rect = target.getBoundingClientRect();
    const currentY = w.scrollY || w.pageYOffset || d.documentElement.scrollTop || d.body.scrollTop || 0;
    const y = Math.max(0, currentY + rect.top - 72);
    try {{ w.sessionStorage.setItem('home_wizard_scroll_y', String(y)); }} catch (e) {{}}
    try {{ w.scrollTo({{ top: y, behavior: 'auto' }}); }} catch (e) {{ w.scrollTo(0, y); }}
    try {{ d.documentElement.scrollTop = y; d.body.scrollTop = y; }} catch (e) {{}}
    return true;
  }}
  [0, 80, 180, 320, 520, 900, 1400].forEach(delay => w.setTimeout(scrollToTarget, delay));
}})();
</script>
        """,
        height=0,
        width=0,
    )
    add_audit_event('wizard_scroll_target_requested', area='WIZARD', step=target, status='OK', details={'target_step': target, 'responsible_file': RESPONSIBLE_FILE})


def _section_title(number: int, title: str) -> None:
    st.markdown('---')
    st.markdown(f'### {number}. {title}')


def _select_origin(origin: str) -> None:
    origin = _normalize_origin_value(origin)
    if origin not in {'arquivo', 'site'}:
        return
    operation = _selected_operation() or 'cadastro'
    previous_origin = st.session_state.get(FLOW_ORIGIN_KEY)
    st.session_state[ORIGIN_RADIO_KEY] = origin
    st.session_state[FLOW_ORIGIN_KEY] = origin
    st.session_state[FLOW_OPERATION_KEY] = operation
    st.session_state['operacao_final'] = operation
    st.session_state['tipo_operacao_final'] = operation
    st.session_state['origem_final'] = origin
    st.session_state['tipo_operacao_site'] = operation if origin == 'site' else ''
    st.session_state['home_slim_flow_operation'] = operation
    st.session_state[WIZARD_STEP_KEY] = STEP_ENTRADA
    _set_scroll_target(STEP_ENTRADA)
    add_audit_event('single_page_origin_selected', area='WIZARD', step=STEP_ORIGEM, details={'origin': origin, 'operation': operation, 'previous_origin': previous_origin, 'scroll_target': STEP_ENTRADA, 'single_page_flow': SINGLE_PAGE_FLOW, 'responsible_file': RESPONSIBLE_FILE})
    try:
        st.query_params['origem'] = origin
        st.query_params['flow'] = 'site' if origin == 'site' else 'planilha'
        st.query_params['step'] = STEP_ENTRADA
        st.query_params['operacao'] = operation
    except Exception:
        pass
    st.rerun()


def _reset_wizard() -> None:
    for key in RESET_OUTPUT_KEYS:
        st.session_state.pop(key, None)
    st.session_state.pop(FLOW_ORIGIN_KEY, None)
    st.session_state.pop('origem_final', None)
    add_audit_event('wizard_reset', area='WIZARD', step=STEP_DOWNLOAD, details={'single_page_flow': SINGLE_PAGE_FLOW, 'responsible_file': RESPONSIBLE_FILE})
    st.rerun()


def _render_model_step() -> None:
    from bling_app_zero.ui.home_models import render_home_bling_models

    _render_step_anchor(STEP_MODELO)
    _section_title(1, 'Modelo')
    with st.container(border=True):
        render_home_bling_models()
    _ensure_universal_operation_state()


def _render_origin_step() -> None:
    _render_step_anchor(STEP_ORIGEM)
    _section_title(2, 'Origem')
    if not _has_home_models():
        render_pending_notice('Liberado após anexar o modelo.')
        return
    _ensure_universal_operation_state()
    selected = _current_origin_choice()
    col1, col2 = st.columns(2)
    with col1:
        if st.button('📎 Arquivo', use_container_width=True, key='origin_choose_file'):
            _select_origin('arquivo')
    with col2:
        if st.button('🌐 Site', use_container_width=True, key='origin_choose_site'):
            _select_origin('site')
    if selected in {'arquivo', 'site'}:
        st.success('Origem selecionada.')
    else:
        render_pending_notice('Escolha Arquivo ou Site.')


def _render_cadastro_entrada() -> None:
    origin = _current_origin_choice()
    _render_step_anchor(STEP_ENTRADA)
    _section_title(3, 'Dados')
    if not _has_home_models():
        render_pending_notice('Liberado após anexar o modelo.')
        return
    if origin not in {'arquivo', 'site'}:
        render_pending_notice('Escolha a origem primeiro.')
        return
    add_audit_event('single_page_origin_data_rendered', area='UNIVERSAL', step=STEP_ENTRADA, details={'origin': origin, 'operation': _selected_operation(), 'single_page_flow': SINGLE_PAGE_FLOW, 'responsible_file': RESPONSIBLE_FILE})
    if origin == 'site':
        from bling_app_zero.ui.site_panel import render_site_panel
        render_site_panel()
    render_cadastro_entrada_step()


def _render_pricing_step() -> None:
    _render_step_anchor(STEP_PRECIFICACAO)
    _section_title(4, 'Preço')
    if not _has_home_models():
        render_pending_notice('Liberado após anexar o modelo.')
        return
    if not cadastro_context_ready():
        render_pending_notice('Carregue os dados primeiro.')
        return
    current_config = get_home_pricing_config()
    use_pricing = st.toggle('Usar calculadora', value=bool(current_config.get('enabled', False)), key='home_pricing_enabled_toggle')
    if use_pricing:
        with st.container(border=True):
            config = render_home_pricing_config_form()
            set_home_pricing_config(config)
    else:
        disable_home_pricing()
        st.caption('Opcional. Se desligada, mantém o preço da origem ou do mapeamento.')


def _render_cadastro_mapeamento() -> None:
    _render_step_anchor(STEP_MAPEAMENTO)
    _section_title(5, 'Mapear campos')
    if not _has_home_models():
        render_pending_notice('Liberado após modelo e dados.')
        return
    if not cadastro_context_ready():
        render_pending_notice('Carregue os dados primeiro.')
        return
    render_cadastro_mapeamento_step()


def _render_ai_review_step() -> None:
    _render_step_anchor(STEP_REGRAS)
    _section_title(6, 'IA / Revisão')
    if not _has_home_models():
        render_pending_notice('Liberado após modelo e mapeamento.')
        return
    if not cadastro_mapping_ready():
        render_pending_notice('Confirme o mapeamento manual primeiro.')
        return

    df_source = st.session_state.get(CADASTRO_ORIGEM_PRICED_KEY)
    if not _looks_like_loaded_df(df_source):
        df_source = st.session_state.get(CADASTRO_ORIGEM_KEY)
    df_modelo = st.session_state.get(CADASTRO_MODELO_KEY)

    with st.expander('🤖 Revisão IA do mapeamento', expanded=False):
        render_mapping_review_panel(
            operation='cadastro',
            mapping=st.session_state.get('mapping_cadastro'),
            confidence=st.session_state.get('mapping_confidence_cadastro'),
            df_source=df_source,
            target_columns=[str(column) for column in getattr(df_modelo, 'columns', [])],
        )

    with st.expander('⚙️ Ajustes avançados do arquivo final', expanded=False):
        render_rules_center_step()


def _render_cadastro_preview() -> None:
    _render_step_anchor(STEP_PREVIEW)
    _section_title(7, 'Preview')
    if not _has_home_models():
        render_pending_notice('Liberado após o mapeamento.')
        return
    if not cadastro_mapping_ready():
        render_pending_notice('Confirme o mapeamento primeiro.')
        return
    render_cadastro_preview_step()


def _render_cadastro_download() -> None:
    _render_step_anchor(STEP_DOWNLOAD)
    _section_title(8, 'Download')
    if not _has_home_models():
        render_pending_notice('Liberado no final.')
        return
    if not cadastro_mapping_ready():
        render_pending_notice('Confirme o mapeamento primeiro.')
        return
    render_cadastro_download_step()
    if st.button('Recomeçar fluxo', use_container_width=True, key='wizard_download_reset_single_page'):
        _reset_wizard()


def render_home_wizard() -> None:
    inject_scroll_guard('home_wizard')
    has_model = _has_home_models()
    operation = _ensure_universal_operation_state()
    st.session_state['wizard_bottom_nav_rendered_current_cycle'] = True
    st.session_state['home_single_page_flow_active'] = True

    if not has_model:
        st.session_state[WIZARD_STEP_KEY] = STEP_MODELO
        st.session_state.pop(FLOW_ORIGIN_KEY, None)
        add_audit_event('wizard_model_first_guard_active', area='WIZARD', step=STEP_MODELO, details={'reason': 'missing_destination_model', 'single_page_flow': SINGLE_PAGE_FLOW, 'responsible_file': RESPONSIBLE_FILE})
        _render_model_step()
        _inject_scroll_to_target()
        return

    add_audit_event('wizard_single_page_rendered', area='WIZARD', step='single_page', details={'operation': operation or 'nao_escolhida', 'steps': UNIVERSAL_STEPS, 'single_page_flow': SINGLE_PAGE_FLOW, 'responsible_file': RESPONSIBLE_FILE})
    _render_model_step()
    _render_origin_step()
    _render_cadastro_entrada()
    _render_pricing_step()
    _render_cadastro_mapeamento()
    _render_ai_review_step()
    _render_cadastro_preview()
    _render_cadastro_download()
    _inject_scroll_to_target()


__all__ = [
    'CADASTRO_STEPS',
    'ESTOQUE_STEPS',
    'HOME_CHOICE_TARGET',
    'STEP_DOWNLOAD',
    'STEP_GERAR_ESTOQUE',
    'STEP_MAPEAMENTO',
    'STEP_REGRAS',
    'render_home_wizard',
    'wizard_next_target',
    'wizard_previous_target',
    'wizard_steps_for_operation',
]
