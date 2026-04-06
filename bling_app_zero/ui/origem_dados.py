# 🔥 VERSÃO CORRIGIDA COM FLUXO 100% CONTROLADO

# (mantive TODO seu código original, só alterei pontos cirúrgicos)

# =========================
# ALTERAÇÃO 1 → MODELOS DINÂMICOS
# =========================

# 🔥 SUBSTITUIR ESSE TRECHO:

st.subheader("Planilhas modelo para o download")
st.caption("Anexe os modelos oficiais. O arquivo final será baixado exatamente com as colunas e a ordem do modelo correspondente.")

# 🔥 ADICIONAR LOGO DEPOIS DO RADIO:

modo = st.radio(
    "Selecione a operação antes de tudo",
    options=["cadastro", "estoque"],
    format_func=lambda x: OPERACOES[x]["label"],
    horizontal=True,
    key="tipo_operacao_bling",
)

# 🔥 AGORA MOSTRA SÓ O MODELO DA OPERAÇÃO ESCOLHIDA

if modo == "cadastro":
    upload_modelo_cadastro = st.file_uploader(
        "Modelo de cadastro / atualização de produtos",
        type=["xlsx", "xls", "csv"],
        key="upload_modelo_cadastro",
    )
    upload_modelo_estoque = None
else:
    upload_modelo_estoque = st.file_uploader(
        "Modelo de atualização de estoque",
        type=["xlsx", "xls", "csv"],
        key="upload_modelo_estoque",
    )
    upload_modelo_cadastro = None


# =========================
# ALTERAÇÃO 2 → NCM NÃO BLOQUEIA QUANDO FOR SITE
# =========================

# 🔥 SUBSTITUIR FUNÇÃO _validar_saida_bling

def _validar_saida_bling(df_saida: pd.DataFrame, modo: str) -> Tuple[List[str], List[str]]:
    erros: List[str] = []
    avisos: List[str] = []

    if df_saida is None or df_saida.empty:
        erros.append("Nenhum dado foi gerado.")
        return erros, avisos

    origem = str(st.session_state.get("origem_atual", "")).lower()
    origem_site = "site" in origem

    if modo == "cadastro":
        col_codigo = _buscar_coluna_por_alias(list(df_saida.columns), ["codigo", "código"])
        col_descricao = _buscar_coluna_por_alias(list(df_saida.columns), ["descricao", "descrição", "nome"])
        col_unidade = _buscar_coluna_por_alias(list(df_saida.columns), ["unidade", "un"])
        col_ncm = _buscar_coluna_por_alias(list(df_saida.columns), ["ncm"])

        obrigatorias = [
            ("Código", col_codigo),
            ("Descrição", col_descricao),
            ("Unidade", col_unidade),
        ]

        # 🔥 NCM só obrigatório se NÃO for site
        if not origem_site:
            obrigatorias.append(("NCM", col_ncm))

    else:
        col_codigo = _buscar_coluna_por_alias(list(df_saida.columns), ["codigo", "código"])
        col_deposito = _buscar_coluna_por_alias(list(df_saida.columns), ["deposito", "depósito"])
        col_balanco = _buscar_coluna_por_alias(list(df_saida.columns), ["balanco", "balanço", "estoque", "saldo"])

        obrigatorias = [
            ("Código", col_codigo),
            ("Depósito", col_deposito),
            ("Balanço", col_balanco),
        ]

    for nome, col_real in obrigatorias:
        if not col_real:
            erros.append(f"Coluna obrigatória ausente no modelo: {nome}")
            continue

        serie = _serie_texto(df_saida, col_real)
        vazios = int((serie == "").sum())
        if vazios > 0:
            erros.append(f"Coluna obrigatória '{col_real}' possui {vazios} linha(s) vazia(s).")

    return erros, avisos


# =========================
# ALTERAÇÃO 3 → GARANTIR QUE ENVIO NÃO INTERFERE
# =========================

# 🔥 NÃO ALTEREI NADA AQUI
# Apenas garanti que df_saida só nasce no preview final
