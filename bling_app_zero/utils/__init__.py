import pandas as pd

def limpar_planilha(modelo_df):
    """
    Mantém apenas as colunas do modelo e remove TODAS as linhas
    """
    df_limpo = pd.DataFrame(columns=modelo_df.columns)
    return df_limpo
