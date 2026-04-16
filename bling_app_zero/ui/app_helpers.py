def _ler_tabular(upload):
    nome = str(upload.name).lower()

    # ================= CSV =================
    if nome.endswith(".csv"):
        bruto = upload.getvalue()

        for sep in [";", ",", "\t", "|"]:
            try:
                df = pd.read_csv(
                    io.BytesIO(bruto),
                    sep=sep,
                    dtype=str,
                    encoding="utf-8",
                    engine="python",
                ).fillna("")

                # 🔥 FORÇA colunas válidas
                df.columns = [str(c).strip() for c in df.columns if str(c).strip()]

                if len(df.columns) > 0:
                    return df

            except Exception:
                continue

        raise ValueError("Não foi possível ler o CSV.")

    # ================= EXCEL =================
    if nome.endswith(".xlsx") or nome.endswith(".xls"):
        try:
            df = pd.read_excel(upload, dtype=str).fillna("")

            # 🔥 LIMPEZA BRUTA
            df.columns = [str(c).strip() for c in df.columns if str(c).strip()]

            # remove colunas totalmente vazias
            df = df.loc[:, df.columns.notna()]
            df = df[[c for c in df.columns if str(c).strip() != ""]]

            # 🔥 CASO MODELO (sem linhas)
            if len(df.columns) > 0:
                return df

        except Exception as e:
            raise ValueError(f"Não foi possível ler o Excel: {e}")

    raise ValueError("Arquivo tabular inválido.")
