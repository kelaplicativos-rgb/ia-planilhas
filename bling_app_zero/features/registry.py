from __future__ import annotations

from dataclasses import replace

from bling_app_zero.features.contracts import FeatureDefinition
from bling_app_zero.features.download_pipeline import DOWNLOAD_FEATURES

RESPONSIBLE_FILE = 'bling_app_zero/features/registry.py'

# BLINGREFORM:
# O mapeamento passa a ser a única fonte de preenchimento de campos:
# - escolher coluna
# - escrever valor fixo
# - deixar vazio
# Portanto recursos de preenchimento por custom_rules ficam fora do runtime.
FILL_RULE_FEATURE_KEYS = {
    'custom_rules',
    'empty_custom_rules',
}

# Proteções que devem valer para todo CSV final do Bling, não só cadastro.
GLOBAL_DOWNLOAD_PROTECTION_KEYS = {
    'normalize_image_separator',
}


def _normalize_download_feature_scope(feature: FeatureDefinition) -> FeatureDefinition:
    if feature.key in GLOBAL_DOWNLOAD_PROTECTION_KEYS and feature.scope != 'global':
        return replace(feature, scope='global')
    return feature


ACTIVE_DOWNLOAD_FEATURES: tuple[FeatureDefinition, ...] = tuple(
    _normalize_download_feature_scope(feature)
    for feature in DOWNLOAD_FEATURES
    if feature.key not in FILL_RULE_FEATURE_KEYS
)

SITE_AND_SYSTEM_FEATURES: tuple[FeatureDefinition, ...] = (
    FeatureDefinition(
        key='site_cadastro_engine',
        title='Motor de cadastro por site',
        description='Captura dados completos de produtos para cadastro sem misturar regra de estoque.',
        scope='cadastro',
        stage='entrada',
        status='beta',
        state_key='feature_site_cadastro_engine_enabled',
        requires=('links_fornecedor',),
        provides=('cadastro_wizard_df_origem', 'cadastro_wizard_df_para_mapear'),
        owner_file='bling_app_zero/engines/site_operations/cadastro_engine.py',
    ),
    FeatureDefinition(
        key='site_estoque_engine',
        title='Motor de estoque por site',
        description='Busca somente as colunas solicitadas pelo modelo de estoque.',
        scope='estoque',
        stage='entrada',
        status='beta',
        state_key='feature_site_estoque_enabled',
        requires=('modelo_estoque', 'links_fornecedor'),
        provides=('estoque_wizard_df_origem_site',),
        owner_file='bling_app_zero/engines/site_operations/estoque_engine.py',
    ),
    FeatureDefinition(
        key='system_reboot',
        title='Reiniciar sistema e voltar para Home',
        description='Limpa caches, estados e query params para começar o fluxo do zero.',
        scope='global',
        stage='global',
        status='stable',
        state_key='feature_system_reboot_enabled',
        provides=('session_state_clean', 'cache_clean'),
        owner_file='bling_app_zero/ui/system_reboot.py',
    ),
)

FEATURE_REGISTRY: tuple[FeatureDefinition, ...] = (
    *ACTIVE_DOWNLOAD_FEATURES,
    *SITE_AND_SYSTEM_FEATURES,
)


def list_features() -> list[FeatureDefinition]:
    return list(FEATURE_REGISTRY)


def get_feature(key: str) -> FeatureDefinition | None:
    wanted = str(key or '').strip()
    for feature in FEATURE_REGISTRY:
        if feature.key == wanted:
            return feature
    return None


def features_by_stage(stage: str) -> list[FeatureDefinition]:
    wanted = str(stage or '').strip().lower()
    return [feature for feature in FEATURE_REGISTRY if feature.stage == wanted]


def features_by_scope(scope: str) -> list[FeatureDefinition]:
    wanted = str(scope or '').strip().lower()
    return [feature for feature in FEATURE_REGISTRY if feature.scope == wanted or feature.scope == 'global']


__all__ = [
    'ACTIVE_DOWNLOAD_FEATURES',
    'FEATURE_REGISTRY',
    'FILL_RULE_FEATURE_KEYS',
    'GLOBAL_DOWNLOAD_PROTECTION_KEYS',
    'RESPONSIBLE_FILE',
    'features_by_scope',
    'features_by_stage',
    'get_feature',
    'list_features',
]
