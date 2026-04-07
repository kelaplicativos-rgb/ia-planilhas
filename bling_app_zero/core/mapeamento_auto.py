# 🔥 ADICIONE ISSO NO FINAL DO ARQUIVO (SEM REMOVER NADA EXISTENTE)

def sugestao_automatica_com_regras(
    df_origem,
    colunas_alvo: list[str],
    bloqueios: dict | None = None,
    mapeamento_existente: dict | None = None,
):
    """
    Versão protegida da sugestão automática:
    - respeita campos bloqueados (preço, depósito, etc)
    - não sobrescreve mapeamento manual
    - evita conflitos
    """

    if pd is None or not isinstance(df_origem, pd.DataFrame):
        return {}

    bloqueios = bloqueios or {}
    mapeamento_existente = mapeamento_existente or {}

    alvos = _preparar_alvos(colunas_alvo or [])
    sugestoes_base = sugestao_automatica(df_origem, alvos)

    sugestoes_finais: dict[str, str] = {}
    alvos_usados: set[str] = set()

    for col_origem, col_alvo in sugestoes_base.items():

        alvo_norm = _normalizar(col_alvo)

        # 🔒 1. RESPEITAR CAMPOS BLOQUEADOS
        if any(k in alvo_norm for k in ["preco", "preço"]):
            if bloqueios.get("preco"):
                continue

        if any(k in alvo_norm for k in ["deposito", "depósito"]):
            if bloqueios.get("deposito"):
                continue

        # 🔒 2. NÃO SOBRESCREVER MANUAL
        if col_origem in mapeamento_existente:
            continue

        # 🔒 3. EVITAR DUPLICIDADE
        if col_alvo in alvos_usados:
            continue

        sugestoes_finais[col_origem] = col_alvo
        alvos_usados.add(col_alvo)

    return sugestoes_finais
