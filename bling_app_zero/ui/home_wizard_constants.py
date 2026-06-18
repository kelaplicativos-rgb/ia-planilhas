from __future__ import annotations

from dataclasses import dataclass

# Chaves históricas mantidas como aliases de compatibilidade.
# No fluxo atual elas representam o mesmo modelo universal enviado pelo usuário.
HOME_CADASTRO_MODEL_KEY = 'home_modelo_cadastro_df'
HOME_ESTOQUE_MODEL_KEY = 'home_modelo_estoque_df'
GLOBAL_CADASTRO_MODEL_KEYS = ['df_modelo_cadastro', 'modelo_cadastro_df']
GLOBAL_ESTOQUE_MODEL_KEYS = ['df_modelo_estoque', 'modelo_estoque_df']

FLOW_ORIGIN_KEY = 'home_slim_flow_origin'
FLOW_OPERATION_KEY = 'home_slim_flow_operation'
FLOW_ACTIVE_KEY = 'home_slim_active_panel'
LEGACY_ORIGIN_RADIO_KEY = 'frontpage_origin_radio'
WIZARD_STEP_KEY = 'bling_wizard_step'

UNIVERSAL_OPERATION_VALUE = 'universal'

STEP_MODELO = 'modelo'
STEP_OPERACAO = 'operacao'
STEP_PRECIFICACAO = 'precificacao'
STEP_ORIGEM = 'origem'
STEP_ENTRADA = 'entrada'
STEP_CATEGORIZACAO = 'categorizacao'
STEP_REGRAS = 'regras'
STEP_MAPEAMENTO = 'mapeamento'
STEP_GERAR_ESTOQUE = 'gerar_estoque'
STEP_PREVIEW = 'preview'
STEP_DOWNLOAD = 'download'
STEP_PROCESSAR = 'processar'

UNIVERSAL_STEPS = [
    STEP_MODELO,
    STEP_ORIGEM,
    STEP_ENTRADA,
    STEP_PRECIFICACAO,
    STEP_CATEGORIZACAO,
    STEP_MAPEAMENTO,
    STEP_REGRAS,
    STEP_PREVIEW,
    STEP_DOWNLOAD,
]

CADASTRO_STEPS = list(UNIVERSAL_STEPS)
ESTOQUE_STEPS = list(UNIVERSAL_STEPS)
ALL_STEPS = list(dict.fromkeys(UNIVERSAL_STEPS + [STEP_OPERACAO, STEP_GERAR_ESTOQUE, STEP_PROCESSAR]))

STEP_LABELS = {
    STEP_MODELO: 'Modelo para mapear',
    STEP_OPERACAO: 'Etapa legada ocultada',
    STEP_ORIGEM: 'Origem dos dados',
    STEP_ENTRADA: 'Dados importados',
    STEP_PRECIFICACAO: 'Precificação',
    STEP_CATEGORIZACAO: 'Categorização Inteligente Automática',
    STEP_MAPEAMENTO: 'Mapeamento',
    STEP_GERAR_ESTOQUE: 'Etapa legada ocultada',
    STEP_REGRAS: 'Revisão final',
    STEP_PREVIEW: 'Prévia final',
    STEP_DOWNLOAD: 'Download',
    STEP_PROCESSAR: 'Processar',
}

DEFAULT_PENDING_MESSAGE = 'Conclua esta etapa para continuar.'

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
    'home_detected_operation',
    'home_slim_flow_operation',
    'active_feature_contract_key',
    'active_feature_operation',
    'active_feature_mode',
    'active_feature_steps',
    'features_runtime_last_results',
    'direct_bling_operation_choice',
    'direct_bling_operation_applied',
    'direct_bling_api_contract_active',
    'direct_bling_api_contract_df',
    'df_final_bling_api',
    'df_final_download_operation',
    'df_final_preview_operation',
    'final_download_operation',
    'flow_spine_operation',
    'flow_spine_mode',
    'flow_spine_origin',
    'flow_spine_api_batch_operation',
    'flow_spine_sender_operation',
    'flow_spine_final_title',
    'bling_finish_mode',
    'mapping_bling_api',
    'mapping_confidence_bling_api',
    'rules_center_reviewed',
    'bling_user_rules',
    'category_wizard_use_categorization_v1',
    'category_wizard_decision_v1',
    'category_wizard_source_key_v1',
    'category_conference_confirmed_v1',
    'category_conference_skipped_v1',
    'category_conference_stats_v1',
    'category_conference_analyzed_df_v1',
    'category_conference_source_signature_v1',
    'category_conference_values_signature_v1',
    'category_conference_dataset_signature_v1',
    'global_decision_dataset_signature_v1',
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
    'df_final_cadastro',
    'df_final_cadastro_preview_rules_applied',
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
    'site_capture_status',
    'site_capture_message',
    'site_capture_finished',
    'site_capture_result_ready',
    'site_capture_error',
    'site_capture_operation',
    'site_capture_rows',
    'site_capture_columns',
    'site_capture_started_at',
    'site_progress_last',
    'site_progress_log',
    'site_progress_last_seen_at',
    'neutral_site_progress_state_v1',
    'neutral_site_capture_state_v1',
    'neutral_site_capture_report_v1',
    'live_operation_progress_state_v1',
    'live_operation_progress_last_v1',
    'live_operation_progress_log_v1',
    'live_operation_progress_last_seen_at_v1',
    'site_stock_requested_columns_enforced',
    'site_stock_requested_columns_count',
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


def nav_for_step(step: str, steps: list[str] | None = None) -> WizardNav:
    safe_steps = list(steps or UNIVERSAL_STEPS)
    current = str(step or STEP_MODELO).strip().lower()
    if current not in safe_steps:
        current = safe_steps[0]
    return WizardNav(current=current, index=safe_steps.index(current), total=len(safe_steps), steps=safe_steps)


__all__ = [
    'ALL_STEPS',
    'CADASTRO_STEPS',
    'DEFAULT_PENDING_MESSAGE',
    'ESTOQUE_STEPS',
    'FLOW_ACTIVE_KEY',
    'FLOW_OPERATION_KEY',
    'FLOW_ORIGIN_KEY',
    'GLOBAL_CADASTRO_MODEL_KEYS',
    'GLOBAL_ESTOQUE_MODEL_KEYS',
    'HOME_CADASTRO_MODEL_KEY',
    'HOME_ESTOQUE_MODEL_KEY',
    'LEGACY_ORIGIN_RADIO_KEY',
    'RESET_OUTPUT_KEYS',
    'STEP_CATEGORIZACAO',
    'STEP_DOWNLOAD',
    'STEP_ENTRADA',
    'STEP_GERAR_ESTOQUE',
    'STEP_MAPEAMENTO',
    'STEP_MODELO',
    'STEP_OPERACAO',
    'STEP_ORIGEM',
    'STEP_PRECIFICACAO',
    'STEP_PREVIEW',
    'STEP_PROCESSAR',
    'STEP_REGRAS',
    'STEP_LABELS',
    'UNIVERSAL_OPERATION_VALUE',
    'UNIVERSAL_STEPS',
    'WIZARD_STEP_KEY',
    'WizardNav',
    'nav_for_step',
]
