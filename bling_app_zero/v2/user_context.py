from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from hashlib import sha256
from uuid import uuid4

import streamlit as st

USER_CONTEXT_KEY = 'v2_user_context'


@dataclass(frozen=True)
class UserContext:
    session_id: str
    workspace_id: str
    user_label: str
    created_at: str

    @property
    def namespace(self) -> str:
        raw = f'{self.workspace_id}:{self.session_id}:{self.user_label}'
        return sha256(raw.encode('utf-8')).hexdigest()[:16]

    def key(self, name: str) -> str:
        safe_name = str(name or '').strip().replace(' ', '_')
        return f'v2:{self.namespace}:{safe_name}'

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _new_context() -> UserContext:
    now = datetime.now(timezone.utc).isoformat()
    session_id = uuid4().hex
    return UserContext(
        session_id=session_id,
        workspace_id=f'workspace_{session_id[:10]}',
        user_label='anonymous',
        created_at=now,
    )


def get_user_context() -> UserContext:
    current = st.session_state.get(USER_CONTEXT_KEY)
    if isinstance(current, dict) and current.get('session_id'):
        return UserContext(
            session_id=str(current.get('session_id', '')),
            workspace_id=str(current.get('workspace_id', '')),
            user_label=str(current.get('user_label', 'anonymous')),
            created_at=str(current.get('created_at', '')),
        )
    context = _new_context()
    st.session_state[USER_CONTEXT_KEY] = context.to_dict()
    return context


def scoped_key(name: str) -> str:
    return get_user_context().key(name)


def set_workspace(workspace_id: str, user_label: str = '') -> UserContext:
    current = get_user_context()
    updated = UserContext(
        session_id=current.session_id,
        workspace_id=str(workspace_id or current.workspace_id).strip() or current.workspace_id,
        user_label=str(user_label or current.user_label or 'anonymous').strip() or 'anonymous',
        created_at=current.created_at,
    )
    st.session_state[USER_CONTEXT_KEY] = updated.to_dict()
    return updated


__all__ = ['USER_CONTEXT_KEY', 'UserContext', 'get_user_context', 'scoped_key', 'set_workspace']
