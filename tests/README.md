# Smoke tests do Wizard

Este diretório contém testes rápidos para proteger os pontos críticos do fluxo principal do sistema IA Planilhas → Bling.

## Objetivo

O smoke test não tenta simular toda a interface do Streamlit. Ele valida contratos importantes para impedir regressões em pontos que já foram corrigidos.

## O que é protegido

### Imports críticos

Garante que os módulos principais do Wizard, site, exportação e GTIN importam sem quebrar.

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
