from __future__ import annotations

import inspect
from typing import Any, Dict

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

from bling_app_zero.ui.app_helpers import log_debug


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
    ]:
        st.session_state.pop(chave, None)


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
        provider_slug = str(contexto.get("provider_slug", "") or profile.get("slug", "") or "").strip()
        products_url = str(contexto.get("products_url", "") or profile.get("products_url", "") or url_site).strip()

        contexto["fornecedor_slug"] = provider_slug
        contexto["products_url"] = products_url
        return contexto
    except Exception as exc:
        log_debug(f"Falha ao montar auth_context: {exc}", nivel="ERRO")
        return None


def _chamar_busca_site_compativel(url_site: str) -> pd.DataFrame:
    auth_context = _auth_context_para_busca(url_site)

    if buscar_produtos_site_com_gpt is not None:
        try:
            kwargs = {
                "base_url": url_site,
                "diagnostico": True,
                "auth_context": auth_context,
                "limite_links": 500,
            }

            try:
                assinatura = inspect.signature(buscar_produtos_site_com_gpt)
                parametros = assinatura.parameters
                if "termo" in parametros:
                    kwargs["termo"] = ""
            except Exception:
                pass

            resultado = buscar_produtos_site_com_gpt(**kwargs)
            if isinstance(resultado, pd.DataFrame):
                return _normalizar_df_saida_site(resultado)
            if isinstance(resultado, list):
                return _normalizar_df_saida_site(pd.DataFrame(resultado))
        except Exception as exc:
            log_debug(f"Fallback GPT falhou: {exc}", nivel="ERRO")

    if SiteAgent is not None:
        try:
            agent = SiteAgent()
            resultado = agent.buscar_dataframe(
                base_url=url_site,
                diagnostico=True,
                auth_context=auth_context,
                limite=500,
            )
            if isinstance(resultado, pd.DataFrame):
                return _normalizar_df_saida_site(resultado)
            if isinstance(resultado, list):
                return _normalizar_df_saida_site(pd.DataFrame(resultado))
        except Exception as exc:
            log_debug(f"Fallback SiteAgent falhou: {exc}", nivel="ERRO")

    raise RuntimeError("Nenhum mecanismo de busca por site disponível.")


def _executar_busca_site(url_site: str) -> None:
    url_site = str(url_site or "").strip()
    if not url_site:
        st.error("Informe a URL do fornecedor ou da categoria.")
        return

    st.session_state["site_busca_em_execucao"] = True
    st.session_state["site_busca_ultimo_status"] = "executando"
    st.session_state["site_busca_resumo_texto"] = "Executando busca..."
    st.session_state["site_busca_fonte_descoberta"] = ""

    try:
        df_site = _chamar_busca_site_compativel(url_site)
        df_site = _normalizar_df_saida_site(df_site)

        if not isinstance(df_site, pd.DataFrame) or df_site.empty:
            _carimbar_execucao_site(0, url_site, "vazio")
            st.session_state["site_busca_em_execucao"] = False
            st.session_state["site_busca_resumo_texto"] = "Busca concluída sem produtos válidos."
            st.warning("Nenhum produto válido encontrado.")
            return

        st.session_state["df_origem"] = df_site
        st.session_state["origem_upload_tipo"] = "site_gpt"
        st.session_state["origem_upload_nome"] = f"site_{url_site}"
        st.session_state["origem_upload_ext"] = "site_gpt"

        total = int(len(df_site))
        _carimbar_execucao_site(total, url_site, "sucesso")
        st.session_state["site_busca_em_execucao"] = False
        st.session_state["site_busca_resumo_texto"] = f"Busca concluída com {total} produto(s)."
        st.success(f"{total} produto(s) encontrados.")
    except Exception as exc:
        st.session_state["site_busca_em_execucao"] = False
        _carimbar_execucao_site(0, url_site, "erro")
        st.session_state["site_busca_resumo_texto"] = f"Falha na busca: {exc}"
        st.error(f"Falha ao executar busca: {exc}")
        log_debug(f"Falha ao executar busca por site: {exc}", nivel="ERRO")


def _render_status(url_site: str) -> None:
    auth_state = _safe_auth_state()
    profile = _safe_profile(url_site)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Fornecedor", str(auth_state.get("provider_name", "") or profile.get("nome", "") or "-"))
    with c2:
        st.metric("Modo", str(auth_state.get("auth_mode", "") or profile.get("auth_mode", "") or "public"))
    with c3:
        st.metric("Sessão", "Pronta" if bool(auth_state.get("session_ready", False)) else "Pendente")

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


def render_origem_site_panel() -> None:
    with st.container(border=True):
        st.markdown("### Buscar no site do fornecedor")
        st.caption("Informe a URL, inspecione o acesso se necessário e execute a busca.")

        if "site_fornecedor_url" not in st.session_state:
            st.session_state["site_fornecedor_url"] = ""

        url_site = st.text_input(
            "URL do fornecedor ou categoria",
            key="site_fornecedor_url",
            placeholder="https://www.fornecedor.com.br/categoria",
        ).strip()

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("Inspecionar", use_container_width=True):
                if not url_site:
                    st.error("Informe a URL antes de inspecionar.")
                else:
                    data = _inspecionar_site(url_site)
                    if data:
                        st.success("Inspeção concluída.")
                        st.rerun()

        with col2:
            if st.button("Buscar produtos", use_container_width=True):
                _executar_busca_site(url_site)
                st.rerun()

        with col3:
            if st.button("Limpar busca", use_container_width=True):
                _resetar_estado_site_ui()
                st.session_state.pop("df_origem", None)
                st.session_state.pop("origem_upload_tipo", None)
                st.session_state.pop("origem_upload_nome", None)
                st.session_state.pop("origem_upload_ext", None)
                st.info("Busca por site limpa.")
                st.rerun()

        _render_status(url_site)
        _render_resumo_busca()

        df_origem = st.session_state.get("df_origem")
        if isinstance(df_origem, pd.DataFrame):
            _preview_dataframe(df_origem, "Preview da busca por site")

        _render_diagnostico()
