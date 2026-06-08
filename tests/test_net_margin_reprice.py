import pandas as pd

from bling_app_zero.core.shared_price_calculator import apply_shared_pricing


def test_preco_minimo_real_cobre_desconto_taxa_e_lucro():
    df = pd.DataFrame([{'Preco': '100,00'}])
    config = {
        'enabled': True,
        'quick_reprice_mode': 'net_margin',
        'quick_markup_percent': 10.0,
        'tax_percent': 6.0,
        'marketplace_fee_percent': 0.0,
        'promo_discount_percent': 4.0,
    }
    out = apply_shared_pricing(df, 'Preco', config=config)
    assert out.loc[0, 'Preço de venda'] == 'R$ 125,00'
    assert out.loc[0, 'Preço promocional'] == 'R$ 120,00'
