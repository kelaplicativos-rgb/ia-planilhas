import pandas as pd

from bling_app_zero.core.category_finalizer import finalize_categories_for_output
from bling_app_zero.core.category_guard import validate_category


def _final_category(description, category, details=''):
    df = pd.DataFrame([
        {
            'Descrição': description,
            'Descrição Complementar': details,
            'Categoria do produto': category,
        }
    ])
    out, report = finalize_categories_for_output(df, context='test_category_guard_critical_cases')
    return out['Categoria do produto'].iloc[0], report


def test_guard_bloqueia_mouse_em_maquina_corte():
    category, report = _final_category(
        'Mouse Sem Fio Recarregável KP-M611',
        'Máquinas para corte de cabelo',
        'Mouse bluetooth 5.1 recarregavel com DPI ajustavel.',
    )
    assert category == 'Mouses'
    assert report['guard_fixed'] >= 1


def test_guard_bloqueia_pen_drive_em_cartao_memoria():
    category, report = _final_category(
        'Pen Drive SanDisk Cruzer Blade 128GB',
        'Cartões de memória',
        'USB flash drive para armazenamento de arquivos.',
    )
    assert category == 'Pen drives'
    assert report['guard_fixed'] >= 1


def test_guard_bloqueia_conversor_em_controle():
    category, report = _final_category(
        'Conversor e Gravador Digital Tomate MCD-999',
        'Controles para televisão',
        'Conversor digital com receptor e gravador para TV.',
    )
    assert category == 'Conversores'
    assert report['guard_fixed'] >= 1


def test_guard_bloqueia_controle_em_conversor():
    category, report = _final_category(
        'Controle para Tv Aoc FBG-7099',
        'Conversores',
        'Controle remoto compatível com TVs AOC.',
    )
    assert category == 'Controles para televisão'
    assert report['guard_fixed'] >= 1


def test_guard_bloqueia_repetidor_em_antena_tv():
    category, report = _final_category(
        'Repetidor Wi-Fi RG-W62',
        'Antenas para TV',
        'Repetidor wireless para ampliar internet doméstica.',
    )
    assert category == 'Redes e internet'
    assert report['guard_fixed'] >= 1


def test_validate_category_retorna_blocked_quando_categoria_incompativel():
    decision = validate_category(
        title='Mouse Bluetooth Recarregável',
        description='Mouse sem fio com ajuste de DPI.',
        current_category='Máquinas para corte de cabelo',
    )
    assert decision.status == 'CATEGORY_BLOCKED'
    assert decision.accepted_category == 'Mouses'
