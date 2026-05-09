from __future__ import annotations

import html

import streamlit as st


def inject_clean_home_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bling-radius: 16px;
            --bling-red: #b91c1c;
            --bling-text: rgba(17, 24, 39, 0.96);
            --bling-muted: rgba(49, 51, 63, 0.68);
        }

        html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {
            overflow-x: hidden !important;
            max-width: 100vw !important;
        }

        .main .block-container,
        .block-container {
            max-width: 1060px !important;
            padding-top: 1.15rem !important;
            padding-bottom: 1.5rem !important;
            overflow-x: hidden !important;
        }

        div[data-testid="stVerticalBlock"],
        div[data-testid="stHorizontalBlock"],
        div[data-testid="stElementContainer"],
        div[data-testid="column"] {
            max-width: 100% !important;
            overflow-x: hidden !important;
            box-sizing: border-box !important;
        }

        div[data-testid="stVerticalBlock"] {
            gap: 0.58rem !important;
        }

        div[data-testid="column"] {
            padding: 0 0.2rem !important;
        }

        .bling-hero,
        .bling-home-card,
        .bling-step-title,
        .bling-muted,
        .bling-compact-note,
        .bling-upload-title,
        .bling-upload-caption {
            box-sizing: border-box !important;
            max-width: 100% !important;
            overflow-wrap: normal !important;
            word-break: normal !important;
        }

        .bling-hero {
            width: min(100%, 860px);
            margin: 0 auto 0.72rem auto;
            border: 1px solid rgba(49, 51, 63, 0.10);
            border-radius: var(--bling-radius);
            padding: 14px 16px 13px 16px;
            background: linear-gradient(180deg, rgba(255,255,255,0.96), rgba(248,249,251,0.92));
            text-align: center;
            overflow: hidden;
        }
        .bling-hero-title {
            font-size: clamp(1.32rem, 4vw, 2rem);
            line-height: 1.20;
            font-weight: 900;
            margin: 0 0 6px 0;
            letter-spacing: -0.006em;
        }
        .bling-hero-subtitle {
            font-size: clamp(0.90rem, 2.4vw, 1rem);
            line-height: 1.42;
            color: var(--bling-muted);
            margin: 0 auto;
            max-width: 820px;
        }

        .bling-home-center {
            width: 100%;
            display: flex;
            justify-content: center;
            align-items: flex-start;
            padding: 0.12rem 0 0 0;
        }
        .bling-home-card {
            width: min(100%, 760px);
            margin: 0 auto 0.55rem auto;
            border: 1px solid rgba(49, 51, 63, 0.10);
            border-radius: 22px;
            padding: 18px 18px 16px 18px;
            background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(248,250,252,0.94));
            box-shadow: 0 12px 35px rgba(15, 23, 42, 0.06);
            text-align: center;
            overflow: hidden;
        }
        .bling-home-pill {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            border-radius: 999px;
            padding: 6px 11px;
            background: rgba(239, 68, 68, 0.09);
            color: var(--bling-red);
            font-size: 0.78rem;
            font-weight: 900;
            margin: 0 auto 10px auto;
        }
        .bling-home-title {
            font-size: clamp(1.20rem, 3.6vw, 1.62rem);
            line-height: 1.22;
            font-weight: 920;
            margin: 0 auto 8px auto;
            color: var(--bling-text);
            max-width: 720px;
            letter-spacing: -0.004em;
        }
        .bling-home-text {
            max-width: 640px;
            margin: 0 auto 14px auto;
            color: var(--bling-muted);
            font-size: 0.94rem;
            line-height: 1.46;
        }
        .bling-home-mini-steps {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 8px;
            margin: 13px auto 4px auto;
            max-width: 680px;
        }
        .bling-home-mini-step {
            border-radius: 14px;
            border: 1px solid rgba(49, 51, 63, 0.08);
            background: rgba(255, 255, 255, 0.82);
            padding: 9px 8px;
            min-height: 56px;
            overflow: hidden;
        }
        .bling-home-mini-step strong {
            display: block;
            font-size: 0.80rem;
            line-height: 1.20;
            margin-bottom: 3px;
            color: rgba(17, 24, 39, 0.92);
        }
        .bling-home-mini-step span {
            display: block;
            font-size: 0.72rem;
            line-height: 1.20;
            color: rgba(49, 51, 63, 0.62);
        }
        .bling-home-button-center {
            width: min(100%, 420px);
            margin: 0.38rem auto 0 auto;
        }
        .bling-home-button-center + div .stButton > button,
        div[data-testid="stVerticalBlock"]:has(.bling-home-button-center) .stButton > button {
            width: 100% !important;
            min-height: 46px !important;
            font-weight: 820 !important;
            border-radius: 16px !important;
        }

        .bling-step-title {
            font-size: 1.14rem;
            line-height: 1.28;
            font-weight: 850;
            margin: 10px 0 5px 0;
            clear: both;
        }
        .bling-muted {
            color: var(--bling-muted);
            font-size: 0.92rem;
            line-height: 1.42;
            margin: 0 0 0.62rem 0;
            clear: both;
        }
        .bling-compact-note {
            border-radius: 12px;
            padding: 9px 11px;
            background: rgba(240, 242, 246, 0.72);
            color: rgba(49, 51, 63, 0.76);
            font-size: 0.88rem;
            line-height: 1.38;
            margin: 7px 0 10px 0;
        }
        .bling-upload-title {
            font-size: 1.10rem;
            font-weight: 850;
            margin: 9px 0 3px 0;
            line-height: 1.28;
        }
        .bling-upload-caption {
            color: rgba(49, 51, 63, 0.62);
            font-size: 0.88rem;
            line-height: 1.36;
            margin: 0 0 7px 0;
        }

        div[data-baseweb="select"] {
            max-width: 100% !important;
            width: 100% !important;
        }
        div[data-baseweb="select"] > div {
            max-width: 100% !important;
            overflow: hidden !important;
            background: #eef2f7 !important;
            border-radius: 14px !important;
        }
        div[data-baseweb="popover"],
        div[data-baseweb="menu"],
        ul[role="listbox"] {
            max-width: calc(100vw - 24px) !important;
            overflow-x: hidden !important;
        }
        ul[role="listbox"] li {
            white-space: normal !important;
            overflow-wrap: anywhere !important;
            word-break: normal !important;
            background: #ffffff !important;
        }

        .stButton > button,
        .stDownloadButton > button {
            border-radius: 14px !important;
            min-height: 44px;
            padding: 0.48rem 0.72rem;
            font-size: 0.95rem;
            line-height: 1.24;
            white-space: normal;
        }
        div[data-testid="stFileUploader"] section {
            padding: 11px 12px !important;
            min-height: 82px !important;
            border-radius: 14px !important;
        }
        div[data-testid="stFileUploader"] section p {
            font-size: 0.86rem !important;
            line-height: 1.24 !important;
            margin-bottom: 0.15rem !important;
        }
        div[data-testid="stFileUploader"] small {
            font-size: 0.74rem !important;
            line-height: 1.20 !important;
        }
        div[data-testid="stExpander"] details {
            border-radius: 14px !important;
        }
        div[data-testid="stExpander"] details summary {
            padding-top: 0.55rem !important;
            padding-bottom: 0.55rem !important;
        }

        @media (max-width: 760px) {
            .main .block-container,
            .block-container {
                padding-left: 0.62rem !important;
                padding-right: 0.62rem !important;
                padding-top: 1.80rem !important;
                padding-bottom: 1rem !important;
                max-width: 100vw !important;
                min-height: 84svh !important;
            }
            header[data-testid="stHeader"] {
                visibility: visible !important;
                height: 2.75rem !important;
                min-height: 2.75rem !important;
                background: rgba(255,255,255,0.78) !important;
                backdrop-filter: blur(10px);
            }
            section[data-testid="stSidebar"] {
                max-width: 88vw !important;
            }
            .bling-hero {
                width: 100%;
                padding: 11px 12px 10px 12px;
                margin: 0 auto 0.62rem auto;
                border-radius: 15px;
            }
            .bling-hero-title {
                font-size: 1.17rem;
                line-height: 1.24;
                margin-bottom: 5px;
                letter-spacing: normal;
            }
            .bling-hero-subtitle {
                font-size: 0.86rem;
                line-height: 1.42;
            }
            .bling-home-card {
                width: 100%;
                border-radius: 18px;
                padding: 15px 12px 13px 12px;
                margin-bottom: 0.55rem;
            }
            .bling-home-pill {
                font-size: 0.74rem;
                padding: 5px 9px;
                margin-bottom: 8px;
            }
            .bling-home-title {
                font-size: 1.16rem;
                line-height: 1.24;
                margin-bottom: 6px;
            }
            .bling-home-text {
                font-size: 0.84rem;
                line-height: 1.42;
                margin-bottom: 11px;
            }
            .bling-home-mini-steps {
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 7px;
                margin: 10px auto 2px auto;
            }
            .bling-home-mini-step {
                min-height: 50px;
                padding: 8px 7px;
                border-radius: 13px;
            }
            .bling-home-mini-step strong {
                font-size: 0.75rem;
            }
            .bling-home-mini-step span {
                font-size: 0.68rem;
            }
            .bling-home-button-center {
                width: 100%;
                margin-top: 0.28rem;
            }
            .bling-step-title {
                font-size: 1.08rem;
                line-height: 1.28;
                margin: 0.62rem 0 0.18rem 0;
            }
            .bling-muted {
                font-size: 0.86rem;
                line-height: 1.42;
                margin: 0 0 0.62rem 0;
            }
            .bling-compact-note {
                padding: 8px 10px;
                margin: 0.45rem 0 0.58rem 0;
                border-radius: 12px;
                font-size: 0.84rem;
                line-height: 1.38;
            }
            .bling-upload-title {
                font-size: 1rem;
                line-height: 1.28;
                margin: 0.55rem 0 0.18rem 0;
            }
            .bling-upload-caption {
                font-size: 0.82rem;
                line-height: 1.36;
                margin: 0 0 0.45rem 0;
            }
            div[data-testid="stVerticalBlock"] {
                gap: 0.54rem !important;
            }
            div[data-testid="stHorizontalBlock"] {
                gap: 0.42rem !important;
            }
            div[data-testid="stMarkdownContainer"] p {
                line-height: 1.36 !important;
                margin-bottom: 0.35rem !important;
            }
            div[role="radiogroup"] label {
                border: 1px solid rgba(49, 51, 63, 0.14);
                border-radius: 14px;
                padding: 9px 10px !important;
                background: rgba(250, 250, 250, 0.84);
                margin-bottom: 6px !important;
                width: 100%;
                min-height: 48px;
                align-items: center;
                overflow: hidden;
            }
            div[role="radiogroup"] label p,
            div[role="radiogroup"] label span,
            div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] p {
                font-size: 0.94rem !important;
                line-height: 1.26 !important;
                white-space: normal !important;
                overflow-wrap: normal !important;
                margin: 0 !important;
            }
            div[data-testid="stFileUploader"] section {
                min-height: 78px !important;
                padding: 9px 10px !important;
                border-radius: 14px !important;
            }
            div[data-testid="stFileUploader"] section p {
                font-size: 0.80rem !important;
                line-height: 1.24 !important;
            }
            div[data-testid="stFileUploader"] small {
                font-size: 0.70rem !important;
                line-height: 1.20 !important;
            }
            div[data-testid="stFileUploader"] button {
                min-height: 36px !important;
                padding: 0.32rem 0.58rem !important;
                font-size: 0.82rem !important;
                line-height: 1.18 !important;
            }
            div[data-testid="stExpander"] details summary p {
                font-size: 0.88rem !important;
                line-height: 1.26 !important;
            }
            div[data-testid="stExpander"] details summary {
                padding: 0.48rem 0.58rem !important;
            }
            .stButton > button,
            .stDownloadButton > button {
                min-height: 46px !important;
                padding: 0.46rem 0.68rem !important;
                font-size: 0.96rem !important;
                line-height: 1.24 !important;
                border-radius: 14px !important;
                white-space: normal !important;
            }
            textarea,
            input,
            div[data-baseweb="input"] input,
            div[data-baseweb="textarea"] textarea {
                font-size: 0.92rem !important;
            }
            div[data-testid="stDataFrame"] {
                max-height: 360px !important;
            }
            iframe,
            div[data-testid="stDataFrame"] > div {
                max-width: 100% !important;
            }
        }

        @media (max-width: 390px) {
            .main .block-container,
            .block-container {
                padding-left: 0.50rem !important;
                padding-right: 0.50rem !important;
                padding-top: 1.65rem !important;
                min-height: 84svh !important;
            }
            header[data-testid="stHeader"] {
                height: 2.6rem !important;
                min-height: 2.6rem !important;
            }
            .bling-hero {
                padding: 10px 11px 9px 11px;
                margin-bottom: 0.55rem;
            }
            .bling-hero-title {
                font-size: 1.08rem;
            }
            .bling-hero-subtitle {
                font-size: 0.80rem;
            }
            .bling-home-card {
                padding: 14px 10px 12px 10px;
                border-radius: 16px;
            }
            .bling-home-title {
                font-size: 1.08rem;
            }
            .bling-home-text {
                font-size: 0.79rem;
            }
            .bling-home-mini-steps {
                gap: 6px;
            }
            .bling-home-mini-step strong {
                font-size: 0.70rem;
            }
            .bling-home-mini-step span {
                font-size: 0.64rem;
            }
            .bling-step-title {
                font-size: 1rem;
            }
            .bling-muted {
                font-size: 0.80rem;
            }
            .stButton > button,
            .stDownloadButton > button {
                min-height: 44px !important;
                font-size: 0.90rem !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_compact_hero() -> None:
    st.markdown(
        """
        <div class="bling-hero">
            <div class="bling-hero-title">🚀 IA Planilhas → Bling</div>
            <p class="bling-hero-subtitle">Transforme site, planilha, PDF ou XML em CSV pronto para cadastro ou estoque no Bling.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_home_start_card() -> None:
    st.markdown(
        """
        <div class="bling-home-center">
            <div class="bling-home-card">
                <div class="bling-home-pill">● Primeiro passo</div>
                <div class="bling-home-title">Comece pelo modelo certo do Bling</div>
                <div class="bling-home-text">
                    Envie o modelo oficial uma vez. A partir dele, o sistema sabe exatamente quais colunas preencher em cadastro ou estoque.
                </div>
                <div class="bling-home-mini-steps">
                    <div class="bling-home-mini-step"><strong>1. Modelo</strong><span>padrão Bling</span></div>
                    <div class="bling-home-mini-step"><strong>2. Preço</strong><span>opcional</span></div>
                    <div class="bling-home-mini-step"><strong>3. Origem</strong><span>site ou arquivo</span></div>
                    <div class="bling-home-mini-step"><strong>4. CSV</strong><span>pronto para importar</span></div>
                </div>
            </div>
        </div>
        <div class="bling-home-button-center"></div>
        """,
        unsafe_allow_html=True,
    )


def render_home_pricing_card() -> None:
    st.markdown(
        """
        <div class="bling-home-center">
            <div class="bling-home-card">
                <div class="bling-home-pill">● Segundo passo</div>
                <div class="bling-home-title">Quer calcular o preço de venda agora?</div>
                <div class="bling-home-text">
                    Configure lucro, taxas e valores fixos. O preço calculado pode entrar automaticamente no cadastro dos produtos.
                </div>
                <div class="bling-home-mini-steps">
                    <div class="bling-home-mini-step"><strong>Lucro</strong><span>margem desejada</span></div>
                    <div class="bling-home-mini-step"><strong>Custos</strong><span>taxas e impostos</span></div>
                    <div class="bling-home-mini-step"><strong>Flexível</strong><span>pode mudar depois</span></div>
                    <div class="bling-home-mini-step"><strong>Opcional</strong><span>seguir sem cálculo</span></div>
                </div>
            </div>
        </div>
        <div class="bling-home-button-center"></div>
        """,
        unsafe_allow_html=True,
    )


def close_home_start_card() -> None:
    return None


def render_step_title(title: str, caption: str | None = None) -> None:
    safe_title = html.escape(str(title or ''))
    st.markdown(f'<div class="bling-step-title">{safe_title}</div>', unsafe_allow_html=True)
    if caption:
        safe_caption = html.escape(str(caption or ''))
        st.markdown(f'<div class="bling-muted">{safe_caption}</div>', unsafe_allow_html=True)


def render_compact_note(text: str) -> None:
    safe_text = html.escape(str(text or ''))
    st.markdown(f'<div class="bling-compact-note">{safe_text}</div>', unsafe_allow_html=True)


__all__ = [
    'inject_clean_home_css',
    'render_compact_hero',
    'render_home_start_card',
    'render_home_pricing_card',
    'close_home_start_card',
    'render_step_title',
    'render_compact_note',
]
