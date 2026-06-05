from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

TOKEN_DIR = Path(os.getenv('BLING_BACKEND_TOKEN_DIR', '.bling_tokens'))
TOKEN_FILE = TOKEN_DIR / 'bling_token.json'


def save_token(payload: dict[str, Any]) -> None:
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    data = dict(payload)
    expires_in = int(data.get('expires_in') or 0)
    if expires_in:
        data['expires_at'] = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()
    data['saved_at'] = datetime.now(timezone.utc).isoformat()
    TOKEN_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def load_token() -> dict[str, Any]:
    if not TOKEN_FILE.exists():
        return {}
    try:
        return json.loads(TOKEN_FILE.read_text(encoding='utf-8'))
    except Exception:
        return {}


def clear_token() -> None:
    try:
        TOKEN_FILE.unlink(missing_ok=True)
    except Exception:
        pass
