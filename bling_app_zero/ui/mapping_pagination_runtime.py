from __future__ import annotations

import streamlit as st

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/mapping_pagination_runtime.py'
PAGE_SIZE = 10
INSTALL_KEY = 'mapping_pagination_runtime_installed_v1'


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value or default)
    except Exception:
        return default


def _page_key(mapping_key: str) -> str:
    return f'{mapping_key}_page_index'


def _meta_key(mapping_key: str) -> str:
    return f'{mapping_key}_page_meta'


def _pending_key(mapping_key: str) -> str:
    return f'{mapping_key}_pending_page_index'


def _scroll_key(mapping_key: str) -> str:
    return f'{mapping_key}_scroll_to_page_top'


def _clamp(index: object, total_pages: int) -> int:
    return max(0, min(max(1, int(total_pages)) - 1, _safe_int(index, 0)))


def _set_query_page(mapping_key: str, page_index: int) -> None:
    try:
        st.query_params['mapping_page'] = str(int(page_index) + 1)
        st.query_params[f'{mapping_key}_page'] = str(int(page_index) + 1)
    except Exception:
        pass


def _query_page(mapping_key: str) -> int | None:
    try:
        raw = st.query_params.get('mapping_page') or st.query_params.get(f'{mapping_key}_page')
    except Exception:
        raw = ''
    if isinstance(raw, list):
        raw = raw[0] if raw else ''
    text = str(raw or '').strip()
    if not text:
        return None
    return max(0, _safe_int(text, 1) - 1)


def _current_page(mapping_key: str, total_pages: int) -> int:
    pending = st.session_state.pop(_pending_key(mapping_key), None)
    if pending is not None:
        page = _clamp(pending, total_pages)
        st.session_state[_page_key(mapping_key)] = page
        _set_query_page(mapping_key, page)
        return page
    query_page = _query_page(mapping_key)
    if query_page is not None:
        page = _clamp(query_page, total_pages)
        st.session_state[_page_key(mapping_key)] = page
        return page
    page = _clamp(st.session_state.get(_page_key(mapping_key), 0), total_pages)
    st.session_state[_page_key(mapping_key)] = page
    return page


