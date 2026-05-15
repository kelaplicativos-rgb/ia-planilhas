from __future__ import annotations

import pandas as pd

# Contratos internos usados SOMENTE quando o usuário não anexar modelo oficial.
# Regra global:
# - se houver modelo anexado, o CSV final deve respeitar exatamente esse cabeçalho;
# - se não houver modelo anexado, o CSV final deve respeitar exatamente estes contratos internos;
# - cadastro e estoque nunca podem exportar nem mapear colunas fora do contrato da operação.

CADASTRO_BLING_COLUMNS = [
    'ID',
    'Código',
    'Descrição',
    'Unidade',
    'NCM',
    'Origem',
    'Preço',
    'Valor IPI fixo',
    'Observações',
    'Situação',
    'Estoque',
    'Preço de custo',
    'Cód no fornecedor',
    'Fornecedor',
    'Localização',
    'Estoque maximo',
    'Estoque minimo',
    'Peso líquido (Kg)',
    'Peso bruto (Kg)',
    'GTIN/EAN',
    'GTIN/EAN da embalagem',
    'Largura do Produto',
    'Altura do Produto',
    'Profundidade do produto',
    'Data Validade',
    'Descrição do Produto no Fornecedor',
    'Descrição Complementar',
    'Itens p/ caixa',
    'Produto Variação',
    'Tipo Produção',
    'Classe de enquadramento do IPI',
    'Código da lista de serviços',
    'Tipo do item',
    'Grupo de Tags/Tags',
    'Tributos',
    'Código Pai',
    'Código Integração',
    'Grupo de produtos',
    'Marca',
    'CEST',
    'Volumes',
    'Descrição Curta',
    'Cross-Docking',
    'URL Imagens Externas',
    'Link Externo',
    'Meses Garantia no Fornecedor',
    'Clonar dados do pai',
    'Condição do produto',
    'Frete Grátis',
    'Número FCI',
    'Vídeo',
    'Departamento',
    'Unidade de medida',
    'Preço de compra',
    'Valor base ICMS ST para retenção',
    'Valor ICMS ST para retenção',
    'Valor ICMS próprio do substituto',
    'Categoria do produto',
    'Informações Adicionais',
]

ESTOQUE_BLING_COLUMNS = [
    'ID Produto',
    'Codigo produto *',
    'GTIN **',
    'Descrição Produto',
    'Deposito (OBRIGATÓRIO)',
    'Balanço (OBRIGATÓRIO)',
    'Preço unitário (OBRIGATÓRIO)',
    'Preço de Custo',
    'Observação',
    'Data',
]


def cadastro_default_model() -> pd.DataFrame:
    return pd.DataFrame(columns=CADASTRO_BLING_COLUMNS)


def estoque_default_model() -> pd.DataFrame:
    return pd.DataFrame(columns=ESTOQUE_BLING_COLUMNS)


def model_columns(df_model: pd.DataFrame | None, operation: str) -> list[str]:
    if isinstance(df_model, pd.DataFrame) and len(df_model.columns):
        return [str(column) for column in df_model.columns]
    op = str(operation or '').strip().lower()
    if op == 'estoque':
        return list(ESTOQUE_BLING_COLUMNS)
    if op == 'cadastro':
        return list(CADASTRO_BLING_COLUMNS)
    return []


def model_for_operation(df_model: pd.DataFrame | None, operation: str) -> pd.DataFrame:
    columns = model_columns(df_model, operation)
    return pd.DataFrame(columns=columns)


def enforce_model_contract(
    df_final: pd.DataFrame | None,
    operation: str,
    df_model: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Força o CSV final a seguir o contrato exato da operação.

    Esta é a trava final antes de preview/download. Ela remove colunas soltas,
    cria colunas ausentes vazias e preserva a ordem do modelo anexado ou interno.
    """
    columns = model_columns(df_model, operation)
    if not columns:
        return pd.DataFrame()
    if not isinstance(df_final, pd.DataFrame):
        return pd.DataFrame(columns=columns)
    return df_final.copy().fillna('').reindex(columns=columns, fill_value='')


__all__ = [
    'CADASTRO_BLING_COLUMNS',
    'ESTOQUE_BLING_COLUMNS',
    'cadastro_default_model',
    'enforce_model_contract',
    'estoque_default_model',
    'model_columns',
    'model_for_operation',
]
