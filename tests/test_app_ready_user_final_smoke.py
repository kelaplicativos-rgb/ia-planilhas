import importlib

import pandas as pd

from bling_app_zero.core.final_output_engine import build_final_output
from bling_app_zero.ui.shared_mapping import FIXED_VALUE_PREFIX, _auto_bind_exact_green_matches


CRITICAL_RUNTIME_MODULES = [
    'app',
    'bling_app_zero.ui.home',
    'bling_app_zero.ui.home_official',
    'bling_app_zero.ui.home_router_v2',
    'bling_app_zero.ui.universal_flow',
    'bling_app_zero.ui.shared_mapping',
    'bling_app_zero.ui.shared_final_csv',
    'bling_app_zero.ui.mapping_locked_fields_runtime',
    'bling_app_zero.ui.critical_mapping_visual_patch',
    'bling_app_zero.core.final_output_engine',
    'bling_app_zero.core.final_csv_exporter',
    'bling_app_zero.core.universal_smart_rules',
    'bling_app_zero.universal.output_builder',
    'bling_app_zero.ai.ai_mapping_suggester',
    'bling_app_zero.ai.ai_openai_mapping_suggester',
]


def test_app_pronto_usuario_final_importa_modulos_criticos():
    """Smoke test de prontidão: falha se algum módulo essencial quebra no import.

    Não clica no Streamlit, mas captura erros que derrubariam o app antes/depois da Home:
    import quebrado, arquivo ausente, símbolo renomeado, dependência ausente ou patch incompatível.
    """
    imported = []
    for module_name in CRITICAL_RUNTIME_MODULES:
        module = importlib.import_module(module_name)
        imported.append(module.__name__)
    assert imported == CRITICAL_RUNTIME_MODULES
    assert callable(getattr(importlib.import_module('app'), 'main'))


def test_app_pronto_usuario_final_fluxo_universal_sem_api_download_csv():
    """Simula jornada mínima de usuário final no fluxo sem API.

    Cobre: modelo anexado, origem anexada, auto-green/faróis, valor fixo,
    recursos inteligentes, montagem final e CSV físico pronto para download.
    """
    model = pd.DataFrame(columns=[
        'Código',
        'Descrição',
        'Preço',
        'Estoque',
        'Categoria do produto',
        'Tags',
        'Código Pai',
        'GTIN/EAN',
        'Imagens',
        'Situação',
    ])
    source = pd.DataFrame([
        {
            'Código': 'SKU-READY-1',
            'Descrição': 'Mouse Sem Fio HP 200',
            'Preço': '49,90',
            'Estoque': '2222',
            'Categoria do produto': 'Mouses',
            'Tags': 'informatica,mouse',
            'Código Pai': 'PAI-READY-1',
            'GTIN/EAN': '7891910000197',
            'Imagens': 'https://cdn.exemplo.com/mouse1.jpg, https://cdn.exemplo.com/mouse2.jpg',
            'Situação': '',
        },
        {
            'Código': 'SKU-READY-2',
            'Descrição': 'Cabo HDMI 2m',
            'Preço': '29,90',
            'Estoque': '111',
            'Categoria do produto': 'Cabos HDMI e vídeo',
            'Tags': 'cabo,hdmi',
            'Código Pai': 'PAI-READY-2',
            'GTIN/EAN': 'GTIN_INVALIDO',
            'Imagens': 'https://cdn.exemplo.com/cabo1.jpg; https://cdn.exemplo.com/cabo2.png; https://loja.exemplo.com/produto/cabo-hdmi',
            'Situação': '',
        },
    ])

    mapping, applied = _auto_bind_exact_green_matches({}, list(model.columns), list(source.columns))
    assert applied == len(model.columns)
    mapping['Situação'] = f'{FIXED_VALUE_PREFIX}Ativo'

    result = build_final_output(
        source,
        model,
        mapping,
        operation='universal',
        file_name='mapeiaai_ready_smoke.csv',
        run_smart_features=True,
        smart_rules_config={
            'enabled': True,
            'clean_text': True,
            'remove_empty_markers': True,
            'normalize_images': True,
            'dedupe_images': True,
            'limit_images': True,
            'max_images': 2,
            'validate_gtin': True,
            'fill_category_aliases': False,
            'overwrite_existing_fixed_values': False,
        },
    )

    assert result.state.result.ok
    assert result.output is not None
    out = result.output
    assert list(out.columns) == list(model.columns)
    assert out['Código'].tolist() == ['SKU-READY-1', 'SKU-READY-2']
    assert out['Categoria do produto'].tolist() == ['Mouses', 'Cabos HDMI e vídeo']
    assert out['Tags'].tolist() == ['informatica,mouse', 'cabo,hdmi']
    assert out['Código Pai'].tolist() == ['PAI-READY-1', 'PAI-READY-2']
    assert out['Situação'].tolist() == ['Ativo', 'Ativo']
    assert out['GTIN/EAN'].tolist() == ['7891910000197', '']
    assert out['Imagens'].iloc[1] == 'https://cdn.exemplo.com/cabo1.jpg|https://cdn.exemplo.com/cabo2.png'

    csv_text = result.csv_bytes.decode('utf-8-sig')
    assert 'SKU-READY-1' in csv_text
    assert 'PAI-READY-1' in csv_text
    assert 'informatica,mouse' in csv_text
    assert 'Cabos HDMI e vídeo' in csv_text
