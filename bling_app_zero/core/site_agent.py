
from __future__ import annotations

from typing import Any

import pandas as pd

from bling_app_zero.core.site_crawler_cleaners import normalizar_url, safe_str
from bling_app_zero.core.site_crawler_extractors import extrair_detalhes_heuristicos
from bling_app_zero.core.site_crawler_gpt import gpt_extrair_produto
from bling_app_zero.core.site_crawler_http import fetch_html_retry
from bling_app_zero.core.site_crawler_links import descobrir_produtos_no_dominio
from bling_app_zero.core.site_crawler_validators import (
    pontuar_produto,
    produto_final_valido,
    titulo_valido,
)


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


def _montar_linha_saida(final: dict) -> dict:
    """
    Saída final da varredura por site.
    Mantém compatibilidade com o fluxo atual e adiciona os campos obrigatórios
    que o usuário exige: marca e descrição curta.
    """
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
    """
    Campos que, por regra do projeto, devem ser fortemente priorizados.
    Não impedimos totalmente a aprovação por todos eles, mas registramos
    claramente quando vierem vazios para diagnóstico e filtro de qualidade.
    """
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

    # url_produto, descricao e url_imagens têm peso máximo
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

    if any(x in url_n for x in ["/categoria", "/categorias", "/departamento", "/search", "/busca"]):
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

    produtos = descobrir_produtos_no_dominio(
        base_url=base_url,
        termo=termo,
        max_paginas=400,
        max_produtos=limite,
        max_segundos=900,
    )

    if not produtos:
        if status_box is not None:
            status_box.warning("Nenhum produto encontrado.")
        _log_debug("Nenhum produto encontrado na descoberta inicial do domínio.", nivel="ERRO")
        return pd.DataFrame()

    rows: list[dict] = []
    vistos: set[str] = set()
    diagnosticos: list[dict] = []

    total = len(produtos)
    _log_debug(f"Links de produto descobertos: {total}", nivel="INFO")

    for i, url_produto in enumerate(produtos, start=1):
        url_produto = safe_str(url_produto)

        _atualizar_progresso(
            i=i,
            total=total,
            url_produto=url_produto,
            fase="🌐 Acessando página do produto...",
            progress_bar=progress_bar,
            status_box=status_box,
            contador_box=contador_box,
        )

        if not url_produto:
            if diagnostico:
                _registrar_diag(
                    diagnosticos,
                    url_produto=url_produto,
                    status="rejeitado",
                    motivo="url_vazia",
                )
            continue

        if url_produto in vistos:
            if diagnostico:
                _registrar_diag(
                    diagnosticos,
                    url_produto=url_produto,
                    status="rejeitado",
                    motivo="url_duplicada",
                )
            continue

        try:
            html_produto = fetch_html_retry(url_produto, tentativas=2)
        except Exception as exc:
            if diagnostico:
                _registrar_diag(
                    diagnosticos,
                    url_produto=url_produto,
                    status="erro",
                    motivo="erro_fetch_html",
                    erro=str(exc),
                )
            _log_debug(f"Erro ao buscar HTML do produto: {url_produto} | {exc}", nivel="ERRO")
            continue

        _atualizar_progresso(
            i=i,
            total=total,
            url_produto=url_produto,
            fase="🔎 Extraindo dados heurísticos...",
            progress_bar=progress_bar,
            status_box=status_box,
            contador_box=contador_box,
        )

        try:
            heuristica = extrair_detalhes_heuristicos(url_produto, html_produto)
        except Exception as exc:
            if diagnostico:
                _registrar_diag(
                    diagnosticos,
                    url_produto=url_produto,
                    status="erro",
                    motivo="erro_extracao_heuristica",
                    erro=str(exc),
                )
            _log_debug(f"Erro na extração heurística: {url_produto} | {exc}", nivel="ERRO")
            continue

        _atualizar_progresso(
            i=i,
            total=total,
            url_produto=url_produto,
            fase="🧠 Refinando com GPT...",
            progress_bar=progress_bar,
            status_box=status_box,
            contador_box=contador_box,
        )

        try:
            final = gpt_extrair_produto(url_produto, html_produto, heuristica)
        except Exception as exc:
            if diagnostico:
                _registrar_diag(
                    diagnosticos,
                    url_produto=url_produto,
                    heuristica=heuristica,
                    status="erro",
                    motivo="erro_gpt",
                    erro=str(exc),
                )
            _log_debug(f"Erro no refinamento GPT: {url_produto} | {exc}", nivel="ERRO")
            continue

        # Blindagem final dos campos obrigatórios
        final["descricao_curta"] = _descricao_curta_padrao(final)
        final["quantidade"] = _quantidade_padrao(final)
        final["url_produto"] = safe_str(final.get("url_produto")) or url_produto
        final["descricao"] = safe_str(final.get("descricao")) or safe_str(heuristica.get("descricao"))
        final["categoria"] = safe_str(final.get("categoria")) or safe_str(heuristica.get("categoria"))
        final["marca"] = safe_str(final.get("marca")) or safe_str(heuristica.get("marca"))
        final["url_imagens"] = safe_str(final.get("url_imagens")) or safe_str(heuristica.get("url_imagens"))
        final["codigo"] = safe_str(final.get("codigo")) or safe_str(heuristica.get("codigo"))
        final["gtin"] = safe_str(final.get("gtin")) or safe_str(heuristica.get("gtin"))
        final["ncm"] = safe_str(final.get("ncm")) or safe_str(heuristica.get("ncm"))
        final["preco"] = safe_str(final.get("preco")) or safe_str(heuristica.get("preco"))

        campos_ok, faltando = _campos_criticos_ok(final)
        if faltando:
            _log_debug(
                f"Produto com campos críticos faltando | url={url_produto} | faltando={', '.join(faltando)}",
                nivel="ERRO" if not campos_ok else "INFO",
            )

        if not produto_final_valido(final):
            if diagnostico:
                _registrar_diag(
                    diagnosticos,
                    url_produto=url_produto,
                    heuristica=heuristica,
                    gpt=final,
                    final=final,
                    status="rejeitado",
                    motivo=_motivo_rejeicao(final),
                )
            continue

        # Mesmo produto válido, se faltar campo duro crítico, reprova
        if not campos_ok:
            if diagnostico:
                _registrar_diag(
                    diagnosticos,
                    url_produto=url_produto,
                    heuristica=heuristica,
                    gpt=final,
                    final=final,
                    status="rejeitado",
                    motivo=_motivo_rejeicao(final),
                )
            continue

        rows.append(_montar_linha_saida(final))
        vistos.add(url_produto)

        if diagnostico:
            _registrar_diag(
                diagnosticos,
                url_produto=url_produto,
                heuristica=heuristica,
                gpt=final,
                final=final,
                status="aprovado",
                motivo="produto_valido",
            )

        if status_box is not None:
            status_box.success(f"✅ Produto validado\n\n{url_produto}")

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
    
