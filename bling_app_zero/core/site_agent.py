
from __future__ import annotations

import concurrent.futures
import re
import threading
import time
from typing import Any

import pandas as pd


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


# ============================================================
# HELPERS GERAIS
# ============================================================

def _streamlit_ctx():
    try:
        import streamlit as st
        return st
    except Exception:
        return None


def _log_debug(msg: str, nivel: str = "INFO") -> None:
    try:
        from bling_app_zero.ui.app_helpers import log_debug  # type: ignore
        log_debug(msg, nivel=nivel)
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
    if any(x in descricao for x in ["sem estoque", "indisponível", "indisponivel", "esgotado", "zerado"]):
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

    if any(x in url_n for x in ["/categoria", "/categorias", "/departamento", "/search", "/busca", "/pagina/"]):
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


def _atualizar_progresso(
    i: int,
    total: int,
    url_produto: str,
    fase: str,
    progress_bar,
    status_box,
    contador_box,
) -> None:
    st = _streamlit_ctx()
    if st is None:
        return

    if total <= 0:
        total = 1

    percentual = int((i / total) * 100)
    percentual = max(0, min(percentual, 100))

    if progress_bar is not None:
        progress_bar.progress(percentual)

    if contador_box is not None:
        contador_box.write(f"Processando {i} de {total}")

    if status_box is not None:
        status_box.info(f"{fase}\n\n{safe_str(url_produto)}")


# ============================================================
# FALLBACKS PRO
# ============================================================

def _executar_fetch_html(url_produto: str) -> str:
    if fetch_html_retry is None:
        return ""

    ultima_exc: Exception | None = None
    for tentativas in (2, 3):
        try:
            return safe_str(fetch_html_retry(url_produto, tentativas=tentativas))
        except Exception as exc:
            ultima_exc = exc

    if ultima_exc is not None:
        raise ultima_exc

    return ""


def _executar_heuristica(url_produto: str, html_produto: str) -> dict[str, Any]:
    if extrair_detalhes_heuristicos is None:
        return {}

    try:
        dados = extrair_detalhes_heuristicos(url_produto, html_produto)
        return dados if isinstance(dados, dict) else {}
    except Exception:
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
        except Exception:
            continue

    return ultimo_resultado


def _resolver_final(url_produto: str, heuristica: dict[str, Any], gpt: dict[str, Any]) -> dict[str, Any]:
    final = {}

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

    final["url_produto"] = safe_str(gpt.get("url_produto")) or safe_str(heuristica.get("url_produto")) or url_produto
    final["descricao"] = safe_str(final.get("descricao")) or safe_str(heuristica.get("titulo")) or safe_str(heuristica.get("nome"))
    final["descricao_curta"] = _descricao_curta_padrao(final)
    final["quantidade"] = _quantidade_padrao(final)
    final["marca"] = _resolver_marca(final, heuristica)

    return final


def _processar_um_produto(
    url_produto: str,
    diagnostico: bool = False,
) -> tuple[str, dict[str, Any]]:
    url_produto = safe_str(url_produto)

    if not url_produto:
        return "rejeitado", {
            "url_produto": url_produto,
            "motivo": "url_vazia",
        }

    try:
        html_produto = _executar_fetch_html(url_produto)
    except Exception as exc:
        return "erro", {
            "url_produto": url_produto,
            "motivo": "erro_fetch_html",
            "erro": str(exc),
        }

    heuristica = _executar_heuristica(url_produto, html_produto)
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


# ============================================================
# FUNÇÃO PRINCIPAL
# ============================================================

def buscar_produtos_site_com_gpt(
    base_url: str,
    termo: str = "",
    limite_links: int | None = None,
    diagnostico: bool = False,
) -> pd.DataFrame:
    st = _streamlit_ctx()

    base_url = normalizar_url(base_url)
    termo = safe_str(termo)

    if not base_url:
        _log_debug("Busca por site cancelada: base_url vazia.", nivel="ERRO")
        return pd.DataFrame()

    if descobrir_produtos_no_dominio is None:
        _log_debug("Busca por site indisponível: descobrir_produtos_no_dominio não carregado.", nivel="ERRO")
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

    _log_debug(
        f"Iniciando busca por site | url={base_url} | termo={termo or '-'} | limite={limite}",
        nivel="INFO",
    )

    try:
        produtos = descobrir_produtos_no_dominio(
            base_url=base_url,
            termo=termo,
            max_paginas=400,
            max_produtos=limite,
            max_segundos=900,
        )
    except Exception as exc:
        if status_box is not None:
            status_box.error(f"Falha ao descobrir produtos no domínio: {exc}")
        _log_debug(f"Falha na descoberta inicial do domínio: {exc}", nivel="ERRO")
        return pd.DataFrame()

    if not produtos:
        if status_box is not None:
            status_box.warning("Nenhum produto encontrado.")
        _log_debug("Nenhum produto encontrado na descoberta inicial do domínio.", nivel="ERRO")
        return pd.DataFrame()

    produtos_limpos = []
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

    _log_debug(f"Links de produto descobertos: {total}", nivel="INFO")

    workers = _max_workers(total)

    def worker(idx_url: tuple[int, str]) -> None:
        i, url_produto = idx_url

        _atualizar_progresso(
            i=i,
            total=total,
            url_produto=url_produto,
            fase="🌐 Acessando / extraindo produto...",
            progress_bar=progress_bar,
            status_box=status_box,
            contador_box=contador_box,
        )

        status, payload = _processar_um_produto(url_produto=url_produto, diagnostico=diagnostico)

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
                    return
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

            if status_box is not None:
                status_box.success(f"✅ Produto validado\n\n{url_produto}")
            return

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

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        list(executor.map(worker, enumerate(produtos, start=1)))

    if progress_bar is not None:
        progress_bar.progress(100)

    if status_box is not None:
        status_box.success("🎉 Busca finalizada.")

    if diagnostico:
        _salvar_diagnostico_em_sessao(
            diagnosticos=diagnosticos,
            produtos_descobertos=produtos,
            rows_validos=rows,
        )

    _log_debug(
        f"Busca por site finalizada | descobertos={len(produtos)} | validos={len(rows)} | rejeitados={max(len(produtos) - len(rows), 0)}",
        nivel="INFO",
    )

    return _df_saida(rows)

