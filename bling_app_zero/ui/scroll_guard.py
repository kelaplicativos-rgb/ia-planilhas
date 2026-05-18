from __future__ import annotations

import streamlit.components.v1 as components


def inject_scroll_guard(namespace: str = 'mapeiaai') -> None:
    """Preserva a posição da tela entre reruns causados por widgets.

    Streamlit reexecuta o script quando selectbox, radio, input ou botão muda.
    Em páginas longas isso pode jogar a tela para o topo. Este guard salva a
    posição antes da interação e restaura logo após o rerun, sem alterar dados
    do fluxo.
    """
    safe_namespace = ''.join(ch for ch in str(namespace or 'mapeiaai') if ch.isalnum() or ch in {'_', '-'})
    storage_key = f'{safe_namespace}_scroll_y'
    installed_key = f'__{safe_namespace}_scroll_guard_installed__'

    components.html(
        f"""
<script>
(function () {{
  const w = window.parent;
  const d = w.document;
  const storageKey = {storage_key!r};
  const installedKey = {installed_key!r};

  function candidates() {{
    const items = [
      w,
      d.scrollingElement,
      d.documentElement,
      d.body,
      d.querySelector('section.main'),
      d.querySelector('[data-testid="stAppViewContainer"]'),
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
      if (y >= 0) w.sessionStorage.setItem(storageKey, String(y));
    }} catch (e) {{}}
  }}

  function restoreScroll() {{
    let y = 0;
    try {{ y = parseInt(w.sessionStorage.getItem(storageKey) || '0', 10) || 0; }} catch (e) {{ y = 0; }}
    if (y <= 0) return;

    const apply = function () {{
      for (const el of candidates()) {{
        try {{
          if (el === w) el.scrollTo(0, y);
          else el.scrollTop = y;
        }} catch (e) {{}}
      }}
    }};

    apply();
    w.requestAnimationFrame(apply);
    w.setTimeout(apply, 60);
    w.setTimeout(apply, 180);
    w.setTimeout(apply, 420);
  }}

  restoreScroll();

  if (!w[installedKey]) {{
    w[installedKey] = true;
    const events = ['mousedown', 'touchstart', 'keydown', 'focusin', 'input', 'change', 'click'];
    for (const eventName of events) {{
      d.addEventListener(eventName, saveScroll, true);
    }}
    w.addEventListener('beforeunload', saveScroll, true);
    w.addEventListener('scroll', function () {{
      if (w.__mapeiaai_scroll_timer__) w.clearTimeout(w.__mapeiaai_scroll_timer__);
      w.__mapeiaai_scroll_timer__ = w.setTimeout(saveScroll, 120);
    }}, true);
  }}
}})();
</script>
        """,
        height=0,
        width=0,
    )


__all__ = ['inject_scroll_guard']
