import io
from pathlib import Path
import xml.etree.ElementTree as ET

import pandas as pd
import streamlit as st

from bling_app_zero.core.site_agent import buscar_produtos_site_com_gpt
from bling_app_zero.ui.app_helpers import (
    ir_para_etapa,
    safe_df,
    safe_df_estrutura,
)


EXTENSOES_ORIGEM = {".csv", ".xlsx", ".xls", ".xml", ".pdf"}
EXTENSOES_MODELO = {".csv", ".xlsx", ".xls", ".xml", ".pdf"}


def _extensao(upload) -> str:
    nome = str(getattr(upload, "name", "") or "").strip().lower()
    return Path(nome).suffix.lower()


def _eh_excel_familia(ext: str) -> bool:
    return ext in {".csv", ".xlsx", ".xls"}


def _normalizar_df(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()

    base = df.copy().fillna("")
    base.columns = [str(c).strip() for c in base.columns]
    return base


def _guardar_upload_bruto(chave_prefixo: str, upload, tipo: str) -> None:
    st.session_state[f"{chave_prefixo}_nome"] = str(upload.name)
    st.session_state[f"{chave_prefixo}_bytes"] = upload.getvalue()
    st.session_state[f"{chave_prefixo}_tipo"] = tipo
    st.session_state[f"{chave_prefixo}_ext"] = _extensao(upload)


def _ler_tabular(upload):
    nome = str(upload.name).lower()

    if nome.endswith(".csv"):
        bruto = upload.getvalue()

        for sep in [";", ",", "\t", "|"]:
            try:
                df = pd.read_csv(
                    io.BytesIO(bruto),
                    sep=sep,
                    dtype=str,
                    encoding="utf-8",
                    engine="python",
                ).fillna("")

                df.columns = [str(c).strip() for c in df.columns if str(c).strip()]

                if len(df.columns) > 0:
                    return df

            except Exception:
                continue

        raise ValueError("Não foi possível ler o CSV.")

    if nome.endswith(".xlsx") or nome.endswith(".xls"):
        df = pd.read_excel(upload, dtype=str).fillna("")
        df.columns = [str(c).strip() for c in df.columns if str(c).strip()]
        return df

    raise ValueError("Arquivo tabular inválido.")


def _parse_xml_nfe(upload) -> pd.DataFrame:
    try:
        xml_bytes = upload.getvalue()
        root = ET.fromstring(xml_bytes)
    except Exception:
        return pd.DataFrame()

    ns = {"nfe": "http://www.portalfiscal.inf.br/nfe"}
    itens = root.findall(".//nfe:det", ns)
    rows = []

    for det in itens:
        prod = det.find(".//nfe:prod", ns)
        if prod is None:
            continue

        def get(tag):
            el = prod.find(f"nfe:{tag}", ns)
            return el.text.strip() if el is not None and el.text else ""

        gtin = get("cEAN")
        if gtin in {"SEM GTIN", "SEM EAN"}:
            gtin = ""

        rows.append(
            {
                "Código": get("cProd"),
                "Descrição": get("xProd"),
                "NCM": get("NCM"),
                "CFOP": get("CFOP"),
                "Unidade": get("uCom"),
                "Quantidade": get("qCom"),
                "Preço de custo": get("vUnCom"),
                "Valor total": get("vProd"),
                "GTIN": gtin,
            }
        )

    return pd.DataFrame(rows)


def _preview_dataframe(df: pd.DataFrame, titulo: str) -> None:
    st.markdown(f"**{titulo}**")

    if not isinstance(df, pd.DataFrame):
        st.info("Arquivo sem estrutura tabular.")
        return

    if len(df.columns) == 0:
        st.error("Nenhuma coluna encontrada no arquivo.")
        return

    if df.empty:
        st.success("Modelo carregado corretamente (sem linhas, apenas estrutura).")
        preview = pd.DataFrame(columns=df.columns)
        st.dataframe(preview, use_container_width=True)
        return

    st.dataframe(df.head(10), use_container_width=True)


def _processar_upload_origem(upload):
    if upload is None:
        return

    ext = _extensao(upload)

    if ext not in EXTENSOES_ORIGEM:
        st.error("Arquivo de origem inválido. Envie CSV, XLSX, XLS, XML ou PDF.")
        return

    if _eh_excel_familia(ext):
        df = _normalizar_df(_ler_tabular(upload))

        if not safe_df(df):
            st.error("A planilha de origem precisa ter linhas com dados.")
            return

        st.session_state["df_origem"] = df
        _guardar_upload_bruto("origem_upload", upload, "tabular")

        st.success(f"Arquivo de origem carregado: {upload.name}")
        _preview_dataframe(df, "Preview da origem")
        return

    if ext == ".xml":
        df = _parse_xml_nfe(upload)

        if not safe_df(df):
            st.error("Não foi possível extrair dados do XML.")
            return

        st.session_state["df_origem"] = df
        _guardar_upload_bruto("origem_upload", upload, "xml")

        st.success("XML convertido com sucesso.")
        _preview_dataframe(df, "Preview do XML")
        return

    _guardar_upload_bruto("origem_upload", upload, "documento")
    st.warning("PDF ainda não processado.")


def _processar_upload_modelo(upload):
    if upload is None:
        return

    ext = _extensao(upload)

    if ext not in EXTENSOES_MODELO:
        st.error("Arquivo modelo inválido. Envie CSV, XLSX, XLS, XML ou PDF.")
        return

    if _eh_excel_familia(ext):
        df = _normalizar_df(_ler_tabular(upload))

        if not safe_df_estrutura(df):
            st.error("O modelo precisa ter pelo menos os cabeçalhos/colunas.")
            return

        st.session_state["df_modelo"] = df
        _guardar_upload_bruto("modelo_upload", upload, "tabular")

        st.success(f"Modelo carregado: {upload.name}")
        _preview_dataframe(df, "Preview do modelo")
        return


def _origem_pronta() -> bool:
    return safe_df(st.session_state.get("df_origem"))


def _modelo_pronto() -> bool:
    return safe_df_estrutura(st.session_state.get("df_modelo"))


def render_origem_dados():
    st.subheader("1. Origem dos dados")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Cadastro de Produtos", use_container_width=True):
            st.session_state["tipo_operacao"] = "cadastro"
            st.session_state["tipo_operacao_bling"] = "cadastro"

    with col2:
        if st.button("Atualização de Estoque", use_container_width=True):
            st.session_state["tipo_operacao"] = "estoque"
            st.session_state["tipo_operacao_bling"] = "estoque"

    if not st.session_state.get("tipo_operacao"):
        st.info("Escolha uma operação para continuar.")
        return

    st.success(f"Operação: {st.session_state['tipo_operacao']}")

    if st.session_state["tipo_operacao"] == "estoque":
        deposito = st.text_input(
            "Nome do depósito",
            value=st.session_state.get("deposito_nome", ""),
            placeholder="Digite o nome do depósito",
        )
        st.session_state["deposito_nome"] = deposito

    st.markdown("### Como deseja trazer a origem?")
    modo_origem = st.radio(
        "Selecione a origem",
        options=["Arquivo do fornecedor", "Buscar no site do fornecedor"],
        horizontal=True,
        key="modo_origem",
    )

    if modo_origem == "Arquivo do fornecedor":
        st.markdown("### Arquivo do fornecedor")
        st.caption("Aceita XML, PDF e família Excel.")

        upload_origem = st.file_uploader(
            "Toque para selecionar o arquivo do fornecedor",
            key="upload_origem",
            help="Aceita CSV, XLSX, XLS, XML e PDF",
        )

        if upload_origem is not None:
            _processar_upload_origem(upload_origem)

    else:
        st.markdown("### Busca no site do fornecedor")
        url_site = st.text_input(
            "URL base do fornecedor",
            value=st.session_state.get("site_fornecedor_url", ""),
            placeholder="https://fornecedor.com.br",
        )
        termo_busca = st.text_input(
            "Busca / categoria / termo",
            value=st.session_state.get("site_fornecedor_termo", ""),
            placeholder="Ex.: caixa de som, smartwatch, cabos",
        )
        limite_links = st.number_input(
            "Limite inicial de produtos para varredura",
            min_value=1,
            max_value=100,
            value=int(st.session_state.get("site_fornecedor_limite", 20) or 20),
            step=1,
        )

        st.session_state["site_fornecedor_url"] = url_site
        st.session_state["site_fornecedor_termo"] = termo_busca
        st.session_state["site_fornecedor_limite"] = int(limite_links)

        if st.button("✨ Buscar produtos com GPT", use_container_width=True, key="btn_buscar_site_gpt"):
            if not str(url_site).strip():
                st.error("Informe a URL base do fornecedor.")
            elif not str(termo_busca).strip():
                st.error("Informe o termo/categoria da busca.")
            else:
                with st.spinner("Buscando produtos, coletando HTML e extraindo com GPT..."):
                    df_site = buscar_produtos_site_com_gpt(
                        base_url=url_site,
                        termo=termo_busca,
                        limite_links=int(limite_links),
                    )

                if not safe_df(df_site):
                    st.error("Nenhum produto foi encontrado na busca por site.")
                else:
                    st.session_state["df_origem"] = df_site
                    st.session_state["origem_upload_nome"] = f"busca_site_{termo_busca}"
                    st.session_state["origem_upload_tipo"] = "site_gpt"
                    st.session_state["origem_upload_ext"] = "site_gpt"

                    st.success(f"Busca concluída com {len(df_site)} produto(s).")
                    _preview_dataframe(df_site, "Preview da busca por site")

    st.markdown("### Modelo")
    upload_modelo = st.file_uploader(
        "Enviar modelo",
        key="upload_modelo",
        help="Aceita CSV, XLSX, XLS",
    )

    if upload_modelo:
        _processar_upload_modelo(upload_modelo)

    st.markdown("### Resumo")
    st.write(f"**Origem anexada:** {st.session_state.get('origem_upload_nome', 'não enviada')}")
    st.write(f"**Modelo anexado:** {st.session_state.get('modelo_upload_nome', 'não enviado')}")

    if safe_df(st.session_state.get("df_origem")):
        st.write(f"**Linhas origem:** {len(st.session_state['df_origem'])}")
        st.write(f"**Colunas origem:** {len(st.session_state['df_origem'].columns)}")

    if safe_df_estrutura(st.session_state.get("df_modelo")):
        st.write(f"**Linhas modelo:** {len(st.session_state['df_modelo'])}")
        st.write(f"**Colunas modelo:** {len(st.session_state['df_modelo'].columns)}")

    if _origem_pronta() and _modelo_pronto():
        if st.button("Continuar ➜", use_container_width=True):
            ir_para_etapa("precificacao")
    else:
        st.info("Envie/gere a origem e envie o modelo para continuar.")
