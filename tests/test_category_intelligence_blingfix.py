from bling_app_zero.core.category_intelligence import suggest_category_for_product


def test_antena_tv_nao_vira_wifi():
    item = suggest_category_for_product(
        'Antena Digital Interna HDTV UHF para TV',
        description='Produto para recepção de sinal de televisão digital UHF/VHF.'
    )
    assert item.category == 'Antenas para TV'
    assert item.confidence >= 0.80


def test_antena_wifi_nao_vira_tv():
    item = suggest_category_for_product(
        'Antena WiFi 5dBi RP-SMA para roteador',
        description='Acessório wireless 2.4GHz para ampliar sinal de internet.'
    )
    assert item.category == 'Antenas Wi-Fi'
    assert item.confidence >= 0.80


def test_cabo_rede_nao_vira_usb():
    item = suggest_category_for_product(
        'Cabo de Rede RJ45 CAT6 Ethernet 2 metros',
        description='Patch cord LAN UTP para internet.'
    )
    assert item.category == 'Cabos de rede'
    assert item.confidence >= 0.80


def test_cabo_usb_nao_vira_rede():
    item = suggest_category_for_product(
        'Cabo USB Tipo C para celular Android',
        description='Cabo de dados e carregamento rápido para smartphone.'
    )
    assert item.category == 'Cabos USB e dados'
    assert item.confidence >= 0.80


def test_cabo_energia_nao_vira_audio():
    item = suggest_category_for_product(
        'Cabo de força tripolar 10A para fonte',
        description='Cabo de energia AC para tomada.'
    )
    assert item.category == 'Cabos de energia'
    assert item.confidence >= 0.80


def test_cabo_audio_nao_vira_energia():
    item = suggest_category_for_product(
        'Cabo P2 para RCA áudio estéreo',
        description='Cabo auxiliar para som e microfone.'
    )
    assert item.category == 'Cabos de áudio'
    assert item.confidence >= 0.80
