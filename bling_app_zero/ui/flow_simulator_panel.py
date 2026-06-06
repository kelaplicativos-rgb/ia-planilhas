from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Callable

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_oauth import connection_status, oauth_config_status
from bling_app_zero.features_runtime.registry import CONTRACTS, list_feature_contracts

RESPONSIBLE_FILE = 'bling_app_zero/ui/flow_simulator_panel.py'
SIMULATION_RESULT_KEY = 'blingfix_flow_simulation_result_v1'

Status = str


@dataclass(frozen=True)
class FlowCheck:
    area: str
    name: str
    status: Status
    message: str
    detail: str = ''

    def to_dict(self) -> dict[str, str]:
        return {
            'Área': self.area,
            'Verificação': self.name,
            'Status': self.status,
            'Mensagem': self.message,
            'Detalhe': self.detail,
        }


def _ok(area: str, name: str, message: str, detail: str = '') -> FlowCheck:
    return FlowCheck(area, name, 'OK', message, detail)


def _warn(area: str, name: str, message: str, detail: str = '') -> FlowCheck:
    return FlowCheck(area, name, 'ATENÇÃO', message, detail)


def _fail(area: str, name: str, message: str, detail: str = '') -> FlowCheck:
    return FlowCheck(area, name, 'ERRO', message, detail)


def _import_check(area: str, module_name: str, label: str) -> FlowCheck:
    try:
        importlib.import_module(module_name)
        return _ok(area, label, 'Módulo carregou sem erro de importação.', module_name)
    except Exception as exc:
        return _fail(area, label, 'Módulo não carregou. Fluxo pode quebrar na tela.', f'{module_name}: {exc}')


def _call_check(area: str, label: str, fn: Callable[[], object], ok_message: str) -> FlowCheck:
    try:
        value = fn()
        return _ok(area, label, ok_message, str(value)[:220])
    except Exception as exc:
        return _fail(area, label, 'Falha ao executar checagem segura.', str(exc)[:350])


def _check_startup_and_home() -> list[FlowCheck]:
    checks = [
        _import_check('Sistema', 'app', 'App principal'),
        _import_check('Sistema', 'bling_app_zero.ui.home', 'Home'),
        _import_check('Sistema', 'bling_app_zero.ui.home_router', 'Roteador da home'),
        _import_check('Sistema', 'bling_app_zero.ui.home_wizard', 'Wizard principal'),
        _import_check('Sistema', 'bling_app_zero.ui.startup_guard', 'Proteção de inicialização'),
    ]
    return checks


def _check_contracts() -> list[FlowCheck]:
    checks: list[FlowCheck] = []
    expected = [
        ('cadastro', 'api'),
        ('estoque', 'api'),
        ('atualizacao_preco', 'api'),
        ('cadastro', 'csv'),
        ('estoque', 'csv'),
        ('atualizacao_preco', 'csv'),
        ('universal', 'csv'),
    ]
    for key in expected:
        contract = CONTRACTS.get(key)
        label = f'{key[0]} · {key[1]}'
        if contract is None:
            checks.append(_fail('Contratos', label, 'Contrato ausente. Fluxo não tem espinha dorsal declarada.'))
            continue
        if not contract.steps:
            checks.append(_fail('Contratos', label, 'Contrato sem etapas.'))
            continue
        mode_ok = (key[1] == 'api' and contract.supports_api) or (key[1] == 'csv' and contract.supports_csv)
        if not mode_ok:
            checks.append(_warn('Contratos', label, 'Contrato existe, mas suporte API/CSV parece incoerente.', str(contract)))
            continue
        checks.append(_ok('Contratos', label, 'Contrato ativo e com etapas definidas.', ' → '.join(contract.steps)))
    checks.append(
        _call_check(
            'Contratos',
            'Listagem de contratos',
            lambda: len(list_feature_contracts()),
            'Registro de contratos respondeu corretamente.',
        )
    )
    return checks


