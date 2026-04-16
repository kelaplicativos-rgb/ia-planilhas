
from __future__ import annotations

import pandas as pd
import streamlit as st


def _to_float(valor: str) -> float:
    texto = str(valor or "").strip()
    if not texto:
        return 0.0
    texto = texto.replace("R$", "").replace(" ", "")
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(",", ".")
    try:
        return float(texto)
    except Exception:
        return 0.0


def _fmt_preco(valor: float) -> str:
    return f"{valor:.2f}".replace(".", ",")


def render_origem_precificacao() -> None:
    st.markdown("### Precificação")
    st.caption("Preencha os campos abaixo. O sistema só seguirá quando os dados obrigatórios forem informados.")

    df_origem = st.session_state.get("df_origem")
    if df_origem is None or df_origem.empty:
        st.warning("Envie a planilha de origem primeiro.")
        return

    colunas = list(df_origem.columns)

    with st.container(border=True):
        preco_coluna = st.selectbox(
            "Coluna da planilha que contém o preço base",
            [""] + colunas,
            index=([""] + colunas).index(st.session_state.get("preco_coluna_origem", "")) if st.session_state.get("preco_coluna_origem", "") in colunas else 0,
        )
        imposto = st.text_input("Impostos (%)", value=st.session_state.get("preco_imposto_pct", ""))
        margem = st.text_input("Margem de lucro (%)", value=st.session_state.get("preco_margem_pct", ""))
        custo_fixo = st.text_input("Custo fixo (R$)", value=st.session_state.get("preco_custo_fixo", ""))
        taxa_fixa = st.text_input("Taxa extra (R$)", value=st.session_state.get("preco_taxa_fixa", ""))

        st.session_state["preco_coluna_origem"] = preco_coluna
        st.session_state["preco_imposto_pct"] = imposto
        st.session_state["preco_margem_pct"] = margem
        st.session_state["preco_custo_fixo"] = custo_fixo
        st.session_state["preco_taxa_fixa"] = taxa_fixa

        campos_ok = all(
            [
                bool(preco_coluna),
                str(imposto).strip() != "",
                str(margem).strip() != "",
                str(custo_fixo).strip() != "",
                str(taxa_fixa).strip() != "",
            ]
        )

        if not campos_ok:
            st.info("Preencha todos os campos de precificação para liberar o próximo fluxo.")
            st.session_state["df_origem_precificado"] = None
            return

        base = df_origem.copy()
        imposto_f = _to_float(imposto) / 100.0
        margem_f = _to_float(margem) / 100.0
        custo_fixo_f = _to_float(custo_fixo)
        taxa_fixa_f = _to_float(taxa_fixa)

        def calc(v):
            preco = _to_float(v)
            preco = preco + (preco * imposto_f)
            preco = preco + (preco * margem_f)
            preco = preco + custo_fixo_f + taxa_fixa_f
            return _fmt_preco(preco)

        base["__preco_calculado_bling__"] = base[preco_coluna].apply(calc)
        st.session_state["df_origem_precificado"] = base

        st.success("Precificação aplicada. Agora o fluxo pode seguir.")
        with st.expander("Ver prévia da precificação", expanded=False):
            preview_cols = [preco_coluna, "__preco_calculado_bling__"]
            st.dataframe(base[preview_cols].head(50), use_container_width=True)


