import io
from typing import Dict, List

import pandas as pd
import streamlit as st


CAMPOS_SISTEMA = [
    "— Não mapear —",
    "ID",
    "Código",
    "Descrição",
    "Unidade",
    "NCM",
    "Origem",
    "Preço",
    "Valor IPI fixo",
    "Observações",
    "Situação",
    "Estoque",
    "Preço de custo",
]

CHAVE_MAPEAMENTO = "mapeamento_fornecedor_para_sistema"


# =========================
# UTIL
# =========================
def normalizar_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    df = df.fillna("")
    return df


def _read_excel(file) -> pd.DataFrame:
    file.seek(0)
    return pd.read_excel(file, dtype=str, engine="openpyxl")


def _read_csv(file, sep=None) -> pd.DataFrame:
    file.seek(0)
    return pd.read_csv(file, dtype=str, sep=sep)


def carregar_planilha(file) -> pd.DataFrame:
    nome = (getattr(file, "name", "") or "").lower()

    erros: List[str] = []

    if nome.endswith((".xlsx", ".xls")):
        try:
            return normalizar_df(_read_excel(file))
        except Exception as exc:
            erros.append(f"excel: {exc}")

    for sep in (None, ";", "\t", "|"):
        try:
            return normalizar_df(_read_csv(file, sep=sep))
        except Exception as exc:
            erros.append(f"csv({sep}): {exc}")

    try:
        return normalizar_df(_read_excel(file))
    except Exception as exc:
        erros.append(f"excel-final: {exc}")

    raise ValueError("Não foi possível ler a planilha enviada.")


def _texto_preview(valor, limite=80) -> str:
    texto = str(valor or "").replace("\n", " ").replace("\r", " ").strip()
    if len(texto) <= limite:
        return texto
    return texto[:limite].rstrip() + "..."


def _inicializar_mapeamento(colunas_fornecedor: List[str]) -> Dict[str, str]:
    atual = st.session_state.get(CHAVE_MAPEAMENTO, {}) or {}
    novo = {}

    for coluna in colunas_fornecedor:
        valor = atual.get(coluna, "— Não mapear —")
        if valor not in CAMPOS_SISTEMA:
            valor = "— Não mapear —"
        novo[coluna] = valor

    st.session_state[CHAVE_MAPEAMENTO] = novo
    return novo


def _resolver_duplicados(mapeamento: Dict[str, str]) -> Dict[str, str]:
    usados = set()
    corrigido = {}

    for coluna, campo_sistema in mapeamento.items():
        if campo_sistema == "— Não mapear —":
            corrigido[coluna] = campo_sistema
            continue

        if campo_sistema in usados:
            corrigido[coluna] = "— Não mapear —"
        else:
            corrigido[coluna] = campo_sistema
            usados.add(campo_sistema)

    return corrigido


def _montar_linha_mapeamento(colunas_fornecedor: List[str]) -> pd.DataFrame:
    mapeamento = _inicializar_mapeamento(colunas_fornecedor)
    return pd.DataFrame([mapeamento], index=["Relacionar com"])


def _salvar_mapeamento_editado(df_mapeamento: pd.DataFrame) -> None:
    linha = df_mapeamento.iloc[0].to_dict()
    linha = {
        str(coluna): (valor if valor in CAMPOS_SISTEMA else "— Não mapear —")
        for coluna, valor in linha.items()
    }

    linha = _resolver_duplicados(linha)
    st.session_state[CHAVE_MAPEAMENTO] = linha

    # compatibilidade com o restante do app:
    # sistema -> coluna do fornecedor
    st.session_state["mapeamento_manual"] = {
        campo_sistema: coluna_fornecedor
        for coluna_fornecedor, campo_sistema in linha.items()
        if campo_sistema != "— Não mapear —"
    }


def _render_preview_com_mapeamento(df: pd.DataFrame) -> None:
    st.markdown("### Preview da entrada")

    preview_df = df.head(1).copy()
    if not preview_df.empty:
        preview_df = preview_df.applymap(_texto_preview)

    st.dataframe(
        preview_df,
        width="stretch",
        height=140,
    )

    st.caption("Clique nas células da linha abaixo para relacionar cada coluna do fornecedor com uma coluna do sistema.")

    df_mapeamento = _montar_linha_mapeamento(list(df.columns))

    column_config = {
        coluna: st.column_config.SelectboxColumn(
            label=coluna,
            options=CAMPOS_SISTEMA,
            required=False,
            help=f"Relacionar a coluna '{coluna}' com um campo do sistema",
            width="small",
        )
        for coluna in df.columns
    }

    editado = st.data_editor(
        df_mapeamento,
        width="stretch",
        hide_index=False,
        num_rows="fixed",
        disabled=False,
        column_config=column_config,
        key="preview_mapeamento_editor",
    )

    _salvar_mapeamento_editado(editado)

    valores = list(st.session_state[CHAVE_MAPEAMENTO].values())
    usados = [v for v in valores if v != "— Não mapear —"]
    if len(usados) != len(set(usados)):
        st.warning("Campos duplicados foram liberados automaticamente e os repetidos voltaram para 'Não mapear'.")


# =========================
# MAIN
# =========================
def render_origem_dados():
    st.subheader("📥 Origem de Dados")

    arquivo = st.file_uploader(
        "Anexar planilha do fornecedor",
        type=["xlsx", "xls", "csv"],
    )

    if not arquivo:
        return

    try:
        df = carregar_planilha(arquivo)
    except Exception as exc:
        st.error(f"Erro ao ler planilha: {exc}")
        return

    st.session_state.df_origem = df

    st.success(f"✅ Planilha carregada: {df.shape[0]} linhas")

    _render_preview_com_mapeamento(df)