def _check_oauth() -> list[FlowCheck]:
    checks: list[FlowCheck] = []
    try:
        config = oauth_config_status()
    except Exception as exc:
        return [_fail('Bling OAuth', 'Configuração OAuth', 'Não foi possível ler configuração OAuth.', str(exc))]

    if bool(config.get('ready')):
        checks.append(_ok('Bling OAuth', 'Configuração OAuth', 'Configuração mínima encontrada.', str(config)))
    else:
        missing = ', '.join(map(str, config.get('missing') or []))
        checks.append(_warn('Bling OAuth', 'Configuração OAuth', 'OAuth ainda não está pronto para usuário final.', f'Faltando: {missing or "backend_auth_url/client_id/client_secret"}'))

    try:
        status = connection_status()
        if bool(status.get('connected')):
            checks.append(_ok('Bling OAuth', 'Token/conexão', 'Bling conectado nesta sessão.', str(status)))
        else:
            checks.append(_warn('Bling OAuth', 'Token/conexão', 'Bling não conectado agora. Fluxos de API precisam conectar antes do envio.', str(status)))
    except Exception as exc:
        checks.append(_fail('Bling OAuth', 'Token/conexão', 'Falha ao consultar conexão Bling.', str(exc)))

    checks.extend(
        [
            _import_check('Bling OAuth', 'bling_app_zero.ui.bling_backend_bridge', 'Ponte backend OAuth'),
            _import_check('Bling OAuth', 'bling_app_zero.core.interaction_guard', 'Guarda de desconexão'),
        ]
    )
    return checks


def _check_sources() -> list[FlowCheck]:
    checks = [
        _import_check('Origem', 'bling_app_zero.ui.smart_upload', 'Upload inteligente'),
        _import_check('Origem', 'bling_app_zero.ui.cadastro_sources', 'Classificação de arquivos'),
        _import_check('Origem', 'bling_app_zero.ui.cadastro_entry_step', 'Entrada de dados'),
        _import_check('Origem', 'bling_app_zero.ui.site_panel', 'Painel de site'),
        _import_check('Origem', 'bling_app_zero.ui.site_panel_capture', 'Captura por site'),
        _import_check('Origem', 'bling_app_zero.ui.site_progress', 'Painel vivo de site'),
    ]
    try:
        from bling_app_zero.ui.smart_upload import SUPPORTED_TYPES

        required_types = {'xlsx', 'xls', 'csv', 'xml', 'pdf', 'html', 'mht', 'mhtml'}
        missing = sorted(required_types - set(SUPPORTED_TYPES))
        if missing:
            checks.append(_warn('Origem', 'Formatos aceitos', 'Alguns formatos esperados não estão liberados.', ', '.join(missing)))
        else:
            checks.append(_ok('Origem', 'Formatos aceitos', 'Formatos principais estão liberados.', ', '.join(SUPPORTED_TYPES)))
    except Exception as exc:
        checks.append(_fail('Origem', 'Formatos aceitos', 'Não consegui validar formatos aceitos.', str(exc)))
    return checks


def _check_processing_steps() -> list[FlowCheck]:
    return [
        _import_check('Processamento', 'bling_app_zero.ui.home_wizard_pricing_step', 'Precificação'),
        _import_check('Processamento', 'bling_app_zero.ui.cadastro_mapping_step', 'Mapeamento'),
        _import_check('Processamento', 'bling_app_zero.ui.mapping_review_panel', 'Revisão de mapeamento'),
        _import_check('Processamento', 'bling_app_zero.ui.rules_center_step', 'Regras e IA'),
        _import_check('Processamento', 'bling_app_zero.ui.cadastro_preview_step', 'Prévia final'),
        _import_check('Processamento', 'bling_app_zero.agents.blingsmartcore', 'BLINGSMARTCORE'),
    ]


def _check_outputs() -> list[FlowCheck]:
    return [
        _import_check('Saída', 'bling_app_zero.ui.cadastro_download_step', 'Download/envio final'),
        _import_check('Saída', 'bling_app_zero.ui.home_download', 'Motor de download/API'),
        _import_check('Saída', 'bling_app_zero.core.exporter', 'Exportador CSV Bling'),
        _import_check('Saída', 'bling_app_zero.ui.bling_api_batch_panel', 'Painel de envio API'),
        _import_check('Saída', 'bling_app_zero.core.bling_intelligent_update_sender', 'Sender inteligente Bling'),
        _import_check('Saída', 'bling_app_zero.core.bling_preflight_scan', 'Pré-varredura de envio'),
    ]


