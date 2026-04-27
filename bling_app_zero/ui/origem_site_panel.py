from __future__ import annotations

import inspect
import time
from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st

try:
    from bling_app_zero.core.site_agent import SiteAgent, buscar_produtos_site_com_gpt
except Exception:
    SiteAgent = None
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
    from bling_app_zero.core.site_supplier_store import (
        delete_site_supplier,
        get_site_supplier_by_slug,
        get_site_supplier_options,
        upsert_site_supplier,
    )
except Exception:
    delete_site_supplier = None
    get_site_supplier_by_slug = None
    get_site_supplier_options = None
    upsert_site_supplier = None

from bling_app_zero.ui.app_helpers import log_debug


MODO_FORNECEDOR_SALVO = "Fornecedor salvo"
MODO_NOVA_URL = "Nova URL"
OPCAO_NOVO_FORNECEDOR = "__novo_fornecedor__"


def _clean_text(value: Any) -> str:
    text = str(value or "").strip()
    return "" if text.lower() in {"none", "null", "nan"} else text


def _normalizar_ncm(valor: Any) -> str:
    texto = str(valor or "").strip()
    somente_digitos = "".join(ch for ch in texto if ch.isdigit())
    return somente_digitos[:8] if len(somente_digitos) >= 8 else ""


def _obter_ncm_padrao_site() -> str:
    return _normalizar_ncm(st.session_state.get("site_ncm_padrao", ""))


