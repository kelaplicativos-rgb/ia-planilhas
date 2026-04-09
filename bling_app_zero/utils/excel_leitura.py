# 🔽 ADICIONAR LOGO APÓS IMPORTS

def _coluna_generica(col) -> bool:
    try:
        c = str(col).strip().lower()
        return (
            c.isdigit()
            or c.startswith("unnamed")
            or c in {"", "none", "nan"}
        )
    except Exception:
        return True


def _linha_parece_header(linha) -> bool:
    try:
        textos = [str(x).strip() for x in linha if str(x).strip()]
        if not textos:
            return False

        proporcao_texto = sum(1 for t in textos if not t.isdigit()) / len(textos)
        unicos = len(set(textos)) / len(textos)

        return proporcao_texto > 0.7 and unicos > 0.7
    except Exception:
        return False


def _corrigir_header_se_preciso(df: pd.DataFrame) -> pd.DataFrame:
    try:
        if not isinstance(df, pd.DataFrame) or df.empty:
            return df

        cols_genericas = sum(1 for c in df.columns if _coluna_generica(c))

        if cols_genericas / len(df.columns) < 0.6:
            return df

        primeira_linha = df.iloc[0].tolist()

        if not _linha_parece_header(primeira_linha):
            return df

        novos_nomes = []
        usados = set()

        for i, v in enumerate(primeira_linha):
            nome = str(v).strip() or f"Coluna_{i+1}"
            base = nome
            c = 2

            while nome in usados:
                nome = f"{base}_{c}"
                c += 1

            usados.add(nome)
            novos_nomes.append(nome)

        df.columns = novos_nomes
        df = df.iloc[1:].reset_index(drop=True)

        log_debug("Header corrigido automaticamente", "SUCCESS")

        return df

    except Exception:
        return df
