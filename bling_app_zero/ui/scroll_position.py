from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

RESPONSIBLE_FILE = 'bling_app_zero/ui/scroll_position.py'
FORCE_TOP_KEY = 'bling_force_scroll_top_next_render'


SCROLL_KEEPER_SCRIPT = """
<script>
(function () {
    const STORAGE_PREFIX = 'bling_scroll_position_v1:';
    const RESTORE_FLAG_PREFIX = 'bling_scroll_restore_enabled_v1:';
    const FORCE_TOP_KEY = 'bling_force_scroll_top_v1';

    function parentWindow() {
        try {
            return window.parent || window;
        } catch (err) {
            return window;
        }
    }

    function parentDocument() {
        try {
            return parentWindow().document || document;
        } catch (err) {
            return document;
        }
    }

    function locationKey() {
        try {
            const loc = parentWindow().location || window.location;
            return STORAGE_PREFIX + loc.pathname + loc.search;
        } catch (err) {
            return STORAGE_PREFIX + 'default';
        }
    }

    function restoreFlagKey() {
        try {
            const loc = parentWindow().location || window.location;
            return RESTORE_FLAG_PREFIX + loc.pathname + loc.search;
        } catch (err) {
            return RESTORE_FLAG_PREFIX + 'default';
        }
    }

    function currentScrollY() {
        const win = parentWindow();
        const doc = parentDocument();
        const body = doc.body || {};
        const root = doc.documentElement || {};
        return Math.max(0, Number(win.scrollY || win.pageYOffset || root.scrollTop || body.scrollTop || 0));
    }

    function maxScrollY() {
        const win = parentWindow();
        const doc = parentDocument();
        const body = doc.body || {};
        const root = doc.documentElement || {};
        const height = Math.max(
            Number(body.scrollHeight || 0),
            Number(root.scrollHeight || 0),
            Number(body.offsetHeight || 0),
            Number(root.offsetHeight || 0)
        );
        return Math.max(0, height - Number(win.innerHeight || root.clientHeight || 0));
    }

    function scrollTopNow() {
        const win = parentWindow();
        const doc = parentDocument();
        try { win.scrollTo({ top: 0, left: 0, behavior: 'auto' }); } catch (err) {}
        try { win.scrollTo(0, 0); } catch (err) {}
        try { doc.documentElement.scrollTop = 0; } catch (err) {}
        try { doc.body.scrollTop = 0; } catch (err) {}
    }

    function shouldForceTop() {
        try {
            const forced = parentWindow().sessionStorage.getItem(FORCE_TOP_KEY) === '1';
            if (forced) {
                parentWindow().sessionStorage.removeItem(FORCE_TOP_KEY);
                parentWindow().localStorage.removeItem(locationKey());
                parentWindow().localStorage.removeItem(restoreFlagKey());
                return true;
            }
        } catch (err) {}
        return false;
    }

    function savePosition() {
        try {
            const y = currentScrollY();
            const payload = {
                y: y,
                savedAt: Date.now(),
                maxY: maxScrollY()
            };
            parentWindow().localStorage.setItem(locationKey(), JSON.stringify(payload));
            parentWindow().localStorage.setItem(restoreFlagKey(), '1');
        } catch (err) {}
    }

    function readPosition() {
        try {
            const enabled = parentWindow().localStorage.getItem(restoreFlagKey());
            if (enabled !== '1') return null;
            const raw = parentWindow().localStorage.getItem(locationKey());
            if (!raw) return null;
            const payload = JSON.parse(raw);
            if (!payload || typeof payload.y !== 'number') return null;
            if (Date.now() - Number(payload.savedAt || 0) > 1000 * 60 * 60 * 8) return null;
            return Math.max(0, Math.min(payload.y, maxScrollY()));
        } catch (err) {
            return null;
        }
    }

    function restorePosition() {
        if (shouldForceTop()) {
            scrollTopNow();
            setTimeout(scrollTopNow, 80);
            setTimeout(scrollTopNow, 220);
            return;
        }
        const y = readPosition();
        if (y === null) return;
        try {
            parentWindow().scrollTo({ top: y, left: 0, behavior: 'auto' });
        } catch (err) {
            try { parentWindow().scrollTo(0, y); } catch (innerErr) {}
        }
    }

    function installListeners() {
        const win = parentWindow();
        const doc = parentDocument();
        if (win.__blingScrollKeeperInstalled) return;
        win.__blingScrollKeeperInstalled = true;

        let ticking = false;
        function throttledSave() {
            if (ticking) return;
            ticking = true;
            win.setTimeout(function () {
                ticking = false;
                savePosition();
            }, 120);
        }

        win.addEventListener('scroll', throttledSave, { passive: true });
        win.addEventListener('pagehide', savePosition);
        win.addEventListener('beforeunload', savePosition);
        doc.addEventListener('visibilitychange', function () {
            if (doc.visibilityState === 'hidden') savePosition();
        });

        ['mousedown', 'mouseup', 'click', 'change', 'input', 'keydown', 'submit'].forEach(function (eventName) {
            doc.addEventListener(eventName, savePosition, true);
        });
    }

    installListeners();
    setTimeout(restorePosition, 40);
    setTimeout(restorePosition, 180);
    setTimeout(restorePosition, 420);
})();
</script>
"""


FORCE_TOP_SCRIPT = """
<script>
(function () {
    function parentWindow() {
        try { return window.parent || window; } catch (err) { return window; }
    }
    const win = parentWindow();
    try { win.sessionStorage.setItem('bling_force_scroll_top_v1', '1'); } catch (err) {}
    try { win.scrollTo({ top: 0, left: 0, behavior: 'auto' }); } catch (err) {}
    try { win.scrollTo(0, 0); } catch (err) {}
})();
</script>
"""


def request_scroll_top() -> None:
    """Marca o próximo render para começar no topo.

    Use em mudanças grandes de fluxo/tela. Reruns normais continuam preservando
    a posição para não atrapalhar preenchimento de campos.
    """
    st.session_state[FORCE_TOP_KEY] = True


def inject_scroll_position_keeper() -> None:
    """Preserva posição nos reruns normais e força topo quando solicitado."""
    if st.session_state.pop(FORCE_TOP_KEY, False):
        components.html(FORCE_TOP_SCRIPT, height=0, width=0)
    components.html(SCROLL_KEEPER_SCRIPT, height=0, width=0)


__all__ = ['inject_scroll_position_keeper', 'request_scroll_top']
