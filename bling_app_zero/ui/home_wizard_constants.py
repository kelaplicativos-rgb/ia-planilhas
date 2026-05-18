from __future__ import annotations

from dataclasses import dataclass

HOME_CADASTRO_MODEL_KEY = 'home_modelo_cadastro_df'
HOME_ESTOQUE_MODEL_KEY = 'home_modelo_estoque_df'
GLOBAL_CADASTRO_MODEL_KEYS = ['df_modelo_cadastro', 'modelo_cadastro_df']
GLOBAL_ESTOQUE_MODEL_KEYS = ['df_modelo_estoque', 'modelo_estoque_df']
FLOW_ORIGIN_KEY = 'home_slim_flow_origin'
FLOW_OPERATION_KEY = 'home_slim_flow_operation'
FLOW_ACTIVE_KEY = 'home_slim_active_panel'
LEGACY_ORIGIN_RADIO_KEY = 'frontpage_origin_radio'
WIZARD_STEP_KEY = 'bling_wizard_step'

STEP_MODELO = 'modelo'
STEP_OPERACAO = 'operacao'
STEP_PRECIFICACAO = 'precificacao'
STEP_ORIGEM = 'origem'
STEP_ENTRADA = 'entrada'
STEP_REGRAS = 'regras'
STEP_MAPEAMENTO = 'mapeamento'
STEP_GERAR_ESTOQUE = 'gerar_estoque'
STEP_PREVIEW = 'preview'
STEP_DOWNLOAD = 'download'
STEP_PROCESSAR = 'processar'

# Ordem oficial do wizard.
# A etapa Regras deixa de ser uma tela solta: proteções globais e ajustes com IA
# passam a morar no contexto de mapeamento/preview, onde o usuário decide coluna,
# valor fixo, vazio ou ação assistida por IA.
CADASTRO_STEPS = [
    STEP_MODELO,
    STEP_OPERACAO,
    STEP_PRECIFICACAO,
    STEP_ORIGEM,
    STEP_ENTRADA,
    STEP_MAPEAMENTO,
    STEP_PREVIEW,
    STEP_DOWNLOAD,
]

# Calculadora compartilhada em todos os fluxos principais.
# No estoque ela fica disponível com toggle on/off para manter padrão global,
# mesmo quando o usuário optar por não alterar preço nesta operação.
ESTOQUE_STEPS = [
    STEP_MODELO,
    STEP_OPERACAO,
    STEP_PRECIFICACAO,
    STEP_ORIGEM,
    STEP_ENTRADA,
    STEP_GERAR_ESTOQUE,
    STEP_PREVIEW,
    STEP_DOWNLOAD,
]

ALL_STEPS = list(dict.fromkeys(CADASTRO_STEPS + ESTOQUE_STEPS + [STEP_REGRAS, STEP_PROCESSAR, STEP_PRECIFICACAO]))

STEP_LABELS = {
    STEP_MODELO: 'Modelo',
    STEP_OPERACAO: 'Operação',
    STEP_PRECIFICACAO: 'Preço',
    STEP_ORIGEM: 'Origem',
    STEP_REGRAS: 'Ajustes IA',
    STEP_ENTRADA: 'Entrada',
    STEP_MAPEAMENTO: 'Mapeamento + IA',
    STEP_GERAR_ESTOQUE: 'Gerar + IA',
    STEP_PREVIEW: 'Preview',
    STEP_DOWNLOAD: 'Download',
    STEP_PROCESSAR: 'Processar',
}

DEFAULT_PENDING_MESSAGE = 'Complete esta etapa para liberar o avanço.'

RESET_OUTPUT_KEYS = [
    FLOW_ORIGIN_KEY,
    FLOW_ACTIVE_KEY,
    'origem_final',
    'origem_dados',
    'origem_tipo',
    'origem_planilha_via_site',
    'site_gerou_origem_planilha',
    'tipo_operacao_site',
    'operation_site',
    'tipo_operacao',
    'operacao_final',
    'tipo_operacao_final',
    'bling_autofluxo_last_step',
    'bling_autofluxo_pause_step',
    'bling_autofluxo_last_move',
    'rules_center_reviewed',
    'bling_user_rules',
    'home_precificacao_inicial',
    'home_pricing_config',
    'cadastro_preco_calculado_ativo',
    'cadastro_preco_calculado_targets_aplicados',
    'cadastro_desconto_comissao',
    'df_origem_cadastro_precificada',
    'cadastro_wizard_df_origem',
    'cadastro_wizard_df_para_mapear',
    'cadastro_wizard_df_modelo',
    'cadastro_wizard_df_modelo_estoque',
    'cadastro_wizard_expected_source_rows',
    'cadastro_wizard_expected_source_signature',
    'cadastro_mapping_confirmed',
    'cadastro_mapping_confirmed_signature',
    'cadastro_supplier_price_master_filter_active',
    'cadastro_supplier_price_master_rows',
    'cadastro_supplier_price_master_signature',
    'cadastro_supplier_price_master_excess_rows_removed',
    'df_final_cadastro',
    'mapping_cadastro',
    'mapping_confidence_cadastro',
    'estoque_wizard_upload',
    'estoque_wizard_df_origem_site',
    'estoque_wizard_df_modelo',
    'estoque_source_signature_atual',
    'estoque_deposito_signature_atual',
    'estoque_multi_outputs',
    'df_final_estoque',
    'mapping_estoque',
    'mapping_confidence_estoque',
    'df_final_estoque_from_cadastro',
    'mapping_estoque_from_cadastro',
    'mapping_confidence_estoque_from_cadastro',
    'df_site_bruto',
    'df_site_bruto_cadastro',
    'df_site_bruto_estoque',
    'df_site_bruto_precos',
    'df_origem_site_como_planilha',
    'df_origem_site_como_planilha_cadastro',
    'df_origem_site_como_planilha_estoque',
    'site_operation_como_planilha',
    'site_source_urls_como_planilha',
    'site_source_urls_como_planilha_cadastro',
    'site_source_urls_como_planilha_estoque',
    'site_requested_columns_como_planilha',
    'site_requested_columns_como_planilha_cadastro',
    'site_requested_columns_como_planilha_estoque',
    'site_modelo_cadastro_como_planilha',
    'site_modelo_estoque_como_planilha',
    'site_modelo_operacao_como_planilha',
    'site_capture_running',
    'site_capture_finished',
    'site_capture_result_ready',
    'site_capture_error',
    'site_capture_operation',
    'site_capture_rows',
    'site_capture_columns',
    'site_capture_started_at',
    'guided_login_capture_config',
    'guided_login_capture_prompt',
    'guided_login_capture_last_prepared_at',
    'guided_login_security_resolved',
    'guided_login_confirmed_logged_in',
    'guided_login_products_page_ready',
    'guided_login_capture_mode',
]


@dataclass(frozen=True)
class WizardNav:
    current: str
    index: int
    total: int
    steps: list[str]


def nav_for_step(steps: list[str], current: str) -> WizardNav:
    if current not in steps:
        current = steps[0]
    return WizardNav(current=current, index=steps.index(current), total=len(steps), steps=steps)
