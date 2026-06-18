from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.category_intelligence import detect_category_column, detect_product_name_column
from bling_app_zero.core.global_dataset_guard import GLOBAL_DECISION_DATASET_SIGNATURE_KEY, GLOBAL_LIVE_DATASET_SIGNATURE_KEY, dataframe_identity_signature
from bling_app_zero.ui.category_conference_step_v2 import (
    CATEGORY_DATASET_SIGNATURE_KEY,
    CATEGORY_DONE_KEY,
    CATEGORY_SKIP_KEY,
    CATEGORY_STATS_KEY,
    CATEGORY_VALUES_SIGNATURE_KEY,
    category_conference_ready,
    category_values_signature,
    render_category_conference_step,
)

RESPONSIBLE_FILE = 'bling_app_zero/ui/category_conference_wizard_step.py'
CATEGORY_WIZARD_TOGGLE_KEY = 'category_wizard_use_categorization_v1'
CATEGORY_WIZARD_DECISION_KEY = 'category_wizard_decision_v1'
CATEGORY_WIZARD_SOURCE_KEY = 'category_wizard_source_key_v1'

# Depois que o usuário formula os preços, a categorização deve operar sobre a
# base já precificada. A base crua fica como fallback para fluxos sem preço.
SOURCE_KEYS = (
    'df_origem_cadastro_precificada',
    'cadastro_wizard_df_origem',
    'df_origem_site_como_planilha_cadastro',
    'df_origem_site_como_planilha_universal',
    'df_origem_site_como_planilha',
    'df_produtos_origem',
    'cadastro_wizard_df_para_mapear',
    'df_origem_cadastro',
    'df_origem_universal',
    'df_origem_planilha',
    'df_origem',
    'df_final_cadastro_preview_rules_applied',
    'df_final_cadastro',
    'df_final_universal',
    'df_final_bling_api',
)


def _valid_df(value: object) -> bool:
    return isinstance(value, pd.DataFrame) and not value.empty and len(value.columns) > 0


def _source_df() -> tuple[pd.DataFrame | None, str]:
    for key in SOURCE_KEYS:
        value = st.session_state.get(key)
        if _valid_df(value):
            return value.copy().fillna(''), key
    return None, ''


def _norm(value: object) -> str:
    text = str(value or '').strip().lower()
    for old, new in {'ã': 'a', 'á': 'a', 'à': 'a', 'â': 'a', 'é': 'e', 'ê': 'e', 'í': 'i', 'ó': 'o', 'ô': 'o', 'õ': 'o', 'ú': 'u', 'ç': 'c'}.items():
        text = text.replace(old, new)
    return text


def _looks_like_price_or_stock_only(df: pd.DataFrame) -> bool:
    cols = [_norm(col) for col in df.columns]
    joined = ' '.join(cols)
    has_name = any(term in joined for term in ('nome', 'descricao', 'produto', 'titulo'))
    has_category = any(term in joined for term in ('categoria', 'category'))
    has_price_channel = any(term in joined for term in ('id na loja', 'nome da loja', 'canal', 'multiloja'))
    has_qty_or_stock = any(term in joined for term in ('quantidade', 'saldo', 'estoque', 'balanco'))
    has_price = any(term in joined for term in ('preco', 'preço', 'valor'))
    if has_category:
        return False
    if has_price_channel and has_price:
        return True
    if has_qty_or_stock and not has_name:
        return True
    return False


def _categorization_applicable(df: pd.DataFrame | None) -> bool:
    if not _valid_df(df):
        return False
    if _looks_like_price_or_stock_only(df):
        return False
    return bool(detect_category_column(df) or detect_product_name_column(df))


