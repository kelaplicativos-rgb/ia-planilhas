# BLINGFIX SITE CAPTURE - 2026-06-16

## Problema encontrado

A busca por produtos por site encontrava links, mas não finalizava bem em lotes grandes.
No diagnóstico analisado, a captura encontrou centenas de URLs, porém pausava por limite técnico antes de transformar todos os links em produtos completos.

## Causas principais

1. `DISCOVERY_BUDGET_SECONDS` estava em 60 segundos.
2. `PRODUCT_READ_BUDGET_SECONDS` estava em 150 segundos.
3. O limite total técnico do Streamlit estava em 180 segundos.
4. O reforço final de nome, descrição e imagens parava nos primeiros 160/180 produtos.
5. O fallback Playwright podia ficar pesado se usado produto por produto.

## Correções aplicadas

### `bling_app_zero/engines/fast_site_scraper/constants.py`

- `STREAMLIT_HARD_BUDGET_SECONDS`: 180 -> 330
- `DISCOVERY_BUDGET_SECONDS`: 60 -> 120
- `PRODUCT_READ_BUDGET_SECONDS`: 150 -> 260
- Timeouts seguros de captura ampliados para 240/300 segundos.

Objetivo: dar tempo real para descoberta + leitura em sites com 300 a 1200 produtos, sem considerar pausa técnica como falha comum.

### `bling_app_zero/pipelines/site_pipeline_blingfix.py`

- `MAX_ROWS`: 180 -> 1200
- Reforço de nome, descrição e imagens agora roda em lote paralelo com `ThreadPoolExecutor`.
- Playwright ficou limitado a poucos casos finais sem imagem (`PLAYWRIGHT_FALLBACK_MAX = 12`) para evitar travamento.
- O progresso agora informa quantas páginas foram conferidas e quantos produtos foram reforçados.
- Auditoria registra linhas candidatas, linhas reforçadas, workers e fallback usado.

## Resultado esperado

- A busca por site deve capturar melhor lojas grandes como Mega Center.
- Produtos depois da linha 180 não devem mais ficar sem reforço por corte fixo.
- A captura deve ter mais chance de terminar antes de entrar em retomada.
- Quando precisar pausar, o checkpoint continua sendo preservado.

## Próximo ajuste recomendado

Criar botão visual de retomada manual dos pendentes e um status final colorido:

- Verde: captura concluída e salva.
- Amarelo: parcial preservado com pendentes.
- Vermelho: falha real.

Também é recomendado melhorar o API Finder para detectar endpoints reais da plataforma usada pelo site, reduzindo dependência de HTML produto por produto.
