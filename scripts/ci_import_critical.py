from __future__ import annotations

import importlib
import pathlib
import traceback

MODULES = [
    'app',
    'bling_app_zero.ui.home',
    'bling_app_zero.ui.home_wizard_v2',
    'bling_app_zero.ui.rules_center_step',
    'bling_app_zero.ui.ai_real_advanced_panel',
    'bling_app_zero.core.flow_spine',
    'bling_app_zero.core.wizard_state',
    'bling_app_zero.core.wizard_engine',
    'bling_app_zero.features_runtime.registry',
    'bling_app_zero.ui.home_shared',
    'bling_app_zero.ui.smart_upload',
    'bling_app_zero.ui.cadastro_panel',
    'bling_app_zero.ui.estoque_panel',
    'bling_app_zero.ui.site_panel',
    'bling_app_zero.pipelines.cadastro_pipeline',
    'bling_app_zero.pipelines.estoque_pipeline',
    'bling_app_zero.pipelines.site_pipeline',
    'bling_app_zero.engines.cadastro_engine',
    'bling_app_zero.engines.estoque_engine',
    'bling_app_zero.engines.site_cadastro_engine',
    'bling_app_zero.engines.site_estoque_engine',
    'bling_app_zero.engines.flash_amplo_engine',
    'bling_app_zero.core.column_contract',
    'bling_app_zero.core.exporter',
    'bling_app_zero.core.files',
    'bling_app_zero.core.validators',
]

REPORT = pathlib.Path('ci_import_failure.txt')


def main() -> int:
    lines: list[str] = []
    for module in MODULES:
        print(f'BLING_IMPORT_START::{module}', flush=True)
        try:
            importlib.import_module(module)
        except Exception as exc:
            tb = traceback.format_exc()
            text = '\n'.join([
                f'BLING_IMPORT_FAIL::{module}',
                f'{type(exc).__name__}: {exc}',
                tb,
            ])
            print(text, flush=True)
            REPORT.write_text(text, encoding='utf-8')
            return 1
        lines.append(f'OK import: {module}')
        print(f'BLING_IMPORT_OK::{module}', flush=True)
    REPORT.write_text('\n'.join(lines), encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
