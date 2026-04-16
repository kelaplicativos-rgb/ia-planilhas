
from __future__ import annotations

import io
from pathlib import Path
import xml.etree.ElementTree as ET

import pandas as pd
import streamlit as st

from bling_app_zero.core.site_agent import buscar_produtos_site_com_gpt
from bling_app_zero.ui.app_helpers import (
    ir_para_etapa,
    safe_df_dados,
    safe_df_estrutura,
)

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


def _limpar_estado_origem() -> None:
    for chave in [
        "df_origem",
        "origem_upload_nome",
        "origem_upload_bytes",
        "origem_upload_tipo",
        "origem_upload_ext",
        "site_busca_diagnostico_df",
        "site_busca_diagnostico_total_descobertos",
        "site_busca_diagnostico_total_validos",
        "site_busca_diagnostico_total_rejeitados",
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


def _guardar_upload_bruto(chave_prefixo: str, upload, tipo: str) -> None:
    st.session_state[f"{chave_prefixo}_nome"] = str(upload.name)
    st.session_state[f"{chave_prefixo}_bytes"] = upload.getvalue()
    st.session_state[f"{chave_prefixo}_tipo"] = tipo
    st.session_state[f"{chave_prefixo}_ext"] = _extensao(upload)


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
    st.markdown(f"**{titulo}**")

    if not isinstance(df, pd.DataFrame):
        st.info("Arquivo sem estrutura tabular.")
        return

    if len(df.columns) == 0:
        st.error("Nenhuma coluna encontrada no arquivo.")
        return

    if df.empty:
        st.success("Arquivo carregado corretamente, mas sem linhas de dados.")
        preview = pd.DataFrame(columns=df.columns)
        st.dataframe(preview, use_container_width=True)
        return

    st.dataframe(df.head(10), use_container_width=True)


def _processar_upload_origem(upload) -> None:
    if upload is None:
        return

    _limpar_estado_origem()
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
        return

    _limpar_estado_modelo()
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

    st.session_state["tipo_operacao"] = opcoes[escolha]
    st.session_state["tipo_operacao_bling"] = opcoes[escolha]


def _render_origem_arquivo() -> None:
    st.markdown("### Arquivo do fornecedor")
    st.caption("Aceita CSV, XLSX, XLS, XML e PDF.")

    upload_origem = st.file_uploader(
        "Toque para selecionar o arquivo do fornecedor",
        type=["csv", "xlsx", "xls", "xml", "pdf"],
        key="upload_origem",
        help="Aceita CSV, XLSX, XLS, XML e PDF.",
    )

    if upload_origem is not None:
        _processar_upload_origem(upload_origem)


def _registrar_origem_site(df_site: pd.DataFrame, url_site: str) -> None:
    st.session_state["df_origem"] = df_site
    st.session_state["origem_upload_nome"] = f"varredura_site_{url_site}"
    st.session_state["origem_upload_tipo"] = "site_gpt"
    st.session_state["origem_upload_ext"] = "site_gpt"


def _render_diagnostico_site() -> None:
    df_diag = st.session_state.get("site_busca_diagnostico_df")

    if not isinstance(df_diag, pd.DataFrame) or df_diag.empty:
        return

    total_descobertos = int(st.session_state.get("site_busca_diagnostico_total_descobertos", 0) or 0)
    total_validos = int(st.session_state.get("site_busca_diagnostico_total_validos", 0) or 0)
    total_rejeitados = int(st.session_state.get("site_busca_diagnostico_total_rejeitados", 0) or 0)

    st.markdown("### Diagnóstico da busca por site")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Descobertos", total_descobertos)
    with c2:
        st.metric("Válidos", total_validos)
    with c3:
        st.metric("Rejeitados/erros", total_rejeitados)

    st.dataframe(df_diag, use_container_width=True)

    csv_diag = df_diag.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "Baixar diagnóstico CSV",
        data=csv_diag,
        file_name="diagnostico_busca_site.csv",
        mime="text/csv",
        use_container_width=True,
    )


def _render_origem_site() -> None:
    st.markdown("### Busca no site do fornecedor")

    url_site = st.text_input(
        "URL base do fornecedor",
        value=st.session_state.get("site_fornecedor_url", ""),
        placeholder="https://fornecedor.com.br",
    )

    modo_diagnostico = st.checkbox(
        "Ativar modo diagnóstico da busca",
        value=bool(st.session_state.get("site_fornecedor_diagnostico", False)),
        key="site_fornecedor_diagnostico",
        help="Salva detalhes da heurística, do GPT e do resultado final para auditoria.",
    )

    st.caption(
        "A varredura tenta buscar produtos em todo o site, sem exigir termo e sem campo de limite na tela."
    )

    st.session_state["site_fornecedor_url"] = url_site
    st.session_state["site_fornecedor_diagnostico"] = modo_diagnostico

    if st.button(
        "✨ Varrer site inteiro com GPT",
        use_container_width=True,
        key="btn_buscar_site_gpt",
    ):
        _limpar_estado_origem()

        if not str(url_site).strip():
            st.error("Informe a URL base do fornecedor.")
            return

        df_site = buscar_produtos_site_com_gpt(
            base_url=url_site,
            diagnostico=modo_diagnostico,
        )

        if not safe_df_dados(df_site):
            st.error("Nenhum produto foi encontrado na varredura do site.")
            _render_diagnostico_site()
            return

        _registrar_origem_site(df_site, url_site)
        st.success(f"Varredura concluída com {len(df_site)} produto(s).")
        _preview_dataframe(df_site, "Preview da varredura do site")
        _render_diagnostico_site()

    else:
        _render_diagnostico_site()


def _render_modelo() -> None:
    st.markdown("### Modelo")

    upload_modelo = st.file_uploader(
        "Enviar modelo",
        type=["csv", "xlsx", "xls"],
        key="upload_modelo",
        help="Aceita CSV, XLSX e XLS.",
    )

    if upload_modelo is not None:
        _processar_upload_modelo(upload_modelo)


def _render_resumo() -> None:
    st.markdown("### Resumo")
    st.write(f"**Origem anexada:** {st.session_state.get('origem_upload_nome', 'não enviada')}")
    st.write(f"**Modelo anexado:** {st.session_state.get('modelo_upload_nome', 'não enviado')}")

    if safe_df_dados(st.session_state.get("df_origem")):
        st.write(f"**Linhas origem:** {len(st.session_state['df_origem'])}")
        st.write(f"**Colunas origem:** {len(st.session_state['df_origem'].columns)}")

    if safe_df_estrutura(st.session_state.get("df_modelo")):
        st.write(f"**Linhas modelo:** {len(st.session_state['df_modelo'])}")
        st.write(f"**Colunas modelo:** {len(st.session_state['df_modelo'].columns)}")


def render_origem_dados() -> None:
    st.subheader("1. Origem dos dados")

    _render_operacao()

    if st.session_state.get("tipo_operacao") == "estoque":
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
        _render_origem_arquivo()
    else:
        _render_origem_site()

    _render_modelo()
    _render_resumo()

    if _origem_pronta() and _modelo_pronto():
        if st.button("Continuar ➜", use_container_width=True):
            ir_para_etapa("precificacao")
    else:
        st.info("Envie/gere a origem e envie o modelo para continuar.")

