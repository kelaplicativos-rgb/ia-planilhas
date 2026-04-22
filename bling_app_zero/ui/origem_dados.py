from __future__ import annotations

import io
from pathlib import Path
import xml.etree.ElementTree as ET

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import (
    ir_para_etapa,
    safe_df_dados,
    safe_df_estrutura,
)
from bling_app_zero.ui.origem_site_panel import render_origem_site_panel


EXTENSOES_ORIGEM = {".csv", ".xlsx", ".xls", ".xml", ".pdf"}
EXTENSOES_MODELO = {".csv", ".xlsx", ".xls"}


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


def _limpar_estado_origem() -> None:
    for chave in [
        "df_origem",
        "origem_upload_nome",
        "origem_upload_bytes",
        "origem_upload_tipo",
        "origem_upload_ext",
    ]:
        st.session_state.pop(chave, None)


def _limpar_estado_modelo() -> None:
    for chave in [
        "df_modelo",
        "modelo_upload_nome",
        "modelo_upload_bytes",
        "modelo_upload_tipo",
        "modelo_upload_ext",
    ]:
        st.session_state.pop(chave, None)


def _ler_tabular(upload) -> pd.DataFrame:
    nome = str(upload.name).lower()

    if nome.endswith(".csv"):
        bruto = upload.getvalue()

        for encoding in ("utf-8", "utf-8-sig", "latin1"):
            for sep in (";", ",", "\t", "|"):
                try:
                    df = pd.read_csv(
                        io.BytesIO(bruto),
                        sep=sep,
                        dtype=str,
                        encoding=encoding,
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

        def get(tag: str) -> str:
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
    with st.expander(titulo, expanded=False):
        if not isinstance(df, pd.DataFrame):
            st.info("Arquivo sem estrutura tabular.")
            return

        if len(df.columns) == 0:
            st.error("Nenhuma coluna encontrada.")
            return

        if df.empty:
            st.info("Arquivo carregado sem linhas.")
            st.dataframe(pd.DataFrame(columns=df.columns), use_container_width=True)
            return

        st.dataframe(df.head(20), use_container_width=True)


def _processar_upload_origem(upload) -> None:
    if upload is None:
        _limpar_estado_origem()
        return

    ext = _extensao(upload)
    if ext not in EXTENSOES_ORIGEM:
        st.error("Arquivo de origem inválido. Envie CSV, XLSX, XLS, XML ou PDF.")
        return

    if _eh_excel_familia(ext):
        try:
            df = _normalizar_df(_ler_tabular(upload))
        except Exception as exc:
            st.error(f"Não foi possível ler a planilha de origem: {exc}")
            return

        if not safe_df_dados(df):
            st.error("A planilha de origem precisa ter linhas com dados.")
            return

        st.session_state["df_origem"] = df
        _guardar_upload_bruto("origem_upload", upload, "tabular")
        st.success(f"Arquivo de origem carregado: {upload.name}")
        _preview_dataframe(df, "Preview da origem")
        return

    if ext == ".xml":
        df = _parse_xml_nfe(upload)
        if not safe_df_dados(df):
            st.error("Não foi possível extrair dados do XML.")
            return

        st.session_state["df_origem"] = df
        _guardar_upload_bruto("origem_upload", upload, "xml")
        st.success("XML convertido com sucesso.")
        _preview_dataframe(df, "Preview do XML")
        return

    _guardar_upload_bruto("origem_upload", upload, "documento")
    st.warning("PDF ainda não processado automaticamente.")


def _processar_upload_modelo(upload) -> None:
    if upload is None:
        _limpar_estado_modelo()
        return

    ext = _extensao(upload)
    if ext not in EXTENSOES_MODELO:
        st.error("Arquivo modelo inválido. Envie CSV, XLSX ou XLS.")
        return

    try:
        df = _normalizar_df(_ler_tabular(upload))
    except Exception as exc:
        st.error(f"Não foi possível ler o modelo: {exc}")
        return

    if not safe_df_estrutura(df):
        st.error("O modelo precisa ter pelo menos os cabeçalhos/colunas.")
        return

    st.session_state["df_modelo"] = df
    _guardar_upload_bruto("modelo_upload", upload, "tabular")
    st.success(f"Modelo carregado: {upload.name}")
    _preview_dataframe(df, "Preview do modelo")


def _origem_pronta() -> bool:
    return safe_df_dados(st.session_state.get("df_origem"))


def _modelo_pronto() -> bool:
    return safe_df_estrutura(st.session_state.get("df_modelo"))


def _render_operacao() -> None:
    tipo_atual = st.session_state.get("tipo_operacao", "cadastro")

    opcoes = {
        "Cadastro de Produtos": "cadastro",
        "Atualização de Estoque": "estoque",
    }

    label_inicial = "Cadastro de Produtos"
    for label, valor in opcoes.items():
        if valor == tipo_atual:
            label_inicial = label
            break

    escolha = st.radio(
        "Escolha a operação",
        options=list(opcoes.keys()),
        index=list(opcoes.keys()).index(label_inicial),
        horizontal=True,
        key="tipo_operacao_visual",
    )

    novo_tipo = opcoes[escolha]
    st.session_state["tipo_operacao"] = novo_tipo
    st.session_state["tipo_operacao_bling"] = novo_tipo


def _render_dados_operacao() -> None:
    operacao = str(st.session_state.get("tipo_operacao", "cadastro") or "cadastro").strip().lower()

    if operacao != "estoque":
        return

    with st.container(border=True):
        st.markdown("### Dados da operação")
        valor_atual = str(st.session_state.get("deposito_nome", "") or "").strip()

        novo_valor = st.text_input(
            "Nome do depósito",
            value=valor_atual,
            key="deposito_nome_input",
            placeholder="Ex.: Depósito Principal",
            help="Esse valor será levado para a planilha final.",
        ).strip()

        st.session_state["deposito_nome"] = novo_valor


def _render_origem_arquivo() -> None:
    with st.container(border=True):
        st.markdown("### Arquivo do fornecedor")
        st.caption("Use esta opção para planilha, XML ou PDF.")

        upload_origem = st.file_uploader(
            "Selecionar arquivo de origem",
            key="upload_origem",
        )

        if upload_origem is not None:
            _processar_upload_origem(upload_origem)


def _render_modelo() -> None:
    with st.container(border=True):
        st.markdown("### Modelo do Bling")
        st.caption("Envie o modelo oficial de cadastro ou estoque.")

        upload_modelo = st.file_uploader(
            "Selecionar modelo",
            key="upload_modelo",
        )

        if upload_modelo:
            _processar_upload_modelo(upload_modelo)


def _validar_dados_operacao_para_continuar() -> bool:
    operacao = str(st.session_state.get("tipo_operacao", "cadastro") or "cadastro").strip().lower()

    if operacao != "estoque":
        return True

    deposito_nome = str(st.session_state.get("deposito_nome", "") or "").strip()
    if not deposito_nome:
        st.error("Informe o nome do depósito para continuar no fluxo de estoque.")
        return False

    return True


def _render_resumo() -> None:
    df_origem = st.session_state.get("df_origem")
    df_modelo = st.session_state.get("df_modelo")
    operacao = str(st.session_state.get("tipo_operacao", "cadastro") or "cadastro").strip().lower()
    deposito_nome = str(st.session_state.get("deposito_nome", "") or "").strip()

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Origem", 0 if not isinstance(df_origem, pd.DataFrame) else len(df_origem))
    with c2:
        st.metric("Modelo", 0 if not isinstance(df_modelo, pd.DataFrame) else len(df_modelo.columns))
    with c3:
        st.metric("Depósito" if operacao == "estoque" else "Operação", deposito_nome or operacao.title())


def _render_continuar() -> None:
    st.markdown("### Continuar")
    _render_resumo()

    if not _origem_pronta():
        st.info("Carregue uma origem válida para continuar.")
        return

    if not _modelo_pronto():
        st.info("Envie um modelo válido para continuar.")
        return

    if not _validar_dados_operacao_para_continuar():
        return

    if st.button("Continuar ➜", key="btn_continuar_origem", use_container_width=True):
        ir_para_etapa("precificacao")


def render_origem_dados() -> None:
    st.subheader("1. Origem dos dados")

    _render_operacao()
    _render_dados_operacao()

    modo = st.radio(
        "Como deseja informar a origem?",
        ["Arquivo do fornecedor", "Buscar no site do fornecedor"],
        horizontal=True,
        key="modo_origem",
    )

    if modo == "Arquivo do fornecedor":
        _render_origem_arquivo()
    else:
        render_origem_site_panel()

    _render_modelo()
    st.markdown("---")
    _render_continuar()

