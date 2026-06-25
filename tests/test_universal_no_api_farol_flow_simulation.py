import pandas as pd

from bling_app_zero.core.final_output_engine import build_final_output
from bling_app_zero.ui.shared_mapping import FIXED_VALUE_PREFIX, _auto_bind_exact_green_matches


def test_fluxo_real_sem_api_modelo_origem_recursos_farol_download_final():
    """Simula o fluxo real sem API:

    1. Usuário anexa modelo final.
    2. Usuário anexa origem de dados.
    3. Recursos/regras são ligados.
    4. Mapeamento por IA fica desligado.
    5. Mapeamento por faróis/auto-green + escolhas manuais.
    6. Download final precisa conter exatamente o que foi mapeado.
    """
    model = pd.DataFrame(columns=[
        'Código',
        'Descrição',
        'Descrição curta',
        'Preço',
        'Preço promocional',
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
        'Altura',
        'Largura',
        'Profundidade',
    ])

    source = pd.DataFrame([
        {
            'Código': 'SKU-001',
            'Descrição': 'Mouse Sem Fio HP 200',
            'Descrição curta': ' Mouse óptico sem fio 1200 DPI ',
            'Preço': '49,90',
            'Preço promocional': '44,90',
            'Estoque': '2222',
            'Categoria do produto': 'Mouses',
            'Tags': 'informatica,mouse',
            'Grupo de Tags': 'Periféricos',
            'Código Pai': 'PAI-MOUSE',
            'GTIN/EAN': '7891910000197',
            'Imagens': 'https://cdn.exemplo.com/mouse1.jpg, https://cdn.exemplo.com/mouse1.jpg, https://cdn.exemplo.com/mouse2.jpg',
            'Unidade': '',
            'Unidade de medida': '',
            'Situação': '',
            'Condição': '',
            'Altura': '',
            'Largura': '',
            'Profundidade': '',
        },
        {
            'Código': 'SKU-002',
            'Descrição': 'Cabo HDMI 2m',
            'Descrição curta': 'Cabo HDMI 2 metros 4K',
            'Preço': '29,90',
            'Preço promocional': '',
            'Estoque': '111',
            'Categoria do produto': 'Cabos HDMI e vídeo',
            'Tags': 'cabo,hdmi',
            'Grupo de Tags': 'Cabos',
            'Código Pai': 'PAI-CABO',
            'GTIN/EAN': 'GTIN_INVALIDO_123',
            'Imagens': 'https://cdn.exemplo.com/cabo1.jpg; https://cdn.exemplo.com/cabo2.png; https://loja.exemplo.com/produto/cabo-hdmi',
            'Unidade': '',
            'Unidade de medida': '',
            'Situação': '',
            'Condição': '',
            'Altura': '',
            'Largura': '',
            'Profundidade': '',
        },
    ])

    # Simula o auto-green/faróis com IA desligada: cabeçalhos idênticos podem ser vinculados.
    mapping, applied = _auto_bind_exact_green_matches({}, list(model.columns), list(source.columns))
    assert applied == len(model.columns)

    # Simula escolhas manuais do usuário depois dos faróis.
    mapping['Situação'] = f'{FIXED_VALUE_PREFIX}Ativo'
    mapping['Condição'] = f'{FIXED_VALUE_PREFIX}Novo'
    # Usuário optou por manter Tags, Grupo de Tags e Código Pai mapeados.
    assert mapping['Tags'] == 'Tags'
    assert mapping['Grupo de Tags'] == 'Grupo de Tags'
    assert mapping['Código Pai'] == 'Código Pai'
    assert mapping['Categoria do produto'] == 'Categoria do produto'

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
        'apply_dimensions_default': True,
        'height_value': '2',
        'width_value': '11',
        'depth_value': '16',
        'overwrite_existing_fixed_values': False,
    }

    result = build_final_output(
        source,
        model,
        mapping,
        operation='universal',
        file_name='mapeiaai_planilha_final_mapeada.csv',
        run_smart_features=True,
        smart_rules_config=rules,
    )

    assert result.state.result.ok
    assert result.output is not None
    out = result.output

    # Contrato do modelo preservado: mesmas colunas e mesma ordem.
    assert list(out.columns) == list(model.columns)
    assert len(out) == len(source)

    # O download final precisa subir exatamente o que foi mapeado por faróis/manual.
    assert out['Código'].tolist() == ['SKU-001', 'SKU-002']
    assert out['Descrição'].tolist() == ['Mouse Sem Fio HP 200', 'Cabo HDMI 2m']
    assert out['Preço'].tolist() == ['49,90', '29,90']
    assert out['Preço promocional'].tolist() == ['44,90', '']
    assert out['Estoque'].tolist() == ['2222', '111']
    assert out['Categoria do produto'].tolist() == ['Mouses', 'Cabos HDMI e vídeo']
    assert out['Tags'].tolist() == ['informatica,mouse', 'cabo,hdmi']
    assert out['Grupo de Tags'].tolist() == ['Periféricos', 'Cabos']
    assert out['Código Pai'].tolist() == ['PAI-MOUSE', 'PAI-CABO']

    # Recursos inteligentes aplicados sem apagar decisão do usuário.
    assert out['Unidade'].tolist() == ['UN', 'UN']
    assert out['Unidade de medida'].tolist() == ['Centímetros', 'Centímetros']
    assert out['Situação'].tolist() == ['Ativo', 'Ativo']
    assert out['Condição'].tolist() == ['Novo', 'Novo']
    assert out['Altura'].tolist() == ['2', '2']
    assert out['Largura'].tolist() == ['11', '11']
    assert out['Profundidade'].tolist() == ['16', '16']

    # Imagens normalizadas/deduplicadas/limitadas e GTIN inválido limpo.
    assert out['Imagens'].iloc[0] == 'https://cdn.exemplo.com/mouse1.jpg|https://cdn.exemplo.com/mouse2.jpg'
    assert out['Imagens'].iloc[1] == 'https://cdn.exemplo.com/cabo1.jpg|https://cdn.exemplo.com/cabo2.png'
    assert out['GTIN/EAN'].tolist() == ['7891910000197', '']

    # Como categorização inteligente/alias de categoria não foi usado, o finalizador não altera a categoria manual.
    assert 'category_finalizer' not in (result.smart_rules_report or {})

    # CSV final físico gerado.
    assert result.csv_bytes
    csv_text = result.csv_bytes.decode('utf-8-sig')
    assert 'SKU-001' in csv_text
    assert 'informatica,mouse' in csv_text
    assert 'PAI-MOUSE' in csv_text
    assert 'Cabos HDMI e vídeo' in csv_text
