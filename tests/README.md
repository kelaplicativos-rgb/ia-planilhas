# Smoke tests do Wizard

Este diretório contém testes rápidos para proteger os pontos críticos do fluxo principal do sistema IA Planilhas → Bling.

## Objetivo

O smoke test não tenta simular toda a interface do Streamlit. Ele valida contratos importantes para impedir regressões em pontos que já foram corrigidos.

## O que é protegido

### Imports críticos

Garante que os módulos principais do app, Home, Wizard, site, exportação e GTIN importam sem quebrar.

### Entrada do Streamlit

Protege o ponto de entrada do app para garantir que o deploy continue abrindo o Wizard novo:

```text
app.py
↓
render_home()
↓
home.py
↓
run_wizard_state_guard()
↓
render_home_wizard()
```

### Ordem dos fluxos

Protege a sequência das etapas:

- Cadastro: modelo → operação → precificação → origem → entrada → mapeamento → preview → download
- Estoque: modelo → operação → precificação → origem → entrada → gerar estoque → preview → download

### Separação entre Site e Arquivo

Protege duas regras importantes:

- Origem por arquivo não pode reaproveitar busca antiga de site.
- Origem por site não pode mostrar upload de fornecedor.

### Separação por operação

Garante que a busca por site de cadastro e a busca por site de estoque fiquem isoladas em chaves próprias de sessão.

### Guardião de estado

Garante que troca de operação ou reset do Wizard limpe estados antigos como preview, mapeamento, origem e confirmação de mapeamento.

### Mapeamento

Protege:

- mapeamento por blocos para performance no celular;
- confirmação manual antes de liberar o preview;
- CSS do mapeamento usando variáveis válidas do tema global.

### Download final

Garante que o download continue acontecendo somente na etapa final e sempre passe pelo exportador oficial.

### CSV do Bling

Protege o contrato básico do CSV:

- separador `;`;
- encoding UTF-8-SIG;
- GTIN inválido vazio;
- imagens separadas por `|`.

## Como rodar localmente

```bash
pytest
```

O arquivo `pytest.ini` já configura:

```ini
pythonpath = .
testpaths = tests
addopts = -q
```

## GitHub Actions

O workflow fica em:

```text
.github/workflows/wizard-smoke.yml
```

Ele pode rodar automaticamente em push/PR para `main` e também manualmente em:

```text
Actions → Wizard Smoke Tests → Run workflow
```

## Troubleshooting do GitHub Actions

Se o workflow não aparecer ou o botão `Run workflow` não estiver disponível, verifique:

```text
Settings → Actions → General
```

E confirme que o repositório permite execução de workflows.

Configuração sugerida:

```text
Allow all actions and reusable workflows
```

Depois salve e volte em:

```text
Actions → Wizard Smoke Tests → Run workflow
```

Se o workflow aparecer, mas falhar, abra a execução e veja o passo:

```text
Run Wizard smoke tests
```

Os logs desse passo indicam exatamente qual contrato quebrou, por exemplo:

- import de módulo;
- ordem do Wizard;
- separação site/arquivo;
- confirmação do mapeamento;
- download fora da etapa final;
- CSV/GTIN/exportador.

Observação: alguns conectores podem não listar execuções de Actions mesmo quando o workflow existe no GitHub. Nesse caso, a conferência deve ser feita diretamente pela aba `Actions` do repositório.
