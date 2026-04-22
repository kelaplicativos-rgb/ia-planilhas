"""
REGISTRY DE FORNECEDORES

Responsável por:
- Registrar todos os fornecedores
- Detectar qual fornecedor usar pela URL
- Executar o fetch correto
"""

from typing import List, Optional, Dict, Any
from urllib.parse import urlparse

from bling_app_zero.core.suppliers.base import SupplierBase

# IMPORTS DOS FORNECEDORES
# (vamos criar esses arquivos nos próximos passos)
try:
    from bling_app_zero.core.suppliers.megacenter import MegaCenterSupplier
except:
    MegaCenterSupplier = None

try:
    from bling_app_zero.core.suppliers.atacadum import AtacadumSupplier
except:
    AtacadumSupplier = None

try:
    from bling_app_zero.core.suppliers.obaobamix import ObaObaMixSupplier
except:
    ObaObaMixSupplier = None

try:
    from bling_app_zero.core.suppliers.generic_supplier import GenericSupplier
except:
    GenericSupplier = None


# -------------------------------
# REGISTRO GLOBAL
# -------------------------------
class SupplierRegistry:

    def __init__(self):
        self.suppliers: List[SupplierBase] = []
        self._registrar_fornecedores()

    # -------------------------------
    # REGISTRAR TODOS OS FORNECEDORES
    # -------------------------------
    def _registrar_fornecedores(self):
        """
        Ordem importa!
        Específicos primeiro, genérico por último.
        """

        if MegaCenterSupplier:
            self.suppliers.append(MegaCenterSupplier())

        if AtacadumSupplier:
            self.suppliers.append(AtacadumSupplier())

        if ObaObaMixSupplier:
            self.suppliers.append(ObaObaMixSupplier())

        # SEMPRE POR ÚLTIMO
        if GenericSupplier:
            self.suppliers.append(GenericSupplier())

    # -------------------------------
    # DETECTAR FORNECEDOR
    # -------------------------------
    def detectar(self, url: str) -> Optional[SupplierBase]:
        """
        Retorna o fornecedor correto baseado na URL
        """

        if not url:
            return None

        for supplier in self.suppliers:
            try:
                if supplier.can_handle(url):
                    return supplier
            except Exception:
                continue

        return None

    # -------------------------------
    # EXECUTAR FETCH
    # -------------------------------
    def fetch(self, url: str, **kwargs) -> List[Dict[str, Any]]:
        """
        Executa o fornecedor correto
        """

        supplier = self.detectar(url)

        if not supplier:
            raise Exception(f"Nenhum fornecedor compatível para URL: {url}")

        produtos = supplier.fetch(url, **kwargs)

        # VALIDAÇÃO PADRÃO
        produtos = supplier.validar_produtos(produtos)

        return produtos

    # -------------------------------
    # FETCH + DATAFRAME (PADRÃO SISTEMA)
    # -------------------------------
    def fetch_dataframe(self, url: str, **kwargs):
        """
        Retorna direto como DataFrame
        """

        supplier = self.detectar(url)

        if not supplier:
            raise Exception(f"Nenhum fornecedor compatível para URL: {url}")

        produtos = supplier.fetch(url, **kwargs)

        produtos = supplier.validar_produtos(produtos)

        return supplier.to_dataframe(produtos)


# -------------------------------
# INSTÂNCIA GLOBAL (singleton simples)
# -------------------------------
_registry_instance: Optional[SupplierRegistry] = None


def get_registry() -> SupplierRegistry:
    global _registry_instance

    if _registry_instance is None:
        _registry_instance = SupplierRegistry()

    return _registry_instance


# -------------------------------
# FUNÇÃO PÚBLICA (USADA NO SITE_AGENT)
# -------------------------------
def fetch_produtos(url: str, **kwargs):
    """
    Função principal usada pelo sistema inteiro
    """

    registry = get_registry()
    return registry.fetch(url, **kwargs)


def fetch_produtos_df(url: str, **kwargs):
    """
    Retorna DataFrame direto
    """

    registry = get_registry()
    return registry.fetch_dataframe(url, **kwargs)
