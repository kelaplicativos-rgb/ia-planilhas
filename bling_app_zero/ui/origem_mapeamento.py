from __future__ import annotations

import pandas as pd
import streamlit as st


def _safe_df(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0
    except Exception:
        return False


def _normalizar_texto_coluna(valor) -> str:
    try:
        texto = str(valor if valor is not None else "").strip()
        texto = texto.replace("\n", " ").replace("\r", " ")
        while "  " in texto:
            texto = texto.replace("  ", " ")
        return texto
    except Exception:
        return ""


def _coluna_parece_generica(col) -> bool:
    texto = _normalizar_texto_coluna(col).lower()

    if texto == "":
        return True

    if texto.isdigit():
        return True

    if texto.startswith("unnamed:"):
        return True

    if texto in {"none", "nan"}:
        return True

    return False


def _linha_parece_cabecalho(valores: list) -> bool:
    try:
        if not valores:
            return False

        textos = [_normalizar_texto_coluna(v) for v in valores]
        preenchidos = [t for t in textos if t]

        if not preenchidos:
            return False

        unicos = len(set(preenchidos))
        proporcao_unicos = unicos / max(len(preenchidos), 1)

        # cabeçalho tende a ser mais textual e mais único
        qtd_textuais = sum(1 for t in preenchidos if not t.isdigit())
        proporcao_textual = qtd_textuais / max(len(preenchidos), 1)

        return proporcao_unicos >= 0.7 and proporcao_textual >= 0.7
    except Exception:
        return False


def _promover_primeira_linha_para_header_se_preciso(df: pd.DataFrame | None) -> pd.DataFrame | None:
    try:
        if not _safe_df(df):
            return df

        df2 = df.copy()

        colunas = list(df2.columns)
        qtd_genericas = sum(1 for c in colunas if _coluna_parece_generica(c))
        proporcao_genericas = qtd_genericas / max(len(colunas), 1)

        if proporcao_genericas < 0.6:
            return df2

        primeira_linha = df2.iloc[0].tolist() if len(df2) > 0 else []
        if not _linha_parece_cabecalho(primeira_linha):
            return df2

        novos_nomes = []
        usados = set()

        for i, valor in enumerate(primeira_linha):
            nome = _normalizar_texto_coluna(valor)
            if not nome:
                nome = f"Coluna_{i + 1}"

            base = nome
            contador = 2
            while nome in usados:
                nome = f"{base}_{contador}"
                contador += 1

            usados.add(nome)
            novos_nomes.append(nome)

        df2.columns = novos_nomes
        df2 = df2.iloc[1:].reset_index(drop=True)

        return df2
    except Exception:
        return df


def _normalizar_nomes_colunas(df: pd.DataFrame | None) -> pd.DataFrame | None:
    try:
        if not _safe_df(df):
            return df

        df2 = df.copy()
        usadas = set()
        novas = []

        for i, col in enumerate(df2.columns):
            nome = _normalizar_texto_coluna(col)
            if not nome:
                nome = f"Coluna_{i + 1}"

            base = nome
            contador = 2
            while nome in usadas:
                nome = f"{base}_{contador}"
                contador += 1

            usadas.add(nome)
            novas.append(nome)

        df2.columns = novas
        return df2
    except Exception:
        return df


def _preparar_df_para_mapeamento(df: pd.DataFrame | None) -> pd.DataFrame | None:
    try:
        if not _safe_df(df):
            return df

        df2 = _promover_primeira_linha_para_header_se_preciso(df)
        df2 = _normalizar_nomes_colunas(df2)
        return df2
    except Exception:
        return df


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


def _widget_key_para_coluna(coluna_modelo: str) -> str:
    texto = _normalizar_texto_coluna(coluna_modelo)
    texto = texto.replace(" ", "_").replace("/", "_").replace("\\", "_")
    texto = texto.replace(".", "_").replace(":", "_").replace("-", "_")
    return f"map_{texto}"


def _get_valor_widget_coluna(coluna_modelo: str, mapping_salvo: dict) -> str:
    chave = _widget_key_para_coluna(coluna_modelo)
    val = st.session_state.get(chave, None)
    if val is None:
        val = mapping_salvo.get(coluna_modelo, "")
    return str(val or "")


def _limpar_mapeamento_widgets(colunas_modelo: list[str]) -> None:
    for col in colunas_modelo:
        st.session_state.pop(_widget_key_para_coluna(col), None)


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

    df_origem_bruto = st.session_state.get("df_origem")
    df_modelo_bruto = _get_modelo()

    if not _safe_df(df_origem_bruto):
        st.warning("Nenhuma planilha de origem carregada.")
        return

    if not _safe_df(df_modelo_bruto):
        st.error("⚠️ Anexe o modelo do Bling antes de continuar.")
        return

    df_origem = _preparar_df_para_mapeamento(df_origem_bruto)
    df_modelo = _preparar_df_para_mapeamento(df_modelo_bruto)

    if not _safe_df(df_origem):
        st.error("⚠️ A planilha de origem ficou inválida após a normalização.")
        return

    if not _safe_df(df_modelo):
        st.error("⚠️ O modelo do Bling ficou inválido após a normalização.")
        return

    # mantém no estado os DFs já normalizados para o restante do fluxo
    st.session_state["df_origem"] = df_origem.copy()
    if st.session_state.get("tipo_operacao_bling") == "cadastro":
        st.session_state["df_modelo_cadastro"] = df_modelo.copy()
    else:
        st.session_state["df_modelo_estoque"] = df_modelo.copy()

    st.markdown("## 🔗 Mapeamento de colunas")

    deposito = _get_deposito()
    colunas_modelo = list(df_modelo.columns)
    colunas_origem = list(df_origem.columns)

    mapping_key = _get_mapping_state_key()
    mapping_salvo = st.session_state.get(mapping_key, {}) or {}

    # remove mapeamentos inválidos antigos
    mapping_salvo = {
        campo: origem
        for campo, origem in mapping_salvo.items()
        if campo in colunas_modelo and (origem in colunas_origem or origem == "")
    }

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
                    st.text_input(
                        col_modelo,
                        value=deposito,
                        disabled=True,
                        key=f"deposito_fix_{_widget_key_para_coluna(col_modelo)}",
                    )
                    mapping_atual[col_modelo] = ""
                    continue

                # BLOQUEIO PREÇO
                if _is_coluna_preco(col_modelo):
                    st.text_input(
                        col_modelo,
                        value="Calculado automaticamente",
                        disabled=True,
                        key=f"preco_fix_{_widget_key_para_coluna(col_modelo)}",
                    )
                    mapping_atual[col_modelo] = ""
                    continue

                valor = _get_valor_widget_coluna(col_modelo, mapping_salvo)
                usadas = _colunas_origem_ja_usadas(mapping_atual, col_modelo, deposito)

                opcoes = [""] + [c for c in colunas_origem if c not in usadas]

                if valor and valor not in opcoes:
                    opcoes.insert(1, valor)

                opcoes = list(dict.fromkeys(opcoes))
                chave_widget = _widget_key_para_coluna(col_modelo)

                escolhido = st.selectbox(
                    col_modelo,
                    opcoes,
                    index=opcoes.index(valor) if valor in opcoes else 0,
                    key=chave_widget,
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
