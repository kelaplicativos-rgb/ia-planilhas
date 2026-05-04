from __future__ import annotations

import re

import pandas as pd
import streamlit as st


def _norm(value) -> str:
    text = str(value or "").strip().lower()
    trans = str.maketrans("áàãâéêíóôõúç", "aaaaeeiooouc")
    return re.sub(r"[^a-z0-9]+", " ", text.translate(trans)).strip()


def _is_estoque_operation() -> bool:
    tipo = _norm(st.session_state.get("tipo_operacao") or st.session_state.get("tipo_operacao_bling") or "")
    return "estoque" in tipo


def _safe_int(value, default: int) -> int:
    try:
        return max(0, int(value))
    except Exception:
        return default


def _quantity_columns(df: pd.DataFrame) -> list[str]:
    cols: list[str] = []
    for col in df.columns:
        n = _norm(col)
        if n in {"quantidade", "qtd", "qtde", "estoque", "saldo", "balanco", "balanco estoque"}:
            cols.append(str(col))
        elif "quantidade" in n or "estoque" in n or "saldo" in n or "balanco" in n:
            cols.append(str(col))
    return cols


def _status_columns(df: pd.DataFrame) -> list[str]:
    cols: list[str] = []
    for col in df.columns:
        n = _norm(col)
        if "status" in n or "disponibilidade" in n or "availability" in n or "origem estoque" in n:
            cols.append(str(col))
    return cols


def _status_row(row: pd.Series, cols: list[str]) -> str:
    return _norm(" ".join(str(row.get(col, "") or "") for col in cols))


def _tem_numero(row: pd.Series, cols: list[str]) -> bool:
    for col in cols:
        value = str(row.get(col, "") or "").strip()
        if re.fullmatch(r"\d+(?:[\.,]\d+)?", value):
            return True
    return False


def _classe_status(status: str) -> str:
    if not status:
        return ""
    if any(x in status for x in ("sem estoque", "indisponivel", "esgotado", "fora de estoque", "outofstock", "soldout", "avise me")):
        return "zero"
    if any(x in status for x in ("baixo", "ultimas unidades", "poucas unidades", "limitedavailability")):
        return "baixo"
    if any(x in status for x in ("disponivel", "em estoque", "comprar", "instock", "in stock")):
        return "disponivel"
    return ""


def aplicar_estoque_inteligente_final(df_final: pd.DataFrame, disponivel: int, baixo: int, sobrescrever: bool) -> pd.DataFrame:
    if not isinstance(df_final, pd.DataFrame) or df_final.empty:
        return df_final

    base = df_final.copy().fillna("")
    qtd_cols = _quantity_columns(base)
    st_cols = _status_columns(base)

    if not qtd_cols:
        st.session_state["estoque_inteligente_alterados"] = 0
        st.session_state["estoque_inteligente_coluna_alvo"] = ""
        st.session_state["estoque_inteligente_origens"] = []
        return base

    alvo = qtd_cols[0]
    alterados = 0
    origem = []

    for idx, row in base.iterrows():
        if not sobrescrever and _tem_numero(row, qtd_cols):
            origem.append("preservado")
            continue

        classe = _classe_status(_status_row(row, st_cols))
        if classe == "zero":
            base.at[idx, alvo] = "0"
            alterados += 1
            origem.append("manual_zero")
        elif classe == "baixo":
            base.at[idx, alvo] = str(baixo)
            alterados += 1
            origem.append("manual_baixo")
        elif classe == "disponivel":
            base.at[idx, alvo] = str(disponivel)
            alterados += 1
            origem.append("manual_disponivel")
        elif sobrescrever:
            base.at[idx, alvo] = str(disponivel)
            alterados += 1
            origem.append("manual_padrao")
        else:
            origem.append("sem_alteracao")

    st.session_state["estoque_inteligente_alterados"] = alterados
    st.session_state["estoque_inteligente_coluna_alvo"] = alvo
    st.session_state["estoque_inteligente_origens"] = origem
    return base


def render_estoque_inteligente_final(df_final: pd.DataFrame) -> pd.DataFrame:
    if not _is_estoque_operation():
        return df_final
    if not isinstance(df_final, pd.DataFrame) or df_final.empty:
        return df_final

    with st.container(border=True):
        st.markdown("### Estoque inteligente")
        st.caption("Último ajuste antes do download. Ao aplicar, o valor manual sobrescreve o estoque capturado no resultado final.")

        c1, c2 = st.columns(2)
        with c1:
            disponivel = st.number_input(
                "Estoque para Disponível",
                min_value=0,
                value=_safe_int(st.session_state.get("estoque_padrao_disponivel", 5), 5),
                step=1,
                key="preview_estoque_padrao_disponivel",
            )
        with c2:
            baixo = st.number_input(
                "Estoque para Baixo",
                min_value=0,
                value=_safe_int(st.session_state.get("estoque_padrao_baixo", 1), 1),
                step=1,
                key="preview_estoque_padrao_baixo",
            )

        sobrescrever = st.checkbox(
            "Sobrescrever estoque capturado com estes valores",
            value=True,
            key="preview_estoque_sobrescrever_capturado",
        )

        st.session_state["estoque_padrao_disponivel"] = int(disponivel)
        st.session_state["estoque_padrao_baixo"] = int(baixo)

        df_ajustado = aplicar_estoque_inteligente_final(df_final, int(disponivel), int(baixo), bool(sobrescrever))
        alterados = int(st.session_state.get("estoque_inteligente_alterados", 0) or 0)
        coluna = str(st.session_state.get("estoque_inteligente_coluna_alvo", "") or "")

        if coluna:
            st.success(f"Aplicado em {alterados} linha(s). Coluna ajustada: {coluna}.")
        else:
            st.warning("Nenhuma coluna de quantidade/estoque foi encontrada no modelo final.")

    return df_ajustado
