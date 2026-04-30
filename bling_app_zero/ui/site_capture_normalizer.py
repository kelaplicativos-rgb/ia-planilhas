from __future__ import annotations

import pandas as pd


def normalizar_captura_site_para_bling(
    df_site: pd.DataFrame,
    df_modelo: pd.DataFrame | None = None,
    tipo_operacao: str = "cadastro",
    deposito_nome: str = "",
) -> pd.DataFrame:
    if not isinstance(df_site, pd.DataFrame) or df_site.empty:
        return pd.DataFrame()

    if not isinstance(df_modelo, pd.DataFrame) or df_modelo.empty:
        return df_site

    df_saida = pd.DataFrame(columns=df_modelo.columns)

    for col in df_modelo.columns:
        nome = str(col).lower()

        if "descricao" in nome or "nome" in nome:
            df_saida[col] = df_site.iloc[:, 0]

        elif "preco" in nome or "valor" in nome:
            df_saida[col] = df_site.iloc[:, 1] if df_site.shape[1] > 1 else ""

        elif "estoque" in nome or "quantidade" in nome:
            df_saida[col] = df_site.iloc[:, 2] if df_site.shape[1] > 2 else ""

        elif "gtin" in nome or "ean" in nome:
            df_saida[col] = ""

        elif "deposito" in nome and tipo_operacao == "estoque":
            df_saida[col] = deposito_nome

        else:
            df_saida[col] = ""

    return df_saida.fillna("")
