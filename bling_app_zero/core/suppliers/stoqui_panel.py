"""
STOQUI PANEL (FORNECEDOR AUTENTICADO)

Objetivo:
- Acessar painel Stoqui
- Ler produtos e estoque real
- Base para automação futura (robô)

⚠️ NÃO é scraper público
⚠️ Depende de autenticação
"""

from typing import List, Dict
import requests

from bling_app_zero.core.suppliers.base import SupplierBase


class StoquiPanelSupplier(SupplierBase):

    nome = "Stoqui Painel"
    dominio = ["app.stoqui.com.br"]

    def __init__(self):
        self.session = requests.Session()

    # -------------------------------
    # DETECÇÃO
    # -------------------------------
    def can_handle(self, url: str) -> bool:
        return any(d in url for d in self.dominio)

    # -------------------------------
    # FETCH PRINCIPAL
    # -------------------------------
    def fetch(self, url: str, **kwargs) -> List[Dict]:

        # ⚠️ requer login prévio
        if not self._is_logged():
            raise Exception("Necessário autenticar no painel Stoqui")

        produtos = self._buscar_produtos()

        return produtos

    # -------------------------------
    # LOGIN (BASE)
    # -------------------------------
    def login(self, token: str = None, cookies: dict = None):
        """
        Formas possíveis de autenticação:
        - via cookie
        - via token (futuro)
        """

        if cookies:
            self.session.cookies.update(cookies)

        # futuro: login real via API / formulário

    # -------------------------------
    # VERIFICA LOGIN
    # -------------------------------
    def _is_logged(self) -> bool:
        """
        Verifica se sessão está autenticada
        """
        try:
            r = self.session.get("https://app.stoqui.com.br/")
            return r.status_code == 200 and "login" not in r.text.lower()
        except:
            return False

    # -------------------------------
    # BUSCAR PRODUTOS
    # -------------------------------
    def _buscar_produtos(self) -> List[Dict]:

        produtos = []

        # ⚠️ endpoint real será ajustado conforme descoberta
        url_api = "https://app.stoqui.com.br/api/products"

        try:
            r = self.session.get(url_api)

            if r.status_code != 200:
                return produtos

            data = r.json()

            for item in data.get("products", []):

                produtos.append({
                    "url_produto": "",
                    "nome": item.get("name", ""),
                    "sku": item.get("sku", ""),
                    "estoque": item.get("stock", 0),
                    "preco": item.get("price", 0),
                })

        except Exception:
            pass

        return produtos
