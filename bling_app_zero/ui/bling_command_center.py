from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event, get_audit_events, get_audit_session_id
from bling_app_zero.core.debug import LOG_SESSION_KEY, add_debug

RESPONSIBLE_FILE = 'bling_app_zero/ui/bling_command_center.py'
COMMAND_PROMPT_KEY = 'bling_command_center_prompt'
COMMAND_NAME_KEY = 'bling_command_center_command_name'
COMMAND_LAST_RUN_KEY = 'bling_command_center_last_run'
REPOSITORY_URL = 'https://github.com/kelaplicativos-rgb/ia-planilhas/tree/main'

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

IMPORTANT_STATE_KEYS = (
    'etapa',
    'etapa_fluxo',
    'etapa_origem',
    'operacao',
    'tipo_operacao',
    'origem_dados',
    'origem_selecionada',
    'df_origem',
    'df_saida',
    'df_final',
    'df_precificado',
    'df_modelo_cadastro',
    'df_modelo_estoque',
    'df_origem_xml',
    'deposito_nome',
    'mapping_state',
    'mapeamento',
    'preco_calculado',
    'blingflow_simulation_result',
)


@dataclass(frozen=True)
class BlingCommand:
    name: str
    button_label: str
    category: str
    goal: str
    instruction: str
    output_format: str


