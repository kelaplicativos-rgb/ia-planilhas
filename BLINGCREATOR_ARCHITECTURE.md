# BLINGCREATOR ALL PONTA A PONTA

Objetivo principal: transformar qualquer origem de dados em um fluxo automatizado compatível com o ERP Bling, reduzindo preenchimento manual, erros humanos e retrabalho.

## Fluxos independentes

### 1. Cadastro de produtos

Entrada: planilha, XML, PDF ou site.

Processamento:
- leitura da origem;
- mapeamento automático;
- precificação opcional;
- limpeza de GTIN;
- tratamento final para CSV Bling.

Saída:
- `bling_cadastro_produtos.csv`.

Motor:
- `bling_app_zero/engines/cadastro_engine.py`

Pipeline:
- `bling_app_zero/pipelines/cadastro_pipeline.py`

### 2. Atualização de estoque

Entrada: planilha de origem + modelo de estoque do Bling.

Regra principal:
- o motor de estoque é separado do cadastro;
- usa somente as colunas pedidas pela planilha modelo;
- campos não encontrados ficam vazios;
- depósito digitado pelo usuário é propagado para campos de depósito.

Saída:
- `bling_atualizacao_estoque.csv`.

Motor:
- `bling_app_zero/engines/estoque_engine.py`

Pipeline:
- `bling_app_zero/pipelines/estoque_pipeline.py`

### 3. Busca inteligente por site

Entrada: links de produtos ou páginas.

Processamento:
- crawler independente;
- extração de título, preço, estoque, SKU e imagens;
- em modo estoque, captura somente o que o modelo solicita;
- em modo cadastro, gera cadastro Bling completo quando possível.

Motor:
- `bling_app_zero/engines/site_engine.py`

Pipeline:
- `bling_app_zero/pipelines/site_pipeline.py`

## Core compartilhado

- `core/files.py`: leitura universal de arquivos.
- `core/text.py`: normalização e limpeza de textos.
- `core/gtin.py`: limpeza de GTIN/EAN inválido.
- `core/mapping.py`: mapeamento automático.
- `core/pricing.py`: calculadora de preço.
- `core/exporter.py`: exportação CSV Bling com `;` e UTF-8-SIG.
- `core/validators.py`: validação final.
- `core/debug.py`: log debug e botão de download.

## Interface

- `app.py`: entrada principal segura do Streamlit.
- `bling_app_zero/ui/home.py`: Home com seleção de operação e execução dos pipelines.

## Regra anti-bagunça

Cada fluxo possui motor independente. Alterações em estoque não devem alterar cadastro. Alterações em cadastro não devem alterar busca por site. O crawler de site deve permanecer separado e apenas alimentar os pipelines.
