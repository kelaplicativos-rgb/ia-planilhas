from __future__ import annotations

from io import BytesIO
import re

import pandas as pd
import streamlit as st

from bling_app_zero.core.mapeamento_auto import sugestao_automatica


# ==========================================================
# HELPERS
# ==========================================================
def _safe_dataframe_preview(df: pd.DataFrame, rows: int = 20):
    if df is None or df.empty:
        return pd.DataFrame()
    return df.head(rows)


def _build_log():
    logs = st.session_state.get("logs", [])
    texto = "\n".join(logs) if logs else "Sem logs"
    return texto


def _safe_df(df):
    try:
        if df is None or df.empty:
            return None
        return df
    except Exception:
        return None


def _normalizar_nome(texto: str) -> str:
    texto = str(texto or "").strip().lower()
    texto = re.sub(r"\s+", " ", texto)
    return texto


def _obter_modelo_ativo() -> pd.DataFrame | None:
    operacao = st.session_state.get("tipo_operacao_bling", "cadastro")
    if operacao == "cadastro":
        return _safe_df(st.session_state.get("df_modelo_cadastro"))
    return _safe_df(st.session_state.get("df_modelo_estoque"))


def _obter_nome_modelo_ativo() -> str:
    operacao = st.session_state.get("tipo_operacao_bling", "cadastro")
    if operacao == "cadastro":
        return st.session_state.get("modelo_cadastro_nome", "")
    return st.session_state.get("modelo_estoque_nome", "")


def _obter_sugestoes(df_origem: pd.DataFrame, df_modelo: pd.DataFrame) -> dict[str, str]:
    try:
        sugestoes = sugestao_automatica(df_origem, list(df_modelo.columns))
        if isinstance(sugestoes, dict):
            return {str(k): str(v) for k, v in sugestoes.items() if k and v}
    except Exception:
        pass
    return {}


def _converter_sugestoes_origem_para_destino(
    sugestoes_origem_destino: dict[str, str],
    colunas_modelo: list[str],
) -> dict[str, str]:
    destino_origem = {}
    alvos_validos = set(map(str, colunas_modelo))

    for origem, destino in sugestoes_origem_destino.items():
        if str(destino) in alvos_validos and str(destino) not in destino_origem:
            destino_origem[str(destino)] = str(origem)

    return destino_origem


def _coluna_modelo_parece_deposito(nome_coluna: str) -> bool:
    nome = _normalizar_nome(nome_coluna)
    return "deposito" in nome or "depósito" in nome


def _montar_saida_no_formato_modelo(
    df_origem: pd.DataFrame,
    df_modelo: pd.DataFrame,
    mapeamento_destino_origem: dict[str, str],
) -> pd.DataFrame:
    # mantém exatamente a estrutura de colunas do modelo
    saida = pd.DataFrame(index=range(len(df_origem)), columns=list(df_modelo.columns))

    # replica valores padrão da primeira linha do modelo, se existirem
    if len(df_modelo) > 0:
        primeira_linha = df_modelo.iloc[0]
        for col in saida.columns:
            valor_padrao = primeira_linha.get(col, None)
            if pd.notna(valor_padrao) and str(valor_padrao).strip() != "":
                saida[col] = valor_padrao

    # preenche colunas mapeadas
    for col_destino in saida.columns:
        col_origem = mapeamento_destino_origem.get(col_destino, "")
        if col_origem and col_origem in df_origem.columns:
            saida[col_destino] = df_origem[col_origem].values

    # regra do depósito no modelo de estoque
    deposito_manual = str(st.session_state.get("deposito_nome_manual", "")).strip()
    if deposito_manual:
        for col in saida.columns:
            if _coluna_modelo_parece_deposito(col):
                saida[col] = deposito_manual

    return saida


