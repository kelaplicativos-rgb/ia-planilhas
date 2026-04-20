
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


# ============================================================
# CONFIG
# ============================================================

OUTPUT_DIR = Path("bling_app_zero/output")
SESSIONS_DIR = OUTPUT_DIR / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

STATUS_SESSAO_PUBLICA = "publico"
STATUS_SESSAO_PRONTA = "session_ready"
STATUS_LOGIN_REQUERIDO = "login_required"
STATUS_LOGIN_CAPTCHA_DETECTADO = "login_captcha_detectado"
STATUS_SESSAO_INVALIDA = "session_invalid"
STATUS_SESSAO_AUSENTE = "session_missing"
STATUS_ERRO = "erro"


# ============================================================
# HELPERS BASE
# ============================================================

def safe_str(value: Any) -> str:
    return str(value or "").strip()


def _log_debug(msg: str, nivel: str = "INFO") -> None:
    try:
        from bling_app_zero.ui.app_helpers import log_debug  # type: ignore

        log_debug(msg, nivel=nivel)
    except Exception:
        pass


def _streamlit():
    try:
        import streamlit as st

        return st
    except Exception:
        return None


def normalizar_url(url: str) -> str:
    url = safe_str(url)
    if not url:
        return ""

    if not re.match(r"^https?://", url, flags=re.IGNORECASE):
        url = f"https://{url}"

    return url.strip()


def _slugify(value: str) -> str:
    value = safe_str(value).lower()
    value = re.sub(r"^https?://", "", value)
    value = value.replace("www.", "")
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "fornecedor"


def inferir_fornecedor_slug(base_url: str, fornecedor: str = "") -> str:
    fornecedor = safe_str(fornecedor)
    if fornecedor:
        return _slugify(fornecedor)

    url = normalizar_url(base_url)
    if not url:
        return "fornecedor"

    try:
        host = urlparse(url).netloc or url
    except Exception:
        host = url

    return _slugify(host)


def _session_paths(base_url: str, fornecedor: str = "") -> dict[str, Path]:
    slug = inferir_fornecedor_slug(base_url=base_url, fornecedor=fornecedor)
    pasta = SESSIONS_DIR / slug
    pasta.mkdir(parents=True, exist_ok=True)

    return {
        "dir": pasta,
        "storage_state": pasta / "storage_state.json",
        "metadata": pasta / "metadata.json",
        "cookies": pasta / "cookies.json",
    }


def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        _log_debug(f"Falha ao ler JSON: {path} | erro={exc}", nivel="ERRO")
    return default


def _write_json(path: Path, data: Any) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return True
    except Exception as exc:
        _log_debug(f"Falha ao gravar JSON: {path} | erro={exc}", nivel="ERRO")
        return False


# ============================================================
# DETECÇÃO DE LOGIN / CAPTCHA
# ============================================================

def detectar_login_captcha(html: str, url_atual: str = "") -> dict[str, Any]:
    html_n = safe_str(html).lower()
    url_n = safe_str(url_atual).lower()

    if not html_n and not url_n:
        return {
            "exige_login": False,
            "captcha_detectado": False,
            "status": STATUS_SESSAO_PUBLICA,
            "motivos": [],
        }

    sinais_login = [
        "fazer login",
        "faça login",
        "entrar",
        "acessar conta",
        "minha conta",
        "identifique-se",
        "autenticação",
        "autenticacao",
        "login",
        "senha",
        "e-mail",
        "email",
        "cpf",
        "cnpj",
    ]

    sinais_captcha = [
        "captcha",
        "g-recaptcha",
        "grecaptcha",
        "hcaptcha",
        "cf-chl",
        "cloudflare",
        "challenge-platform",
        "verify you are human",
        "verifique se você é humano",
        "verifique se voce e humano",
        "não sou um robô",
        "nao sou um robo",
    ]

    url_sugere_login = any(
        token in url_n
        for token in [
            "/login",
            "/entrar",
            "/conta",
            "/account",
            "/auth",
            "/autenticacao",
            "/autenticacao",
            "customer/account/login",
        ]
    )

    html_sugere_login = any(token in html_n for token in sinais_login)
    captcha_detectado = any(token in html_n for token in sinais_captcha)

    motivos: list[str] = []
    if url_sugere_login:
        motivos.append("url_login")
    if html_sugere_login:
        motivos.append("html_login")
    if captcha_detectado:
        motivos.append("captcha")

    exige_login = url_sugere_login or html_sugere_login

    if exige_login and captcha_detectado:
        status = STATUS_LOGIN_CAPTCHA_DETECTADO
    elif exige_login:
        status = STATUS_LOGIN_REQUERIDO
    else:
        status = STATUS_SESSAO_PUBLICA

    return {
        "exige_login": exige_login,
        "captcha_detectado": captcha_detectado,
        "status": status,
        "motivos": motivos,
    }


