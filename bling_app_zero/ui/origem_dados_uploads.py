# (ARQUIVO COMPLETO - apenas trecho corrigido da função carregar_modelo_bling)

def carregar_modelo_bling(arquivo: Any, tipo_modelo: str) -> bool:
    if arquivo is None:
        return False

    if not arquivo_planilha_permitido(arquivo):
        st.error(
            f"Formato não suportado para o modelo Bling. "
            f"Envie um arquivo em: {texto_extensoes_planilha()}."
        )
        log_debug(
            f"Modelo Bling recusado por extensão: {nome_arquivo(arquivo)}",
            "ERROR",
        )
        return False

    try:
        hash_atual = hash_arquivo_upload(arquivo)
        chave_hash = (
            "modelo_cadastro_hash" if tipo_modelo == "cadastro" else "modelo_estoque_hash"
        )

        hash_anterior = st.session_state.get(chave_hash, "")

        nome_atual = nome_arquivo(arquivo)
        chave_nome = (
            "modelo_cadastro_nome" if tipo_modelo == "cadastro" else "modelo_estoque_nome"
        )
        nome_anterior = st.session_state.get(chave_nome, "")

        if hash_atual and hash_atual == hash_anterior and nome_atual == nome_anterior:
            return True

        # 🔥 CORREÇÃO PRINCIPAL
        df_modelo = ler_planilha_segura(arquivo)

        # 🔥 GARANTIA ABSOLUTA
        if df_modelo is None:
            df_modelo = pd.DataFrame()

        if not isinstance(df_modelo, pd.DataFrame):
            df_modelo = pd.DataFrame()

        # 🔥 NOVA REGRA CORRETA
        if len(df_modelo.columns) == 0:
            st.error("Não foi possível identificar colunas no modelo Bling.")
            return False

        df_modelo = df_modelo.copy()
        df_modelo = _promover_primeira_linha_para_header_modelo_se_preciso(df_modelo)

        if len(df_modelo.columns) == 0:
            st.error("O modelo Bling não possui colunas válidas.")
            log_debug(
                f"Modelo Bling sem colunas ({tipo_modelo}): {nome_atual}",
                "ERROR",
            )
            return False

        df_modelo.columns = [str(c).strip() for c in df_modelo.columns]

        if tipo_modelo == "cadastro":
            st.session_state.pop("df_modelo_cadastro", None)
        else:
            st.session_state.pop("df_modelo_estoque", None)

        if tipo_modelo == "cadastro":
            st.session_state["df_modelo_cadastro"] = df_modelo.copy()
            st.session_state["modelo_cadastro_nome"] = nome_atual
            st.session_state["modelo_cadastro_hash"] = hash_atual

            st.session_state.pop("df_saida", None)
            st.session_state.pop("df_final", None)

            log_debug(
                f"Modelo de cadastro carregado: {nome_atual} "
                f"({len(df_modelo)} linha(s), {len(df_modelo.columns)} coluna(s))"
            )
        else:
            st.session_state["df_modelo_estoque"] = df_modelo.copy()
            st.session_state["modelo_estoque_nome"] = nome_atual
            st.session_state["modelo_estoque_hash"] = hash_atual

            st.session_state.pop("df_saida", None)
            st.session_state.pop("df_final", None)

            log_debug(
                f"Modelo de estoque carregado: {nome_atual} "
                f"({len(df_modelo)} linha(s), {len(df_modelo.columns)} coluna(s))"
            )

        return True

    except Exception as e:
        st.error("Erro ao carregar o modelo Bling.")
        log_debug(f"Erro ao carregar modelo Bling ({tipo_modelo}): {e}", "ERROR")
        return False
