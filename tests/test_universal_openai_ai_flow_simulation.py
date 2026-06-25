import pandas as pd

from bling_app_zero.ai.ai_schema import AIResult
from bling_app_zero.ai import ai_openai_mapping_suggester as openai_mapper
from bling_app_zero.core.final_output_engine import build_final_output
from bling_app_zero.ui.shared_mapping import FIXED_VALUE_PREFIX


def test_fluxo_real_sem_api_com_ia_openai_mapeamento_download_final(monkeypatch):
    """Simula o fluxo real sem API usando a IA real de mapeamento.

    A chamada externa é isolada com monkeypatch para o teste não depender de chave/API,
    mas o caminho executado é o mesmo do motor OpenAI: suggest_mapping_with_openai
    -> sanitização por certeza máxima -> revisão do usuário -> build_final_output.
    """
    model = pd.DataFrame(columns=[
        'Código',
        'Descrição',
        'Descrição curta',
        'Preço',
        'Estoque',
        'Categoria do produto',
        'Tags',
        'Grupo de Tags',
        'Código Pai',
        'GTIN/EAN',
        'Imagens',
        'Unidade',
        'Unidade de medida',
        'Situação',
        'Condição',
    ])

    source = pd.DataFrame([
        {
            'ID Produto': 'SKU-IA-001',
            'Nome Comercial': 'Mouse Sem Fio HP 200',
            'Resumo Produto': 'Mouse óptico sem fio 1200 DPI',
            'Valor Venda': '49,90',
            'Qtd Disponível': '2222',
            'Departamento': 'Mouses',
            'Tags': 'informatica,mouse',
            'Grupo de Tags': 'Periféricos',
            'Código Pai': 'PAI-MOUSE-IA',
            'EAN': '7891910000197',
            'Fotos Produto': 'https://cdn.exemplo.com/mouse1.jpg, https://cdn.exemplo.com/mouse2.jpg',
            'Unidade': '',
            'Unidade de medida': '',
            'Situação': '',
            'Condição': '',
        },
        {
            'ID Produto': 'SKU-IA-002',
            'Nome Comercial': 'Cabo HDMI 2m',
            'Resumo Produto': 'Cabo HDMI 2 metros 4K',
            'Valor Venda': '29,90',
            'Qtd Disponível': '111',
            'Departamento': 'Cabos HDMI e vídeo',
            'Tags': 'cabo,hdmi',
            'Grupo de Tags': 'Cabos',
            'Código Pai': 'PAI-CABO-IA',
            'EAN': 'GTIN_INVALIDO_123',
            'Fotos Produto': 'https://cdn.exemplo.com/cabo1.jpg; https://cdn.exemplo.com/cabo2.png; https://loja.exemplo.com/produto/cabo-hdmi',
            'Unidade': '',
            'Unidade de medida': '',
            'Situação': '',
            'Condição': '',
        },
    ])

    def fake_call_openai_json(task, instructions, payload, *, settings=None):
        assert task == 'mapping_suggester_openai_max_certainty'
        assert 'source' in payload and 'target' in payload
        return AIResult(
            ok=True,
            task=task,
            data={
                'suggestions': [
                    {'target_column': 'Código', 'source_column': 'ID Produto', 'confidence': 1.0, 'reason': 'SKU/código confirmado por cabeçalho e amostras'},
                    {'target_column': 'Descrição', 'source_column': 'Nome Comercial', 'confidence': 1.0, 'reason': 'nome comercial é o título do produto'},
                    {'target_column': 'Descrição curta', 'source_column': 'Resumo Produto', 'confidence': 1.0, 'reason': 'resumo é descrição curta'},
                    {'target_column': 'Preço', 'source_column': 'Valor Venda', 'confidence': 1.0, 'reason': 'valor de venda com formato de preço'},
                    {'target_column': 'Estoque', 'source_column': 'Qtd Disponível', 'confidence': 1.0, 'reason': 'quantidade disponível é estoque'},
                    {'target_column': 'Categoria do produto', 'source_column': 'Departamento', 'confidence': 1.0, 'reason': 'departamento equivale à categoria'},
                    {'target_column': 'Tags', 'source_column': 'Tags', 'confidence': 1.0, 'reason': 'campo idêntico'},
                    {'target_column': 'Grupo de Tags', 'source_column': 'Grupo de Tags', 'confidence': 1.0, 'reason': 'campo idêntico'},
                    {'target_column': 'Código Pai', 'source_column': 'Código Pai', 'confidence': 1.0, 'reason': 'campo idêntico'},
                    {'target_column': 'GTIN/EAN', 'source_column': 'EAN', 'confidence': 1.0, 'reason': 'EAN é GTIN'},
                    {'target_column': 'Imagens', 'source_column': 'Fotos Produto', 'confidence': 1.0, 'reason': 'fotos são URLs de imagens'},
                ]
            },
        )

    monkeypatch.setattr(openai_mapper, 'ai_is_enabled', lambda: True)
    monkeypatch.setattr(openai_mapper, 'get_ai_settings', lambda: {'provider': 'openai', 'model': 'simulado'})
    monkeypatch.setattr(openai_mapper, 'call_openai_json', fake_call_openai_json)

    ai_result = openai_mapper.suggest_mapping_with_openai(source, model, operation='universal')
    assert ai_result.ok
    assert ai_result.data.get('engine') == 'openai_plus_semantic_content_local'

    # Simula a etapa de revisão do usuário após a IA: o usuário pode manter, corrigir
    # ou preencher qualquer campo. Isso garante que nenhuma coluna fica bloqueada.
    mapping = dict(ai_result.data.get('mapping') or {})
    mapping.update(
        {
            'Código': 'ID Produto',
            'Descrição': 'Nome Comercial',
            'Descrição curta': 'Resumo Produto',
            'Preço': 'Valor Venda',
            'Estoque': 'Qtd Disponível',
            'Categoria do produto': 'Departamento',
            'Tags': 'Tags',
            'Grupo de Tags': 'Grupo de Tags',
            'Código Pai': 'Código Pai',
            'GTIN/EAN': 'EAN',
            'Imagens': 'Fotos Produto',
            'Situação': f'{FIXED_VALUE_PREFIX}Ativo',
            'Condição': f'{FIXED_VALUE_PREFIX}Novo',
        }
    )

    rules = {
        'enabled': True,
        'clean_text': True,
        'remove_empty_markers': True,
        'normalize_images': True,
        'dedupe_images': True,
        'limit_images': True,
        'max_images': 2,
        'validate_gtin': True,
        'fill_category_aliases': False,
        'apply_unit_default': True,
        'unit_value': 'UN',
        'apply_measure_unit_default': True,
        'measure_unit_value': 'Centímetros',
        'apply_status_default': True,
        'status_value': 'Ativo',
        'apply_condition_default': True,
        'condition_value': 'Novo',
        'overwrite_existing_fixed_values': False,
    }

    result = build_final_output(
        source,
        model,
        mapping,
        operation='universal',
        file_name='mapeiaai_planilha_final_mapeada_ai.csv',
        run_smart_features=True,
        smart_rules_config=rules,
    )

    assert result.state.result.ok
    assert result.output is not None
    out = result.output

    assert list(out.columns) == list(model.columns)
    assert out['Código'].tolist() == ['SKU-IA-001', 'SKU-IA-002']
    assert out['Descrição'].tolist() == ['Mouse Sem Fio HP 200', 'Cabo HDMI 2m']
    assert out['Descrição curta'].tolist() == ['Mouse óptico sem fio 1200 DPI', 'Cabo HDMI 2 metros 4K']
    assert out['Preço'].tolist() == ['49,90', '29,90']
    assert out['Estoque'].tolist() == ['2222', '111']
    assert out['Categoria do produto'].tolist() == ['Mouses', 'Cabos HDMI e vídeo']
    assert out['Tags'].tolist() == ['informatica,mouse', 'cabo,hdmi']
    assert out['Grupo de Tags'].tolist() == ['Periféricos', 'Cabos']
    assert out['Código Pai'].tolist() == ['PAI-MOUSE-IA', 'PAI-CABO-IA']
    assert out['Unidade'].tolist() == ['UN', 'UN']
    assert out['Unidade de medida'].tolist() == ['Centímetros', 'Centímetros']
    assert out['Situação'].tolist() == ['Ativo', 'Ativo']
    assert out['Condição'].tolist() == ['Novo', 'Novo']
    assert out['Imagens'].iloc[0] == 'https://cdn.exemplo.com/mouse1.jpg|https://cdn.exemplo.com/mouse2.jpg'
    assert out['Imagens'].iloc[1] == 'https://cdn.exemplo.com/cabo1.jpg|https://cdn.exemplo.com/cabo2.png'
    assert out['GTIN/EAN'].tolist() == ['7891910000197', '']

    # Categoria definida pela origem/revisão do usuário deve seguir para o CSV sem ser trocada.
    assert 'category_finalizer' not in (result.smart_rules_report or {})

    csv_text = result.csv_bytes.decode('utf-8-sig')
    assert 'SKU-IA-001' in csv_text
    assert 'PAI-MOUSE-IA' in csv_text
    assert 'informatica,mouse' in csv_text
    assert 'Cabos HDMI e vídeo' in csv_text
