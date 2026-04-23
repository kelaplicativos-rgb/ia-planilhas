from __future__ import annotations

import pandas as pd
import streamlit as st


def _df_valido(df: object) -> bool:
    return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0


def _identificar_colunas_descricao(df: pd.DataFrame) -> list[str]:
    colunas = []
    for c in df.columns:
        nome = str(c).lower()
        if any(k in nome for k in ["descr", "titulo", "nome", "resumo"]):
            colunas.append(c)
    return colunas


def _gerar_descricao_persuasiva(texto: str, estilo: str) -> str:
    """
    Simulação inicial (fallback local).
    Aqui depois você pode plugar GPT real.
    """
    texto = str(texto or "").strip()
    if not texto:
        return texto

    if estilo == "Mais vendedor":
        return f"{texto}. Produto ideal para quem busca qualidade, praticidade e excelente custo-benefício."
    elif estilo == "Mais técnico":
        return f"{texto}. Desenvolvido com foco em desempenho, eficiência e confiabilidade."
    elif estilo == "Mais curto":
        return texto
    else:  # marketplace
        return f"{texto}. Perfeito para uso diário, com ótimo desempenho e praticidade."



def _aplicar_ia_em_colunas(
    df_base: pd.DataFrame,
    colunas: list[str],
    estilo: str,
    apenas_vazios: bool,
) -> pd.DataFrame:

    df_saida = df_base.copy().fillna("")

    for coluna in colunas:
        if coluna not in df_saida.columns:
            continue

        novos_valores = []

        for valor in df_saida[coluna]:
            valor_str = str(valor or "").strip()

            if apenas_vazios and valor_str != "":
                novos_valores.append(valor_str)
                continue

            novo = _gerar_descricao_persuasiva(valor_str, estilo)
            novos_valores.append(novo)

        df_saida[coluna] = novos_valores

    return df_saida



def render_ai_descricao(df_final: pd.DataFrame) -> pd.DataFrame:

    if not _df_valido(df_final):
        return df_final

    st.markdown("### ✨ Otimização de Descrição com IA")

    df_base = st.session_state.get("df_final", df_final).copy().fillna("")

    colunas_desc = _identificar_colunas_descricao(df_base)

    if not colunas_desc:
        st.info("Nenhuma coluna de descrição identificada para otimização.")
        return df_base

    st.caption(f"Colunas detectadas: {', '.join(colunas_desc)}")

    estilo = st.selectbox(
        "Estilo da descrição",
        options=[
            "Mais vendedor",
            "Mais técnico",
            "Mais marketplace",
            "Mais curto",
        ],
        key="ia_desc_estilo",
    )

    apenas_vazios = st.checkbox(
        "Aplicar apenas onde estiver vazio",
        value=False,
        key="ia_desc_apenas_vazios",
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button("👁️ Gerar prévia com IA", use_container_width=True):

            df_preview = _aplicar_ia_em_colunas(
                df_base=df_base,
                colunas=colunas_desc,
                estilo=estilo,
                apenas_vazios=apenas_vazios,
            )

            st.session_state["df_preview_ia_desc"] = df_preview
            st.success("Prévia gerada com sucesso.")

    with col2:
        if st.button("✅ Aplicar IA nas descrições", use_container_width=True):

            df_preview = st.session_state.get("df_preview_ia_desc")

            if not _df_valido(df_preview):
                st.warning("Gere a prévia antes de aplicar.")
                return df_base

            # 🔒 preserva manual e só substitui colunas de descrição
            df_resultado = df_base.copy()

            for coluna in colunas_desc:
                if coluna in df_preview.columns:
                    df_resultado[coluna] = df_preview[coluna]

            st.session_state["df_final"] = df_resultado.copy()
            st.success("Descrições atualizadas com IA.")
            st.rerun()

    # Preview visual
    df_preview = st.session_state.get("df_preview_ia_desc")

    if _df_valido(df_preview):
        with st.expander("🔎 Visualizar prévia IA", expanded=False):
            st.dataframe(df_preview.head(10), use_container_width=True)

    return st.session_state.get("df_final", df_base)
