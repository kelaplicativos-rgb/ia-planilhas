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


# ============================================================
# HELPERS BASE
# ============================================================

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


def _resetar_estado_site_ui() -> None:
    for chave in [
        "site_busca_em_execucao",
        "site_busca_ultima_url",
        "site_busca_ultimo_total",
        "site_busca_ultimo_status",
        "site_busca_ultima_execucao",
        "site_busca_diagnostico_df",
        "site_busca_diagnostico_total_descobertos",
        "site_busca_diagnostico_total_validos",
        "site_busca_diagnostico_total_rejeitados",
        "site_busca_login_status",
        "site_busca_resumo_texto",
        "site_busca_fonte_descoberta",
        "site_busca_modo_sitemap_primeiro",
    ]:
        st.session_state.pop(chave, None)


def _limpar_estado_origem() -> None:
    for chave in [
        "df_origem",
        "origem_upload_nome",
        "origem_upload_bytes",
        "origem_upload_tipo",
        "origem_upload_ext",
    ]:
        st.session_state.pop(chave, None)

    _resetar_estado_site_ui()
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
        _resetar_estado_site_ui()

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
        _resetar_estado_site_ui()

        st.success("XML convertido com sucesso.")
        _preview_dataframe(df, "Preview do XML")
        return

    _guardar_upload_bruto("origem_upload", upload, "documento")
    _resetar_estado_site_ui()
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


def _tem_resultado_site() -> bool:
    origem_tipo = str(st.session_state.get("origem_upload_tipo", "") or "").strip().lower()
    return origem_tipo == "site_gpt" and safe_df_dados(st.session_state.get("df_origem"))


def _fonte_descoberta_label(valor: str) -> str:
    valor_n = str(valor or "").strip().lower()

    mapa = {
        "sitemap": "Sitemap",
        "crawler_links": "Varredura de links",
        "http_direto": "Leitura direta do HTML",
        "produto_direto": "URL de produto",
        "": "-",
    }

    return mapa.get(valor_n, valor_n.replace("_", " ").title() or "-")


def _resumo_origem_atual() -> None:
    df_origem = st.session_state.get("df_origem")
    df_modelo = st.session_state.get("df_modelo")
    fonte_descoberta = _fonte_descoberta_label(st.session_state.get("site_busca_fonte_descoberta", ""))

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Origem", 0 if not isinstance(df_origem, pd.DataFrame) else len(df_origem))
    with col2:
        st.metric("Colunas origem", 0 if not isinstance(df_origem, pd.DataFrame) else len(df_origem.columns))
    with col3:
        st.metric("Colunas modelo", 0 if not isinstance(df_modelo, pd.DataFrame) else len(df_modelo.columns))
    with col4:
        st.metric("Fonte descoberta", fonte_descoberta)


# ============================================================
# OPERAÇÃO
# ============================================================

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


# ============================================================
# ORIGEM POR ARQUIVO
# ============================================================

def _render_origem_arquivo() -> None:
    st.markdown("### Arquivo do fornecedor")
    st.caption("Envie a planilha ou XML do fornecedor para usar como origem.")

    upload_origem = st.file_uploader(
        "Selecionar arquivo de origem",
        key="upload_origem",
    )

    if upload_origem is not None:
        _processar_upload_origem(upload_origem)


# ============================================================
# BUSCA POR SITE
# ============================================================

