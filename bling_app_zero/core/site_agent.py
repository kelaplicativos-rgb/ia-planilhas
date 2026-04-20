
from __future__ import annotations

import concurrent.futures
import re
import threading
from typing import Any

import pandas as pd
import requests


# ============================================================
# IMPORTS BLINDADOS
# ============================================================

try:
    from bling_app_zero.core.site_crawler_cleaners import normalizar_url, safe_str
except Exception:
    def normalizar_url(url: str) -> str:
        return str(url or "").strip()

    def safe_str(value: Any) -> str:
        return str(value or "").strip()


try:
    from bling_app_zero.core.site_crawler_extractors import extrair_detalhes_heuristicos
except Exception:
    extrair_detalhes_heuristicos = None


try:
    from bling_app_zero.core.site_crawler_gpt import gpt_extrair_produto
except Exception:
    gpt_extrair_produto = None


try:
    from bling_app_zero.core.site_crawler_http import fetch_html_retry
except Exception:
    fetch_html_retry = None


try:
    from bling_app_zero.core.site_crawler_links import descobrir_produtos_no_dominio
except Exception:
    descobrir_produtos_no_dominio = None


try:
    from bling_app_zero.core.site_crawler_validators import (
        pontuar_produto,
        produto_final_valido,
        titulo_valido,
    )
except Exception:
    def pontuar_produto(**kwargs) -> int:
        return 0

    def produto_final_valido(item: dict) -> bool:
        return bool(safe_str(item.get("descricao")) and safe_str(item.get("url_produto")))

    def titulo_valido(titulo: str, url_produto: str = "") -> bool:
        return bool(safe_str(titulo))


try:
    from bling_app_zero.core.session_manager import (
        STATUS_LOGIN_CAPTCHA_DETECTADO,
        STATUS_LOGIN_REQUERIDO,
        STATUS_SESSAO_PRONTA,
        detectar_e_salvar_status_login,
        detectar_login_captcha,
        montar_auth_context,
        salvar_status_login_em_sessao,
    )
