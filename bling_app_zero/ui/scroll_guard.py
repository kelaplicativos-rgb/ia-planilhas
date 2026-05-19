from __future__ import annotations

import streamlit.components.v1 as components


def inject_scroll_guard(namespace: str = 'mapeiaai') -> None:
    """Preserva a posição da tela entre reruns causados por widgets.

    Regra de UX: depois de clicar, anexar, selecionar ou buscar, a tela deve
    permanecer na região da ação. O guard salva a posição antes da interação e
    evita que o rerun do Streamlit sobrescreva a posição salva com o topo da tela.
    """
    safe_namespace = ''.join(ch for ch in str(namespace or 'mapeiaai') if ch.isalnum() or ch in {'_', '-'})
    storage_key = f'{safe_namespace}_scroll_y'
    installed_key = f'__{safe_namespace}_scroll_guard_installed__'
    pending_restore_key = f'{safe_namespace}_scroll_pending_restore'
    restoring_until_key = f'{safe_namespace}_scroll_restoring_until'

    components.html(
        f"""
<script>
(function () {{
  const w = window.parent;
  const d = w.document;
  const storageKey = {storage_key!r};
  const installedKey = {installed_key!r};
  const pendingRestoreKey = {pending_restore_key!r};
  const restoringUntilKey = {restoring_until_key!r};

  function now() {{ return Date.now ? Date.now() : new Date().getTime(); }}

  function candidates() {{
    const items = [
      w,
      d.scrollingElement,
      d.documentElement,
      d.body,
      d.querySelector('section.main'),
      d.querySelector('.main'),
      d.querySelector('[data-testid="stAppViewContainer"]'),
      d.querySelector('[data-testid="stMain"]'),
      d.querySelector('[data-testid="stVerticalBlock"]')
    ];
    return items.filter(Boolean);
  }}

  function currentY() {{
    let y = 0;
    for (const el of candidates()) {{
      try {{
        const value = el === w ? (w.scrollY || w.pageYOffset || 0) : (el.scrollTop || 0);
        if (value > y) y = value;
      }} catch (e) {{}}
    }}
    return y;
  }}

  function readSavedY() {{
    try {{ return parseInt(w.sessionStorage.getItem(storageKey) || '0', 10) || 0; }} catch (e) {{ return 0; }}
  }}

  function isRestoring() {{
    try {{
      const until = parseInt(w.sessionStorage.getItem(restoringUntilKey) || '0', 10) || 0;
      return until > now();
    }} catch (e) {{
      return false;
    }}
  }}

  function markPendingRestore(durationMs) {{
    try {{
      w.sessionStorage.setItem(pendingRestoreKey, '1');
      w.sessionStorage.setItem(restoringUntilKey, String(now() + (durationMs || 3200)));
    }} catch (e) {{}}
  }}

  function saveScroll(force) {{
    try {{
      const y = currentY();
      const saved = readSavedY();

      // Durante o rerun, o Streamlit pode jogar a tela para 0 antes de remontar.
      // Não deixe esse 0 apagar a posição real onde o usuário clicou.
      if (!force && isRestoring() && y < Math.max(20, saved - 80)) return;

      if (y >= 0) {{
        w.sessionStorage.setItem(storageKey, String(y));
        markPendingRestore(3400);
      }}
    }} catch (e) {{}}
  }}

  function saveInteractionPosition(event) {{
    try {{
      const y = currentY();
      if (y > 0) {{
        w.sessionStorage.setItem(storageKey, String(y));
        markPendingRestore(3600);
      }}
    }} catch (e) {{
      saveScroll(true);
    }}
  }}

  function shouldRestore(y) {{
    if (y <= 0) return false;
    try {{
      const pending = w.sessionStorage.getItem(pendingRestoreKey) === '1';
      const current = currentY();
      return pending || current < Math.max(20, y - 80);
    }} catch (e) {{
      return true;
    }}
  }}

  function applyScroll(y) {{
    for (const el of candidates()) {{
      try {{
        if (el === w) el.scrollTo(0, y);
        else el.scrollTop = y;
      }} catch (e) {{}}
    }}
  }}

  function restoreScroll() {{
    const y = readSavedY();
    if (!shouldRestore(y)) return;
    markPendingRestore(3600);

    const delays = [0, 35, 80, 140, 220, 340, 520, 760, 1050, 1400, 1850, 2400, 3100];
    for (const delay of delays) {{
      w.setTimeout(function () {{
        const target = readSavedY();
        if (shouldRestore(target)) applyScroll(target);
      }}, delay);
    }}

    w.setTimeout(function () {{
      try {{
        w.sessionStorage.removeItem(pendingRestoreKey);
        w.sessionStorage.removeItem(restoringUntilKey);
      }} catch (e) {{}}
    }}, 3800);
  }}

  restoreScroll();

  if (!w[installedKey]) {{
    w[installedKey] = true;
    const interactionEvents = ['mousedown', 'touchstart', 'touchend', 'pointerdown', 'keydown', 'focusin', 'input', 'change', 'click', 'submit'];
    for (const eventName of interactionEvents) {{
      d.addEventListener(eventName, saveInteractionPosition, true);
    }}
    w.addEventListener('beforeunload', function () {{ saveScroll(true); }}, true);
    w.addEventListener('pagehide', function () {{ saveScroll(true); }}, true);
    w.addEventListener('visibilitychange', function () {{ saveScroll(true); }}, true);
    w.addEventListener('scroll', function () {{
      if (w.__mapeiaai_scroll_timer__) w.clearTimeout(w.__mapeiaai_scroll_timer__);
      w.__mapeiaai_scroll_timer__ = w.setTimeout(function () {{ saveScroll(false); }}, 120);
    }}, true);
  }}
}})();
</script>
        """,
        height=0,
        width=0,
    )


__all__ = ['inject_scroll_guard']
