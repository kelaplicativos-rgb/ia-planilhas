from __future__ import annotations

import html

import streamlit as st

from bling_app_zero.ui.home_wizard_constants import DEFAULT_PENDING_MESSAGE, STEP_LABELS, WizardNav


def render_section_card(kicker: str, title: str, text: str) -> None:
    st.markdown(
        f"""
        <section class="bling-flow-card">
            <div class="bling-flow-card-kicker">{html.escape(kicker)}</div>
            <h2 class="bling-flow-card-title">{html.escape(title)}</h2>
            <p class="bling-flow-card-text">{html.escape(text)}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_pending_notice(message: str | None = None) -> None:
    safe_message = html.escape(str(message or DEFAULT_PENDING_MESSAGE))
    st.markdown(
        f"""
        <div class="bling-alert-card bling-alert-warning" role="status" aria-live="polite">
            <div class="bling-alert-icon">⚠️</div>
            <div class="bling-alert-content">
                <strong>Atenção</strong>
                <span>{safe_message}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_step_header(*, steps: list[str], current: str) -> WizardNav:
    index = steps.index(current)
    total = len(steps)
    percent = int(((index + 1) / total) * 100)
    progress_width = max(1, min(100, percent))
    labels = []
    for i, step in enumerate(steps):
        prefix = '●' if i == index else '✓' if i < index else '○'
        labels.append(f'{prefix} {STEP_LABELS[step]}')

    label_text = html.escape('  ·  '.join(labels))
    progress_text = html.escape(f'Etapa {index + 1} de {total} · {STEP_LABELS[current]} · {percent}%')
    st.markdown(
        f"""
        <section class="bling-flow-card bling-wizard-progress-card" aria-label="Progresso do fluxo">
            <div class="bling-wizard-progress-title">{progress_text}</div>
            <div class="bling-wizard-progress-track" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{percent}">
                <div class="bling-wizard-progress-fill" style="width:{progress_width}%"></div>
            </div>
            <div class="bling-wizard-steps-line">{label_text}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    return WizardNav(current=current, index=index, total=total, steps=steps)


def render_blocked_next_slot(pending_message: str | None = None) -> None:
    """Mantido por compatibilidade; o aviso bloqueado fica acima dos botões."""
    return None
