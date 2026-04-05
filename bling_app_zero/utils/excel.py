from io import BytesIO
from typing import Dict, Iterable, List, Optional

import pandas as pd


def _normalizar_header(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    if len(df.columns) > 0 and all(str(col).isdigit() for col in df.columns):
        df.columns = df.iloc[0]
        df = df.iloc[1:].reset_index(drop=True)

    df = df.fillna("").astype(str)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def ler_planilha(file):
    if file is None:
        return pd.DataFrame()

    nome = (getattr(file, "name", "") or "").lower().strip()

    if nome.endswith(".csv"):
        try:
            file.seek(0)
            df = pd.read_csv(file, dtype=str)
        except Exception:
            file.seek(0)
            df = pd.read_csv(file, dtype=str, sep=";")
        return _normalizar_header(df)

    file.seek(0)
    df = pd.read_excel(file, dtype=str)
    return _normalizar_header(df)


def limpar_valores_vazios(df):
    if df is None or df.empty:
        return pd.DataFrame()
    return df.fillna("").astype(str)


def normalizar_colunas(df):
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _valor_vazio(valor) -> bool:
    return str(valor or "").strip() == ""


def _primeiro_valor_disponivel(row: pd.Series, colunas: Iterable[str]) -> str:
    for col in colunas:
        if col in row.index:
            valor = str(row[col] if row[col] is not None else "").strip()
            if valor:
                return valor
    return ""


def build_download_dataframe(
    df_origem: pd.DataFrame,
    mapeamento: Dict[str, str],
    colunas_destino: Optional[List[str]] = None,
    campos_fixos: Optional[Dict[str, object]] = None,
) -> pd.DataFrame:
    if df_origem is None or df_origem.empty:
        return pd.DataFrame()

    df_origem = df_origem.copy().fillna("")
    df_origem.columns = [str(c).strip() for c in df_origem.columns]

    if not colunas_destino:
        usados = [str(v).strip() for v in (mapeamento or {}).values() if str(v).strip()]
        colunas_destino = list(dict.fromkeys(usados))

    if campos_fixos:
        for campo in campos_fixos.keys():
            if campo not in colunas_destino:
                colunas_destino.append(campo)

    linhas_saida = []
    mapeamento = mapeamento or {}

    for _, row in df_origem.iterrows():
        item = {col: "" for col in colunas_destino}

        for col_origem, col_destino in mapeamento.items():
            if not col_destino or col_origem not in df_origem.columns:
                continue
            if col_destino not in item:
                item[col_destino] = ""
            item[col_destino] = row[col_origem]

        # Reforço inteligente para XML e bases já enriquecidas
        aliases = {
            "codigo": ["codigo", "referencia_fornecedor", "codigo_fabricante", "item"],
            "nome": ["nome", "descricao_curta", "descricao"],
            "descricao_curta": ["descricao_curta", "descricao", "nome"],
            "descricao_completa": ["descricao_completa", "descricao_curta", "descricao", "nome"],
            "descricao_html": ["descricao_html", "descricao_completa
