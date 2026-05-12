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
STEP_MAPEAMENTO = 'mapeamento'
STEP_GERAR_ESTOQUE = 'gerar_estoque'
STEP_PREVIEW = 'preview'
STEP_DOWNLOAD = 'download'
STEP_PROCESSAR = 'processar'

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

ALL_STEPS = list(dict.fromkeys(CADASTRO_STEPS + ESTOQUE_STEPS + [STEP_PROCESSAR]))

STEP_LABELS = {
    STEP_MODELO: 'Modelo',
    STEP_OPERACAO: 'Operação',
    STEP_PRECIFICACAO: 'Preço',
    STEP_ORIGEM: 'Origem',
    STEP_ENTRADA: 'Entrada',
    STEP_MAPEAMENTO: 'Mapeamento',
    STEP_GERAR_ESTOQUE: 'Gerar',
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
    'tipo_operacao_site',
    'operation_site',
    'cadastro_wizard_df_origem',
    'cadastro_wizard_df_para_mapear',
    'cadastro_wizard_df_modelo',
    'cadastro_wizard_df_modelo_estoque',
    'cadastro_mapping_confirmed',
    'cadastro_mapping_confirmed_signature',
    'estoque_wizard_upload',
    'estoque_wizard_df_origem_site',
    'estoque_wizard_df_modelo',
    'df_final_cadastro',
    'mapping_cadastro',
    'mapping_confidence_cadastro',
    'estoque_multi_outputs',
    'df_final_estoque',
    'mapping_estoque',
]


@dataclass(frozen=True)
class WizardNav:
    current: str
    index: int
    total: int
    steps: list[str]
