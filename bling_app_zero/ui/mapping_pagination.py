from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.home_wizard_rerun import safe_rerun

RESPONSIBLE_FILE = 'bling_app_zero/ui/mapping_pagination.py'
MOBILE_MAPPING_PAGE_SIZE = 10


def mapping_page_key(mapping_key: str) -> str:
    return f'{mapping_key}_page_index'


def mapping_page_meta_key(mapping_key: str) -> str:
    return f'{mapping_key}_page_meta'


def mapping_page_scroll_key(mapping_key: str) -> str:
    return f'{mapping_key}_scroll_to_page_top'


def mapping_page_pending_key(mapping_key: str) -> str:
    return f'{mapping_key}_pending_page_index'


def mapping_page_select_key(mapping_key: str) -> str:
    return f'{mapping_key}_page_selector'


def mapping_page_anchor_id(mapping_key: str) -> str:
    safe = ''.join(ch if ch.isalnum() else '-' for ch in str(mapping_key))
    safe = '-'.join(part for part in safe.split('-') if part)
    return f'bling-mapping-page-anchor-{safe or "default"}'


def _page_size() -> int:
    return MOBILE_MAPPING_PAGE_SIZE


def _scroll_script(anchor_id: str) -> str:
    return f"""
    <script>
    (function() {{
        const anchorId = {anchor_id!r};
        function findAnchor() {{
            try {{
                const parentDoc = window.parent && window.parent.document ? window.parent.document : null;
                if (parentDoc) {{
                    const fromParent = parentDoc.getElementById(anchorId);
                    if (fromParent) return fromParent;
                }}
            }} catch (err) {{}}
            try {{ return document.getElementById(anchorId); }} catch (err) {{ return null; }}
        }}
        function scrollToAnchor() {{
            const el = findAnchor();
            if (!el) return;
            try {{ el.scrollIntoView({{ behavior: 'smooth', block: 'start' }}); }}
            catch (err) {{ try {{ el.scrollIntoView(true); }} catch (err2) {{}} }}
        }}
        setTimeout(scrollToAnchor, 60);
        setTimeout(scrollToAnchor, 220);
        setTimeout(scrollToAnchor, 520);
    }})();
    </script>
    """


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value or default)
    except Exception:
        return default


def _query_page_index(mapping_key: str) -> int | None:
    try:
        raw = st.query_params.get('mapping_page') or st.query_params.get(f'{mapping_key}_page')
    except Exception:
        raw = ''
    if isinstance(raw, list):
        raw = raw[0] if raw else ''
    text = str(raw or '').strip()
    if not text:
        return None
    value = _safe_int(text, 1)
    return max(0, value - 1)


def _set_query_page(mapping_key: str, page_index: int) -> None:
    try:
        st.query_params['mapping_page'] = str(int(page_index) + 1)
        st.query_params[f'{mapping_key}_page'] = str(int(page_index) + 1)
    except Exception:
        pass


def _clamp_page(index: object, total_pages: int) -> int:
    return max(0, min(max(1, int(total_pages)) - 1, _safe_int(index, 0)))


def _current_page_index(mapping_key: str, total_pages: int) -> int:
    page_key = mapping_page_key(mapping_key)
    pending_key = mapping_page_pending_key(mapping_key)
    pending = st.session_state.pop(pending_key, None)
    if pending is not None:
        page_index = _clamp_page(pending, total_pages)
        st.session_state[page_key] = page_index
        _set_query_page(mapping_key, page_index)
        return page_index

    query_index = _query_page_index(mapping_key)
    if query_index is not None:
        page_index = _clamp_page(query_index, total_pages)
        st.session_state[page_key] = page_index
        return page_index

    page_index = _clamp_page(st.session_state.get(page_key, 0), total_pages)
    st.session_state[page_key] = page_index
    return page_index


def _page_option_labels(total_pages: int) -> list[str]:
    return [f'Página {index + 1}' for index in range(max(1, total_pages))]


