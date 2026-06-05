# Backend OAuth do Bling

Este backend separa o OAuth do Bling do Streamlit.

O Streamlit continua como interface, mas o login/autorizacao do Bling pode ser feito por um backend FastAPI separado.

## Arquivos principais

- `bling_backend/main.py` — rotas FastAPI
- `bling_backend/config.py` — variaveis de ambiente
- `bling_backend/token_store.py` — armazenamento simples de token
- `bling_backend/requirements.txt` — dependencias do backend
- `render.yaml` — blueprint para Render
- `Procfile` — comando web generico

## Rotas

- `GET /health` — verifica status do backend
- `GET /auth/bling/start` — inicia autorizacao no Bling
- `GET /auth/bling/callback` — recebe retorno do Bling
- `GET /auth/bling/status` — informa se ha token salvo
- `POST /auth/bling/disconnect` — limpa token salvo

## Deploy rapido no Render

1. Abra Render.
2. Crie um novo Blueprint ou Web Service usando este repositorio.
3. Use o `render.yaml` ou configure manualmente:

Build Command:

```bash
pip install -r bling_backend/requirements.txt
```

Start Command:

```bash
uvicorn bling_backend.main:app --host 0.0.0.0 --port $PORT
```

4. Configure as variaveis de ambiente:

```bash
BLING_CLIENT_ID=seu_client_id
BLING_CLIENT_SECRET=seu_client_secret
BLING_REDIRECT_URI=https://SEU-BACKEND.onrender.com/auth/bling/callback
FRONTEND_RETURN_URL=https://ia-planilhas.streamlit.app/
BLING_BACKEND_TOKEN_DIR=/tmp/bling_tokens
```

5. Depois do deploy, teste:

```text
https://SEU-BACKEND.onrender.com/health
```

## Configuracao no Bling

No app v3 do Bling, configure a URL de redirecionamento/callback como:

```text
https://SEU-BACKEND.onrender.com/auth/bling/callback
```

Ela precisa ser exatamente igual ao valor de `BLING_REDIRECT_URI`.

## Configuracao no Streamlit

No Secrets do Streamlit, adicione:

```toml
[bling]
backend_auth_url = "https://SEU-BACKEND.onrender.com/auth/bling/start"
```

Depois disso, o botao `Conectar ao Bling` passa a usar o backend externo.

Se `backend_auth_url` nao estiver configurado, o sistema continua usando o OAuth antigo do Streamlit como fallback.

## Observacao importante

O armazenamento atual do backend usa arquivo JSON simples. Para producao real, o ideal e trocar por Firestore, Postgres ou outro armazenamento persistente.
