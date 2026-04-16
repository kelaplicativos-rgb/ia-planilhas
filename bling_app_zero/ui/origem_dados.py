
from __future__ import annotations

import io
from typing import Optional

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import (
    log_debug,
    normalizar_coluna_busca,
    safe_df_dados,
    sincronizar_etapa_global,
)

try:
    from bling_app_zero.core.site_crawler import executar_crawler_site
except Exception:
    executar_crawler_site = None

try:
    from bling_app_zero.core.xml_nfe import converter_upload_xml_para_dataframe
except Exception:
    converter_upload_xml_para_dataframe = None

try:
    from bling_app_zero.core.fetch_router import (
        buscar_produtos_fornecedor,
        listar_fornecedores_disponiveis,
    )
except Exception:
    buscar_produtos_fornecedor = None

    def listar_fornecedores_disponiveis() -> list[str]:
        return []


# ============================================================
# HELPERS BÁSICOS
# ============================================================

def _safe_str(valor) -> str:
    try:
        if valor is None:
            return ""
        texto = str(valor).strip()
        if texto.lower() in {"none", "nan", "nat"}:
            return ""
        return texto
    except Exception:
        return ""


def _to_float_brasil(valor) -> float:
    texto = _safe_str(valor)
    if not texto:
        return 0.0

    texto = texto.replace("R$", "").replace(" ", "")
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(",", ".")

    try:
        return float(texto)
    except Exception:
        return 0.0


def _formatar_numero_bling(valor) -> str:
    return f"{_to_float_brasil(valor):.2f}".replace(".", ",")


def _limpar_fluxo_abaixo_da_origem() -> None:
    for chave in [
        "df_saida",
        "df_final",
        "df_precificado",
        "df_calc_precificado",
        "df_mapeado",
        "df_preview_mapeamento",
    ]:
        st.session_state[chave] = None

    for chave in [
        "mapping_origem",
        "mapping_origem_rascunho",
        "mapping_origem_defaults",
    ]:
        st.session_state[chave] = {}


def _modelo_padrao_por_operacao(tipo_operacao_bling: str) -> pd.DataFrame:
    if str(tipo_operacao_bling).strip().lower() == "estoque":
        colunas = [
            "Código",
            "Descrição",
            "Depósito (OBRIGATÓRIO)",
            "Balanço (OBRIGATÓRIO)",
            "Preço unitário (OBRIGATÓRIO)",
            "Situação",
        ]
    else:
        colunas = [
            "Código",
            "Descrição",
            "Descrição Curta",
            "Preço de venda",
            "GTIN/EAN",
            "Situação",
            "URL Imagens",
            "Categoria",
        ]
    return pd.DataFrame(columns=colunas)


def _set_operacao(label: str) -> None:
    if label == "Atualização de Estoque":
        st.session_state["tipo_operacao"] = "Atualização de Estoque"
        st.session_state["tipo_operacao_radio"] = "Atualização de Estoque"
        st.session_state["tipo_operacao_bling"] = "estoque"
    else:
        st.session_state["tipo_operacao"] = "Cadastro de Produtos"
        st.session_state["tipo_operacao_radio"] = "Cadastro de Produtos"
        st.session_state["tipo_operacao_bling"] = "cadastro"

    st.session_state["df_modelo_operacao"] = _modelo_padrao_por_operacao(
        st.session_state["tipo_operacao_bling"]
    )


def _resolver_df_origem_atual() -> Optional[pd.DataFrame]:
    for chave in [
        "df_origem",
        "df_saida",
        "df_final",
        "df_precificado",
        "df_calc_precificado",
    ]:
        df = st.session_state.get(chave)
        if safe_df_dados(df):
            return df.copy()
    return None


# ============================================================
# LEITURA DE ARQUIVOS
# ============================================================

def _ler_csv_upload(upload) -> Optional[pd.DataFrame]:
    bruto = upload.getvalue()
    for sep in [";", ",", "\t", "|"]:
        try:
            df = pd.read_csv(io.BytesIO(bruto), sep=sep, dtype=str).fillna("")
            if safe_df_dados(df):
                return df
        except Exception:
            continue
    return None


def _ler_excel_upload(upload) -> Optional[pd.DataFrame]:
    try:
        return pd.read_excel(upload, dtype=str).fillna("")
    except Exception:
        return None


