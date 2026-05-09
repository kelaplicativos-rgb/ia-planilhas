from __future__ import annotations

import streamlit as st


APP_THEME_CSS = """
<style id="bling-app-theme">
:root {
    --bling-bg: #07111f;
    --bling-bg-soft: #0b1728;
    --bling-card: rgba(15, 23, 42, 0.92);
    --bling-card-strong: rgba(17, 24, 39, 0.96);
    --bling-border: rgba(148, 163, 184, 0.22);
    --bling-border-strong: rgba(59, 130, 246, 0.42);
    --bling-text: #e5edf8;
    --bling-muted: #9ca3af;
    --bling-primary: #38bdf8;
    --bling-primary-strong: #0ea5e9;
    --bling-success: #22c55e;
    --bling-warning: #f59e0b;
    --bling-danger: #ef4444;
    --bling-radius-lg: 22px;
    --bling-radius-md: 16px;
    --bling-shadow: 0 18px 50px rgba(0, 0, 0, 0.34);
}

html,
body,
[data-testid="stAppViewContainer"],
.stApp {
    background:
        radial-gradient(circle at top left, rgba(14, 165, 233, 0.20), transparent 34rem),
        radial-gradient(circle at top right, rgba(34, 197, 94, 0.12), transparent 30rem),
        linear-gradient(180deg, var(--bling-bg) 0%, #020617 100%) !important;
    color: var(--bling-text) !important;
}

[data-testid="stHeader"] {
    background: rgba(7, 17, 31, 0.80) !important;
    backdrop-filter: blur(16px) !important;
    border-bottom: 1px solid rgba(148, 163, 184, 0.10) !important;
}

[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
#MainMenu {
    visibility: visible !important;
    opacity: 1 !important;
    pointer-events: auto !important;
}

.block-container {
    padding-top: 2.2rem !important;
    padding-bottom: 4rem !important;
    max-width: 1180px !important;
}

h1, h2, h3, h4, h5, h6,
p, span, label, div, small,
[data-testid="stMarkdownContainer"] {
    color: inherit;
}

[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] span {
    color: var(--bling-text);
}

.bling-hero {
    border: 1px solid var(--bling-border);
    background:
        linear-gradient(135deg, rgba(14, 165, 233, 0.18), rgba(34, 197, 94, 0.08)),
        var(--bling-card);
    border-radius: 28px;
    padding: 26px 28px;
    box-shadow: var(--bling-shadow);
    margin-bottom: 22px;
}

.bling-hero-kicker {
    color: var(--bling-primary);
    font-size: 0.78rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin-bottom: 8px;
}

.bling-hero-title {
    color: #f8fafc;
    font-size: clamp(1.9rem, 4vw, 3.2rem);
    line-height: 1.05;
    font-weight: 900;
    margin: 0 0 10px 0;
}

.bling-hero-subtitle {
    color: var(--bling-muted);
    font-size: 1rem;
    max-width: 760px;
    margin: 0;
}

.bling-flow-card,
.bling-inline-card {
    border: 1px solid var(--bling-border);
    background: var(--bling-card);
    border-radius: var(--bling-radius-lg);
    padding: 20px 22px;
    margin: 18px 0 12px 0;
    box-shadow: 0 14px 36px rgba(0, 0, 0, 0.22);
}

.bling-flow-card-kicker {
    color: var(--bling-primary);
    font-size: 0.74rem;
    font-weight: 800;
    letter-spacing: 0.10em;
    text-transform: uppercase;
    margin-bottom: 6px;
}

.bling-flow-card-title {
    color: #f8fafc !important;
    font-size: 1.35rem;
    font-weight: 850;
    margin: 0 0 6px 0;
}

.bling-flow-card-text {
    color: var(--bling-muted) !important;
    margin: 0;
    font-size: 0.96rem;
}

.bling-selected-flow-badge {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    padding: 10px 14px;
    border: 1px solid var(--bling-border-strong);
    border-radius: 999px;
    background: rgba(14, 165, 233, 0.12);
    color: #e0f2fe;
    font-weight: 800;
    margin: 14px 0 8px 0;
}

.bling-selected-flow-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--bling-success);
    box-shadow: 0 0 0 5px rgba(34, 197, 94, 0.16);
}

[data-testid="stSidebar"] {
    background: rgba(2, 6, 23, 0.96) !important;
    border-right: 1px solid rgba(148, 163, 184, 0.16) !important;
}

[data-testid="stFileUploader"],
[data-testid="stDataFrame"],
[data-testid="stExpander"],
[data-testid="stForm"],
[data-testid="stAlert"],
div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div,
div[data-baseweb="textarea"] textarea,
textarea,
input {
    border-radius: var(--bling-radius-md) !important;
}

[data-testid="stFileUploader"] section {
    background: rgba(15, 23, 42, 0.72) !important;
    border: 1px dashed rgba(56, 189, 248, 0.42) !important;
    border-radius: var(--bling-radius-lg) !important;
}

[data-testid="stExpander"] {
    border: 1px solid var(--bling-border) !important;
    background: rgba(15, 23, 42, 0.72) !important;
}

button,
[data-testid="stBaseButton-secondary"],
[data-testid="stBaseButton-primary"],
[data-testid="stBaseButton-primaryFormSubmit"],
[data-testid="stDownloadButton"] button {
    border-radius: 14px !important;
    font-weight: 800 !important;
    transition: transform 0.12s ease, border-color 0.12s ease, background 0.12s ease !important;
}

button:hover,
[data-testid="stBaseButton-secondary"]:hover,
[data-testid="stBaseButton-primary"]:hover,
[data-testid="stDownloadButton"] button:hover {
    transform: translateY(-1px);
    border-color: rgba(56, 189, 248, 0.64) !important;
}

[data-testid="stBaseButton-primary"],
[data-testid="stBaseButton-primaryFormSubmit"],
[data-testid="stDownloadButton"] button {
    background: linear-gradient(135deg, var(--bling-primary), var(--bling-primary-strong)) !important;
    color: #00111f !important;
    border: 0 !important;
}

[data-testid="stBaseButton-secondary"] {
    background: rgba(15, 23, 42, 0.88) !important;
    border: 1px solid rgba(148, 163, 184, 0.28) !important;
    color: var(--bling-text) !important;
}

.stRadio [role="radiogroup"] {
    gap: 0.65rem;
}

.stRadio label,
.stCheckbox label,
.stToggle label {
    background: rgba(15, 23, 42, 0.70);
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: 14px;
    padding: 8px 10px;
}

[data-testid="stDataFrame"] {
    border: 1px solid rgba(148, 163, 184, 0.16) !important;
    overflow: hidden !important;
}

@media (max-width: 760px) {
    .block-container {
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        padding-top: 1.2rem !important;
    }

    .bling-hero,
    .bling-flow-card,
    .bling-inline-card {
        padding: 18px 16px;
        border-radius: 18px;
    }

    .bling-hero-title {
        font-size: 2rem;
    }
}
</style>
"""


def inject_app_layout() -> None:
    """Injeta o tema visual em toda execução do Streamlit.

    Streamlit recarrega o script inteiro a cada clique. Por isso este CSS não
    pode depender de estado temporário nem ser renderizado apenas uma vez.
    """
    st.markdown(APP_THEME_CSS, unsafe_allow_html=True)


def render_compact_hero() -> None:
    st.markdown(
        """
        <section class="bling-hero">
            <div class="bling-hero-kicker">IA Planilhas → Bling</div>
            <h1 class="bling-hero-title">Prepare seus produtos para o Bling em poucos passos</h1>
            <p class="bling-hero-subtitle">
                Envie o modelo, escolha a origem dos dados e gere um CSV final limpo, validado e pronto para importação.
            </p>
        </section>
        """,
        unsafe_allow_html=True,
    )