except Exception:
    STATUS_LOGIN_CAPTCHA_DETECTADO = "login_captcha_detectado"
    STATUS_LOGIN_REQUERIDO = "login_required"
    STATUS_SESSAO_PRONTA = "session_ready"

    def detectar_login_captcha(html: str, url_atual: str = "") -> dict[str, Any]:
        html_n = safe_str(html).lower()
        url_n = safe_str(url_atual).lower()

        sinais_login = [
            "fazer login",
            "faça login",
            "entrar",
            "login",
            "senha",
            "autenticacao",
            "autenticação",
            "minha conta",
        ]
        sinais_captcha = [
            "captcha",
            "g-recaptcha",
            "grecaptcha",
            "hcaptcha",
            "cloudflare",
            "verify you are human",
            "não sou um robô",
            "nao sou um robo",
        ]

        url_sugere_login = any(
            token in url_n
            for token in ["/login", "/entrar", "/conta", "/account", "/auth"]
        )
        html_sugere_login = any(token in html_n for token in sinais_login)
        captcha_detectado = any(token in html_n for token in sinais_captcha)
        exige_login = url_sugere_login or html_sugere_login

        if exige_login and captcha_detectado:
            status = STATUS_LOGIN_CAPTCHA_DETECTADO
        elif exige_login:
            status = STATUS_LOGIN_REQUERIDO
        else:
            status = "publico"

        return {
            "exige_login": exige_login,
            "captcha_detectado": captcha_detectado,
            "status": status,
            "motivos": [],
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
        return {
            **analise,
            "mensagem": mensagem_extra,
            "auth_context": {},
        }

    def montar_auth_context(base_url: str, fornecedor: str = "") -> dict[str, Any]:
        return {}

    def salvar_status_login_em_sessao(
        *,
        base_url: str,
        status: str,
        mensagem: str = "",
        exige_login: bool = False,
        captcha_detectado: bool = False,
        fornecedor: str = "",
    ) -> None:
        return None


# ============================================================
# HELPERS GERAIS
# ============================================================

def _streamlit_ctx():
    try:
        import streamlit as st
        return st
    except Exception:
        return None


def _em_thread_secundaria() -> bool:
    return threading.current_thread() is not threading.main_thread()


def _log_debug(msg: str, nivel: str = "INFO") -> None:
    """
    Importante:
    - no main thread: usa o log do app normalmente
    - em threads paralelas: NÃO toca em Streamlit/session_state para evitar
      'missing ScriptRunContext'
    """
    if _em_thread_secundaria():
        try:
            print(f"[SITE_AGENT][{nivel}] {msg}")
        except Exception:
            pass
        return

    try:
        from bling_app_zero.ui.app_helpers import log_debug  # type: ignore
        log_debug(msg, nivel=nivel)
    except Exception:
        try:
            print(f"[SITE_AGENT][{nivel}] {msg}")
        except Exception:
            pass


def _limite_tecnico(limite_links: int | None) -> int:
    limite_padrao = 8000

    if not isinstance(limite_links, int):
        return limite_padrao

    if limite_links <= 0:
        return limite_padrao

    return min(max(limite_links, 1), limite_padrao)


def _max_workers(total: int) -> int:
    if total <= 0:
        return 1
    return min(max(total // 20, 4), 12)


def _descricao_curta_padrao(final: dict[str, Any]) -> str:
    descricao_curta = safe_str(final.get("descricao_curta"))
    if descricao_curta:
        return descricao_curta[:120]

    descricao = safe_str(final.get("descricao"))
    if descricao:
        return descricao[:120]

    descricao_detalhada = safe_str(final.get("descricao_detalhada"))
    if descricao_detalhada:
        return descricao_detalhada[:120]

    return ""


def _quantidade_padrao(final: dict[str, Any]) -> str:
    quantidade = safe_str(final.get("quantidade"))
    if quantidade:
        return quantidade

    descricao = safe_str(final.get("descricao_detalhada")).lower()
    if any(
        x in descricao
        for x in ["sem estoque", "indisponível", "indisponivel", "esgotado", "zerado"]
    ):
        return "0"

    return "1"


def _limpar_marca(marca: str, titulo: str = "") -> str:
    marca = safe_str(marca).strip()
    titulo = safe_str(titulo).strip()

    if not marca:
        return ""

    marca_lower = marca.lower()
    titulo_lower = titulo.lower()

    bloqueadas_parciais = [
        "mega center",
        "eletronicos",
        "eletrônicos",
        "minha loja",
        "nossa loja",
        "loja oficial",
        "distribuidora",
        "atacadista",
        "atacado",
        "varejo",
        "store",
        "shop",
        "ecommerce",
        "e-commerce",
    ]

    for termo in bloqueadas_parciais:
        if termo in marca_lower:
            return ""

    genericas = {
        "fone",
        "fones",
        "cabo",
        "cabos",
        "carregador",
        "carregadores",
        "caixa",
        "som",
        "produto",
        "produtos",
        "acessorio",
        "acessório",
        "acessorios",
        "acessórios",
        "eletronico",
        "eletrônico",
        "eletronicos",
        "eletrônicos",
        "bluetooth",
        "usb",
        "usb-c",
        "tipo-c",
        "celular",
        "smartphone",
    }

    if marca_lower in genericas:
        return ""

    if len(marca) > 40:
        return ""

    if marca.isdigit():
        return ""

    if titulo_lower and marca_lower == titulo_lower:
        return ""

    if marca.count(" ") >= 4:
        return ""

    return marca


def _inferir_marca_do_titulo(titulo: str) -> str:
    titulo = safe_str(titulo).strip()
    if not titulo:
        return ""

    palavras_invalidas = {
        "fone",
        "fones",
        "cabo",
        "cabos",
        "carregador",
        "carregadores",
        "caixa",
        "som",
        "produto",
        "kit",
        "para",
        "com",
        "sem",
        "de",
        "da",
        "do",
        "usb",
        "bluetooth",
        "wireless",
        "tipo",
        "celular",
        "smartphone",
    }

    tokens = re.split(r"\s+", titulo)
    for token in tokens[:5]:
        candidato = re.sub(r"[^A-Za-z0-9\-]", "", safe_str(token)).strip()
        if not candidato:
            continue
        if len(candidato) <= 2:
            continue
        if candidato.lower() in palavras_invalidas:
            continue
        if candidato.isdigit():
            continue
        return candidato

    return ""


def _resolver_marca(final: dict[str, Any], heuristica: dict[str, Any]) -> str:
    descricao = safe_str(final.get("descricao")) or safe_str(heuristica.get("descricao"))

    candidatos = [
        safe_str(final.get("marca")),
        safe_str(heuristica.get("marca")),
    ]

    for candidato in candidatos:
        marca_limpa = _limpar_marca(candidato, descricao)
        if marca_limpa:
            return marca_limpa

    marca_titulo = _inferir_marca_do_titulo(descricao)
    return _limpar_marca(marca_titulo, descricao)


def _montar_linha_saida(final: dict) -> dict:
    return {
        "Código": safe_str(final.get("codigo")),
        "Descrição": safe_str(final.get("descricao")),
        "Descrição Curta": _descricao_curta_padrao(final),
        "Categoria": safe_str(final.get("categoria")),
        "Marca": safe_str(final.get("marca")),
        "GTIN": safe_str(final.get("gtin")),
        "NCM": safe_str(final.get("ncm")),
        "Preço de custo": safe_str(final.get("preco")),
        "Quantidade": _quantidade_padrao(final),
        "URL Imagens": safe_str(final.get("url_imagens")),
        "URL Produto": safe_str(final.get("url_produto")),
    }


def _df_saida(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).fillna("")

    if "URL Produto" in df.columns:
        df = df.drop_duplicates(subset=["URL Produto"], keep="first")

    colunas_ordenadas = [
        "Código",
        "Descrição",
        "Descrição Curta",
        "Categoria",
        "Marca",
        "GTIN",
        "NCM",
        "Preço de custo",
        "Quantidade",
        "URL Imagens",
        "URL Produto",
    ]

    for col in colunas_ordenadas:
        if col not in df.columns:
            df[col] = ""

    return df[colunas_ordenadas].reset_index(drop=True)


def _limpar_dict_debug(data: dict[str, Any]) -> dict[str, str]:
    saida: dict[str, str] = {}
    for chave, valor in data.items():
        saida[chave] = safe_str(valor)
    return saida


def _score_produto(item: dict) -> int:
    return pontuar_produto(
        titulo=safe_str(item.get("descricao")),
        preco=safe_str(item.get("preco")),
        codigo=safe_str(item.get("codigo")),
        gtin=safe_str(item.get("gtin")),
        imagens=safe_str(item.get("url_imagens")),
        categoria=safe_str(item.get("categoria")),
        url_produto=safe_str(item.get("url_produto")),
    )


def _campos_criticos_ok(final: dict[str, Any]) -> tuple[bool, list[str]]:
    faltando: list[str] = []

    campos = {
        "codigo": safe_str(final.get("codigo")),
        "descricao": safe_str(final.get("descricao")),
        "descricao_curta": _descricao_curta_padrao(final),
        "quantidade": _quantidade_padrao(final),
        "categoria": safe_str(final.get("categoria")),
        "marca": safe_str(final.get("marca")),
        "url_imagens": safe_str(final.get("url_imagens")),
        "url_produto": safe_str(final.get("url_produto")),
    }

    for chave, valor in campos.items():
        if not valor:
            faltando.append(chave)

    criticos_duros = {"descricao", "url_produto", "url_imagens"}
    if any(campo in faltando for campo in criticos_duros):
        return False, faltando

    return True, faltando


def _motivo_rejeicao(final: dict) -> str:
    descricao = safe_str(final.get("descricao"))
    preco = safe_str(final.get("preco"))
    codigo = safe_str(final.get("codigo"))
    gtin = safe_str(final.get("gtin"))
    imagens = safe_str(final.get("url_imagens"))
    categoria = safe_str(final.get("categoria"))
    marca = safe_str(final.get("marca"))
    quantidade = safe_str(final.get("quantidade"))
    url_produto = safe_str(final.get("url_produto"))

    url_n = url_produto.lower()
    categoria_n = categoria.lower()

    if not descricao:
        return "sem_descricao"

    if not titulo_valido(descricao, url_produto):
        return "titulo_invalido_ou_pagina_institucional"

    if url_n in {"", "/"} or url_n.endswith("/conta") or url_n.endswith("/login"):
        return "url_institucional"

    if any(
        x in url_n
        for x in ["/categoria", "/categorias", "/departamento", "/search", "/busca", "/pagina/"]
    ):
        return "url_de_categoria"

    if categoria_n and all(ch in " 0123456789>-" for ch in categoria_n):
        return "categoria_invalida"

    campos_ok, faltando = _campos_criticos_ok(final)
    if not campos_ok:
        return f"faltando_campos_criticos_{'_'.join(faltando)}"

    sinais = 0
    if preco:
        sinais += 1
    if codigo:
        sinais += 1
    if gtin:
        sinais += 1
    if imagens:
        sinais += 1
    if categoria:
        sinais += 1
    if marca:
        sinais += 1
    if quantidade:
        sinais += 1

    if sinais == 0:
        return "sem_sinais_minimos_de_produto"

    score = _score_produto(final)
    return f"reprovado_na_validacao_final_score_{score}"


def _registrar_diag(
    diagnosticos: list[dict],
    url_produto: str,
    heuristica: dict | None = None,
    gpt: dict | None = None,
    final: dict | None = None,
    status: str = "",
    motivo: str = "",
    erro: str = "",
) -> None:
    item = {
        "url_produto": safe_str(url_produto),
        "status": safe_str(status),
        "motivo": safe_str(motivo),
        "erro": safe_str(erro),
    }

    if heuristica is not None:
        heuristica_limpa = _limpar_dict_debug(heuristica)
        for chave, valor in heuristica_limpa.items():
            item[f"heuristica_{chave}"] = valor

    if gpt is not None:
        gpt_limpo = _limpar_dict_debug(gpt)
        for chave, valor in gpt_limpo.items():
            item[f"gpt_{chave}"] = valor

    if final is not None:
        final_limpo = _limpar_dict_debug(final)
        for chave, valor in final_limpo.items():
            item[f"final_{chave}"] = valor
        item["final_descricao_curta"] = _descricao_curta_padrao(final)
        item["final_quantidade_normalizada"] = _quantidade_padrao(final)
        item["final_score"] = str(_score_produto(final))
        _, faltando = _campos_criticos_ok(final)
        item["final_campos_criticos_faltando"] = ", ".join(faltando)

    diagnosticos.append(item)


def _salvar_diagnostico_em_sessao(
    diagnosticos: list[dict],
    produtos_descobertos: list[str],
    rows_validos: list[dict],
    login_status: dict[str, Any] | None = None,
) -> None:
    st = _streamlit_ctx()
    if st is None:
        return

    try:
        df_diag = pd.DataFrame(diagnosticos).fillna("")
    except Exception:
        df_diag = pd.DataFrame()

    st.session_state["site_busca_diagnostico_df"] = df_diag
    st.session_state["site_busca_diagnostico_total_descobertos"] = len(produtos_descobertos)
    st.session_state["site_busca_diagnostico_total_validos"] = len(rows_validos)
    st.session_state["site_busca_diagnostico_total_rejeitados"] = max(
        len(diagnosticos) - len(rows_validos),
        0,
    )
    st.session_state["site_busca_login_status"] = login_status or {}


def _atualizar_progresso_main_thread(
    processados: int,
    total: int,
    ultimo_status: str,
    progress_bar,
    status_box,
    contador_box,
) -> None:
    if total <= 0:
        total = 1

    percentual = int((processados / total) * 100)
    percentual = max(0, min(percentual, 100))

    if progress_bar is not None:
        progress_bar.progress(percentual)

    if contador_box is not None:
        contador_box.write(f"Processando {processados} de {total}")

    if status_box is not None and ultimo_status:
        status_box.info(ultimo_status)


def _fornecedor_slug_do_contexto(base_url: str, auth_context: dict[str, Any] | None) -> str:
    if isinstance(auth_context, dict):
        slug = safe_str(auth_context.get("fornecedor_slug"))
        if slug:
            return slug
    base = safe_str(base_url).lower()
    base = re.sub(r"^https?://", "", base)
    base = base.replace("www.", "")
    base = re.sub(r"[^a-z0-9]+", "_", base).strip("_")
    return base or "fornecedor"


def _texto_tem_sinais_de_produto(texto: str) -> bool:
    texto_n = safe_str(texto).lower()
    if not texto_n:
        return False

    sinais = [
        '"@type":"product"',
        '"@type": "product"',
        "application/ld+json",
        "add to cart",
        "adicionar ao carrinho",
        "comprar agora",
        "sku",
        "código",
        "codigo",
        "gtin",
        "ean",
        "parcel",
        "r$",
        "price",
        "product",
    ]
    return any(s in texto_n for s in sinais)


def _score_html_produto(texto: str) -> int:
    texto_n = safe_str(texto).lower()
    if not texto_n:
        return 0

    score = 0
    if '"@type":"product"' in texto_n or '"@type": "product"' in texto_n:
        score += 4
    if "adicionar ao carrinho" in texto_n or "add to cart" in texto_n or "comprar agora" in texto_n:
        score += 2
    if "sku" in texto_n or "gtin" in texto_n or "ean" in texto_n or "código" in texto_n or "codigo" in texto_n:
        score += 1
    if "r$" in texto_n or "price" in texto_n or "parcel" in texto_n:
        score += 1
    return score


def _parece_html_login_puro(html: str, url_atual: str = "") -> bool:
    try:
        analise = detectar_login_captcha(html=html, url_atual=url_atual)
    except Exception:
        return False

    status = safe_str(analise.get("status"))
    if status not in {STATUS_LOGIN_CAPTCHA_DETECTADO, STATUS_LOGIN_REQUERIDO}:
        return False

    if _texto_tem_sinais_de_produto(html):
        return False

    return _score_html_produto(html) <= 0


# ============================================================
# AUTENTICAÇÃO / CONTEXTO
# ============================================================

def _auth_context_tem_dados_http(auth_context: dict[str, Any] | None) -> bool:
    if not isinstance(auth_context, dict):
        return False

    cookies = auth_context.get("cookies")
    headers = auth_context.get("headers")

    tem_cookies = isinstance(cookies, list) and len(cookies) > 0
    tem_headers = isinstance(headers, dict) and len(headers) > 0

    return tem_cookies or tem_headers


def _auth_context_valido(auth_context: dict[str, Any] | None) -> bool:
    if not isinstance(auth_context, dict):
        return False

    if bool(auth_context.get("session_ready", False)) and _auth_context_tem_dados_http(auth_context):
        return True

    if bool(auth_context.get("manual_mode", False)) and _auth_context_tem_dados_http(auth_context):
        return True

    return False


def _normalizar_headers_auth(headers: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(headers, dict):
        return {}

    saida: dict[str, str] = {}
    for chave, valor in headers.items():
        k = safe_str(chave)
        v = safe_str(valor)
        if k and v:
            saida[k] = v
    return saida


def _criar_sessao_autenticada(auth_context: dict[str, Any] | None) -> requests.Session:
    session = requests.Session()

    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        }
    )

    if not _auth_context_valido(auth_context):
        return session

    headers = _normalizar_headers_auth(auth_context.get("headers"))
    if headers:
        session.headers.update(headers)

    cookies = auth_context.get("cookies", [])
    if isinstance(cookies, list):
        for cookie in cookies:
            if not isinstance(cookie, dict):
                continue

            nome = safe_str(cookie.get("name"))
            valor = safe_str(cookie.get("value"))
            dominio = safe_str(cookie.get("domain"))
            path = safe_str(cookie.get("path")) or "/"

            if not nome:
                continue

            try:
                session.cookies.set(
                    nome,
                    valor,
                    domain=dominio or None,
                    path=path,
                )
            except Exception:
                continue

    return session


def _url_produtos_contexto(base_url: str, auth_context: dict[str, Any] | None) -> str:
    if isinstance(auth_context, dict):
        products_url = safe_str(auth_context.get("products_url"))
        if products_url:
            return normalizar_url(products_url)
    return normalizar_url(base_url)


def _fetch_html_publico(url_produto: str) -> str:
    if fetch_html_retry is None:
        return ""

    ultima_exc: Exception | None = None
    for tentativas in (2, 3):
        try:
            html = safe_str(fetch_html_retry(url_produto, tentativas=tentativas))
            if html:
                return html
        except Exception as exc:
            ultima_exc = exc

    if ultima_exc is not None:
        raise ultima_exc

    return ""


def _fetch_html_autenticado(url_produto: str, auth_context: dict[str, Any] | None) -> str:
    if not _auth_context_valido(auth_context):
        return ""

    session = _criar_sessao_autenticada(auth_context)

    ultima_exc: Exception | None = None
    for _ in range(2):
        try:
            response = session.get(url_produto, timeout=45, allow_redirects=True)
            if response.ok and safe_str(response.text):
                html = safe_str(response.text)
                if "<html" in html.lower() or "</body>" in html.lower() or len(html) > 500:
                    return html
            ultima_exc = RuntimeError(f"HTTP {response.status_code}")
        except Exception as exc:
            ultima_exc = exc

    if ultima_exc is not None:
        raise ultima_exc

    return ""


def _primeiro_fetch_para_deteccao(
    base_url: str,
    auth_context: dict[str, Any] | None = None,
) -> tuple[str, str]:
    alvo = _url_produtos_contexto(base_url, auth_context)

    if _auth_context_valido(auth_context):
        try:
            html_auth = _fetch_html_autenticado(alvo, auth_context=auth_context)
            if html_auth:
                return html_auth, alvo
        except Exception as exc:
            _log_debug(
                f"Falha no fetch autenticado para detecção inicial | url={alvo} | erro={exc}",
                nivel="ERRO",
            )

    try:
        html = _fetch_html_publico(alvo)
        if html:
            return html, alvo
    except Exception as exc:
        _log_debug(
            f"Falha no fetch público para detecção inicial | url={alvo} | erro={exc}",
            nivel="ERRO",
        )

    return "", alvo


def _detectar_bloqueio_login(
    base_url: str,
    auth_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    html, url_final = _primeiro_fetch_para_deteccao(base_url, auth_context=auth_context)
    fornecedor = _fornecedor_slug_do_contexto(base_url, auth_context)

    if not html:
        return {
            "status": "",
            "exige_login": False,
            "captcha_detectado": False,
            "mensagem": "",
            "auth_context": auth_context or {},
        }

    analise = detectar_e_salvar_status_login(
        base_url=base_url,
        html=html,
        url_atual=url_final,
        mensagem_extra="",
        fornecedor=fornecedor,
    )

    status = safe_str(analise.get("status"))
    if status in {STATUS_LOGIN_CAPTCHA_DETECTADO, STATUS_LOGIN_REQUERIDO}:
        _log_debug(
            f"Possível bloqueio de login detectado | url={base_url} | status={status}",
            nivel="INFO",
        )

    return analise


def _resolver_auth_context(base_url: str, auth_context: dict[str, Any] | None = None) -> dict[str, Any]:
    if _auth_context_valido(auth_context):
        return auth_context or {}

    try:
        fornecedor = _fornecedor_slug_do_contexto(base_url, auth_context)
        contexto_salvo = montar_auth_context(base_url=base_url, fornecedor=fornecedor)
        if _auth_context_valido(contexto_salvo):
            _log_debug(
                f"Sessão HTTP autenticada reutilizada com sucesso | url={base_url} | fornecedor={fornecedor}",
                nivel="INFO",
            )
            return contexto_salvo
    except Exception as exc:
        _log_debug(
            f"Falha ao montar auth_context salvo | url={base_url} | erro={exc}",
            nivel="ERRO",
        )

    return auth_context or {}


# ============================================================
# FALLBACKS PRO
# ============================================================

def _executar_fetch_html(url_produto: str, auth_context: dict[str, Any] | None = None) -> str:
    """
    Estratégia blindada:
    1) tenta sessão HTTP autenticada somente se houver cookies/headers reais
    2) cai para fetch público
    3) não depende de navegador visível / playwright
    """
    if _auth_context_valido(auth_context):
        try:
            html_auth = _fetch_html_autenticado(url_produto, auth_context=auth_context)
            if html_auth and not _parece_html_login_puro(html_auth, url_atual=url_produto):
                return html_auth

            if html_auth and _parece_html_login_puro(html_auth, url_atual=url_produto):
                _log_debug(
                    f"Resposta autenticada parece página de login; tentando modo público | url={url_produto}",
                    nivel="INFO",
                )
        except Exception as exc:
            _log_debug(
                f"Falha no fetch autenticado, usando fallback comum | url={url_produto} | erro={exc}",
                nivel="ERRO",
            )

    return _fetch_html_publico(url_produto)


def _executar_heuristica(url_produto: str, html_produto: str) -> dict[str, Any]:
    if extrair_detalhes_heuristicos is None:
        return {}

    try:
        dados = extrair_detalhes_heuristicos(url_produto, html_produto)
        return dados if isinstance(dados, dict) else {}
    except Exception as exc:
        _log_debug(f"Heurística falhou | url={url_produto} | erro={exc}", nivel="ERRO")
        return {}


def _executar_gpt(url_produto: str, html_produto: str, heuristica: dict[str, Any]) -> dict[str, Any]:
    if gpt_extrair_produto is None:
        return {}

    ultimo_resultado: dict[str, Any] = {}
    for _ in range(2):
        try:
            dados = gpt_extrair_produto(url_produto, html_produto, heuristica)
            if isinstance(dados, dict) and dados:
                return dados
            if isinstance(dados, dict):
                ultimo_resultado = dados
        except Exception as exc:
            _log_debug(f"GPT falhou | url={url_produto} | erro={exc}", nivel="ERRO")
            continue

    return ultimo_resultado


def _resolver_final(url_produto: str, heuristica: dict[str, Any], gpt: dict[str, Any]) -> dict[str, Any]:
    final: dict[str, Any] = {}

    for campo in [
        "descricao",
        "descricao_curta",
        "descricao_detalhada",
        "categoria",
        "marca",
        "url_imagens",
        "codigo",
        "gtin",
        "ncm",
        "preco",
        "quantidade",
    ]:
        final[campo] = safe_str(gpt.get(campo)) or safe_str(heuristica.get(campo))

    final["url_produto"] = (
        safe_str(gpt.get("url_produto"))
        or safe_str(heuristica.get("url_produto"))
        or url_produto
    )
    final["descricao"] = (
        safe_str(final.get("descricao"))
        or safe_str(heuristica.get("titulo"))
        or safe_str(heuristica.get("nome"))
    )
    final["descricao_curta"] = _descricao_curta_padrao(final)
    final["quantidade"] = _quantidade_padrao(final)
    final["marca"] = _resolver_marca(final, heuristica)

    return final


def _deve_bloquear_produto_por_login(
    html_produto: str,
    url_produto: str,
    heuristica: dict[str, Any],
    auth_context: dict[str, Any] | None = None,
) -> bool:
    manual_mode = isinstance(auth_context, dict) and bool(auth_context.get("manual_mode", False))
    if manual_mode:
        return False

    if _auth_context_valido(auth_context):
        return False

    try:
        analise_bloqueio = detectar_login_captcha(html_produto, url_atual=url_produto)
    except Exception:
        return False

    status = safe_str(analise_bloqueio.get("status"))
    if status not in {STATUS_LOGIN_CAPTCHA_DETECTADO, STATUS_LOGIN_REQUERIDO}:
        return False

    if heuristica:
        score_heuristica = pontuar_produto(
            titulo=safe_str(heuristica.get("descricao")) or safe_str(heuristica.get("titulo")),
            preco=safe_str(heuristica.get("preco")),
            codigo=safe_str(heuristica.get("codigo")),
            gtin=safe_str(heuristica.get("gtin")),
            imagens=safe_str(heuristica.get("url_imagens")),
            categoria=safe_str(heuristica.get("categoria")),
            url_produto=safe_str(heuristica.get("url_produto")) or url_produto,
        )
        if score_heuristica > 0:
            return False

    return _parece_html_login_puro(html_produto, url_atual=url_produto)


def _processar_um_produto(
    url_produto: str,
    diagnostico: bool = False,
    auth_context: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    url_produto = safe_str(url_produto)

    if not url_produto:
        return "rejeitado", {
            "url_produto": url_produto,
            "motivo": "url_vazia",
        }

    try:
        html_produto = _executar_fetch_html(url_produto, auth_context=auth_context)
    except Exception as exc:
        return "erro", {
            "url_produto": url_produto,
            "motivo": "erro_fetch_html",
            "erro": str(exc),
        }

    heuristica = _executar_heuristica(url_produto, html_produto)

    if _deve_bloquear_produto_por_login(
        html_produto=html_produto,
        url_produto=url_produto,
        heuristica=heuristica,
        auth_context=auth_context,
    ):
        return "bloqueado_login", {
            "url_produto": url_produto,
            "motivo": "login_ou_captcha_sem_sessao_http_utilizavel",
            "erro": "",
            "heuristica": heuristica,
            "gpt": {},
            "final": {},
        }

    gpt = _executar_gpt(url_produto, html_produto, heuristica)
    final = _resolver_final(url_produto, heuristica, gpt)

    campos_ok, faltando = _campos_criticos_ok(final)
    if faltando:
        _log_debug(
            f"Produto com campos críticos faltando | url={url_produto} | faltando={', '.join(faltando)}",
            nivel="ERRO" if not campos_ok else "INFO",
        )

    if not produto_final_valido(final):
        return "rejeitado", {
            "url_produto": url_produto,
            "heuristica": heuristica,
            "gpt": gpt,
            "final": final,
            "motivo": _motivo_rejeicao(final),
        }

    if not campos_ok:
        return "rejeitado", {
            "url_produto": url_produto,
            "heuristica": heuristica,
            "gpt": gpt,
            "final": final,
            "motivo": _motivo_rejeicao(final),
        }

    return "aprovado", {
        "url_produto": url_produto,
        "heuristica": heuristica,
        "gpt": gpt,
        "final": final,
        "row": _montar_linha_saida(final),
    }


def _descobrir_produtos_com_contexto(
    base_url: str,
    termo: str,
    limite: int,
    auth_context: dict[str, Any] | None = None,
) -> list[str]:
    alvo_descoberta = _url_produtos_contexto(base_url, auth_context)

    candidatos_tentativa: list[tuple[str, dict[str, Any] | None]] = []

    if _auth_context_valido(auth_context):
        candidatos_tentativa.append((alvo_descoberta, auth_context))

    candidatos_tentativa.append((alvo_descoberta, None))

    vistos_urls: set[str] = set()
    saida: list[str] = []

    for alvo, ctx in candidatos_tentativa:
        chave = f"{alvo}|{'auth' if ctx else 'publico'}"
        if chave in vistos_urls:
            continue
        vistos_urls.add(chave)

        if descobrir_produtos_no_dominio is None:
            if alvo:
                return [alvo]
            continue

        try:
            produtos = descobrir_produtos_no_dominio(
                base_url=alvo,
                termo=termo,
                max_paginas=400,
                max_produtos=limite,
                max_segundos=900,
                auth_context=ctx,
            )
            if isinstance(produtos, list) and produtos:
                for url in produtos:
                    url_n = safe_str(url)
                    if url_n and url_n not in saida:
                        saida.append(url_n)
                if saida:
                    return saida
        except Exception as exc:
            modo = "autenticado_http" if ctx else "publico"
            _log_debug(
                f"Falha ao descobrir produtos | modo={modo} | url={alvo} | erro={exc}",
                nivel="ERRO",
            )

    if alvo_descoberta:
        return [alvo_descoberta]

    return []


# ============================================================
# FUNÇÃO PRINCIPAL
# ============================================================

def buscar_produtos_site_com_gpt(
    base_url: str,
    termo: str = "",
    limite_links: int | None = None,
    diagnostico: bool = False,
    auth_context: dict[str, Any] | None = None,
) -> pd.DataFrame:
    st = _streamlit_ctx()

    base_url = normalizar_url(base_url)
    termo = safe_str(termo)

    if not base_url:
        _log_debug("Busca por site cancelada: base_url vazia.", nivel="ERRO")
        return pd.DataFrame()

    limite = _limite_tecnico(limite_links)

    progress_bar = None
    status_box = None
    contador_box = None

    if st is not None:
        progress_bar = st.progress(0)
        status_box = st.empty()
        contador_box = st.empty()
        status_box.info("🔍 Descobrindo produtos no site...")

    auth_context = _resolver_auth_context(base_url=base_url, auth_context=auth_context)
    fornecedor = _fornecedor_slug_do_contexto(base_url, auth_context)
    manual_mode = isinstance(auth_context, dict) and bool(auth_context.get("manual_mode", False))
    auth_http_ok = _auth_context_valido(auth_context)

    auth_mode = "manual_http" if manual_mode and auth_http_ok else ("autenticado_http" if auth_http_ok else "publico")
    _log_debug(
        f"Iniciando busca por site | url={base_url} | termo={termo or '-'} | limite={limite} | modo={auth_mode}",
        nivel="INFO",
    )
    _log_debug(
        (
            "Auth context | "
            f"manual_mode={manual_mode} | "
            f"session_ready={safe_str(auth_context.get('session_ready'))} | "
            f"auth_http_ok={auth_http_ok}"
        ),
        nivel="INFO",
    )

    login_status = _detectar_bloqueio_login(base_url=base_url, auth_context=auth_context)
    login_status_normalizado = safe_str(login_status.get("status"))

    # Não interrompe cedo mais.
    # Primeiro tenta descobrir e processar os produtos em modo HTTP público/autenticado.
    if login_status_normalizado in {STATUS_LOGIN_CAPTCHA_DETECTADO, STATUS_LOGIN_REQUERIDO}:
        mensagem_info = safe_str(login_status.get("mensagem"))
        if not mensagem_info:
            if login_status_normalizado == STATUS_LOGIN_CAPTCHA_DETECTADO:
                mensagem_info = (
                    "Possível captcha/login detectado. Tentando captura por HTTP público/autenticado "
                    "sem depender de navegador visível."
                )
            else:
                mensagem_info = (
                    "Possível página com login detectada. Tentando captura por HTTP público/autenticado "
                    "sem depender de navegador visível."
                )

        if status_box is not None:
            status_box.warning(mensagem_info)

        _log_debug(
            f"Detecção inicial de login/captcha não interrompeu o crawler | url={base_url} | status={login_status_normalizado}",
            nivel="INFO",
        )

    if auth_http_ok:
        salvar_status_login_em_sessao(
            base_url=base_url,
            fornecedor=fornecedor,
            status=STATUS_SESSAO_PRONTA,
            mensagem=(
                "Sessão HTTP autenticada pronta para uso."
                if not manual_mode
                else "Contexto manual convertido em sessão HTTP utilizável."
            ),
            exige_login=False,
            captcha_detectado=False,
        )

    produtos = _descobrir_produtos_com_contexto(
        base_url=base_url,
        termo=termo,
        limite=limite,
        auth_context=auth_context,
    )

    if not produtos:
        if login_status_normalizado in {STATUS_LOGIN_CAPTCHA_DETECTADO, STATUS_LOGIN_REQUERIDO} and not auth_http_ok:
            mensagem = (
                "Fornecedor aparenta exigir login/captcha e não há sessão HTTP utilizável. "
                "Busca pública não encontrou catálogo."
            )
            salvar_status_login_em_sessao(
                base_url=base_url,
                fornecedor=fornecedor,
                status=login_status_normalizado or STATUS_LOGIN_REQUERIDO,
                mensagem=mensagem,
                exige_login=bool(login_status.get("exige_login")),
                captcha_detectado=bool(login_status.get("captcha_detectado")),
            )
            if status_box is not None:
                status_box.warning(mensagem)
        else:
            if status_box is not None:
                status_box.warning("Nenhum produto encontrado.")
            _log_debug("Nenhum produto encontrado na descoberta inicial do domínio.", nivel="ERRO")

        if diagnostico:
            _salvar_diagnostico_em_sessao(
                diagnosticos=[],
                produtos_descobertos=[],
                rows_validos=[],
                login_status=login_status,
            )
        return pd.DataFrame()

    produtos_limpos: list[str] = []
    vistos_descoberta: set[str] = set()
    for url in produtos:
        url_n = safe_str(url)
        if not url_n:
            continue
        if url_n in vistos_descoberta:
            continue
        vistos_descoberta.add(url_n)
        produtos_limpos.append(url_n)

    produtos = produtos_limpos
    total = len(produtos)

    rows: list[dict] = []
    rows_lock = threading.Lock()

    vistos_aprovados: set[str] = set()
    aprovados_lock = threading.Lock()

    diagnosticos: list[dict] = []
    diag_lock = threading.Lock()

    login_bloqueios = 0

    _log_debug(f"Links de produto descobertos: {total}", nivel="INFO")

    workers = _max_workers(total)
    processados = 0

    def worker(url_produto: str) -> tuple[str, dict[str, Any]]:
        return _processar_um_produto(
            url_produto=url_produto,
            diagnostico=diagnostico,
            auth_context=auth_context,
        )

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_url = {
                executor.submit(worker, url_produto): url_produto
                for url_produto in produtos
            }

            for future in concurrent.futures.as_completed(future_to_url):
                url_produto = future_to_url[future]
                processados += 1

                try:
                    status, payload = future.result()
                except Exception as exc:
                    status = "erro"
                    payload = {
                        "url_produto": url_produto,
                        "motivo": "erro_worker_nao_tratado",
                        "erro": repr(exc),
                    }
                    _log_debug(
                        f"Worker falhou sem tratamento | url={url_produto} | erro={repr(exc)}",
                        nivel="ERRO",
                    )

                ultimo_status = f"🌐 Processando produto {processados}/{total}\n\n{url_produto}"
                _atualizar_progresso_main_thread(
                    processados=processados,
                    total=total,
                    ultimo_status=ultimo_status,
                    progress_bar=progress_bar,
                    status_box=status_box,
                    contador_box=contador_box,
                )

                if status == "aprovado":
                    row = payload.get("row", {})
                    final = payload.get("final", {})
                    heuristica = payload.get("heuristica", {})
                    gpt = payload.get("gpt", {})

                    with aprovados_lock:
                        if url_produto in vistos_aprovados:
                            if diagnostico:
                                with diag_lock:
                                    _registrar_diag(
                                        diagnosticos,
                                        url_produto=url_produto,
                                        heuristica=heuristica,
                                        gpt=gpt,
                                        final=final,
                                        status="rejeitado",
                                        motivo="url_duplicada",
                                    )
                            continue
                        vistos_aprovados.add(url_produto)

                    with rows_lock:
                        rows.append(row)

                    if diagnostico:
                        with diag_lock:
                            _registrar_diag(
                                diagnosticos,
                                url_produto=url_produto,
                                heuristica=heuristica,
                                gpt=gpt,
                                final=final,
                                status="aprovado",
                                motivo="produto_valido",
                            )
                    continue

                if status == "bloqueado_login":
                    login_bloqueios += 1

                if diagnostico:
                    with diag_lock:
                        _registrar_diag(
                            diagnosticos,
                            url_produto=url_produto,
                            heuristica=payload.get("heuristica"),
                            gpt=payload.get("gpt"),
                            final=payload.get("final"),
                            status=status,
                            motivo=safe_str(payload.get("motivo")),
                            erro=safe_str(payload.get("erro")),
                        )

    except Exception as exc:
        _log_debug(f"Falha geral no processamento paralelo: {repr(exc)}", nivel="ERRO")
        raise RuntimeError(f"Falha no processamento paralelo dos produtos: {repr(exc)}") from exc

    if login_bloqueios > 0 and len(rows) == 0 and not auth_http_ok:
        mensagem_bloqueio = (
            "Os links processados aparentam exigir login/captcha e não existe sessão HTTP utilizável "
            "para continuar a captura no deploy atual."
        )
        salvar_status_login_em_sessao(
            base_url=base_url,
            fornecedor=fornecedor,
            status=STATUS_LOGIN_CAPTCHA_DETECTADO,
            mensagem=mensagem_bloqueio,
            exige_login=True,
            captcha_detectado=True,
        )
        if status_box is not None:
            status_box.warning(mensagem_bloqueio)
        _log_debug(
            f"Todos os itens foram bloqueados por login/captcha | url={base_url} | bloqueios={login_bloqueios}",
            nivel="ERRO",
        )

    if progress_bar is not None:
        progress_bar.progress(100)

    if status_box is not None:
        if len(rows) > 0:
            status_box.success(f"🎉 Busca finalizada. Produtos válidos: {len(rows)}")
        elif login_bloqueios > 0 and not auth_http_ok:
            status_box.warning("Busca finalizada sem produtos válidos por login/captcha sem sessão HTTP utilizável.")
        else:
            status_box.warning("Busca finalizada sem produtos válidos.")

    if diagnostico:
        _salvar_diagnostico_em_sessao(
            diagnosticos=diagnosticos,
            produtos_descobertos=produtos,
            rows_validos=rows,
            login_status=login_status,
        )

    _log_debug(
        (
            "Busca por site finalizada | "
            f"descobertos={len(produtos)} | "
            f"validos={len(rows)} | "
            f"rejeitados={max(len(produtos) - len(rows), 0)} | "
            f"login_bloqueios={login_bloqueios} | "
            f"manual_mode={manual_mode} | "
            f"auth_http_ok={auth_http_ok}"
        ),
        nivel="INFO",
    )

    return _df_saida(rows)