def _parse_xml(upload) -> pd.DataFrame:
    if converter_upload_xml_para_dataframe is not None:
        try:
            df_xml = converter_upload_xml_para_dataframe(upload)
            if isinstance(df_xml, pd.DataFrame):
                return df_xml.fillna("")
        except Exception as e:
            log_debug(f"Falha no parser XML: {e}", "WARNING")
    return pd.DataFrame()


def _ler_upload_arquivo(upload) -> Optional[pd.DataFrame]:
    if upload is None:
        return None

    nome = _safe_str(getattr(upload, "name", "")).lower()

    try:
        if nome.endswith(".csv"):
            return _ler_csv_upload(upload)
        if nome.endswith(".xlsx") or nome.endswith(".xls"):
            return _ler_excel_upload(upload)
        if nome.endswith(".xml"):
            return _parse_xml(upload)
    except Exception as e:
        log_debug(f"Erro lendo upload: {e}", "ERROR")

    return None


# ============================================================
# NORMALIZAÇÃO DA ORIGEM
# ============================================================

def _primeira_coluna_existente(df: pd.DataFrame, candidatos: list[str]) -> str:
    mapa = {normalizar_coluna_busca(col): col for col in df.columns}

    for candidato in candidatos:
        chave = normalizar_coluna_busca(candidato)
        if chave in mapa:
            return mapa[chave]

    for col in df.columns:
        ncol = normalizar_coluna_busca(col)
        for candidato in candidatos:
            if normalizar_coluna_busca(candidato) in ncol:
                return col

    return ""