def _normalizar_df_saida_site(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()

    base = df.copy().fillna("")
    base.columns = [str(c).strip() for c in base.columns]

    for col in base.columns:
        try:
            base[col] = (
                base[col]
                .astype(str)
                .replace({"nan": "", "None": "", "none": "", "NaN": ""})
                .fillna("")
            )
        except Exception:
            continue

    return base


def _aplicar_ncm_padrao_df(df: pd.DataFrame) -> pd.DataFrame:
    base = _normalizar_df_saida_site(df)
    if base.empty and len(base.columns) == 0:
        return base

    ncm_padrao = _obter_ncm_padrao_site()

    if "NCM" not in base.columns:
        base["NCM"] = ""

    if ncm_padrao:
        base["NCM"] = base["NCM"].apply(lambda atual: _normalizar_ncm(atual) or ncm_padrao)
    else:
        base["NCM"] = base["NCM"].apply(_normalizar_ncm)

    return base


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


def _safe_auth_state() -> dict:
    value = st.session_state.get("site_auth_state")
    return value if isinstance(value, dict) else {}


def _registrar_evento_progresso_site(mensagem: str) -> None:
    mensagem = str(mensagem or "").strip()
    if not mensagem:
        return

    logs = st.session_state.get("site_busca_progress_logs")
    if not isinstance(logs, list):
        logs = []

    logs.append(mensagem)
    st.session_state["site_busca_progress_logs"] = logs[-30:]


def _logs_recentes_site(limite: int = 8) -> list[str]:
    logs = st.session_state.get("site_busca_progress_logs")
    if not isinstance(logs, list):
        logs = []

    globais = st.session_state.get("logs")
    if isinstance(globais, list):
        for item in globais[-limite:]:
            texto = str(item or "").strip()
            if texto and texto not in logs:
                logs.append(texto)

    return [str(x).strip() for x in logs[-limite:] if str(x).strip()]


def _atualizar_progresso_site(
    percentual: int,
    etapa: str,
    detalhe: str = "",
    *,
    status: str = "executando",
) -> None:
    percentual = max(0, min(int(percentual or 0), 100))
    etapa = str(etapa or "").strip()
    detalhe = str(detalhe or "").strip()

    st.session_state["site_busca_progress_percent"] = percentual
    st.session_state["site_busca_progress_etapa"] = etapa
    st.session_state["site_busca_progress_detalhe"] = detalhe
    st.session_state["site_busca_progress_status"] = status
    st.session_state["site_busca_ultimo_status"] = status

    texto = detalhe or etapa
    if texto:
        st.session_state["site_busca_resumo_texto"] = texto
        _registrar_evento_progresso_site(f"{percentual}% — {etapa or status}: {texto}")


def _iniciar_progresso_site(url_site: str, *, modo_completo: bool, sitemap_completo: bool) -> None:
    st.session_state["site_busca_progress_inicio_ts"] = time.time()
    st.session_state["site_busca_progress_logs"] = []
    st.session_state["site_busca_ultimo_total"] = 0
    st.session_state["site_busca_ultima_url"] = url_site
    st.session_state["site_busca_fonte_descoberta"] = (
        "http_hybrid_completo_sitemap" if sitemap_completo else "http_hybrid"
    )
    st.session_state["site_busca_modo_execucao"] = (
        "varredura_completa" if modo_completo else "varredura_controlada"
    )
    _atualizar_progresso_site(
        3,
        "Preparando busca",
        "Montando leitura HTTP-first do fornecedor.",
    )


def _status_legivel_site(status: str) -> str:
    mapa = {
        "executando": "Executando",
        "sucesso": "Concluído",
        "erro": "Erro",
        "vazio": "Sem produtos",
        "inativo": "Aguardando",
    }
    status = str(status or "").strip().lower()
    return mapa.get(status, status.replace("_", " ").title() if status else "Aguardando")


def _modo_legivel_site(modo: str) -> str:
    mapa = {
        "varredura_completa": "Completa",
        "varredura_controlada": "Controlada",
        "http_hybrid_completo_sitemap": "HTTP + sitemap",
        "http_hybrid": "HTTP híbrido",
    }
    modo = str(modo or "").strip().lower()
    return mapa.get(modo, modo.replace("_", " ").title() if modo else "-")


def _criar_painel_progresso_site() -> Dict[str, Any]:
    st.markdown("### Progresso da busca")
    return {
        "barra": st.empty(),
        "cards": st.empty(),
        "status": st.empty(),
        "logs": st.empty(),
    }


def _desenhar_cards_progresso_site(container: Any, status: str, total: int, decorrido: int, modo: str) -> None:
    with container.container():
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Status", _status_legivel_site(status))
        c2.metric("Produtos", int(total or 0))
        c3.metric("Tempo", f"{int(decorrido or 0)}s")
        c4.metric("Modo", _modo_legivel_site(modo))


def _desenhar_painel_progresso_site(painel: Optional[Dict[str, Any]] = None) -> None:
    if not isinstance(painel, dict):
        return

    percentual = int(st.session_state.get("site_busca_progress_percent", 0) or 0)
    etapa = _clean_text(st.session_state.get("site_busca_progress_etapa", ""))
    detalhe = _clean_text(st.session_state.get("site_busca_progress_detalhe", ""))
    status = _clean_text(st.session_state.get("site_busca_progress_status", "executando"))
    total = int(st.session_state.get("site_busca_ultimo_total", 0) or 0)
    modo = _clean_text(st.session_state.get("site_busca_modo_execucao", "-"))
    url = _clean_text(st.session_state.get("site_busca_ultima_url", ""))
    inicio = float(st.session_state.get("site_busca_progress_inicio_ts", time.time()) or time.time())
    decorrido = max(0, int(time.time() - inicio))

    painel["barra"].progress(percentual, text=f"{percentual}% — {etapa or _status_legivel_site(status)}")
    _desenhar_cards_progresso_site(painel["cards"], status, total, decorrido, modo)

    texto_status = detalhe or etapa or "Busca em andamento."
    if url:
        texto_status = f"{texto_status}\n\nURL: {url}"

    if status == "erro":
        painel["status"].error(texto_status)
    elif status == "sucesso":
        painel["status"].success(texto_status)
    elif status == "vazio":
        painel["status"].warning(texto_status)
    else:
        painel["status"].info(texto_status)

    with painel["logs"].container():
        logs = _logs_recentes_site(8)
        if logs:
            st.caption("Últimos eventos")
            for log in logs[-6:]:
                st.caption(f"• {log}")


def _render_progresso_persistente_site() -> None:
    etapa = _clean_text(st.session_state.get("site_busca_progress_etapa", ""))
    detalhe = _clean_text(st.session_state.get("site_busca_progress_detalhe", ""))
    status = _clean_text(st.session_state.get("site_busca_progress_status", ""))

    if not etapa and not detalhe and not status:
        return

    percentual = int(st.session_state.get("site_busca_progress_percent", 0) or 0)

    with st.expander("Progresso da última busca", expanded=False):
        st.progress(percentual, text=f"{percentual}% — {etapa or _status_legivel_site(status)}")
        if detalhe:
            st.caption(detalhe)

        modo = _clean_text(st.session_state.get("site_busca_modo_execucao", ""))
        total = int(st.session_state.get("site_busca_ultimo_total", 0) or 0)
        inicio = float(st.session_state.get("site_busca_progress_inicio_ts", time.time()) or time.time())
        decorrido = max(0, int(time.time() - inicio))
        _desenhar_cards_progresso_site(st.empty(), status, total, decorrido, modo)

        logs = _logs_recentes_site(8)
        for log in logs[-6:]:
            st.caption(f"• {log}")


def _preview_dataframe(df: pd.DataFrame, titulo: str) -> None:
    with st.expander(titulo, expanded=False):
        if not isinstance(df, pd.DataFrame):
            st.info("Sem estrutura tabular.")
            return

        if len(df.columns) == 0:
            st.info("Nenhuma coluna encontrada.")
            return

        if df.empty:
            st.info("Busca executada sem linhas úteis.")
            st.dataframe(pd.DataFrame(columns=df.columns), use_container_width=True)
            return

        st.dataframe(df.head(80), use_container_width=True)


def _carimbar_execucao_site(total_produtos: int, url_site: str, status: str) -> None:
    from datetime import datetime

    st.session_state["site_busca_ultima_url"] = url_site
    st.session_state["site_busca_ultimo_total"] = int(total_produtos or 0)
    st.session_state["site_busca_ultimo_status"] = status
    st.session_state["site_busca_ultima_execucao"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _limpar_df_origem_site() -> None:
    for chave in [
        "df_origem",
        "origem_upload_tipo",
        "origem_upload_nome",
        "origem_upload_ext",
        "origem_upload_bytes",
    ]:
        st.session_state.pop(chave, None)


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
        "site_busca_modo_execucao",
        "site_auth_last_result",
        "site_auth_inspecionado_url",
        "site_auth_state",
        "site_busca_progress_percent",
        "site_busca_progress_etapa",
        "site_busca_progress_detalhe",
        "site_busca_progress_status",
        "site_busca_progress_inicio_ts",
        "site_busca_progress_logs",
    ]:
        st.session_state.pop(chave, None)


def _forcar_http_first_execucao() -> None:
    st.session_state["preferir_http"] = True
    st.session_state["site_runtime_http_first"] = True
    st.session_state["site_runtime_modo"] = "http_hybrid"
    st.session_state["site_runtime_browser_opcional"] = False
    st.session_state["crawler_runtime_mode"] = "http_hybrid"
    st.session_state["crawler_browser_disponivel"] = False
    st.session_state["crawler_forcar_http"] = True
    st.session_state["playwright_habilitado"] = False
    st.session_state["playwright_browser_ok"] = False
    st.session_state["site_busca_usa_playwright"] = False
    st.session_state["site_login_usa_playwright"] = False
    st.session_state["site_origem_usa_playwright"] = False

    for chave in [
        "_playwright_bootstrap",
        "_crawler_runtime_bootstrap_done",
        "playwright_modulo_instalado",
        "_playwright_forcado_erro",
        "site_login_modo_browser",
    ]:
        st.session_state.pop(chave, None)


def _fornecedores_preset() -> list[dict]:
    return [
        {
            "slug": "preset_megacenter",
            "nome": "Mega Center",
            "url_base": "https://www.megacentereletronicos.com.br/",
            "login_url": "",
            "products_url": "https://www.megacentereletronicos.com.br/",
            "auth_mode": "public",
            "observacoes": "Catálogo público. Use a home ou uma categoria específica.",
            "origem": "preset",
        },
        {
            "slug": "preset_atacadum",
            "nome": "Atacadum",
            "url_base": "https://www.atacadum.com.br/",
            "login_url": "",
            "products_url": "https://www.atacadum.com.br/",
            "auth_mode": "public",
            "observacoes": "Catálogo público. Busca direta por site em modo HTTP-first.",
            "origem": "preset",
        },
    ]


def _carregar_fornecedores_mixados() -> list[dict]:
    presets = _fornecedores_preset()
    salvos: list[dict] = []

    if get_site_supplier_options is not None and get_site_supplier_by_slug is not None:
        try:
            opcoes = get_site_supplier_options() or []
            for item in opcoes:
                slug = _clean_text(item.get("value"))
                if not slug:
                    continue

                fornecedor = get_site_supplier_by_slug(slug)
                if fornecedor:
                    salvos.append(
                        {
                            "slug": _clean_text(fornecedor.get("slug")),
                            "nome": _clean_text(fornecedor.get("nome")),
                            "url_base": _clean_text(fornecedor.get("url_base")),
                            "login_url": _clean_text(fornecedor.get("login_url")),
                            "products_url": _clean_text(fornecedor.get("products_url")),
                            "auth_mode": _clean_text(fornecedor.get("auth_mode")),
                            "observacoes": _clean_text(fornecedor.get("observacoes")),
                            "origem": "salvo",
                        }
                    )
        except Exception as exc:
            log_debug(f"Falha ao carregar fornecedores salvos: {exc}", nivel="ERRO")

    resultado: list[dict] = []
    vistos = set()

    for fornecedor in salvos + presets:
        slug = _clean_text(fornecedor.get("slug"))
        if not slug or slug in vistos:
            continue
        vistos.add(slug)
        resultado.append(fornecedor)

    return resultado


def _aplicar_fornecedor_na_tela(fornecedor: Optional[Dict[str, Any]]) -> None:
    if not fornecedor:
        return

    st.session_state["site_fornecedor_slug"] = _clean_text(fornecedor.get("slug"))
    st.session_state["site_fornecedor_nome_manual"] = _clean_text(fornecedor.get("nome"))
    st.session_state["site_fornecedor_url"] = _clean_text(fornecedor.get("url_base"))
    st.session_state["site_fornecedor_login_url"] = _clean_text(fornecedor.get("login_url"))
    st.session_state["site_fornecedor_products_url"] = _clean_text(fornecedor.get("products_url"))
    st.session_state["site_fornecedor_auth_mode"] = _clean_text(fornecedor.get("auth_mode"))
    st.session_state["site_fornecedor_observacoes"] = _clean_text(fornecedor.get("observacoes"))


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
            "status": _clean_text(data.get("status")),
            "provider_slug": _clean_text(data.get("provider_slug")),
            "provider_name": _clean_text(data.get("provider_name")),
            "requires_login": bool(data.get("requires_login", False)),
            "captcha_detected": bool(data.get("captcha_detected", False)),
            "login_url": _clean_text(data.get("login_url")),
            "products_url": _clean_text(data.get("products_url")),
            "auth_mode": _clean_text(data.get("auth_mode") or "public"),
            "session_ready": bool(data.get("session_ready", False)),
            "last_message": _clean_text(data.get("message")),
        }
        st.session_state["site_auth_inspecionado_url"] = url_site
        return data
    except Exception as exc:
        log_debug(f"Falha ao inspecionar site: {exc}", nivel="ERRO")
        return {}


