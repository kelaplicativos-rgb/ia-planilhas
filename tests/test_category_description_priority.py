from bling_app_zero.core.category_intelligence import suggest_category_for_product


def test_descricao_radio_vence_titulo_generico():
    item = suggest_category_for_product(
        'Caixa Bluetooth Super Bass',
        description='Produto principal: radio portatil am fm com antena telescopica, entrada usb e bateria recarregavel.'
    )
    assert item.category == 'Rádios AM e FM'
    assert 'descrição' in item.reason


def test_descricao_caixa_de_som_vence_radio_como_recurso():
    item = suggest_category_for_product(
        'Radio FM Bluetooth USB',
        description='Produto principal: caixa de som amplificada com funcao radio fm, entrada usb e cartao de memoria.'
    )
    assert item.category == 'Caixas de som'
    assert 'descrição' in item.reason


def test_descricao_tecnica_vence_titulo_cabo_generico():
    item = suggest_category_for_product(
        'Cabo reforcado premium 2 metros',
        description='Ficha tecnica: cabo rj45 cat6 ethernet lan utp para rede e internet.'
    )
    assert item.category == 'Cabos de rede'
    assert 'descrição' in item.reason