def _check_final_state() -> list[FlowCheck]:
    checks: list[FlowCheck] = []
    running = bool(st.session_state.get('site_capture_running'))
    rows = int(st.session_state.get('site_capture_rows') or 0)
    error = str(st.session_state.get('site_capture_error') or '').strip()
    if running:
        checks.append(_warn('Estado atual', 'Captura por site', 'Existe captura marcada como em andamento.', f'Linhas salvas: {rows}; erro: {error or "sem erro"}'))
    elif error:
        checks.append(_warn('Estado atual', 'Última captura por site', 'Existe erro/aviso de captura anterior.', error))
    else:
        checks.append(_ok('Estado atual', 'Captura por site', 'Nenhuma captura travada marcada no estado atual.'))

    final_df = st.session_state.get('df_final_cadastro_preview_rules_applied')
    if isinstance(final_df, pd.DataFrame) and not final_df.empty:
        checks.append(_ok('Estado atual', 'Prévia final', 'Existe base final validada na sessão.', f'{len(final_df)} linha(s), {len(final_df.columns)} coluna(s).'))
    else:
        checks.append(_warn('Estado atual', 'Prévia final', 'Nenhuma base final validada carregada nesta sessão. Normal se o fluxo ainda não chegou à prévia.'))
    return checks


def run_flow_simulation() -> list[FlowCheck]:
    checks: list[FlowCheck] = []
    for collector in (
        _check_startup_and_home,
        _check_contracts,
        _check_oauth,
        _check_sources,
        _check_processing_steps,
        _check_outputs,
        _check_final_state,
    ):
        checks.extend(collector())
    st.session_state[SIMULATION_RESULT_KEY] = [check.to_dict() for check in checks]
    add_audit_event(
        'blingfix_flow_simulation_ran',
        area='BLINGFIX',
        status='OK' if not any(check.status == 'ERRO' for check in checks) else 'ERRO',
        details={
            'total': len(checks),
            'ok': sum(1 for check in checks if check.status == 'OK'),
            'attention': sum(1 for check in checks if check.status == 'ATENÇÃO'),
            'errors': sum(1 for check in checks if check.status == 'ERRO'),
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return checks


def _render_summary(checks: list[FlowCheck]) -> None:
    total = len(checks)
    ok = sum(1 for check in checks if check.status == 'OK')
    attention = sum(1 for check in checks if check.status == 'ATENÇÃO')
    errors = sum(1 for check in checks if check.status == 'ERRO')
    cols = st.columns(4)
    cols[0].metric('Total', total)
    cols[1].metric('OK', ok)
    cols[2].metric('Atenção', attention)
    cols[3].metric('Erros', errors)
    if errors:
        st.error('Sistema ainda não está pronto para usuário final: existem erros bloqueantes.')
    elif attention:
        st.warning('Sistema passou sem erro técnico bloqueante, mas ainda possui pontos que exigem validação real ou configuração.')
    else:
        st.success('Simulação lógica aprovada. Faça apenas o teste real de ponta a ponta antes da entrega final.')


def _render_result_table(checks: list[FlowCheck]) -> None:
    df = pd.DataFrame([check.to_dict() for check in checks])
    if df.empty:
        st.caption('Nenhuma verificação executada ainda.')
        return
    st.dataframe(df, use_container_width=True, hide_index=True, height=360)
    csv = df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
    st.download_button(
        '⬇️ Baixar relatório da simulação',
        data=csv,
        file_name='blingfix_simulacao_fluxos.csv',
        mime='text/csv; charset=utf-8',
        use_container_width=True,
        key='download_blingfix_flow_simulation_report',
    )


def render_flow_simulator_panel() -> None:
    with st.sidebar.expander('✅ Verificar sistema', expanded=False):
        st.caption('Simula os fluxos por checagem segura. Não envia dados ao Bling e não altera produtos.')
        if st.button('Rodar simulação dos fluxos', use_container_width=True, key='run_blingfix_flow_simulation'):
            run_flow_simulation()
        stored = st.session_state.get(SIMULATION_RESULT_KEY)
        if isinstance(stored, list) and stored:
            checks = [
                FlowCheck(
                    area=str(item.get('Área') or ''),
                    name=str(item.get('Verificação') or ''),
                    status=str(item.get('Status') or ''),
                    message=str(item.get('Mensagem') or ''),
                    detail=str(item.get('Detalhe') or ''),
                )
                for item in stored
                if isinstance(item, dict)
            ]
            _render_summary(checks)
            _render_result_table(checks)
        else:
            st.info('Toque no botão para simular Home, OAuth, origem, site, mapeamento, prévia, download e envio API.')


__all__ = ['render_flow_simulator_panel', 'run_flow_simulation']
