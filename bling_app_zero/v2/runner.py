from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from bling_app_zero.v2.contracts import ModuleResult, ModuleSpec, TablePayload


@dataclass
class V2Runner:
    modules: list[ModuleSpec] = field(default_factory=list)

    def register(self, module: ModuleSpec) -> None:
        key = str(module.key or '').strip()
        if not key:
            raise ValueError('Modulo V2 sem chave.')
        if any(item.key == key for item in self.modules):
            raise ValueError(f'Modulo V2 duplicado: {key}')
        self.modules.append(module)

    def extend(self, modules: Iterable[ModuleSpec]) -> None:
        for module in modules:
            self.register(module)

    def select(self, operation: str, stage: str) -> list[ModuleSpec]:
        op = str(operation or 'global').strip().lower()
        stg = str(stage or 'global').strip().lower()
        selected: list[ModuleSpec] = []
        for module in self.modules:
            if not module.enabled:
                continue
            if module.operation not in {'global', op}:
                continue
            if module.stage not in {'global', stg}:
                continue
            selected.append(module)
        return selected

    def run(self, payload: TablePayload, stage: str | None = None) -> ModuleResult:
        current = payload.with_df(payload.df, stage=stage or payload.stage)
        warnings: list[str] = []
        executed: list[str] = []
        for module in self.select(str(current.operation), str(current.stage)):
            if module.runner is None:
                warnings.append(f'Modulo sem executor: {module.key}')
                continue
            result = module.runner(current)
            if not isinstance(result, ModuleResult):
                return ModuleResult(False, current, f'Retorno invalido: {module.key}', errors=(module.key,))
            executed.append(module.key)
            warnings.extend(result.warnings)
            if not result.ok:
                return ModuleResult(False, result.payload, result.message, warnings=tuple(warnings), errors=result.errors, metrics={'executed': executed})
            current = result.payload
        return ModuleResult(True, current, 'V2 executado com sucesso.', warnings=tuple(warnings), metrics={'executed': executed})


__all__ = ['V2Runner']
