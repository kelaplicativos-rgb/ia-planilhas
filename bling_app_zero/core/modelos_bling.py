from __future__ import annotations

from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
MODELOS_DIR = BASE_DIR / "modelos"

ARQUIVO_MODELO_CADASTRO = MODELOS_DIR / "modelo_cadastro.xlsx"
ARQUIVO_MODELO_ESTOQUE = MODELOS_DIR / "modelo_estoque.xlsx"


COLUNAS_FALLBACK_CADASTRO = [
    "ID",
    "Código",
    "Descrição",
    "Descrição Curta",
    "Preço de venda",
    "Preço de custo",
    "Marca",
    "NCM",
    "GTIN",
    "GTIN tributário",
    "Unidade",
    "Peso Líquido (Kg)",
    "Peso Bruto (Kg)",
    "Largura (cm)",
    "Altura (cm)",
    "Profundidade (cm)",
    "Estoque",
    "Situação",
    "Imagens",
    "Link Externo",
]

COLUNAS_FALLBACK_ESTOQUE = [
    "ID",
    "Código",
    "Descrição",
    "Depósito",
    "Quantidade",
    "Preço",
    "Situação",
]


def _normalizar_df(df: pd.DataFrame) -> pd.DataFrame:
    try:
        df = df.copy()
        df.columns = [str(col).strip() for col in df.columns]
        for col in df.columns:
            df[col] = df[col].replace({None: ""}).fillna("")
        return df
    except Exception:
        return df


def _safe_df_estrutura(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0
    except Exception:
        return False


def _carregar_excel(caminho: Path) -> pd.DataFrame | None:
    try:
        if not caminho.exists():
            return None
        df = pd.read_excel(caminho)
        if not _safe_df_estrutura(df):
            return None
        return _normalizar_df(df)
    except Exception:
        return None


def _criar_fallback(colunas: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=colunas)


def carregar_modelo_cadastro_interno() -> pd.DataFrame:
    df = _carregar_excel(ARQUIVO_MODELO_CADASTRO)
    if _safe_df_estrutura(df):
        return df
    return _criar_fallback(COLUNAS_FALLBACK_CADASTRO)


def carregar_modelo_estoque_interno() -> pd.DataFrame:
    df = _carregar_excel(ARQUIVO_MODELO_ESTOQUE)
    if _safe_df_estrutura(df):
        return df
    return _criar_fallback(COLUNAS_FALLBACK_ESTOQUE)


def carregar_modelo_por_operacao(tipo_operacao: str) -> pd.DataFrame:
    tipo = str(tipo_operacao or "").strip().lower()

    if tipo in {"cadastro", "cadastro de produtos"}:
        return carregar_modelo_cadastro_interno()

    return carregar_modelo_estoque_interno()


def caminho_modelo_por_operacao(tipo_operacao: str) -> str:
    tipo = str(tipo_operacao or "").strip().lower()

    if tipo in {"cadastro", "cadastro de produtos"}:
        return str(ARQUIVO_MODELO_CADASTRO)

    return str(ARQUIVO_MODELO_ESTOQUE)


def modelo_interno_existe(tipo_operacao: str) -> bool:
    tipo = str(tipo_operacao or "").strip().lower()

    if tipo in {"cadastro", "cadastro de produtos"}:
        return ARQUIVO_MODELO_CADASTRO.exists()

    return ARQUIVO_MODELO_ESTOQUE.exists()
