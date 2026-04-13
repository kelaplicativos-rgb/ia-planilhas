from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from urllib.parse import urljoin, urlparse

import pandas as pd
import streamlit as st
from bs4 import BeautifulSoup

from bling_app_zero.core.fetch_router import fetch_payload_router
from bling_app_zero.core.site_crawler_extractors import extrair_produto_crawler
from bling_app_zero.core.site_crawler_helpers import (
    MAX_PAGINAS,
    MAX_PRODUTOS,
    MAX_THREADS,
    extrair_links_paginacao_crawler,
    extrair_links_produtos_crawler,
    link_parece_produto_crawler,
)

# ==========================================================
# VERSION
# ==========================================================
SITE_CRAWLER_VERSION = "V3_AUTH_SYNC_READY"

# ==========================================================
# LOG
# ==========================================================
try:
    from bling_app_zero.utils.excel_logs import log_debug
except Exception:
    def log_debug(*args, **kwargs):
        return None


# ==========================================================
# SAFE
# ==========================================================
def _safe_list(v: Any) -> list[Any]:
    return v if isinstance(v, list) else []


def _safe_dict(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _safe_int(valor: Any, padrao: int) -> int:
    try:
        n = int(valor)
        return n if n >= 0 else padrao
    except Exception:
        return padrao


def _safe_bool(valor: Any) -> bool:
    if isinstance(valor, bool):
        return valor
    try:
        texto = str(valor or "").strip().lower()
    except Exception:
        return False
    return texto in {"1", "true", "sim", "yes", "y", "on"}


def _safe_str(valor: Any) -> str:
    try:
        return str(valor or "").strip()
    except Exception:
        return ""


def _normalizar_url(url: str) -> str:
    url = _safe_str(url)
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        return "https://" + url
    return url


def _dominio(url: str) -> str:
    try:
        return urlparse(_normalizar_url(url)).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _mesmo_dominio(url_a: str, url_b: str) -> bool:
    return bool(_dominio(url_a)) and _dominio(url_a) == _dominio(url_b)


def _normalizar_estoque_df(valor: Any) -> int:
    try:
        if valor is None:
            return 0
        if isinstance(valor, bool):
            return 0

        texto = _safe_str(valor)
        if not texto:
            return 0

        texto_lower = texto.lower()
        if any(
            token in texto_lower
            for token in [
                "sem estoque",
                "esgotado",
                "indisponível",
                "indisponivel",
                "zerado",
                "sold out",
                "out of stock",
            ]
        ):
            return 0

        numero = int(float(texto.replace(".", "").replace(",", ".")))
        if numero < 0:
            return 0
        return numero
    except Exception:
        return 0


# ==========================================================
# IMAGENS
# ==========================================================
def _eh_url_imagem_invalida(url: str) -> bool:
    try:
        u = _safe_str(url).lower()
        if not u:
            return True

        tokens_ruins = [
            "facebook.com/tr",
            "facebook.net",
            "doubleclick.net",
            "google-analytics.com",
            "googletagmanager.com",
            "/pixel",
            "/track",
            "/tracking",
            "/collect",
            "fbclid=",
            "gclid=",
            "utm_",
            "sprite",
            "icon",
            "logo",
            "banner",
            "avatar",
            "placeholder",
            "spacer",
            "blank.",
            "loader",
            "loading",
            "favicon",
            "lazyload",
            "thumb",
            "thumbnail",
            "mini",
            "small",
        ]

        if any(token in u for token in tokens_ruins):
            return True

        if not u.startswith(("http://", "https://")):
            return True

        return False
    except Exception:
        return True


def _normalizar_url_imagem(url: str, base_url: str = "") -> str:
    try:
        txt = _safe_str(url)
        if not txt:
            return ""

        if txt.startswith("data:image"):
            return ""

        if "," in txt:
            partes = [p.strip() for p in txt.split(",") if p.strip()]
            for parte in partes:
                primeira = parte.split(" ")[0].strip()
                if primeira:
                    txt = primeira
                    break

        absoluto = urljoin(base_url, txt).strip() if base_url else txt.strip()
        if not absoluto.startswith(("http://", "https://")):
            return ""

        if _eh_url_imagem_invalida(absoluto):
            return ""

        return absoluto
    except Exception:
        return ""


def _lista_imagens_para_pipe(valor: Any, base_url: str = "") -> str:
    itens: list[str] = []

    if isinstance(valor, list):
        origem = valor
    else:
        texto = _safe_str(valor)
        if not texto:
            origem = []
        else:
            origem = [p.strip() for p in texto.replace(";", ",").split(",") if p.strip()]

    vistos: set[str] = set()

    for item in origem:
        img = _normalizar_url_imagem(item, base_url=base_url)
        if not img:
            continue
        if img in vistos:
            continue
        vistos.add(img)
        itens.append(img)

    return "|".join(itens)


# ==========================================================
# AUTH / CONTEXTO
# ==========================================================
def _resolver_auth_config(
    *,
    usuario: str = "",
    senha: str = "",
    precisa_login: bool = False,
    auth_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    auth_config = _safe_dict(auth_config)

    usuario_final = _safe_str(
        auth_config.get("usuario")
        or auth_config.get("username")
        or auth_config.get("email")
        or usuario
    )
    senha_final = _safe_str(
        auth_config.get("senha")
        or auth_config.get("password")
        or senha
    )
    precisa_login_final = _safe_bool(
        auth_config["precisa_login"] if "precisa_login" in auth_config else precisa_login
    )

    saida = dict(auth_config)
    saida["usuario"] = usuario_final
    saida["senha"] = senha_final
    saida["precisa_login"] = precisa_login_final
    return saida


# ==========================================================
# EXTRAÇÃO SEGURA
# ==========================================================
def _extrair_produto_seguro(
    html: str,
    url_produto: str,
    *,
    url_base: str = "",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Tenta chamar o extrator existente com múltiplas assinaturas,
    preservando compatibilidade com a base.
    """
    payload = _safe_dict(payload)

    tentativas = [
        lambda: extrair_produto_crawler(html, url_produto, url_base, payload),
        lambda: extrair_produto_crawler(html, url_produto, url_base),
        lambda: extrair_produto_crawler(html, url_produto),
        lambda: extrair_produto_crawler(html=html, url=url_produto, url_base=url_base, payload=payload),
        lambda: extrair_produto_crawler(html=html, url=url_produto, url_base=url_base),
        lambda: extrair_produto_crawler(html=html, url=url_produto),
    ]

    for fn in tentativas:
        try:
            resultado = fn()
            if isinstance(resultado, dict):
                return resultado
        except TypeError:
            continue
        except Exception as e:
            log_debug(f"[SITE_CRAWLER] extrator falhou em uma tentativa: {e}", "WARNING")
            break

    return {}


def _normalizar_registro_produto(
    registro: dict[str, Any],
    *,
    url_produto: str,
    url_base: str,
    estoque_padrao_disponivel: int = 1,
) -> dict[str, Any]:
    registro = _safe_dict(registro)

    codigo = _safe_str(
        registro.get("codigo")
        or registro.get("Código")
        or registro.get("sku")
        or registro.get("SKU")
        or registro.get("referencia")
        or registro.get("Referência")
    )

    nome = _safe_str(
        registro.get("nome")
        or registro.get("Nome")
        or registro.get("titulo")
        or registro.get("Título")
        or registro.get("descricao")
        or registro.get("Descrição")
        or registro.get("produto")
    )

    descricao = _safe_str(
        registro.get("descricao")
        or registro.get("Descrição")
        or registro.get("descricao_curta")
        or registro.get("Descrição Curta")
        or nome
    )

    preco = (
        registro.get("preco")
        or registro.get("Preço")
        or registro.get("preco_venda")
        or registro.get("Preço de venda")
        or registro.get("valor")
        or ""
    )

    estoque_raw = (
        registro.get("estoque")
        or registro.get("Estoque")
        or registro.get("quantidade")
        or registro.get("Quantidade")
        or registro.get("saldo")
        or ""
    )

    estoque = _normalizar_estoque_df(estoque_raw)

    # fallback: se extrator não trouxe estoque e não há sinal de indisponível, usa o padrão
    if estoque == 0:
        texto_geral = " ".join(
            [
                _safe_str(registro.get("disponibilidade")),
                _safe_str(registro.get("status_estoque")),
                _safe_str(registro.get("observacao_estoque")),
            ]
        ).lower()
        if texto_geral and not any(
            token in texto_geral
            for token in ["sem estoque", "esgotado", "indisponível", "indisponivel", "zerado"]
        ):
            estoque = max(0, _safe_int(estoque_padrao_disponivel, 1))

    imagens_pipe = _lista_imagens_para_pipe(
        registro.get("imagens")
        or registro.get("Imagens")
        or registro.get("imagem")
        or registro.get("Imagem")
        or registro.get("url_imagem")
        or registro.get("URL Imagem"),
        base_url=url_produto or url_base,
    )

    categoria = _safe_str(
        registro.get("categoria")
        or registro.get("Categoria")
        or registro.get("breadcrumb")
        or registro.get("Breadcrumb")
    )

    marca = _safe_str(registro.get("marca") or registro.get("Marca"))
    gtin = _safe_str(
        registro.get("gtin")
        or registro.get("GTIN")
        or registro.get("ean")
        or registro.get("EAN")
    )
    ncm = _safe_str(registro.get("ncm") or registro.get("NCM"))

    saida = dict(registro)
    saida["codigo"] = codigo
    saida["nome"] = nome or descricao
    saida["descricao"] = descricao or nome
    saida["preco"] = preco
    saida["estoque"] = estoque
    saida["categoria"] = categoria
    saida["marca"] = marca
    saida["gtin"] = gtin
    saida["ncm"] = ncm
    saida["imagens"] = imagens_pipe
    saida["url"] = _safe_str(registro.get("url") or url_produto)
    saida["origem"] = "site"
    saida["situacao"] = _safe_str(registro.get("situacao") or registro.get("Situação") or "ativo")
    return saida


# ==========================================================
# LINKS
# ==========================================================
def _coletar_links_categoria(
    html: str,
    url_atual: str,
) -> tuple[list[str], list[str]]:
    produtos: list[str] = []
    paginas: list[str] = []

    try:
        produtos = _safe_list(extrair_links_produtos_crawler(html, url_atual))
    except Exception as e:
        log_debug(f"[SITE_CRAWLER] falha ao extrair links de produto: {e}", "WARNING")

    try:
        paginas = _safe_list(extrair_links_paginacao_crawler(html, url_atual))
    except Exception as e:
        log_debug(f"[SITE_CRAWLER] falha ao extrair links de paginação: {e}", "WARNING")

    return produtos, paginas


def _filtrar_links_mesmo_dominio(links: list[str], url_base: str) -> list[str]:
    saida: list[str] = []
    vistos: set[str] = set()

    for link in links:
        url = _normalizar_url(link)
        if not url:
            continue
        if not _mesmo_dominio(url, url_base):
            continue
        if url in vistos:
            continue
        vistos.add(url)
        saida.append(url)

    return saida


# ==========================================================
# FETCH WRAPPER
# ==========================================================
def _fetch_url_crawler(
    url: str,
    *,
    preferir_js: bool,
    auth_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    auth_config = _safe_dict(auth_config)

    try:
        payload = fetch_payload_router(
            url=url,
            preferir_js=preferir_js,
            usuario=_safe_str(auth_config.get("usuario")),
            senha=_safe_str(auth_config.get("senha")),
            precisa_login=_safe_bool(auth_config.get("precisa_login")),
            auth_config=auth_config,
        )
        return _safe_dict(payload)
    except Exception as e:
        log_debug(f"[SITE_CRAWLER] fetch falhou | url={url} | erro={e}", "ERROR")
        return {
            "ok": False,
            "url": url,
            "html": "",
            "error": str(e),
            "engine": "none",
        }


# ==========================================================
# PRODUTO INDIVIDUAL
# ==========================================================
def _processar_produto(
    url_produto: str,
    *,
    url_base: str,
    preferir_js: bool,
    auth_config: dict[str, Any] | None = None,
    estoque_padrao_disponivel: int = 1,
) -> dict[str, Any]:
    payload = _fetch_url_crawler(
        url_produto,
        preferir_js=preferir_js,
        auth_config=auth_config,
    )

    html = _safe_str(payload.get("html"))
    if not payload.get("ok") or not html:
        return {
            "ok": False,
            "url": url_produto,
            "erro": _safe_str(payload.get("error")) or "falha_fetch_produto",
            "engine": _safe_str(payload.get("engine")),
        }

    try:
        extraido = _extrair_produto_seguro(
            html,
            url_produto,
            url_base=url_base,
            payload=payload,
        )
        registro = _normalizar_registro_produto(
            extraido,
            url_produto=url_produto,
            url_base=url_base,
            estoque_padrao_disponivel=estoque_padrao_disponivel,
        )

        # mínimo para aproveitar o registro
        if not _safe_str(registro.get("nome")) and not _safe_str(registro.get("codigo")):
            return {
                "ok": False,
                "url": url_produto,
                "erro": "extracao_sem_nome_e_sem_codigo",
                "engine": _safe_str(payload.get("engine")),
            }

        return {
            "ok": True,
            "url": url_produto,
            "engine": _safe_str(payload.get("engine")),
            "registro": registro,
        }
    except Exception as e:
        return {
            "ok": False,
            "url": url_produto,
            "erro": f"erro_extracao_produto: {e}",
            "engine": _safe_str(payload.get("engine")),
        }


# ==========================================================
# DATAFRAME
# ==========================================================
def _produtos_para_dataframe(produtos: list[dict[str, Any]]) -> pd.DataFrame:
    if not produtos:
        return pd.DataFrame()

    df = pd.DataFrame(produtos).copy()

    ordem_preferencial = [
        "codigo",
        "nome",
        "descricao",
        "preco",
        "estoque",
        "categoria",
        "marca",
        "gtin",
        "ncm",
        "imagens",
        "url",
        "situacao",
        "origem",
    ]

    colunas_existentes = [c for c in ordem_preferencial if c in df.columns]
    demais = [c for c in df.columns if c not in colunas_existentes]
    df = df[colunas_existentes + demais]

    try:
        if "estoque" in df.columns:
            df["estoque"] = df["estoque"].apply(_normalizar_estoque_df)
    except Exception:
        pass

    try:
        if "imagens" in df.columns:
            df["imagens"] = df["imagens"].apply(lambda x: _lista_imagens_para_pipe(x))
    except Exception:
        pass

    return df.fillna("")


# ==========================================================
# CRAWLER PRINCIPAL
# ==========================================================
def crawl_site_produtos(
    url: str,
    *,
    preferir_js: bool = False,
    max_paginas: int | None = None,
    max_produtos: int | None = None,
    max_threads: int | None = None,
    usuario: str = "",
    senha: str = "",
    precisa_login: bool = False,
    auth_config: dict[str, Any] | None = None,
    estoque_padrao_disponivel: int = 1,
    progresso_callback=None,
    atualizar_streamlit_state: bool = True,
) -> dict[str, Any]:
    url = _normalizar_url(url)
    if not url:
        return {
            "ok": False,
            "erro": "url_invalida",
            "produtos": [],
            "df": pd.DataFrame(),
            "links_produto": [],
            "paginas_visitadas": [],
            "stats": {},
            "version": SITE_CRAWLER_VERSION,
        }

    auth_final = _resolver_auth_config(
        usuario=usuario,
        senha=senha,
        precisa_login=precisa_login,
        auth_config=auth_config,
    )

    limite_paginas = min(max(1, _safe_int(max_paginas, MAX_PAGINAS)), max(1, MAX_PAGINAS))
    limite_produtos = min(max(1, _safe_int(max_produtos, MAX_PRODUTOS)), max(1, MAX_PRODUTOS))
    limite_threads = min(max(1, _safe_int(max_threads, MAX_THREADS)), max(1, MAX_THREADS))

    log_debug(
        (
            f"[SITE_CRAWLER] START | url={url} | preferir_js={preferir_js} | "
            f"max_paginas={limite_paginas} | max_produtos={limite_produtos} | "
            f"max_threads={limite_threads} | precisa_login={auth_final.get('precisa_login')}"
        ),
        "INFO",
    )

    paginas_visitadas: list[str] = []
    links_produto: list[str] = []
    erros: list[str] = []
    produtos_extraidos: list[dict[str, Any]] = []

    fila_paginas: list[str] = [url]
    paginas_vistas: set[str] = set()
    produtos_vistos: set[str] = set()

    # ------------------------------------------------------
    # 1) SE A URL JÁ PARECE PRODUTO, PROCESSA DIRETO
    # ------------------------------------------------------
    if link_parece_produto_crawler(url):
        log_debug("[SITE_CRAWLER] URL inicial já parece produto", "INFO")
        resultado = _processar_produto(
            url,
            url_base=url,
            preferir_js=preferir_js or _safe_bool(auth_final.get("precisa_login")),
            auth_config=auth_final,
            estoque_padrao_disponivel=estoque_padrao_disponivel,
        )
        if resultado.get("ok") and isinstance(resultado.get("registro"), dict):
            produtos_extraidos.append(resultado["registro"])
            links_produto.append(url)
        else:
            erros.append(_safe_str(resultado.get("erro")) or "falha_produto_direto")

        df = _produtos_para_dataframe(produtos_extraidos)
        retorno = {
            "ok": not df.empty,
            "erro": "" if not df.empty else "; ".join([e for e in erros if e]),
            "produtos": produtos_extraidos,
            "df": df,
            "links_produto": links_produto,
            "paginas_visitadas": [url],
            "erros": erros,
            "stats": {
                "paginas_visitadas": 1,
                "links_produto": len(links_produto),
                "produtos_extraidos": len(produtos_extraidos),
                "login_required": _safe_bool(auth_final.get("precisa_login")),
                "auth_used": bool(_safe_str(auth_final.get("usuario")) and _safe_str(auth_final.get("senha"))),
            },
            "version": SITE_CRAWLER_VERSION,
        }

        if atualizar_streamlit_state:
            _persistir_estado_crawler(retorno)

        return retorno

    # ------------------------------------------------------
    # 2) VARREDURA DE CATEGORIAS / PAGINAÇÃO
    # ------------------------------------------------------
    while fila_paginas and len(paginas_visitadas) < limite_paginas and len(links_produto) < limite_produtos:
        url_pagina = _normalizar_url(fila_paginas.pop(0))
        if not url_pagina:
            continue
        if url_pagina in paginas_vistas:
            continue

        paginas_vistas.add(url_pagina)
        paginas_visitadas.append(url_pagina)

        if callable(progresso_callback):
            try:
                progresso_callback(
                    {
                        "fase": "paginas",
                        "pagina_atual": url_pagina,
                        "paginas_visitadas": len(paginas_visitadas),
                        "links_produto": len(links_produto),
                    }
                )
            except Exception:
                pass

        payload = _fetch_url_crawler(
            url_pagina,
            preferir_js=preferir_js or _safe_bool(auth_final.get("precisa_login")),
            auth_config=auth_final,
        )

        html = _safe_str(payload.get("html"))
        if not payload.get("ok") or not html:
            erros.append(
                f"falha_pagina::{url_pagina}::{_safe_str(payload.get('error')) or 'sem_html'}"
            )
            continue

        try:
            links_prod, links_pag = _coletar_links_categoria(html, url_pagina)
        except Exception as e:
            erros.append(f"erro_links::{url_pagina}::{e}")
            continue

        links_prod = _filtrar_links_mesmo_dominio(links_prod, url)
        links_pag = _filtrar_links_mesmo_dominio(links_pag, url)

        for lp in links_prod:
            if lp in produtos_vistos:
                continue
            produtos_vistos.add(lp)
            links_produto.append(lp)
            if len(links_produto) >= limite_produtos:
                break

        for pg in links_pag:
            if pg in paginas_vistas or pg in fila_paginas:
                continue
            fila_paginas.append(pg)

    # ------------------------------------------------------
    # 3) EXTRAÇÃO DOS PRODUTOS
    # ------------------------------------------------------
    links_produto = links_produto[:limite_produtos]

    if callable(progresso_callback):
        try:
            progresso_callback(
                {
                    "fase": "produtos",
                    "total_links_produto": len(links_produto),
                    "paginas_visitadas": len(paginas_visitadas),
                }
            )
        except Exception:
            pass

    if links_produto:
        with ThreadPoolExecutor(max_workers=limite_threads) as executor:
            futures = {
                executor.submit(
                    _processar_produto,
                    link,
                    url_base=url,
                    preferir_js=preferir_js or _safe_bool(auth_final.get("precisa_login")),
                    auth_config=auth_final,
                    estoque_padrao_disponivel=estoque_padrao_disponivel,
                ): link
                for link in links_produto
            }

            concluidos = 0
            for future in as_completed(futures):
                link = futures[future]
                concluidos += 1

                if callable(progresso_callback):
                    try:
                        progresso_callback(
                            {
                                "fase": "extraindo_produto",
                                "produto_atual": link,
                                "concluidos": concluidos,
                                "total": len(links_produto),
                            }
                        )
                    except Exception:
                        pass

                try:
                    resultado = future.result()
                except Exception as e:
                    erros.append(f"erro_future::{link}::{e}")
                    continue

                if resultado.get("ok") and isinstance(resultado.get("registro"), dict):
                    produtos_extraidos.append(resultado["registro"])
                else:
                    erros.append(
                        f"falha_produto::{link}::{_safe_str(resultado.get('erro')) or 'desconhecida'}"
                    )

    # ------------------------------------------------------
    # 4) DEDUP FINAL
    # ------------------------------------------------------
    produtos_unicos: list[dict[str, Any]] = []
    chaves_vistas: set[str] = set()

    for item in produtos_extraidos:
        codigo = _safe_str(item.get("codigo"))
        nome = _safe_str(item.get("nome"))
        url_item = _safe_str(item.get("url"))
        chave = codigo or url_item or nome

        if not chave:
            continue
        if chave in chaves_vistas:
            continue

        chaves_vistas.add(chave)
        produtos_unicos.append(item)

    df = _produtos_para_dataframe(produtos_unicos)

    retorno = {
        "ok": not df.empty,
        "erro": "" if not df.empty else ("; ".join([e for e in erros if e]) or "nenhum_produto_extraido"),
        "produtos": produtos_unicos,
        "df": df,
        "links_produto": links_produto,
        "paginas_visitadas": paginas_visitadas,
        "erros": erros,
        "stats": {
            "paginas_visitadas": len(paginas_visitadas),
            "links_produto": len(links_produto),
            "produtos_extraidos": len(produtos_unicos),
            "erros": len(erros),
            "login_required": _safe_bool(auth_final.get("precisa_login")),
            "auth_used": bool(_safe_str(auth_final.get("usuario")) and _safe_str(auth_final.get("senha"))),
        },
        "version": SITE_CRAWLER_VERSION,
    }

    if atualizar_streamlit_state:
        _persistir_estado_crawler(retorno)

    log_debug(
        (
            f"[SITE_CRAWLER] END | ok={retorno['ok']} | "
            f"paginas={retorno['stats']['paginas_visitadas']} | "
            f"links={retorno['stats']['links_produto']} | "
            f"produtos={retorno['stats']['produtos_extraidos']} | "
            f"erros={retorno['stats']['erros']}"
        ),
        "INFO",
    )

    return retorno


# ==========================================================
# STREAMLIT STATE
# ==========================================================
def _persistir_estado_crawler(resultado: dict[str, Any]) -> None:
    try:
        df = resultado.get("df")
        if isinstance(df, pd.DataFrame):
            st.session_state["df_origem"] = df.copy()
            st.session_state["df_saida"] = df.copy()
            st.session_state["df_final"] = df.copy()

        st.session_state["site_processado"] = bool(resultado.get("ok"))
        st.session_state["site_ultimo_resultado"] = resultado
    except Exception as e:
        log_debug(f"[SITE_CRAWLER] falha ao persistir estado: {e}", "WARNING")


# ==========================================================
# ALIASES DE COMPATIBILIDADE
# ==========================================================
def buscar_produtos_site(
    url: str,
    *,
    preferir_js: bool = False,
    max_paginas: int | None = None,
    max_produtos: int | None = None,
    max_threads: int | None = None,
    usuario: str = "",
    senha: str = "",
    precisa_login: bool = False,
    auth_config: dict[str, Any] | None = None,
    estoque_padrao_disponivel: int = 1,
    progresso_callback=None,
    atualizar_streamlit_state: bool = True,
) -> dict[str, Any]:
    return crawl_site_produtos(
        url=url,
        preferir_js=preferir_js,
        max_paginas=max_paginas,
        max_produtos=max_produtos,
        max_threads=max_threads,
        usuario=usuario,
        senha=senha,
        precisa_login=precisa_login,
        auth_config=auth_config,
        estoque_padrao_disponivel=estoque_padrao_disponivel,
        progresso_callback=progresso_callback,
        atualizar_streamlit_state=atualizar_streamlit_state,
    )


def buscar_produtos_site_df(
    url: str,
    *,
    preferir_js: bool = False,
    max_paginas: int | None = None,
    max_produtos: int | None = None,
    max_threads: int | None = None,
    usuario: str = "",
    senha: str = "",
    precisa_login: bool = False,
    auth_config: dict[str, Any] | None = None,
    estoque_padrao_disponivel: int = 1,
) -> pd.DataFrame:
    resultado = crawl_site_produtos(
        url=url,
        preferir_js=preferir_js,
        max_paginas=max_paginas,
        max_produtos=max_produtos,
        max_threads=max_threads,
        usuario=usuario,
        senha=senha,
        precisa_login=precisa_login,
        auth_config=auth_config,
        estoque_padrao_disponivel=estoque_padrao_disponivel,
        atualizar_streamlit_state=True,
    )
    df = resultado.get("df")
    return df if isinstance(df, pd.DataFrame) else pd.DataFrame()


def executar_crawler_site(*args, **kwargs):
    return crawl_site_produtos(*args, **kwargs)