def _auth_context_para_busca(url_site: str) -> dict | None:
    contexto: dict = {}

    if get_auth_headers_and_cookies is not None:
        try:
            recebido = get_auth_headers_and_cookies()
            if isinstance(recebido, dict):
                contexto.update(recebido)
        except Exception as exc:
            log_debug(f"Falha ao montar auth_context: {exc}", nivel="ERRO")

    profile = _safe_profile(url_site)

    provider_slug = _clean_text(
        contexto.get("provider_slug")
        or contexto.get("fornecedor_slug")
        or st.session_state.get("site_fornecedor_slug")
        or profile.get("slug")
    )

    products_url = _clean_text(
        contexto.get("products_url")
        or st.session_state.get("site_fornecedor_products_url")
        or profile.get("products_url")
        or url_site
    )

    login_url = _clean_text(
        contexto.get("login_url")
        or st.session_state.get("site_fornecedor_login_url")
        or profile.get("login_url")
    )

    auth_mode = _clean_text(
        contexto.get("auth_mode")
        or st.session_state.get("site_fornecedor_auth_mode")
        or profile.get("auth_mode")
        or "public"
    )

    contexto["fornecedor_slug"] = provider_slug
    contexto["provider_slug"] = provider_slug
    contexto["products_url"] = products_url
    contexto["login_url"] = login_url
    contexto["auth_mode"] = auth_mode
    contexto["preferir_http"] = True
    contexto["crawler_runtime_mode"] = "http_hybrid"
    contexto["browser_disabled"] = True

    return contexto


