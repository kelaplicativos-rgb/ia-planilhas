from __future__ import annotations

import inspect
from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st

try:
    from bling_app_zero.core.site_agent import buscar_produtos_site_com_gpt, SiteAgent
except Exception:
    buscar_produtos_site_com_gpt = None
    SiteAgent = None

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


def _normalizar_df_saida_site(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()

    base = df.copy().fillna("")
    base.columns = [str(c).strip() for c in base.columns]

    for col in base.columns:
        try:
            base[col] = base[col].astype(str).replace({"nan": "", "None": "", "none": ""}).fillna("")
        except Exception:
            continue

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

        st.dataframe(df.head(50), use_container_width=True)


def _carimbar_execucao_site(total_produtos: int, url_site: str, status: str) -> None:
    from datetime import datetime

    st.session_state["site_busca_ultima_url"] = url_site
    st.session_state["site_busca_ultimo_total"] = int(total_produtos)
    st.session_state["site_busca_ultimo_status"] = status
    st.session_state["site_busca_ultima_execucao"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _limpar_df_origem_site() -> None:
    st.session_state.pop("df_origem", None)
    st.session_state.pop("origem_upload_tipo", None)
    st.session_state.pop("origem_upload_nome", None)
    st.session_state.pop("origem_upload_ext", None)


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
        "site_auth_last_result",
        "site_auth_inspecionado_url",
        "site_auth_state",
    ]:
        st.session_state.pop(chave, None)


def _resetar_estado_busca_ao_trocar_fornecedor() -> None:
    _resetar_estado_site_ui()
    _limpar_df_origem_site()


def _forcar_modo_fornecedor(modo: str) -> None:
    st.session_state["site_modo_fornecedor_forcado"] = modo


def _aplicar_modo_fornecedor_forcado() -> None:
    modo_forcado = _clean_text(st.session_state.pop("site_modo_fornecedor_forcado", ""))
    if modo_forcado in {MODO_FORNECEDOR_SALVO, MODO_NOVA_URL}:
        st.session_state["site_modo_fornecedor"] = modo_forcado


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
    """
    Fornecedores base para preenchimento rápido.
    """
    return [
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
        {
            "slug": "preset_obaobamix",
            "nome": "Oba Oba Mix",
            "url_base": "https://app.obaobamix.com.br/",
            "login_url": "https://app.obaobamix.com.br/login",
            "products_url": "https://app.obaobamix.com.br/admin/products",
            "auth_mode": "captcha",
            "observacoes": "Fornecedor com login/painel. Pode exigir inspeção/autenticação antes da busca.",
            "origem": "preset",
        },
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
            "slug": "preset_stoqui",
            "nome": "Stoqui",
            "url_base": "https://stoqui.com.br/",
            "login_url": "https://stoqui.com.br/login",
            "products_url": "https://stoqui.com.br/",
            "auth_mode": "whatsapp_code",
            "observacoes": "Ambiente autenticado. Pode exigir código e inspeção antes da busca.",
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
                try:
                    fornecedor = get_site_supplier_by_slug(slug)
                except Exception:
                    fornecedor = None
                if fornecedor:
                    salvos.append(
                        {
                            "slug": str(fornecedor.get("slug", "") or ""),
                            "nome": str(fornecedor.get("nome", "") or ""),
                            "url_base": str(fornecedor.get("url_base", "") or ""),
                            "login_url": str(fornecedor.get("login_url", "") or ""),
                            "products_url": str(fornecedor.get("products_url", "") or ""),
                            "auth_mode": str(fornecedor.get("auth_mode", "") or ""),
                            "observacoes": str(fornecedor.get("observacoes", "") or ""),
                            "origem": "salvo",
                        }
                    )
        except Exception as exc:
            log_debug(f"Falha ao carregar fornecedores salvos: {exc}", nivel="ERRO")

    resultado: list[dict] = []
    slugs_vistos = set()

    for fornecedor in salvos + presets:
        slug = _clean_text(fornecedor.get("slug"))
        if not slug or slug in slugs_vistos:
            continue
        slugs_vistos.add(slug)
        resultado.append(fornecedor)

    return resultado


def _aplicar_fornecedor_na_tela(fornecedor: Optional[Dict[str, Any]]) -> None:
    if not fornecedor:
        return

    st.session_state["site_fornecedor_slug"] = str(fornecedor.get("slug", "") or "")
    st.session_state["site_fornecedor_nome_manual"] = str(fornecedor.get("nome", "") or "")
    st.session_state["site_fornecedor_url"] = str(fornecedor.get("url_base", "") or "")
    st.session_state["site_fornecedor_login_url"] = str(fornecedor.get("login_url", "") or "")
    st.session_state["site_fornecedor_products_url"] = str(fornecedor.get("products_url", "") or "")
    st.session_state["site_fornecedor_auth_mode"] = str(fornecedor.get("auth_mode", "") or "")
    st.session_state["site_fornecedor_observacoes"] = str(fornecedor.get("observacoes", "") or "")


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
        }
        st.session_state["site_auth_inspecionado_url"] = url_site
        return data
    except Exception as exc:
        log_debug(f"Falha ao inspecionar site: {exc}", nivel="ERRO")
        return {}


def _auth_context_para_busca(url_site: str) -> dict | None:
    if get_auth_headers_and_cookies is None:
        return None

    try:
        contexto = get_auth_headers_and_cookies()
        if not isinstance(contexto, dict):
            return None

        profile = _safe_profile(url_site)
        provider_slug = str(
            contexto.get("provider_slug", "")
            or st.session_state.get("site_fornecedor_slug", "")
            or profile.get("slug", "")
            or ""
        ).strip()
        products_url = str(
            contexto.get("products_url", "")
            or st.session_state.get("site_fornecedor_products_url", "")
            or profile.get("products_url", "")
            or url_site
        ).strip()
        login_url = str(
            contexto.get("login_url", "")
            or st.session_state.get("site_fornecedor_login_url", "")
            or profile.get("login_url", "")
            or ""
        ).strip()
        auth_mode = str(
            contexto.get("auth_mode", "")
            or st.session_state.get("site_fornecedor_auth_mode", "")
            or profile.get("auth_mode", "")
            or "public"
        ).strip()

        contexto["fornecedor_slug"] = provider_slug
        contexto["provider_slug"] = provider_slug
        contexto["products_url"] = products_url
        contexto["login_url"] = login_url
        contexto["auth_mode"] = auth_mode
        contexto["preferir_http"] = True
        contexto["crawler_runtime_mode"] = "http_hybrid"
        contexto["browser_disabled"] = True
        return contexto
    except Exception as exc:
        log_debug(f"Falha ao montar auth_context: {exc}", nivel="ERRO")
        return None


def _chamar_busca_site_compativel(url_site: str) -> pd.DataFrame:
    _forcar_http_first_execucao()
    auth_context = _auth_context_para_busca(url_site)

    if SiteAgent is not None:
        try:
            agent = SiteAgent()
            resultado = agent.buscar_dataframe(
                base_url=url_site,
                diagnostico=True,
                auth_context=auth_context,
                limite=500,
                preferir_http=True,
                usar_fornecedor=False,
                usar_generico=False,
                max_workers=10,
                limite_paginas=12,
            )
            if isinstance(resultado, pd.DataFrame):
                return _normalizar_df_saida_site(resultado)
            if isinstance(resultado, list):
                return _normalizar_df_saida_site(pd.DataFrame(resultado))
        except Exception as exc:
            log_debug(f"SiteAgent falhou: {exc}", nivel="ERRO")

    if buscar_produtos_site_com_gpt is not None:
        try:
            kwargs_gpt: Dict[str, Any] = {
                "base_url": url_site,
                "diagnostico": True,
                "auth_context": auth_context,
                "limite_links": 500,
            }

            try:
                assinatura = inspect.signature(buscar_produtos_site_com_gpt)
                parametros = assinatura.parameters
                kwargs_filtrados = {k: v for k, v in kwargs_gpt.items() if k in parametros}
                if "termo" in parametros:
                    kwargs_filtrados["termo"] = ""
            except Exception:
                kwargs_filtrados = kwargs_gpt

            resultado = buscar_produtos_site_com_gpt(**kwargs_filtrados)
            if isinstance(resultado, pd.DataFrame):
                return _normalizar_df_saida_site(resultado)
            if isinstance(resultado, list):
                return _normalizar_df_saida_site(pd.DataFrame(resultado))
        except Exception as exc:
            log_debug(f"Fallback GPT falhou: {exc}", nivel="ERRO")

    raise RuntimeError("Nenhum mecanismo de busca por site disponível.")


def _executar_busca_site(url_site: str) -> None:
    url_site = str(url_site or "").strip()
    if not url_site:
        st.error("Informe a URL do fornecedor ou da categoria.")
        return

    if st.session_state.get("site_busca_em_execucao"):
        st.warning("Já existe uma busca em andamento.")
        return

    _forcar_http_first_execucao()

    st.session_state["site_busca_em_execucao"] = True
    st.session_state["site_busca_ultimo_status"] = "executando"
    st.session_state["site_busca_resumo_texto"] = "Executando busca HTTP-first..."
    st.session_state["site_busca_fonte_descoberta"] = "http_hybrid"

    try:
        df_site = _chamar_busca_site_compativel(url_site)
        df_site = _normalizar_df_saida_site(df_site)

        if not isinstance(df_site, pd.DataFrame) or df_site.empty:
            _carimbar_execucao_site(0, url_site, "vazio")
            st.session_state["site_busca_resumo_texto"] = "Busca concluída sem produtos válidos."
            st.warning("Nenhum produto válido encontrado.")
            return

        st.session_state["df_origem"] = df_site
        st.session_state["origem_upload_tipo"] = "site_gpt"
        st.session_state["origem_upload_nome"] = f"site_{url_site}"
        st.session_state["origem_upload_ext"] = "site_gpt"

        total = int(len(df_site))
        _carimbar_execucao_site(total, url_site, "sucesso")
        st.session_state["site_busca_resumo_texto"] = f"Busca concluída com {total} produto(s)."
        st.session_state["site_busca_fonte_descoberta"] = "http_hybrid"
        st.success(f"{total} produto(s) encontrados.")
    except Exception as exc:
        _carimbar_execucao_site(0, url_site, "erro")
        st.session_state["site_busca_resumo_texto"] = f"Falha na busca: {exc}"
        st.error(f"Falha ao executar busca: {exc}")
        log_debug(f"Falha ao executar busca por site: {exc}", nivel="ERRO")
    finally:
        st.session_state["site_busca_em_execucao"] = False


def _render_status(url_site: str) -> None:
    auth_state = _safe_auth_state()
    profile = _safe_profile(url_site)

    provider_name = str(
        auth_state.get("provider_name", "")
        or st.session_state.get("site_fornecedor_nome_manual", "")
        or profile.get("nome", "")
        or "-"
    )
    auth_mode = str(
        auth_state.get("auth_mode", "")
        or st.session_state.get("site_fornecedor_auth_mode", "")
        or profile.get("auth_mode", "")
        or "public"
    )
    login_url = str(
        auth_state.get("login_url", "")
        or st.session_state.get("site_fornecedor_login_url", "")
        or profile.get("login_url", "")
        or ""
    )
    products_url = str(
        auth_state.get("products_url", "")
        or st.session_state.get("site_fornecedor_products_url", "")
        or profile.get("products_url", "")
        or ""
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Fornecedor", provider_name)
    with c2:
        st.metric("Modo", auth_mode)
    with c3:
        st.metric("Sessão", "Pronta" if bool(auth_state.get("session_ready", False)) else "Pendente")

    if login_url or products_url:
        with st.expander("Dados do acesso", expanded=False):
            if login_url:
                st.write(f"**Login:** {login_url}")
            if products_url:
                st.write(f"**Área de produtos:** {products_url}")

    msg = str(auth_state.get("last_message", "") or "").strip()
    if msg:
        st.caption(msg)


def _render_resumo_busca() -> None:
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Status", str(st.session_state.get("site_busca_ultimo_status", "inativo") or "inativo").title())
    with c2:
        st.metric("Produtos", int(st.session_state.get("site_busca_ultimo_total", 0) or 0))
    with c3:
        st.metric("Última URL", "OK" if st.session_state.get("site_busca_ultima_url") else "-")

    resumo = str(st.session_state.get("site_busca_resumo_texto", "") or "").strip()
    if resumo:
        st.caption(resumo)


def _render_diagnostico() -> None:
    df_diag = st.session_state.get("site_busca_diagnostico_df")
    if not isinstance(df_diag, pd.DataFrame):
        return

    with st.expander("Diagnóstico da busca", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Descobertos", int(st.session_state.get("site_busca_diagnostico_total_descobertos", 0) or 0))
        with c2:
            st.metric("Válidos", int(st.session_state.get("site_busca_diagnostico_total_validos", 0) or 0))
        with c3:
            st.metric("Rejeitados", int(st.session_state.get("site_busca_diagnostico_total_rejeitados", 0) or 0))

        if df_diag.empty:
            st.info("Sem linhas de diagnóstico.")
        else:
            st.dataframe(df_diag.head(100), use_container_width=True)


def _render_modo_fornecedor(possui_fornecedores: bool) -> str:
    opcoes = [MODO_FORNECEDOR_SALVO, MODO_NOVA_URL]

    _aplicar_modo_fornecedor_forcado()

    if "site_modo_fornecedor" not in st.session_state:
        st.session_state["site_modo_fornecedor"] = MODO_FORNECEDOR_SALVO if possui_fornecedores else MODO_NOVA_URL

    if not possui_fornecedores:
        st.session_state["site_modo_fornecedor"] = MODO_NOVA_URL

    modo_anterior = _clean_text(st.session_state.get("site_modo_fornecedor_atual"))
    modo = st.radio(
        "Como deseja selecionar o fornecedor?",
        opcoes,
        horizontal=True,
        key="site_modo_fornecedor",
    )

    if modo != modo_anterior:
        st.session_state["site_modo_fornecedor_atual"] = modo
        _resetar_estado_busca_ao_trocar_fornecedor()

    return modo


def _render_select_fornecedor_salvo() -> str:
    fornecedores = _carregar_fornecedores_mixados()

    valores = [item["slug"] for item in fornecedores]
    labels = {
        item["slug"]: (
            f"{item['nome']} ({'salvo' if item.get('origem') == 'salvo' else 'preset'})"
        )
        for item in fornecedores
    }

    valores.append(OPCAO_NOVO_FORNECEDOR)
    labels[OPCAO_NOVO_FORNECEDOR] = "Outro fornecedor / inserir URL manualmente"

    valor_atual = _clean_text(st.session_state.get("site_fornecedor_salvo_slug"))
    if valor_atual not in valores:
        valor_atual = valores[0] if fornecedores else OPCAO_NOVO_FORNECEDOR
        st.session_state["site_fornecedor_salvo_slug"] = valor_atual

    escolhido = st.selectbox(
        "Fornecedor",
        options=valores,
        index=valores.index(valor_atual),
        format_func=lambda x: labels.get(x, x),
        key="site_fornecedor_salvo_slug",
    )

    if st.session_state.get("site_fornecedor_salvo_slug_aplicado") != escolhido:
        st.session_state["site_fornecedor_salvo_slug_aplicado"] = escolhido
        _resetar_estado_busca_ao_trocar_fornecedor()

        if escolhido != OPCAO_NOVO_FORNECEDOR:
            fornecedor = next((f for f in fornecedores if f["slug"] == escolhido), None)
            _aplicar_fornecedor_na_tela(fornecedor)

    if escolhido == OPCAO_NOVO_FORNECEDOR:
        _forcar_modo_fornecedor(MODO_NOVA_URL)
        return MODO_NOVA_URL

    fornecedor = next((f for f in fornecedores if f["slug"] == escolhido), None)

    if fornecedor:
        with st.expander("Detalhes do fornecedor selecionado", expanded=False):
            st.write(f"**URL base:** {fornecedor.get('url_base', '-')}")
            if fornecedor.get("login_url"):
                st.write(f"**Login:** {fornecedor.get('login_url')}")
            if fornecedor.get("products_url"):
                st.write(f"**Área de produtos:** {fornecedor.get('products_url')}")
            if fornecedor.get("auth_mode"):
                st.write(f"**Modo de acesso:** {fornecedor.get('auth_mode')}")
            if fornecedor.get("observacoes"):
                st.caption(str(fornecedor.get("observacoes", "") or "").strip())

        if fornecedor.get("origem") == "salvo" and delete_site_supplier is not None:
            if st.button("Excluir fornecedor salvo", use_container_width=True, key="btn_excluir_fornecedor_salvo"):
                try:
                    ok = delete_site_supplier(fornecedor.get("slug", ""))
                    if ok:
                        st.success("Fornecedor removido com sucesso.")
                        st.session_state["site_fornecedor_salvo_slug"] = ""
                        st.session_state["site_fornecedor_salvo_slug_aplicado"] = ""
                        _forcar_modo_fornecedor(MODO_NOVA_URL)
                        _resetar_estado_busca_ao_trocar_fornecedor()
                        st.rerun()
                    else:
                        st.error("Não foi possível remover o fornecedor.")
                except Exception as exc:
                    st.error(f"Falha ao remover fornecedor: {exc}")

    return MODO_FORNECEDOR_SALVO


def _render_campos_fornecedor_manual() -> None:
    valor_nome = _clean_text(st.session_state.get("site_fornecedor_nome_manual"))
    valor_url = _clean_text(st.session_state.get("site_fornecedor_url"))
    valor_login = _clean_text(st.session_state.get("site_fornecedor_login_url"))
    valor_products = _clean_text(st.session_state.get("site_fornecedor_products_url"))
    valor_auth_mode = _clean_text(st.session_state.get("site_fornecedor_auth_mode"))
    valor_obs = _clean_text(st.session_state.get("site_fornecedor_observacoes"))

    st.text_input(
        "Nome do fornecedor",
        value=valor_nome,
        key="site_fornecedor_nome_manual",
        placeholder="Ex.: Fornecedor ABC",
    )

    st.text_input(
        "URL do fornecedor ou categoria",
        value=valor_url,
        key="site_fornecedor_url",
        placeholder="https://www.fornecedor.com.br/categoria",
    )

    with st.expander("Detalhes opcionais do fornecedor", expanded=False):
        st.text_input(
            "URL de login",
            value=valor_login,
            key="site_fornecedor_login_url",
            placeholder="https://www.fornecedor.com.br/login",
        )
        st.text_input(
            "URL da área de produtos",
            value=valor_products,
            key="site_fornecedor_products_url",
            placeholder="https://www.fornecedor.com.br/produtos",
        )
        st.text_input(
            "Modo de acesso",
            value=valor_auth_mode,
            key="site_fornecedor_auth_mode",
            placeholder="Ex.: public, login, whatsapp_code",
        )
        st.text_area(
            "Observações",
            value=valor_obs,
            key="site_fornecedor_observacoes",
            height=90,
            placeholder="Informações úteis sobre esse fornecedor.",
        )


def _obter_url_ativa() -> str:
    return _clean_text(st.session_state.get("site_fornecedor_url"))


def _salvar_fornecedor_manual() -> None:
    if upsert_site_supplier is None:
        st.error("Módulo de fornecedores salvos indisponível.")
        return

    nome = _clean_text(st.session_state.get("site_fornecedor_nome_manual"))
    url_base = _clean_text(st.session_state.get("site_fornecedor_url"))
    login_url = _clean_text(st.session_state.get("site_fornecedor_login_url"))
    products_url = _clean_text(st.session_state.get("site_fornecedor_products_url"))
    auth_mode = _clean_text(st.session_state.get("site_fornecedor_auth_mode"))
    observacoes = _clean_text(st.session_state.get("site_fornecedor_observacoes"))

    if not url_base:
        st.error("Informe a URL base antes de salvar.")
        return

    if not nome:
        st.error("Informe o nome do fornecedor antes de salvar.")
        return

    try:
        fornecedor = upsert_site_supplier(
            nome=nome,
            url_base=url_base,
            login_url=login_url,
            products_url=products_url,
            auth_mode=auth_mode,
            observacoes=observacoes,
        )
        st.session_state["site_fornecedor_salvo_slug"] = fornecedor.get("slug", "")
        st.session_state["site_fornecedor_salvo_slug_aplicado"] = ""
        st.session_state["site_fornecedor_slug"] = fornecedor.get("slug", "")
        _forcar_modo_fornecedor(MODO_FORNECEDOR_SALVO)
        st.success("Fornecedor salvo com sucesso.")
        st.rerun()
    except Exception as exc:
        st.error(f"Falha ao salvar fornecedor: {exc}")


def _render_bloco_acao(modo: str, url_site: str) -> None:
    em_execucao = bool(st.session_state.get("site_busca_em_execucao", False))
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button(
            "Inspecionar",
            use_container_width=True,
            key="btn_inspecionar_site_origem",
            disabled=em_execucao,
        ):
            if not url_site:
                st.error("Informe ou selecione uma URL antes de inspecionar.")
            else:
                data = _inspecionar_site(url_site)
                if data:
                    st.success("Inspeção concluída.")
                    st.rerun()

    with col2:
        if st.button(
            "Buscar produtos",
            use_container_width=True,
            key="btn_buscar_site_origem",
            disabled=em_execucao,
        ):
            url_site = str(st.session_state.get("site_fornecedor_url", "")).strip()
            log_debug(f"[CLICK] Botão buscar acionado | URL: {url_site}")

            if not url_site:
                st.error("Informe a URL antes de buscar.")
            else:
                with st.spinner("Executando varredura do site..."):
                    _executar_busca_site(url_site)

    with col3:
        if modo == MODO_NOVA_URL:
            if st.button(
                "Salvar fornecedor",
                use_container_width=True,
                key="btn_salvar_fornecedor_site",
                disabled=em_execucao,
            ):
                _salvar_fornecedor_manual()
        else:
            if st.button(
                "Limpar busca",
                use_container_width=True,
                key="btn_limpar_busca_site",
                disabled=em_execucao,
            ):
                _resetar_estado_busca_ao_trocar_fornecedor()
                st.info("Busca por site limpa.")
                st.rerun()


def render_origem_site_panel() -> None:
    _forcar_http_first_execucao()

    with st.container(border=True):
        # sem título duplicado aqui
        st.caption("Selecione um fornecedor salvo, um fornecedor sugerido, ou informe uma nova URL para buscar os produtos.")

        fornecedores_mixados = _carregar_fornecedores_mixados()
        possui_fornecedores = bool(fornecedores_mixados)

        modo = _render_modo_fornecedor(possui_fornecedores)

        if modo == MODO_FORNECEDOR_SALVO:
            modo_efetivo = _render_select_fornecedor_salvo()
            if modo_efetivo == MODO_NOVA_URL:
                modo = MODO_NOVA_URL
                _render_campos_fornecedor_manual()
        else:
            _render_campos_fornecedor_manual()

        url_site = _obter_url_ativa()

        if modo == MODO_NOVA_URL and url_site:
            st.session_state["site_fornecedor_slug"] = _clean_text(
                st.session_state.get("site_fornecedor_slug")
            )

        _render_bloco_acao(modo, url_site)

        if url_site:
            _render_status(url_site)

        _render_resumo_busca()

        df_origem = st.session_state.get("df_origem")
        if isinstance(df_origem, pd.DataFrame):
            _preview_dataframe(df_origem, "Preview da busca por site")

        _render_diagnostico()
