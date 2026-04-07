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
    candidatos = [
        "deposito_nome",
        "deposito_nome_widget",
        "deposito_nome_manual",
    ]

    for chave in candidatos:
        valor = str(st.session_state.get(chave, "") or "").strip()
        if valor:
            if chave != "deposito_nome":
                st.session_state["deposito_nome"] = valor
            return valor

    return ""


def _is_coluna_deposito(nome) -> bool:
    nome = str(nome).strip().lower()
    return "deposit" in nome or "depós" in nome or "deposito" in nome


def _is_coluna_preco(nome) -> bool:
    nome = str(nome).strip().lower()

    palavras = [
        "preço",
        "preco",
        "valor venda",
        "valor_venda",
        "preco venda",
        "preço venda",
        "price",
    ]

    return any(p in nome for p in palavras)


def _get_mapping_state_key() -> str:
    tipo = str(st.session_state.get("tipo_operacao_bling", "padrao") or "padrao").strip().lower()
    return f"mapeamento_manual_{tipo}"


def _get_bloqueios() -> dict:
    bloqueios = st.session_state.get("bloquear_campos_auto", {})
    if isinstance(bloqueios, dict):
        return bloqueios
    return {}


def _get_valor_widget_coluna(coluna_modelo: str, mapping_salvo: dict) -> str:
    chave = f"map_{coluna_modelo}"
    valor_widget = st.session_state.get(chave, None)

    if valor_widget is None:
        valor_widget = mapping_salvo.get(coluna_modelo, "")

    if valor_widget is None:
        return ""

    return str(valor_widget)


def _limpar_mapeamento_widgets(colunas_modelo: list[str]) -> None:
    for col in colunas_modelo:
        st.session_state.pop(f"map_{col}", None)


# 🔥 CORREÇÃO CRÍTICA AQUI
def _montar_df_saida(df_origem: pd.DataFrame, df_modelo: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    bloqueios = _get_bloqueios()
    deposito = _get_deposito()

    # 🚨 BASE AGORA É SEMPRE NOVA (MODELO)
    df_saida = pd.DataFrame(index=df_origem.index)

    for col in df_modelo.columns:
        origem = mapping.get(col, "")

        # PREÇO
        if _is_coluna_preco(col):
            df_saida[col] = ""
            continue

        # DEPÓSITO
        if _is_coluna_deposito(col) and deposito:
            df_saida[col] = deposito
            continue

        # MAPEAMENTO
        if origem and origem in df_origem.columns:
            df_saida[col] = df_origem[origem]
        else:
            df_saida[col] = ""

    # GARANTIA FINAL (ordem do modelo)
    df_saida = df_saida.reindex(columns=df_modelo.columns, fill_value="")

    return df_saida


def _colunas_origem_ja_usadas(mapping_atual, coluna_atual_modelo, bloqueios, deposito):
    usadas = set()

    for campo_modelo, origem in mapping_atual.items():
        if campo_modelo == coluna_atual_modelo:
            continue

        if not origem:
            continue

        if _is_coluna_deposito(campo_modelo) and deposito:
            continue

        if _is_coluna_preco(campo_modelo):
            continue

        usadas.add(str(origem))

    return usadas


def render_origem_mapeamento():
    etapa = str(st.session_state.get("etapa_origem", "") or "").strip().lower()
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

    st.markdown("### 🔗 Mapeamento")

    deposito = _get_deposito()
    bloqueios = _get_bloqueios()
    colunas_modelo = list(df_modelo.columns)
    colunas_origem = list(df_origem.columns)

    mapping_state_key = _get_mapping_state_key()
    mapping_salvo = st.session_state.get(mapping_state_key, {})
    if not isinstance(mapping_salvo, dict):
        mapping_salvo = {}

    col_top_1, col_top_2 = st.columns(2)

    with col_top_1:
        if st.button("🧹 Limpar mapeamento", use_container_width=True):
            st.session_state[mapping_state_key] = {}
            _limpar_mapeamento_widgets(colunas_modelo)
            st.rerun()

    with col_top_2:
        st.caption("Campos automáticos (preço e depósito) protegidos.")

    mapping_atual = {}

    for i in range(0, len(colunas_modelo), 2):
        cols = st.columns(2)

        for j in range(2):
            if i + j >= len(colunas_modelo):
                continue

            col_modelo = colunas_modelo[i + j]

            with cols[j]:

                if _is_coluna_deposito(col_modelo) and deposito:
                    st.text_input(
                        col_modelo,
                        value=deposito,
                        disabled=True,
                        key=f"lock_dep_{col_modelo}",
                    )
                    mapping_atual[col_modelo] = ""
                    continue

                if _is_coluna_preco(col_modelo):
                    st.text_input(
                        col_modelo,
                        value="Calculado automaticamente",
                        disabled=True,
                        key=f"lock_preco_{col_modelo}",
                    )
                    mapping_atual[col_modelo] = ""
                    continue

                valor_inicial = _get_valor_widget_coluna(col_modelo, mapping_salvo)

                usadas = _colunas_origem_ja_usadas(
                    mapping_atual,
                    col_modelo,
                    bloqueios,
                    deposito,
                )

                opcoes = [""] + [c for c in colunas_origem if c not in usadas]

                if valor_inicial and valor_inicial not in opcoes:
                    opcoes.insert(1, valor_inicial)

                escolhido = st.selectbox(
                    col_modelo,
                    list(dict.fromkeys(opcoes)),
                    index=opcoes.index(valor_inicial) if valor_inicial in opcoes else 0,
                    key=f"map_{col_modelo}",
                )

                mapping_atual[col_modelo] = escolhido

    st.session_state[mapping_state_key] = mapping_atual.copy()

    try:
        df_saida = _montar_df_saida(df_origem, df_modelo, mapping_atual)
    except Exception as e:
        st.error(f"Erro ao montar o mapeamento: {e}")
        return

    st.session_state["df_saida"] = df_saida.copy()
    st.session_state["df_final"] = df_saida.copy()

    with st.expander("📦 Preview final", expanded=False):
        st.dataframe(df_saida.head(20), use_container_width=True, hide_index=True)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("⬅️ Voltar"):
            st.session_state["etapa_origem"] = "upload"
            st.rerun()

    with col2:
        if st.button("➡️ Finalizar"):
            st.session_state["etapa_origem"] = "final"
            st.rerun()
