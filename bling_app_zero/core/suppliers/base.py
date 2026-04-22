"""
BASE DE FORNECEDORES

Contrato padrão que TODOS os módulos de fornecedor devem seguir.
Isso garante que Mega Center, Atacadum, ObaObaMix e Genérico
retornem sempre o mesmo formato e não quebrem o restante do sistema.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
import pandas as pd


class SupplierBase(ABC):
    """
    Classe base para TODOS os fornecedores.

    Cada fornecedor deve herdar essa classe e implementar:
    - can_handle(url)
    - fetch(url, **kwargs)
    """

    nome: str = "Fornecedor Base"
    dominio: List[str] = []

    def __init__(self):
        pass

    # -------------------------------
    # DETECÇÃO DO FORNECEDOR
    # -------------------------------
    def can_handle(self, url: str) -> bool:
        """
        Verifica se este fornecedor consegue tratar a URL.
        """
        if not url:
            return False

        url = url.lower()

        for dominio in self.dominio:
            if dominio in url:
                return True

        return False

    # -------------------------------
    # EXECUÇÃO PRINCIPAL
    # -------------------------------
    @abstractmethod
    def fetch(self, url: str, **kwargs) -> List[Dict[str, Any]]:
        """
        Deve retornar uma lista de produtos no formato padrão.
        """
        pass

    # -------------------------------
    # NORMALIZAÇÃO PADRÃO
    # -------------------------------
    def normalizar_produto(self, produto: Dict[str, Any]) -> Dict[str, Any]:
        """
        Garante que todos os produtos tenham o mesmo formato.
        """

        return {
            "fornecedor": self.nome,
            "url_produto": produto.get("url_produto", ""),
            "nome": produto.get("nome", ""),
            "sku": produto.get("sku", ""),
            "marca": produto.get("marca", ""),
            "categoria": produto.get("categoria", ""),
            "preco": produto.get("preco", 0),
            "estoque": produto.get("estoque", 0),
            "gtin": produto.get("gtin", ""),
            "descricao": produto.get("descricao", ""),
            "imagens": self._normalizar_imagens(produto.get("imagens", "")),
        }

    # -------------------------------
    # NORMALIZA IMAGENS (PADRÃO BLING)
    # -------------------------------
    def _normalizar_imagens(self, imagens: Any) -> str:
        """
        Garante separador "|" nas imagens
        """

        if isinstance(imagens, list):
            imagens = [str(i).strip() for i in imagens if i]
            return "|".join(imagens)

        if isinstance(imagens, str):
            imagens = imagens.replace(",", "|").replace(";", "|")
            partes = [p.strip() for p in imagens.split("|") if p.strip()]
            return "|".join(partes)

        return ""

    # -------------------------------
    # CONVERSÃO PARA DATAFRAME
    # -------------------------------
    def to_dataframe(self, produtos: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Converte lista de produtos para DataFrame padrão
        """

        normalizados = [self.normalizar_produto(p) for p in produtos]

        if not normalizados:
            return pd.DataFrame()

        return pd.DataFrame(normalizados)

    # -------------------------------
    # VALIDAÇÃO FINAL
    # -------------------------------
    def validar_produtos(self, produtos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove produtos inválidos
        """

        validos = []

        for p in produtos:
            if not p:
                continue

            nome = str(p.get("nome", "")).strip()
            preco = p.get("preco", 0)

            # regra mínima
            if not nome:
                continue

            # evita lixo
            if nome.lower() in ["produto", "item", "sem nome"]:
                continue

            validos.append(p)

        return validos
