from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.debug import add_debug

RESPONSIBLE_FILE = 'bling_app_zero/ui/blingscan_prompt_panel.py'
BLINGSCAN_PROMPT_KEY = 'blingscan_prompt_ready'
BLINGSCAN_LAST_RUN_KEY = 'blingscan_prompt_last_run'

STATE_KEYS_TO_SCAN: tuple[str, ...] = (
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
    'deposito_nome',
    'mapping_state',
    'mapeamento',
    'preco_calculado',
    'blingflow_simulation_result',
)


def _describe_value(value: Any) -> str:
    if isinstance(value, pd.DataFrame):
        return f'DataFrame linhas={len(value)} colunas={len(value.columns)} colunas_lista={list(value.columns)[:40]}'
    if isinstance(value, dict):
        return f'dict chaves={list(value.keys())[:40]}'
    if isinstance(value, (list, tuple, set)):
        return f'{type(value).__name__} tamanho={len(value)} amostra={list(value)[:20]}'
    if value is None:
        return 'None'
    text = str(value)
    if len(text) > 280:
        text = text[:280] + '...'
    return text


def _collect_state_snapshot() -> str:
    lines: list[str] = []
    for key in STATE_KEYS_TO_SCAN:
        if key not in st.session_state:
            lines.append(f'- {key}: AUSENTE')
            continue
        lines.append(f'- {key}: {_describe_value(st.session_state.get(key))}')
    return '\n'.join(lines)


def _collect_dataframe_snapshot() -> str:
    blocks: list[str] = []
    for key in ('df_origem', 'df_saida', 'df_precificado', 'df_final', 'df_modelo_cadastro', 'df_modelo_estoque'):
        value = st.session_state.get(key)
        if not isinstance(value, pd.DataFrame):
            continue
        columns = [str(column) for column in value.columns]
        required_like = [column for column in columns if any(token in column.lower() for token in ('descri', 'preço', 'preco', 'gtin', 'ean', 'imagem', 'estoque', 'depósito', 'deposito'))]
        blocks.append(
            '\n'.join(
                [
                    f'### {key}',
                    f'- linhas: {len(value)}',
                    f'- colunas: {columns[:80]}',
                    f'- colunas sensíveis encontradas: {required_like[:80]}',
                ]
            )
        )
    return '\n\n'.join(blocks) if blocks else 'Nenhum DataFrame principal carregado no momento.'