def _carimbar_execucao_site(total_produtos: int, url_site: str, status: str) -> None:
    from datetime import datetime

    st.session_state["site_busca_ultima_url"] = url_site
    st.session_state["site_busca_ultimo_total"] = int(total_produtos)
    st.session_state["site_busca_ultimo_status"] = status
    st.session_state["site_busca_ultima_execucao"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _chamar_busca_site_compativel(url_site: str):
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
    except Exception:
        pass

    return buscar_produtos_site_com_gpt(**kwargs)


def _resumo_status_site_texto() -> str:
    status = str(st.session_state.get("site_busca_ultimo_status", "") or "").strip().lower()
    total = int(st.session_state.get("site_busca_ultimo_total", 0) or 0)
    fonte = _fonte_descoberta_label(st.session_state.get("site_busca_fonte_descoberta", ""))

    if status == "sucesso":
        if fonte != "-":
            return f"Busca concluída com {total} produto(s) encontrado(s) via {fonte.lower()}."
        return f"Busca concluída com {total} produto(s) encontrado(s)."
    if status == "vazio":
        return "A busca terminou sem produtos encontrados."
    if status == "erro":
        return "A busca terminou com erro."
    if status == "executando":
        return "Busca em andamento..."
    return "Nenhuma busca executada ainda."


def _executar_busca_site(url_site: str) -> None:
    url_site = str(url_site or "").strip()

    if not url_site:
        st.error("Informe a URL base do fornecedor.")
        return

    if not buscar_produtos_site_com_gpt:
        st.error("Módulo de busca por site indisponível.")
        return

    st.session_state["site_busca_em_execucao"] = True
    st.session_state["site_busca_ultimo_status"] = "executando"
    st.session_state["site_busca_resumo_texto"] = "Busca em andamento..."
    st.session_state["site_busca_fonte_descoberta"] = ""

    log_debug(f"Iniciando busca simplificada por site | url={url_site}", nivel="INFO")

    try:
        df_site = _chamar_busca_site_compativel(url_site)

        if not isinstance(df_site, pd.DataFrame) or df_site.empty:
            _carimbar_execucao_site(0, url_site, "vazio")
            st.session_state["site_busca_em_execucao"] = False
            st.session_state["site_busca_resumo_texto"] = "A busca terminou sem produtos encontrados."
            st.warning("Nenhum produto encontrado na busca por site.")
            return

        st.session_state["df_origem"] = df_site
        st.session_state["origem_upload_tipo"] = "site_gpt"
        st.session_state["origem_upload_nome"] = f"site_{url_site}"
        st.session_state["origem_upload_ext"] = "site_gpt"

        total = int(len(df_site))
        _carimbar_execucao_site(total, url_site, "sucesso")
        st.session_state["site_busca_em_execucao"] = False
        st.session_state["site_busca_resumo_texto"] = _resumo_status_site_texto()

        fonte_descoberta = _fonte_descoberta_label(st.session_state.get("site_busca_fonte_descoberta", ""))
        if fonte_descoberta != "-":
            st.success(f"{total} produto(s) encontrados no site via {fonte_descoberta.lower()}.")
        else:
            st.success(f"{total} produto(s) encontrados no site.")

        _preview_dataframe(df_site, "Preview da busca por site")
        log_debug(f"Busca por site finalizada com {total} produto(s).", nivel="INFO")

    except Exception as exc:
        st.session_state["site_busca_em_execucao"] = False
        _carimbar_execucao_site(0, url_site, "erro")
        st.session_state["site_busca_resumo_texto"] = f"Falha na busca: {exc}"
        st.error(f"Falha ao executar busca no site: {exc}")
        log_debug(f"Falha ao executar busca por site: {exc}", nivel="ERRO")


def _render_resumo_busca_site() -> None:
    ultima_url = str(st.session_state.get("site_busca_ultima_url", "") or "").strip()
    ultimo_total = int(st.session_state.get("site_busca_ultimo_total", 0) or 0)
    ultimo_status = str(st.session_state.get("site_busca_ultimo_status", "inativo") or "inativo")
    ultima_execucao = str(st.session_state.get("site_busca_ultima_execucao", "") or "").strip()
    resumo_texto = str(st.session_state.get("site_busca_resumo_texto", "") or "").strip() or _resumo_status_site_texto()
    fonte_descoberta = _fonte_descoberta_label(st.session_state.get("site_busca_fonte_descoberta", ""))

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Status", ultimo_status.title())
    with c2:
        st.metric("Produtos", ultimo_total)
    with c3:
        st.metric("Origem site", "Sim" if _tem_resultado_site() else "Não")
    with c4:
        st.metric("Fonte descoberta", fonte_descoberta)

    if resumo_texto:
        st.caption(resumo_texto)

    if ultima_url:
        st.write(f"**Última URL:** {ultima_url}")
    if ultima_execucao:
        st.write(f"**Última execução:** {ultima_execucao}")


def _render_diagnostico_site() -> None:
    df_diag = st.session_state.get("site_busca_diagnostico_df")
    total_descobertos = int(st.session_state.get("site_busca_diagnostico_total_descobertos", 0) or 0)
    total_validos = int(st.session_state.get("site_busca_diagnostico_total_validos", 0) or 0)
    total_rejeitados = int(st.session_state.get("site_busca_diagnostico_total_rejeitados", 0) or 0)
    login_status = st.session_state.get("site_busca_login_status", {})
    fonte_descoberta = _fonte_descoberta_label(st.session_state.get("site_busca_fonte_descoberta", ""))

    if not isinstance(df_diag, pd.DataFrame) and not isinstance(login_status, dict):
        return

    with st.expander("Diagnóstico da busca", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Descobertos", total_descobertos)
        with c2:
            st.metric("Válidos", total_validos)
        with c3:
            st.metric("Rejeitados", total_rejeitados)
        with c4:
            st.metric("Fonte", fonte_descoberta)

        if isinstance(login_status, dict) and login_status:
            mensagem = str(login_status.get("mensagem", "") or "").strip()
            status = str(login_status.get("status", "") or "").strip()
            if status:
                st.write(f"**Status de acesso:** {status}")
            if mensagem:
                st.caption(mensagem)

        if isinstance(df_diag, pd.DataFrame) and not df_diag.empty:
            st.dataframe(df_diag.head(100), use_container_width=True)
        elif isinstance(df_diag, pd.DataFrame):
            st.info("Sem linhas de diagnóstico disponíveis.")


def _render_etapas_busca_site(url_site: str) -> None:
    st.markdown("#### Etapa 1 — Informar a URL")
    if not url_site:
        st.info("Cole a URL do fornecedor para habilitar a busca.")
        return

    st.success("URL preenchida.")

    st.markdown("#### Etapa 2 — Executar a busca")
    executando = bool(st.session_state.get("site_busca_em_execucao", False))

    col1, col2 = st.columns([2, 1])

    with col1:
        if st.button(
            "Buscar produtos do site",
            use_container_width=True,
            key="btn_buscar_site_simplificado",
            disabled=executando,
        ):
            _executar_busca_site(url_site)
            st.rerun()

    with col2:
        if st.button(
            "Limpar busca",
            use_container_width=True,
            key="btn_limpar_busca_site",
        ):
            _limpar_estado_origem()
            st.info("Busca por site limpa.")
            st.rerun()

    if executando:
        st.info("A busca está em andamento...")

    st.markdown("---")
    _render_resumo_busca_site()

    st.markdown("#### Etapa 3 — Conferir resultado")
    if _tem_resultado_site():
        _preview_dataframe(st.session_state.get("df_origem"), "Preview da busca por site")
    else:
        st.info("Depois da busca, o preview dos produtos encontrados aparecerá aqui.")

    _render_diagnostico_site()


def _render_origem_site() -> None:
    st.markdown("### Busca no site do fornecedor")
    st.caption(
        "Fluxo simplificado: informe a URL, execute a busca, confira o preview e siga para a próxima etapa."
    )

    if "site_fornecedor_url" not in st.session_state:
        st.session_state["site_fornecedor_url"] = ""

    url_site = st.text_input(
        "URL do fornecedor ou categoria",
        key="site_fornecedor_url",
        placeholder="https://www.fornecedor.com.br/categoria",
    ).strip()

    with st.container(border=True):
        st.checkbox(
            "Priorizar sitemap quando disponível",
            key="site_busca_modo_sitemap_primeiro",
            value=True,
            disabled=True,
            help="Atualmente a busca já usa sitemap primeiro automaticamente quando o site expõe esse recurso.",
        )
        _render_etapas_busca_site(url_site)


# ============================================================
# MODELO
# ============================================================

def _render_modelo() -> None:
    st.markdown("### Modelo do Bling")
    st.caption("Envie o modelo que será usado como estrutura de saída.")

    upload_modelo = st.file_uploader(
        "Selecionar modelo",
        key="upload_modelo",
    )

    if upload_modelo:
        _processar_upload_modelo(upload_modelo)


# ============================================================
# CONTINUAR
# ============================================================

def _render_continuar() -> None:
    st.markdown("---")
    st.markdown("### Pronto para seguir?")
    _resumo_origem_atual()

    origem_ok = _origem_pronta()
    modelo_ok = _modelo_pronto()

    if not origem_ok:
        st.info("Carregue uma origem válida para continuar.")
        return

    if not modelo_ok:
        st.info("Envie um modelo válido para continuar.")
        return

    if st.button("Continuar ➜", key="btn_continuar_origem", use_container_width=True):
        ir_para_etapa("precificacao")


# ============================================================
# RENDER PRINCIPAL
# ============================================================

def render_origem_dados() -> None:
    st.subheader("1. Origem dos dados")

    _render_operacao()

    modo = st.radio(
        "Como deseja informar a origem?",
        ["Arquivo do fornecedor", "Buscar no site do fornecedor"],
        horizontal=True,
        key="modo_origem",
    )

    if modo == "Arquivo do fornecedor":
        _render_origem_arquivo()
    else:
        _render_origem_site()

    st.markdown("---")
    _render_modelo()
    _render_continuar()
