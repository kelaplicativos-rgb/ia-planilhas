import pandas as pd

from bling_app_zero.core.critical_empty_fields_guard import is_manual_choice_target, strip_critical_empty_mappings
from bling_app_zero.core.final_output_engine import build_final_output


def test_campos_sensiveis_exigem_escolha_manual_sem_forcar_vazio():
    assert is_manual_choice_target('Tags')
    assert is_manual_choice_target('Código Pai')

    mapping, report = strip_critical_empty_mappings({
        'Código': 'SKU',
        'Tags': 'Tags',
        'Código Pai': 'Código Pai',
    })

    assert mapping['Código'] == 'SKU'
    assert mapping['Tags'] == 'Tags'
    assert mapping['Código Pai'] == 'Código Pai'
    assert report == []


def test_download_final_respeita_deixar_vazio():
    source = pd.DataFrame([
        {'SKU': 'ABC-1', 'Tags': 'tag-valida', 'Código Pai': 'PAI-1'},
        {'SKU': 'ABC-2', 'Tags': 'outra-tag', 'Código Pai': 'PAI-2'},
    ])
    model = pd.DataFrame(columns=['Código', 'Tags', 'Código Pai'])
    mapping = {
        'Código': 'SKU',
        'Tags': '',
        'Código Pai': '',
    }

    result = build_final_output(source, model, mapping, run_smart_features=False)

    assert result.state.result.ok
    assert result.output is not None
    assert result.output['Código'].tolist() == ['ABC-1', 'ABC-2']
    assert result.output['Tags'].tolist() == ['', '']
    assert result.output['Código Pai'].tolist() == ['', '']


def test_download_final_respeita_usuario_quando_mapeia_tags_e_codigo_pai():
    source = pd.DataFrame([
        {'SKU': 'ABC-1', 'Tags': 'tag-valida', 'Código Pai': 'PAI-1'},
        {'SKU': 'ABC-2', 'Tags': 'outra-tag', 'Código Pai': 'PAI-2'},
    ])
    model = pd.DataFrame(columns=['Código', 'Tags', 'Código Pai'])
    mapping = {
        'Código': 'SKU',
        'Tags': 'Tags',
        'Código Pai': 'Código Pai',
    }

    result = build_final_output(source, model, mapping, run_smart_features=False)

    assert result.state.result.ok
    assert result.output is not None
    assert result.output['Código'].tolist() == ['ABC-1', 'ABC-2']
    assert result.output['Tags'].tolist() == ['tag-valida', 'outra-tag']
    assert result.output['Código Pai'].tolist() == ['PAI-1', 'PAI-2']


def test_download_final_respeita_categoria_mapeada_sem_regras_inteligentes():
    source = pd.DataFrame([
        {'Produto': 'Mouse Sem Fio', 'Categoria origem': 'Minha Categoria Manual'},
    ])
    model = pd.DataFrame(columns=['Descrição', 'Categoria do produto'])
    mapping = {
        'Descrição': 'Produto',
        'Categoria do produto': 'Categoria origem',
    }

    result = build_final_output(source, model, mapping, run_smart_features=False)

    assert result.state.result.ok
    assert result.output is not None
    assert result.output['Descrição'].tolist() == ['Mouse Sem Fio']
    assert result.output['Categoria do produto'].tolist() == ['Minha Categoria Manual']
    assert 'category_finalizer' not in (result.smart_rules_report or {})


def test_download_final_respeita_categoria_vazia_sem_regras_inteligentes():
    source = pd.DataFrame([
        {'Produto': 'Mouse Sem Fio', 'Categoria origem': 'Mouses'},
    ])
    model = pd.DataFrame(columns=['Descrição', 'Categoria do produto'])
    mapping = {
        'Descrição': 'Produto',
        'Categoria do produto': '',
    }

    result = build_final_output(source, model, mapping, run_smart_features=False)

    assert result.state.result.ok
    assert result.output is not None
    assert result.output['Categoria do produto'].tolist() == ['']
