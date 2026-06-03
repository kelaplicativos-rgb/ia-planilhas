from __future__ import annotations

from dataclasses import dataclass

RESPONSIBLE_FILE = 'bling_app_zero/core/app_actions.py'

ACTION_PARAM = 'app_action'

ACTION_REFRESH = 'refresh'
ACTION_CLEAR = 'clear'
ACTION_SHORTCUTS = 'shortcuts'
ACTION_DIAGNOSTIC = 'diagnostic'

TECHNICAL_KEEP_PREFIXES = ('bling_token', 'bling_oauth', 'oauth')

SAFE_CLEAR_KEYS = (
    'site_capture_running',
    'site_capture_finished',
    'site_capture_error',
    'site_capture_started_at',
    'site_progress_log',
    'site_progress_last',
    'blingsmartscan_manual_continue_required',
    'blingsmartscan_ready_to_continue',
    'blingsmartscan_continue_target_step',
    'blingsmartscan_finished_operation',
    'blingsmartscan_finished_rows',
    'blingsmartscan_finished_columns',
    'blingsmartscan_budget_notice',
    'bling_api_batch_send_state_v2',
    'cadastro_entry_autoscroll_signature',
    'home_wizard_scroll_target_step',
    'wizard_bottom_nav_rendered_current_cycle',
)

SAFE_CLEAR_PREFIXES = (
    'site_deep_capture_',
    'site_capture_',
    'blingsmartscan_notice_',
    'blingsmartscan_report_',
    'bling_smart_sender_category_cache',
    'bling_smart_sender_product_cache',
)


@dataclass(frozen=True)
class AppAction:
    key: str
    label: str
    icon: str
    description: str = ''

    @property
    def title(self) -> str:
        return f'{self.icon} {self.label}'.strip()


BOTTOM_BAR_ACTIONS: tuple[AppAction, ...] = (
    AppAction(ACTION_REFRESH, 'Atualizar', '🔄', 'Recarrega a tela atual sem apagar dados.'),
    AppAction(ACTION_CLEAR, 'Limpar', '🧹', 'Remove travamentos, progresso antigo e cache seguro.'),
    AppAction(ACTION_SHORTCUTS, 'Atalhos', '⚡', 'Abre atalhos rápidos para as principais ações.'),
    AppAction(ACTION_DIAGNOSTIC, 'Diagnóstico', '🧪', 'Mostra dados de sessão e ferramentas de diagnóstico.'),
)


def is_known_action(action: object) -> bool:
    text = str(action or '').strip()
    return any(item.key == text for item in BOTTOM_BAR_ACTIONS)


def action_title(action: object) -> str:
    text = str(action or '').strip()
    for item in BOTTOM_BAR_ACTIONS:
        if item.key == text:
            return item.title
    return text


__all__ = [
    'ACTION_CLEAR',
    'ACTION_DIAGNOSTIC',
    'ACTION_PARAM',
    'ACTION_REFRESH',
    'ACTION_SHORTCUTS',
    'AppAction',
    'BOTTOM_BAR_ACTIONS',
    'SAFE_CLEAR_KEYS',
    'SAFE_CLEAR_PREFIXES',
    'TECHNICAL_KEEP_PREFIXES',
    'action_title',
    'is_known_action',
]
