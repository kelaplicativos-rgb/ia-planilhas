from __future__ import annotations

import json
import zipfile
from io import BytesIO
from typing import Iterable

from bling_app_zero.core.protected_supplier_collectors import COLLECTOR_SCRIPT, README_TEMPLATE, RUN_BAT, build_provider_config

RESPONSIBLE_FILE = 'bling_app_zero/core/protected_supplier_contract_collectors.py'


def _clean_columns(columns: Iterable[object]) -> list[str]:
    out: list[str] = []
    for column in columns or []:
        text = str(column or '').strip()
        if text and text not in out:
            out.append(text)
    return out


def build_contract_collector_zip(
    provider_key: str,
    *,
    start_url: str = '',
    pages: int | None = None,
    capture_format: str = '',
    requested_columns: Iterable[object] | None = None,
) -> bytes:
    columns = _clean_columns(requested_columns or [])
    config = build_provider_config(provider_key, start_url=start_url, pages=pages, capture_format=capture_format)
    config['schema_version'] = 'mapeiaai_protected_supplier_collector_v2_contract_columns'
    config['requested_columns'] = columns
    config['requested_columns_count'] = len(columns)
    config['collector_rule'] = 'capturar tudo que estiver disponivel na origem para as colunas solicitadas pelo modelo, sem criar colunas finais fora do modelo'

    readme = README_TEMPLATE.format(
        provider_name=config['provider_name'],
        start_url=config['start_url'],
        pages=config['pages'],
        format=config['format'],
    )
    if columns:
        readme += '\nContrato de colunas do modelo anexado:\n'
        readme += f'- {len(columns)} coluna(s) solicitada(s).\n'
        readme += '- O MapeiaAI vai procurar, no HTML/MHTML capturado, dados disponíveis para essas colunas.\n'
        readme += '- A saída final continua travada exatamente nas colunas do modelo.\n'

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('coletor_fornecedor_protegido.py', COLLECTOR_SCRIPT)
        zf.writestr('RUN_COLETOR.bat', RUN_BAT)
        zf.writestr('provider_config.json', json.dumps(config, ensure_ascii=False, indent=2))
        zf.writestr('README.txt', readme)
    return buffer.getvalue()


__all__ = ['build_contract_collector_zip']
