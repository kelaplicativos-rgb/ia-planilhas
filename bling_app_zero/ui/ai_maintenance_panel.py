from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import requests
import streamlit as st

from bling_app_zero.core.audit import add_audit_event, get_audit_events, get_audit_session_id
from bling_app_zero.core.debug import LOG_SESSION_KEY

RESPONSIBLE_FILE = 'bling_app_zero/ui/ai_maintenance_panel.py'
OPENAI_RESPONSES_URL = 'https://api.openai.com/v1/responses'
DEFAULT_MODEL = 'gpt-5.1-codex-mini'
SENSITIVE_KEYWORDS = (
    'password',
    'senha',
    'secret',
    'token',
    'client_secret',
    'authorization',
    'cookie',
    'api_key',
    'apikey',
)


def _is_sensitive_key(key: Any) -> bool:
    normalized = str(key or '').strip().lower()
    return any(word in normalized for word in SENSITIVE_KEYWORDS)


def _state_value_summary(value: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {'type': type(value).__name__}
    if value is None:
        summary['empty'] = True
        return summary
    if hasattr(value, 'shape') and hasattr(value, 'columns'):
        try:
            summary['shape'] = tuple(value.shape)
            summary['columns'] = [str(col) for col in list(value.columns)[:80]]
        except Exception:
            pass
        return summary
    if isinstance(value, (list, tuple, set, dict, str)):
        try:
            summary['length'] = len(value)
        except Exception:
            pass
    if isinstance(value, (bool, int, float)):
        summary['value'] = value
    elif isinstance(value, str):
        summary['preview'] = value[:220]
    return summary


def _session_state_summary() -> dict[str, Any]:
    state: dict[str, Any] = {}
    for key, value in st.session_state.items():
        text_key = str(key)
        if _is_sensitive_key(text_key):
            state[text_key] = {'type': type(value).__name__, 'value': '[REDACTED]'}
        else:
            state[text_key] = _state_value_summary(value)
    return state


def _safe_recent_logs(limit: int = 80) -> list[dict[str, Any]]:
    logs = list(st.session_state.get(LOG_SESSION_KEY, []))
    safe: list[dict[str, Any]] = []
    for item in logs[-limit:]:
        if not isinstance(item, dict):
            continue
        safe.append(
            {
                'hora': item.get('hora'),
                'nivel': item.get('nivel'),
                'origem': item.get('origem'),
                'mensagem': str(item.get('mensagem') or '')[:800],
            }
        )
    return safe


def _safe_recent_audit(limit: int = 80) -> list[dict[str, Any]]:
    events = get_audit_events()[-limit:]
    safe: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        safe.append(
            {
                'timestamp': event.get('timestamp'),
                'area': event.get('area'),
                'step': event.get('step'),
                'action': event.get('action'),
                'status': event.get('status'),
                'details': event.get('details'),
            }
        )
    return safe


def _current_route_summary() -> dict[str, Any]:
    try:
        query_params = dict(st.query_params)
    except Exception:
        query_params = {}
    return {
        'query_params': query_params,
        'audit_session_id': get_audit_session_id(),
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'responsible_file': RESPONSIBLE_FILE,
    }


def _build_diagnostic_payload(problem: str, mode: str, include_state: bool, include_logs: bool, include_audit: bool) -> dict[str, Any]:
    payload: dict[str, Any] = {
        'problem_reported_by_user': problem.strip(),
        'requested_mode': mode,
        'route': _current_route_summary(),
        'rules_for_ai': [
            'Nunca aplique mudanças direto em produção sem revisão do usuário.',
            'Responder em português do Brasil.',
            'Quando sugerir correção, informar arquivo/caminho e código completo quando possível.',
            'Preservar o fluxo principal do app e evitar mudanças desnecessárias.',
            'Ocultar ou mascarar qualquer segredo, token, senha ou chave.',
        ],
    }
    if include_state:
        payload['session_state_summary'] = _session_state_summary()
    if include_logs:
        payload['recent_technical_logs'] = _safe_recent_logs()
    if include_audit:
        payload['recent_audit_events'] = _safe_recent_audit()
    return payload


def _build_blingfix_prompt(payload: dict[str, Any]) -> str:
    return (
        'BLINGFIX ASSISTENTE TÉCNICO\n\n'
        'Acesse o repositório e busque os arquivos necessários. '
        'Devolva diagnóstico objetivo e, quando for correção de código, devolva arquivo/caminho + código completo corrigido.\n\n'
        'Repositório base: https://github.com/kelaplicativos-rgb/ia-planilhas/tree/main\n\n'
        'Contexto capturado pelo app:\n'
        f'{json.dumps(payload, ensure_ascii=False, indent=2, default=str)}'
    )


def _extract_openai_text(response_json: dict[str, Any]) -> str:
    if isinstance(response_json.get('output_text'), str):
        return response_json['output_text']
    chunks: list[str] = []
    for item in response_json.get('output', []) or []:
        if not isinstance(item, dict):
            continue
        for content in item.get('content', []) or []:
            if not isinstance(content, dict):
                continue
            text = content.get('text') or content.get('value')
            if isinstance(text, str):
                chunks.append(text)
    return '\n'.join(chunks).strip() or json.dumps(response_json, ensure_ascii=False, indent=2, default=str)[:8000]


def _call_openai_responses(api_key: str, model: str, prompt: str) -> str:
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    body = {
        'model': model.strip() or DEFAULT_MODEL,
        'input': prompt,
    }
    response = requests.post(OPENAI_RESPONSES_URL, headers=headers, json=body, timeout=90)
    if response.status_code >= 400:
        raise RuntimeError(f'OpenAI API retornou HTTP {response.status_code}: {response.text[:1200]}')
    return _extract_openai_text(response.json())


def _render_generated_prompt(prompt: str) -> None:
    st.text_area(
        'Prompt BLINGFIX pronto para copiar',
        value=prompt,
        height=260,
        key='ai_maintenance_generated_prompt_textarea',
    )
    st.download_button(
        'Baixar prompt técnico (.txt)',
        data=prompt.encode('utf-8'),
        file_name='blingfix_prompt_tecnico.txt',
        mime='text/plain; charset=utf-8',
        use_container_width=True,
        key='ai_maintenance_download_prompt',
    )


def render_ai_maintenance_panel() -> None:
    with st.sidebar:
        with st.expander('Assistente IA de correção', expanded=False):
            st.caption('Painel seguro: a IA diagnostica e prepara correções. Nada é aplicado em produção sem revisão.')

            api_key = st.text_input(
                'OpenAI API key opcional',
                type='password',
                key='ai_maintenance_openai_api_key',
                help='Use somente se quiser chamar a API direto pelo app. Se deixar vazio, o sistema gera um prompt BLINGFIX para copiar.',
            )
            model = st.text_input('Modelo', value=DEFAULT_MODEL, key='ai_maintenance_model')
            mode = st.selectbox(
                'Modo de trabalho',
                ['Diagnóstico', 'Gerar prompt BLINGFIX', 'Sugerir patch', 'Preparar issue GitHub'],
                key='ai_maintenance_mode',
            )
            problem = st.text_area(
                'Descreva o problema ou ajuste desejado',
                placeholder='Ex.: preview duplicado, botão aparecendo bloqueado, erro ao ler ZIP, etc.',
                height=120,
                key='ai_maintenance_problem',
            )

            include_state = st.checkbox('Incluir resumo seguro do estado da tela', value=True, key='ai_maintenance_include_state')
            include_logs = st.checkbox('Incluir últimos logs técnicos', value=True, key='ai_maintenance_include_logs')
            include_audit = st.checkbox('Incluir últimos eventos de auditoria', value=True, key='ai_maintenance_include_audit')

            if st.button('Preparar assistência técnica', use_container_width=True, key='ai_maintenance_prepare'):
                if not problem.strip():
                    st.warning('Descreva o problema antes de preparar a assistência técnica.')
                    return
                payload = _build_diagnostic_payload(problem, mode, include_state, include_logs, include_audit)
                prompt = _build_blingfix_prompt(payload)
                st.session_state['ai_maintenance_last_prompt'] = prompt
                st.session_state['ai_maintenance_last_payload'] = payload
                add_audit_event(
                    'ai_maintenance_prompt_prepared',
                    area='IA_MANUTENCAO',
                    details={'mode': mode, 'has_api_key': bool(api_key), 'responsible_file': RESPONSIBLE_FILE},
                )
                if api_key.strip():
                    try:
                        with st.spinner('Consultando a OpenAI API...'):
                            answer = _call_openai_responses(api_key.strip(), model, prompt)
                        st.session_state['ai_maintenance_last_answer'] = answer
                        add_audit_event('ai_maintenance_api_answered', area='IA_MANUTENCAO', details={'model': model, 'responsible_file': RESPONSIBLE_FILE})
                    except Exception as exc:
                        st.session_state['ai_maintenance_last_answer'] = ''
                        add_audit_event('ai_maintenance_api_failed', area='IA_MANUTENCAO', status='ERRO', details={'error': str(exc), 'responsible_file': RESPONSIBLE_FILE})
                        st.error(f'Falha ao chamar a API: {exc}')

            last_prompt = st.session_state.get('ai_maintenance_last_prompt')
            if isinstance(last_prompt, str) and last_prompt.strip():
                _render_generated_prompt(last_prompt)

            last_answer = st.session_state.get('ai_maintenance_last_answer')
            if isinstance(last_answer, str) and last_answer.strip():
                st.markdown('###### Resposta da IA')
                st.markdown(last_answer)
                st.download_button(
                    'Baixar resposta da IA (.md)',
                    data=last_answer.encode('utf-8'),
                    file_name='resposta_ia_manutencao.md',
                    mime='text/markdown; charset=utf-8',
                    use_container_width=True,
                    key='ai_maintenance_download_answer',
                )


__all__ = ['render_ai_maintenance_panel']
