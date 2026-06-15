from __future__ import annotations

import base64
import gzip
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_token_store import _firestore_client, get_user_session_id, token_store_mode
from bling_app_zero.core.operation_contract import OP_ATUALIZACAO_PRECO, OP_CADASTRO, OP_ESTOQUE, normalize_operation

RESPONSIBLE_FILE = 'bling_app_zero/core/background_jobs.py'
DEFAULT_SQLITE_PATH = Path('bling_background_jobs') / 'jobs.sqlite3'
DEFAULT_FIRESTORE_COLLECTION = 'bling_background_jobs'
JOB_STATUS_QUEUED = 'queued'
JOB_STATUS_RUNNING = 'running'
JOB_STATUS_DONE = 'done'
JOB_STATUS_ERROR = 'error'
JOB_STATUS_PAUSED = 'paused'
SUPPORTED_JOB_OPERATIONS = {OP_CADASTRO, OP_ESTOQUE, OP_ATUALIZACAO_PRECO}


@dataclass(frozen=True)
class BackgroundJobSnapshot:
    job_id: str
    status: str
    operation: str
    total_rows: int
    attempted: int
    sent: int
    failed: int
    skipped: int
    created_at: str
    updated_at: str
    last_error: str = ''
    title: str = ''

    def to_dict(self) -> dict[str, Any]:
        return {
            'job_id': self.job_id,
            'status': self.status,
            'operation': self.operation,
            'total_rows': self.total_rows,
            'attempted': self.attempted,
            'sent': self.sent,
            'failed': self.failed,
            'skipped': self.skipped,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'last_error': self.last_error,
            'title': self.title,
        }


def _now() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _job_store_mode() -> str:
    # Firestore é o único modo realmente persistente para continuar fora da aba no Streamlit Cloud.
    # SQLite fica como fallback local/dev, mas não é recomendado para produção Cloud.
    try:
        return token_store_mode()
    except Exception:
        return 'sqlite'


def _collection_name() -> str:
    return DEFAULT_FIRESTORE_COLLECTION


def _sqlite_path() -> Path:
    return DEFAULT_SQLITE_PATH


def _ensure_sqlite() -> Path:
    path = _sqlite_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS bling_background_jobs (
                job_id TEXT PRIMARY KEY,
                user_session_id TEXT NOT NULL,
                status TEXT NOT NULL,
                operation TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            '''
        )
        conn.commit()
    return path


def _encode_dataframe(df: pd.DataFrame) -> dict[str, Any]:
    if not isinstance(df, pd.DataFrame):
        df = pd.DataFrame()
    csv_text = df.fillna('').to_csv(index=False, sep=';', encoding='utf-8-sig')
    compressed = gzip.compress(csv_text.encode('utf-8-sig'))
    return {
        'format': 'csv_gzip_base64',
        'rows': int(len(df)),
        'columns': [str(column) for column in df.columns],
        'data': base64.b64encode(compressed).decode('ascii'),
    }


def decode_dataframe(encoded: dict[str, Any]) -> pd.DataFrame:
    if not isinstance(encoded, dict):
        return pd.DataFrame()
    if encoded.get('format') != 'csv_gzip_base64':
        return pd.DataFrame()
    raw = base64.b64decode(str(encoded.get('data') or '').encode('ascii'))
    csv_text = gzip.decompress(raw).decode('utf-8-sig')
    return pd.read_csv(StringIO(csv_text), sep=';', dtype=str).fillna('')


def _safe_payload_for_snapshot(payload: dict[str, Any]) -> BackgroundJobSnapshot:
    return BackgroundJobSnapshot(
        job_id=str(payload.get('job_id') or ''),
        status=str(payload.get('status') or ''),
        operation=normalize_operation(payload.get('operation')),
        total_rows=int(payload.get('total_rows') or 0),
        attempted=int(payload.get('attempted') or 0),
        sent=int(payload.get('sent') or 0),
        failed=int(payload.get('failed') or 0),
        skipped=int(payload.get('skipped') or 0),
        created_at=str(payload.get('created_at') or ''),
        updated_at=str(payload.get('updated_at') or ''),
        last_error=str(payload.get('last_error') or ''),
        title=str(payload.get('title') or ''),
    )


def create_background_bling_job(
    df: pd.DataFrame,
    *,
    operation: str,
    title: str = '',
    source: str = 'api_bling',
    metadata: dict[str, Any] | None = None,
    batch_size: int = 0,
) -> BackgroundJobSnapshot:
    normalized = normalize_operation(operation)
    if normalized not in SUPPORTED_JOB_OPERATIONS:
        raise ValueError(f'Operação não suportada para segundo plano: {normalized}')
    if not isinstance(df, pd.DataFrame) or df.empty:
        raise ValueError('Não é possível criar tarefa em segundo plano sem linhas aptas.')

    now = _now()
    job_id = uuid4().hex
    user_session_id = get_user_session_id()
    payload: dict[str, Any] = {
        'job_id': job_id,
        'user_session_id': user_session_id,
        'status': JOB_STATUS_QUEUED,
        'operation': normalized,
        'source': source,
        'title': title or _default_title(normalized),
        'created_at': now,
        'updated_at': now,
        'started_at': '',
        'finished_at': '',
        'total_rows': int(len(df)),
        'attempted': 0,
        'sent': 0,
        'failed': 0,
        'skipped': 0,
        'offset': 0,
        'batch_size': int(batch_size or 0),
        'last_error': '',
        'errors': [],
        'not_found_indices': [],
        'dataframe': _encode_dataframe(df),
        'metadata': metadata or {},
        'responsible_file': RESPONSIBLE_FILE,
    }
    _save_job_payload(payload)
    add_audit_event(
        'background_bling_job_created',
        area='BACKGROUND_JOBS',
        status='OK',
        details={'job_id': job_id, 'operation': normalized, 'rows': len(df), 'store_mode': _job_store_mode(), 'responsible_file': RESPONSIBLE_FILE},
    )
    return _safe_payload_for_snapshot(payload)


def _default_title(operation: str) -> str:
    operation = normalize_operation(operation)
    if operation == OP_ESTOQUE:
        return 'Atualização de estoque em segundo plano'
    if operation == OP_ATUALIZACAO_PRECO:
        return 'Atualização de preços em segundo plano'
    return 'Cadastro de produtos em segundo plano'


def _save_job_payload(payload: dict[str, Any]) -> None:
    if _job_store_mode() == 'firestore':
        _save_firestore(payload)
        return
    _save_sqlite(payload)


def _save_firestore(payload: dict[str, Any]) -> None:
    client = _firestore_client()
    client.collection(_collection_name()).document(str(payload['job_id'])).set(payload)


def _save_sqlite(payload: dict[str, Any]) -> None:
    path = _ensure_sqlite()
    with sqlite3.connect(path) as conn:
        conn.execute(
            '''
            INSERT OR REPLACE INTO bling_background_jobs
            (job_id, user_session_id, status, operation, payload_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                str(payload['job_id']),
                str(payload.get('user_session_id') or ''),
                str(payload.get('status') or ''),
                normalize_operation(payload.get('operation')),
                json.dumps(payload, ensure_ascii=False),
                str(payload.get('created_at') or _now()),
                str(payload.get('updated_at') or _now()),
            ),
        )
        conn.commit()


