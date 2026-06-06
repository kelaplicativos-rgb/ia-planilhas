# BLINGCLEAN · Rota oficial do envio Bling

Este documento registra a rota oficial depois dos BLINGFIX/BLINGCLEAN para evitar que módulos antigos voltem a assumir a responsabilidade do envio.

## Rota principal de envio

```text
bling_app_zero/ui/bling_api_batch_panel.py
→ bling_app_zero/core/bling_intelligent_update_sender.py
→ bling_app_zero/core/bling_direct_sender_smart_diff.py
```

## Responsabilidades

- `bling_api_batch_panel.py`: interface, lote, progresso e resultado do envio.
- `bling_intelligent_update_sender.py`: pré-decisão inteligente por operação.
- `bling_direct_sender_smart_diff.py`: cadastro/update real com comparação, bloqueio de duplicidade e fallback seguro.
- `bling_api_base_patch.py`: garante em runtime a base correta `https://api.bling.com.br/Api/v3` nos módulos carregados.
- `bling_autocadastro_upsert.py`: motor isolado de upsert usado pelo AutoCadastro via API.
- `blingsmartcore_autocadastro_api_panel.py`: painel de AutoCadastro via API para produtos não confirmados.
- `blingsmartcore_autocadastro.py`: compatibilidade da rota antiga; deve delegar para o painel API e não voltar para mapeamento como fluxo principal.

## Regra de API

A base correta para chamadas de API é:

```text
https://api.bling.com.br/Api/v3
```

Se algum secret antigo ainda vier com:

```text
https://www.bling.com.br/Api/v3
```

os pontos corrigidos devem normalizar para a base correta antes da chamada.

## Regra de cadastro

Cadastro deve ser tratado como upsert:

```text
procurar por código/GTIN
→ se existir, atualizar
→ se não existir, criar
→ se criar retornar conflito, procurar novamente e atualizar
```

## Regra de estoque

Estoque só deve ser atualizado depois de produto confirmado no Bling e depósito resolvido.

## Módulos antigos

`bling_direct_sender.py`, `bling_direct_sender_safe.py` e `bling_direct_sender_smart.py` ainda podem existir como base/fallback. Eles não devem voltar a ser a rota principal isolada sem passar pela rota oficial acima.
