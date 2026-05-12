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
        <style>
        .bling-wizard-progress-card {{
            padding: 1.15rem 1.25rem !important;
        }}
        .bling-wizard-progress-top {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: .85rem;
            margin-bottom: .85rem;
        }}
        .bling-wizard-progress-kicker {{
            color: #2563eb;
            font-size: .76rem;
            font-weight: 800;
            letter-spacing: .045em;
            text-transform: uppercase;
        }}
        .bling-wizard-progress-title {{
            color: #111827;
            font-size: 1.02rem;
            font-weight: 850;
            line-height: 1.22;
            margin-top: .15rem;
        }}
        .bling-wizard-progress-percent {{
            flex: 0 0 auto;
            min-width: 3.35rem;
            border-radius: 999px;
            background: #eef6ff;
            border: 1px solid #bfdbfe;
            color: #1d4ed8;
            font-size: .82rem;
            font-weight: 850;
            padding: .36rem .62rem;
            text-align: center;
        }}
        .bling-wizard-progress-track {{
            width: 100%;
            height: .48rem;
            border-radius: 999px;
            background: #e5edf8;
            overflow: hidden;
            box-shadow: inset 0 1px 2px rgba(15, 23, 42, .08);
        }}
        .bling-wizard-progress-fill {{
            height: 100%;
            border-radius: inherit;
            background: linear-gradient(90deg, #2563eb, #06b6d4);
        }}
        .bling-wizard-steps-line {{
            display: flex;
            flex-wrap: wrap;
            gap: .45rem;
            margin-top: .9rem;
        }}
        .bling-wizard-chip {{
            display: inline-flex;
            align-items: center;
            gap: .36rem;
            border-radius: 999px;
            padding: .34rem .56rem;
            font-size: .78rem;
            font-weight: 760;
            line-height: 1;
            border: 1px solid #e2e8f0;
            background: #ffffff;
            color: #64748b;
            white-space: nowrap;
        }}
        .bling-wizard-chip-active {{
            border-color: #bfdbfe;
            background: #eff6ff;
            color: #1d4ed8;
            box-shadow: 0 8px 20px rgba(37, 99, 235, .08);
        }}
        .bling-wizard-chip-done {{
            border-color: #bbf7d0;
            background: #f0fdf4;
            color: #15803d;
        }}
        .bling-wizard-chip-dot {{
            width: .42rem;
            height: .42rem;
            border-radius: 999px;
            display: inline-block;
            background: #cbd5e1;
        }}
        .bling-wizard-chip-dot-active {{ background: #2563eb; }}
        .bling-wizard-chip-dot-done {{ background: #22c55e; }}
        .bling-wizard-chip-dot-pending {{ background: #cbd5e1; }}
        @media (max-width: 640px) {{
            .bling-wizard-progress-card {{
                padding: 1rem !important;
            }}
            .bling-wizard-progress-top {{
                align-items: flex-start;
                margin-bottom: .75rem;
            }}
            .bling-wizard-progress-title {{
                font-size: .98rem;
            }}
            .bling-wizard-steps-line {{
                gap: .38rem;
            }}
            .bling-wizard-chip {{
                font-size: .74rem;
                padding: .32rem .48rem;
            }}
        }}
        </style>
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