# ============================================================
# STORAGE STATE / AUTH CONTEXT
# ============================================================

@dataclass
class SessionSnapshot:
    fornecedor_slug: str
    base_url: str
    storage_state_path: str
    metadata_path: str
    existe_storage_state: bool
    session_ready: bool
    status: str
    products_url: str
    cookies_count: int
    headers: dict[str, str]
    cookies: list[dict[str, Any]]
    metadata: dict[str, Any]

    def to_auth_context(self) -> dict[str, Any]:
        return {
            "session_ready": self.session_ready,
            "status": self.status,
            "base_url": self.base_url,
            "products_url": self.products_url,
            "storage_state_path": self.storage_state_path,
            "metadata_path": self.metadata_path,
            "headers": self.headers,
            "cookies": self.cookies,
            "fornecedor_slug": self.fornecedor_slug,
            "metadata": self.metadata,
        }


def extrair_cookies_do_storage_state(storage_state: dict[str, Any]) -> list[dict[str, Any]]:
    cookies = storage_state.get("cookies", [])
    if not isinstance(cookies, list):
        return []

    saida: list[dict[str, Any]] = []
    for item in cookies:
        if not isinstance(item, dict):
            continue

        nome = safe_str(item.get("name"))
        valor = safe_str(item.get("value"))
        if not nome:
            continue

        saida.append(
            {
                "name": nome,
                "value": valor,
                "domain": safe_str(item.get("domain")),
                "path": safe_str(item.get("path")) or "/",
                "expires": item.get("expires"),
                "httpOnly": bool(item.get("httpOnly", False)),
                "secure": bool(item.get("secure", False)),
                "sameSite": safe_str(item.get("sameSite")),
            }
        )

    return saida


def headers_padrao_sessao() -> dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }


def salvar_storage_state(
    *,
    base_url: str,
    storage_state: dict[str, Any],
    fornecedor: str = "",
    products_url: str = "",
    login_url: str = "",
    status: str = STATUS_SESSAO_PRONTA,
    observacao: str = "",
) -> dict[str, Any]:
    base_url = normalizar_url(base_url)
    paths = _session_paths(base_url=base_url, fornecedor=fornecedor)

    cookies = extrair_cookies_do_storage_state(storage_state)
    agora = int(time.time())

    metadata = {
        "base_url": base_url,
        "fornecedor_slug": inferir_fornecedor_slug(base_url=base_url, fornecedor=fornecedor),
        "products_url": normalizar_url(products_url) or base_url,
        "login_url": normalizar_url(login_url),
        "status": safe_str(status) or STATUS_SESSAO_PRONTA,
        "observacao": safe_str(observacao),
        "updated_at": agora,
        "cookies_count": len(cookies),
        "session_ready": bool(cookies),
    }

    ok_state = _write_json(paths["storage_state"], storage_state)
    ok_meta = _write_json(paths["metadata"], metadata)
    ok_cookies = _write_json(paths["cookies"], cookies)

    if ok_state and ok_meta and ok_cookies:
        _log_debug(
            f"Sessão salva com sucesso | fornecedor={metadata['fornecedor_slug']} | cookies={len(cookies)}",
            nivel="INFO",
        )
    else:
        _log_debug(
            f"Falha parcial ao salvar sessão | fornecedor={metadata['fornecedor_slug']}",
            nivel="ERRO",
        )

    return {
        "ok": bool(ok_state and ok_meta and ok_cookies),
        "storage_state_path": str(paths["storage_state"]),
        "metadata_path": str(paths["metadata"]),
        "cookies_path": str(paths["cookies"]),
        "metadata": metadata,
    }


def carregar_storage_state(base_url: str, fornecedor: str = "") -> dict[str, Any]:
    base_url = normalizar_url(base_url)
    paths = _session_paths(base_url=base_url, fornecedor=fornecedor)
    return _read_json(paths["storage_state"], {})


def carregar_session_snapshot(
    *,
    base_url: str,
    fornecedor: str = "",
) -> SessionSnapshot:
    base_url = normalizar_url(base_url)
    paths = _session_paths(base_url=base_url, fornecedor=fornecedor)

    storage_state = _read_json(paths["storage_state"], {})
    metadata = _read_json(paths["metadata"], {})
    cookies = extrair_cookies_do_storage_state(storage_state)

    session_ready = bool(paths["storage_state"].exists() and cookies)
    status = safe_str(metadata.get("status"))

    if not paths["storage_state"].exists():
        status = STATUS_SESSAO_AUSENTE
    elif not cookies:
        status = STATUS_SESSAO_INVALIDA
    elif not status:
        status = STATUS_SESSAO_PRONTA

    return SessionSnapshot(
        fornecedor_slug=inferir_fornecedor_slug(base_url=base_url, fornecedor=fornecedor),
        base_url=base_url,
        storage_state_path=str(paths["storage_state"]),
        metadata_path=str(paths["metadata"]),
        existe_storage_state=paths["storage_state"].exists(),
        session_ready=session_ready,
        status=status,
        products_url=normalizar_url(metadata.get("products_url")) or base_url,
        cookies_count=len(cookies),
        headers=headers_padrao_sessao(),
        cookies=cookies,
        metadata=metadata if isinstance(metadata, dict) else {},
    )


