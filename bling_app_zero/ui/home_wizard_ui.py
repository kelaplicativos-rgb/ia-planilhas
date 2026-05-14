from __future__ import annotations

import html

import streamlit as st

from bling_app_zero.ui.alerts import render_alert
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
    render_alert(
        str(message or DEFAULT_PENDING_MESSAGE),
        title='Atenção',
        variant='warning',
    )


def _step_chip(label: str, state: str) -> str:
    safe_label = html.escape(label)
    dot_class = f'bling-wizard-chip-dot bling-wizard-chip-dot-{state}'
    chip_class = f'bling-wizard-chip bling-wizard-chip-{state}'
    return f'<span class="{chip_class}"><span class="{dot_class}"></span>{safe_label}</span>'


def render_step_header(*, steps: list[str], current: str) -> WizardNav:
    index = steps.index(current)
    total = len(steps)
    percent = int(((index + 1) / total) * 100)
    progress_width = max(1, min(100, percent))
    chips: list[str] = []
    for i, step in enumerate(steps):
        state = 'active' if i == index else 'done' if i < index else 'pending'
        chips.append(_step_chip(STEP_LABELS[step], state))

    current_label = html.escape(STEP_LABELS[current])
    st.markdown(
        f"""
        <section class="bling-flow-card bling-wizard-progress-card" aria-label="Progresso do fluxo">
            <div class="bling-wizard-progress-top">
                <div>
                    <div class="bling-wizard-progress-kicker">Etapa {index + 1} de {total}</div>
                    <div class="bling-wizard-progress-title">{current_label}</div>
                </div>
                <div class="bling-wizard-progress-percent">{percent}%</div>
            </div>
            <div class="bling-wizard-progress-track" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{percent}">
                <div class="bling-wizard-progress-fill" style="width:{progress_width}%"></div>
            </div>
            <div class="bling-wizard-steps-line">{''.join(chips)}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    return WizardNav(current=current, index=index, total=total, steps=steps)
