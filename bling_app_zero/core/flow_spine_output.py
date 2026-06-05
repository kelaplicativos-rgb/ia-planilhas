from __future__ import annotations

from bling_app_zero.core.flow_spine import FlowSpinePlan, build_flow_spine_plan, is_api_destination

RESPONSIBLE_FILE = 'bling_app_zero/core/flow_spine_output.py'


def output_plan() -> FlowSpinePlan:
    return build_flow_spine_plan()


def output_is_api() -> bool:
    try:
        return is_api_destination(output_plan())
    except Exception:
        return False


def preview_title() -> str:
    try:
        plan = output_plan()
        return f'Prévia final · {plan.final_title}'
    except Exception:
        return 'Prévia final'


def preview_caption() -> str:
    try:
        plan = output_plan()
        if is_api_destination(plan):
            return 'Confira a base revisada antes de enviar ao Bling. A saída final usará exatamente esta versão.'
        return plan.final_caption
    except Exception:
        return 'Confira se o arquivo final segue o modelo de destino anexado no início.'


def output_operation() -> str:
    try:
        return str(output_plan().operation or 'universal')
    except Exception:
        return 'universal'


def output_diagnostics() -> dict[str, object]:
    try:
        return output_plan().to_dict()
    except Exception:
        return {'responsible_file': RESPONSIBLE_FILE, 'status': 'legacy_fallback'}


__all__ = ['output_diagnostics', 'output_is_api', 'output_operation', 'output_plan', 'preview_caption', 'preview_title']
