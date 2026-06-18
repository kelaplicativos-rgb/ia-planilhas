from __future__ import annotations

from dataclasses import dataclass

from bling_app_zero.core.wizard_state import (
    STEP_CATEGORIZACAO,
    STEP_DOWNLOAD,
    STEP_ENTRADA,
    STEP_IA,
    STEP_MAPEAMENTO,
    STEP_MODELO,
    STEP_ORIGEM,
    STEP_PRECIFICACAO,
    STEP_PREVIEW,
    STEP_REGRAS,
    WizardState,
    normalize_step,
)

RESPONSIBLE_FILE = 'bling_app_zero/core/wizard_engine.py'


@dataclass(frozen=True)
class WizardCommandResult:
    wizard: WizardState
    allowed: bool = True
    needs_rerun: bool = True
    message: str = ''
    warning: str = ''


def required_flag_for_step(step: str) -> str:
    if step == STEP_MODELO:
        return ''
    if step == STEP_ORIGEM:
        return 'has_model'
    if step == STEP_ENTRADA:
        return 'has_origin'
    if step == STEP_PRECIFICACAO:
        return 'has_data'
    if step == STEP_CATEGORIZACAO:
        return 'has_pricing'
    if step == STEP_MAPEAMENTO:
        return 'has_pricing'
    if step == STEP_REGRAS:
        return 'has_mapping'
    if step == STEP_IA:
        return 'has_rules'
    if step == STEP_PREVIEW:
        return 'has_rules'
    if step == STEP_DOWNLOAD:
        return 'has_preview'
    return ''


def can_enter_step(wizard: WizardState, step: str) -> tuple[bool, str]:
    normalized = normalize_step(step, api_mode=wizard.api_mode)
    if wizard.api_mode:
        if normalized == STEP_ENTRADA and not wizard.has_origin:
            return False, 'Escolha a origem dos dados antes de continuar.'
        if normalized == STEP_DOWNLOAD and not wizard.has_data:
            return False, 'Carregue ou capture os dados antes de enviar ao Bling.'
        return True, ''

    required = required_flag_for_step(normalized)
    if not required:
        return True, ''
    if bool(getattr(wizard, required, False)):
        return True, ''
    messages = {
        'has_model': 'Confirme o modelo antes de escolher a origem.',
        'has_origin': 'Escolha a origem dos dados antes de continuar.',
        'has_data': 'Carregue os dados antes de precificar.',
        'has_pricing': 'Finalize a precificação antes de categorizar ou mapear.',
        'has_mapping': 'Finalize o mapeamento antes de revisar regras.',
        'has_rules': 'Revise as regras antes da IA ou da prévia.',
        'has_preview': 'Gere o preview antes de baixar/enviar.',
    }
    return False, messages.get(required, 'Etapa anterior pendente.')


def go_to_step(wizard: WizardState, step: str, *, force: bool = False) -> WizardCommandResult:
    normalized = normalize_step(step, api_mode=wizard.api_mode)
    if not force:
        allowed, warning = can_enter_step(wizard, normalized)
        if not allowed:
            return WizardCommandResult(wizard, False, False, '', warning)
    return WizardCommandResult(wizard.with_updates(step=normalized), True, True, f'Etapa alterada para {normalized}.', '')


def next_step(wizard: WizardState, *, force: bool = False) -> WizardCommandResult:
    if wizard.is_last_step:
        return WizardCommandResult(wizard, True, False, 'Já está na última etapa.', '')
    target = wizard.steps[wizard.step_index + 1]
    return go_to_step(wizard, target, force=force)


def previous_step(wizard: WizardState) -> WizardCommandResult:
    if wizard.is_first_step:
        return WizardCommandResult(wizard, True, False, 'Já está na primeira etapa.', '')
    target = wizard.steps[wizard.step_index - 1]
    return WizardCommandResult(wizard.with_updates(step=target), True, True, f'Voltou para {target}.', '')


def mark_step_ready(wizard: WizardState, step: str | None = None) -> WizardState:
    current = normalize_step(step or wizard.step, api_mode=wizard.api_mode)
    updates: dict[str, bool] = {}
    if current == STEP_MODELO:
        updates['has_model'] = True
    elif current == STEP_ORIGEM:
        updates['has_origin'] = True
    elif current == STEP_ENTRADA:
        updates['has_data'] = True
    elif current == STEP_PRECIFICACAO:
        updates['has_pricing'] = True
    elif current == STEP_MAPEAMENTO:
        updates['has_mapping'] = True
    elif current == STEP_REGRAS:
        updates['has_rules'] = True
    elif current == STEP_IA:
        updates['has_rules'] = True
    elif current == STEP_PREVIEW:
        updates['has_preview'] = True
    return wizard.with_updates(**updates)


def set_origin(wizard: WizardState, origin: str) -> WizardCommandResult:
    text = str(origin or '').strip()
    return WizardCommandResult(wizard.with_updates(origin=text, has_origin=bool(text)), True, True, 'Origem atualizada.', '')


def set_operation(wizard: WizardState, operation: str) -> WizardCommandResult:
    text = str(operation or '').strip() or wizard.operation
    return WizardCommandResult(wizard.with_updates(operation=text), True, True, 'Operação atualizada.', '')


__all__ = [
    'WizardCommandResult',
    'can_enter_step',
    'go_to_step',
    'mark_step_ready',
    'next_step',
    'previous_step',
    'required_flag_for_step',
    'set_operation',
    'set_origin',
]