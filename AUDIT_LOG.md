# AUDIT LOG — IA Planilhas → Bling

Este arquivo registra mudanças estruturais importantes do projeto, principalmente ações de BLINGMODULAR, BLINGCLEAN, BLINGFIX e BLINGSCAN.

## 2026-05-11 — Modularização e limpeza do fluxo principal

### Objetivo

Reduzir acoplamento do `app.py`, remover CSS legado de alerta/bloqueio e padronizar o aviso visual de etapas bloqueadas.

### Resultado

- `app.py` passou a funcionar como orquestrador principal.
- Configuração global foi movida para `bling_app_zero/core/app_config.py`.
- Registro de erro crítico foi movido para `bling_app_zero/core/app_errors.py`.
- Fix de toolbar/sidebar foi movido para `bling_app_zero/ui/layout/toolbar_fix.py`.
- Exportações centrais foram organizadas em:
  - `bling_app_zero/core/__init__.py`
  - `bling_app_zero/ui/layout/__init__.py`
- Wizard principal foi modularizado com:
  - `bling_app_zero/ui/home_wizard_constants.py`
  - `bling_app_zero/ui/home_wizard_ui.py`
- CSS legado de bloqueio antigo foi removido:
  - `bling-pending-next-card`
  - `bling-pending-next-text`
  - `bling-blocked-next-card`
  - `bling-blocked-next-text`
- Função legada removida:
  - `render_blocked_next_slot()`

### Versões envolvidas

- `3.5.22-BLINGMODULAR-WIZARD-ALERTS`
- `3.5.23-BLINGFIX-CLEAN-ALERTS`
- `3.5.24-BLINGMODULAR-APP`
- `3.5.25-BLINGCLEAN-MODULAR-APP`
- `3.5.26-BLINGMODULAR-CONFIG`

### Commits principais

- `c859230639db1bf894b3d9d0694c4693892e0365` — extrai constantes do wizard.
- `cd4979e9050a3e9d6b68d70e8da2930b5abb2e04` — extrai UI do wizard.
- `81c99607d4da30764ea1d9be02f8266e194ca33e` — conecta `home_wizard.py` aos módulos extraídos.
- `3e2ca72f42e3670558563ae1b24e37ee7c1906a5` — adiciona CSS global para alertas laranja.
- `736eb3f0697c119cba47f193dff02b3e4ee722c8` — remove função morta do wizard UI.
- `13fe0c9763dfc2f4224844a91acaab179f85af49` — remove CSS legado de bloqueio antigo do tema.
- `752a572b6c8978419654da573b0eb03e9b73e80f` — limpa CSS antigo do `app.py`.
- `8fb2edf38a896f6085a0334a7b97c06ab2b6b0e6` — adiciona módulo de erro crítico.
- `b3d0b1d818c33922249c6fb6059e4f5aa93f509f` — simplifica `app.py` como orquestrador.
- `9920b922c65a0a52d2b990c1e91a7d64050d2737` — exporta toolbar fix pelo pacote layout.
- `fe016329e977d3fe62781481b84596e2241653a2` — importa toolbar fix pelo pacote layout.
- `1850bf477e7e08f82fdb5cbcd1f33639b2c72625` — adiciona configuração central do app.
- `c24b7481e74bf2ad00aa321d4474cd0772dc5ad3` — usa configuração central no `app.py`.
- `c94de08b817b36455a26723a831d594a630649f6` — exporta config e erros pelo core.
- `40028a30ebc0814b1bd13b0c1d2d1ad96fbbbe9e` — importa config e erro pelo pacote core.

### Regras confirmadas

- Alerta/bloqueio deve usar cor diferenciada, preferencialmente laranja claro.
- Quando uma etapa estiver bloqueada, o botão normal de “Continuar” não deve aparecer disponível.
- O `app.py` deve permanecer como entrada/orquestrador, evitando CSS grande, lógica de erro e configuração espalhada.
- Mudanças de BLINGMODULAR devem criar módulos pequenos, evitando bagunçar fluxos já corrigidos.

### Status

Aprovado em BLINGSCAN após as limpezas.