def _modo_varredura_completa_ativo() -> bool:
    if "site_varrer_completo" not in st.session_state:
        st.session_state["site_varrer_completo"] = True
    return bool(st.session_state.get("site_varrer_completo", True))


def _modo_sitemap_completo_ativo() -> bool:
    if "site_usar_sitemap_completo" not in st.session_state:
        st.session_state["site_usar_sitemap_completo"] = True
    return bool(st.session_state.get("site_usar_sitemap_completo", True))


def _montar_kwargs_busca_site(url_site: str, auth_context: Optional[dict]) -> Dict[str, Any]:
    modo_completo = _modo_varredura_completa_ativo()
    sitemap_completo = _modo_sitemap_completo_ativo()

    kwargs_busca: Dict[str, Any] = {
        "base_url": url_site,
        "diagnostico": True,
        "auth_context": auth_context,
        "preferir_http": True,
        "usar_fornecedor": True,
        "usar_generico": True,
        "max_workers": 16 if modo_completo else 8,
        "varrer_site_completo": modo_completo,
        "sitemap_completo": sitemap_completo,
        "varrer_sitemap_completo": sitemap_completo,
    }

    if modo_completo:
        kwargs_busca["limite"] = 0
        kwargs_busca["limite_links"] = 0
        kwargs_busca["limite_paginas"] = 0
    else:
        kwargs_busca["limite"] = 300
        kwargs_busca["limite_links"] = 300
        kwargs_busca["limite_paginas"] = 20

    return kwargs_busca


