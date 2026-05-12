# BLINGMODULE

Arquitetura oficial para adicionar recursos futuros ao IA Planilhas / Bling sem bagunçar o fluxo principal.

## Objetivo

Todo recurso novo deve nascer como módulo plugável, com contrato claro, estado controlado, arquivo dono e registro no painel técnico.

Evite adicionar recurso novo diretamente em arquivos centrais como:

- `app.py`
- `bling_app_zero/ui/home_wizard.py`
- `bling_app_zero/core/exporter.py`
- motores de site sem passar por roteador/contrato

## Estrutura oficial

```txt
bling_app_zero/features/
    __init__.py
    contracts.py
    state.py
    registry.py
    runtime.py
    validator.py
    template_feature.py
```

## Contratos

Todo recurso deve declarar uma `FeatureDefinition` com:

- `key`: chave única do módulo
- `title`: nome amigável
- `description`: explicação curta
- `scope`: `cadastro`, `estoque` ou `global`
- `stage`: `entrada`, `mapeamento`, `preview`, `download`, `sidebar` ou `global`
- `status`: `stable`, `beta`, `experimental` ou `disabled`
- `state_key`: chave principal de estado
- `requires`: entradas exigidas
- `provides`: entregas do módulo
- `owner_file`: arquivo responsável
- `runner`: função executável opcional
- `renderer`: UI opcional

## Runner

Um recurso executável deve receber `FeatureContext` e devolver `FeatureResult`.

```python
from bling_app_zero.features.contracts import FeatureContext, FeatureResult


def run_feature(context: FeatureContext) -> FeatureResult:
    return FeatureResult(
        ok=True,
        message='Executado com sucesso.',
        source_df=context.source_df,
        final_df=context.final_df,
    )
```

## Registry

Depois de criar o módulo, registre a definição em:

```txt
bling_app_zero/features/registry.py
```

O painel da sidebar mostra automaticamente os módulos registrados.

## Estado

Use somente helpers de `bling_app_zero/features/state.py` para estado de módulo:

- `feature_enabled_key()`
- `feature_config_key()`
- `is_feature_enabled()`
- `set_feature_enabled()`
- `get_feature_config()`
- `set_feature_config()`
- `clear_feature_state()`

Padrão de chave:

```txt
feature_<nome_do_recurso>_enabled
feature_<nome_do_recurso>_config
```

## Runtime

A camada `bling_app_zero/features/runtime.py` executa recursos ativos por escopo e etapa:

```python
from bling_app_zero.features.runtime import run_features_for_stage

context = run_features_for_stage(
    operation='cadastro',
    stage='download',
    final_df=df_final,
)
df_final = context.final_df
```

## Validação

A arquitetura é validada por:

```txt
bling_app_zero/features/validator.py
```

O painel lateral `Módulos e recursos` mostra erros e avisos de contrato.

## Regra de ouro

Recurso novo só entra se responder:

1. Qual é o arquivo dono?
2. Qual etapa usa?
3. Qual operação usa?
4. Qual estado controla?
5. O que ele exige?
6. O que ele entrega?
7. Onde aparece na sidebar?
8. Como ele registra log/audit trail?

Se não responder isso, ainda não está pronto para entrar no sistema.
