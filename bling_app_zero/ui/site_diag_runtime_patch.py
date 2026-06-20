from __future__ import annotations

import streamlit as st

from bling_app_zero.core.audit import add_audit_event

PATCH_KEY = 'site_diag_runtime_patch_installed_v1'
RESPONSIBLE_FILE = 'bling_app_zero/ui/site_diag_runtime_patch.py'


def install_site_diag_runtime_patch() -> None:
    if st.session_state.get(PATCH_KEY):
        return
    try:
        from bling_app_zero.core.site_diag_frames_min import sync_site_diag_frames
        from bling_app_zero.ui import site_progress

        original_append = getattr(site_progress, '_blingfix_original_append_site_progress_for_diag', None)
        if original_append is None:
            original_append = site_progress.append_site_progress
            setattr(site_progress, '_blingfix_original_append_site_progress_for_diag', original_append)

        def append_with_diag(payload: dict) -> None:
            original_append(payload)
            try:
                sync_site_diag_frames()
            except Exception:
                pass

        site_progress.append_site_progress = append_with_diag

        try:
            from bling_app_zero.adapters import streamlit_site_capture_adapter as adapter
            original_sync = getattr(adapter, '_blingfix_original_sync_site_capture_for_diag', None)
            if original_sync is None:
                original_sync = adapter.sync_site_capture_to_streamlit
                setattr(adapter, '_blingfix_original_sync_site_capture_for_diag', original_sync)

            def sync_with_diag(result, *, data=None) -> None:
                original_sync(result, data=data)
                try:
                    sync_site_diag_frames()
                except Exception:
                    pass

            adapter.sync_site_capture_to_streamlit = sync_with_diag
        except Exception:
            pass

        st.session_state[PATCH_KEY] = True
        add_audit_event('site_diag_runtime_patch_installed', area='SITE', status='OK', details={'responsible_file': RESPONSIBLE_FILE})
    except Exception as exc:
        add_audit_event('site_diag_runtime_patch_failed', area='SITE', status='AVISO', details={'error': str(exc)[:240], 'responsible_file': RESPONSIBLE_FILE})


__all__ = ['install_site_diag_runtime_patch']