def _registrar_status_execucao_site(
    mensagem: str,
    *,
    status: str = "executando",
    percentual: Optional[int] = None,
    etapa: str = "",
    painel_progress: Optional[Dict[str, Any]] = None,
) -> None:
    st.session_state["site_busca_ultimo_status"] = status
    st.session_state["site_busca_resumo_texto"] = mensagem

    if percentual is not None:
        _atualizar_progresso_site(percentual, etapa or mensagem, mensagem, status=status)
        _desenhar_painel_progresso_site(painel_progress)
    else:
        _registrar_evento_progresso_site(mensagem)

    try:
        log_debug(mensagem)
    except Exception:
        pass


def _chamar_busca_site_compativel(url_site: str, painel_progress: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
    _forcar_http_first_execucao()

    _registrar_status_execucao_site(
        "Preparando sessão do fornecedor.",
        percentual=8,
        etapa="Preparando sessão",
        painel_progress=painel_progress,
    )
    auth_context = _auth_context_para_busca(url_site)

    _registrar_status_execucao_site(
        "Montando parâmetros de varredura.",
        percentual=15,
        etapa="Montando busca",
        painel_progress=painel_progress,
    )
    kwargs_busca = _montar_kwargs_busca_site(url_site, auth_context)

    _registrar_status_execucao_site(
        "Lendo site, sitemap, categorias, paginações e páginas de produto.",
        percentual=28,
        etapa="Coletando produtos",
        painel_progress=painel_progress,
    )

    if SiteAgent is not None:
        try:
            agent = SiteAgent()
            resultado = agent.buscar_dataframe(**kwargs_busca)

            _registrar_status_execucao_site(
                "Normalizando resultado retornado pelo SiteAgent.",
                percentual=82,
                etapa="Normalizando dados",
                painel_progress=painel_progress,
            )

            if isinstance(resultado, pd.DataFrame):
                return _normalizar_df_saida_site(resultado)
            if isinstance(resultado, list):
                return _normalizar_df_saida_site(pd.DataFrame(resultado))
        except Exception as exc:
            log_debug(f"SiteAgent falhou: {exc}", nivel="ERRO")

    if buscar_produtos_site_com_gpt is not None:
        try:
            _registrar_status_execucao_site(
                "Fallback ativado. Tentando mecanismo alternativo de busca.",
                percentual=55,
                etapa="Fallback",
                painel_progress=painel_progress,
            )

            kwargs_gpt = dict(kwargs_busca)

            try:
                assinatura = inspect.signature(buscar_produtos_site_com_gpt)
                parametros = assinatura.parameters

                if "termo" in parametros:
                    kwargs_gpt["termo"] = ""

                aceita_kwargs = any(
                    p.kind == inspect.Parameter.VAR_KEYWORD for p in parametros.values()
                )

                if not aceita_kwargs:
                    kwargs_gpt = {k: v for k, v in kwargs_gpt.items() if k in parametros}

            except Exception:
                pass

            resultado = buscar_produtos_site_com_gpt(**kwargs_gpt)

            if isinstance(resultado, pd.DataFrame):
                return _normalizar_df_saida_site(resultado)
            if isinstance(resultado, list):
                return _normalizar_df_saida_site(pd.DataFrame(resultado))
            if isinstance(resultado, dict):
                for chave in ["df", "dataframe", "produtos", "items", "dados"]:
                    valor = resultado.get(chave)
                    if isinstance(valor, pd.DataFrame):
                        return _normalizar_df_saida_site(valor)
                    if isinstance(valor, list):
                        return _normalizar_df_saida_site(pd.DataFrame(valor))

        except Exception as exc:
            log_debug(f"Fallback buscar_produtos_site_com_gpt falhou: {exc}", nivel="ERRO")

    return pd.DataFrame()


def _executar_busca_site(url_site: str) -> None:
    url_site = _clean_text(url_site)

    if not url_site:
        st.error("Informe a URL do fornecedor.")
        return

    if not url_site.startswith(("http://", "https://")):
        url_site = "https://" + url_site

    modo_completo = _modo_varredura_completa_ativo()
    sitemap_completo = _modo_sitemap_completo_ativo()

    _limpar_df_origem_site()
    st.session_state["site_busca_em_execucao"] = True
    _iniciar_progresso_site(url_site, modo_completo=modo_completo, sitemap_completo=sitemap_completo)

    painel = _criar_painel_progresso_site()
    _desenhar_painel_progresso_site(painel)

    try:
        df = _chamar_busca_site_compativel(url_site, painel)
        df = _aplicar_ncm_padrao_df(df)

        total = len(df) if isinstance(df, pd.DataFrame) else 0

        if total > 0:
            st.session_state["df_origem"] = df
            st.session_state["origem_upload_tipo"] = "site"
            st.session_state["origem_upload_nome"] = url_site
            st.session_state["origem_upload_ext"] = ".site"
            st.session_state["site_busca_ultimo_total"] = total

            _carimbar_execucao_site(total, url_site, "sucesso")
            _registrar_status_execucao_site(
                f"Busca concluída. {total} produto(s) encontrado(s).",
                status="sucesso",
                percentual=100,
                etapa="Concluído",
                painel_progress=painel,
            )
            st.success(f"Busca concluída: {total} produto(s) encontrado(s).")
            _preview_dataframe(df, "Preview dos produtos capturados")
        else:
            _carimbar_execucao_site(0, url_site, "vazio")
            _registrar_status_execucao_site(
                "Busca concluída, mas nenhum produto útil foi encontrado.",
                status="vazio",
                percentual=100,
                etapa="Sem produtos",
                painel_progress=painel,
            )
            st.warning("Nenhum produto foi encontrado nessa URL.")

    except Exception as exc:
        _carimbar_execucao_site(0, url_site, "erro")
        _registrar_status_execucao_site(
            f"Erro na busca: {exc}",
            status="erro",
            percentual=100,
            etapa="Erro",
            painel_progress=painel,
        )
        st.error(f"Erro na busca pelo site: {exc}")
        log_debug(f"Erro na busca pelo site: {exc}", nivel="ERRO")
    finally:
        st.session_state["site_busca_em_execucao"] = False


def _render_fornecedor_salvo() -> str:
    fornecedores = _carregar_fornecedores_mixados()

    if not fornecedores:
        st.info("Nenhum fornecedor salvo encontrado. Use uma nova URL.")
        return ""

    labels = [
        f"{f.get('nome') or f.get('slug')} — {f.get('url_base') or f.get('products_url')}"
        for f in fornecedores
    ]

    escolha = st.selectbox(
        "Fornecedor",
        options=list(range(len(fornecedores))),
        format_func=lambda i: labels[i],
        key="site_fornecedor_select_idx",
    )

    fornecedor = fornecedores[int(escolha)]
    _aplicar_fornecedor_na_tela(fornecedor)

    url_padrao = _clean_text(fornecedor.get("products_url") or fornecedor.get("url_base"))

    st.caption(_clean_text(fornecedor.get("observacoes")) or "Fornecedor selecionado.")
    return st.text_input(
        "URL para buscar",
        value=url_padrao,
        key="site_url_fornecedor_salvo",
        placeholder="https://www.exemplo.com.br/categoria",
    ).strip()


def _render_nova_url() -> str:
    url_atual = _clean_text(st.session_state.get("site_url_manual", ""))

    url_site = st.text_input(
        "URL do fornecedor ou categoria",
        value=url_atual,
        key="site_url_manual",
        placeholder="https://www.megacentereletronicos.com.br/",
    ).strip()

    st.session_state["site_fornecedor_url"] = url_site
    st.session_state["site_fornecedor_products_url"] = url_site

    return url_site


def _render_opcoes_avancadas() -> None:
    with st.expander("Opções da busca", expanded=False):
        st.checkbox(
            "Buscar o máximo possível no site",
            value=bool(st.session_state.get("site_varrer_completo", True)),
            key="site_varrer_completo",
            help="Quando ativo, tenta ler sitemap completo, categorias e paginações sem limite artificial.",
        )
        st.checkbox(
            "Usar sitemap completo quando disponível",
            value=bool(st.session_state.get("site_usar_sitemap_completo", True)),
            key="site_usar_sitemap_completo",
        )

        ncm_atual = _clean_text(st.session_state.get("site_ncm_padrao", ""))
        st.text_input(
            "NCM padrão para preencher quando o site não informar",
            value=ncm_atual,
            key="site_ncm_padrao",
            placeholder="Ex.: 85183000",
            help="Opcional. Use 8 dígitos.",
        )


def _render_botoes_auxiliares(url_site: str) -> None:
    c1, c2 = st.columns(2)

    with c1:
        if st.button("Inspecionar site", key="btn_inspecionar_site", use_container_width=True):
            if not url_site:
                st.warning("Informe uma URL antes de inspecionar.")
            else:
                url = url_site if url_site.startswith(("http://", "https://")) else f"https://{url_site}"
                data = _inspecionar_site(url)
                if data:
                    st.success("Inspeção concluída.")
                    with st.expander("Resultado da inspeção", expanded=False):
                        st.json(data)
                else:
                    st.info("Inspeção não retornou dados úteis.")

    with c2:
        if st.button("Limpar busca do site", key="btn_limpar_busca_site", use_container_width=True):
            _resetar_estado_site_ui()
            _limpar_df_origem_site()
            st.success("Busca do site limpa.")
            st.rerun()


def _render_resultado_atual() -> None:
    df = st.session_state.get("df_origem")

    if not isinstance(df, pd.DataFrame) or df.empty:
        return

    if st.session_state.get("origem_upload_tipo") != "site":
        return

    st.success(f"Origem por site carregada: {len(df)} produto(s).")
    _preview_dataframe(df, "Preview atual da origem por site")


def _render_salvar_fornecedor(url_site: str) -> None:
    if upsert_site_supplier is None:
        return

    with st.expander("Salvar fornecedor", expanded=False):
        nome = st.text_input(
            "Nome do fornecedor",
            value=_clean_text(st.session_state.get("site_fornecedor_nome_manual", "")),
            key="site_fornecedor_nome_manual",
            placeholder="Ex.: Mega Center",
        )

        slug = st.text_input(
            "Slug interno",
            value=_clean_text(st.session_state.get("site_fornecedor_slug", "")),
            key="site_fornecedor_slug",
            placeholder="ex.: megacenter",
        )

        login_url = st.text_input(
            "URL de login, se houver",
            value=_clean_text(st.session_state.get("site_fornecedor_login_url", "")),
            key="site_fornecedor_login_url",
        )

        obs = st.text_area(
            "Observações",
            value=_clean_text(st.session_state.get("site_fornecedor_observacoes", "")),
            key="site_fornecedor_observacoes",
        )

        if st.button("Salvar fornecedor", key="btn_salvar_fornecedor_site", use_container_width=True):
            if not nome or not slug or not url_site:
                st.warning("Informe nome, slug e URL antes de salvar.")
                return

            try:
                upsert_site_supplier(
                    {
                        "slug": slug,
                        "nome": nome,
                        "url_base": url_site,
                        "login_url": login_url,
                        "products_url": url_site,
                        "auth_mode": "public",
                        "observacoes": obs,
                    }
                )
                st.success("Fornecedor salvo.")
            except Exception as exc:
                st.error(f"Não foi possível salvar o fornecedor: {exc}")


def render_origem_site_panel() -> None:
    _forcar_http_first_execucao()

    st.markdown("#### Buscar produtos no site")
    st.caption(
        "Informe a URL da home, categoria ou página do fornecedor. "
        "A busca prioriza HTTP-first, sitemap, categorias e paginações."
    )

    if "site_modo_fornecedor" not in st.session_state:
        st.session_state["site_modo_fornecedor"] = MODO_NOVA_URL

    modo = st.radio(
        "Como deseja buscar?",
        [MODO_NOVA_URL, MODO_FORNECEDOR_SALVO],
        horizontal=True,
        key="site_modo_fornecedor",
    )

    if modo == MODO_FORNECEDOR_SALVO:
        url_site = _render_fornecedor_salvo()
    else:
        url_site = _render_nova_url()

    _render_opcoes_avancadas()
    _render_botoes_auxiliares(url_site)
    _render_progresso_persistente_site()

    st.markdown("### Executar busca")

    if st.button("Buscar produtos no site", key="btn_executar_busca_site", use_container_width=True):
        _executar_busca_site(url_site)

    _render_resultado_atual()
    _render_salvar_fornecedor(url_site)
