
from __future__ import annotations

import inspect
import io
from pathlib import Path
import xml.etree.ElementTree as ET

import pandas as pd
import streamlit as st

try:
    from bling_app_zero.core.site_agent import buscar_produtos_site_com_gpt
except Exception:
    buscar_produtos_site_com_gpt = None

from bling_app_zero.ui.app_helpers import (
    ir_para_etapa,
    log_debug,
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


def _resetar_flag_avanco_origem() -> None:
    st.session_state["origem_pronta_para_avancar"] = False


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

    _resetar_flag_avanco_origem()


def _limpar_estado_modelo() -> None:
    for chave in [
        "df_modelo",
        "modelo_upload_nome",
        "modelo_upload_bytes",
        "modelo_upload_tipo",
        "modelo_upload_ext",
    ]:
        st.session_state.pop(chave, None)

    _resetar_flag_avanco_origem()


def _guardar_upload_bruto(chave_prefixo: str, upload, tipo: str) -> None:
    st.session_state[f"{chave_prefixo}_nome"] = str(upload.name)
    st.session_state[f"{chave_prefixo}_bytes"] = upload.getvalue()
    st.session_state[f"{chave_prefixo}_tipo"] = tipo
    st.session_state[f"{chave_prefixo}_ext"] = _extensao(upload)
    _resetar_flag_avanco_origem()


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

    novo_tipo = opcoes[escolha]
    tipo_anterior = st.session_state.get("tipo_operacao")

    if tipo_anterior != novo_tipo:
        _resetar_flag_avanco_origem()

    st.session_state["tipo_operacao"] = novo_tipo
    st.session_state["tipo_operacao_bling"] = novo_tipo


def _render_origem_arquivo() -> None:
    st.markdown("### Arquivo do fornecedor")

    upload_origem = st.file_uploader(
        "Toque para selecionar o arquivo do fornecedor",
        key="upload_origem",
    )

    if upload_origem is not None:
        _processar_upload_origem(upload_origem)


def _carimbar_execucao_site(total_produtos: int, url_site: str) -> None:
    from datetime import datetime

    st.session_state["site_auto_ultima_execucao"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state["site_auto_ultima_url"] = url_site
    st.session_state["site_auto_ultimo_total_produtos"] = int(total_produtos)
    st.session_state["site_auto_status"] = (
        "ativo" if st.session_state.get("site_auto_loop_ativo", False) else "inativo"
    )


def _chamar_busca_site_compativel(url_site: str, intervalo: int):
    if buscar_produtos_site_com_gpt is None:
        raise RuntimeError("Módulo de busca por site indisponível.")

    kwargs = {
        "base_url": url_site,
        "diagnostico": True,
    }

    try:
        assinatura = inspect.signature(buscar_produtos_site_com_gpt)
        parametros = assinatura.parameters

        if "termo" in parametros:
            kwargs["termo"] = ""
        if "limite_links" in parametros:
            kwargs["limite_links"] = None
        if "modo_loop" in parametros:
            kwargs["modo_loop"] = False
        if "intervalo_segundos" in parametros:
            kwargs["intervalo_segundos"] = intervalo
    except Exception:
        pass

    return buscar_produtos_site_com_gpt(**kwargs)


def _executar_busca_site(url_site: str) -> None:
    if not url_site:
        st.error("Informe a URL base do fornecedor.")
        return

    if not buscar_produtos_site_com_gpt:
        st.error("Módulo de busca por site indisponível.")
        return

    intervalo = int(st.session_state.get("site_auto_intervalo_segundos", 60) or 60)
    st.session_state["site_auto_status"] = "executando"
    log_debug(f"Disparo manual do monitoramento do site | url={url_site} | intervalo={intervalo}s", nivel="INFO")

    try:
        df_site = _chamar_busca_site_compativel(url_site, intervalo)

        if not isinstance(df_site, pd.DataFrame) or df_site.empty:
            st.warning("Nenhum produto encontrado.")
            st.session_state["site_auto_status"] = "erro"
            _carimbar_execucao_site(0, url_site)
            return

        st.session_state["df_origem"] = df_site
        st.session_state["origem_upload_tipo"] = "site_gpt"
        st.session_state["origem_upload_nome"] = f"varredura_site_{url_site}"
        st.session_state["origem_upload_ext"] = "site_gpt"

        total = int(len(df_site))
        _carimbar_execucao_site(total, url_site)

        st.success(f"{total} produtos encontrados")
        _preview_dataframe(df_site, "Preview do site")
        log_debug(f"Monitoramento manual executado com {total} produto(s).", nivel="INFO")

    except Exception as exc:
        st.session_state["site_auto_status"] = "erro"
        st.error(f"Falha ao executar busca no site: {exc}")
        log_debug(f"Falha ao executar monitoramento do site: {exc}", nivel="ERRO")


def _render_origem_site() -> None:
    st.markdown("### Busca no site do fornecedor")

    url_site = st.text_input(
        "URL base do fornecedor",
        key="site_fornecedor_url",
    ).strip()

    if not url_site:
        st.info("Informe a URL para habilitar a busca e a automação do site.")
        return

    col1, col2 = st.columns(2)

    with col1:
        if st.button("✨ Varrer site inteiro com GPT", use_container_width=True, key="btn_varrer_site_gpt"):
            _executar_busca_site(url_site)
            st.rerun()

    with col2:
        if st.button("🟢 Ativar monitoramento", use_container_width=True, key="btn_ativar_monitoramento_site"):
            st.session_state["site_auto_loop_ativo"] = True
            st.session_state["site_auto_status"] = "ativo"
            st.success("Monitoramento automático ativado.")
            log_debug("Loop automático do site ativado.", nivel="INFO")
            st.rerun()

    origem_tipo = str(st.session_state.get("origem_upload_tipo", "") or "").strip().lower()
    origem_nome = str(st.session_state.get("origem_upload_nome", "") or "").strip().lower()
    site_ativo = "site_gpt" in origem_tipo or "varredura_site_" in origem_nome

    if site_ativo:
        st.markdown("---")
        with st.expander("⚙️ Automação do site", expanded=True):
            status = str(st.session_state.get("site_auto_status", "inativo") or "inativo")
            ultima_execucao = str(st.session_state.get("site_auto_ultima_execucao", "") or "").strip()
            ultimo_total = int(st.session_state.get("site_auto_ultimo_total_produtos", 0) or 0)

            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Loop automático", "Ativo" if st.session_state.get("site_auto_loop_ativo", False) else "Inativo")
            with c2:
                st.metric("Status", status.title())
            with c3:
                st.metric("Último total", ultimo_total)

            st.number_input(
                "Intervalo do monitoramento (segundos)",
                min_value=5,
                step=5,
                key="site_auto_intervalo_segundos",
                help="Define o intervalo base do monitoramento do site.",
            )

            st.write(f"**URL monitorada:** {url_site}")
            if ultima_execucao:
                st.write(f"**Última execução:** {ultima_execucao}")

            b1, b2, b3 = st.columns(3)

            with b1:
                if st.button("▶️ Executar agora", use_container_width=True, key="btn_site_auto_executar_agora_origem"):
                    _executar_busca_site(url_site)
                    st.rerun()

            with b2:
                if st.button("🟢 Ativar loop", use_container_width=True, key="btn_site_auto_ativar_origem"):
                    st.session_state["site_auto_loop_ativo"] = True
                    st.session_state["site_auto_status"] = "ativo"
                    st.success("Loop automático marcado como ativo.")
                    log_debug("Loop automático do site ativado.", nivel="INFO")
                    st.rerun()

            with b3:
                if st.button("⏹️ Parar loop", use_container_width=True, key="btn_site_auto_parar_origem"):
                    st.session_state["site_auto_loop_ativo"] = False
                    st.session_state["site_auto_status"] = "inativo"
                    st.info("Loop automático marcado como inativo.")
                    log_debug("Loop automático do site desativado.", nivel="INFO")
                    st.rerun()


def _render_modelo() -> None:
    upload_modelo = st.file_uploader("Enviar modelo", key="upload_modelo")

    if upload_modelo:
        _processar_upload_modelo(upload_modelo)


def _render_continuar() -> None:
    if _origem_pronta() and _modelo_pronto():
        if st.button("Continuar ➜", key="btn_continuar_origem"):
            ir_para_etapa("precificacao")


def render_origem_dados() -> None:
    st.subheader("1. Origem dos dados")

    _render_operacao()

    modo = st.radio(
        "Origem",
        ["Arquivo do fornecedor", "Buscar no site do fornecedor"],
        horizontal=True,
        key="modo_origem",
    )

    if modo == "Arquivo do fornecedor":
        _render_origem_arquivo()
    else:
        _render_origem_site()

    _render_modelo()
    _render_continuar()

