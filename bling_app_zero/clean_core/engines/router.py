from __future__ import annotations

from ..operations import Operation
from .cadastro_site import CadastroSiteEngine
from .estoque_site import EstoqueSiteEngine


def get_engine(operation: Operation):
    if operation == Operation.ESTOQUE:
        return EstoqueSiteEngine()
    return CadastroSiteEngine()
