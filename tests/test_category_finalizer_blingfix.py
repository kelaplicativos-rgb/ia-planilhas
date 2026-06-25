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
        {
            'Descrição': 'Carregador Portatil 10.000 22.5W',
            'Descrição Complementar': 'Power bank 10000mAh bateria externa para smartphone.',
            'Categoria do produto': 'Carregadores para celular',
        },
    ])
    assert categories == ['Power banks', 'Power banks']
    assert report['forced'] >= 2


def test_pilha_mah_nao_vira_power_bank():
    categories, _report = _run([
        {
            'Descrição': 'Pilhas Recarregáveis AA 2700mAh',
            'Descrição Complementar': 'Kit com pilhas AA recarregaveis 2700mAh.',
            'Categoria do produto': 'Pilhas e baterias',
        },
    ])
    assert categories == ['Pilhas e baterias']


def test_radio_nao_vira_caixa_de_som():
    categories, _report = _run([
        {
            'Descrição': 'Radio Toca CD Lenoxx',
            'Descrição Complementar': 'Radio portatil AM FM com antena telescopica e entrada USB.',
            'Categoria do produto': 'Caixas de som',
        },
        {
            'Descrição': 'Radio AM/FM Kapbom',
            'Descrição Complementar': 'Radio am fm recarregavel com sintonia e antena.',
            'Categoria do produto': 'Caixas de som',
        },
    ])
    assert categories == ['Rádios AM e FM', 'Rádios AM e FM']


def test_radio_com_entrada_fone_nao_vira_fone():
    categories, _report = _run([
        {
            'Descrição': 'Radio AM/FM com entrada de fone',
            'Descrição Complementar': 'Radio portatil com antena telescopica, entrada para fone e USB.',
            'Categoria do produto': 'Fones de ouvido',
        },
    ])
    assert categories == ['Rádios AM e FM']


def test_caixa_de_som_com_microfone_nao_vira_microfone():
    categories, _report = _run([
        {
            'Descrição': 'Caixa de Som Portátil 20W com Microfones',
            'Descrição Complementar': 'Caixa de som amplificada bluetooth com microfone incluso.',
            'Categoria do produto': 'Microfones',
        },
    ])
    assert categories == ['Caixas de som']


def test_cabo_rede_nao_vira_categoria_errada():
    categories, _report = _run([
        {
            'Descrição': 'Cabo de Rede 5M Hmaston CR-5',
            'Descrição Complementar': 'Cabo RJ-45 CAT6 Ethernet LAN para internet.',
            'Categoria do produto': 'Projetores',
        },
    ])
    assert categories == ['Cabos de rede']


def test_fone_nao_vira_mouse():
    categories, _report = _run([
        {
            'Descrição': 'Fone de Ouvido Intra-auricular',
            'Descrição Complementar': 'Fone intra auricular com microfone para celular.',
            'Categoria do produto': 'Mouses',
        },
    ])
    assert categories == ['Fones de ouvido']


def test_fone_curto_nao_vira_microfone():
    categories, _report = _run([
        {
            'Descrição': 'Fone Gamer com Microfone Integrado',
            'Descrição Complementar': 'Fone bluetooth gamer com microfone para chamadas.',
            'Categoria do produto': 'Microfones',
        },
    ])
    assert categories == ['Fones de ouvido']


def test_antena_wifi_nao_fica_generica():
    categories, _report = _run([
        {
            'Descrição': 'Adaptador Wireless USB com Antena Wi-Fi',
            'Descrição Complementar': 'Adaptador wireless para internet com antena wifi 5dBi.',
            'Categoria do produto': 'Antenas',
        },
    ])
    assert categories == ['Antenas Wi-Fi']


def test_fone_tipo_c_nao_vira_cabo_usb():
    categories, _report = _run([
        {
            'Descrição': 'Fone de Ouvido Tipo C com Microfone',
            'Descrição Complementar': 'Fone intra auricular tipo c para celular android.',
            'Categoria do produto': 'Cabos USB e dados',
        },
    ])
    assert categories == ['Fones de ouvido']


def test_microfone_com_cabo_nao_vira_cabo_audio():
    categories, _report = _run([
        {
            'Descrição': 'Microfone de Lapela P2 para Celular',
            'Descrição Complementar': 'Microfone lapela com cabo p2 para gravação de voz.',
            'Categoria do produto': 'Cabos de áudio',
        },
    ])
    assert categories == ['Microfones']


def test_carregador_tipo_c_nao_vira_cabo_usb():
    categories, _report = _run([
        {
            'Descrição': 'Carregador Turbo Tipo C 30W',
            'Descrição Complementar': 'Fonte carregador de tomada usb c para celular.',
            'Categoria do produto': 'Cabos USB e dados',
        },
    ])
    assert categories == ['Carregadores para celular']


def test_cabo_tipo_c_continua_cabo_usb():
    categories, _report = _run([
        {
            'Descrição': 'Cabo Tipo C para iPhone 1 Metro',
            'Descrição Complementar': 'Cabo de dados tipo c lightning para celular.',
            'Categoria do produto': '',
        },
    ])
    assert categories == ['Cabos USB e dados']


def test_rca_nao_bate_dentro_de_palavra_reforcado():
    categories, _report = _run([
        {
            'Descrição': 'Cabo reforcado USB 2 metros',
            'Descrição Complementar': 'Cabo usb tipo c para dados.',
            'Categoria do produto': '',
        },
    ])
    assert categories == ['Cabos USB e dados']
