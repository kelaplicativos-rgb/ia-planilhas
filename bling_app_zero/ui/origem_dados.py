from typing import Dict, List

import streamlit as st

from bling_app_zero.utils.excel import df_to_excel_bytes
from bling_app_zero.utils.numeros import format_money
from bling_app_zero.core.memoria_fornecedor import (
    carregar_perfil,
    salvar_perfil,
    deletar_perfil,
)
from bling_app_zero.core.roteador_entrada import (
    ORIGEM_PLANILHA,
    ORIGEM_SITE,
    ORIGEM_XML,
    MODO_CADASTRO,
    MODO_ESTOQUE,
    carregar_entrada_upload,
    carregar_entrada_urls,
    detectar_modo_visual_por_upload,
)
from bling_app_zero.core.precificacao import calcular_preco_compra_automatico_df
from bling_app_zero.core.mapeamento_auto import sugestao_automatica


def render_origem_dados() -> None:
    st.subheader("Origem de dados")

    modo = st.radio(
        "Modo de operação",
        [MODO_CADASTRO, MODO_ESTOQUE],
        horizontal=True,
    )

    origem = st.radio(
        "Escolha a origem",
        [ORIGEM_PLANILHA, ORIGEM_XML, ORIGEM_SITE],
        horizontal=True,
    )

    df = None
    tipo_visual = ""

    if origem == ORIGEM_PLANILHA:
        arquivo = st.file_uploader(
            "Anexar planilha do fornecedor",
            type=["xlsx", "xls", "csv"],
            key="uploader_planilha",
        )
        if not arquivo:
            return

        tipo_visual = detectar_modo_visual_por_upload(arquivo)
        df = carregar_entrada_upload(arquivo)

    elif origem == ORIGEM_XML:
        arquivo = st.file_uploader(
            "Anexar XML da nota fiscal",
            type=["xml"],
            key="uploader_xml",
        )
        if not arquivo:
            return

        tipo_visual = detectar_modo_visual_por_upload(arquivo)
        df = carregar_entrada_upload(arquivo)

    else:
        texto_urls = st.text_area(
            "Cole uma URL por linha",
            height=180,
            placeholder=(
                "https://site.com/produto-1\n"
                "https://site.com/produto-2\n"
                "https://site.com/produto-3"
            ),
        )
        if not texto_urls.strip():
            return

        with st.spinner("Buscando produtos nos sites..."):
            df = carregar_entrada_urls(texto_urls)

        tipo_visual = "Site / URLs"

    if df is None or df.empty:
        st.error("Não foi possível gerar dados de entrada.")
        return

    st.session_state.df_origem = df
    st.session_state.origem_atual = tipo_visual

    if tipo_visual == "XML NF-e":
        preco_auto = calcular_preco_compra_automatico_df(df)
        st.session_state.preco_compra_modulo_precificacao = preco_auto
        st.success(
            f"XML lido com sucesso.\n\nPreço de compra automático: {format_money(preco_auto)}"
        )
    else:
        st.session_state.preco_compra_modulo_precificacao = 0.0

    st.info(f"Entrada detectada: **{tipo_visual}**")

    assinatura = list(df.columns)
    perfil = carregar_perfil(assinatura)

    if perfil:
        st.session_state.mapeamento_manual = perfil
        st.success("Perfil de colunas carregado automaticamente.")
    else:
        sugestoes = {}
        for col in df.columns:
            sugestoes[col] = sugestao_automatica(col)
        st.session_state.mapeamento_manual = sugestoes
        st.info("Nenhum perfil salvo encontrado.\n\nSugestões automáticas aplicadas.")

    with st.expander("Preview da entrada", expanded=False):
        st.dataframe(df.head(30), use_container_width=True)

    if tipo_visual == "XML NF-e":
        cols_debug = [
            c
            for c in [
                "codigo",
                "descricao_curta",
                "quantidade",
                "preco",
                "preco_custo",
                "custo_total_item_xml",
                "frete_item",
                "seguro_item",
                "desconto_item",
                "outras_despesas_item",
                "valor_ipi_item",
                "valor_icms_st_item",
                "valor_fcp_st_item",
                "valor_ii_item",
                "total_impostos_item",
            ]
            if c in df.columns
        ]

        if cols_debug:
            with st.expander("Custos calculados do XML", expanded=False):
                st.dataframe(df[cols_debug], use_container_width=True)

    if modo == MODO_CADASTRO:
        campos = [
            "",
            "codigo",
            "nome",
            "descricao_curta",
            "preco",
            "preco_custo",
            "estoque",
            "gtin",
            "marca",
            "categoria",
            "ncm",
            "cest",
            "cfop",
            "unidade",
            "fornecedor",
            "cnpj_fornecedor",
            "numero_nfe",
            "data_emissao",
            "imagens",
            "origem",
        ]
    else:
        campos = [
            "",
            "codigo",
            "estoque",
            "preco",
            "preco_custo",
            "deposito_id",
            "origem",
        ]

    st.markdown("#### Mapeamento manual")

    mapeamento: Dict[str, str] = {}
    usados: List[str] = []

    for col in df.columns:
        valor_inicial = ""
        if isinstance(st.session_state.mapeamento_manual, dict):
            valor_inicial = st.session_state.mapeamento_manual.get(col, "")

        opcoes = [x for x in campos if x == "" or x == valor_inicial or x not in usados]
        idx = opcoes.index(valor_inicial) if valor_inicial in opcoes else 0

        escolha = st.selectbox(
            label=col,
            options=opcoes,
            index=idx,
            key=f"map_{col}",
        )

        mapeamento[col] = escolha
        if escolha:
            usados.append(escolha)

    st.session_state.mapeamento_manual = mapeamento

    c1, c2 = st.columns(2)

    with c1:
        if st.button("Salvar perfil de colunas", use_container_width=True):
            salvar_perfil(list(df.columns), mapeamento)
            st.success("Perfil salvo com sucesso.")

    with c2:
        if st.button("Excluir perfil de colunas", use_container_width=True):
            apagou = deletar_perfil(list(df.columns))
            if apagou:
                st.success("Perfil excluído.")
            else:
                st.warning("Nenhum perfil salvo para esta estrutura.")

    with st.expander("Mapeamento final", expanded=False):
        st.json(mapeamento)

    st.download_button(
        "Baixar entrada tratada",
        data=df_to_excel_bytes(df, "entrada_tratada"),
        file_name="entrada_tratada.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
