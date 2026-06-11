# Centralizador de precificação de produtos

Arquivo responsável: `bling_app_zero/core/product_pricing_center.py`.

Este módulo reúne a calculadora de preço, normalização de valores, detecção de coluna de custo/preço e aplicação da precificação em DataFrames.

Módulos antigos devem continuar existindo apenas como compatibilidade e importar deste centralizador.

Pontos conectados:

- `bling_app_zero/core/pricing.py`
- `bling_app_zero/core/shared_price_calculator.py`
- `bling_app_zero/core/price_calculator_plugin.py`
- telas de UI que usam os módulos antigos
