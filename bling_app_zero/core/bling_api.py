from __future__ import annotations

from typing import Any, Dict


class BlingApiClient:
    """
    Cliente neutralizado.
    A integração com a API do Bling foi removida do projeto.
    """

    def __init__(self, *args, **kwargs) -> None:
        self.disabled = True

    def ping(self) -> Dict[str, Any]:
        return {
            "ok": False,
            "disabled": True,
            "message": "API do Bling removida do projeto.",
        }

    def request(self, *args, **kwargs) -> Dict[str, Any]:
        return {
            "ok": False,
            "disabled": True,
            "message": "API do Bling removida do projeto.",
        }
