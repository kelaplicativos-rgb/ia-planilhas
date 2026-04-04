# =====================================
# REGRA FIXA DEFINITIVA BLING
# =====================================

nome_produto = limpar_texto_serie(
    obter_serie(df, mapeamento_final, "nome", "")
)

descricao_real = limpar_texto_serie(
    obter_serie(df, mapeamento_final, "descricao_curta", "")
)

# fallback inteligente (evita campos vazios)
nome_final = nome_produto.copy()
vazios_nome = nome_final.astype(str).str.strip() == ""
nome_final[vazios_nome] = descricao_real[vazios_nome]

descricao_final = descricao_real.copy()
vazios_desc = descricao_final.astype(str).str.strip() == ""
descricao_final[vazios_desc] = nome_final[vazios_desc]

# APLICAÇÃO CORRETA
saida["descricao"] = nome_final
saida["descricao_curta"] = descricao_final

# regras fixas obrigatórias
saida["video"] = ""
saida["link_externo"] = ""
