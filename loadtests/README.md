# Load test / Stress test

Este pacote prepara testes de carga seguros para o app.

## Aviso importante

Não rode testes pesados contra produção sem autorização, staging e monitoramento.
Milhões de usuários simultâneos exigem infraestrutura distribuída.
Streamlit Cloud não deve ser tratado como ambiente para teste de milhões de usuários.

## Instalação

```bash
pip install -r requirements-loadtest.txt
```

## Smoke test local

Com o app rodando localmente:

```bash
streamlit run app.py
bash loadtests/run_smoke.sh http://localhost:8501
```

Padrão:

- 25 usuários
- spawn rate 5/s
- duração 2 minutos

## Teste moderado

```bash
USERS=250 SPAWN_RATE=25 DURATION=5m bash loadtests/run_smoke.sh https://SEU-STAGING
```

## Teste alto

```bash
USERS=2000 SPAWN_RATE=100 DURATION=15m bash loadtests/run_smoke.sh https://SEU-STAGING
```

## Milhões de usuários

Para simular milhões, use Locust distribuído em múltiplas máquinas:

```bash
locust -f loadtests/locustfile.py --master --host https://SEU-STAGING
```

Em cada worker:

```bash
locust -f loadtests/locustfile.py --worker --master-host IP_DO_MASTER
```

A escala real depende de:

- quantidade de workers;
- CPU/RAM/rede dos workers;
- capacidade do servidor alvo;
- banco/cache/fila/CDN;
- limites do provedor.

## Métricas para observar

- P95/P99 de resposta;
- taxa de falhas;
- CPU/RAM do app;
- uso de rede;
- reinícios do Streamlit;
- erros de sessão;
- consumo de APIs externas.
