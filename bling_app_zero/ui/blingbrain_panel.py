from __future__ import annotations

from datetime import datetime
from typing import Any

import streamlit as st

from bling_app_zero.ai_tools import build_blingbrain_response


EXAMPLES = [
    'Revisar descrições antes do download final',
    'Reformular títulos dos produtos',
    'Procurar a palavra bluetooth nas descrições',
    'Sugerir NCM para revisão manual',
    'Verificar GTINs inválidos e gerar SKU interno quando faltar código',
]

TASKS_KEY = 'blingbrain_tasks'
PROMPT_KEY = 'blingbrain_prompt'


def _current_context() -> tuple[str, str]:
    etapa = str(
        st.session_state.get('etapa_fluxo')
        or st.session_state.get('etapa')
        or st.session_state.get('home_slim_step')
        or 'etapa atual'
    )
    operacao = str(
        st.session_state.get('tipo_operacao')
        or st.session_state.get('operacao_final')
        or st.session_state.get('home_slim_flow_operation')
        or 'fluxo atual'
    )
    return etapa, operacao


def _tasks() -> list[dict[str, Any]]:
    tasks = st.session_state.get(TASKS_KEY)
    if isinstance(tasks, list):
        return tasks
    st.session_state[TASKS_KEY] = []
    return st.session_state[TASKS_KEY]


def _short(text: str, limit: int = 42) -> str:
    value = str(text or '').strip().replace('\n', ' ')
    return value if len(value) <= limit else value[: limit - 3] + '...'


def _add_task(prompt: str, etapa: str, operacao: str) -> None:
    clean_prompt = str(prompt or '').strip()
    if not clean_prompt:
        return
    response = build_blingbrain_response(clean_prompt, etapa=etapa, operacao=operacao)
    tasks = _tasks()
    tasks.insert(
        0,
        {
            'created_at': datetime.now().strftime('%H:%M:%S'),
            'prompt': clean_prompt,
            'etapa': etapa,
            'operacao': operacao,
            'validated': False,
            'response': response,
        },
    )
    # Mantém a sidebar leve no celular.
    del tasks[8:]
    st.session_state[PROMPT_KEY] = ''


def _validate_task(index: int) -> None:
    tasks = _tasks()
    if 0 <= index < len(tasks):
        tasks[index]['validated'] = True


def _remove_task(index: int) -> None:
    tasks = _tasks()
    if 0 <= index < len(tasks):
        tasks.pop(index)


def _clear_tasks() -> None:
    st.session_state[TASKS_KEY] = []


def _render_examples() -> None:
    with st.expander('Exemplos', expanded=False):
        for example in EXAMPLES:
            if st.button(example, use_container_width=True, key=f'blingbrain_example_{example}'):
                st.session_state[PROMPT_KEY] = example


def _render_task(task: dict[str, Any], index: int) -> None:
    response = task.get('response')
    if response is None:
        return
    badge = '✅' if task.get('validated') else '🕓'
    title = f'{badge} {task.get("created_at", "")}: {_short(task.get("prompt", ""))}'
    with st.expander(title, expanded=index == 0 and not task.get('validated')):
        st.caption(f'Contexto: {task.get("operacao")} · {task.get("etapa")}')
        st.success(response.title)
        st.caption(response.safety)
        st.markdown('**Plano sugerido:**')
        for step in response.steps:
            st.markdown(f'- {step}')
        col1, col2 = st.columns(2)
        with col1:
            if st.button('Validar', use_container_width=True, key=f'blingbrain_validate_{index}'):
                _validate_task(index)
                st.rerun()
        with col2:
            if st.button('Remover', use_container_width=True, key=f'blingbrain_remove_{index}'):
                _remove_task(index)
                st.rerun()


def render_blingbrain_panel() -> None:
    st.markdown('##### 🧠 BlingBrain')
    st.caption('Multitarefas: peça uma ajuda, valide, peça outra e continue sem apagar o histórico.')

    etapa, operacao = _current_context()
    st.caption(f'Contexto detectado: {operacao} · {etapa}')

    prompt = st.text_area(
        'Pedido para IA',
        key=PROMPT_KEY,
        height=68,
        placeholder='Ex: reformule as descrições antes do download final',
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button('Adicionar tarefa', use_container_width=True, key='blingbrain_add_task'):
            _add_task(prompt, etapa, operacao)
            st.rerun()
    with col2:
        if st.button('Limpar', use_container_width=True, key='blingbrain_clear_tasks'):
            _clear_tasks()
            st.rerun()

    _render_examples()

    tasks = _tasks()
    if not tasks:
        st.info('Adicione uma tarefa para o BlingBrain orientar o próximo passo.')
        return

    st.caption(f'{len(tasks)} tarefa(s) no BlingBrain. Valide uma e adicione a próxima quando quiser.')
    for index, task in enumerate(tasks):
        _render_task(task, index)
