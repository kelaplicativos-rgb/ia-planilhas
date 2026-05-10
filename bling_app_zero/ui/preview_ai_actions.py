from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ai_tools.product_ai_reviewer import (
    ai_ready,
    apply_product_ai_suggestions,
    detect_product_columns,
    generate_product_ai_suggestions,
    suggestions_to_dataframe,
)
from bling_app_zero.core.debug import add_debug
from bling_app_zero.ui.home_shared import df_signature, preview_df


OPERATION_LABELS = {
    'cadastro': 'CADASTRO',
    'estoque': 'ESTOQUE',
}

TARGET_DF_KEYS = {
    'cadastro': 'df_final_cadastro',
    'estoque': 'df_final_estoque',
}

EXAMPLE_TASKS = [
    'Crie títulos para produtos que estão sem nome.',
    'Padronize os títulos com marca + modelo quando essas informações existirem.',
    'Melhore as descrições complementares vazias ou muito curtas.',
    'Sugira NCM para produtos que estão com NCM vazio.',
]


def _operation_label(operation: str) -> str:
    return OPERATION_LABELS.get(str(operation or '').strip().lower(), 'ARQUIVO')


def _state_key(operation: str, signature: str, suffix: str) -> str:
    op = str(operation or 'arquivo').strip().lower() or 'arquivo'
    safe_signature = str(signature).replace(' ', '_').replace(':', '_').replace('|', '_')[:120]
    return f'preview_ai_{op}_{safe_signature}_{suffix}'


def _render_detected_columns(df: pd.DataFrame) -> None:
    columns = detect_product_columns(df)
    detected = {
        'Título/Nome': columns.get('title') or '(não encontrada)',
        'Descrição complementar': columns.get('description') or '(não encontrada)',
        'NCM': columns.get('ncm') or '(não encontrada)',
        'Código/SKU apoio': columns.get('sku') or '(não encontrada)',
        'Marca apoio': columns.get('brand') or '(não encontrada)',
        'Categoria apoio': columns.get('category') or '(não encontrada)',
    }
    with st.expander('Colunas que a IA vai usar', expanded=False):
        st.dataframe(pd.DataFrame([detected]).astype(str), use_container_width=True, height=90)


def _store_applied_df(operation: str, df_applied: pd.DataFrame) -> None:
    op = str(operation or '').strip().lower()
    target_key = TARGET_DF_KEYS.get(op)
    if target_key:
        st.session_state[target_key] = df_applied
    if op == 'estoque':
        outputs = st.session_state.get('estoque_multi_outputs')
        if isinstance(outputs, list) and outputs:
            outputs[0]['df_final'] = df_applied
            st.session_state['estoque_multi_outputs'] = outputs


def _render_suggestions_editor(suggestions_df: pd.DataFrame, editor_key: str) -> pd.DataFrame:
    disabled_columns = ['Linha', 'Produto', 'Campo', 'Coluna', 'Original', 'Motivo']
    return st.data_editor(
        suggestions_df,
        use_container_width=True,
        hide_index=True,
        disabled=disabled_columns,
        column_config={
            'Aplicar': st.column_config.CheckboxColumn('Aplicar', help='Marque as sugestões que devem entrar no CSV final.'),
            'Sugestão IA': st.column_config.TextColumn('Sugestão IA', help='Você pode ajustar o texto antes de aplicar.'),
        },
        key=editor_key,
    )


def _render_multitask_box(op: str, signature: str) -> str:
    task_key = _state_key(op, signature, 'custom_task')
    with st.expander('🧠 Multitarefa da IA', expanded=True):
        st.caption('Peça uma ação livre para a IA executar na planilha final. Ela vai gerar sugestões por linha e você confirma antes de aplicar.')
        custom_task = st.text_area(
            'O que você quer que a IA faça na planilha?',
            value=st.session_state.get(task_key, ''),
            key=task_key,
            height=96,
            placeholder='Ex: crie títulos para produtos sem nome, melhore descrições vazias e sugira NCM onde estiver vazio.',
        )
        with st.expander('Exemplos rápidos', expanded=False):
            for index, example in enumerate(EXAMPLE_TASKS, start=1):
                if st.button(example, use_container_width=True, key=_state_key(op, signature, f'example_{index}')):
                    st.session_state[task_key] = example
                    st.rerun()
        st.caption('Proteção ativa: a IA não aplica automaticamente e não deve alterar preço, GTIN/EAN, estoque, depósito, SKU, imagens ou URLs.')
    return str(custom_task or '').strip()


