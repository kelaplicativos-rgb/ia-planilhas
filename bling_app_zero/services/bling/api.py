from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import httpx

from bling_app_zero.core.bling_auth import BlingAuthManager


class BlingAPIClient:
    def __init__(self, user_key: str = "default") -> None:
        self.auth = BlingAuthManager(user_key=user_key)
        self.base_url = self.auth.settings.api_base_url.rstrip("/")

    def _headers(self, access_token: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "enable-jwt": "1",
        }

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0,
    ) -> Tuple[bool, Any]:
        ok, token_or_msg = self.auth.get_valid_access_token()
        if not ok:
            return False, token_or_msg

        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = self._headers(token_or_msg)

        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.request(
                    method.upper(),
                    url,
                    headers=headers,
                    params=params,
                    json=json,
                )

            if resp.status_code == 401:
                refresh_ok, refresh_msg = self.auth.refresh_access_token()
                if not refresh_ok:
                    return False, refresh_msg

                ok2, token_or_msg2 = self.auth.get_valid_access_token()
                if not ok2:
                    return False, token_or_msg2

                headers = self._headers(token_or_msg2)

                with httpx.Client(timeout=timeout) as client:
                    resp = client.request(
                        method.upper(),
                        url,
                        headers=headers,
                        params=params,
                        json=json,
                    )

            content_type = resp.headers.get("content-type", "")
            payload = resp.json() if "application/json" in content_type else resp.text

            if resp.status_code >= 400:
                return False, {
                    "status_code": resp.status_code,
                    "error": payload,
                    "url": url,
                }

            return True, payload

        except Exception as exc:
            return False, f"Erro de comunicação com o Bling: {exc}"
