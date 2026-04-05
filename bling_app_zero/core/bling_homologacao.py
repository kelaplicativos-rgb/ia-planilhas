from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import httpx

from bling_app_zero.core.bling_api import BlingAPIClient


class BlingHomologacaoService:
    def __init__(self, user_key: str = "default") -> None:
        self.client = BlingAPIClient(user_key=user_key)
        self.base_url = self.client.base_url.rstrip("/")

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Optional[Dict[str, Any]] = None,
        previous_hash: Optional[str] = None,
        timeout: float = 30.0,
    ) -> Tuple[bool, Any, Optional[str]]:
        ok, token_or_msg = self.client.auth.get_valid_access_token()
        if not ok:
            return False, token_or_msg, None

        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = self.client._headers(token_or_msg)
        if previous_hash:
            headers["x-bling-homologacao"] = previous_hash

        try:
            with httpx.Client(timeout=timeout) as session:
                resp = session.request(
                    method.upper(),
                    url,
                    headers=headers,
                    json=json_body,
                )

                if resp.status_code == 401:
                    refresh_ok, refresh_msg = self.client.auth.refresh_access_token()
                    if not refresh_ok:
                        return False, refresh_msg, None

                    ok2, token_or_msg2 = self.client.auth.get_valid_access_token()
                    if not ok2:
                        return False, token_or_msg2, None

                    headers = self.client._headers(token_or_msg2)
                    if previous_hash:
                        headers["x-bling-homologacao"] = previous_hash

                    resp = session.request(
                        method.upper(),
                        url,
                        headers=headers,
                        json=json_body,
                    )

            content_type = resp.headers.get("content-type", "")
            payload = (
                resp.json() if "application/json" in content_type else {"raw": resp.text}
            )
            next_hash = resp.headers.get("x-bling-homologacao")

            if resp.status_code >= 400:
                return (
                    False,
                    {
                        "status_code": resp.status_code,
                        "error": payload,
                        "url": url,
                        "body": json_body,
                    },
                    next_hash,
                )

            return True, payload, next_hash
        except Exception as exc:
            return False, f"Erro de comunicação com a homologação do Bling: {exc}", None

    @staticmethod
    def _extract_data(payload: Any) -> Dict[str, Any]:
        if isinstance(payload, dict):
            data = payload.get("data")
            if isinstance(data, dict):
                return data
            return payload
        return {}

    @staticmethod
    def _coerce_id(payload: Dict[str, Any]) -> Optional[Any]:
        for key in ("id", "produto", "produto_id"):
            value = payload.get(key)
            if value not in (None, ""):
                return value
        return None

    def run(self) -> Tuple[bool, List[Dict[str, Any]]]:
        logs: List[Dict[str, Any]] = []
        next_hash: Optional[str] = None

        # 1) GET dados para criação
        ok, payload_get, next_hash = self._request(
            "GET",
            "/homologacao/produtos",
            previous_hash=next_hash,
        )
        logs.append(
            {
                "etapa": 1,
                "acao": "GET /homologacao/produtos",
                "ok": ok,
                "retorno": payload_get,
                "hash_retorno": next_hash,
            }
        )
        if not ok:
            return False, logs

        produto_base = self._extract_data(payload_get)
        if not produto_base:
            logs.append(
                {
                    "etapa": 1,
                    "acao": "parse dados homologação",
                    "ok": False,
                    "retorno": "A resposta de homologação não trouxe payload utilizável em data.",
                }
            )
            return False, logs

        # 2) POST cria produto simulado na homologação
        ok, payload_post, next_hash = self._request(
            "POST",
            "/homologacao/produtos",
            json_body=produto_base,
            previous_hash=next_hash,
        )
        logs.append(
            {
                "etapa": 2,
                "acao": "POST /homologacao/produtos",
                "ok": ok,
                "retorno": payload_post,
                "hash_retorno": next_hash,
            }
        )
        if not ok:
            return False, logs

        produto_criado = self._extract_data(payload_post)
        produto_id = self._coerce_id(produto_criado)
        if produto_id in (None, ""):
            logs.append(
                {
                    "etapa": 2,
                    "acao": "captura id homologação",
                    "ok": False,
                    "retorno": "Não foi possível identificar o id retornado pela homologação.",
                }
            )
            return False, logs

        # 3) PUT altera descrição para Copo, conforme fluxo oficial
        body_put = dict(produto_base)
        body_put["descricao"] = "Copo"
        body_put["nome"] = body_put.get("nome") or body_put.get("descricao") or "Copo"

        ok, payload_put, next_hash = self._request(
            "PUT",
            f"/homologacao/produtos/{produto_id}",
            json_body=body_put,
            previous_hash=next_hash,
        )
        logs.append(
            {
                "etapa": 3,
                "acao": f"PUT /homologacao/produtos/{produto_id}",
                "ok": ok,
                "retorno": payload_put,
                "hash_retorno": next_hash,
            }
        )
        if not ok:
            return False, logs

        # 4) DELETE remove o produto da homologação, prática comum no fluxo de validação
        ok, payload_delete, next_hash = self._request(
            "DELETE",
            f"/homologacao/produtos/{produto_id}",
            previous_hash=next_hash,
        )
        logs.append(
            {
                "etapa": 4,
                "acao": f"DELETE /homologacao/produtos/{produto_id}",
                "ok": ok,
                "retorno": payload_delete,
                "hash_retorno": next_hash,
            }
        )

        return ok, logs
