from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ai_tools.product_ai_batch_runner import DEFAULT_AI_BATCH_SIZE, generate_product_ai_suggestions_batched
from bling_app_zero.ai_tools.product_ai_reviewer import (
    ai_ready,
    apply_product_ai_suggestions,
    detect_product_columns,
    suggestions_to_dataframe,
)
from bling_app_zero.core.debug import add_debug
from bling_app_zero.core.marketplace_text_guard import alerts_to_dataframe, analyze_marketplace_text
from bling_app_zero.core.text import clean_cell
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

DESCRIPTION_LIMITS = {
    'pequena': 220,
    'media': 520,
    'grande': 1000,
}

DEFAULT_PREVIEW_AI_POLICY = {
    'limit_title_60': True,
    'description_size': 'media',
    'marketplace_text_guard': False,
    'out_of_context_filter': False,
    'blocked_terms': '',
    'context_filter_terms': '',
}


def _operation_label(operation: str) -> str:
    return OPERATION_LABELS.get(str(operation or '').strip().lower(), 'ARQUIVO')


def _state_key(operation: str, signature: str, suffix: str) -> str:
    op = str(operation or 'arquivo').strip().lower() or 'arquivo'
    safe_signature = str(signature).replace(' ', '_').replace(':', '_').replace('|', '_')[:120]
    return f'preview_ai_{op}_{safe_signature}_{suffix}'


def _set_custom_task(task_key: str, example: str) -> None:
    st.session_state[task_key] = example


def _truncate_text(value: object, limit: int) -> str:
    text = clean_cell(value)
    if limit <= 0 or len(text) <= limit:
        return text
    cut = text[:limit].rstrip()
    if ' ' in cut:
        cut = cut.rsplit(' ', 1)[0].rstrip()
    return cut


def _apply_ai_resource_policy_to_dataframe(suggestions_df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(suggestions_df, pd.DataFrame) or suggestions_df.empty:
        return suggestions_df

    limit_title = bool(DEFAULT_PREVIEW_AI_POLICY['limit_title_60'])
    description_size = str(DEFAULT_PREVIEW_AI_POLICY['description_size'])
    description_limit = DESCRIPTION_LIMITS.get(description_size, DESCRIPTION_LIMITS['media'])

    out = suggestions_df.copy()
    if out.empty or 'Sugestão IA' not in out.columns or 'Campo' not in out.columns:
        return out

    def _adjust(row: pd.Series) -> str:
        field = str(row.get('Campo') or '').strip().lower()
        suggestion = clean_cell(row.get('Sugestão IA', ''))
        if field == 'title' and limit_title:
            return _truncate_text(suggestion, 60)
        if field == 'description':
            return _truncate_text(suggestion, description_limit)
        return suggestion

    out['Sugestão IA'] = out.apply(_adjust, axis=1)
    return out.reset_index(drop=True)


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


def _render_marketplace_guard_alerts(df_final: pd.DataFrame, resources: dict) -> None:
    alerts = analyze_marketplace_text(df_final, resources)
    guard_enabled = bool(resources.get('marketplace_text_guard', False))
    context_enabled = bool(resources.get('out_of_context_filter', False))
    if not guard_enabled and not context_enabled:
        return
    if not alerts:
        st.success('Blindagem marketplace: nenhum termo proibido/sensível ou descrição fora de contexto foi detectado no preview final.')
        return

    alerts_df = alerts_to_dataframe(alerts)
    st.warning(f'Blindagem marketplace encontrou {len(alerts_df)} alerta(s). Revise antes de baixar a planilha final.')
    with st.expander('⚠️ Alertas de palavras proibidas e descrição fora de contexto', expanded=True):
        st.dataframe(alerts_df.astype(str), use_container_width=True, height=260)
        st.caption('Por segurança, o sistema apenas alerta. Use a IA de catálogo ou edite o mapeamento para corrigir antes do download.')


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
            'Aplicar': st.column_config.CheckboxColumn('Aplicar', help='Marcado = entra na planilha final.'),
            'Sugestão IA': st.column_config.TextColumn('Sugestão IA', help='Você pode ajustar o texto antes de aplicar.'),
        },
        key=editor_key,
    )


def _render_multitask_box(op: str, signature: str) -> str:
    task_key = _state_key(op, signature, 'custom_task')
    if task_key not in st.session_state:
        st.session_state[task_key] = ''

    with st.expander('🧠 Multitarefa da IA', expanded=False):
        st.caption('Peça uma ação livre para a IA executar na planilha final. Ela vai gerar sugestões por linha e você confirma antes de aplicar.')
        custom_task = st.text_area(
            'O que você quer que a IA faça na planilha?',
            key=task_key,
            height=96,
            placeholder='Ex: reformule todos os títulos dos produtos com no máximo 60 caracteres.',
        )
        st.caption('Exemplos rápidos')
        for index, example in enumerate(EXAMPLE_TASKS, start=1):
            st.button(
                example,
                use_container_width=True,
                key=_state_key(op, signature, f'example_{index}'),
                on_click=_set_custom_task,
                args=(task_key, example),
            )
        st.caption('Proteção ativa: a IA não aplica automaticamente e não deve alterar preço, GTIN/EAN, estoque, depósito, SKU, imagens ou URLs.')
    return str(custom_task or '').strip()


