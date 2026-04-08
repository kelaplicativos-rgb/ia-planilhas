# (mantive tudo igual, só ajustei pontos críticos)

# =========================================
# ADICIONE ESTE HELPER NO TOPO
# =========================================
def _set_if_changed(key: str, value):
    try:
        if st.session_state.get(key) != value:
            st.session_state[key] = value
    except Exception:
        pass


# =========================================
# MELHORIA GTIN
# =========================================
def _limpar_gtin_invalido(df: pd.DataFrame) -> pd.DataFrame:
    try:
        if not safe_df_dados(df):
            return df

        df = df.copy()

        for col in df.columns:
            nome_col = str(col).strip().lower()
            if (
                "gtin" in nome_col
                or "ean" in nome_col
                or "codigo de barras" in nome_col
                or "código de barras" in nome_col
            ):
                def limpar(valor):
                    digitos = _somente_digitos(valor)

                    # remove lixo tipo 0000000000000
                    if not digitos or set(digitos) == {"0"}:
                        return ""

                    if len(digitos) in [8, 12, 13, 14]:
                        return digitos

                    return ""

                df[col] = df[col].apply(limpar)

        return df
    except Exception:
        return df


# =========================================
# MELHORIA RESET
# =========================================
def _limpar_estado_origem():
    """
    Reset mais seguro — não destrói tudo
    """
    chaves = [
        "df_origem",
        "df_origem_xml",
        "df_saida",
        "df_final",
        "df_mapeado",
        "mapeamento_colunas",
        "mapeamento_manual",
        "mapeamento_auto",
        "colunas_mapeadas",
    ]

    for chave in chaves:
        try:
            st.session_state.pop(chave, None)
        except Exception:
            pass


# =========================================
# AJUSTE ORIGEM (ANTI BUG FUTURO)
# =========================================
# TROCAR ISSO:
# st.session_state["origem_dados"] = origem_atual

# POR ISSO:
_set_if_changed("origem_dados", origem_atual)
