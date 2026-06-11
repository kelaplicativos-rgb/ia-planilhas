"""Interfaces Streamlit do BLINGCREATOR."""

try:
    from bling_app_zero.ui.live_operation_runtime_patch import install_live_operation_runtime_patch
    install_live_operation_runtime_patch()
except Exception:
    pass

try:
    from bling_app_zero.ui.download_estoque_runtime_fix import install_download_estoque_runtime_fix
    install_download_estoque_runtime_fix()
except Exception:
    pass

__all__ = []
