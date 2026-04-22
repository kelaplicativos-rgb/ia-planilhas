
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

try:
    from bling_app_zero.core.site_auth import (
        apply_inspection_to_state,
        get_auth_headers_and_cookies,
        get_profile_for_url,
        inspect_site_auth,
    )
except Exception:
    apply_inspection_to_state = None
    get_auth_headers_and_cookies = None
    get_profile_for_url = None
    inspect_site_auth = None

try:
    from bling_app_zero.core.site_login_assisted import (
        iniciar_fluxo_login_assistido,
        resumo_fluxo_login_assistido,
        salvar_sessao_assistida,
    )
except Exception:
    iniciar_fluxo_login_assistido = None
    resumo_fluxo_login_assistido = None
    salvar_sessao_assistida = None

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


def _safe_auth_state() -> dict:
    valor = st.session_state.get("site_auth_state")
    return valor if isinstance(valor, dict) else {}


def _safe_profile(url_site: str) -> dict:
    if get_profile_for_url is None:
        return {}

    try:
        profile = get_profile_for_url(url_site)
        if profile is None:
            return {}
        if hasattr(profile, "__dict__"):
            return dict(profile.__dict__)
        if isinstance(profile, dict):
            return profile
    except Exception:
        return {}
    return {}


def _profile_slug(url_site: str) -> str:
    profile = _safe_profile(url_site)
    return str(profile.get("slug", "") or "").strip().lower()


def _fornecedor_nome(url_site: str) -> str:
    profile = _safe_profile(url_site)
    nome = str(profile.get("nome", "") or "").strip()
    if nome:
        return nome
    return "Fornecedor"


def _profile_requires_login(url_site: str) -> bool:
    profile = _safe_profile(url_site)
    return bool(profile.get("login_required", False))


def _profile_requires_assisted_login(url_site: str) -> bool:
    profile = _safe_profile(url_site)
    return bool(profile.get("requires_assisted_login", False))


def _profile_requires_whatsapp_code(url_site: str) -> bool:
    profile = _safe_profile(url_site)
    return bool(profile.get("requires_whatsapp_code", False))


def _profile_captcha_expected(url_site: str) -> bool:
    profile = _safe_profile(url_site)
    return bool(profile.get("captcha_expected", False))


def _profile_products_url(url_site: str) -> str:
    profile = _safe_profile(url_site)
    return str(profile.get("products_url", "") or "").strip()


def _profile_login_url(url_site: str) -> str:
    profile = _safe_profile(url_site)
    return str(profile.get("login_url", "") or "").strip()


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
        "site_auth_state",
        "site_auth_last_result",
        "site_auth_inspecionado_url",
        "site_login_assistido_confirmado",
        "site_login_assistido_observacao",
        "site_login_assistido_inicio",
        "site_login_assistido_resumo",
        "site_login_assistido_cookies_json",
        "site_login_assistido_headers_json",
        "site_login_assistido_status_texto",
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
    with st.expander(titulo, expanded=False):
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
    operacao = str(st.session_state.get("tipo_operacao", "cadastro") or "cadastro").strip().lower()
    deposito_nome = str(st.session_state.get("deposito_nome", "") or "").strip()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Origem", 0 if not isinstance(df_origem, pd.DataFrame) else len(df_origem))
    with col2:
        st.metric("Modelo", 0 if not isinstance(df_modelo, pd.DataFrame) else len(df_modelo.columns))
    with col3:
        if operacao == "estoque":
            st.metric("Depósito", deposito_nome or "-")
        else:
            st.metric("Fonte", fonte_descoberta)


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
            help="Esse valor será levado automaticamente para a coluna de depósito no mapeamento e no resultado final.",
        ).strip()

        st.session_state["deposito_nome"] = novo_valor


def _render_origem_arquivo() -> None:
    with st.container(border=True):
        st.markdown("### Arquivo do fornecedor")

        upload_origem = st.file_uploader(
            "Selecionar arquivo de origem",
            key="upload_origem",
        )

        if upload_origem is not None:
            _processar_upload_origem(upload_origem)