def build_blingscan_prompt() -> str:
    generated_at = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    state_snapshot = _collect_state_snapshot()
    dataframe_snapshot = _collect_dataframe_snapshot()

    return f'''BLINGSCAN AUTOMÁTICO

Data/hora da solicitação dentro do sistema: {generated_at}
Arquivo responsável pelo botão: {RESPONSIBLE_FILE}

Execute uma varredura completa no sistema IA Planilhas / Bling, usando o repositório oficial como fonte principal:

https://github.com/kelaplicativos-rgb/ia-planilhas/tree/main

Objetivo:
Detectar erros visuais, erros de fluxo, problemas de estado, botões indevidos, mensagens confusas, duplicações de tela, campos aparecendo fora da etapa correta, problemas de mapeamento, bloqueios mal sinalizados, pré-requisitos não cumpridos, inconsistências entre cadastro e atualização de estoque, problemas no preview final e riscos antes do download CSV.

Contexto capturado automaticamente da sessão atual:

{state_snapshot}

Resumo dos DataFrames carregados:

{dataframe_snapshot}

Verifique especialmente:

1. Fluxo geral do sistema
- Origem dos dados
- Upload dos modelos
- Cadastro de produtos
- Atualização de estoque
- Busca por site
- Mapeamento
- Precificação
- Preview final
- Download CSV
- Envio/API, se existir

2. Botões e navegação
- Se existe botão “Continuar” aparecendo mesmo quando a etapa está bloqueada
- Se botão bloqueado está claramente identificado
- Se existe opção de voltar sem apagar dados
- Se algum botão está duplicado, cortado ou fora de contexto
- Se o usuário consegue avançar sem cumprir pré-requisitos

3. Alertas e mensagens
- Toda mensagem de alerta, bloqueio ou atenção deve usar visual diferenciado
- Preferir laranja claro para avisos e bloqueios
- Evitar alerta azul quando for algo que impede o avanço
- Mensagem bloqueante deve explicar exatamente o que falta fazer

4. Layout e UX
- Detectar elementos cortados
- Detectar excesso de informação na tela
- Detectar títulos duplicados
- Detectar seções repetidas
- Detectar botões com tamanho ruim
- Detectar telas confusas no mobile
- Detectar previews duplicados ou fora do lugar

5. Estado interno
- Verificar chaves de estado importantes do Streamlit
- Verificar se etapa atual está correta
- Verificar se df_origem, df_final, df_saida, df_precificado e modelos estão consistentes
- Verificar se voltar/avançar não limpa dados indevidamente
- Verificar se envio/API não altera df_final usado no download

6. Mapeamento
- Verificar colunas duplicadas nos selects
- Verificar se colunas já mapeadas somem das próximas opções
- Verificar se campos calculados ou automáticos ficam bloqueados
- Verificar se preço calculado entra em “Preço unitário (OBRIGATÓRIO)”
- Verificar se depósito automático aparece corretamente no fluxo de estoque
- Verificar se descrição curta/complementar não está sendo mapeada de forma errada

7. Cadastro x Estoque
- Confirmar que cadastro de produto e atualização de estoque usam motores separados
- No fluxo de estoque por site, buscar somente as colunas pedidas pela planilha modelo
- Se não encontrar uma informação solicitada pela planilha, deixar vazio
- Nome do produto pode aparecer apenas como apoio/identificação quando necessário

8. Exportação final
- Confirmar que o download final é CSV
- Confirmar separador “;”
- Confirmar encoding UTF-8-SIG
- Confirmar limpeza de GTIN inválido
- Confirmar imagens separadas por “|”
- Confirmar que df_final é a fonte única do download

Retorne o diagnóstico em formato claro:

- ERRO ENCONTRADO
- ARQUIVO PROVÁVEL
- GRAVIDADE: baixa, média ou alta
- IMPACTO NO USUÁRIO
- CORREÇÃO RECOMENDADA
- SE PRECISA BLINGFIX: sim ou não

Não altere código automaticamente nesta etapa.
Apenas faça a varredura e entregue o relatório.
'''


def _render_prompt_actions(prompt: str) -> None:
    st.text_area(
        'Prompt BLINGSCAN pronto para copiar',
        value=prompt,
        height=420,
        key='blingscan_prompt_textarea',
    )
    st.download_button(
        '⬇️ Baixar prompt BLINGSCAN .txt',
        data=prompt.encode('utf-8-sig'),
        file_name='blingscan_prompt.txt',
        mime='text/plain',
        use_container_width=True,
        key='download_blingscan_prompt_txt',
    )


def render_blingscan_prompt_panel() -> None:
    st.markdown('##### BLINGSCAN automático')
    st.caption('Gera um prompt completo com o estado atual da sessão para varrer fluxo, layout, botões, mapeamento, preview e exportação.')

    if st.button('🔎 Executar varredura BLINGSCAN', use_container_width=True, key='run_blingscan_prompt_builder'):
        prompt = build_blingscan_prompt()
        st.session_state[BLINGSCAN_PROMPT_KEY] = prompt
        st.session_state[BLINGSCAN_LAST_RUN_KEY] = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        add_debug('Prompt BLINGSCAN gerado pela sidebar.', origin='BLINGSCAN')
        add_audit_event(
            'blingscan_prompt_generated',
            area='DIAGNOSTICO',
            details={
                'responsible_file': RESPONSIBLE_FILE,
                'state_keys_scanned': list(STATE_KEYS_TO_SCAN),
            },
        )

    prompt = st.session_state.get(BLINGSCAN_PROMPT_KEY)
    if not prompt:
        st.info('Aperte o botão para gerar o prompt de varredura com o estado atual do sistema.')
        return

    last_run = st.session_state.get(BLINGSCAN_LAST_RUN_KEY, 'agora')
    st.success(f'Prompt BLINGSCAN gerado em {last_run}.')
    _render_prompt_actions(str(prompt))

    st.warning('Depois de colar este prompt no ChatGPT, se aparecer erro grave, execute BLINGFIX para corrigir.')


__all__ = ['build_blingscan_prompt', 'render_blingscan_prompt_panel']
