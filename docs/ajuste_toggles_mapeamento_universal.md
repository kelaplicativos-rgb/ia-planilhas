# Ajuste de UX: toggles do fluxo universal

Diagnóstico confirmado em bling_diagnostico_completo (32):

- `Preço / cálculo marketplace` deve iniciar desligado.
- `Categorização inteligente` deve iniciar desligado.
- `Regras e recursos inteligentes no download` deve iniciar desligado.
- `Mapeamento automático com IA` deve ficar junto da seção `Mapeamento`, abaixo do título, e também iniciar desligado.

Arquivo alvo:

```text
bling_app_zero/ui/universal_flow.py
```

Mudanças necessárias:

1. Em `_render_toggles()`, manter apenas preço, categoria e regras.
2. Alterar regras para `value=False`.
3. Remover o toggle de mapeamento automático da área de opcionais.
4. Renderizar `Mapeamento automático com IA` logo antes de `render_shared_contract_mapping(...)`.
5. Manter `default=False` no toggle de IA.

Motivo:

O recurso de IA pertence ao momento do mapeamento. Deixar o toggle junto da lista de campos reduz confusão no mobile e evita que o usuário precise voltar a tela para ligar/desligar o mapeamento automático.
