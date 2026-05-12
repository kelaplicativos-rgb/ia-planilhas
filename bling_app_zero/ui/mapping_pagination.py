from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.mapping_constants import MAPPING_PAGE_SIZE


def mapping_page_key(mapping_key: str) -> str:
    return f'{mapping_key}_page_index'


def mapping_page_meta_key(mapping_key: str) -> str:
    return f'{mapping_key}_page_meta'


def mapping_page_scroll_key(mapping_key: str) -> str:
    return f'{mapping_key}_scroll_to_page_top'


def mapping_page_anchor_id(mapping_key: str) -> str:
    return f'{mapping_key}_page_anchor'.replace('_', '-')


def render_mapping_page_scroll_anchor(mapping_key: str) -> None:
    anchor_id = mapping_page_anchor_id(mapping_key)
    should_scroll = bool(st.session_state.pop(mapping_page_scroll_key(mapping_key), False))
    st.markdown(f'<div id="{anchor_id}" style="height:1px;"></div>', unsafe_allow_html=True)
    if not should_scroll:
        return
    st.markdown(
        f"""
        <script>
        setTimeout(function() {{
            const doc = window.parent ? window.parent.document : document;
            const el = doc.getElementById("{anchor_id}");
            if (el) {{
                el.scrollIntoView({{behavior: "smooth", block: "start"}});
            }}
        }}, 120);
        </script>
        """,
        unsafe_allow_html=True,
    )


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
    }
    return targets[start:end]


def render_mapping_page_arrows(mapping_key: str) -> None:
    meta = st.session_state.get(mapping_page_meta_key(mapping_key))
    if not isinstance(meta, dict):
        return
    page_key = mapping_page_key(mapping_key)
    scroll_key = mapping_page_scroll_key(mapping_key)
    page_index = int(meta.get('page_index') or 0)
    total_pages = max(1, int(meta.get('total_pages') or 1))

    st.markdown('<div style="height:.15rem"></div>', unsafe_allow_html=True)
    col_prev, col_mid, col_next = st.columns([1, 2, 1])
    with col_prev:
        if st.button('←', use_container_width=True, disabled=page_index <= 0, key=f'{mapping_key}_page_prev'):
            st.session_state[page_key] = max(0, page_index - 1)
            st.session_state[scroll_key] = True
            st.rerun()
    with col_mid:
        st.markdown(
            f'<div style="text-align:center; padding-top:.55rem; color:#64748b; font-size:.86rem; font-weight:700;">{page_index + 1}/{total_pages}</div>',
            unsafe_allow_html=True,
        )
    with col_next:
        if st.button('→', use_container_width=True, disabled=page_index >= total_pages - 1, key=f'{mapping_key}_page_next'):
            st.session_state[page_key] = min(total_pages - 1, page_index + 1)
            st.session_state[scroll_key] = True
            st.rerun()


__all__ = [
    'mapping_page_anchor_id',
    'mapping_page_key',
    'mapping_page_meta_key',
    'mapping_page_scroll_key',
    'render_mapping_page_arrows',
    'render_mapping_page_scroll_anchor',
    'visible_targets',
]
