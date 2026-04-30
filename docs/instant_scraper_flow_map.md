# Mapa manual do modulo Instant Scraper

Este documento define os fluxos necessarios para desenvolver o modulo de busca por site no padrao parecido com extensoes de extracao de dados, priorizando DOM/HTML e reduzindo dependencia de browser no Streamlit Cloud.

## Objetivo do modulo

Transformar uma URL de fornecedor ou categoria em uma tabela confiavel para o fluxo Bling:

1. Origem dos dados
2. Precificacao
3. Mapeamento
4. Preview final
5. Download CSV ou envio Bling

## Principio tecnico

O fluxo principal deve ser estilo Instant Data Scraper:

- Carregar HTML disponivel por HTTP.
- Detectar tabelas e blocos repetidos no DOM.
- Gerar candidatos com score.
- Permitir preview e escolha manual quando houver mais de um candidato.
- Normalizar dados para campos de produto.
- Seguir para mapeamento Bling.

Playwright deve ser fallback opcional e nunca requisito para o app funcionar.

## Fluxo 1 - Entrada da URL

Estado inicial:

- usuario informa URL do fornecedor, categoria ou produto.
- sistema normaliza URL.
- se URL mudou, limpa cache, candidatos e resultado anterior.

Entradas:

- `site_url_input`
- `site_url_origem`
- `click_html`
- `instant_candidates`
- `df_origem`

Saidas esperadas:

- URL valida normalizada.
- estado pronto para detectar estruturas.

## Fluxo 2 - Captura HTML

Prioridade:

1. HTTP com cache controlavel.
2. Se HTML vier grande, nao descartar por falso anti-bot.
3. Se HTML vier vazio, registrar diagnostico.
4. Browser opcional apenas como fallback.

Estados:

- `site_busca_status=carregando_html`
- `site_busca_erro`
- `site_runtime_modo`
- `site_runtime_browser_opcional`

Saidas:

- HTML bruto.
- diagnostico de status HTTP, tamanho e motivo.

## Fluxo 3 - Deteccao estilo Instant DOM

Motor principal:

- `instant_dom_engine.instant_extract`

Responsabilidades:

- detectar tabelas HTML.
- detectar cards/listas repetidas.
- extrair nome, preco, imagem, link, descricao e sku.
- calcular score do candidato.
- ignorar menus, footer, login, cookie, breadcrumb e paginacao.

Estados:

- `instant_candidates`
- `instant_selected_candidate`
- `site_busca_status=estruturas_detectadas`

Saidas:

- lista de candidatos.
- melhor dataframe sugerido.

## Fluxo 4 - Escolha manual do candidato

Quando existir mais de um candidato:

- mostrar preview de cada candidato.
- mostrar score.
- permitir botao "usar esta estrutura".
- permitir salvar aprendizado por dominio.

Estados:

- `instant_selected_candidate`
- `click_opcoes`
- `learning_store`

Saidas:

- `df_origem` preenchido.
- estrutura aprendida para o dominio.

## Fluxo 5 - Aprendizado por dominio

Quando usuario escolher uma estrutura:

- salvar assinatura/selector do candidato.
- na proxima URL do mesmo dominio, tentar a estrutura aprendida primeiro.

Estados:

- dominio normalizado.
- selector ou assinatura.
- score.
- data/hora do aprendizado.

Regras:

- se aprendizado falhar, voltar para deteccao automatica.
- aprendizado nunca deve impedir busca manual.

## Fluxo 6 - Paginacao

Paginacao deve ser segura:

- detectar link de proxima pagina.
- tentar parametros `page`, `pagina`, `p`, `pg`.
- parar se HTML repetir.
- parar se URL repetir.
- limite padrao: 8 paginas.

Estados:

- `paginas_visitadas`
- `motivo_parada_paginacao`

Saidas:

- dataframe consolidado.
- duplicados removidos por URL/nome.

## Fluxo 7 - Normalizacao AI local

Depois da extracao:

- limpar nome.
- normalizar preco.
- limpar imagens ruins.
- limpar GTIN invalido.
- inferir marca, sku e categoria.
- gerar `_ai_score`, `_ai_status`, `_ai_alertas`.

Motor:

- `ai_normalizer.normalizar_produtos_ai`

## Fluxo 8 - GPT opcional

GPT deve ser opcional:

- rodar somente se `OPENAI_API_KEY` existir.
- limitar quantidade processada.
- preservar preco, GTIN, URL, imagem, SKU e estoque.
- enriquecer somente nome, marca, categoria e descricao.

Motor:

- `gpt_enricher.enriquecer_produtos_gpt`

## Fluxo 9 - Passagem para Bling

Saida do modulo deve alimentar:

- `df_origem`
- mapeamento manual/IA.
- precificacao.
- preview final.

Campos minimos recomendados:

- `nome`
- `preco`
- `url_produto`
- `imagens`
- `descricao`
- `sku`
- `gtin`
- `estoque`
- `marca`
- `categoria`

## Fluxo 10 - UI de desenvolvimento

A tela deve mostrar sempre:

- URL analisada.
- modo de captura usado.
- tamanho do HTML.
- quantidade de candidatos.
- score do melhor candidato.
- preview dos dados.
- botao para limpar busca.
- botao para detectar novamente.
- botao para usar candidato escolhido.

## Estados principais recomendados

```text
site_url_input
site_url_origem
site_busca_status
site_busca_erro
site_busca_total
click_html
click_url
instant_candidates
instant_selected_candidate
click_opcoes
df_origem
site_runtime_modo
site_runtime_browser_opcional
site_runtime_http_first
```

## Status oficiais

```text
idle
carregando_html
html_carregado
detectando_estruturas
estruturas_detectadas
extraindo
concluido
erro
```

## Regra de ouro

Nenhum erro de Playwright pode bloquear o fluxo principal. O modulo deve continuar funcionando por HTTP + Instant DOM.