def montar_auth_context(base_url: str, fornecedor: str = "") -> dict[str, Any]:
    snapshot = carregar_session_snapshot(base_url=base_url, fornecedor=fornecedor)
    return snapshot.to_auth_context()


def sessao_esta_pronta(base_url: str, fornecedor: str = "") -> bool:
    snapshot = carregar_session_snapshot(base_url=base_url, fornecedor=fornecedor)
    return bool(snapshot.session_ready)


def limpar_sessao(base_url: str, fornecedor: str = "") -> dict[str, Any]:
    base_url = normalizar_url(base_url)
    paths = _session_paths(base_url=base_url, fornecedor=fornecedor)

    removidos: list[str] = []
    for chave in ("storage_state", "metadata", "cookies"):
        path = paths[chave]
        try:
            if path.exists():
                path.unlink()
                removidos.append(str(path))
        except Exception as exc:
            _log_debug(f"Falha ao remover arquivo de sessão: {path} | erro={exc}", nivel="ERRO")

    return {
        "ok": True,
        "removidos": removidos,
        "fornecedor_slug": inferir_fornecedor_slug(base_url=base_url, fornecedor=fornecedor),
    }


# ============================================================
# PLAYWRIGHT
# ============================================================

def playwright_disponivel() -> bool:
    try:
        import playwright  # noqa: F401

        return True
    except Exception:
        return False


def iniciar_login_assistido(
    *,
    base_url: str,
    fornecedor: str = "",
    login_url: str = "",
    products_url: str = "",
    timeout_ms: int = 300000,
    headless: bool = False,
) -> dict[str, Any]:
    """
    Abre um navegador visível para o usuário fazer login manualmente e salvar a sessão.
    Uso ideal:
    - detectar login/captcha
    - chamar esta função
    - usuário autentica manualmente
    - sistema salva storage_state para reutilizar depois
    """
    base_url = normalizar_url(base_url)
    login_url = normalizar_url(login_url) or base_url
    products_url = normalizar_url(products_url) or base_url

    if not playwright_disponivel():
        return {
            "ok": False,
            "status": STATUS_ERRO,
            "mensagem": (
                "Playwright não está disponível no ambiente. "
                "Instale playwright e os browsers necessários antes de usar login assistido."
            ),
        }

    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return {
            "ok": False,
            "status": STATUS_ERRO,
            "mensagem": f"Falha ao importar Playwright: {exc}",
        }

    st = _streamlit()
    info_box = None
    if st is not None:
        info_box = st.empty()
        info_box.info(
            "🔐 Abrindo navegador para login assistido. "
            "Faça login manualmente, resolva o captcha e aguarde a captura da sessão."
        )

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context()
            page = context.new_page()
            page.goto(login_url, wait_until="domcontentloaded", timeout=timeout_ms)

            if st is not None and info_box is not None:
                info_box.warning(
                    "Navegador aberto. Após concluir o login e entrar na área logada do fornecedor, "
                    "volte ao app e aguarde a persistência da sessão."
                )

            # Espera curta inicial para dar tempo de renderizar a página.
            time.sleep(3)

            # Tenta ir para a área de produtos, caso já esteja logado.
            try:
                page.goto(products_url, wait_until="domcontentloaded", timeout=timeout_ms)
            except Exception:
                pass

            # Janela de observação para o usuário concluir login/captcha.
            inicio = time.time()
            ultimo_status = ""
            while (time.time() - inicio) * 1000 < timeout_ms:
                try:
                    html = page.content()
                    url_atual = page.url
                except Exception:
                    html = ""
                    url_atual = ""

                analise = detectar_login_captcha(html=html, url_atual=url_atual)

                # Sessão pronta quando deixou a tela de login/captcha e já tem cookies.
                cookies = context.cookies()
                tem_cookies = bool(cookies)

                if tem_cookies and not analise["exige_login"] and not analise["captcha_detectado"]:
                    storage_state = context.storage_state()
                    salvo = salvar_storage_state(
                        base_url=base_url,
                        fornecedor=fornecedor,
                        products_url=products_url,
                        login_url=login_url,
                        storage_state=storage_state,
                        status=STATUS_SESSAO_PRONTA,
                        observacao="Sessão capturada por login assistido com Playwright.",
                    )
                    browser.close()

                    if st is not None and info_box is not None:
                        info_box.success("✅ Sessão autenticada salva com sucesso.")

                    return {
                        "ok": True,
                        "status": STATUS_SESSAO_PRONTA,
                        "mensagem": "Sessão autenticada salva com sucesso.",
                        "storage": salvo,
                        "url_final": url_atual,
                        "cookies_count": len(cookies),
                    }

                status_atual = analise["status"]
                if status_atual != ultimo_status:
                    _log_debug(
                        f"Login assistido em andamento | fornecedor={inferir_fornecedor_slug(base_url, fornecedor)} "
                        f"| status={status_atual} | url={url_atual}",
                        nivel="INFO",
                    )
                    ultimo_status = status_atual

                time.sleep(2)

            # Timeout
            try:
                storage_state = context.storage_state()
                cookies = context.cookies()
                if cookies:
                    salvo = salvar_storage_state(
                        base_url=base_url,
                        fornecedor=fornecedor,
                        products_url=products_url,
                        login_url=login_url,
                        storage_state=storage_state,
                        status=STATUS_SESSAO_PRONTA,
                        observacao="Sessão salva ao final do timeout do login assistido.",
                    )
                    browser.close()
                    return {
                        "ok": True,
                        "status": STATUS_SESSAO_PRONTA,
                        "mensagem": "Sessão salva ao final da espera do login assistido.",
                        "storage": salvo,
                        "cookies_count": len(cookies),
                    }
            except Exception:
                pass

            browser.close()
            return {
                "ok": False,
                "status": STATUS_LOGIN_CAPTCHA_DETECTADO,
                "mensagem": (
                    "O navegador foi encerrado sem captura válida de sessão. "
                    "Faça login completo e resolva o captcha antes de encerrar."
                ),
            }

    except PlaywrightTimeoutError:
        return {
            "ok": False,
            "status": STATUS_ERRO,
            "mensagem": "Tempo excedido durante o login assistido.",
        }
    except Exception as exc:
        _log_debug(f"Falha no login assistido | erro={exc}", nivel="ERRO")
        return {
            "ok": False,
            "status": STATUS_ERRO,
            "mensagem": f"Falha no login assistido: {exc}",
        }


