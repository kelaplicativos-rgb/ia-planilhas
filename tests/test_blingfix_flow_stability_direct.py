from pathlib import Path


def test_app_refreshes_runtime_patches_once_per_policy():
    app = Path('app.py').read_text(encoding='utf-8')
    assert 'RUNTIME_PATCH_REFRESH_MARKER_KEY' in app
    assert 'RUNTIME_PATCH_REFRESH_POLICY_VERSION' in app
    assert 'blingfix_runtime_patch_session_keys_refreshed_once_per_version' in app
    assert "st.session_state.get(RUNTIME_PATCH_REFRESH_MARKER_KEY) == RUNTIME_PATCH_REFRESH_POLICY_VERSION" in app


def test_universal_flow_uses_official_mapping_auto_toggle():
    flow = Path('bling_app_zero/ui/universal_flow.py').read_text(encoding='utf-8')
    assert 'render_mapping_auto_decision_toggle' in flow
    assert "label='Mapeamento automático'" in flow
    assert "default=False" in flow
    assert "mapeiaai_universal_toggle_mapping_auto" in flow
    assert "mapping_auto_user_decided=True" in flow


def test_mapping_auto_decision_is_audited():
    decision = Path('bling_app_zero/ui/mapping_auto_decision.py').read_text(encoding='utf-8')
    assert 'mapping_auto_toggle_rendered' in decision
    assert 'manual_mode_means_blank_mapping' in decision
    assert '_audit_mapping_toggle' in decision
