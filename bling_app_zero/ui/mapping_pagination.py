from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.mapping_constants import MAPPING_PAGE_SIZE

RESPONSIBLE_FILE = 'bling_app_zero/ui/mapping_pagination.py'


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

            try {{
                return document.getElementById(anchorId);
            }} catch (err) {{
                return null;
            }}
        }}

        function scrollToAnchor() {{
            const el = findAnchor();
            if (!el) return;

            try {{
                const parentWindow = window.parent || window;
                const rect = el.getBoundingClientRect();
                const currentY = parentWindow.scrollY || parentWindow.pageYOffset || 0;
                const targetY = Math.max(0, rect.top + currentY - 18);
                parentWindow.scrollTo({{ top: targetY, behavior: 'smooth' }});
                return;
            }} catch (err) {{}}

            try {{
                el.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
            }} catch (err) {{}}
        }}

        setTimeout(scrollToAnchor, 80);
        setTimeout(scrollToAnchor, 240);
        setTimeout(scrollToAnchor, 520);
    }})();
    </script>
    """


def render_mapping_page_scroll_anchor(mapping_key: str) -> None:
    anchor_id = mapping_page_anchor_id(mapping_key)
    should_scroll = bool(st.session_state.pop(mapping_page_scroll_key(mapping_key), False))
    st.markdown(
        f'<div id="{anchor_id}" data-bling-scroll-anchor="mapping-page" style="height:1px; scroll-margin-top:18px;"></div>',
        unsafe_allow_html=True,
    )
    if not should_scroll:
        return

    add_audit_event(
        'mapping_page_scroll_requested',
        area='MAPEAMENTO',
        details={
            'mapping_key': mapping_key,
            'anchor_id': anchor_id,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    components.html(_scroll_script(anchor_id), height=0, width=0)


def visible_targets(mapping_key: str, targets: list[str]) -> list[str]:
    if len(targets) <= MAPPING_PAGE_SIZE:
        st.session_state.pop(mapping_page_meta_key(mapping_key), None)
        return targets

    total_pages = (len(targets) + MAPPING_PAGE_SIZE - 1) // MAPPING_PAGE_SIZE
    page_key = mapping_page_key(mapping_key)
    try:
        page_index = int(st.session_state.get(page_key, 0) or 0)
    except Exception:
        page_index = 0
    page_index = max(0, min(page_index, total_pages - 1))
    st.session_state[page_key] = page_index

    start = page_index * MAPPING_PAGE_SIZE
    end = min(start + MAPPING_PAGE_SIZE, len(targets))
    st.caption(
        f'Bloco {page_index + 1} de {total_pages} · Exibindo {start + 1} a {end} de {len(targets)} campo(s). '
        'Os demais continuam salvos e entram no CSV final.'
    )
    render_mapping_page_scroll_anchor(mapping_key)
    st.session_state[mapping_page_meta_key(mapping_key)] = {
        'page_index': page_index,
        'total_pages': total_pages,
        'visible_start': start + 1,
        'visible_end': end,
        'total_targets': len(targets),
    }
    return targets[start:end]


def _change_mapping_page(mapping_key: str, next_index: int, *, direction: str, total_pages: int) -> None:
    page_key = mapping_page_key(mapping_key)
    scroll_key = mapping_page_scroll_key(mapping_key)
    previous_index = int(st.session_state.get(page_key, 0) or 0)
    safe_next = max(0, min(total_pages - 1, int(next_index)))
    st.session_state[page_key] = safe_next
    st.session_state[scroll_key] = True
    add_audit_event(
        'mapping_page_changed',
        area='MAPEAMENTO',
        details={
            'mapping_key': mapping_key,
            'direction': direction,
            'from_page': previous_index + 1,
            'to_page': safe_next + 1,
            'total_pages': total_pages,
            'scroll_to_top': True,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    st.rerun()


def render_mapping_page_arrows(mapping_key: str) -> None:
    meta = st.session_state.get(mapping_page_meta_key(mapping_key))
    if not isinstance(meta, dict):
        return
    page_index = int(meta.get('page_index') or 0)
    total_pages = max(1, int(meta.get('total_pages') or 1))

    st.markdown('<div style="height:.15rem"></div>', unsafe_allow_html=True)
    col_prev, col_mid, col_next = st.columns([1, 2, 1])
    with col_prev:
        if st.button('←', use_container_width=True, disabled=page_index <= 0, key=f'{mapping_key}_page_prev'):
            _change_mapping_page(mapping_key, page_index - 1, direction='previous', total_pages=total_pages)
    with col_mid:
        st.markdown(
            f'<div style="text-align:center; padding-top:.55rem; color:#64748b; font-size:.86rem; font-weight:700;">{page_index + 1}/{total_pages}</div>',
            unsafe_allow_html=True,
        )
    with col_next:
        if st.button('→', use_container_width=True, disabled=page_index >= total_pages - 1, key=f'{mapping_key}_page_next'):
            _change_mapping_page(mapping_key, page_index + 1, direction='next', total_pages=total_pages)


__all__ = [
    'mapping_page_anchor_id',
    'mapping_page_key',
    'mapping_page_meta_key',
    'mapping_page_scroll_key',
    'render_mapping_page_arrows',
    'render_mapping_page_scroll_anchor',
    'visible_targets',
]
