from __future__ import annotations

from typing import Any

RESPONSIBLE_FILE = 'bling_app_zero/ui/critical_mapping_visual_patch.py'


def _audit(event: str, *, status: str = 'OK', details: dict[str, Any] | None = None) -> None:
    try:
        from bling_app_zero.core.audit import add_audit_event
        add_audit_event(event, area='UNIVERSAL', status=status, details={**(details or {}), 'responsible_file': RESPONSIBLE_FILE})
    except Exception:
        pass


def install() -> None:
    try:
        from bling_app_zero.ui import shared_mapping
    except Exception as exc:
        _audit('critical_mapping_visual_patch_import_failed', status='AVISO', details={'error': str(exc)[:220]})
        return

    if getattr(shared_mapping, '_mapeiaai_critical_mapping_visual_patched', False):
        return

    # BLINGFIX: não existe mais coluna "crítica" que bloqueia mapeamento.
    # Categoria, Tags, Grupo de tags, Código Pai e qualquer outro campo seguem a
    # mesma regra: auto-green pode sugerir/preencher campos idênticos e o usuário
    # pode desfazer, deixar vazio, escolher outra coluna ou escrever valor fixo.
    def _render_bling_import_guard_clean(*args: Any, **kwargs: Any) -> None:
        return None

    shared_mapping._render_bling_import_guard = _render_bling_import_guard_clean
    shared_mapping._mapeiaai_critical_mapping_visual_patched = True
    _audit('critical_mapping_visual_patch_installed', details={'visual': 'neutral', 'auto_bind_all_fields': True})


__all__ = ['install']
