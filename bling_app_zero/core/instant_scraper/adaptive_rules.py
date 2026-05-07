from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SiteAdaptiveRule:
    domain: str
    selectors: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


class AdaptiveRuleBook:
    """Base simples para aprendizado futuro de padrões por site.

    Nesta etapa inicial a classe mantém a arquitetura pronta sem persistir dados
    automaticamente, evitando efeitos colaterais no app publicado.
    """

    def __init__(self) -> None:
        self._rules: dict[str, SiteAdaptiveRule] = {}

    def get(self, domain: str) -> SiteAdaptiveRule:
        domain = (domain or "").strip().lower()
        return self._rules.setdefault(domain, SiteAdaptiveRule(domain=domain))

    def remember_selector(self, domain: str, field_kind: str, selector: str) -> None:
        rule = self.get(domain)
        if field_kind and selector:
            rule.selectors[field_kind] = selector

    def as_dict(self) -> dict[str, Any]:
        return {
            domain: {"selectors": rule.selectors, "notes": rule.notes}
            for domain, rule in self._rules.items()
        }
