from __future__ import annotations

import streamlit.components.v1 as components


def inject_scroll_guard(namespace: str = 'mapeiaai') -> None:
    """Preserva a posição da tela entre reruns causados por widgets.

    Streamlit reexecuta o script quando selectbox, radio, input, upload ou botão
    muda. Em mobile, o DOM pode demorar mais para estabilizar; por isso a
    restauração precisa ser repetida por mais tempo para evitar que a tela suba
    depois da ação.
    """
    safe_namespace = ''.join(ch for ch in str(namespace or 'mapeiaai') if ch.isalnum() or ch in {'_', '-'})
    storage_key = f'{safe_namespace}_scroll_y'
    installed_key = f'__{safe_namespace}_scroll_guard_installed__'
    pending_restore_key = f'{safe_namespace}_scroll_pending_restore'

    components.html(
        f"""
<script>
(function () {{
  const w = window.parent;
  const d = w.document;
  const storageKey = {storage_key!r};
  const installedKey = {installed_key!r};
  const pendingRestoreKey = {pending_restore_key!r};

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

  function saveScroll() {{
    try {{
      const y = currentY();
      if (y >= 0) {{
        w.sessionStorage.setItem(storageKey, String(y));
        w.sessionStorage.setItem(pendingRestoreKey, '1');
      }}
    }} catch (e) {{}}
  }}

  function readSavedY() {{
    try {{ return parseInt(w.sessionStorage.getItem(storageKey) || '0', 10) || 0; }} catch (e) {{ return 0; }}
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

    const delays = [0, 40, 90, 160, 260, 420, 650, 900, 1250, 1650, 2200];
    for (const delay of delays) {{
      w.setTimeout(function () {{
        const target = readSavedY();
        if (shouldRestore(target)) {{
          applyScroll(target);
        }}
      }}, delay);
    }}

    w.setTimeout(function () {{
      try {{ w.sessionStorage.removeItem(pendingRestoreKey); }} catch (e) {{}}
    }}, 2600);
  }}

  restoreScroll();

  if (!w[installedKey]) {{
    w[installedKey] = true;
    const events = ['mousedown', 'touchstart', 'touchend', 'pointerdown', 'keydown', 'focusin', 'input', 'change', 'click', 'submit'];
    for (const eventName of events) {{
      d.addEventListener(eventName, saveScroll, true);
    }}
    w.addEventListener('beforeunload', saveScroll, true);
    w.addEventListener('pagehide', saveScroll, true);
    w.addEventListener('visibilitychange', saveScroll, true);
    w.addEventListener('scroll', function () {{
      if (w.__mapeiaai_scroll_timer__) w.clearTimeout(w.__mapeiaai_scroll_timer__);
      w.__mapeiaai_scroll_timer__ = w.setTimeout(saveScroll, 100);
    }}, true);
  }}
}})();
</script>
        """,
        height=0,
        width=0,
    )


__all__ = ['inject_scroll_guard']
