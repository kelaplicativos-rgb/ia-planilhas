from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlencode

RESPONSIBLE_FILE = 'bling_app_zero/core/navigation_controller.py'


@dataclass
class NavigationState:
    params: dict[str, str] = field(default_factory=dict)

    def get(self, key: str, default: str = '') -> str:
        return str(self.params.get(key, default) or '')

    def set(self, key: str, value: object) -> None:
        text = str(value or '').strip()
        if text:
            self.params[str(key)] = text
        else:
            self.params.pop(str(key), None)

    def pop(self, key: str) -> None:
        self.params.pop(str(key), None)

    def clear_keys(self, keys: tuple[str, ...]) -> None:
        for key in keys:
            self.pop(key)

    def snapshot(self) -> dict[str, str]:
        return dict(self.params)

    def to_query_string(self) -> str:
        if not self.params:
            return ''
        return '?' + urlencode(self.params)

    @classmethod
    def from_query_string(cls, query_string: str) -> 'NavigationState':
        text = str(query_string or '').strip().lstrip('?')
        if not text:
            return cls()
        parsed = parse_qs(text, keep_blank_values=False)
        return cls({key: str(values[0]) for key, values in parsed.items() if values})


@dataclass(frozen=True)
class NavigationCommand:
    flow: str = ''
    step: str = ''
    operation: str = ''
    origin: str = ''
    action: str = ''
    context: str = ''

    def apply_to(self, nav: NavigationState) -> NavigationState:
        if self.flow:
            nav.set('operation_v2', self.flow)
        if self.step:
            nav.set('step', self.step)
        if self.operation:
            nav.set('operation', self.operation)
        if self.origin:
            nav.set('origin', self.origin)
        if self.action:
            nav.set('app_action', self.action)
        if self.context:
            nav.set('context', self.context)
        return nav


def clear_workflow_navigation(nav: NavigationState) -> NavigationState:
    nav.clear_keys(('operation_v2', 'step', 'flow', 'origem', 'origin', 'operacao', 'operation', 'context'))
    return nav


def action_href(current_params: dict[str, str], *, action_param: str, action: str) -> str:
    nav = NavigationState({str(k): str(v) for k, v in current_params.items() if str(k) != action_param})
    nav.set(action_param, action)
    return nav.to_query_string() or '?'


__all__ = [
    'NavigationCommand',
    'NavigationState',
    'action_href',
    'clear_workflow_navigation',
]