BLING_COMMANDS: tuple[BlingCommand, ...] = (
    BlingCommand(
        name='BLINGSCAN',
        button_label='🔎 BLINGSCAN — varrer e diagnosticar',
        category='Análise',
        goal='Executar uma varredura geral no sistema para encontrar erros de fluxo, layout, estado, mapeamento, preview e exportação.',
        instruction='Não altere código nesta etapa. Analise o repositório e o contexto capturado. Liste erros, riscos e pontos de atenção com arquivo provável.',
        output_format='Retorne: ERRO ENCONTRADO, ARQUIVO PROVÁVEL, GRAVIDADE, IMPACTO NO USUÁRIO, CORREÇÃO RECOMENDADA, SE PRECISA BLINGFIX.',
    ),
    BlingCommand(
        name='BLINGFIX',
        button_label='🛠️ BLINGFIX — corrigir erro',
        category='Correção',
        goal='Corrigir bug ou comportamento errado mantendo a estrutura atual do projeto.',
        instruction='Acesse o repositório, busque os arquivos necessários e devolva os arquivos completos corrigidos. Evite mudanças desnecessárias.',
        output_format='Retorne sempre arquivo/caminho + código completo pronto para copiar e colar, ou aplique no repositório quando solicitado explicitamente.',
    ),
    BlingCommand(
        name='BLINGMASTERFIX',
        button_label='🧰 BLINGMASTERFIX — correção profunda',
        category='Correção',
        goal='Fazer correção mais profunda cruzando múltiplos arquivos relacionados.',
        instruction='Investigue imports, estado, chamadas entre módulos, UI e efeitos colaterais. Corrija a causa raiz, não apenas o sintoma.',
        output_format='Retorne diagnóstico por arquivo e os arquivos completos corrigidos, com cuidado para não quebrar fluxos já estabilizados.',
    ),
    BlingCommand(
        name='BLINGSCANMASTERFIX',
        button_label='🚨 BLINGSCANMASTERFIX — scan + correção raiz',
        category='Análise + Correção',
        goal='Executar scan profundo e preparar correção raiz dos problemas encontrados.',
        instruction='Primeiro diagnostique. Depois proponha/aplique correção apenas dos problemas confirmados. Não mexa fora do escopo.',
        output_format='Retorne: diagnóstico, causa raiz, arquivos afetados, correção aplicada/proposta e checklist final.',
    ),
    BlingCommand(
        name='BLINGMODULAR',
        button_label='🧩 BLINGMODULAR — modularizar arquivo grande',
        category='Arquitetura',
        goal='Separar arquivos grandes ou misturados em módulos menores sem alterar o comportamento final.',
        instruction='Use a regra: arquivos com mais de 400 linhas devem ser modularizados. Preserve nomes públicos, imports e compatibilidade.',
        output_format='Retorne nova estrutura de arquivos, responsabilidades por módulo e códigos completos dos arquivos criados/alterados.',
    ),
    BlingCommand(
        name='BLINGDETECTA',
        button_label='👀 BLINGDETECTA — detectar problema visual',
        category='UX/Layout',
        goal='Analisar tela, print ou estado atual para encontrar elementos cortados, duplicados, confusos ou fora de contexto.',
        instruction='Foque em UX, botões, alertas, textos, títulos duplicados, fluxo bloqueado e clareza visual. Não gere imagem.',
        output_format='Retorne achados visuais, impacto, arquivo provável e recomendação de ajuste.',
    ),
    BlingCommand(
        name='BLINGUX',
        button_label='🎨 BLINGUX — revisar interface e alertas',
        category='UX/Layout',
        goal='Melhorar clareza visual, botões, avisos laranja claro, bloqueios e navegação.',
        instruction='Atenção especial: alerta/bloqueio deve ter cor diferenciada, preferencialmente laranja claro; não mostrar botão Continuar quando pré-requisito faltar.',
        output_format='Retorne melhorias por tela/arquivo e código completo quando houver correção.',
    ),
    BlingCommand(
        name='BLINGFLOW',
        button_label='🧭 BLINGFLOW — revisar fluxo ponta a ponta',
        category='Fluxo',
        goal='Validar o caminho completo Origem → Mapeamento → Precificação → Preview → CSV/Envio.',
        instruction='Verifique avanço, voltar, pré-requisitos, preservação de dados e separação entre download e envio/API.',
        output_format='Retorne mapa do fluxo, gargalos, estados quebrados e correções recomendadas.',
    ),
    BlingCommand(
        name='BLINGMAP',
        button_label='🗺️ BLINGMAP — revisar mapeamento',
        category='Mapeamento',
        goal='Detectar falhas nos selects de mapeamento, colunas duplicadas, campos automáticos e confiança visual.',
        instruction='Verifique preço obrigatório, depósito, GTIN, descrições, colunas já mapeadas e bolinhas/indicadores de confiança.',
        output_format='Retorne problemas de mapeamento, arquivo provável e correção por arquivo.',
    ),
    BlingCommand(
        name='BLINGPRICE',
        button_label='💰 BLINGPRICE — revisar precificação',
        category='Precificação',
        goal='Validar calculadora de preço, lucro, taxas, impostos e reflexo em Preço unitário obrigatório.',
        instruction='Confirme que preço calculado entra no DataFrame correto, não duplica coluna e aparece no preview/download.',
        output_format='Retorne inconsistências, origem do preço, impacto e correção completa se necessário.',
    ),
    BlingCommand(
        name='BLINGSTOCK',
        button_label='📦 BLINGSTOCK — revisar estoque',
        category='Estoque',
        goal='Validar fluxo de atualização de estoque, depósito e motor independente de busca por site.',
        instruction='No estoque por site, buscar somente o que a planilha modelo pede. Se não encontrar, deixar vazio. Nome do produto só como apoio.',
        output_format='Retorne se cadastro e estoque estão separados, quais arquivos cuidam disso e correções recomendadas.',
    ),
    BlingCommand(
        name='BLINGCRAWLER',
        button_label='🕷️ BLINGCRAWLER — revisar busca por site',
        category='Crawler',
        goal='Analisar captura por site, extração de produto, imagem, preço, SKU, GTIN, disponibilidade e loop infinito.',
        instruction='Verifique fetch, anti-loop, limites, JSON-LD, meta tags, imagens separadas por | e heurísticas de estoque indisponível=0.',
        output_format='Retorne gargalos, riscos de loop, campos ausentes, arquivo provável e correção recomendada.',
    ),
    BlingCommand(
        name='BLINGCSV',
        button_label='📄 BLINGCSV — revisar exportação CSV',
        category='Exportação',
        goal='Validar download final CSV para Bling.',
        instruction='Confirmar separador ;, UTF-8-SIG, limpeza GTIN inválido, imagens com |, sanitização e df_final como fonte única.',
        output_format='Retorne checklist de exportação, falhas encontradas e correção por arquivo.',
    ),
    BlingCommand(
        name='BLINGDEPLOY',
        button_label='🚀 BLINGDEPLOY — revisar deploy/cache/versão',
        category='Deploy',
        goal='Verificar problemas de Streamlit Cloud, cache, versão, secrets e atualização do app publicado.',
        instruction='Analise app.py, versionamento, cache, requirements e possíveis falhas de deploy sem expor secrets.',
        output_format='Retorne causa provável, passos de correção e arquivos a alterar.',
    ),
    BlingCommand(
        name='BLINGLOGS',
        button_label='📋 BLINGLOGS — revisar logs e chaves de estado',
        category='Logs',
        goal='Melhorar logs técnicos, nomes de arquivos, chaves de estado e rastreabilidade.',
        instruction='Verifique se logs mostram etapa, arquivo responsável, chave de estado e erro útil para BLINGFIX.',
        output_format='Retorne melhorias de logging e código completo dos arquivos alterados.',
    ),
    BlingCommand(
        name='BLINGNEXT',
        button_label='➡️ BLINGNEXT — próxima evolução segura',
        category='Evolução',
        goal='Planejar a próxima melhoria sem quebrar o que já funciona.',
        instruction='Proponha evolução em módulos independentes, com baixo risco e checklist de validação.',
        output_format='Retorne plano em etapas, arquivos novos/alterados e riscos controlados.',
    ),
)


