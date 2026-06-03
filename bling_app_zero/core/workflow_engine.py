from __future__ import annotations

from dataclasses import dataclass

from bling_app_zero.core.app_state import AppState
from bling_app_zero.core.navigation_controller import NavigationCommand, NavigationState, clear_workflow_navigation

RESPONSIBLE_FILE = 'bling_app_zero/core/workflow_engine.py'

FLOW_HOME = 'home'
FLOW_WIZARD = 'wizard_cadastro_estoque'

CONTEXT_API = 'api_direct'
CONTEXT_UNIVERSAL = 'universal'

STEP_MODELO = 'modelo'
STEP_ORIGEM = 'origem'
STEP_ENTRADA = 'entrada'
STEP_PRECIFICACAO = 'precificacao'
STEP_MAPEAMENTO = 'mapeamento'
STEP_REGRAS = 'regras'
STEP_DOWNLOAD = 'download'

ACTIVE_FLOW_KEY = 'home_active_operation_v2'
HOME_ALLOW_FLOW_KEY = 'home_allow_operation_v2_session'
WIZARD_STEP_KEY = 'bling_wizard_step'


@dataclass(frozen=True)
class WorkflowResult:
    state: AppState
    navigation: NavigationState
    needs_rerun: bool = True
    message: str = ''


def go_home(state: AppState, navigation: NavigationState) -> WorkflowResult:
    state.set(ACTIVE_FLOW_KEY, FLOW_HOME)
    state.set(HOME_ALLOW_FLOW_KEY, False)
    state.set('home_single_page_flow_active', False)
    clear_workflow_navigation(navigation)
    return WorkflowResult(state, navigation, True, 'Voltou para o início.')


def set_wizard(
    state: AppState,
    navigation: NavigationState,
    *,
    context: str,
    step: str,
    operation: str = '',
    origin: str = '',
    api_mode: bool = False,
) -> WorkflowResult:
    state.set(ACTIVE_FLOW_KEY, FLOW_WIZARD)
    state.set(HOME_ALLOW_FLOW_KEY, True)
    state.set('home_single_page_flow_active', True)
    state.set('entry_context', context)
    state.set('bling_finish_mode', 'api_direct' if api_mode else 'csv_download')
    state.set(WIZARD_STEP_KEY, step)

    if operation:
        state.update(
            {
                'direct_bling_operation_choice': operation,
                'home_slim_flow_operation': operation,
                'home_detected_operation': operation,
                'operacao_final': operation,
                'tipo_operacao_final': operation,
                'model_contract_type': operation,
            }
        )
    if origin:
        state.update({'home_slim_flow_origin': origin, 'origem_final': origin})

    NavigationCommand(flow=FLOW_WIZARD, step=step, operation=operation, origin=origin, context=context).apply_to(navigation)
    return WorkflowResult(state, navigation, True, 'Fluxo atualizado.')


def current_operation(state: AppState, default: str = 'cadastro') -> str:
    return str(state.get('direct_bling_operation_choice') or state.get('home_slim_flow_operation') or default)


def current_context_is_api(state: AppState) -> bool:
    return str(state.get('bling_finish_mode') or '') == 'api_direct'


__all__ = [
    'ACTIVE_FLOW_KEY',
    'CONTEXT_API',
    'CONTEXT_UNIVERSAL',
    'FLOW_HOME',
    'FLOW_WIZARD',
    'HOME_ALLOW_FLOW_KEY',
    'STEP_DOWNLOAD',
    'STEP_ENTRADA',
    'STEP_MAPEAMENTO',
    'STEP_MODELO',
    'STEP_ORIGEM',
    'STEP_PRECIFICACAO',
    'STEP_REGRAS',
    'WIZARD_STEP_KEY',
    'WorkflowResult',
    'current_context_is_api',
    'current_operation',
    'go_home',
    'set_wizard',
]
