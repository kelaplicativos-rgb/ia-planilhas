
from __future__ import annotations

import io
from typing import Optional

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import (
    log_debug,
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


def _normalizar_texto_coluna(valor: str) -> str:
    texto = _safe_str(valor).lower()
    trocas = {
        "ã": "a",
        "á": "a",
        "à": "a",
        "â": "a",
        "é": "e",
        "ê": "e",
        "í": "i",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "ú": "u",
        "ç": "c",
        "/": " ",
        "-": " ",
        "_": " ",
        "(": " ",
        ")": " ",
        ".": " ",
    }
    for origem, destino in trocas.items():
        texto = texto.replace(origem, destino)
    return " ".join(texto.split())


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
    numero = _to_float_brasil(valor)
    return f"{numero:.2f}".replace(".", ",")


def _limpar_fluxo_abaixo_da_origem() -> None:
    for chave in [
        "df_saida",
        "df_final",
        "df_precificado",
        "df_calc_precificado",
        "df_preview_mapeamento",
        "mapping_origem",
        "mapping_origem_rascunho",
        "mapping_origem_defaults",
    ]:
        if chave in st.session_state:
            st.session_state[chave] = {} if "mapping" in chave else None


def _modelo_padrao_por_operacao(tipo_operacao_bling: str) -> pd.DataFrame:
    if tipo_operacao_bling == "estoque":
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


def _parse_xml_basico(upload) -> pd.DataFrame:
    if converter_upload_xml_para_dataframe is not None:
        try:
            df_xml = converter_upload_xml_para_dataframe(upload)
            if isinstance(df_xml, pd.DataFrame):
                return df_xml.fillna("")
        except Exception as e:
            log_debug(f"Falha no parser XML do projeto: {e}", "WARNING")

    try:
        import xml.etree.ElementTree as ET

        bruto = upload.getvalue()
        root = ET.fromstring(bruto)

        produtos = []
        for elem in root.iter():
            tag = elem.tag.lower()
            if tag.endswith("det"):
                atual = {
                    "codigo_fornecedor": "",
                    "descricao_fornecedor": "",
                    "preco_base": "",
                    "quantidade_real": "",
                    "gtin": "",
                }
                for sub in elem.iter():
                    stag = sub.tag.lower()
                    texto = _safe_str(sub.text)

                    if not texto:
                        continue

                    if stag.endswith("cprod") and not atual["codigo_fornecedor"]:
                        atual["codigo_fornecedor"] = texto
                    elif stag.endswith("xprod") and not atual["descricao_fornecedor"]:
                        atual["descricao_fornecedor"] = texto
                    elif stag.endswith("vuncom") and not atual["preco_base"]:
                        atual["preco_base"] = texto
                    elif stag.endswith("qcom") and not atual["quantidade_real"]:
                        atual["quantidade_real"] = texto
                    elif stag.endswith("cean") and not atual["gtin"]:
                        atual["gtin"] = texto

                if atual["descricao_fornecedor"] or atual["codigo_fornecedor"]:
                    produtos.append(atual)

        return pd.DataFrame(produtos).fillna("")
    except Exception as e:
        log_debug(f"Erro lendo XML básico: {e}", "ERROR")
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
            return _parse_xml_basico(upload)
    except Exception as e:
        log_debug(f"Erro lendo upload: {e}", "ERROR")

    return None


# ============================================================
# NORMALIZAÇÃO DA ORIGEM
# ============================================================

def _primeira_coluna_existente(df: pd.DataFrame, candidatos: list[str]) -> str:
    mapa = {_normalizar_texto_coluna(col): col for col in df.columns}
    for candidato in candidatos:
        chave = _normalizar_texto_coluna(candidato)
        if chave in mapa:
            return mapa[chave]

    for col in df.columns:
        ncol = _normalizar_texto_coluna(col)
        for candidato in candidatos:
            if _normalizar_texto_coluna(candidato) in ncol:
                return col

    return ""


def _normalizar_df_origem(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()

    base = df.copy().fillna("")
    base.columns = [_safe_str(c) for c in base.columns]

    col_codigo = _primeira_coluna_existente(
        base,
        [
            "codigo",
            "codigo fornecedor",
            "codigo_fornecedor",
            "sku",
            "referencia",
            "ref",
            "cod",
            "cprod",
        ],
    )
    col_descricao = _primeira_coluna_existente(
        base,
        [
            "descricao",
            "descricao fornecedor",
            "descricao_fornecedor",
            "produto",
            "nome",
            "xprod",
            "titulo",
        ],
    )
    col_preco = _primeira_coluna_existente(
        base,
        [
            "preco",
            "preco base",
            "preco_base",
            "valor",
            "valor unitario",
            "preco site",
            "vuncom",
        ],
    )
    col_quantidade = _primeira_coluna_existente(
        base,
        [
            "quantidade",
            "quantidade_real",
            "estoque",
            "saldo",
            "qcom",
            "balanco",
        ],
    )
    col_gtin = _primeira_coluna_existente(
        base,
        ["gtin", "ean", "gtin/ean", "codigo de barras", "cean"]
    )
    col_imagem = _primeira_coluna_existente(
        base,
        ["imagem", "imagens", "url imagem", "url imagens", "image", "images"]
    )
    col_categoria = _primeira_coluna_existente(
        base,
        ["categoria", "departamento", "breadcrumb", "grupo"]
    )

    df_saida = pd.DataFrame()
    df_saida["codigo_fornecedor"] = base[col_codigo] if col_codigo else ""
    df_saida["descricao_fornecedor"] = base[col_descricao] if col_descricao else ""
    df_saida["preco_base"] = (
        base[col_preco].map(_formatar_numero_bling) if col_preco else ""
    )
    df_saida["quantidade_real"] = base[col_quantidade] if col_quantidade else ""
    df_saida["gtin"] = base[col_gtin] if col_gtin else ""
    df_saida["categoria"] = base[col_categoria] if col_categoria else ""
    df_saida["url_imagens"] = base[col_imagem] if col_imagem else ""

    for col in base.columns:
        if col not in df_saida.columns:
            df_saida[col] = base[col]

    df_saida = df_saida.fillna("").astype(str)
    return df_saida


# ============================================================
# ORIGEM POR SITE
# ============================================================

def _executar_busca_site(url: str, padrao_disponivel: int) -> pd.DataFrame:
    if executar_crawler_site is None:
        log_debug(
            "Crawler do projeto não disponível. Origem por site está em modo inativo.",
            "WARNING",
        )
        return pd.DataFrame()

    try:
        df = executar_crawler_site(
            url=url,
            max_paginas=5,
            max_threads=5,
            padrao_disponivel=padrao_disponivel,
        )
        if isinstance(df, pd.DataFrame):
            return df.fillna("")
    except TypeError:
        try:
            df = executar_crawler_site(url, 5, 5, padrao_disponivel)
            if isinstance(df, pd.DataFrame):
                return df.fillna("")
        except Exception as e:
            log_debug(f"Erro no crawler por assinatura alternativa: {e}", "ERROR")
            return pd.DataFrame()
    except Exception as e:
        log_debug(f"Erro executando crawler do site: {e}", "ERROR")
        return pd.DataFrame()

    return pd.DataFrame()


# ============================================================
# RENDER
# ============================================================

def render_origem_dados() -> Optional[pd.DataFrame]:
    st.markdown("### Origem dos dados")
    st.caption(
        "Escolha a operação, carregue a base por planilha/XML/site e siga para a precificação."
    )

    operacao_atual = _safe_str(
        st.session_state.get("tipo_operacao") or "Cadastro de Produtos"
    )
    if operacao_atual not in {"Cadastro de Produtos", "Atualização de Estoque"}:
        operacao_atual = "Cadastro de Produtos"

    if "tipo_operacao_bling" not in st.session_state:
        _set_operacao(operacao_atual)
    if "df_modelo_operacao" not in st.session_state:
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
        ):
            _set_operacao("Cadastro de Produtos")
            st.rerun()

    with col2:
        if st.button(
            "Atualização de Estoque",
            use_container_width=True,
            type="primary" if operacao_atual == "Atualização de Estoque" else "secondary",
        ):
            _set_operacao("Atualização de Estoque")
            st.rerun()

    if st.session_state.get("tipo_operacao_bling") == "estoque":
        deposito_atual = _safe_str(st.session_state.get("deposito_nome"))
        deposito_digitado = st.text_input(
            "Nome do depósito",
            value=deposito_atual,
            key="deposito_nome_input",
        )
        st.session_state["deposito_nome"] = deposito_digitado

    st.markdown("#### Como deseja informar a origem?")
    origem_tipo = st.radio(
        "Selecione a origem",
        ["Planilha fornecedora", "XML da nota fiscal", "Buscar pelo site"],
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

    else:
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
            key="padrao_disponivel_site_input",
        )
        st.session_state["padrao_disponivel_site"] = int(padrao_disponivel)

        if st.button("Buscar produtos no site", use_container_width=True):
            if not _safe_str(url_site):
                st.warning("Informe a URL do site para iniciar a busca.")
            else:
                with st.spinner("Buscando produtos no site..."):
                    df_site = _executar_busca_site(url_site, int(padrao_disponivel))
                    df_novo = _normalizar_df_origem(df_site) if safe_df_dados(df_site) else None

                if df_novo is None or not safe_df_dados(df_novo):
                    st.error("Nenhum produto válido foi encontrado no site.")

    if safe_df_dados(df_novo):
        st.session_state["df_origem"] = df_novo.copy()
        st.session_state["origem_tipo"] = origem_tipo
        _limpar_fluxo_abaixo_da_origem()
        st.session_state["df_origem"] = df_novo.copy()
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

    if st.button("Continuar ➜", use_container_width=True, disabled=not pode_continuar):
        st.session_state["df_saida"] = df_origem.copy()
        sincronizar_etapa_global("precificacao")
        st.rerun()

    return df_origem
