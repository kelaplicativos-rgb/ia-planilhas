import pandas as pd

from bling_app_zero.core.category_finalizer import finalize_categories_for_output


def _run(rows):
    df = pd.DataFrame(rows)
    out, report = finalize_categories_for_output(df, context='test')
    return out['Categoria do produto'].tolist(), report


def test_power_bank_nao_vira_carregador_celular():
    categories, report = _run([
        {
            'Descrição': 'Power Bank 20.000 Imenso IMS-6079',
            'Descrição Complementar': 'Bateria externa portatil 20000mAh para celular com USB.',
            'Categoria do produto': 'Carregadores para celular',
        },
    ])
    assert categories == ['Power banks']
    assert report['forced'] >= 1


def test_fone_tipo_c_nao_vira_cabo_usb():
    categories, _report = _run([
        {
            'Descrição': 'Fone de Ouvido Tipo C com Microfone',
            'Descrição Complementar': 'Fone intra auricular tipo c para celular android.',
            'Categoria do produto': 'Cabos USB e dados',
        },
    ])
    assert categories == ['Fones de ouvido']


def test_mouse_nao_vira_maquina_de_corte():
    categories, report = _run([
        {
            'Descrição': 'Mouse Sem Fio Recarregável KP-M611',
            'Descrição Complementar': 'Mouse bluetooth 5.1 recarregavel com DPI ajustavel.',
            'Categoria do produto': 'Máquinas para corte de cabelo',
        },
    ])
    assert categories == ['Mouses']
    assert report['guard_fixed'] >= 1


def test_pen_drive_nao_vira_cartao_memoria():
    categories, report = _run([
        {
            'Descrição': 'Pen Drive SanDisk Cruzer Blade 128GB',
            'Descrição Complementar': 'USB flash drive para armazenamento de arquivos.',
            'Categoria do produto': 'Cartões de memória',
        },
    ])
    assert categories == ['Pen drives']
    assert report['guard_fixed'] >= 1


def test_conversor_nao_vira_controle():
    categories, report = _run([
        {
            'Descrição': 'Conversor e Gravador Digital Tomate MCD-999',
            'Descrição Complementar': 'Conversor digital com receptor e gravador para TV.',
            'Categoria do produto': 'Controles para televisão',
        },
    ])
    assert categories == ['Conversores']
    assert report['guard_fixed'] >= 1


def test_repetidor_wifi_nao_vira_antena_tv():
    categories, report = _run([
        {
            'Descrição': 'Repetidor Wi-Fi RG-W62',
            'Descrição Complementar': 'Repetidor wireless para ampliar internet doméstica.',
            'Categoria do produto': 'Antenas para TV',
        },
    ])
    assert categories == ['Redes e internet']
    assert report['guard_fixed'] >= 1
