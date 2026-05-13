from __future__ import annotations

import streamlit.components.v1 as components

RESPONSIBLE_FILE = 'bling_app_zero/ui/scroll_position.py'


SCROLL_KEEPER_SCRIPT = """
<script>
(function () {
    const STORAGE_PREFIX = 'bling_scroll_position_v1:';
    const RESTORE_FLAG_PREFIX = 'bling_scroll_restore_enabled_v1:';

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


def inject_scroll_position_keeper() -> None:
    """Preserva a posição visual da tela nos reruns normais do Streamlit.

    Regra do projeto:
    - Qualquer clique, seleção ou alteração no fluxo mantém a posição atual após rerun.
    - A exceção do mapeamento por página continua sendo controlada por mapping_pagination.py.
    """
    components.html(SCROLL_KEEPER_SCRIPT, height=0, width=0)


__all__ = ['inject_scroll_position_keeper']
