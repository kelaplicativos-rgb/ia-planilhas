# Fluxo congelado: Atualização de estoque por site

Este fluxo foi validado e aprovado em 2026-05-05.

## Status

CONGELADO.

## Regra

Não alterar este fluxo sem pedido explícito do usuário.

## Escopo congelado

- Atualização de estoque por busca de produtos por site.
- Uso do modelo Bling anexado como espelho do preview da origem, preview final e download.
- Captura de SKU/código.
- Captura do nome do produto.
- Captura do saldo/estoque.
- Captura do preço unitário quando disponível no site.
- Depósito manual no mapeamento.
- Sem precificação no fluxo de estoque.
- Remoção de opções duplicadas nos campos de seleção.

## Arquivos sensíveis

- app.py
- bling_app_zero/stable/stock_ui_patch.py
- bling_app_zero/stable/sitefix_patch.py
- bling_app_zero/stable/site_price_extractor.py
- bling_app_zero/stable/stock_flash_crawler.py
- bling_app_zero/stable/stable_app.py

## Snapshot de segurança

Branch criada para preservar o estado aprovado:

locked-fluxo-estoque-site-finalizado

Commit base do snapshot:

92a9f4a223c50d95507e3bcc4010fd0b19b700f8
