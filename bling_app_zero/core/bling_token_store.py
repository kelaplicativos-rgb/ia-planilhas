from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional


class BlingTokenStore:
    """
    Store simples em JSON local no servidor.
    Pode ser trocado depois por banco sem alterar a camada de auth/api.
    """

    def __init__(self, file_path: str) -> None:
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def _read_all(self) -> Dict[str, Any]:
        if not self.file_path.exists():
            return {}
        try:
            raw = self.file_path.read_text(encoding="utf-8").strip()
            if not raw:
                return {}
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _write_all(self, data: Dict[str, Any]) -> None:
        payload = json.dumps(data, ensure_ascii=False, indent=2)
        self.file_path.write_text(payload, encoding="utf-8")

    def get(self, user_key: str = "default") -> Optional[Dict[str, Any]]:
        with self._lock:
            data = self._read_all()
            item = data.get(user_key)
            return item if isinstance(item, dict) else None

    def save_token_payload(
        self,
        token_payload: Dict[str, Any],
        user_key: str = "default",
        company_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)

        expires_in = int(token_payload.get("expires_in", 0) or 0)
        expires_at = now + timedelta(seconds=max(expires_in, 0))

        current = self.get(user_key) or {}

        stored = {
            "access_token": token_payload.get("access_token", ""),
            "refresh_token": token_payload.get("refresh_token", current.get("refresh_token", "")),
            "token_type": token_payload.get("token_type", "Bearer"),
            "scope": token_payload.get("scope", ""),
            "expires_in": expires_in,
            "expires_at": expires_at.isoformat(),
            "last_auth_at": now.isoformat(),
            "company_name": company_name or current.get("company_name"),
        }

        with self._lock:
            data = self._read_all()
            data[user_key] = stored
            self._write_all(data)

        return stored

    def update_company_name(self, company_name: str, user_key: str = "default") -> None:
        with self._lock:
            data = self._read_all()
            item = data.get(user_key, {})
            if not isinstance(item, dict):
                item = {}
            item["company_name"] = company_name
            data[user_key] = item
            self._write_all(data)

    def delete(self, user_key: str = "default") -> bool:
        with self._lock:
            data = self._read_all()
            if user_key in data:
                del data[user_key]
                self._write_all(data)
                return True
            return False

    @staticmethod
    def is_expired(token_data: Optional[Dict[str, Any]], leeway_seconds: int = 120) -> bool:
        if not token_data:
            return True

        expires_at = token_data.get("expires_at")
        if not expires_at:
            return True

        try:
            expires_dt = datetime.fromisoformat(expires_at)
            now = datetime.now(timezone.utc)
            return now >= (expires_dt - timedelta(seconds=leeway_seconds))
        except Exception:
            return True
