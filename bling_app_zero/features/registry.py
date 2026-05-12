from __future__ import annotations

from bling_app_zero.features.contracts import FeatureDefinition

RESPONSIBLE_FILE = 'bling_app_zero/features/registry.py'

# Registry oficial de recursos plugáveis.
# Regra: recurso novo deve entrar aqui com key, contrato, escopo, estágio e arquivo dono.
# Evite ligar recurso novo diretamente no app.py, home_wizard.py ou exporter.py sem contrato.
FEATURE_REGISTRY: tuple[FeatureDefinition, ...] = (
    FeatureDefinition(
        key='clean_invalid_gtin',
        title='Limpar GTIN inválido',
        description='Remove GTIN/EAN fora dos tamanhos aceitos antes do CSV final.',
        scope='global',
        stage='download',
        status='stable',
        state_key='clean_invalid_gtin',
        provides=('gtin_sanitizado',),
        owner_file='bling_app_zero/core/exporter.py',
    ),
    FeatureDefinition(
        key='normalize_image_separator',
        title='Separar imagens por |',
        description='Garante que múltiplas URLs de imagens saiam separadas por barra vertical no CSV.',
        scope='cadastro',
        stage='download',
        status='stable',
        state_key='normalize_image_separator',
        provides=('imagens_normalizadas',),
        owner_file='bling_app_zero/core/exporter.py',
    ),
    FeatureDefinition(
        key='normalize_measures_to_meters',
        title='Normalizar medidas para metro',
        description='Converte medidas como altura, largura e comprimento para o padrão esperado pelo Bling.',
        scope='cadastro',
        stage='download',
        status='beta',
        state_key='normalize_measures_to_meters',
        provides=('medidas_normalizadas',),
        owner_file='bling_app_zero/core/exporter.py',
    ),
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
        state_key='feature_site_estoque_engine_enabled',
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
    'FEATURE_REGISTRY',
    'RESPONSIBLE_FILE',
    'features_by_scope',
    'features_by_stage',
    'get_feature',
    'list_features',
]
