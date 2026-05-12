from __future__ import annotations

from dataclasses import dataclass, field

from bling_app_zero.features.registry import list_features

RESPONSIBLE_FILE = 'bling_app_zero/features/validator.py'


@dataclass(frozen=True)
class FeatureArchitectureIssue:
    feature: str
    severity: str
    message: str


@dataclass(frozen=True)
class FeatureArchitectureReport:
    ok: bool
    total_features: int
    issues: list[FeatureArchitectureIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[FeatureArchitectureIssue]:
        return [issue for issue in self.issues if issue.severity == 'erro']

    @property
    def warnings(self) -> list[FeatureArchitectureIssue]:
        return [issue for issue in self.issues if issue.severity == 'aviso']


VALID_SCOPES = {'cadastro', 'estoque', 'global'}
VALID_STAGES = {'entrada', 'mapeamento', 'preview', 'download', 'sidebar', 'global'}
VALID_STATUS = {'stable', 'beta', 'experimental', 'disabled'}


def validate_feature_architecture() -> FeatureArchitectureReport:
    issues: list[FeatureArchitectureIssue] = []
    seen_keys: set[str] = set()
    features = list_features()

    for feature in features:
        key = str(feature.key or '').strip()
        if not key:
            issues.append(FeatureArchitectureIssue(feature='(sem chave)', severity='erro', message='Módulo sem key.'))
            continue
        if key in seen_keys:
            issues.append(FeatureArchitectureIssue(feature=key, severity='erro', message='Key duplicada no registry.'))
        seen_keys.add(key)

        if not str(feature.title or '').strip():
            issues.append(FeatureArchitectureIssue(feature=key, severity='erro', message='Módulo sem título.'))
        if not str(feature.description or '').strip():
            issues.append(FeatureArchitectureIssue(feature=key, severity='aviso', message='Módulo sem descrição.'))
        if feature.scope not in VALID_SCOPES:
            issues.append(FeatureArchitectureIssue(feature=key, severity='erro', message=f'Escopo inválido: {feature.scope}.'))
        if feature.stage not in VALID_STAGES:
            issues.append(FeatureArchitectureIssue(feature=key, severity='erro', message=f'Etapa inválida: {feature.stage}.'))
        if feature.status not in VALID_STATUS:
            issues.append(FeatureArchitectureIssue(feature=key, severity='erro', message=f'Status inválido: {feature.status}.'))
        if not str(feature.owner_file or '').strip():
            issues.append(FeatureArchitectureIssue(feature=key, severity='aviso', message='Módulo sem arquivo dono.'))
        if feature.status in {'stable', 'beta'} and not (feature.provides or feature.runner or feature.renderer):
            issues.append(
                FeatureArchitectureIssue(
                    feature=key,
                    severity='aviso',
                    message='Módulo ativo sem provides, runner ou renderer declarado.',
                )
            )

    ok = not any(issue.severity == 'erro' for issue in issues)
    return FeatureArchitectureReport(ok=ok, total_features=len(features), issues=issues)


__all__ = [
    'FeatureArchitectureIssue',
    'FeatureArchitectureReport',
    'validate_feature_architecture',
]
