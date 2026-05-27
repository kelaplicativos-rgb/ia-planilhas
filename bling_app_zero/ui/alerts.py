from __future__ import annotations

from typing import Any, Callable

import streamlit as st

RESPONSIBLE_FILE = 'bling_app_zero/ui/alerts.py'
ALERT_THEME_STYLE_ID = 'bling-alert-theme-style-v2'

_ORIGINAL_INFO: Callable[..., Any] | None = None
_ORIGINAL_BUTTON: Callable[..., Any] | None = None
_POLICY_INSTALLED = False

_NAVIGATION_LABELS = (
    'continuar',
    'avancar',
    'avançar',
    'proximo',
    'próximo',
    'seguir',
    'liberar',
)

_ATTENTION_TERMS = (
    'atenção',
    'atencao',
    'bloquead',
    'bloqueio',
    'pendente',
    'pré-requisito',
    'pre-requisito',
    'requisito',
    'obrigatório',
    'obrigatorio',
    'ausente',
    'não encontrado',
    'nao encontrado',
    'não foi anexad',
    'nao foi anexad',
    'anexe',
    'carregue',
    'envie',
    'escolha',
    'confirme',
    'volte',
    'erro',
    'falhou',
    'falha',
)


def _normalize_text(value: object) -> str:
    return str(value or '').strip().lower()


def _is_navigation_label(label: object) -> bool:
    text = _normalize_text(label)
    return any(term in text for term in _NAVIGATION_LABELS)


def _looks_like_attention_message(message: object) -> bool:
    text = _normalize_text(message)
    if not text:
        return False
    return any(term in text for term in _ATTENTION_TERMS)


def inject_alert_theme() -> None:
    """Injeta o visual mestre para mensagens de atenção, erro e sucesso."""
    st.markdown(
        f'''
<style id="{ALERT_THEME_STYLE_ID}">
[data-testid="stAlert"] {{
    border-radius: 16px !important;
    border: 1px solid #e2e8f0 !important;
    box-shadow: 0 8px 20px rgba(15, 23, 42, 0.045) !important;
}}
[data-testid="stAlert"] [data-testid="stMarkdownContainer"] p,
[data-testid="stAlert"] [data-testid="stMarkdownContainer"] span,
[data-testid="stAlert"] [data-testid="stMarkdownContainer"] strong {{
    color: inherit !important;
}}
[data-testid="stAlert"][kind="warning"] {{
    background: #fff7ed !important;
    border-color: #fed7aa !important;
    color: #c2410c !important;
}}
[data-testid="stAlert"][kind="error"] {{
    background: #fef2f2 !important;
    border-color: #fecaca !important;
    color: #dc2626 !important;
}}
[data-testid="stAlert"][kind="success"] {{
    background: #ecfdf5 !important;
    border-color: #bbf7d0 !important;
    color: #16a34a !important;
}}
.bling-attention-card {{
    background: #fff7ed;
    border: 1px solid #fed7aa;
    border-radius: 16px;
    color: #c2410c;
    padding: .85rem .95rem;
    box-shadow: 0 8px 20px rgba(15, 23, 42, 0.045);
}}
.bling-attention-card p,
.bling-attention-card span,
.bling-attention-card strong {{
    color: #c2410c;
}}
</style>
''',
        unsafe_allow_html=True,
    )


def render_alert(message: str, *, title: str | None = None, variant: str = 'warning', icon: str | None = None) -> None:
    _ = icon
    text = str(message or '').strip()
    if not text:
        return
    inject_alert_theme()
    prefix = str(title or '').strip()
    output = f'{prefix}: {text}' if prefix else text
    method_name = variant if variant in {'warning', 'error', 'success', 'info'} else 'warning'
    if method_name == 'info' and _looks_like_attention_message(output):
        method_name = 'warning'
    getattr(st, method_name)(output)


def enforce_attention_alert_policy() -> None:
    """Aplica a regra visual global de atenção/bloqueio.

    BLINGFIX:
    - mensagens neutras continuam podendo usar `st.info`;
    - mensagens com pré-requisito, bloqueio, ausência de arquivo/modelo ou erro
      passam a usar o visual de aviso;
    - botão de navegação desabilitado não aparece como ação normal, sendo
      substituído por aviso claro de bloqueio.
    """
    global _ORIGINAL_BUTTON, _ORIGINAL_INFO, _POLICY_INSTALLED

    inject_alert_theme()

    if _POLICY_INSTALLED:
        return

    _ORIGINAL_INFO = st.info
    _ORIGINAL_BUTTON = st.button

    def attention_info(*args: Any, **kwargs: Any) -> Any:
        if args and _looks_like_attention_message(args[0]):
            return st.warning(*args, **kwargs)
        if _ORIGINAL_INFO is None:
            return None
        return _ORIGINAL_INFO(*args, **kwargs)

    def guarded_button(label: str, *args: Any, **kwargs: Any) -> Any:
        disabled = bool(kwargs.get('disabled', False))
        if disabled and _is_navigation_label(label):
            st.warning(
                'Ação bloqueada: conclua o pré-requisito desta etapa para liberar o botão de continuar.'
            )
            return False
        if _ORIGINAL_BUTTON is None:
            return False
        return _ORIGINAL_BUTTON(label, *args, **kwargs)

    st.info = attention_info  # type: ignore[method-assign]
    st.button = guarded_button  # type: ignore[method-assign]
    _POLICY_INSTALLED = True


__all__ = ['enforce_attention_alert_policy', 'inject_alert_theme', 'render_alert']
