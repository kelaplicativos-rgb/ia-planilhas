from __future__ import annotations

import pandas as pd

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.source_upload_recovery import recover_uploaded_source_file

RESPONSIBLE_FILE = 'bling_app_zero/ui/source_upload_recovery_runtime.py'
PATCH_ATTR = '_mapeiaai_source_upload_recovery_patch_v1'


def _valid_frame(df: object) -> bool:
    return isinstance(df, pd.DataFrame) and len(df.columns) > 0


def install_source_upload_recovery_runtime() -> bool:
    """Evita que Origem de dados falhe com dataframe sem colunas.

    O leitor principal continua sendo usado primeiro. Este patch só entra quando
    o leitor devolve vazio/sem colunas ou lança exceção, especialmente em ZIPs
    contendo PDF, ZIP aninhado ou arquivos de texto fora do padrão.
    """
    try:
        from bling_app_zero.core import files as files_module
    except Exception as exc:
        add_audit_event(
            'source_upload_recovery_runtime_import_failed',
            area='ORIGEM',
            status='AVISO',
            details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE},
        )
        return False

    current = getattr(files_module, 'read_uploaded_file', None)
    if getattr(current, PATCH_ATTR, False):
        return False

    original = current

    def patched_read_uploaded_file(uploaded_file):
        try:
            df = original(uploaded_file) if callable(original) else pd.DataFrame()
        except Exception:
            df = pd.DataFrame()
        if _valid_frame(df):
            return df
        recovered = recover_uploaded_source_file(uploaded_file)
        if _valid_frame(recovered):
            add_audit_event(
                'source_upload_recovery_runtime_used',
                area='ORIGEM',
                status='OK',
                details={
                    'file_name': str(getattr(uploaded_file, 'name', '') or ''),
                    'rows': int(len(recovered)),
                    'columns': int(len(recovered.columns)),
                    'responsible_file': RESPONSIBLE_FILE,
                },
            )
            return recovered
        return df

    setattr(patched_read_uploaded_file, PATCH_ATTR, True)
    setattr(files_module, 'read_uploaded_file', patched_read_uploaded_file)

    # universal_flow importa a função diretamente; quando o módulo já está em
    # memória, também é necessário substituir a referência local dele.
    try:
        from bling_app_zero.ui import universal_flow
        setattr(universal_flow, 'read_uploaded_file', patched_read_uploaded_file)
    except Exception:
        pass

    add_audit_event(
        'source_upload_recovery_runtime_installed',
        area='ORIGEM',
        status='OK',
        details={
            'fallbacks': ['zip_pdf', 'zip_aninhado', 'arquivo_texto_sem_cabecalho', 'arquivo_desconhecido_com_texto'],
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return True


__all__ = ['install_source_upload_recovery_runtime']
