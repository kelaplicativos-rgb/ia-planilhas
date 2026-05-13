from __future__ import annotations

import html

import streamlit as st

RESPONSIBLE_FILE = 'bling_app_zero/ui/alerts.py'

_ALERT_VARIANTS = {
    'warning': {
        'icon': '⚠️',
        'title': 'Atenção',
        'class_name': 'bling-alert-warning',
    },
    'error': {
        'icon': '⛔',
        'title': 'Erro',
        'class_name': 'bling-alert-error',
    },
    'success': {
        'icon': '✅',
        'title': 'Tudo certo',
        'class_name': 'bling-alert-success',
    },
    'info': {
        'icon': 'ℹ️',
        'title': 'Informação',
        'class_name': 'bling-alert-info',
    },
}


def inject_alert_theme() -> None:
    """CSS global dos balões do sistema, acoplado ao tema único."""
    st.markdown(
        """
        <style id="bling-alert-theme">
        .bling-alert-card {
            display: flex;
            align-items: flex-start;
            gap: .78rem;
            width: 100%;
            border-radius: var(--bling-radius-lg, 18px);
            padding: .92rem 1rem;
            margin: .85rem 0 1rem 0;
            box-shadow: var(--bling-shadow-soft, 0 8px 22px rgba(15, 23, 42, 0.045));
            box-sizing: border-box;
        }
        .bling-alert-warning {
            background: var(--bling-warning-bg, #fff7ed);
            border: 1px solid var(--bling-warning-border, #fed7aa);
            color: var(--bling-warning-text, #7c2d12);
        }
        .bling-alert-error {
            background: #fef2f2;
            border: 1px solid rgba(248, 113, 113, .42);
            color: #7f1d1d;
        }
        .bling-alert-success {
            background: #f0fdf4;
            border: 1px solid rgba(34, 197, 94, .34);
            color: #14532d;
        }
        .bling-alert-info {
            background: var(--bling-surface-soft, #eff6ff);
            border: 1px solid var(--bling-border, rgba(37, 99, 235, 0.14));
            color: var(--bling-primary-dark, #1d4ed8);
        }
        .bling-alert-icon {
            flex: 0 0 auto;
            width: 2.15rem;
            height: 2.15rem;
            border-radius: 999px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background: rgba(255, 255, 255, .55);
            border: 1px solid currentColor;
            font-size: 1.08rem;
            line-height: 1;
        }
        .bling-alert-content {
            display: flex;
            flex-direction: column;
            gap: .22rem;
            min-width: 0;
        }
        .bling-alert-content strong {
            color: inherit;
            font-size: .92rem;
            font-weight: 900;
            letter-spacing: .01em;
        }
        .bling-alert-content span {
            color: inherit;
            font-size: .9rem;
            line-height: 1.38;
            font-weight: 650;
        }
        @media (max-width: 640px) {
            .bling-alert-card {
                border-radius: 16px;
                padding: .82rem .9rem;
            }
            .bling-alert-icon {
                width: 2rem;
                height: 2rem;
            }
            .bling-alert-content span {
                font-size: .86rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_alert(
    message: str,
    *,
    title: str | None = None,
    variant: str = 'warning',
    icon: str | None = None,
) -> None:
    variant_config = _ALERT_VARIANTS.get(variant, _ALERT_VARIANTS['warning'])
    safe_title = html.escape(str(title or variant_config['title']))
    safe_message = html.escape(str(message or '').strip())
    safe_icon = html.escape(str(icon or variant_config['icon']))
    class_name = variant_config['class_name']

    if not safe_message:
        return

    inject_alert_theme()
    st.markdown(
        f"""
        <div class="bling-alert-card {class_name}" role="alert" aria-live="assertive">
            <div class="bling-alert-icon">{safe_icon}</div>
            <div class="bling-alert-content">
                <strong>{safe_title}</strong>
                <span>{safe_message}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


__all__ = ['inject_alert_theme', 'render_alert']