def _goto_page(mapping_key: str, page_index: int, total_pages: int, reason: str) -> None:
    previous = _safe_int(st.session_state.get(_page_key(mapping_key), 0), 0)
    page = _clamp(page_index, total_pages)
    st.session_state[_page_key(mapping_key)] = page
    st.session_state[_pending_key(mapping_key)] = page
    st.session_state[_scroll_key(mapping_key)] = True
    _set_query_page(mapping_key, page)
    add_audit_event(
        'mapping_runtime_page_changed',
        area='MAPEAMENTO',
        status='OK',
        details={
            'mapping_key': mapping_key,
            'from_page': previous + 1,
            'to_page': page + 1,
            'total_pages': total_pages,
            'reason': reason,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    st.rerun()


def runtime_visible_targets(mapping_key: str, targets: list[str]) -> list[str]:
    clean_targets = [str(target).strip() for target in targets if str(target).strip()]
    total = len(clean_targets)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = _current_page(mapping_key, total_pages)
    start = page * PAGE_SIZE
    end = min(start + PAGE_SIZE, total)
    visible = clean_targets[start:end]
    st.caption(f'Campos {start + 1 if total else 0} a {end} de {total} · página {page + 1}/{total_pages}')
    st.session_state[_meta_key(mapping_key)] = {
        'page_index': page,
        'total_pages': total_pages,
        'visible_start': start + 1 if total else 0,
        'visible_end': end,
        'total_targets': total,
        'page_size': PAGE_SIZE,
        'visible_count': len(visible),
        'runtime_pagination': True,
    }
    add_audit_event(
        'mapping_runtime_page_visible',
        area='MAPEAMENTO',
        status='OK',
        details={
            'mapping_key': mapping_key,
            'page': page + 1,
            'total_pages': total_pages,
            'visible_start': start + 1 if total else 0,
            'visible_end': end,
            'visible_count': len(visible),
            'total_targets': total,
            'page_size': PAGE_SIZE,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return visible


def runtime_mapping_has_more_pages(mapping_key: str) -> bool:
    meta = st.session_state.get(_meta_key(mapping_key))
    if not isinstance(meta, dict):
        return False
    return _safe_int(meta.get('page_index'), 0) < max(1, _safe_int(meta.get('total_pages'), 1)) - 1


def runtime_go_to_next_mapping_page(mapping_key: str, *, reason: str = 'mapping_continue_next_fields') -> bool:
    meta = st.session_state.get(_meta_key(mapping_key))
    if not isinstance(meta, dict):
        return False
    page = _safe_int(meta.get('page_index'), 0)
    total_pages = max(1, _safe_int(meta.get('total_pages'), 1))
    if page >= total_pages - 1:
        return False
    _goto_page(mapping_key, page + 1, total_pages, reason)
    return True


def runtime_render_mapping_page_arrows(mapping_key: str, *, position: str = 'bottom') -> None:
    meta = st.session_state.get(_meta_key(mapping_key))
    if not isinstance(meta, dict):
        return
    page = _safe_int(meta.get('page_index'), 0)
    total_pages = max(1, _safe_int(meta.get('total_pages'), 1))
    total = _safe_int(meta.get('total_targets'), 0)
    start = _safe_int(meta.get('visible_start'), 0)
    end = _safe_int(meta.get('visible_end'), 0)
    st.caption(f'Página {page + 1}/{total_pages} · Campos {start} a {end} de {total}')
    col_prev, col_next = st.columns(2)
    with col_prev:
        if st.button('← Campos anteriores', use_container_width=True, disabled=page <= 0, key=f'{mapping_key}_rt_prev_{position}'):
            _goto_page(mapping_key, page - 1, total_pages, 'previous_button')
    with col_next:
        if st.button('Próximos campos →', use_container_width=True, disabled=page >= total_pages - 1, key=f'{mapping_key}_rt_next_{position}'):
            _goto_page(mapping_key, page + 1, total_pages, 'next_button')

    if total_pages > 1 and position == 'bottom':
        st.caption('Ir direto para página:')
        page_cols = st.columns(min(total_pages, 6))
        for index in range(total_pages):
            with page_cols[index % len(page_cols)]:
                if st.button(str(index + 1), use_container_width=True, disabled=index == page, key=f'{mapping_key}_rt_page_{index + 1}_{position}'):
                    _goto_page(mapping_key, index, total_pages, 'page_number_button')


def install_mapping_pagination_runtime() -> None:
    if st.session_state.get(INSTALL_KEY):
        return
    try:
        from bling_app_zero.ui import mapping_pagination
        from bling_app_zero.ui import mapping_cadastro_flow

        mapping_pagination.visible_targets = runtime_visible_targets
        mapping_pagination.render_mapping_page_arrows = runtime_render_mapping_page_arrows
        mapping_pagination.mapping_has_more_pages = runtime_mapping_has_more_pages
        mapping_pagination.go_to_next_mapping_page = runtime_go_to_next_mapping_page

        mapping_cadastro_flow.visible_targets = runtime_visible_targets
        mapping_cadastro_flow.render_mapping_page_arrows = runtime_render_mapping_page_arrows
        mapping_cadastro_flow.mapping_has_more_pages = runtime_mapping_has_more_pages
        mapping_cadastro_flow.go_to_next_mapping_page = runtime_go_to_next_mapping_page

        st.session_state[INSTALL_KEY] = True
        add_audit_event('mapping_pagination_runtime_installed', area='MAPEAMENTO', status='OK', details={'page_size': PAGE_SIZE, 'responsible_file': RESPONSIBLE_FILE})
    except Exception as exc:
        add_audit_event('mapping_pagination_runtime_install_failed', area='MAPEAMENTO', status='ERRO', details={'error': str(exc)[:240], 'responsible_file': RESPONSIBLE_FILE})


__all__ = ['install_mapping_pagination_runtime']
