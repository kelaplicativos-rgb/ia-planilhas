from __future__ import annotations

import importlib

import streamlit as st
import streamlit.components.v1 as components

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.ai_real_advanced_panel import render_ai_real_advanced_panel
from bling_app_zero.ui.cadastro_wizard_state import (
    CADASTRO_MODELO_KEY,
    CADASTRO_ORIGEM_KEY,
    CADASTRO_ORIGEM_PRICED_KEY,
)
from bling_app_zero.ui.cadastro_wizard_steps import (
    render_universal_download_step,
    render_universal_entrada_step,
    render_universal_mapeamento_step,
    render_universal_preview_step,
    universal_context_ready,
    universal_mapping_ready,
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
HOME_CHOICE_TARGET = '__home_choice__'
SCROLL_TARGET_KEY = 'home_wizard_scroll_target_step'
ORIGIN_RADIO_KEY = 'frontpage_origin_radio_universal'
UNIVERSAL_OPERATION = 'universal'
UNIVERSAL_REVIEW_OPERATION = 'modelo_destino'
UNIVERSAL_STEPS = [step for step in CADASTRO_STEPS if step != STEP_OPERACAO]
FINAL_CHECK_REPORT_KEY = 'home_wizard_final_check_report'
SAFE_FIX_SUGGESTIONS_KEY = 'home_wizard_safe_fix_suggestions'
FINAL_UNIVERSAL_KEY = 'df_final_universal'
FINAL_UNIVERSAL_LEGACY_KEY = 'df_final_cadastro'
STALE_CADASTRO_OPERATION_KEYS = (
    'df_final_download_operation',
    'df_final_preview_operation',
    'final_download_operation',
    'bling_wizard_state_guard_last_operation',
)


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


def _clear_stale_cadastro_operation_state() -> None:
    """Remove operações antigas que faziam o download universal aparecer como CADASTRO."""
    removed: list[str] = []
    for key in STALE_CADASTRO_OPERATION_KEYS:
        if str(st.session_state.get(key) or '').strip().lower() == 'cadastro':
            st.session_state.pop(key, None)
            removed.append(key)

    widget_key = str(st.session_state.get('final_download_widget_key') or '')
    if '_cadastro_' in widget_key or widget_key.endswith('_cadastro'):
        st.session_state.pop('final_download_widget_key', None)
        removed.append('final_download_widget_key')

    for key in list(st.session_state.keys()):
        text_key = str(key)
        if text_key.startswith('download_template_modelo_anexado_cadastro'):
            st.session_state.pop(key, None)
            removed.append(text_key)

    if removed:
        add_audit_event(
            'universal_flow_stale_cadastro_state_cleared',
            area='WIZARD',
            step='download',
            status='OK',
            details={'removed_keys': removed[:30], 'removed_count': len(removed), 'responsible_file': RESPONSIBLE_FILE},
        )


def _ensure_universal_operation_state() -> str:
    if not _has_home_models():
        return ''
    _clear_stale_cadastro_operation_state()
    st.session_state[FLOW_OPERATION_KEY] = UNIVERSAL_OPERATION
    st.session_state['operacao_final'] = UNIVERSAL_OPERATION
    st.session_state['tipo_operacao_final'] = UNIVERSAL_OPERATION
    st.session_state['home_detected_operation'] = UNIVERSAL_OPERATION
    st.session_state['home_slim_flow_operation'] = UNIVERSAL_OPERATION
    st.session_state.pop('tipo_operacao_site', None)
    return UNIVERSAL_OPERATION


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
    previous_origin = st.session_state.get(FLOW_ORIGIN_KEY)
    st.session_state[ORIGIN_RADIO_KEY] = origin
    st.session_state[FLOW_ORIGIN_KEY] = origin
    st.session_state[FLOW_OPERATION_KEY] = UNIVERSAL_OPERATION
    st.session_state['operacao_final'] = UNIVERSAL_OPERATION
    st.session_state['tipo_operacao_final'] = UNIVERSAL_OPERATION
    st.session_state['origem_final'] = origin
    st.session_state.pop('tipo_operacao_site', None)
    st.session_state['home_slim_flow_operation'] = UNIVERSAL_OPERATION
    _clear_stale_cadastro_operation_state()
    st.session_state[WIZARD_STEP_KEY] = STEP_ENTRADA
    _set_scroll_target(STEP_ENTRADA)
    add_audit_event('single_page_origin_selected', area='WIZARD', step=STEP_ORIGEM, details={'origin': origin, 'operation': UNIVERSAL_OPERATION, 'previous_origin': previous_origin, 'scroll_target': STEP_ENTRADA, 'single_page_flow': SINGLE_PAGE_FLOW, 'responsible_file': RESPONSIBLE_FILE})
    try:
        st.query_params['origem'] = origin
        st.query_params['flow'] = 'site' if origin == 'site' else 'arquivo'
        st.query_params['step'] = STEP_ENTRADA
        st.query_params.pop('operacao', None)
        st.query_params.pop('operation', None)
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
    _section_title(2, 'Origem dos dados')
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


def _render_universal_entrada() -> None:
    origin = _current_origin_choice()
    _render_step_anchor(STEP_ENTRADA)
    _section_title(3, 'Dados do fornecedor')
    if not _has_home_models():
        render_pending_notice('Liberado após anexar o modelo.')
        return
    if origin not in {'arquivo', 'site'}:
        render_pending_notice('Escolha a origem primeiro.')
        return
    add_audit_event('single_page_origin_data_rendered', area='UNIVERSAL', step=STEP_ENTRADA, details={'origin': origin, 'operation': UNIVERSAL_OPERATION, 'single_page_flow': SINGLE_PAGE_FLOW, 'responsible_file': RESPONSIBLE_FILE})
    if origin == 'site':
        from bling_app_zero.ui.site_panel import render_site_panel
        render_site_panel()
    render_universal_entrada_step()


def _render_pricing_step() -> None:
    _render_step_anchor(STEP_PRECIFICACAO)
    _section_title(4, 'Preço')
    if not _has_home_models():
        render_pending_notice('Liberado após anexar o modelo.')
        return
    if not universal_context_ready():
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


def _render_universal_mapeamento() -> None:
    _render_step_anchor(STEP_MAPEAMENTO)
    _section_title(5, 'Mapear campos')
    if not _has_home_models():
        render_pending_notice('Liberado após modelo e dados.')
        return
    if not universal_context_ready():
        render_pending_notice('Carregue os dados primeiro.')
        return
    render_universal_mapeamento_step()


def _run_final_checker(df_source: object, df_modelo: object, df_final: object) -> object:
    module = importlib.import_module('bling_app_zero.ai.ai_real_engine')
    checker = getattr(module, 'run_ai_real_final_check')
    return checker(
        df_source=df_source if _looks_like_loaded_df(df_source) else None,
        df_modelo=df_modelo if _looks_like_loaded_df(df_modelo) else None,
        df_final=df_final if _looks_like_loaded_df(df_final) else None,
    )


def _safe_fixes_module():
    return importlib.import_module('bling_app_zero.ai.ai_real_safe_fixes')


def _get_df_final_universal():
    current = st.session_state.get(FINAL_UNIVERSAL_KEY)
    if _looks_like_loaded_df(current):
        return current
    # Chave técnica legada: historicamente chama df_final_cadastro, mas hoje representa o modelo final universal.
    return st.session_state.get(FINAL_UNIVERSAL_LEGACY_KEY)


def _set_df_final_universal(df_final: object) -> None:
    if not _looks_like_loaded_df(df_final):
        return
    st.session_state[FINAL_UNIVERSAL_KEY] = df_final
    st.session_state[FINAL_UNIVERSAL_LEGACY_KEY] = df_final
    st.session_state.pop('df_final_cadastro_preview_rules_applied', None)
    st.session_state.pop(FINAL_CHECK_REPORT_KEY, None)


def _render_checker_item(item: object) -> None:
    level = str(getattr(item, 'level', '') or '')
    title = str(getattr(item, 'title', '') or '')
    message = str(getattr(item, 'message', '') or '')
    column = str(getattr(item, 'column', '') or '')
    prefix = '⛔' if level == 'erro' else '⚠️' if level == 'aviso' else '✅'
    text = f'{prefix} **{title}** — {message}'
    if column:
        text += f'  \nCampo: `{column}`'
    if level == 'erro':
        st.error(text)
    elif level == 'aviso':
        st.warning(text)
    else:
        st.success(text)


def _render_final_checker(df_source: object, df_modelo: object) -> None:
    df_final_universal = _get_df_final_universal()
    if not _looks_like_loaded_df(df_final_universal):
        st.warning('Conferência aguardando o arquivo final gerado pelo mapeamento.')
        return

    st.markdown('#### Conferência inteligente')
    st.caption('Verifica modelo, campos vazios, descrições, imagens e GTIN antes do preview/download. Não altera seus dados automaticamente.')

    if st.button('Verificar planilha agora', use_container_width=True, key='home_wizard_final_checker_run'):
        with st.spinner('Conferindo planilha final...'):
            report = _run_final_checker(df_source, df_modelo, df_final_universal)
        st.session_state[FINAL_CHECK_REPORT_KEY] = report
        add_audit_event(
            'home_wizard_final_checker_finished',
            area='FINAL_CHECK',
            step=STEP_REGRAS,
            status='OK' if bool(getattr(report, 'ok', False)) else 'AVISO',
            details={
                'summary': str(getattr(report, 'summary', '') or ''),
                'findings_count': len(getattr(report, 'findings', []) or []),
                'responsible_file': RESPONSIBLE_FILE,
            },
        )

    report = st.session_state.get(FINAL_CHECK_REPORT_KEY)
    if report is None:
        st.caption('Clique em verificar para receber um diagnóstico antes do preview.')
        return

    summary = str(getattr(report, 'summary', '') or '')
    if bool(getattr(report, 'ok', False)):
        st.success(f'Conferência concluída: {summary}')
    else:
        st.warning(f'Conferência concluída: {summary}')

    ai_message = str(getattr(report, 'ai_message', '') or '')
    if ai_message:
        st.info(ai_message)

    actions = getattr(report, 'actions', []) or []
    if actions:
        st.markdown('##### Próximos passos')
        for action in list(actions)[:6]:
            st.write(f'• {action}')

    findings = getattr(report, 'findings', []) or []
    with st.expander('Detalhes encontrados pela conferência', expanded=not bool(getattr(report, 'ok', False))):
        if not findings:
            st.success('Nenhum problema encontrado.')
        for item in list(findings)[:30]:
            _render_checker_item(item)


def _render_safe_fixes() -> None:
    df_final_universal = _get_df_final_universal()
    if not _looks_like_loaded_df(df_final_universal):
        return

    fixes = _safe_fixes_module()
    suggestions = fixes.build_safe_fix_suggestions(df_final_universal)
    st.markdown('#### Correções seguras')
    st.caption('Sugere ajustes automáticos de baixo risco. Nada é aplicado sem você clicar.')

    if not suggestions:
        st.success('Nenhuma correção segura pendente encontrada.')
        return

    options = [item.id for item in suggestions]
    labels = {item.id: f'{item.title} · {item.rows} linha(s) · {item.column}' for item in suggestions}
    selected = st.multiselect(
        'Escolha as correções para aplicar',
        options=options,
        default=options,
        format_func=lambda value: labels.get(value, value),
        key='home_wizard_safe_fix_selected',
    )

    with st.expander('Ver detalhes das correções sugeridas', expanded=True):
        for item in suggestions:
            st.write(f'• **{item.title}** — {item.description} ({item.rows} linha(s))')

    if not selected:
        st.caption('Selecione pelo menos uma correção para liberar o botão de aplicar.')
        return

    if st.button('Aplicar correções seguras', use_container_width=True, key='home_wizard_safe_fix_apply'):
        fixed_df, applied = fixes.apply_safe_fixes(df_final_universal, selected)
        if _looks_like_loaded_df(fixed_df):
            _set_df_final_universal(fixed_df)
            st.session_state[SAFE_FIX_SUGGESTIONS_KEY] = [getattr(item, 'id', '') for item in applied]
            add_audit_event(
                'home_wizard_safe_fixes_applied',
                area='FINAL_CHECK',
                step=STEP_REGRAS,
                status='OK',
                details={
                    'applied_count': len(applied),
                    'applied_ids': [getattr(item, 'id', '') for item in applied],
                    'responsible_file': RESPONSIBLE_FILE,
                },
            )
            st.success(f'{len(applied)} correção(ões) segura(s) aplicada(s). Confira o preview antes de baixar.')
            st.rerun()
        else:
            st.warning('Nenhuma alteração foi aplicada.')


def _render_ai_review_step() -> None:
    _render_step_anchor(STEP_REGRAS)
    _section_title(6, 'Revisão final')
    if not _has_home_models():
        render_pending_notice('Liberado após modelo e mapeamento.')
        return
    if not universal_mapping_ready():
        render_pending_notice('Confirme o mapeamento manual primeiro.')
        return

    df_source = st.session_state.get(CADASTRO_ORIGEM_PRICED_KEY)
    if not _looks_like_loaded_df(df_source):
        df_source = st.session_state.get(CADASTRO_ORIGEM_KEY)
    df_modelo = st.session_state.get(CADASTRO_MODELO_KEY)

    st.caption('Revise os campos ligados e aplique as proteções finais antes do preview.')
    render_mapping_review_panel(
        operation=UNIVERSAL_REVIEW_OPERATION,
        mapping=st.session_state.get('mapping_cadastro'),
        confidence=st.session_state.get('mapping_confidence_cadastro'),
        df_source=df_source,
        target_columns=[str(column) for column in getattr(df_modelo, 'columns', [])],
    )

    _render_final_checker(df_source, df_modelo)
    _render_safe_fixes()
    render_ai_real_advanced_panel()

    st.markdown('#### Ajustes avançados do arquivo final')
    render_rules_center_step()


def _render_universal_preview() -> None:
    _render_step_anchor(STEP_PREVIEW)
    _section_title(7, 'Preview')
    if not _has_home_models():
        render_pending_notice('Liberado após o mapeamento.')
        return
    if not universal_mapping_ready():
        render_pending_notice('Confirme o mapeamento primeiro.')
        return
    render_universal_preview_step()


def _render_universal_download() -> None:
    _render_step_anchor(STEP_DOWNLOAD)
    _section_title(8, 'Download')
    if not _has_home_models():
        render_pending_notice('Liberado no final.')
        return
    if not universal_mapping_ready():
        render_pending_notice('Confirme o mapeamento primeiro.')
        return
    _clear_stale_cadastro_operation_state()
    render_universal_download_step()
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

    add_audit_event('wizard_single_page_rendered', area='WIZARD', step='single_page', details={'operation': operation or 'universal', 'steps': UNIVERSAL_STEPS, 'single_page_flow': SINGLE_PAGE_FLOW, 'responsible_file': RESPONSIBLE_FILE})
    _render_model_step()
    _render_origin_step()
    _render_universal_entrada()
    _render_pricing_step()
    _render_universal_mapeamento()
    _render_ai_review_step()
    _render_universal_preview()
    _render_universal_download()
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