from __future__ import annotations

"""Checkpoint simples para o Flash Amplo.

Objetivo:
- Evitar perder tudo se o Streamlit reiniciar a execução quando o usuário sai da
  aba, o celular bloqueia, a conexão cai ou a sessão dá rerun.
- Salvar linhas já capturadas em disco temporário.
- Permitir retomar a mesma busca reaproveitando produtos já lidos.

Observação:
- Em Streamlit Cloud, o disco temporário sobrevive a reruns/reconexões normais
  da mesma instância, mas pode ser limpo se a máquina for recriada.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Iterable

import pandas as pd


CHECKPOINT_DIR = Path(os.environ.get("BLING_FLASH_CHECKPOINT_DIR", "/tmp/bling_flash_checkpoints"))


def fingerprint_urls(seed_urls: Iterable[str], *, max_products: int) -> str:
    normalized = [str(url or "").strip() for url in seed_urls if str(url or "").strip()]
    payload = json.dumps({"urls": normalized, "max_products": int(max_products or 0)}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def checkpoint_path(fingerprint: str) -> Path:
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    return CHECKPOINT_DIR / f"flash_{fingerprint}.jsonl"


def _row_url(row: dict[str, object]) -> str:
    return str(row.get("Link Externo") or row.get("URL do Produto") or "").strip()


def load_checkpoint_rows(fingerprint: str) -> list[dict[str, str]]:
    path = checkpoint_path(fingerprint)
    if not path.exists():
        return []

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if not isinstance(row, dict):
                    continue
                url = _row_url(row)
                if url and url in seen:
                    continue
                if url:
                    seen.add(url)
                rows.append({str(k): "" if v is None else str(v) for k, v in row.items()})
    except Exception:
        return []
    return rows


def append_checkpoint_row(fingerprint: str, row: dict[str, object]) -> None:
    path = checkpoint_path(fingerprint)
    safe_row = {str(k): "" if v is None else str(v) for k, v in row.items()}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(safe_row, ensure_ascii=False) + "\n")


def checkpoint_dataframe(fingerprint: str) -> pd.DataFrame:
    return pd.DataFrame(load_checkpoint_rows(fingerprint))


def clear_checkpoint(fingerprint: str) -> None:
    path = checkpoint_path(fingerprint)
    try:
        if path.exists():
            path.unlink()
    except Exception:
        pass