def _carimbar_execucao_site(total_produtos: int, url_site: str, status: str) -> None:
    from datetime import datetime

    st.session_state["site_busca_ultima_url"] = url_site
    st.session_state["site_busca_ultimo_total"] = int(total_produtos)
    st.session_state["site_busca_ultimo_status"] = status
    st.session_state["site_busca_ultima_execucao"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _inspecionar_site(url_site: str) -> dict:
    if inspect_site_auth is None:
        return {}

    try:
        resultado = inspect_site_auth(url_site)
        if apply_inspection_to_state is not None:
            apply_inspection_to_state(resultado)
        if hasattr(resultado, "__dict__"):
            data = dict(resultado.__dict__)
        elif isinstance(resultado, dict):
            data = resultado
        else:
            data = {}
        st.session_state["site_auth_last_result"] = data
        st.session_state["site_auth_state"] = {
            **_safe_auth_state(),
            "status": str(data.get("status", "") or ""),
            "provider_slug": str(data.get("provider_slug", "") or ""),
            "provider_name": str(data.get("provider_name", "") or ""),
            "requires_login": bool(data.get("requires_login", False)),
            "captcha_detected": bool(data.get("captcha_detected", False)),
            "login_url": str(data.get("login_url", "") or ""),
            "products_url": str(data.get("products_url", "") or ""),
            "auth_mode": str(data.get("auth_mode", "public") or "public"),
            "session_ready": bool(data.get("session_ready", False)),
            "last_message": str(data.get("message", "") or ""),
            "detected_whatsapp_code": bool(data.get("detected_whatsapp_code", False)),
            "requires_whatsapp_code": bool((data.get("profile") or {}).get("requires_whatsapp_code", False)),
            "source_kind": str((data.get("profile") or {}).get("source_kind", "") or ""),
        }
        st.session_state["site_auth_inspecionado_url"] = url_site
        return data
    except Exception as exc:
        log_debug(f"Falha ao inspecionar site: {exc}", nivel="ERRO")
        return {}


def _atualizar_resumo_login_assistido(url_site: str) -> dict:
    if resumo_fluxo_login_assistido is None:
        return {}

    try:
        resumo = resumo_fluxo_login_assistido(url_site)
        if isinstance(resumo, dict):
            st.session_state["site_login_assistido_resumo"] = resumo
            auth_state = _safe_auth_state()
            auth_state["session_ready"] = bool(resumo.get("session_ready", auth_state.get("session_ready", False)))
            auth_state["last_message"] = str(resumo.get("mensagem", auth_state.get("last_message", "")) or "")
            st.session_state["site_auth_state"] = auth_state
            return resumo
    except Exception as exc:
        log_debug(f"Falha ao atualizar resumo do login assistido: {exc}", nivel="ERRO")

    return {}


def _iniciar_login_assistido_real(url_site: str) -> dict:
    if iniciar_fluxo_login_assistido is None:
        return {}

    try:
        resultado = iniciar_fluxo_login_assistido(url_site)
        if isinstance(resultado, dict):
            st.session_state["site_login_assistido_inicio"] = resultado
            st.session_state["site_login_assistido_status_texto"] = str(resultado.get("mensagem", "") or "")
            return resultado
    except Exception as exc:
        log_debug(f"Falha ao iniciar login assistido real: {exc}", nivel="ERRO")

    return {}


def _parse_json_texto(texto: str, campo: str):
    valor = str(texto or "").strip()
    if not valor:
        if campo == "cookies":
            return []
        return {}

    try:
        data = __import__("json").loads(valor)
    except Exception as exc:
        raise ValueError(f"JSON inválido em {campo}: {exc}") from exc

    if campo == "cookies" and not isinstance(data, list):
        raise ValueError("O campo cookies precisa ser uma lista JSON.")
    if campo == "headers" and not isinstance(data, dict):
        raise ValueError("O campo headers precisa ser um objeto JSON.")

    return data


def _salvar_sessao_assistida_real(url_site: str) -> dict:
    if salvar_sessao_assistida is None:
        return {}

    cookies_json = str(st.session_state.get("site_login_assistido_cookies_json", "") or "").strip()
    headers_json = str(st.session_state.get("site_login_assistido_headers_json", "") or "").strip()
    observacao = str(st.session_state.get("site_login_assistido_observacao", "") or "").strip()

    cookies = _parse_json_texto(cookies_json, "cookies")
    headers = _parse_json_texto(headers_json, "headers")

    resultado = salvar_sessao_assistida(
        url=url_site,
        cookies=cookies,
        headers=headers,
        observacao=observacao,
    )

    if isinstance(resultado, dict):
        st.session_state["site_login_assistido_resumo"] = resultado
        auth_state = _safe_auth_state()
        auth_state["session_ready"] = bool((resultado.get("auth_context") or {}).get("session_ready", False))
        auth_state["last_message"] = str(resultado.get("mensagem", "") or auth_state.get("last_message", ""))
        st.session_state["site_auth_state"] = auth_state
        return resultado

    return {}


def _auth_context_para_busca(url_site: str) -> dict | None:
    if get_auth_headers_and_cookies is None:
        return None

    try:
        contexto = get_auth_headers_and_cookies()
        if not isinstance(contexto, dict):
            return None

        provider_slug = str(contexto.get("provider_slug", "") or "").strip()
        products_url = str(contexto.get("products_url", "") or "").strip()
        login_url = str(contexto.get("login_url", "") or "").strip()

        if not provider_slug:
            provider_slug = _profile_slug(url_site)

        contexto["fornecedor_slug"] = provider_slug
        contexto["products_url"] = products_url or _profile_products_url(url_site) or url_site
        contexto["login_url"] = login_url or _profile_login_url(url_site)
        contexto["manual_mode"] = bool(st.session_state.get("site_login_assistido_confirmado", False))
        return contexto
    except Exception as exc:
        log_debug(f"Falha ao montar auth_context para busca: {exc}", nivel="ERRO")
        return None


def _chamar_busca_site_compativel(url_site: str):
    if buscar_produtos_site_com_gpt is None:
        raise RuntimeError("Módulo de busca por site indisponível.")

    kwargs = {
        "base_url": url_site,
        "diagnostico": True,
    }

    auth_context = _auth_context_para_busca(url_site)
    if auth_context:
        kwargs["auth_context"] = auth_context

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
    ultimo_total = int(st.session_state.get("site_busca_ultimo_total", 0) or 0)
    ultimo_status = str(st.session_state.get("site_busca_ultimo_status", "inativo") or "inativo")
    resumo_texto = str(st.session_state.get("site_busca_resumo_texto", "") or "").strip() or _resumo_status_site_texto()

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Status", ultimo_status.title())
    with col2:
        st.metric("Produtos", ultimo_total)

    if resumo_texto:
        st.caption(resumo_texto)


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


def _render_resumo_fornecedor(url_site: str) -> None:
    profile = _safe_profile(url_site)
    if not profile:
        return

    with st.expander("Perfil do fornecedor", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Fornecedor", str(profile.get("nome", "-") or "-"))
        with c2:
            st.metric("Modo", str(profile.get("auth_mode", "public") or "public"))
        with c3:
            st.metric("Tipo", str(profile.get("source_kind", "-") or "-"))

        notes = str(profile.get("notes", "") or "").strip()
        if notes:
            st.caption(notes)


def _render_status_autenticacao(url_site: str) -> None:
    state = _safe_auth_state()
    if not state and not url_site:
        return

    with st.container(border=True):
        st.markdown("### Autenticação do fornecedor")

        provider_name = str(state.get("provider_name", "") or _fornecedor_nome(url_site) or "Fornecedor").strip()
        status = str(state.get("status", "") or "inativo").strip()
        auth_mode = str(state.get("auth_mode", "") or "public").strip()
        session_ready = bool(state.get("session_ready", False))
        captcha_detected = bool(state.get("captcha_detected", False))
        detected_whatsapp_code = bool(state.get("detected_whatsapp_code", False))
        requires_whatsapp_code = bool(state.get("requires_whatsapp_code", False))
        last_message = str(state.get("last_message", "") or "").strip()

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Fornecedor", provider_name or "-")
        with c2:
            st.metric("Status", status or "-")
        with c3:
            st.metric("Modo", auth_mode or "-")
        with c4:
            st.metric("Sessão", "Pronta" if session_ready else "Pendente")

        if captcha_detected:
            st.warning("Captcha detectado. O fluxo recomendado é login assistido.")
        if detected_whatsapp_code or requires_whatsapp_code:
            st.warning("Código assistido/WhatsApp detectado. A sessão precisa ser autenticada manualmente.")
        if last_message:
            st.caption(last_message)


def _render_login_assistido(url_site: str) -> None:
    profile = _safe_profile(url_site)
    if not profile:
        return

    requires_login = bool(profile.get("login_required", False))
    requires_assisted = bool(profile.get("requires_assisted_login", False))
    requires_whatsapp = bool(profile.get("requires_whatsapp_code", False))
    captcha_expected = bool(profile.get("captcha_expected", False))
    login_url = str(profile.get("login_url", "") or "").strip()
    products_url = str(profile.get("products_url", "") or "").strip()

    if not requires_login:
        return

    with st.container(border=True):
        st.markdown("### Login assistido")
        st.caption("Use este bloco para fornecedores com painel autenticado, captcha ou código via WhatsApp.")

        if login_url:
            st.write(f"**URL de login:** {login_url}")
        if products_url:
            st.write(f"**Área de produtos:** {products_url}")

        if requires_whatsapp:
            st.info("Este fornecedor pode exigir código por WhatsApp antes de liberar o painel.")
        elif captcha_expected:
            st.info("Este fornecedor pode exigir captcha antes de liberar o painel.")
        elif requires_assisted:
            st.info("Este fornecedor exige autenticação assistida antes da busca.")

        col1, col2 = st.columns(2)
        with col1:
            if st.button(
                "Iniciar login assistido",
                use_container_width=True,
                key="btn_iniciar_login_assistido_real",
            ):
                resultado = _iniciar_login_assistido_real(url_site)
                if resultado:
                    st.success(str(resultado.get("mensagem", "") or "Fluxo assistido iniciado."))
                    st.rerun()
                st.error("Não foi possível iniciar o login assistido.")

        with col2:
            if st.button(
                "Atualizar status da sessão",
                use_container_width=True,
                key="btn_resumo_login_assistido_real",
            ):
                resumo = _atualizar_resumo_login_assistido(url_site)
                if resumo:
                    st.success(str(resumo.get("mensagem", "") or "Status atualizado."))
                    st.rerun()
                st.error("Não foi possível atualizar o status da sessão.")

        inicio = st.session_state.get("site_login_assistido_inicio", {})
        if isinstance(inicio, dict) and inicio:
            mensagem_inicio = str(inicio.get("mensagem", "") or "").strip()
            if mensagem_inicio:
                st.caption(mensagem_inicio)

        observacao_atual = str(st.session_state.get("site_login_assistido_observacao", "") or "").strip()
        observacao = st.text_input(
            "Observação da sessão assistida",
            value=observacao_atual,
            key="site_login_assistido_observacao",
            placeholder="Ex.: login concluído e painel de produtos já aberto",
        ).strip()

        cookies_atual = str(st.session_state.get("site_login_assistido_cookies_json", "") or "").strip()
        headers_atual = str(st.session_state.get("site_login_assistido_headers_json", "") or "").strip()

        st.text_area(
            "Cookies da sessão em JSON",
            value=cookies_atual,
            key="site_login_assistido_cookies_json",
            height=140,
            placeholder='[{"name":"session","value":"abc","domain":"app.fornecedor.com","path":"/"}]',
        )

        st.text_area(
            "Headers da sessão em JSON",
            value=headers_atual,
            key="site_login_assistido_headers_json",
            height=110,
            placeholder='{"User-Agent":"Mozilla/5.0","Accept":"text/html"}',
        )

        confirmado = bool(st.session_state.get("site_login_assistido_confirmado", False))
        novo_confirmado = st.checkbox(
            "Confirmo que o login assistido foi concluído e a sessão do fornecedor está pronta",
            value=confirmado,
            key="site_login_assistido_confirmado_checkbox",
        )

        st.session_state["site_login_assistido_confirmado"] = novo_confirmado
        st.session_state["site_login_assistido_observacao"] = observacao

        if st.button(
            "Salvar sessão assistida",
            use_container_width=True,
            key="btn_salvar_sessao_assistida_real",
        ):
            try:
                resultado = _salvar_sessao_assistida_real(url_site)
                if resultado:
                    st.success(str(resultado.get("mensagem", "") or "Sessão assistida salva com sucesso."))
                    st.rerun()
                st.error("Não foi possível salvar a sessão assistida.")
            except Exception as exc:
                st.error(str(exc))
                log_debug(f"Falha ao salvar sessão assistida: {exc}", nivel="ERRO")

        resumo = st.session_state.get("site_login_assistido_resumo", {})
        if isinstance(resumo, dict) and resumo:
            with st.expander("Resumo da sessão assistida", expanded=False):
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.metric("Fornecedor", str(resumo.get("provider_slug", "-") or "-"))
                with c2:
                    st.metric("Modo", str(resumo.get("auth_mode", "-") or "-"))
                with c3:
                    st.metric("Sessão", "Pronta" if bool(resumo.get("session_ready", False)) else "Pendente")

                mensagem_resumo = str(resumo.get("mensagem", "") or "").strip()
                if mensagem_resumo:
                    st.caption(mensagem_resumo)

        if novo_confirmado:
            st.success("Sessão assistida marcada como pronta para a próxima busca.")
        else:
            st.caption("Depois de autenticar no fornecedor, marque a sessão como pronta.")


def _render_inspecao_site(url_site: str) -> None:
    if not url_site:
        return

    with st.container(border=True):
        st.markdown("### Inspeção inteligente do fornecedor")

        col1, col2 = st.columns([2, 1])

        with col1:
            if st.button(
                "Inspecionar fornecedor",
                use_container_width=True,
                key="btn_inspecionar_fornecedor",
            ):
                resultado = _inspecionar_site(url_site)
                if resultado:
                    st.success("Inspeção concluída.")
                    st.rerun()
                st.error("Não foi possível inspecionar o fornecedor.")

        with col2:
            if st.button(
                "Limpar autenticação",
                use_container_width=True,
                key="btn_limpar_auth_site",
            ):
                st.session_state.pop("site_auth_state", None)
                st.session_state.pop("site_auth_last_result", None)
                st.session_state.pop("site_auth_inspecionado_url", None)
                st.session_state["site_login_assistido_confirmado"] = False
                st.session_state["site_login_assistido_observacao"] = ""
                st.info("Estado de autenticação limpo.")
                st.rerun()

        _render_resumo_fornecedor(url_site)
        _render_status_autenticacao(url_site)
        _render_login_assistido(url_site)


def _render_etapas_busca_site(url_site: str) -> None:
    if not url_site:
        st.info("Cole a URL do fornecedor para habilitar a busca.")
        return

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

    _render_resumo_busca_site()

    if _tem_resultado_site():
        _preview_dataframe(st.session_state.get("df_origem"), "Preview da busca por site")
    else:
        st.caption("Depois da busca, o preview dos produtos encontrados aparecerá aqui.")

    _render_diagnostico_site()


def _render_origem_site() -> None:
    with st.container(border=True):
        st.markdown("### Buscar no site do fornecedor")

        if "site_fornecedor_url" not in st.session_state:
            st.session_state["site_fornecedor_url"] = ""

        url_site = st.text_input(
            "URL do fornecedor ou categoria",
            key="site_fornecedor_url",
            placeholder="https://www.fornecedor.com.br/categoria",
        ).strip()

        st.checkbox(
            "Priorizar sitemap quando disponível",
            key="site_busca_modo_sitemap_primeiro",
            value=True,
            disabled=True,
            help="A busca já usa sitemap primeiro automaticamente quando o site expõe esse recurso.",
        )

        _render_inspecao_site(url_site)
        _render_etapas_busca_site(url_site)


def _render_modelo() -> None:
    with st.container(border=True):
        st.markdown("### Modelo do Bling")

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


def _render_continuar() -> None:
    st.markdown("### Continuar")
    _resumo_origem_atual()

    origem_ok = _origem_pronta()
    modelo_ok = _modelo_pronto()

    if not origem_ok:
        st.info("Carregue uma origem válida para continuar.")
        return

    if not modelo_ok:
        st.info("Envie um modelo válido para continuar.")
        return

    if not _validar_dados_operacao_para_continuar():
        return

    if st.button("Continuar ➜", key="btn_continuar_origem", use_container_width=True):
        ir_para_etapa("precificacao")
