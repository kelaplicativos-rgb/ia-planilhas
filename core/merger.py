import pandas as pd

def merge_dados(planilha_df, site_df, url_base, estoque_padrao):
    if planilha_df.empty:
        return site_df
    if site_df.empty:
        return planilha_df

    return pd.concat([planilha_df, site_df]).drop_duplicates()