def _inject_toggle_state_style() -> None:
    """Deixa o estado ligado visualmente verde e reduz o risco de parecer erro.

    Streamlit herda a cor primária do tema; nesta app ela pode aparecer vermelha.
    O badge textual abaixo garante clareza mesmo se o seletor CSS mudar em versão futura.
    """
    st.markdown(
        """
        <style>
        div[data-testid="stToggle"] label:has(input:checked) span,
        div[data-testid="stToggle"] label:has(input[aria-checked="true"]) span {
            color: #047857 !important;
            font-weight: 800 !important;
        }
        div[data-testid="stToggle"] label:has(input:checked) [data-testid="stMarkdownContainer"],
        div[data-testid="stToggle"] label:has(input[aria-checked="true"]) [data-testid="stMarkdownContainer"] {
            color: #047857 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _mark_skipped(df: pd.DataFrame | None, source_key: str, *, reason: str) -> None:
    if not _valid_df(df):
        st.session_state[CATEGORY_SKIP_KEY] = True
        st.session_state[CATEGORY_DONE_KEY] = False
        st.session_state[CATEGORY_WIZARD_DECISION_KEY] = 'skip_without_dataframe'
        return
    dataset_sig = dataframe_identity_signature(df, context='category_wizard_skip').signature
    st.session_state[CATEGORY_SKIP_KEY] = True
    st.session_state[CATEGORY_DONE_KEY] = False
    st.session_state[CATEGORY_VALUES_SIGNATURE_KEY] = category_values_signature(df)
    st.session_state[CATEGORY_DATASET_SIGNATURE_KEY] = dataset_sig
    st.session_state[GLOBAL_DECISION_DATASET_SIGNATURE_KEY] = dataset_sig
    st.session_state[GLOBAL_LIVE_DATASET_SIGNATURE_KEY] = dataset_sig
    st.session_state[CATEGORY_WIZARD_DECISION_KEY] = f'skip_{reason}'
    st.session_state[CATEGORY_WIZARD_SOURCE_KEY] = source_key
    add_audit_event(
        'category_wizard_skipped',
        area='CATEGORIAS',
        step='categorizacao',
        status='PULADO',
        details={
            'reason': reason,
            'rows': int(len(df)),
            'source_key': source_key,
            'category_values_signature': st.session_state.get(CATEGORY_VALUES_SIGNATURE_KEY),
            'dataset_identity_signature': dataset_sig,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def _clear_toggle_off_skip_state() -> None:
    """Ao ligar o toggle, remove apenas o pulo automático criado pelo toggle desligado."""
    if str(st.session_state.get(CATEGORY_WIZARD_DECISION_KEY) or '') != 'skip_toggle_off':
        return
    for key in (
        CATEGORY_SKIP_KEY,
        CATEGORY_DONE_KEY,
        CATEGORY_STATS_KEY,
        CATEGORY_VALUES_SIGNATURE_KEY,
        CATEGORY_DATASET_SIGNATURE_KEY,
        GLOBAL_DECISION_DATASET_SIGNATURE_KEY,
    ):
        st.session_state.pop(key, None)
    st.session_state[CATEGORY_WIZARD_DECISION_KEY] = 'enabled_panel'


def category_wizard_ready() -> bool:
    df, _source_key = _source_df()
    if not _categorization_applicable(df):
        return True
    use_categorization = st.session_state.get(CATEGORY_WIZARD_TOGGLE_KEY)
    if use_categorization is False:
        return True
    return category_conference_ready()


def render_category_conference_wizard_step() -> None:
    df, source_key = _source_df()
    # O título principal já é renderizado pelo wizard como "4. Categorização...".
    # Aqui fica apenas a explicação para evitar título duplicado na tela.
    st.caption('Recurso opcional. Ao ligar, o sistema categoriza automaticamente e só libera avanço com 100% dos produtos contendo categoria final válida.')

    if not _categorization_applicable(df):
        _mark_skipped(df, source_key, reason='not_applicable')
        st.info('Esta base não parece exigir categorização. A etapa foi liberada sem alterar dados.')
        return

    if CATEGORY_WIZARD_TOGGLE_KEY not in st.session_state:
        st.session_state[CATEGORY_WIZARD_TOGGLE_KEY] = False

    _inject_toggle_state_style()
    toggle_is_on = bool(st.session_state.get(CATEGORY_WIZARD_TOGGLE_KEY, False))
    toggle_label = '✅ Categorização automática ATIVADA' if toggle_is_on else 'Usar Categorização Inteligente Automática'
    use_categorization = st.toggle(
        toggle_label,
        value=toggle_is_on,
        key=CATEGORY_WIZARD_TOGGLE_KEY,
        help='Ligado: o sistema categoriza automaticamente. Desligado: segue sem alterar categorias.',
    )

    if not use_categorization:
        _mark_skipped(df, source_key, reason='toggle_off')
        st.info('Categorização desligada. Ligue o toggle acima se quiser que o sistema categorize automaticamente.')
        return

    _clear_toggle_off_skip_state()
    if not category_conference_ready():
        st.info('Categorização ativada. O sistema está processando automaticamente com trava de 100%.')
    render_category_conference_step()
    if not category_conference_ready():
        st.info('Sistema processando categorias automaticamente. Se alguma categoria não for segura, a etapa será bloqueada.')


__all__ = [
    'CATEGORY_WIZARD_DECISION_KEY',
    'CATEGORY_WIZARD_TOGGLE_KEY',
    'category_wizard_ready',
    'render_category_conference_wizard_step',
]
