# BLINGBACKGROUND · Ativação do worker em segundo plano

Este guia deixa o envio ao Bling rodando fora da aba do navegador.

## O que já existe no código

- Botão no app: `Iniciar em segundo plano e poder fechar o navegador`.
- Fila persistente: `bling_app_zero/core/background_jobs.py`.
- Worker de lote: `bling_app_zero/workers/bling_background_worker.py`.
- Daemon contínuo: `bling_app_zero/workers/bling_background_daemon.py`.
- Blueprint Render com serviço worker: `render.yaml`.

## Comando do worker

```bash
python -m bling_app_zero.workers.bling_background_daemon
```

## Render

No Render, o projeto deve ter dois serviços:

1. Web OAuth do Bling: `mapeiaai-bling-oauth`.
2. Worker: `ia-planilhas-bling-worker`.

O worker precisa usar o mesmo repositório e branch `main`.

## Variáveis obrigatórias

Configure no Streamlit e no Render Worker os mesmos valores de OAuth e Firestore.

### Persistência

```text
BLING_TOKEN_STORE_MODE=firestore
BLING_BACKGROUND_WORKER_INTERVAL_SECONDS=30
BLING_BACKGROUND_WORKER_MAX_JOBS=3
BLING_BACKGROUND_WORKER_MAX_BATCHES_PER_JOB=1000
BLING_BACKGROUND_JOBS_COLLECTION=bling_background_jobs
```

### Google / Firestore

Use as mesmas credenciais que o app já usa para token persistente:

```text
GOOGLE_SERVICE_ACCOUNT_JSON=<json-da-conta-de-servico>
GOOGLE_CLOUD_PROJECT=<id-do-projeto>
```

Também são aceitos aliases já suportados no código:

```text
BLING_FIRESTORE_SERVICE_ACCOUNT_JSON=<json-da-conta-de-servico>
BLING_FIRESTORE_PROJECT_ID=<id-do-projeto>
```

### Bling OAuth

Use os mesmos valores configurados para a conexão OAuth do Bling:

```text
BLING_CLIENT_ID=<client-id>
BLING_CLIENT_SECRET=<client-secret>
BLING_REDIRECT_URI=<redirect-uri>
```

## Como testar

1. No app, conecte o Bling.
2. Prepare uma operação: cadastro, preço ou estoque.
3. Na tela de envio, clique em `Iniciar em segundo plano e poder fechar o navegador`.
4. Feche a aba.
5. No Render Worker, confira logs do serviço `ia-planilhas-bling-worker`.
6. Volte ao app e abra `Minhas tarefas em segundo plano`.

## Resultado esperado

A tarefa deve sair de:

```text
queued -> running -> done
```

Se falhar, ficará:

```text
error
```

com `last_error` salvo na tarefa.

## Observações importantes

- O Streamlit sozinho não executa tarefas com a aba fechada.
- O worker precisa estar ativo em serviço separado.
- Firestore é obrigatório para produção, porque o Streamlit e o worker precisam enxergar a mesma fila.
- SQLite serve apenas para teste local.
