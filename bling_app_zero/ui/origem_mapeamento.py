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
    """
    Mantém compatibilidade com os diferentes estados já usados no projeto.
    Prioriza a chave principal e cai nos fallbacks.
    """
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
    return "preço" in nome or "preco" in nome


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


def _encontrar_coluna_existente(df: pd.DataFrame, coluna_modelo: str) -> str:
    """
    Tenta localizar no df já preparado uma coluna equivalente à coluna do modelo.
    Isso ajuda a preservar preço/deposito já calculados, mesmo com pequenas variações.
    """
    if not _safe_df(df):
        return ""

    alvo = str(coluna_modelo).strip().lower()

    for col in df.columns:
        if str(col).strip().lower() == alvo:
            return col

    if _is_coluna_preco(coluna_modelo):
        for col in df.columns:
            if _is_coluna_preco(col):
                return col

    if _is_coluna_deposito(coluna_modelo):
        for col in df.columns:
            if _is_coluna_deposito(col):
                return col

    return ""


def _montar_df_saida(df_origem: pd.DataFrame, df_modelo: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    bloqueios = _get_bloqueios()
    deposito = _get_deposito()

    df_preparado = st.session_state.get("df_saida")
    if _safe_df(df_preparado):
        df_base = df_preparado.copy()
    else:
        df_base = pd.DataFrame(index=df_origem.index)

    df_saida = pd.DataFrame(index=df_origem.index)

    for col in df_modelo.columns:
        origem = mapping.get(col, "")
        col_existente = _encontrar_coluna_existente(df_base, col)

        # 1) PREÇO AUTOMÁTICO: preserva o valor já calculado
        if _is_coluna_preco(col) and bloqueios.get("preco"):
            if col_existente and col_existente in df_base.columns:
                df_saida[col] = df_base[col_existente]
            else:
                df_saida[col] = ""
            continue

        # 2) DEPÓSITO MANUAL: sempre prevalece quando informado
        if _is_coluna_deposito(col) and deposito:
            df_saida[col] = deposito
            continue

        # 3) MAPEAMENTO MANUAL NORMAL
        if origem and origem in df_origem.columns:
            df_saida[col] = df_origem[origem]
            continue

        # 4) PRESERVA VALOR JÁ EXISTENTE EM DF_BASE QUANDO HOUVER
        if col_existente and col_existente in df_base.columns:
            df_saida[col] = df_base[col_existente]
            continue

        # 5) FALLBACK VAZIO
        df_saida[col] = ""

    # Reforço final do depósito
    if deposito:
        encontrou = False
        for col in df_saida.columns:
            if _is_coluna_deposito(col):
                df_saida[col] = deposito
                encontrou = True

        if not encontrou:
            # só cria se realmente o modelo não trouxer depósito
            pass

    df_saida = df_saida.reindex(columns=df_modelo.columns, fill_value="")
    return df_saida


def _colunas_origem_ja_usadas(
    mapping_atual: dict,
    coluna_atual_modelo: str,
    bloqueios: dict,
    deposito: str,
) -> set[str]:
    usadas = set()

    for campo_modelo, origem in mapping_atual.items():
        if campo_modelo == coluna_atual_modelo:
            continue

        if not origem:
            continue

        if _is_coluna_deposito(campo_modelo) and deposito:
            continue

        if _is_coluna_preco(campo_modelo) and bloqueios.get("preco"):
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
        st.warning("Anexe o modelo oficial antes de mapear.")
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
        if st.button("🧹 Limpar mapeamento", use_container_width=True, key="btn_limpar_mapeamento_manual"):
            st.session_state[mapping_state_key] = {}
            _limpar_mapeamento_widgets(colunas_modelo)
            st.rerun()

    with col_top_2:
        st.caption("Os campos automáticos permanecem bloqueados para evitar sobrescrita.")

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

                if _is_coluna_preco(col_modelo) and bloqueios.get("preco"):
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
                    mapping_atual=mapping_atual,
                    coluna_atual_modelo=col_modelo,
                    bloqueios=bloqueios,
                    deposito=deposito,
                )

                opcoes_livres = [col for col in colunas_origem if col not in usadas]

                if valor_inicial and valor_inicial not in opcoes_livres and valor_inicial in colunas_origem:
                    opcoes = ["", valor_inicial] + opcoes_livres
                else:
                    opcoes = [""] + opcoes_livres

                opcoes = list(dict.fromkeys(opcoes))
                indice = opcoes.index(valor_inicial) if valor_inicial in opcoes else 0

                escolhido = st.selectbox(
                    col_modelo,
                    opcoes,
                    index=indice,
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

    col_acao_1, col_acao_2 = st.columns(2)

    with col_acao_1:
        if st.button("⬅️ Voltar para origem", use_container_width=True, key="btn_voltar_origem"):
            st.session_state["etapa_origem"] = "upload"
            st.rerun()

    with col_acao_2:
        if st.button("➡️ Continuar para preview final", use_container_width=True, key="btn_ir_final"):
            st.session_state["df_saida"] = df_saida.copy()
            st.session_state["df_final"] = df_saida.copy()
            st.session_state["etapa_origem"] = "final"
            st.rerun()
