from __future__ import annotations

import io
from pathlib import Path
import xml.etree.ElementTree as ET

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_core_flow import set_etapa_segura
from bling_app_zero.ui.app_helpers import safe_df_dados, safe_df_estrutura
from bling_app_zero.ui.origem_auto_map_preview import render_preview_inteligente
from bling_app_zero.ui.origem_site_panel import render_origem_site_panel


EXTENSOES_ORIGEM = {".csv", ".xlsx", ".xls", ".xml"}
EXTENSOES_MODELO = {".csv", ".xlsx", ".xls"}


def _extensao(upload) -> str:
    return Path(str(getattr(upload, "name", "") or "").strip().lower()).suffix.lower()


def _normalizar_df(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    base = df.copy().fillna("")
    base.columns = [str(c).strip() for c in base.columns]
    return base


def _guardar_upload(prefixo: str, upload, tipo: str) -> None:
    st.session_state[f"{prefixo}_nome"] = str(upload.name)
    st.session_state[f"{prefixo}_bytes"] = upload.getvalue()
    st.session_state[f"{prefixo}_tipo"] = tipo
    st.session_state[f"{prefixo}_ext"] = _extensao(upload)


def _limpar(chaves: list[str]) -> None:
    for chave in chaves:
        st.session_state.pop(chave, None)


def _limpar_origem() -> None:
    _limpar([
        "df_origem", "df_saida", "df_preview_inteligente", "df_auto_mapa",
        "df_preview_fornecedor_modelo_bling", "df_preview_site_modelo_bling",
        "df_precificado", "df_final", "origem_site_preview_modelo_bling",
        "origem_fornecedor_preview_modelo_bling", "origem_upload_nome",
        "origem_upload_bytes", "origem_upload_tipo", "origem_upload_ext",
    ])


def _limpar_modelo() -> None:
    _limpar([
        "df_modelo", "df_origem", "df_saida", "df_preview_inteligente",
        "df_auto_mapa", "df_preview_fornecedor_modelo_bling",
        "df_preview_site_modelo_bling", "df_precificado", "df_final",
        "origem_site_preview_modelo_bling", "origem_fornecedor_preview_modelo_bling",
        "modelo_upload_nome", "modelo_upload_bytes", "modelo_upload_tipo",
        "modelo_upload_ext", "mapping_manual", "mapping_sugerido",
        "agent_ui_package", "_ia_auto_mapping_executado",
    ])


def _ler_tabular(upload) -> pd.DataFrame:
    nome = str(upload.name).lower()
    if nome.endswith(".csv"):
        bruto = upload.getvalue()
        for encoding in ("utf-8", "utf-8-sig", "latin1"):
            for sep in (";", ",", "\t", "|"):
                try:
                    df = pd.read_csv(io.BytesIO(bruto), sep=sep, dtype=str, encoding=encoding, engine="python").fillna("")
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
        root = ET.fromstring(upload.getvalue())
    except Exception:
        return pd.DataFrame()
    ns = {"nfe": "http://www.portalfiscal.inf.br/nfe"}
    rows = []
    for det in root.findall(".//nfe:det", ns):
        prod = det.find(".//nfe:prod", ns)
        if prod is None:
            continue

        def get(tag: str) -> str:
            el = prod.find(f"nfe:{tag}", ns)
            return el.text.strip() if el is not None and el.text else ""

        gtin = get("cEAN")
        if gtin in {"SEM GTIN", "SEM EAN"}:
            gtin = ""
        rows.append({
            "Código": get("cProd"), "Descrição": get("xProd"), "NCM": get("NCM"),
            "CFOP": get("CFOP"), "Unidade": get("uCom"), "Quantidade": get("qCom"),
            "Preço de custo": get("vUnCom"), "Valor total": get("vProd"), "GTIN": gtin,
        })
    return pd.DataFrame(rows)


def _preview(df: pd.DataFrame, titulo: str) -> None:
    with st.expander(titulo, expanded=False):
        if not isinstance(df, pd.DataFrame) or len(df.columns) == 0:
            st.info("Arquivo sem estrutura tabular.")
            return
        st.dataframe(df.head(20), use_container_width=True)


def _modelo_pronto() -> bool:
    return safe_df_estrutura(st.session_state.get("df_modelo"))


def _origem_pronta() -> bool:
    return safe_df_dados(st.session_state.get("df_origem"))


def _preview_pronto() -> bool:
    return safe_df_estrutura(st.session_state.get("df_preview_inteligente"))


def _processar_modelo(upload) -> None:
    if upload is None:
        _limpar_modelo()
        return
    if _extensao(upload) not in EXTENSOES_MODELO:
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
    _guardar_upload("modelo_upload", upload, "tabular")
    st.success(f"Modelo carregado: {upload.name}")
    _preview(df, "Estrutura do modelo Bling anexado")


def _processar_origem(upload) -> None:
    if upload is None:
        _limpar_origem()
        return
    if not _modelo_pronto():
        st.error("Anexe primeiro o modelo Bling antes de enviar a planilha do fornecedor.")
        return
    ext = _extensao(upload)
    if ext not in EXTENSOES_ORIGEM:
        st.error("Arquivo de origem inválido. Envie CSV, XLSX, XLS ou XML.")
        return
    try:
        df = _parse_xml_nfe(upload) if ext == ".xml" else _normalizar_df(_ler_tabular(upload))
    except Exception as exc:
        st.error(f"Não foi possível ler a origem: {exc}")
        return
    if not safe_df_dados(df):
        st.error("Não foi possível extrair dados da origem.")
        return
    st.session_state["df_origem"] = df
    _guardar_upload("origem_upload", upload, "xml" if ext == ".xml" else "tabular")
    st.success(f"Origem carregada: {upload.name}")
    _preview(df, "Preview bruto da origem")


def _render_operacao() -> None:
    atual = st.session_state.get("tipo_operacao", "cadastro")
    opcoes = {"Cadastro de Produtos": "cadastro", "Atualização de Estoque": "estoque"}
    inicial = next((label for label, valor in opcoes.items() if valor == atual), "Cadastro de Produtos")
    escolha = st.radio("Escolha a operação", list(opcoes.keys()), index=list(opcoes.keys()).index(inicial), horizontal=True, key="tipo_operacao_visual")
    st.session_state["tipo_operacao"] = opcoes[escolha]
    st.session_state["tipo_operacao_bling"] = opcoes[escolha]


def _render_deposito() -> None:
    if str(st.session_state.get("tipo_operacao", "cadastro")).lower() != "estoque":
        return
    with st.container(border=True):
        st.markdown("### Dados da operação")
        valor = str(st.session_state.get("deposito_nome", "") or "").strip()
        st.session_state["deposito_nome"] = st.text_input("Nome do depósito", value=valor, key="deposito_nome_input", placeholder="Ex.: Depósito Principal").strip()


def _render_modelo() -> None:
    with st.container(border=True):
        st.markdown("### Modelo do Bling")
        st.caption("Envie primeiro o modelo oficial de cadastro ou estoque.")
        upload = st.file_uploader("Selecionar modelo", type=["csv", "xlsx", "xls"], key="upload_modelo")
        if upload:
            _processar_modelo(upload)


def _render_origem_arquivo() -> None:
    with st.container(border=True):
        st.markdown("### Arquivo do fornecedor")
        upload = st.file_uploader("Selecionar arquivo de origem", type=["csv", "xlsx", "xls", "xml"], key="upload_origem")
        if upload is not None:
            _processar_origem(upload)


def _render_preview_modelo() -> None:
    if st.session_state.get("modo_origem") == "Buscar no site do fornecedor":
        return
    if st.session_state.get("origem_site_preview_modelo_bling") or not _origem_pronta() or not _modelo_pronto():
        return
    st.markdown("---")
    df_preview = render_preview_inteligente(st.session_state.get("df_origem"), st.session_state.get("df_modelo"), titulo="Preview da planilha do fornecedor baseado no modelo Bling anexado")
    if safe_df_estrutura(df_preview):
        st.session_state["df_preview_inteligente"] = df_preview.copy()
        st.session_state["df_preview_fornecedor_modelo_bling"] = df_preview.copy()
        st.session_state["df_precificado"] = df_preview.copy()
        st.session_state["origem_fornecedor_preview_modelo_bling"] = True
        st.session_state.pop("df_final", None)
        st.success("Preview da origem montado nas colunas do modelo Bling.")


def _validar_continuar() -> bool:
    if str(st.session_state.get("tipo_operacao", "cadastro")).lower() == "estoque":
        if not str(st.session_state.get("deposito_nome", "") or "").strip():
            st.error("Informe o nome do depósito para continuar.")
            return False
    return True


def _render_continuar() -> None:
    st.markdown("### Continuar")
    df_origem = st.session_state.get("df_origem")
    df_modelo = st.session_state.get("df_modelo")
    df_preview = st.session_state.get("df_preview_inteligente")
    c1, c2, c3 = st.columns(3)
    c1.metric("Origem bruta", 0 if not isinstance(df_origem, pd.DataFrame) else len(df_origem))
    c2.metric("Modelo", 0 if not isinstance(df_modelo, pd.DataFrame) else len(df_modelo.columns))
    c3.metric("Preview", 0 if not isinstance(df_preview, pd.DataFrame) else len(df_preview))

    if not _modelo_pronto():
        st.info("Envie o modelo Bling válido para liberar a origem dos dados.")
        return
    if not _origem_pronta():
        st.info("Agora carregue a planilha do fornecedor ou faça a busca por site.")
        return
    if not _preview_pronto():
        st.info("Aguarde o sistema montar o preview nas colunas do modelo Bling.")
        return
    if not _validar_continuar():
        return
    if st.button("Continuar ➜", key="btn_continuar_origem", use_container_width=True):
        df_preview = st.session_state.get("df_preview_inteligente").copy()
        st.session_state["df_precificado"] = df_preview
        st.session_state["df_saida"] = df_preview
        st.session_state.pop("df_final", None)
        if set_etapa_segura("precificacao", origem="origem_dados_modular"):
            st.rerun()
        st.error("Não foi possível avançar.")


def render_origem_dados() -> None:
    st.subheader("1. Origem dos dados")
    _render_operacao()
    _render_deposito()
    _render_modelo()
    if not _modelo_pronto():
        st.info("Anexe primeiro o modelo Bling para liberar o próximo passo.")
        st.markdown("---")
        _render_continuar()
        return
    modo = st.radio("Como deseja informar a origem?", ["Arquivo do fornecedor", "Buscar no site do fornecedor"], horizontal=True, key="modo_origem")
    if modo == "Arquivo do fornecedor":
        _render_origem_arquivo()
        _render_preview_modelo()
    else:
        with st.container(border=True):
            st.markdown("### Busca no site do fornecedor")
            render_origem_site_panel()
    st.markdown("---")
    _render_continuar()
