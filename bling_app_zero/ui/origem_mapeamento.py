from __future__ import annotations

import pandas as pd
import streamlit as st


def _safe_df(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0
    except Exception:
        return False


def _get_modelo():
    if st.session_state.get("tipo_operacao_bling") == "cadastro":
        return st.session_state.get("df_modelo_cadastro")
    return st.session_state.get("df_modelo_estoque")


def _get_deposito() -> str:
    for chave in ["deposito_nome", "deposito_nome_widget", "deposito_nome_manual"]:
        valor = str(st.session_state.get(chave, "") or "").strip()
        if valor:
            if chave != "deposito_nome":
                st.session_state["deposito_nome"] = valor
            return valor
    return ""


def _is_coluna_deposito(nome) -> bool:
    nome = str(nome).lower()
    return "deposit" in nome or "depós" in nome or "deposito" in nome


def _is_coluna_preco(nome) -> bool:
    nome = str(nome).lower()
    return any(
        p in nome
        for p in [
            "preço",
            "preco",
            "valor venda",
            "valor_venda",
            "preco venda",
            "preço venda",
            "price",
        ]
    )


def _get_mapping_state_key() -> str:
    tipo = str(st.session_state.get("tipo_operacao_bling", "padrao")).lower()
    return f"mapeamento_manual_{tipo}"


def _get_valor_widget_coluna(coluna_modelo: str, mapping_salvo: dict) -> str:
    val = st.session_state.get(f"map_{coluna_modelo}", None)
    if val is None:
        val = mapping_salvo.get(coluna_modelo, "")
    return str(val or "")


def _limpar_mapeamento_widgets(colunas_modelo: list[str]) -> None:
    for col in colunas_modelo:
        st.session_state.pop(f"map_{col}", None)


def _montar_df_saida(df_origem, df_modelo, mapping):
    deposito = _get_deposito()
    df_saida = pd.DataFrame(index=df_origem.index)

    for col in df_modelo.columns:
        origem = mapping.get(col, "")

        if _is_coluna_preco(col):
            df_saida[col] = ""
            continue

        if _is_coluna_deposito(col) and deposito:
            df_saida[col] = deposito
            continue

        df_saida[col] = df_origem[origem] if origem in df_origem.columns else ""

    return df_saida.reindex(columns=df_modelo.columns, fill_value="")


def _colunas_origem_ja_usadas(mapping_atual, coluna_modelo, deposito):
    usadas = set()

    for campo, origem in mapping_atual.items():
        if campo == coluna_modelo or not origem:
            continue
        if _is_coluna_deposito(campo) and deposito:
            continue
        if _is_coluna_preco(campo):
            continue
        usadas.add(origem)

    return usadas


def render_origem_mapeamento():
    etapa = str(st.session_state.get("etapa_origem", "")).lower()
    if etapa not in {"mapeamento", ""}:
        return

    df_origem = st.session_state.get("df_origem")
    df_modelo = _get_modelo()

    if not _safe_df(df_origem):
        st.warning("Nenhuma planilha de origem carregada.")
        return

    if not _safe_df(df_modelo):
        st.error("⚠️ Anexe o modelo do Bling antes de continuar.")
        return

    st.markdown("## 🔗 Mapeamento de colunas")

    deposito = _get_deposito()
    colunas_modelo = list(df_modelo.columns)
    colunas_origem = list(df_origem.columns)

    mapping_key = _get_mapping_state_key()
    mapping_salvo = st.session_state.get(mapping_key, {}) or {}

    # =========================================================
    # TOPO
    # =========================================================
    top1, top2 = st.columns([1, 2])

    with top1:
        if st.button("🧹 Limpar", use_container_width=True):
            st.session_state[mapping_key] = {}
            _limpar_mapeamento_widgets(colunas_modelo)
            st.rerun()

    with top2:
        st.caption("Campos automáticos (preço e depósito) já protegidos.")

    # =========================================================
    # GRID MAPEAMENTO
    # =========================================================
    mapping_atual = {}

    for i in range(0, len(colunas_modelo), 2):
        cols = st.columns(2)

        for j in range(2):
            if i + j >= len(colunas_modelo):
                continue

            col_modelo = colunas_modelo[i + j]

            with cols[j]:

                # BLOQUEIO DEPÓSITO
                if _is_coluna_deposito(col_modelo) and deposito:
                    st.text_input(col_modelo, value=deposito, disabled=True)
                    mapping_atual[col_modelo] = ""
                    continue

                # BLOQUEIO PREÇO
                if _is_coluna_preco(col_modelo):
                    st.text_input(col_modelo, value="Calculado automaticamente", disabled=True)
                    mapping_atual[col_modelo] = ""
                    continue

                valor = _get_valor_widget_coluna(col_modelo, mapping_salvo)

                usadas = _colunas_origem_ja_usadas(mapping_atual, col_modelo, deposito)

                opcoes = [""] + [c for c in colunas_origem if c not in usadas]

                if valor and valor not in opcoes:
                    opcoes.insert(1, valor)

                escolhido = st.selectbox(
                    col_modelo,
                    list(dict.fromkeys(opcoes)),
                    index=opcoes.index(valor) if valor in opcoes else 0,
                    key=f"map_{col_modelo}",
                )

                mapping_atual[col_modelo] = escolhido

    st.session_state[mapping_key] = mapping_atual.copy()

    # =========================================================
    # SAÍDA
    # =========================================================
    try:
        df_saida = _montar_df_saida(df_origem, df_modelo, mapping_atual)
    except Exception as e:
        st.error(f"Erro ao montar: {e}")
        return

    st.session_state["df_saida"] = df_saida.copy()
    st.session_state["df_final"] = df_saida.copy()

    # =========================================================
    # PREVIEW
    # =========================================================
    with st.expander("📦 Preview final", expanded=False):
        st.dataframe(df_saida.head(15), use_container_width=True, hide_index=True)

    # =========================================================
    # AÇÕES
    # =========================================================
    c1, c2 = st.columns(2)

    with c1:
        if st.button("⬅️ Voltar", use_container_width=True):
            st.session_state["etapa_origem"] = "upload"
            st.rerun()

    with c2:
        if st.button("➡️ Finalizar", use_container_width=True):
            st.session_state["etapa_origem"] = "final"
            st.rerun()
