from __future__ import annotations

import pandas as pd  # ✅ CORREÇÃO PRINCIPAL

# (mantém o resto dos imports que já existem no seu arquivo)
# IMPORTANTE: não remover nada existente abaixo


def _obter_serie_preco_para_saida(df_origem: pd.DataFrame) -> pd.Series:
    """
    Pega automaticamente a coluna de preço calculado no fluxo.
    NÃO depende mais de nome fixo.
    """

    try:
        df_fluxo = _get_df_fluxo_base(df_origem)

        # 🔥 PRIORIDADE 1 — coluna padrão
        candidatos = [
            "Preço de venda",
            "preço de venda",
            "Preco de venda",
            "preco de venda",
        ]

        for nome in candidatos:
            if nome in df_fluxo.columns:
                return df_fluxo[nome].reset_index(drop=True)

        # 🔥 PRIORIDADE 2 — detectar coluna nova criada pela precificação
        colunas_origem = set(df_origem.columns)

        for col in df_fluxo.columns:
            if col not in colunas_origem:
                return df_fluxo[col].reset_index(drop=True)

        # 🔥 PRIORIDADE 3 — detectar mudança de valores
        for col in df_fluxo.columns:
            if col in df_origem.columns:
                try:
                    s1 = df_origem[col].fillna("").astype(str)
                    s2 = df_fluxo[col].fillna("").astype(str)

                    if not s1.equals(s2):
                        return s2.reset_index(drop=True)
                except Exception:
                    continue

        # 🔥 fallback FINAL
        coluna_preco_base = _get_coluna_preco_base_precificacao(df_origem)

        if coluna_preco_base and coluna_preco_base in df_fluxo.columns:
            return df_fluxo[coluna_preco_base].reset_index(drop=True)

    except Exception:
        pass

    return pd.Series([""] * len(df_origem), index=range(len(df_origem)), dtype="object")
