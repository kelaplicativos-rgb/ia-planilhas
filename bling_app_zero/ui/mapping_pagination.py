from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.home_wizard_rerun import safe_rerun
from bling_app_zero.ui.mapping_constants import MAPPING_PAGE_SIZE

RESPONSIBLE_FILE = 'bling_app_zero/ui/mapping_pagination.py'
MOBILE_MAPPING_PAGE_SIZE = 6


def mapping_page_key(mapping_key: str) -> str:
    return f'{mapping_key}_page_index'


def mapping_page_meta_key(mapping_key: str) -> str:
    return f'{mapping_key}_page_meta'


def mapping_page_scroll_key(mapping_key: str) -> str:
    return f'{mapping_key}_scroll_to_page_top'


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
    page_key = mapping_page_key(mapping_key)
    try:
        page_index = int(st.session_state.get(page_key, 0) or 0)
    except Exception:
        page_index = 0
    page_index = max(0, min(page_index, total_pages - 1))
    st.session_state[page_key] = page_index

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
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return targets[start:end]


def _change_mapping_page(mapping_key: str, next_index: int, *, direction: str, total_pages: int) -> None:
    page_key = mapping_page_key(mapping_key)
    scroll_key = mapping_page_scroll_key(mapping_key)
    previous_index = int(st.session_state.get(page_key, 0) or 0)
    safe_next = max(0, min(total_pages - 1, int(next_index)))
    st.session_state[page_key] = safe_next
    st.session_state[scroll_key] = True
    st.session_state['mapping_last_interruption_point'] = {
        'mapping_key': mapping_key,
        'from_page': previous_index + 1,
        'to_page': safe_next + 1,
        'total_pages': total_pages,
        'direction': direction,
        'reason': 'usuario_navegou_campos_mapeamento',
        'responsible_file': RESPONSIBLE_FILE,
    }
    add_audit_event('mapping_page_changed', area='MAPEAMENTO', details={'mapping_key': mapping_key, 'direction': direction, 'from_page': previous_index + 1, 'to_page': safe_next + 1, 'total_pages': total_pages, 'scroll_to_top': True, 'responsible_file': RESPONSIBLE_FILE})
    safe_rerun('mapping_page_changed')


def _page_label(meta: dict) -> str:
    page_index = int(meta.get('page_index') or 0)
    total_pages = max(1, int(meta.get('total_pages') or 1))
    start = int(meta.get('visible_start') or 0)
    end = int(meta.get('visible_end') or 0)
    total = int(meta.get('total_targets') or 0)
    if total <= 0:
        return 'Nenhum campo neste filtro.'
    return f'Página {page_index + 1}/{total_pages} · Campos {start} a {end} de {total}'


def render_mapping_page_arrows(mapping_key: str, *, position: str = 'bottom') -> None:
    meta = st.session_state.get(mapping_page_meta_key(mapping_key))
    if not isinstance(meta, dict):
        return
    page_index = int(meta.get('page_index') or 0)
    total_pages = max(1, int(meta.get('total_pages') or 1))
    total_targets = int(meta.get('total_targets') or 0)

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
    'mapping_page_anchor_id',
    'mapping_page_key',
    'mapping_page_meta_key',
    'mapping_page_scroll_key',
    'render_mapping_page_arrows',
    'render_mapping_page_scroll_anchor',
    'visible_targets',
]