def _is_sensitive_key(key: Any) -> bool:
    normalized = str(key or '').strip().lower()
    return any(word in normalized for word in SENSITIVE_KEYWORDS)


def _summarize_value(value: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {'type': type(value).__name__}
    if value is None:
        summary['empty'] = True
        return summary
    if isinstance(value, pd.DataFrame):
        summary['shape'] = tuple(value.shape)
        summary['columns'] = [str(column) for column in list(value.columns)[:80]]
        return summary
    if isinstance(value, dict):
        summary['length'] = len(value)
        summary['keys'] = [str(key) for key in list(value.keys())[:80]]
        return summary
    if isinstance(value, (list, tuple, set)):
        summary['length'] = len(value)
        summary['sample'] = [str(item)[:120] for item in list(value)[:20]]
        return summary
    if isinstance(value, (bool, int, float)):
        summary['value'] = value
        return summary
    text = str(value)
    summary['preview'] = text[:260]
    if len(text) > 260:
        summary['truncated'] = True
    return summary


def _session_state_summary() -> dict[str, Any]:
    state: dict[str, Any] = {}
    for key in IMPORTANT_STATE_KEYS:
        if key not in st.session_state:
            state[key] = {'status': 'AUSENTE'}
            continue
        if _is_sensitive_key(key):
            state[key] = {'type': type(st.session_state.get(key)).__name__, 'value': '[REDACTED]'}
            continue
        state[key] = _summarize_value(st.session_state.get(key))
    return state


def _recent_logs(limit: int = 60) -> list[dict[str, Any]]:
    logs = list(st.session_state.get(LOG_SESSION_KEY, []))
    safe_logs: list[dict[str, Any]] = []
    for item in logs[-limit:]:
        if not isinstance(item, dict):
            continue
        safe_logs.append(
            {
                'hora': item.get('hora'),
                'nivel': item.get('nivel'),
                'origem': item.get('origem'),
                'mensagem': str(item.get('mensagem') or '')[:700],
            }
        )
    return safe_logs


def _recent_audit(limit: int = 60) -> list[dict[str, Any]]:
    safe_events: list[dict[str, Any]] = []
    for event in get_audit_events()[-limit:]:
        if not isinstance(event, dict):
            continue
        safe_events.append(
            {
                'timestamp': event.get('timestamp'),
                'area': event.get('area'),
                'step': event.get('step'),
                'action': event.get('action'),
                'status': event.get('status'),
                'details': event.get('details'),
            }
        )
    return safe_events


def _build_context_payload(include_logs: bool, include_audit: bool) -> dict[str, Any]:
    payload: dict[str, Any] = {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'repository': REPOSITORY_URL,
        'responsible_file': RESPONSIBLE_FILE,
        'audit_session_id': get_audit_session_id(),
        'important_session_state': _session_state_summary(),
    }
    if include_logs:
        payload['recent_logs'] = _recent_logs()
    if include_audit:
        payload['recent_audit_events'] = _recent_audit()
    return payload


def _build_command_prompt(command: BlingCommand, user_note: str, include_logs: bool, include_audit: bool) -> str:
    payload = _build_context_payload(include_logs=include_logs, include_audit=include_audit)
    note = user_note.strip() or 'Sem observação adicional do usuário.'
    return (
        f'{command.name}\n\n'
        'Acesse o repositório e use como fonte principal:\n'
        f'{REPOSITORY_URL}\n\n'
        f'Categoria: {command.category}\n'
        f'Objetivo: {command.goal}\n\n'
        f'Instrução principal:\n{command.instruction}\n\n'
        'Regras fixas deste projeto:\n'
        '- Responder em português do Brasil.\n'
        '- Preservar o fluxo principal do IA Planilhas / Bling.\n'
        '- Evitar mudanças desnecessárias que possam quebrar o sistema.\n'
        '- Quando houver correção de código, devolver arquivo/caminho + código completo corrigido.\n'
        '- Para correções no repositório, buscar os arquivos reais no GitHub antes de alterar.\n'
        '- Arquivos com mais de 400 linhas devem ser considerados para modularização.\n'
        '- Alertas e bloqueios devem ter visual diferenciado, preferencialmente laranja claro.\n'
        '- Não mostrar botão Continuar como disponível quando pré-requisito não estiver cumprido.\n'
        '- Cadastro de produto e atualização de estoque devem ter motores separados quando a função exigir.\n'
        '- No estoque por site, buscar somente as colunas solicitadas pela planilha modelo.\n'
        '- Download final deve ser CSV com separador ;, encoding UTF-8-SIG, GTIN inválido vazio e imagens separadas por |.\n\n'
        f'Observação do usuário:\n{note}\n\n'
        f'Formato esperado da resposta:\n{command.output_format}\n\n'
        'Contexto seguro capturado dentro do app:\n'
        f'{json.dumps(payload, ensure_ascii=False, indent=2, default=str)}\n'
    )


def _store_prompt(command: BlingCommand, prompt: str) -> None:
    st.session_state[COMMAND_PROMPT_KEY] = prompt
    st.session_state[COMMAND_NAME_KEY] = command.name
    st.session_state[COMMAND_LAST_RUN_KEY] = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    add_debug(f'Prompt {command.name} gerado pela Central de Comandos BLING.', origin='BLINGCOMMAND')
    add_audit_event(
        'bling_command_prompt_generated',
        area='COMANDOS_BLING',
        details={
            'command': command.name,
            'category': command.category,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def _render_command_button(command: BlingCommand, user_note: str, include_logs: bool, include_audit: bool) -> None:
    if st.button(command.button_label, use_container_width=True, key=f'bling_command_{command.name.lower()}'):
        prompt = _build_command_prompt(command, user_note=user_note, include_logs=include_logs, include_audit=include_audit)
        _store_prompt(command, prompt)


def _render_command_groups(user_note: str, include_logs: bool, include_audit: bool) -> None:
    categories = list(dict.fromkeys(command.category for command in BLING_COMMANDS))
    for category in categories:
        with st.expander(category, expanded=category in {'Análise', 'Correção'}):
            for command in [item for item in BLING_COMMANDS if item.category == category]:
                _render_command_button(command, user_note=user_note, include_logs=include_logs, include_audit=include_audit)


def _render_generated_prompt() -> None:
    prompt = st.session_state.get(COMMAND_PROMPT_KEY)
    if not isinstance(prompt, str) or not prompt.strip():
        st.info('Escolha um comando BLING para gerar o prompt pronto.')
        return

    command_name = st.session_state.get(COMMAND_NAME_KEY, 'BLING')
    last_run = st.session_state.get(COMMAND_LAST_RUN_KEY, 'agora')
    st.success(f'Prompt {command_name} gerado em {last_run}.')
    st.text_area(
        'Prompt pronto para copiar e colar no ChatGPT',
        value=prompt,
        height=360,
        key='bling_command_center_prompt_textarea',
    )
    st.download_button(
        f'⬇️ Baixar prompt {command_name}.txt',
        data=prompt.encode('utf-8-sig'),
        file_name=f'{str(command_name).lower()}_prompt.txt',
        mime='text/plain',
        use_container_width=True,
        key='bling_command_center_download_prompt',
    )


def render_bling_command_center() -> None:
    st.markdown('##### Central de Comandos BLING')
    st.caption('Botões rápidos para gerar prompts prontos de análise, correção, modularização, deploy, crawler, estoque, CSV e UX.')

    user_note = st.text_area(
        'Observação opcional para entrar no prompt',
        placeholder='Ex.: botão cortado, estoque não puxou depósito, mapeamento duplicou preço...',
        height=90,
        key='bling_command_center_user_note',
    )
    include_logs = st.checkbox('Incluir logs recentes no prompt', value=True, key='bling_command_center_include_logs')
    include_audit = st.checkbox('Incluir auditoria recente no prompt', value=True, key='bling_command_center_include_audit')

    _render_command_groups(user_note=user_note, include_logs=include_logs, include_audit=include_audit)
    _render_generated_prompt()


__all__ = ['render_bling_command_center']
