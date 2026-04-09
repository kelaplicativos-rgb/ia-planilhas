from __future__ import annotations

import pandas as pd
import streamlit as st


ETAPAS_VALIDAS_ORIGEM = {"origem", "mapeamento"}


def _safe_df(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0
    except Exception:
        return False


def _safe_df_com_linhas(df) -> bool:
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
    if texto == "" or texto.isdigit() or texto.startswith("unnamed:"):
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
        qtd_textuais = sum(1 for t in preenchidos if not t.isdigit())
        proporcao_textual = qtd_textuais / max(len(preenchidos), 1)

        return proporcao_unicos >= 0.7 and proporcao_textual >= 0.7
    except Exception:
        return False


def _promover_primeira_linha_para_header_se_preciso(df):
    try:
        if not _safe_df_com_linhas(df):
            return df

        df2 = df.copy()
        colunas = list(df2.columns)

        qtd_genericas = sum(1 for c in colunas if _coluna_parece_generica(c))
        if qtd_genericas / max(len(colunas), 1) < 0.6:
            return df2

        primeira = df2.iloc[0].tolist()
        if not _linha_parece_cabecalho(primeira):
            return df2

        novos = []
        usados = set()

        for i, v in enumerate(primeira):
            nome = _normalizar_texto_coluna(v) or f"Coluna_{i + 1}"
            base = nome
            c = 2
            while nome in usados:
                nome = f"{base}_{c}"
                c += 1
            usados.add(nome)
            novos.append(nome)

        df2.columns = novos
        return df2.iloc[1:].reset_index(drop=True)

    except Exception:
        return df


def _normalizar_nomes_colunas(df):
    try:
        if not _safe_df(df):
            return df

        df2 = df.copy()
        usadas = set()
        novas = []

        for i, col in enumerate(df2.columns):
            nome = _normalizar_texto_coluna(col) or f"Coluna_{i + 1}"
            base = nome
            c = 2
            while nome in usadas:
                nome = f"{base}_{c}"
                c += 1
            usadas.add(nome)
            novas.append(nome)

        df2.columns = novas
        return df2.reset_index(drop=True)
    except Exception:
        return df


def _preparar_df_origem_para_mapeamento(df):
    df = _promover_primeira_linha_para_header_se_preciso(df)
    df = _normalizar_nomes_colunas(df)
    return df


def _preparar_df_modelo_para_mapeamento(df):
    """
    Modelo do Bling deve ser preservado ao máximo.
    Aqui só normalizamos nomes duplicados/vazios,
    sem promover primeira linha para cabeçalho.
    """
    return _normalizar_nomes_colunas(df)


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


def _is_coluna_preco(nome) -> bool:
    nome = str(nome).lower().strip()
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


def _is_coluna_deposito(nome) -> bool:
    nome = str(nome).lower().strip()
    return "deposit" in nome or "depós" in nome or "deposito" in nome


def _preview_coluna(df, coluna):
    try:
        if coluna in df.columns:
            valores = (
                df[coluna]
                .fillna("")
                .astype(str)
                .replace("nan", "")
                .head(5)
                .tolist()
            )
            return valores
    except Exception:
        pass
    return []


def _get_coluna_preco_base_precificacao(df_origem: pd.DataFrame) -> str:
    try:
        coluna = str(st.session_state.get("coluna_preco_base", "") or "").strip()
        if coluna and coluna in df_origem.columns:
            return coluna
    except Exception:
        pass
    return ""


def _get_df_fluxo_base(df_origem: pd.DataFrame) -> pd.DataFrame:
    """
    Retorna o DataFrame atual do fluxo, priorizando df_saida quando ele ainda
    representa a base antes do mapeamento final. Se não existir, cai para df_origem.
    """
    try:
        df_fluxo = st.session_state.get("df_saida")
        if _safe_df_com_linhas(df_fluxo):
            return df_fluxo.copy().reset_index(drop=True)
    except Exception:
        pass

    return df_origem.copy().reset_index(drop=True)


def _serie_vazia_tamanho_origem(df_origem: pd.DataFrame) -> pd.Series:
    return pd.Series(
        [""] * len(df_origem),
        index=range(len(df_origem)),
        dtype="object",
    )


def _alinhar_serie_para_origem(serie: pd.Series, df_origem: pd.DataFrame) -> pd.Series:
    try:
        return (
            serie.reset_index(drop=True)
            .reindex(range(len(df_origem)), fill_value="")
            .astype("object")
        )
    except Exception:
        return _serie_vazia_tamanho_origem(df_origem)


def _obter_serie_preco_para_saida(df_origem: pd.DataFrame) -> pd.Series:
    """
    Detecta automaticamente a coluna de preço calculado no fluxo.
    Totalmente independente de nome fixo.
    """
    try:
        df_fluxo = _get_df_fluxo_base(df_origem)

        if not _safe_df_com_linhas(df_fluxo):
            return _serie_vazia_tamanho_origem(df_origem)

        candidatos = [
            "preço de venda",
            "preco de venda",
            "preço venda",
            "preco venda",
            "valor de venda",
            "valor venda",
        ]

        for col in df_fluxo.columns:
            nome = str(col).lower().strip()
            for candidato in candidatos:
                if candidato in nome:
                    return _alinhar_serie_para_origem(df_fluxo[col], df_origem)

        colunas_origem = set(df_origem.columns)

        for col in df_fluxo.columns:
            if col not in colunas_origem:
                return _alinhar_serie_para_origem(df_fluxo[col], df_origem)

        for col in df_fluxo.columns:
            if col in df_origem.columns:
                try:
                    s1 = (
                        df_origem[col]
                        .reindex(range(len(df_origem)), fill_value="")
                        .fillna("")
                        .astype(str)
                        .reset_index(drop=True)
                    )
                    s2 = (
                        df_fluxo[col]
                        .reindex(range(len(df_origem)), fill_value="")
                        .fillna("")
                        .astype(str)
                        .reset_index(drop=True)
                    )

                    if not s1.equals(s2):
                        return _alinhar_serie_para_origem(df_fluxo[col], df_origem)
                except Exception:
                    continue

        coluna_preco_base = _get_coluna_preco_base_precificacao(df_origem)
        if coluna_preco_base and coluna_preco_base in df_fluxo.columns:
            return _alinhar_serie_para_origem(df_fluxo[coluna_preco_base], df_origem)

    except Exception:
        pass

    return _serie_vazia_tamanho_origem(df_origem)


def _montar_df_saida(
    df_origem: pd.DataFrame,
    df_modelo: pd.DataFrame,
    mapping: dict,
) -> pd.DataFrame:
    deposito = _get_deposito()
    serie_preco = _obter_serie_preco_para_saida(df_origem)

    df_origem = df_origem.copy().reset_index(drop=True)
    df_modelo = df_modelo.copy().reset_index(drop=True)

    df_saida = pd.DataFrame(index=range(len(df_origem)))

    for col in df_modelo.columns:
        origem = str(mapping.get(col, "") or "").strip()

        if _is_coluna_preco(col):
            try:
                df_saida[col] = serie_preco.reset_index(drop=True)
            except Exception:
                df_saida[col] = ""
            continue

        if _is_coluna_deposito(col):
            df_saida[col] = deposito if deposito else ""
            continue

        if origem in df_origem.columns:
            try:
                df_saida[col] = (
                    df_origem[origem]
                    .reset_index(drop=True)
                    .reindex(range(len(df_origem)), fill_value="")
                )
            except Exception:
                df_saida[col] = ""
        else:
            df_saida[col] = ""

    try:
        df_saida = df_saida.reindex(columns=df_modelo.columns, fill_value="")
    except Exception:
        pass

    try:
        df_saida = df_saida.fillna("")
    except Exception:
        pass

    return df_saida


def _salvar_estado_mapeamento(mapping_key: str, mapping: dict) -> None:
    try:
        st.session_state[mapping_key] = mapping.copy()
    except Exception:
        pass


def _voltar_para_origem() -> None:
    try:
        st.session_state["etapa_origem"] = "origem"
    except Exception:
        st.session_state["etapa_origem"] = "origem"
    st.rerun()


def _garantir_etapa_valida() -> None:
    try:
        etapa = str(
            st.session_state.get("etapa_origem", "origem") or "origem"
        ).strip().lower()
        if etapa not in ETAPAS_VALIDAS_ORIGEM:
            st.session_state["etapa_origem"] = "origem"
    except Exception:
        st.session_state["etapa_origem"] = "origem"


def _opcoes_origem_sem_repeticao(
    col_modelo_atual: str,
    colunas_origem: list[str],
    mapping_atual: dict,
    valor_atual: str,
) -> list[str]:
    """
    Evita reutilizar a mesma coluna da origem em vários campos do modelo.
    Mantém a coluna já escolhida no campo atual para não quebrar edição.
    """
    usadas = set()

    for campo_modelo, coluna_origem in mapping_atual.items():
        if campo_modelo == col_modelo_atual:
            continue
        coluna_origem = str(coluna_origem or "").strip()
        if coluna_origem:
            usadas.add(coluna_origem)

    opcoes = [""]

    for coluna in colunas_origem:
        if coluna == valor_atual or coluna not in usadas:
            opcoes.append(coluna)

    if valor_atual and valor_atual not in opcoes:
        opcoes.append(valor_atual)

    return opcoes


def render_origem_mapeamento():
    _garantir_etapa_valida()

    if str(st.session_state.get("etapa_origem", "origem")).strip().lower() != "mapeamento":
        return

    df_origem = st.session_state.get("df_origem")
    df_modelo = _get_modelo()

    if not _safe_df_com_linhas(df_origem) or not _safe_df(df_modelo):
        st.warning("Dados de origem ou modelo não encontrados. Volte para a etapa anterior.")
        return

    df_origem = _preparar_df_origem_para_mapeamento(df_origem)
    df_modelo = _preparar_df_modelo_para_mapeamento(df_modelo)

    topo_a, topo_b = st.columns([1, 1])

    with topo_a:
        if st.button("⬅️ Voltar", use_container_width=True):
            _voltar_para_origem()

    with topo_b:
        if st.button("🧹 Limpar mapeamento", use_container_width=True):
            mapping_key_limpar = (
                f"mapeamento_manual_{str(st.session_state.get('tipo_operacao_bling', 'padrao')).lower()}"
            )
            st.session_state[mapping_key_limpar] = {}

            for col_modelo in df_modelo.columns:
                chave_widget = f"map_{col_modelo}"
                if chave_widget in st.session_state:
                    del st.session_state[chave_widget]

            st.rerun()

    with st.container():
        st.markdown("### 👁️ Preview da planilha fornecedora")
        st.dataframe(
            df_origem.head(5),
            use_container_width=True,
            hide_index=True,
        )

    colunas_modelo = list(df_modelo.columns)
    colunas_origem = list(df_origem.columns)

    mapping_key = (
        f"mapeamento_manual_{str(st.session_state.get('tipo_operacao_bling', 'padrao')).lower()}"
    )
    mapping_salvo = st.session_state.get(mapping_key, {}) or {}
    mapping = {}

    st.markdown("### 🧩 Relacione as colunas")

    for col_modelo in colunas_modelo:
        if _is_coluna_preco(col_modelo):
            coluna_base = _get_coluna_preco_base_precificacao(df_origem)
            texto_preco = "Calculado automaticamente"
            if coluna_base:
                texto_preco = f"Calculado automaticamente ({coluna_base})"

            st.text_input(
                col_modelo,
                value=texto_preco,
                disabled=True,
                key=f"preco_fix_{col_modelo}",
            )
            mapping[col_modelo] = ""
            continue

        if _is_coluna_deposito(col_modelo):
            deposito = _get_deposito()
            st.text_input(
                col_modelo,
                value=deposito or "Depósito automático",
                disabled=True,
                key=f"deposito_fix_{col_modelo}",
            )
            mapping[col_modelo] = ""
            continue

        valor_inicial = str(mapping_salvo.get(col_modelo, "") or "")
        opcoes = _opcoes_origem_sem_repeticao(
            col_modelo_atual=col_modelo,
            colunas_origem=colunas_origem,
            mapping_atual={**mapping_salvo, **mapping},
            valor_atual=valor_inicial,
        )

        escolhido = st.selectbox(
            col_modelo,
            opcoes,
            index=opcoes.index(valor_inicial) if valor_inicial in opcoes else 0,
            key=f"map_{col_modelo}",
        )

        mapping[col_modelo] = escolhido

        if escolhido:
            valores = _preview_coluna(df_origem, escolhido)
            if valores:
                st.caption(f"Exemplo: {valores}")

    _salvar_estado_mapeamento(mapping_key, mapping)

    df_saida = _montar_df_saida(df_origem, df_modelo, mapping)

    st.session_state["df_saida"] = df_saida.copy()
    st.session_state["df_final"] = df_saida.copy()

    st.markdown("### 📄 Preview da saída")
    st.dataframe(
        df_saida.head(10),
        use_container_width=True,
        hide_index=True,
    )

    rodape_a, rodape_b = st.columns([1, 1])

    with rodape_a:
        if st.button(
            "⬅️ Voltar para origem",
            key="voltar_origem_rodape",
            use_container_width=True,
        ):
            _voltar_para_origem()

    with rodape_b:
        st.button(
            "✅ Mapeamento salvo",
            disabled=True,
            key="mapeamento_salvo_info",
            use_container_width=True,
        )
