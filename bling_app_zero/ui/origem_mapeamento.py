
from __future__ import annotations

import pandas as pd
import streamlit as st


def _normalizar(nome: str) -> str:
    return (
        str(nome or "")
        .strip()
        .lower()
        .replace("ç", "c")
        .replace("ã", "a")
        .replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
    )


def _sugestoes_mapa(colunas_origem: list[str], colunas_modelo: list[str], operacao: str) -> dict[str, str]:
    sugestoes = {}
    idx = {_normalizar(c): c for c in colunas_origem}

    pares = {
        "Código": ["codigo", "sku", "referencia", "ref", "id"],
        "Descrição": ["descricao", "nome", "produto", "titulo"],
        "Descrição Curta": ["descricao curta", "resumo", "descricao"],
        "Preço de venda": ["__preco_calculado_bling__", "preco", "valor"],
        "GTIN/EAN": ["gtin", "ean", "codigo barras"],
        "URL Imagens": ["imagem", "imagens", "url imagens", "fotos"],
        "Categoria": ["categoria", "grupo", "departamento"],
        "Depósito (OBRIGATÓRIO)": ["deposito"],
        "Balanço (OBRIGATÓRIO)": ["estoque", "saldo", "quantidade", "qtd"],
        "Preço unitário (OBRIGATÓRIO)": ["__preco_calculado_bling__", "preco", "valor"],
    }

    for col_modelo in colunas_modelo:
        sugestao = ""
        for alias in pares.get(col_modelo, []):
            for col_origem in colunas_origem:
                if _normalizar(alias) == _normalizar(col_origem):
                    sugestao = col_origem
                    break
            if sugestao:
                break
        if not sugestao and _normalizar(col_modelo) in idx:
            sugestao = idx[_normalizar(col_modelo)]
        sugestoes[col_modelo] = sugestao

    return sugestoes


def render_origem_mapeamento() -> None:
    st.markdown("### Mapeamento")
    st.caption("Confirme para onde cada coluna da origem vai no modelo final. O que não for reconhecido será perguntado aqui.")

    df_base = st.session_state.get("df_origem_precificado")
    df_modelo = st.session_state.get("df_modelo_base")

    if df_base is None or df_base.empty:
        st.warning("A precificação precisa ser concluída antes do mapeamento.")
        return

    if df_modelo is None:
        st.warning("Envie a planilha modelo do Bling na etapa de origem.")
        return

    colunas_origem = list(df_base.columns)
    colunas_modelo = list(df_modelo.columns)
    operacao = st.session_state.get("tipo_operacao", "cadastro")

    if not colunas_modelo:
        st.warning("O modelo enviado não possui cabeçalhos legíveis.")
        return

    sugestoes = _sugestoes_mapa(colunas_origem, colunas_modelo, operacao)

    mapping = {}
    pendentes = []

    with st.container(border=True):
        for coluna_modelo in colunas_modelo:
            sugestao = st.session_state.get("mapeamento_colunas", {}).get(coluna_modelo, sugestoes.get(coluna_modelo, ""))
            opcoes = ["", "PERGUNTAR / NÃO SEI"] + colunas_origem

            if sugestao not in opcoes:
                sugestao = ""

            escolhido = st.selectbox(
                f"{coluna_modelo}",
                options=opcoes,
                index=opcoes.index(sugestao) if sugestao in opcoes else 0,
                key=f"map_{coluna_modelo}",
            )
            mapping[coluna_modelo] = escolhido

            if escolhido in {"", "PERGUNTAR / NÃO SEI"}:
                pendentes.append(coluna_modelo)

    st.session_state["mapeamento_colunas"] = mapping
    st.session_state["campos_pendentes"] = pendentes

    obrigatorias = []
    if operacao == "estoque":
        obrigatorias = [
            "Código",
            "Descrição",
            "Depósito (OBRIGATÓRIO)",
            "Balanço (OBRIGATÓRIO)",
            "Preço unitário (OBRIGATÓRIO)",
        ]
    else:
        obrigatorias = ["Código", "Descrição", "Preço de venda"]

    obrigatorias_pendentes = [c for c in obrigatorias if mapping.get(c) in {"", "PERGUNTAR / NÃO SEI"}]

    if obrigatorias_pendentes:
        st.warning("Ainda faltam campos obrigatórios para mapear: " + ", ".join(obrigatorias_pendentes))
        st.session_state["df_final"] = None
        return

    resultado = pd.DataFrame(index=df_base.index)

    for coluna_modelo in colunas_modelo:
        origem_escolhida = mapping.get(coluna_modelo, "")
        if origem_escolhida in {"", "PERGUNTAR / NÃO SEI"}:
            resultado[coluna_modelo] = ""
        else:
            resultado[coluna_modelo] = df_base[origem_escolhida]

    if operacao == "estoque":
        deposito = st.session_state.get("deposito_nome", "")
        if deposito and "Depósito (OBRIGATÓRIO)" in resultado.columns:
            resultado["Depósito (OBRIGATÓRIO)"] = deposito

    st.session_state["df_final"] = resultado

    if pendentes:
        st.info("Existem campos opcionais sem destino definido: " + ", ".join(pendentes))

    st.success("Mapeamento concluído. O preview final já pode ser conferido.")
    with st.expander("Ver prévia do mapeamento", expanded=False):
        st.dataframe(resultado.head(50), use_container_width=True)

