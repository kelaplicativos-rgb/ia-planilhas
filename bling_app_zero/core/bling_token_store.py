from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional


class BlingTokenStore:
    def __init__(self, file_path: str) -> None:
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    # =========================
    # HELPERS
    # =========================
    def _normalize_user_key(self, user_key: str) -> str:
        chave = str(user_key or "").strip()
        return chave or "default"

    def _safe_json_load(self, raw: str) -> Dict[str, Any]:
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

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

        novo = {}
        for k, v in data.items():
            try:
                expires_at = v.get("expires_at")
                if not expires_at:
                    continue

                dt = datetime.fromisoformat(str(expires_at))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)

                # mantém tokens ainda válidos ou com refresh
                if dt > now - timedelta(days=30):
                    novo[k] = v
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
    # SAVE TOKEN
    # =========================
    def save_token_payload(
        self,
        token_payload: Dict[str, Any],
        user_key: str = "default",
        company_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        chave = self._normalize_user_key(user_key)
        payload = token_payload if isinstance(token_payload, dict) else {}

        access_token = str(payload.get("access_token", "") or "").strip()
        if not access_token:
            return {}

        now = datetime.now(timezone.utc)

        # 🔥 BLINDAGEM expires_in
        try:
            expires_in = int(payload.get("expires_in", 0) or 0)
            if expires_in <= 0:
                expires_in = 3600  # fallback 1h
        except Exception:
            expires_in = 3600

        expires_at = now + timedelta(seconds=expires_in)

        atual = self.get(chave) or {}

        item = {
            "access_token": access_token,
            "refresh_token": str(
                payload.get("refresh_token", atual.get("refresh_token", "")) or ""
            ).strip(),
            "token_type": str(payload.get("token_type", "Bearer") or "Bearer").strip(),
            "scope": str(payload.get("scope", "") or "").strip(),
            "expires_in": expires_in,
            "expires_at": expires_at.isoformat(),
            "last_auth_at": now.isoformat(),
            "company_name": (
                str(company_name).strip()
                if company_name and str(company_name).strip()
                else atual.get("company_name")
            ),
        }

        with self._lock:
            data = self._read_all()

            # 🔥 LIMPEZA automática antes de salvar
            data = self._clean_expired_tokens(data)

            data[chave] = item
            self._write_all(data)

        return item.copy()

    # =========================
    # UPDATE COMPANY
    # =========================
    def update_company_name(self, company_name: str, user_key: str = "default") -> None:
        chave = self._normalize_user_key(user_key)
        nome = str(company_name or "").strip()

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
    @staticmethod
    def is_expired(
        token_data: Optional[Dict[str, Any]],
        leeway_seconds: int = 120,
    ) -> bool:
        if not token_data:
            return True

        expires_at = token_data.get("expires_at")
        if not expires_at:
            return True

        try:
            expires_dt = datetime.fromisoformat(str(expires_at))

            if expires_dt.tzinfo is None:
                expires_dt = expires_dt.replace(tzinfo=timezone.utc)

            now = datetime.now(timezone.utc)

            return now >= (
                expires_dt - timedelta(seconds=max(0, int(leeway_seconds)))
            )

        except Exception:
            return True