def _make_preview_ai_progress() -> tuple[object, object, object]:
    progress_bar = st.progress(0, text='IA aguardando início...')
    status_box = st.empty()
    counter_box = st.empty()
    return progress_bar, status_box, counter_box


def _progress_callback(progress_bar: object, status_box: object, counter_box: object):
    def _callback(info: dict) -> None:
        current = int(info.get('current') or 0)
        total = max(1, int(info.get('total') or 1))
        percent = int(info.get('percent') or 0)
        message = str(info.get('message') or '')
        stage = str(info.get('stage') or 'Processando')
        progress = max(0.0, min(1.0, float(info.get('progress') or 0.0)))
        progress_bar.progress(progress, text=f'{stage}: {current}/{total} produto(s) · {percent}%')
        status_box.caption(message)
        counter_box.caption(f'{current} de {total} produto(s) processado(s)')
    return _callback


def _append_suggestions(existing: object, new_df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(existing, pd.DataFrame) or existing.empty:
        return new_df
    if not isinstance(new_df, pd.DataFrame) or new_df.empty:
        return existing
    combined = pd.concat([existing, new_df], ignore_index=True)
    subset = [column for column in ['Linha', 'Campo', 'Coluna', 'Sugestão IA'] if column in combined.columns]
    if subset:
        combined = combined.drop_duplicates(subset=subset, keep='last')
    return combined.reset_index(drop=True)


def _marked_suggestions_count(df: pd.DataFrame) -> int:
    if not isinstance(df, pd.DataFrame) or df.empty or 'Aplicar' not in df.columns:
        return 0
    return int(df['Aplicar'].fillna(False).astype(bool).sum())


def _affected_products_count(df: pd.DataFrame) -> int:
    if not isinstance(df, pd.DataFrame) or df.empty or 'Linha' not in df.columns:
        return 0
    if 'Aplicar' in df.columns:
        selected = df[df['Aplicar'].fillna(False).astype(bool)]
    else:
        selected = df
    if selected.empty:
        return 0
    return int(selected['Linha'].nunique())


def render_preview_ai_actions(df_final: pd.DataFrame | None, operation: str) -> None:
    if not isinstance(df_final, pd.DataFrame) or df_final.empty:
        return

    op = str(operation or 'arquivo').strip().lower() or 'arquivo'
    label = _operation_label(op)
    signature = df_signature(df_final)
    suggestions_key = _state_key(op, signature, 'suggestions')
    status_key = _state_key(op, signature, 'status')
    editor_key = _state_key(op, signature, 'editor')
    offset_key = _state_key(op, signature, 'offset')
    resources = dict(DEFAULT_PREVIEW_AI_POLICY)
    total_rows = int(len(df_final))

    st.markdown(
        """
        <div class="bling-inline-card">
            <div class="bling-flow-card-kicker">IA de catálogo</div>
            <div class="bling-flow-card-title">Revisar produtos com IA</div>
            <p class="bling-flow-card-text">A IA analisa todos os produtos do preview final e gera sugestões apenas onde encontrar ajuste seguro.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _render_marketplace_guard_alerts(df_final, resources)

    if op != 'cadastro':
        st.caption('A IA de catálogo foi feita para produto/cadastro. No estoque ela fica disponível só como apoio quando houver colunas compatíveis.')

    if ai_ready():
        st.success('IA conectada. As sugestões serão geradas com a chave OpenAI informada no sidebar.')
    else:
        st.warning('Chave OpenAI não informada no sidebar. O sistema ainda pode mostrar sugestões locais simples, mas ortografia/gramática, NCM e multitarefa livre precisam da IA conectada.')

    _render_detected_columns(df_final)

    st.markdown('##### O que a IA deve fazer agora?')
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        use_title = st.checkbox('Títulos', value=True, key=_state_key(op, signature, 'use_title'))
    with col2:
        use_description = st.checkbox('Descrições', value=True, key=_state_key(op, signature, 'use_description'))
    with col3:
        use_grammar = st.checkbox('Ortografia', value=False, key=_state_key(op, signature, 'use_grammar'))
    with col4:
        use_ncm = st.checkbox('NCM vazio', value=True, key=_state_key(op, signature, 'use_ncm'))

    custom_task = _render_multitask_box(op, signature)

    current_offset = int(st.session_state.get(offset_key, 0) or 0)
    current_offset = max(0, min(current_offset, total_rows))
    remaining = max(0, total_rows - current_offset)

    st.markdown('##### Controle de execução')
    col_batch, col_limit = st.columns(2)
    with col_batch:
        batch_size = st.selectbox(
            'Produtos por lote',
            [5, 10, 20, 50],
            index=1,
            key=_state_key(op, signature, 'batch_size'),
            help='Use 5 ou 10 quando a IA estiver dando timeout. Isso não muda o total, só divide o processamento.',
        )
    with col_limit:
        max_rows_run = st.number_input(
            'Analisar produtos nesta execução',
            min_value=5,
            max_value=max(5, total_rows),
            value=max(5, remaining or total_rows),
            step=5,
            key=_state_key(op, signature, 'max_rows_run'),
            help='Padrão: todos os produtos restantes. Reduza apenas se houver timeout.',
        )

    if current_offset > 0 and current_offset < total_rows:
        st.info(f'Continuação disponível: próxima execução começa em {current_offset + 1}/{total_rows} e pode analisar todos os {remaining} produto(s) restantes.')
    elif current_offset >= total_rows:
        st.success('Todos os produtos já foram analisados pela IA. Agora aplique as sugestões geradas.')
    else:
        st.info(f'A próxima execução pode analisar todos os {total_rows} produto(s) do preview final.')

    col_reset, _ = st.columns([1, 2])
    with col_reset:
        if st.button('Reiniciar IA', use_container_width=True, key=_state_key(op, signature, 'reset_ai')):
            st.session_state[offset_key] = 0
            st.session_state.pop(suggestions_key, None)
            st.session_state.pop(status_key, None)
            st.rerun()

    can_run = bool(use_title or use_description or use_grammar or use_ncm or custom_task) and current_offset < total_rows
    run_label = f'🤖 Analisar todos os produtos restantes com IA · {label}'
    if st.button(run_label, use_container_width=True, disabled=not can_run, key=_state_key(op, signature, 'run')):
        progress_bar, status_box, counter_box = _make_preview_ai_progress()
        suggestions, status, next_offset = generate_product_ai_suggestions_batched(
            df_final,
            actions={'title': bool(use_title), 'description': bool(use_description), 'grammar': bool(use_grammar), 'ncm': bool(use_ncm)},
            max_rows=int(max_rows_run),
            custom_task=custom_task,
            batch_size=int(batch_size or DEFAULT_AI_BATCH_SIZE),
            start_offset=current_offset,
            progress_callback=_progress_callback(progress_bar, status_box, counter_box),
        )
        new_suggestions_df = _apply_ai_resource_policy_to_dataframe(suggestions_to_dataframe(suggestions))
        st.session_state[suggestions_key] = _append_suggestions(st.session_state.get(suggestions_key), new_suggestions_df)
        st.session_state[status_key] = status
        st.session_state[offset_key] = next_offset
        add_debug(f'IA de catálogo executada de {current_offset + 1} até {next_offset} de {total_rows} linha(s) no preview final de {label}: {status}', origin='PREVIEW_IA', level='INFO')
        st.success(f'IA analisou até {next_offset}/{total_rows} produto(s).')
        st.rerun()

    status = st.session_state.get(status_key)
    if status:
        st.caption(str(status))

    suggestions_df = st.session_state.get(suggestions_key)
    if not isinstance(suggestions_df, pd.DataFrame):
        return

    suggestions_df = _apply_ai_resource_policy_to_dataframe(suggestions_df)
    st.session_state[suggestions_key] = suggestions_df

    if suggestions_df.empty:
        st.info('A IA analisou os produtos, mas não encontrou alterações seguras para aplicar.')
        return

    total_suggestions = int(len(suggestions_df))
    affected_before_editor = _affected_products_count(suggestions_df)
    st.info(f'IA analisou {min(current_offset, total_rows)}/{total_rows} produto(s) e gerou {total_suggestions} sugestão(ões) para {affected_before_editor} produto(s). Produtos sem sugestão não serão alterados.')

    st.markdown('##### Antes/depois sugerido pela IA')
    edited = _render_suggestions_editor(suggestions_df, editor_key)

    preview_applied = apply_product_ai_suggestions(df_final, edited)
    with st.expander('Prévia da planilha final se aplicar as sugestões marcadas', expanded=False):
        preview_df(f'Prévia com IA · {label}', preview_applied)

    apply_count = _marked_suggestions_count(edited)
    affected_products = _affected_products_count(edited)
    button_label = f'✅ Aplicar {apply_count} sugestão(ões) em {affected_products} produto(s) da planilha final'
    if st.button(button_label, use_container_width=True, key=_state_key(op, signature, 'apply')):
        if apply_count <= 0:
            st.warning('Nenhuma sugestão marcada para aplicar.')
            return
        df_applied = apply_product_ai_suggestions(df_final, edited)
        _store_applied_df(op, df_applied)
        add_debug(f'{apply_count} sugestão(ões) da IA aplicadas em {affected_products} produto(s) na planilha final de {label}.', origin='PREVIEW_IA', level='INFO')
        st.success(f'Sugestões aplicadas em {affected_products} produto(s). Confira novamente o preview antes de baixar.')
        st.rerun()


__all__ = ['render_preview_ai_actions']