def _normalizar_df_origem(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()

    base = df.copy().fillna("")
    base.columns = [_safe_str(c) for c in base.columns]

    col_codigo = _primeira_coluna_existente(
        base,
        ["codigo", "codigo_fornecedor", "sku", "referencia", "ref", "cprod"],
    )
    col_descricao = _primeira_coluna_existente(
        base,
        ["descricao", "descricao_fornecedor", "produto", "nome", "xprod", "titulo"],
    )
    col_preco = _primeira_coluna_existente(
        base,
        ["preco", "preco_base", "valor", "valor unitario", "vUnCom", "vuncom"],
    )
    col_quantidade = _primeira_coluna_existente(
        base,
        ["quantidade", "quantidade_real", "estoque", "saldo", "qcom", "balanco"],
    )
    col_gtin = _primeira_coluna_existente(
        base,
        ["gtin", "ean", "gtin/ean", "codigo de barras", "cean"],
    )
    col_imagem = _primeira_coluna_existente(
        base,
        ["url_imagens", "imagem", "imagens", "url imagem", "url imagens"],
    )
    col_categoria = _primeira_coluna_existente(
        base,
        ["categoria", "departamento", "breadcrumb", "grupo"],
    )

    saida = pd.DataFrame(index=base.index)
    saida["codigo_fornecedor"] = base[col_codigo] if col_codigo else ""
    saida["descricao_fornecedor"] = base[col_descricao] if col_descricao else ""
    saida["preco_base"] = base[col_preco].apply(_formatar_numero_bling) if col_preco else ""
    saida["quantidade_real"] = base[col_quantidade] if col_quantidade else ""
    saida["gtin"] = base[col_gtin] if col_gtin else ""
    saida["categoria"] = base[col_categoria] if col_categoria else ""
    saida["url_imagens"] = base[col_imagem] if col_imagem else ""

    for col in base.columns:
        if col not in saida.columns:
            saida[col] = base[col]

    return saida.fillna("")


# ============================================================
# FONTES EXTERNAS
# ============================================================

def _executar_busca_site(url: str, padrao_disponivel: int) -> pd.DataFrame:
    if executar_crawler_site is None:
        log_debug("Crawler do projeto não disponível.", "WARNING")
        return pd.DataFrame()

    tentativas = [
        lambda: executar_crawler_site(
            url=url,
            max_paginas=5,
            max_threads=5,
            padrao_disponivel=padrao_disponivel,
        ),
        lambda: executar_crawler_site(url, 5, 5, padrao_disponivel),
    ]

    for tentativa in tentativas:
        try:
            df = tentativa()
            if isinstance(df, pd.DataFrame):
                return df.fillna("")
        except Exception:
            continue

    return pd.DataFrame()


def _executar_api_fornecedor(fornecedor: str, categoria: str = "") -> pd.DataFrame:
    if buscar_produtos_fornecedor is None:
        log_debug("Fetch router do projeto não disponível.", "WARNING")
        return pd.DataFrame()

    tentativas = [
        lambda: buscar_produtos_fornecedor(
            fornecedor=fornecedor,
            categoria=categoria,
            operacao=st.session_state.get("tipo_operacao_bling", "cadastro"),
        ),
        lambda: buscar_produtos_fornecedor(fornecedor, categoria),
        lambda: buscar_produtos_fornecedor(fornecedor),
    ]

    for tentativa in tentativas:
        try:
            df = tentativa()
            if isinstance(df, pd.DataFrame):
                return df.fillna("")
        except Exception:
            continue

    return pd.DataFrame()


# ============================================================
# RENDER
# ============================================================

def render_origem_dados() -> Optional[pd.DataFrame]:
    st.markdown("### Origem dos dados")
    st.caption(
        "Escolha a operação, informe a origem e prepare a base para precificação e mapeamento."
    )

    operacao_atual = _safe_str(
        st.session_state.get("tipo_operacao") or "Cadastro de Produtos"
    )
    if operacao_atual not in {"Cadastro de Produtos", "Atualização de Estoque"}:
        operacao_atual = "Cadastro de Produtos"

    if "tipo_operacao_bling" not in st.session_state:
        _set_operacao(operacao_atual)
    if "df_modelo_operacao" not in st.session_state or st.session_state.get("df_modelo_operacao") is None:
        st.session_state["df_modelo_operacao"] = _modelo_padrao_por_operacao(
            st.session_state.get("tipo_operacao_bling", "cadastro")
        )

    st.markdown("#### O que você quer fazer?")
    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "Cadastro de Produtos",
            use_container_width=True,
            type="primary" if operacao_atual == "Cadastro de Produtos" else "secondary",
            key="origem_btn_cadastro",
        ):
            _set_operacao("Cadastro de Produtos")
            st.rerun()

    with col2:
        if st.button(
            "Atualização de Estoque",
            use_container_width=True,
            type="primary" if operacao_atual == "Atualização de Estoque" else "secondary",
            key="origem_btn_estoque",
        ):
            _set_operacao("Atualização de Estoque")
            st.rerun()

    if st.session_state.get("tipo_operacao_bling") == "estoque":
        deposito_atual = _safe_str(st.session_state.get("deposito_nome"))
        deposito_digitado = st.text_input(
            "Nome do depósito",
            value=deposito_atual,
            key="origem_deposito_nome",
        )
        st.session_state["deposito_nome"] = deposito_digitado

    st.markdown("#### Como deseja informar a origem?")

    opcoes_origem = [
        "Planilha fornecedora",
        "XML da nota fiscal",
        "Buscar pelo site",
        "Fornecedor via API",
    ]

    valor_atual_origem = _safe_str(st.session_state.get("origem_tipo_radio"))
    if valor_atual_origem not in opcoes_origem:
        valor_atual_origem = "Planilha fornecedora"
        st.session_state["origem_tipo_radio"] = valor_atual_origem

    origem_tipo = st.radio(
        "Selecione a origem",
        options=opcoes_origem,
        index=opcoes_origem.index(valor_atual_origem),
        horizontal=False,
        key="origem_tipo_radio",
    )

    df_novo = None

    if origem_tipo == "Planilha fornecedora":
        upload = st.file_uploader(
            "Envie CSV, XLSX ou XLS",
            type=["csv", "xlsx", "xls"],
            key="origem_upload_fornecedor",
        )
        if upload is not None:
            df_lido = _ler_upload_arquivo(upload)
            df_novo = _normalizar_df_origem(df_lido) if safe_df_dados(df_lido) else None
            if df_novo is None or not safe_df_dados(df_novo):
                st.error("Não foi possível ler a planilha enviada.")

    elif origem_tipo == "XML da nota fiscal":
        upload_xml = st.file_uploader(
            "Envie o XML da nota fiscal",
            type=["xml"],
            key="origem_upload_xml",
        )
        if upload_xml is not None:
            df_lido = _ler_upload_arquivo(upload_xml)
            df_novo = _normalizar_df_origem(df_lido) if safe_df_dados(df_lido) else None
            if df_novo is None or not safe_df_dados(df_novo):
                st.error("Não foi possível ler o XML enviado.")

    elif origem_tipo == "Buscar pelo site":
        url_site = st.text_input(
            "URL do site ou categoria do fornecedor",
            value=_safe_str(st.session_state.get("origem_site_url")),
            key="origem_site_url_input",
            placeholder="https://www.seusite.com.br/categoria/produtos",
        )
        st.session_state["origem_site_url"] = url_site

        padrao_disponivel = st.number_input(
            "Quantidade padrão quando o site indicar disponibilidade sem número exato",
            min_value=0,
            value=int(st.session_state.get("padrao_disponivel_site", 10) or 10),
            step=1,
            key="origem_padrao_disponivel_site",
        )
        st.session_state["padrao_disponivel_site"] = int(padrao_disponivel)

        if st.button("Buscar produtos no site", use_container_width=True, key="origem_btn_buscar_site"):
            if not _safe_str(url_site):
                st.warning("Informe a URL do site para iniciar a busca.")
            else:
                with st.spinner("Buscando produtos no site..."):
                    df_site = _executar_busca_site(url_site, int(padrao_disponivel))
                    df_novo = _normalizar_df_origem(df_site) if safe_df_dados(df_site) else None

                if df_novo is None or not safe_df_dados(df_novo):
                    st.error("Nenhum produto válido foi encontrado no site.")

    else:
        fornecedores = listar_fornecedores_disponiveis()
        opcoes_fornecedor = (
            fornecedores if fornecedores else ["Atacadum", "Mega Center Eletrônicos", "Oba Oba Mix"]
        )

        valor_fornecedor = _safe_str(st.session_state.get("origem_fornecedor_api"))
        if valor_fornecedor not in opcoes_fornecedor:
            valor_fornecedor = opcoes_fornecedor[0]

        fornecedor_escolhido = st.selectbox(
            "Selecione o fornecedor",
            options=opcoes_fornecedor,
            index=opcoes_fornecedor.index(valor_fornecedor),
            key="origem_fornecedor_api",
        )

        categoria_api = st.text_input(
            "Categoria opcional",
            value=_safe_str(st.session_state.get("origem_categoria_api")),
            key="origem_categoria_api_input",
            placeholder="Ex.: smartwatch, caixas de som, cabos",
        )
        st.session_state["origem_categoria_api"] = categoria_api

        if st.button("Buscar produtos do fornecedor", use_container_width=True, key="origem_btn_buscar_api"):
            fornecedor_normalizado = fornecedor_escolhido
            fornecedor_norm = normalizar_coluna_busca(fornecedor_escolhido)

            if "mega center" in fornecedor_norm:
                fornecedor_normalizado = "mega_center"
            elif "oba oba" in fornecedor_norm:
                fornecedor_normalizado = "oba_oba_mix"
            elif "atacadum" in fornecedor_norm:
                fornecedor_normalizado = "atacadum"

            with st.spinner("Buscando produtos do fornecedor..."):
                df_api = _executar_api_fornecedor(
                    fornecedor=fornecedor_normalizado,
                    categoria=categoria_api,
                )
                df_novo = _normalizar_df_origem(df_api) if safe_df_dados(df_api) else None

            if df_novo is None or not safe_df_dados(df_novo):
                st.error("Nenhum produto válido foi encontrado no fornecedor selecionado.")

    if safe_df_dados(df_novo):
        st.session_state["df_origem"] = df_novo.copy()
        st.session_state["origem_tipo"] = origem_tipo
        st.session_state["df_modelo_operacao"] = _modelo_padrao_por_operacao(
            st.session_state.get("tipo_operacao_bling", "cadastro")
        )
        _limpar_fluxo_abaixo_da_origem()
        log_debug(f"Origem carregada com sucesso: {origem_tipo}", "INFO")

    df_origem = _resolver_df_origem_atual()

    if safe_df_dados(df_origem):
        st.success(
            f"Origem pronta com {len(df_origem)} linha(s) e {len(df_origem.columns)} coluna(s)."
        )
        with st.expander("Preview da origem", expanded=False):
            st.dataframe(df_origem.head(50), use_container_width=True)
    else:
        st.info("Carregue uma origem para liberar o próximo passo.")

    st.markdown("---")
    pode_continuar = safe_df_dados(df_origem)

    if st.button(
        "Continuar ➜",
        use_container_width=True,
        disabled=not pode_continuar,
        key="origem_btn_continuar",
    ):
        st.session_state["df_saida"] = df_origem.copy()
        sincronizar_etapa_global("precificacao")
        st.rerun()

    return df_origem
