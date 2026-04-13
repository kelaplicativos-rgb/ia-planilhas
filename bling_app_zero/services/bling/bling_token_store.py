from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional


class BlingTokenStore:
    def __init__(self, file_path: str) -> None:
        self.file_path = Path(str(file_path or "").strip() or "bling_app_zero/output/bling_tokens.json")
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    # =========================
    # HELPERS
    # =========================
    @staticmethod
    def _safe_str(value: Any) -> str:
        try:
            return str(value or "").strip()
        except Exception:
            return ""

    def _normalize_user_key(self, user_key: str) -> str:
        chave = self._safe_str(user_key)
        return chave or "default"

    @staticmethod
    def _safe_json_load(raw: str) -> Dict[str, Any]:
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _parse_iso_datetime(self, value: Any) -> Optional[datetime]:
        try:
            texto = self._safe_str(value)
            if not texto:
                return None

            if texto.endswith("Z"):
                texto = texto.replace("Z", "+00:00")

            dt = datetime.fromisoformat(texto)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            return dt.astimezone(timezone.utc)
        except Exception:
            return None

    def _read_all(self) -> Dict[str, Any]:
        if not self.file_path.exists():
            return {}

        try:
            raw = self.file_path.read_text(encoding="utf-8").strip()
            if not raw:
                return {}
            return self._safe_json_load(raw)
        except Exception:
            return {}

    def _write_all(self, data: Dict[str, Any]) -> None:
        temp_path = self.file_path.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp_path.replace(self.file_path)

    # =========================
    # LIMPEZA AUTOMÁTICA
    # =========================
    def _clean_expired_tokens(self, data: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        novo: Dict[str, Any] = {}

        for chave, valor in data.items():
            try:
                if not isinstance(valor, dict):
                    continue

                expires_at = valor.get("expires_at")
                if not expires_at:
                    continue

                dt = self._parse_iso_datetime(expires_at)
                if not dt:
                    continue

                # mantém um histórico curto para evitar lixo acumulado,
                # mas não remove imediatamente um token recém-expirado.
                if dt > now - timedelta(days=30):
                    novo[chave] = valor
            except Exception:
                continue

        return novo

    # =========================
    # GET
    # =========================
    def get(self, user_key: str = "default") -> Optional[Dict[str, Any]]:
        chave = self._normalize_user_key(user_key)

        with self._lock:
            data = self._read_all()
            value = data.get(chave)

        return value.copy() if isinstance(value, dict) else None

    # =========================
    # SAVE
    # =========================
    def save(
        self,
        user_key: str,
        token_payload: Dict[str, Any],
        company_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.save_token_payload(
            token_payload=token_payload,
            user_key=user_key,
            company_name=company_name,
        )

    def save_token_payload(
        self,
        token_payload: Dict[str, Any],
        user_key: str = "default",
        company_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        chave = self._normalize_user_key(user_key)
        payload = token_payload if isinstance(token_payload, dict) else {}

        access_token = self._safe_str(payload.get("access_token"))
        if not access_token:
            return {}

        now = datetime.now(timezone.utc)

        try:
            expires_in = int(payload.get("expires_in", 0) or 0)
            if expires_in <= 0:
                expires_in = 3600
        except Exception:
            expires_in = 3600

        expires_at = now + timedelta(seconds=expires_in)
        atual = self.get(chave) or {}

        item = {
            "access_token": access_token,
            "refresh_token": self._safe_str(
                payload.get("refresh_token", atual.get("refresh_token", ""))
            ),
            "token_type": self._safe_str(payload.get("token_type", "Bearer")) or "Bearer",
            "scope": self._safe_str(payload.get("scope", "")),
            "expires_in": expires_in,
            "expires_at": expires_at.isoformat(),
            "last_auth_at": now.isoformat(),
            "company_name": (
                self._safe_str(company_name)
                if self._safe_str(company_name)
                else atual.get("company_name")
            ),
        }

        with self._lock:
            data = self._read_all()
            data = self._clean_expired_tokens(data)
            data[chave] = item
            self._write_all(data)

        return item.copy()

    # =========================
    # UPDATE COMPANY
    # =========================
    def update_company_name(self, company_name: str, user_key: str = "default") -> None:
        chave = self._normalize_user_key(user_key)
        nome = self._safe_str(company_name)

        if not nome:
            return

        with self._lock:
            data = self._read_all()
            atual = data.get(chave, {})
            if not isinstance(atual, dict):
                atual = {}

            atual["company_name"] = nome
            data[chave] = atual
            self._write_all(data)

    # =========================
    # DELETE
    # =========================
    def delete(self, user_key: str = "default") -> bool:
        chave = self._normalize_user_key(user_key)

        with self._lock:
            data = self._read_all()

            if chave in data:
                del data[chave]
                self._write_all(data)
                return True

        return False

    # =========================
    # EXPIRAÇÃO
    # =========================
    def is_expired(
        self,
        token_data: Optional[Dict[str, Any]],
        leeway_seconds: int = 120,
    ) -> bool:
        if not token_data or not isinstance(token_data, dict):
            return True

        expires_at = token_data.get("expires_at")
        if not expires_at:
            return True

        dt = self._parse_iso_datetime(expires_at)
        if not dt:
            return True

        now = datetime.now(timezone.utc)
        return now >= (dt - timedelta(seconds=max(0, int(leeway_seconds))))