# ============================================================
# UI / SESSION STATE
# ============================================================

def salvar_status_login_em_sessao(
    *,
    base_url: str,
    status: str,
    mensagem: str = "",
    exige_login: bool = False,
    captcha_detectado: bool = False,
    fornecedor: str = "",
) -> None:
    st = _streamlit()
    if st is None:
        return

    slug = inferir_fornecedor_slug(base_url=base_url, fornecedor=fornecedor)

    st.session_state["site_login_status"] = {
        "fornecedor_slug": slug,
        "base_url": normalizar_url(base_url),
        "status": safe_str(status),
        "mensagem": safe_str(mensagem),
        "exige_login": bool(exige_login),
        "captcha_detectado": bool(captcha_detectado),
        "session_ready": sessao_esta_pronta(base_url=base_url, fornecedor=fornecedor),
        "auth_context": montar_auth_context(base_url=base_url, fornecedor=fornecedor),
    }


def detectar_e_salvar_status_login(
    *,
    base_url: str,
    html: str,
    url_atual: str = "",
    mensagem_extra: str = "",
    fornecedor: str = "",
) -> dict[str, Any]:
    analise = detectar_login_captcha(html=html, url_atual=url_atual)

    mensagem = ""
    if analise["status"] == STATUS_LOGIN_CAPTCHA_DETECTADO:
        mensagem = "Fornecedor com login detectado e indício de captcha. Fluxo autenticado necessário."
    elif analise["status"] == STATUS_LOGIN_REQUERIDO:
        mensagem = "Fornecedor exige autenticação antes da captura dos produtos."
    elif analise["status"] == STATUS_SESSAO_PUBLICA:
        mensagem = "Acesso público detectado. Fluxo autenticado não é necessário neste momento."

    if mensagem_extra:
        mensagem = f"{mensagem} {safe_str(mensagem_extra)}".strip()

    salvar_status_login_em_sessao(
        base_url=base_url,
        fornecedor=fornecedor,
        status=analise["status"],
        mensagem=mensagem,
        exige_login=bool(analise["exige_login"]),
        captcha_detectado=bool(analise["captcha_detectado"]),
    )

    return {
        **analise,
        "mensagem": mensagem,
        "auth_context": montar_auth_context(base_url=base_url, fornecedor=fornecedor),
    }


def obter_status_login_da_sessao() -> dict[str, Any]:
    st = _streamlit()
    if st is None:
        return {}
    valor = st.session_state.get("site_login_status", {})
    return valor if isinstance(valor, dict) else {}