def _render_direct_page_selector(mapping_key: str, page_index: int, total_pages: int, total_targets: int) -> int:
    if total_pages <= 1:
        return page_index
    labels = _page_option_labels(total_pages)
    selector_key = mapping_page_select_key(mapping_key)
    current_label = labels[_clamp_page(page_index, total_pages)]
    st.caption('Navegação do mapeamento')
    selected = st.selectbox(
        'Escolher página de campos',
        labels,
        index=labels.index(current_label),
        key=selector_key,
        label_visibility='collapsed',
        help='Use este seletor se o botão Próximos campos não mudar a tela no celular.',
    )
    selected_index = labels.index(selected)
    if selected_index != page_index:
        st.session_state[mapping_page_key(mapping_key)] = selected_index
        st.session_state[mapping_page_scroll_key(mapping_key)] = True
        _set_query_page(mapping_key, selected_index)
        add_audit_event(
            'mapping_page_selector_changed',
            area='MAPEAMENTO',
            status='OK',
            details={
                'mapping_key': mapping_key,
                'from_page': page_index + 1,
                'to_page': selected_index + 1,
                'total_pages': total_pages,
                'total_targets': total_targets,
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
        return selected_index
    return page_index


def render_mapping_page_scroll_anchor(mapping_key: str) -> None:
    anchor_id = mapping_page_anchor_id(mapping_key)
    should_scroll = bool(st.session_state.pop(mapping_page_scroll_key(mapping_key), False))
    st.markdown(f'<div id="{anchor_id}" data-bling-scroll-anchor="mapping-page"></div>', unsafe_allow_html=True)
    if not should_scroll:
        return
    add_audit_event('mapping_page_scroll_requested', area='MAPEAMENTO', details={'mapping_key': mapping_key, 'anchor_id': anchor_id, 'responsible_file': RESPONSIBLE_FILE})
    components.html(_scroll_script(anchor_id), height=0, width=0)


def visible_targets(mapping_key: str, targets: list[str]) -> list[str]:
    page_size = _page_size()
    total_targets = len(targets)
    total_pages = max(1, (total_targets + page_size - 1) // page_size)
    page_index = _current_page_index(mapping_key, total_pages)
    page_index = _render_direct_page_selector(mapping_key, page_index, total_pages, total_targets)
    page_index = _clamp_page(page_index, total_pages)
    st.session_state[mapping_page_key(mapping_key)] = page_index
    _set_query_page(mapping_key, page_index)

    start = page_index * page_size
    end = min(start + page_size, total_targets)
    if total_targets:
        label = f'Campos {start + 1} a {end} de {total_targets} · página {page_index + 1}/{total_pages}'
    else:
        label = 'Nenhum campo neste filtro.'
    st.caption(label)
    render_mapping_page_scroll_anchor(mapping_key)
    st.session_state[mapping_page_meta_key(mapping_key)] = {
        'page_index': page_index,
        'total_pages': total_pages,
        'visible_start': start + 1 if total_targets else 0,
        'visible_end': end,
        'total_targets': total_targets,
        'page_size': page_size,
    }
    add_audit_event(
        'mapping_page_visible',
        area='MAPEAMENTO',
        details={
            'mapping_key': mapping_key,
            'page': page_index + 1,
            'total_pages': total_pages,
            'visible_start': start + 1 if total_targets else 0,
            'visible_end': end,
            'total_targets': total_targets,
            'page_size': page_size,
            'selector_enabled': total_pages > 1,
            'query_page_synced': True,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return targets[start:end]


def _change_mapping_page(mapping_key: str, next_index: int, *, direction: str, total_pages: int) -> None:
    page_key = mapping_page_key(mapping_key)
    pending_key = mapping_page_pending_key(mapping_key)
    scroll_key = mapping_page_scroll_key(mapping_key)
    previous_index = _safe_int(st.session_state.get(page_key, 0), 0)
    safe_next = _clamp_page(next_index, total_pages)
    st.session_state[page_key] = safe_next
    st.session_state[pending_key] = safe_next
    st.session_state[scroll_key] = True
    _set_query_page(mapping_key, safe_next)
    st.session_state['mapping_last_interruption_point'] = {
        'mapping_key': mapping_key,
        'from_page': previous_index + 1,
        'to_page': safe_next + 1,
        'total_pages': total_pages,
        'direction': direction,
        'reason': 'usuario_navegou_campos_mapeamento',
        'responsible_file': RESPONSIBLE_FILE,
    }
    add_audit_event('mapping_page_changed', area='MAPEAMENTO', details={'mapping_key': mapping_key, 'direction': direction, 'from_page': previous_index + 1, 'to_page': safe_next + 1, 'total_pages': total_pages, 'scroll_to_top': True, 'query_page_synced': True, 'responsible_file': RESPONSIBLE_FILE})
    safe_rerun('mapping_page_changed')


def go_to_next_mapping_page(mapping_key: str, *, reason: str = 'mapping_continue_next_fields') -> bool:
    meta = st.session_state.get(mapping_page_meta_key(mapping_key))
    if not isinstance(meta, dict):
        return False
    page_index = _safe_int(meta.get('page_index'), 0)
    total_pages = max(1, _safe_int(meta.get('total_pages'), 1))
    if page_index >= total_pages - 1:
        return False
    visited_key = f'{mapping_key}_visited_pages'
    visited_raw = st.session_state.get(visited_key)
    visited = set(visited_raw or []) if isinstance(visited_raw, (list, tuple, set)) else set()
    visited.add(page_index)
    visited.add(page_index + 1)
    st.session_state[visited_key] = sorted(visited)
    add_audit_event(
        'mapping_continue_to_next_fields_clicked',
        area='MAPEAMENTO',
        status='OK',
        details={
            'mapping_key': mapping_key,
            'from_page': page_index + 1,
            'to_page': page_index + 2,
            'total_pages': total_pages,
            'reason': reason,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    _change_mapping_page(mapping_key, page_index + 1, direction='next_required', total_pages=total_pages)
    return True


def mapping_has_more_pages(mapping_key: str) -> bool:
    meta = st.session_state.get(mapping_page_meta_key(mapping_key))
    if not isinstance(meta, dict):
        return False
    page_index = _safe_int(meta.get('page_index'), 0)
    total_pages = max(1, _safe_int(meta.get('total_pages'), 1))
    return page_index < total_pages - 1


def _page_label(meta: dict) -> str:
    page_index = _safe_int(meta.get('page_index'), 0)
    total_pages = max(1, _safe_int(meta.get('total_pages'), 1))
    start = _safe_int(meta.get('visible_start'), 0)
    end = _safe_int(meta.get('visible_end'), 0)
    total = _safe_int(meta.get('total_targets'), 0)
    if total <= 0:
        return 'Nenhum campo neste filtro.'
    return f'Página {page_index + 1}/{total_pages} · Campos {start} a {end} de {total}'


def render_mapping_page_arrows(mapping_key: str, *, position: str = 'bottom') -> None:
    meta = st.session_state.get(mapping_page_meta_key(mapping_key))
    if not isinstance(meta, dict):
        return
    page_index = _safe_int(meta.get('page_index'), 0)
    total_pages = max(1, _safe_int(meta.get('total_pages'), 1))
    total_targets = _safe_int(meta.get('total_targets'), 0)

    st.caption(_page_label(meta))
    col_prev, col_next = st.columns(2)
    with col_prev:
        if st.button('← Campos anteriores', use_container_width=True, disabled=page_index <= 0, key=f'{mapping_key}_page_prev_{position}'):
            _change_mapping_page(mapping_key, page_index - 1, direction='previous', total_pages=total_pages)
    with col_next:
        if st.button('Próximos campos →', use_container_width=True, disabled=page_index >= total_pages - 1, key=f'{mapping_key}_page_next_{position}'):
            _change_mapping_page(mapping_key, page_index + 1, direction='next', total_pages=total_pages)

    if total_targets > 0 and total_pages <= 1 and position == 'bottom':
        st.caption('Todos os campos do filtro atual já estão nesta tela.')


__all__ = [
    'go_to_next_mapping_page',
    'mapping_has_more_pages',
    'mapping_page_anchor_id',
    'mapping_page_key',
    'mapping_page_meta_key',
    'mapping_page_pending_key',
    'mapping_page_scroll_key',
    'mapping_page_select_key',
    'render_mapping_page_arrows',
    'render_mapping_page_scroll_anchor',
    'visible_targets',
]
