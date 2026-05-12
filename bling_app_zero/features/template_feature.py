from __future__ import annotations

from bling_app_zero.features.contracts import FeatureContext, FeatureDefinition, FeatureResult

# TEMPLATE OFICIAL BLINGMODULE
# Para criar recurso novo:
# 1. Copie este arquivo para bling_app_zero/features/<nome_do_recurso>.py
# 2. Renomeie FEATURE_KEY, FEATURE_DEFINITION e run_feature
# 3. Registre FEATURE_DEFINITION em bling_app_zero/features/registry.py
# 4. Se tiver UI, crie renderer próprio ou painel na sidebar
# 5. Nunca acesse st.session_state solto sem declarar state_key/requires/provides

FEATURE_KEY = 'template_feature'


def run_feature(context: FeatureContext) -> FeatureResult:
    """Runner padrão de um recurso plugável.

    Recebe FeatureContext e devolve FeatureResult. Não deve quebrar o fluxo principal.
    Em caso de erro previsível, retorne FeatureResult(ok=False, errors=[...]).
    """
    return FeatureResult(
        ok=True,
        message='Template executado sem alterações.',
        source_df=context.source_df,
        final_df=context.final_df,
    )


FEATURE_DEFINITION = FeatureDefinition(
    key=FEATURE_KEY,
    title='Template de recurso',
    description='Modelo base para criar novos recursos plugáveis no padrão BLINGMODULE.',
    scope='global',
    stage='global',
    status='disabled',
    state_key=f'feature_{FEATURE_KEY}_enabled',
    requires=(),
    provides=(),
    owner_file='bling_app_zero/features/template_feature.py',
    runner=run_feature,
)


__all__ = ['FEATURE_DEFINITION', 'FEATURE_KEY', 'run_feature']