def load_job_payload(job_id: str) -> dict[str, Any] | None:
    job_id = str(job_id or '').strip()
    if not job_id:
        return None
    if _job_store_mode() == 'firestore':
        snapshot = _firestore_client().collection(_collection_name()).document(job_id).get()
        return snapshot.to_dict() if snapshot.exists else None
    path = _ensure_sqlite()
    with sqlite3.connect(path) as conn:
        row = conn.execute('SELECT payload_json FROM bling_background_jobs WHERE job_id = ?', (job_id,)).fetchone()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except Exception:
        return None


def update_job_payload(job_id: str, changes: dict[str, Any]) -> dict[str, Any] | None:
    payload = load_job_payload(job_id)
    if not isinstance(payload, dict):
        return None
    payload.update(changes or {})
    payload['updated_at'] = _now()
    _save_job_payload(payload)
    return payload


def list_my_background_jobs(limit: int = 20) -> list[BackgroundJobSnapshot]:
    user_session_id = get_user_session_id()
    limit = max(1, min(int(limit or 20), 50))
    rows: list[dict[str, Any]] = []
    if _job_store_mode() == 'firestore':
        client = _firestore_client()
        query = client.collection(_collection_name()).where('user_session_id', '==', user_session_id).order_by('created_at', direction='DESCENDING').limit(limit)
        rows = [snapshot.to_dict() or {} for snapshot in query.stream()]
    else:
        path = _ensure_sqlite()
        with sqlite3.connect(path) as conn:
            result = conn.execute(
                'SELECT payload_json FROM bling_background_jobs WHERE user_session_id = ? ORDER BY created_at DESC LIMIT ?',
                (user_session_id, limit),
            ).fetchall()
        for row in result:
            try:
                rows.append(json.loads(row[0]))
            except Exception:
                pass
    return [_safe_payload_for_snapshot(row) for row in rows]


def list_queued_jobs(limit: int = 10) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit or 10), 50))
    if _job_store_mode() == 'firestore':
        client = _firestore_client()
        query = client.collection(_collection_name()).where('status', '==', JOB_STATUS_QUEUED).order_by('created_at').limit(limit)
        return [snapshot.to_dict() or {} for snapshot in query.stream()]
    path = _ensure_sqlite()
    rows: list[dict[str, Any]] = []
    with sqlite3.connect(path) as conn:
        result = conn.execute(
            'SELECT payload_json FROM bling_background_jobs WHERE status = ? ORDER BY created_at ASC LIMIT ?',
            (JOB_STATUS_QUEUED, limit),
        ).fetchall()
    for row in result:
        try:
            rows.append(json.loads(row[0]))
        except Exception:
            pass
    return rows


def background_jobs_available() -> bool:
    try:
        mode = _job_store_mode()
        if mode == 'firestore':
            _firestore_client()
            return True
        _ensure_sqlite()
        return True
    except Exception as exc:
        add_audit_event('background_jobs_unavailable', area='BACKGROUND_JOBS', status='AVISO', details={'error': str(exc)[:240], 'responsible_file': RESPONSIBLE_FILE})
        return False


def background_jobs_mode() -> str:
    return _job_store_mode()


__all__ = [
    'BackgroundJobSnapshot',
    'JOB_STATUS_DONE',
    'JOB_STATUS_ERROR',
    'JOB_STATUS_PAUSED',
    'JOB_STATUS_QUEUED',
    'JOB_STATUS_RUNNING',
    'background_jobs_available',
    'background_jobs_mode',
    'create_background_bling_job',
    'decode_dataframe',
    'list_my_background_jobs',
    'list_queued_jobs',
    'load_job_payload',
    'update_job_payload',
]