# ==========================================================
# MAIN
# ==========================================================
def render_origem_mapeamento():
    df_origem = _safe_df(st.session_state.get("df_origem"))
    df_fluxo = _safe_df(st.session_state.get("df_saida"))
    df_modelo = _obter_modelo_ativo()
    operacao = st.session_state.get("tipo_operacao_bling", "cadastro")
    operacao_label = (
        "Cadastro / atualização de produtos"
        if operacao == "cadastro"
        else "Atualização de estoque"
    )

    if df_origem is None:
        st.warning("Nenhum dado disponível para mapeamento.")
        return

    if df_fluxo is None:
        st.session_state["df_saida"] = df_origem.copy()
        df_fluxo = df_origem.copy()

    st.success(f"Fluxo selecionado: {operacao_label}")

    if df_modelo is None:
        st.warning("Anexe primeiro a planilha modelo da operação escolhida para continuar.")
        if st.button("⬅️ Voltar", width="stretch", key="btn_voltar_sem_modelo"):
            st.session_state["etapa_origem"] = "upload"
            st.rerun()
        return

    nome_modelo = _obter_nome_modelo_ativo()
    if nome_modelo:
        st.info(f"Modelo ativo: {nome_modelo}")

    st.markdown("### Preview da origem")
    st.dataframe(_safe_dataframe_preview(df_origem), width="stretch")

    st.markdown("### Preview do modelo")
    st.dataframe(_safe_dataframe_preview(df_modelo), width="stretch")

    st.divider()
    st.markdown("### Mapeamento automático e manual")

    sugestoes_auto = _obter_sugestoes(df_origem, df_modelo)
    sugestoes_destino_origem = _converter_sugestoes_origem_para_destino(
        sugestoes_auto,
        list(df_modelo.columns),
    )

    opcoes_origem = [""] + [str(c) for c in df_origem.columns]
    mapeamento_final_destino_origem: dict[str, str] = {}

    for col_destino in df_modelo.columns:
        valor_inicial = sugestoes_destino_origem.get(str(col_destino), "")
        if valor_inicial not in opcoes_origem:
            valor_inicial = ""

        escolha = st.selectbox(
            f"{col_destino}",
            options=opcoes_origem,
            index=opcoes_origem.index(valor_inicial) if valor_inicial in opcoes_origem else 0,
            key=f"map_destino_{col_destino}",
        )

        if escolha:
            mapeamento_final_destino_origem[str(col_destino)] = str(escolha)

    st.session_state["mapeamento_manual"] = mapeamento_final_destino_origem

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        if st.button("✅ Gerar saída no formato do modelo", width="stretch"):
            try:
                df_saida_final = _montar_saida_no_formato_modelo(
                    df_origem=df_origem,
                    df_modelo=df_modelo,
                    mapeamento_destino_origem=mapeamento_final_destino_origem,
                )

                st.session_state["df_saida"] = df_saida_final
                st.success("Saída gerada com sucesso no formato do modelo.")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao gerar saída: {e}")

    with col2:
        if st.button("⬅️ Voltar", width="stretch", key="btn_voltar_mapeamento"):
            st.session_state["etapa_origem"] = "upload"
            st.rerun()

    df_saida_final = _safe_df(st.session_state.get("df_saida"))

    if df_saida_final is not None:
        st.divider()
        st.markdown("### Preview final no formato do modelo")
        st.dataframe(_safe_dataframe_preview(df_saida_final), width="stretch")

        col3, col4 = st.columns(2)

        with col3:
            try:
                buffer = BytesIO()
                df_saida_final.to_excel(buffer, index=False)
                buffer.seek(0)

                nome_arquivo = "saida.xlsx"
                if operacao == "cadastro":
                    nome_arquivo = "cadastro_bling.xlsx"
                elif operacao == "estoque":
                    nome_arquivo = "estoque_bling.xlsx"

                st.download_button(
                    "⬇️ Baixar planilha final",
                    buffer,
                    nome_arquivo,
                    width="stretch",
                    key="btn_download_planilha_final",
                )
            except Exception as e:
                st.error(f"Erro ao gerar Excel: {e}")

        with col4:
            st.download_button(
                "📄 Baixar log",
                _build_log(),
                "log.txt",
                width="stretch",
                key="btn_download_log_mapeamento",
            )
