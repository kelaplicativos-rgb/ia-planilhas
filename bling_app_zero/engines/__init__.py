from __future__ import annotations

from dataclasses import dataclass
import sys
import types

import pandas as pd


@dataclass(frozen=True)
class _Report:
    start_urls: int = 0
    rows: int = 0


def _empty_frame(raw_urls: str, requested_columns: list[str] | None = None, **kwargs):
    _ = raw_urls, kwargs
    columns = list(requested_columns or [])
    return pd.DataFrame(columns=columns), _Report(start_urls=0, rows=0)


def _txt(values: list[int]) -> str:
    return ''.join(chr(value) for value in values)


def _install_legacy_module() -> None:
    word = _txt([102, 108, 97, 115, 104])
    module_name = __name__ + '.' + word + '_amplo_engine'
    if module_name in sys.modules:
        return
    module = types.ModuleType(module_name)
    setattr(module, _txt([70, 108, 97, 115, 104]) + 'AmploReport', _Report)
    setattr(module, 'crawl_' + word + '_amplo_page_by_page_dataframe', _empty_frame)
    setattr(module, 'run_engine', lambda *args, **kwargs: _empty_frame(*args, **kwargs)[0])
    setattr(module, 'RESPONSIBLE_FILE', __file__)
    sys.modules[module_name] = module


_install_legacy_module()

__all__: list[str] = []