def render_preview_ai_actions(df_final: pd.DataFrame | None, operation: str) -> None:
    """IA funcional no preview final.

    Revisa título, descrição complementar, NCM e também aceita um pedido livre
    multitarefa para gerar sugestões editáveis antes de aplicar no CSV final.
    """
    if not isinstance(df_final, pd.DataFrame) or df_final.empty:
        return

    op = str(operation or 'arquivo').strip().lower() or 'arquivo'
    label = _operation_label(op)
    signature = df_signature(df_final)
    suggestions_key = _state_key(op, signature, 'suggestions')
    status_key = _state_key(op, signature, 'status')
    editor_key = _state_key(op, signature, 'editor')

    st.markdown(
        """
        <div class="bling-inline-card">
            <div class="bling-flow-card-kicker">IA de catálogo</div>
            <div class="bling-flow-card-title">Revisar produtos com IA</div>
            <p class="bling-flow-card-text">Reformule títulos, melhore descrições complementares, sugira NCM e peça tarefas livres antes do download final.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if op != 'cadastro':
        st.caption('A IA de catálogo foi feita para produto/cadastro. No estoque ela fica disponível só como apoio quando houver colunas compatíveis.')

    if ai_ready():
        st.success('IA conectada. As sugestões serão geradas com OpenAI.')
    else:
        st.warning('OPENAI_API_KEY não encontrada. O sistema ainda pode mostrar sugestões locais simples, mas NCM e multitarefa livre precisam da chave configurada.')

    _render_detected_columns(df_final)

    col1, col2, col3 = st.columns(3)
    with col1:
        use_title = st.checkbox('Títulos', value=True, key=_state_key(op, signature, 'use_title'))
    with col2:
        use_description = st.checkbox('Descrições complementares', value=True, key=_state_key(op, signature, 'use_description'))
    with col3:
        use_ncm = st.checkbox('NCM vazio', value=True, key=_state_key(op, signature, 'use_ncm'))

    custom_task = _render_multitask_box(op, signature)

    max_rows = st.slider(
        'Quantidade máxima de produtos para revisar por execução',
        min_value=10,
        max_value=200,
        value=min(60, max(10, len(df_final))),
        step=10,
        key=_state_key(op, signature, 'max_rows'),
    )

    if st.button(f'🤖 Executar IA no preview final de {label}', use_container_width=True, key=_state_key(op, signature, 'run')):
        with st.spinner('IA revisando produtos do preview final...'):
            suggestions, status = generate_product_ai_suggestions(
                df_final,
                actions={'title': use_title, 'description': use_description, 'ncm': use_ncm},
                max_rows=max_rows,
                custom_task=custom_task,
            )
        st.session_state[suggestions_key] = suggestions_to_dataframe(suggestions)
        st.session_state[status_key] = status
        add_debug(f'IA de catálogo executada no preview final de {label}: {status}', origin='PREVIEW_IA', level='INFO')
        st.rerun()

    status = st.session_state.get(status_key)
    if status:
        st.caption(str(status))

    suggestions_df = st.session_state.get(suggestions_key)
    if not isinstance(suggestions_df, pd.DataFrame):
        return

    if suggestions_df.empty:
        st.info('A IA não encontrou alterações seguras para aplicar neste preview final.')
        return

    st.markdown('##### Antes/depois sugerido pela IA')
    edited = _render_suggestions_editor(suggestions_df, editor_key)

    preview_applied = apply_product_ai_suggestions(df_final, edited)
    with st.expander('Prévia do CSV final se aplicar as sugestões marcadas', expanded=False):
        preview_df(f'Prévia com IA · {label}', preview_applied)

    apply_count = int(edited['Aplicar'].sum()) if 'Aplicar' in edited.columns else 0
    if st.button(f'✅ Aplicar {apply_count} sugestão(ões) no CSV final', use_container_width=True, key=_state_key(op, signature, 'apply')):
        if apply_count <= 0:
            st.warning('Nenhuma sugestão marcada para aplicar.')
            return
        df_applied = apply_product_ai_suggestions(df_final, edited)
        _store_applied_df(op, df_applied)
        add_debug(f'{apply_count} sugestão(ões) da IA aplicadas no CSV final de {label}.', origin='PREVIEW_IA', level='INFO')
        st.success('Sugestões aplicadas no CSV final. Confira novamente o preview antes de baixar.')
        st.rerun()


__all__ = ['render_preview_ai_actions']
