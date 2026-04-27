"""
REGISTRY DE FORNECEDORES

Responsável por:
- Registrar todos os fornecedores
- Detectar qual fornecedor usar pela URL
- Executar o fetch correto
- Diagnosticar fornecedores carregados ou indisponíveis

BLINGFIX:
- Não esconde mais erro de import silenciosamente.
- Mantém compatibilidade com o fluxo atual.
- Registra fornecedores indisponíveis em REGISTRY_IMPORT_ERRORS.
- Expõe diagnóstico por get_registry_diagnostics().
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Type

from bling_app_zero.core.suppliers.base import SupplierBase


REGISTRY_IMPORT_ERRORS: Dict[str, str] = {}


def _registrar_erro_import(nome: str, exc: Exception) -> None:
    REGISTRY_IMPORT_ERRORS[nome] = f"{exc.__class__.__name__}: {exc}"


def _importar_fornecedor(nome: str, caminho_modulo: str, nome_classe: str):
    """
    Importa fornecedor sem derrubar o app inteiro.

    Antes:
    - o registry usava except vazio;
    - fornecedor quebrado sumia silenciosamente;
    - o usuário achava que estava usando fornecedor específico.

    Agora:
    - erro fica registrado em REGISTRY_IMPORT_ERRORS;
    - fluxo segue usando outros fornecedores disponíveis;
    - diagnóstico pode ser exibido em tela/log.
    """
    try:
        modulo = __import__(caminho_modulo, fromlist=[nome_classe])
        classe = getattr(modulo, nome_classe)
        REGISTRY_IMPORT_ERRORS.pop(nome, None)
        return classe
    except Exception as exc:
        _registrar_erro_import(nome, exc)
        return None


MegaCenterSupplier = _importar_fornecedor(
    nome="Mega Center",
    caminho_modulo="bling_app_zero.core.suppliers.megacenter",
    nome_classe="MegaCenterSupplier",
)

AtacadumSupplier = _importar_fornecedor(
    nome="Atacadum",
    caminho_modulo="bling_app_zero.core.suppliers.atacadum",
    nome_classe="AtacadumSupplier",
)

ObaObaMixSupplier = _importar_fornecedor(
    nome="Oba Oba Mix",
    caminho_modulo="bling_app_zero.core.suppliers.obaobamix",
    nome_classe="ObaObaMixSupplier",
)

GenericSupplier = _importar_fornecedor(
    nome="Genérico",
    caminho_modulo="bling_app_zero.core.suppliers.generic_supplier",
    nome_classe="GenericSupplier",
)


class SupplierRegistry:
    def __init__(self):
        self.suppliers: List[SupplierBase] = []
        self.status_fornecedores: List[Dict[str, Any]] = []
        self._registrar_fornecedores()

    def _adicionar_status(
        self,
        nome: str,
        status: str,
        classe: Optional[Type[SupplierBase]] = None,
        erro: str = "",
    ) -> None:
        self.status_fornecedores.append(
            {
                "nome": nome,
                "status": status,
                "classe": getattr(classe, "__name__", "") if classe is not None else "",
                "erro": erro,
            }
        )

    def _instanciar_fornecedor(self, nome: str, classe) -> Optional[SupplierBase]:
        if classe is None:
            self._adicionar_status(
                nome=nome,
                status="indisponivel",
                classe=None,
                erro=REGISTRY_IMPORT_ERRORS.get(nome, "Classe não carregada."),
            )
            return None

        try:
            fornecedor = classe()
            self._adicionar_status(
                nome=nome,
                status="ok",
                classe=classe,
                erro="",
            )
            return fornecedor
        except Exception as exc:
            erro = f"{exc.__class__.__name__}: {exc}"
            self._adicionar_status(
                nome=nome,
                status="erro_instanciacao",
                classe=classe,
                erro=erro,
            )
            return None

    def _registrar_fornecedores(self) -> None:
        """
        Ordem importa:
        - fornecedores específicos primeiro;
        - fornecedor genérico por último.
        """

        fornecedores = [
            ("Mega Center", MegaCenterSupplier),
            ("Atacadum", AtacadumSupplier),
            ("Oba Oba Mix", ObaObaMixSupplier),
            ("Genérico", GenericSupplier),
        ]

        for nome, classe in fornecedores:
            fornecedor = self._instanciar_fornecedor(nome, classe)
            if fornecedor is not None:
                self.suppliers.append(fornecedor)

    def diagnostico(self) -> Dict[str, Any]:
        return {
            "total_carregados": len(self.suppliers),
            "fornecedores": list(self.status_fornecedores),
            "erros_import": dict(REGISTRY_IMPORT_ERRORS),
            "ordem_execucao": [
                str(getattr(supplier, "nome", supplier.__class__.__name__))
                for supplier in self.suppliers
            ],
        }

    def detectar(self, url: str) -> Optional[SupplierBase]:
        """
        Retorna o fornecedor correto baseado na URL.
        """

        if not url:
            return None

        for supplier in self.suppliers:
            try:
                if supplier.can_handle(url):
                    return supplier
            except Exception as exc:
                nome = str(getattr(supplier, "nome", supplier.__class__.__name__))
                REGISTRY_IMPORT_ERRORS[f"can_handle:{nome}"] = f"{exc.__class__.__name__}: {exc}"
                continue

        return None

    def fetch(self, url: str, **kwargs) -> List[Dict[str, Any]]:
        """
        Executa o fornecedor correto.
        """

        supplier = self.detectar(url)

        if not supplier:
            diagnostico = self.diagnostico()
            disponiveis = ", ".join(diagnostico.get("ordem_execucao", [])) or "nenhum"
            raise Exception(
                f"Nenhum fornecedor compatível para URL: {url}. "
                f"Fornecedores carregados: {disponiveis}."
            )

        produtos = supplier.fetch(url, **kwargs)

        try:
            produtos = supplier.validar_produtos(produtos)
        except Exception as exc:
            nome = str(getattr(supplier, "nome", supplier.__class__.__name__))
            REGISTRY_IMPORT_ERRORS[f"validar:{nome}"] = f"{exc.__class__.__name__}: {exc}"
            raise

        return produtos

    def fetch_dataframe(self, url: str, **kwargs):
        """
        Retorna direto como DataFrame.
        """

        supplier = self.detectar(url)

        if not supplier:
            diagnostico = self.diagnostico()
            disponiveis = ", ".join(diagnostico.get("ordem_execucao", [])) or "nenhum"
            raise Exception(
                f"Nenhum fornecedor compatível para URL: {url}. "
                f"Fornecedores carregados: {disponiveis}."
            )

        produtos = supplier.fetch(url, **kwargs)

        try:
            produtos = supplier.validar_produtos(produtos)
            return supplier.to_dataframe(produtos)
        except Exception as exc:
            nome = str(getattr(supplier, "nome", supplier.__class__.__name__))
            REGISTRY_IMPORT_ERRORS[f"dataframe:{nome}"] = f"{exc.__class__.__name__}: {exc}"
            raise


_registry_instance: Optional[SupplierRegistry] = None


def get_registry() -> SupplierRegistry:
    global _registry_instance

    if _registry_instance is None:
        _registry_instance = SupplierRegistry()

    return _registry_instance


def reset_registry() -> SupplierRegistry:
    """
    Reinicia o singleton do registry.

    Útil em testes, debug ou recarregamento controlado.
    """
    global _registry_instance
    _registry_instance = SupplierRegistry()
    return _registry_instance


def get_registry_diagnostics() -> Dict[str, Any]:
    """
    Diagnóstico público para UI/log/debug.

    Exemplo de uso:
    - mostrar fornecedores carregados;
    - detectar Oba Oba Mix indisponível;
    - verificar se o genérico está ativo.
    """
    return get_registry().diagnostico()


def fetch_produtos(url: str, **kwargs):
    """
    Função principal usada pelo sistema inteiro.
    """

    registry = get_registry()
    return registry.fetch(url, **kwargs)


def fetch_produtos_df(url: str, **kwargs):
    """
    Retorna DataFrame direto.
    """

    registry = get_registry()
    return registry.fetch_dataframe(url, **kwargs)
