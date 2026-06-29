from __future__ import annotations

from functools import wraps

import pandas as pd

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/core/mhtml_capture_runtime.py'
PATCH_ATTR = '_mapeiaai_mhtml_capture_runtime_v1'


def _normalize_mhtml_bytes(data: bytes) -> bytes:
    raw = bytes(data or b'')
    return raw.replace(b'\r\r\n', b'\r\n').replace(b'\r\r', b'\r')


def install_mhtml_capture_runtime() -> bool:
    """Corrige MHTML salvo pelo Chrome/Playwright com quebras CR duplicadas.

    Alguns snapshots Page.captureSnapshot chegam com ``\r\r\n``. O parser de
    email entende isso como linha em branco entre cabeçalhos e não decodifica o
    trecho quoted-printable, fazendo o HTML virar texto bruto. Este runtime
    normaliza os bytes antes do extrator e antes do leitor importado em files.py.
    """
    try:
        from bling_app_zero.core import html_product_extractor as hpe
        from bling_app_zero.core import files as files_module
    except Exception as exc:
        add_audit_event(
            'mhtml_capture_runtime_import_failed',
            area='ORIGEM',
            status='AVISO',
            details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE},
        )
        return False

    installed = False

    current_extract = getattr(hpe, 'extract_html_parts_from_mhtml', None)
    if callable(current_extract) and not getattr(current_extract, PATCH_ATTR, False):
        original_extract = current_extract

        @wraps(original_extract)
        def patched_extract_html_parts_from_mhtml(data: bytes) -> list[str]:
            return original_extract(_normalize_mhtml_bytes(data))

        setattr(patched_extract_html_parts_from_mhtml, PATCH_ATTR, True)
        hpe.extract_html_parts_from_mhtml = patched_extract_html_parts_from_mhtml
        installed = True

    current_read = getattr(hpe, 'read_mhtml_product_bytes', None)
    if callable(current_read) and not getattr(current_read, PATCH_ATTR, False):
        original_read = current_read

        @wraps(original_read)
        def patched_read_mhtml_product_bytes(data: bytes) -> pd.DataFrame:
            return original_read(_normalize_mhtml_bytes(data))

        setattr(patched_read_mhtml_product_bytes, PATCH_ATTR, True)
        hpe.read_mhtml_product_bytes = patched_read_mhtml_product_bytes
        files_module.read_mhtml_product_bytes = patched_read_mhtml_product_bytes
        installed = True

    add_audit_event(
        'mhtml_capture_runtime_installed',
        area='ORIGEM',
        status='OK' if installed else 'INFO',
        details={
            'normalizes_crlf': True,
            'patches_files_module_alias': True,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return installed


__all__ = ['install_mhtml_capture_runtime']
