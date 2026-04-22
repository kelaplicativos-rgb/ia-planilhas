
from __future__ import annotations

import json
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import (
    blindar_df_para_bling,
    dataframe_para_csv_bytes,
    get_etapa,
    ir_para_etapa,
    log_debug,
    normalizar_imagens_pipe,
    normalizar_texto,
    safe_df_estrutura,
    safe_lower,
    sincronizar_etapa_global,
    validar_df_para_download,
    voltar_etapa_anterior,
)


def _garantir_etapa_preview_ativa() -> None:
    if get_etapa() != "preview_final":
        sincronizar_etapa_global("preview_final")
    st.session_state["_etapa_url_inicializada"] = True
    st.session_state["_ultima_etapa_sincronizada_url"] = "preview_final"


def _safe_import_bling_auth():
    try:
        from bling_app_zero.core.bling_auth import (
            obter_resumo_conexao,
            render_conectar_bling,
            tem_token_valido,
            usuario_conectado_bling,
        )
        return {
            "obter_resumo_conexao": obter_resumo_conexao,
            "render_conectar_bling": render_conectar_bling,
            "tem_token_valido": tem_token_valido,
            "usuario_conectado_bling": usuario_conectado_bling,
        }
    except Exception:
        return None


def _safe_import_bling_sync():
    try:
        from bling_app_zero.services.bling import bling_sync  # type: ignore
        return bling_sync
    except Exception:
        return None


def _normalizar_df_visual(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()

    base = df.copy().fillna("")
    for col in base.columns:
        nome = str(col).strip().lower()
        if nome in {"url imagens", "url imagem", "imagens", "imagem"} or "imagem" in nome:
            base[col] = base[col].apply(normalizar_imagens_pipe)

    return base


def _obter_df_final_exclusivo() -> pd.DataFrame:
    df = st.session_state.get("df_final")
    if safe_df_estrutura(df):
        return df.copy()
    return pd.DataFrame()


def _coluna_por_match_ou_parcial(df: pd.DataFrame, exatos: list[str], parciais: list[str]) -> str:
    if not isinstance(df, pd.DataFrame) or len(df.columns) == 0:
        return ""

    mapa = {normalizar_texto(c): str(c) for c in df.columns}

    for nome in exatos:
        achado = mapa.get(normalizar_texto(nome))
        if achado:
            return achado

    for col in df.columns:
        nome_col = normalizar_texto(col)
        if any(parcial in nome_col for parcial in parciais):
            return str(col)

    return ""


def _coluna_codigo(df: pd.DataFrame) -> str:
    return _coluna_por_match_ou_parcial(
        df,
        ["Código", "codigo", "Código do produto", "SKU", "Sku", "sku"],
        ["codigo", "código", "cod", "sku", "referencia", "referência", "id produto"],
    )


def _coluna_descricao(df: pd.DataFrame) -> str:
    return _coluna_por_match_ou_parcial(
        df,
        ["Descrição", "descricao", "Descrição do produto", "Nome", "nome", "Título", "titulo"],
        ["descricao", "descrição", "nome", "titulo", "título", "produto"],
    )


def _coluna_preco(df: pd.DataFrame) -> str:
    return _coluna_por_match_ou_parcial(
        df,
        [
            "Preço de venda",
            "Preço unitário (OBRIGATÓRIO)",
            "Preço calculado",
            "Preço",
            "preco",
            "preço",
        ],
        ["preco", "preço", "valor", "unitario", "unitário", "venda"],
    )


def _coluna_gtin(df: pd.DataFrame) -> str:
    return _coluna_por_match_ou_parcial(
        df,
        ["GTIN/EAN", "GTIN", "EAN", "gtin", "ean"],
        ["gtin", "ean", "codigo de barras", "código de barras"],
    )


def _serie_texto_limpa(df: pd.DataFrame, coluna: str) -> pd.Series:
    if not isinstance(df, pd.DataFrame) or not coluna or coluna not in df.columns:
        return pd.Series(dtype="object")

    return (
        df[coluna]
        .astype(str)
        .str.strip()
        .replace({"nan": "", "None": "", "none": ""})
    )


def _garantir_coluna_codigo_canonica(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()

    base = df.copy().fillna("")
    candidatos = [
        "Código",
        "codigo",
        "Código do produto",
        "SKU",
        "Sku",
        "sku",
        "ID Produto",
        "Id Produto",
        "ID do Produto",
        "Referencia",
        "Referência",
        "Ref",
    ]

    coluna_origem = _coluna_por_match_ou_parcial(
        base,
        candidatos,
        ["codigo", "código", "sku", "referencia", "referência", "id produto", "id do produto"],
    )

    if "Código" not in base.columns:
        base["Código"] = ""

    serie_codigo = _serie_texto_limpa(base, "Código")
    if serie_codigo.empty or serie_codigo.eq("").all():
        if coluna_origem and coluna_origem in base.columns:
            serie_origem = _serie_texto_limpa(base, coluna_origem)
            if not serie_origem.empty and not serie_origem.eq("").all():
                base["Código"] = serie_origem
                log_debug(f"Coluna canônica Código criada a partir de: {coluna_origem}", nivel="INFO")

    serie_codigo = _serie_texto_limpa(base, "Código")
    if serie_codigo.empty or serie_codigo.eq("").all():
        base["Código"] = [f"PROD_{i+1:05d}" for i in range(len(base.index))]
        log_debug("Código automático gerado no preview final por ausência de coluna válida.", nivel="INFO")

    return base.fillna("")


def _garantir_coluna_descricao_canonica(df: pd.DataFrame, tipo_operacao: str) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()

    base = df.copy().fillna("")
    operacao = normalizar_texto(tipo_operacao) or "cadastro"

    candidatos_exatos = [
        "Descrição",
        "descricao",
        "Descrição do produto",
        "Nome",
        "nome",
        "Título",
        "titulo",
        "Descrição Curta",
        "Descricao Curta",
    ]
    coluna_descricao = _coluna_por_match_ou_parcial(
        base,
        candidatos_exatos,
        ["descricao", "descrição", "nome", "titulo", "título"],
    )
    coluna_codigo = _coluna_por_match_ou_parcial(
        base,
        ["Código", "codigo", "Código do produto", "SKU", "Sku", "sku", "ID Produto", "Id Produto"],
        ["codigo", "código", "sku", "referencia", "referência", "id produto"],
    )

    if "Descrição" not in base.columns:
        base["Descrição"] = ""

    serie_desc = _serie_texto_limpa(base, "Descrição")
    if serie_desc.empty or serie_desc.eq("").all():
        if coluna_descricao and coluna_descricao in base.columns and coluna_descricao != coluna_codigo:
            serie_origem = _serie_texto_limpa(base, coluna_descricao)
            if not serie_origem.empty and not serie_origem.eq("").all():
                base["Descrição"] = serie_origem
                log_debug(f"Coluna canônica Descrição criada a partir de: {coluna_descricao}", nivel="INFO")

    serie_desc = _serie_texto_limpa(base, "Descrição")
    serie_codigo = _serie_texto_limpa(base, "Código") if "Código" in base.columns else pd.Series(dtype="object")

    if operacao == "estoque":
        precisa_fallback = serie_desc.empty or serie_desc.eq("").all() or (
            not serie_codigo.empty and serie_desc.equals(serie_codigo)
        )
        if precisa_fallback:
            base["Descrição"] = [
                f"Produto {codigo}" if str(codigo).strip() else f"Produto {i+1}"
                for i, codigo in enumerate(serie_codigo.tolist() or [""] * len(base.index))
            ]
            log_debug("Descrição canônica gerada automaticamente no preview final para operação de estoque.", nivel="INFO")

    return base.fillna("")


def _garantir_coluna_descricao_curta_canonica(df: pd.DataFrame, tipo_operacao: str) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()

    base = df.copy().fillna("")
    operacao = normalizar_texto(tipo_operacao) or "cadastro"

    coluna_curta = _coluna_por_match_ou_parcial(
        base,
        ["Descrição Curta", "Descricao Curta"],
        ["descricao curta", "descrição curta"],
    )
    coluna_descricao = _coluna_por_match_ou_parcial(
        base,
        ["Descrição", "descricao", "Descrição do produto", "Nome", "nome", "Título", "titulo"],
        ["descricao", "descrição", "nome", "titulo", "título"],
    )

    if "Descrição Curta" not in base.columns:
        base["Descrição Curta"] = ""

    serie_curta = _serie_texto_limpa(base, "Descrição Curta")
    if serie_curta.empty or serie_curta.eq("").all():
        if coluna_curta and coluna_curta in base.columns and coluna_curta != "Descrição Curta":
            serie_origem = _serie_texto_limpa(base, coluna_curta)
            if not serie_origem.empty and not serie_origem.eq("").all():
                base["Descrição Curta"] = serie_origem
                log_debug(f"Coluna canônica Descrição Curta criada a partir de: {coluna_curta}", nivel="INFO")

    serie_curta = _serie_texto_limpa(base, "Descrição Curta")
    if serie_curta.empty or serie_curta.eq("").all():
        if coluna_descricao and coluna_descricao in base.columns:
            serie_desc = _serie_texto_limpa(base, coluna_descricao)
            if not serie_desc.empty and not serie_desc.eq("").all():
                base["Descrição Curta"] = serie_desc
                log_debug("Descrição Curta preenchida automaticamente a partir da Descrição.", nivel="INFO")

    serie_curta = _serie_texto_limpa(base, "Descrição Curta")
    if serie_curta.empty or serie_curta.eq("").all():
        coluna_codigo = _coluna_codigo(base)
        serie_codigo = _serie_texto_limpa(base, coluna_codigo) if coluna_codigo else pd.Series(dtype="object")

        if operacao == "estoque":
            base["Descrição Curta"] = [
                f"Produto {codigo}" if str(codigo).strip() else f"Produto {i+1}"
                for i, codigo in enumerate(serie_codigo.tolist() or [""] * len(base.index))
            ]
        else:
            base["Descrição Curta"] = [f"Produto {i+1}" for i in range(len(base.index))]

        log_debug("Descrição Curta gerada automaticamente no preview final por ausência de valor válido.", nivel="INFO")

    return base.fillna("")


def _garantir_df_final_canonico(df: pd.DataFrame, tipo_operacao: str, deposito_nome: str) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()

    base = _normalizar_df_visual(df)
    base = blindar_df_para_bling(
        df=base,
        tipo_operacao_bling=tipo_operacao,
        deposito_nome=deposito_nome,
    )
    base = _garantir_coluna_codigo_canonica(base)
    base = _garantir_coluna_descricao_canonica(base, tipo_operacao)
    base = _garantir_coluna_descricao_curta_canonica(base, tipo_operacao)

    return base.fillna("")


def _contar_preenchidos(df: pd.DataFrame, coluna: str) -> int:
    if not safe_df_estrutura(df) or not coluna or coluna not in df.columns:
        return 0

    return int(
        df[coluna]
        .astype(str)
        .str.strip()
        .replace({"nan": "", "None": "", "none": ""})
        .ne("")
        .sum()
    )


def _montar_resumo(df: pd.DataFrame) -> dict[str, Any]:
    codigo_col = _coluna_codigo(df)
    descricao_col = _coluna_descricao(df)
    preco_col = _coluna_preco(df)
    gtin_col = _coluna_gtin(df)

    return {
        "linhas": int(len(df.index)) if isinstance(df, pd.DataFrame) else 0,
        "colunas": int(len(df.columns)) if isinstance(df, pd.DataFrame) else 0,
        "codigo_col": codigo_col,
        "descricao_col": descricao_col,
        "preco_col": preco_col,
        "gtin_col": gtin_col,
        "codigo_ok": _contar_preenchidos(df, codigo_col),
        "descricao_ok": _contar_preenchidos(df, descricao_col),
        "preco_ok": _contar_preenchidos(df, preco_col),
        "gtin_ok": _contar_preenchidos(df, gtin_col),
    }


def _origem_site_ativa() -> bool:
    modo_origem = safe_lower(st.session_state.get("modo_origem", ""))
    origem_tipo = safe_lower(st.session_state.get("origem_upload_tipo", ""))
    origem_nome = safe_lower(st.session_state.get("origem_upload_nome", ""))

    return (
        "site" in modo_origem
        or "site_gpt" in origem_tipo
        or "varredura_site_" in origem_nome
        or "site_" in origem_nome
    )


def _url_site_atual() -> str:
    return str(st.session_state.get("site_fornecedor_url", "") or "").strip()


def _varredura_site_concluida() -> bool:
    if not _origem_site_ativa():
        return False

    df_origem = st.session_state.get("df_origem")
    return isinstance(df_origem, pd.DataFrame) and not df_origem.empty


def _oauth_liberado(validacao_ok: bool) -> bool:
    return bool(
        validacao_ok
        and st.session_state.get("preview_download_realizado", False)
        and (not _origem_site_ativa() or _varredura_site_concluida())
    )


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


def _obter_deposito_nome_persistido() -> str:
    candidatos = [
        st.session_state.get("deposito_nome"),
        st.session_state.get("deposito_nome_widget"),
        st.session_state.get("deposito"),
    ]
    for valor in candidatos:
        texto = str(valor or "").strip()
        if texto:
            return texto
    return ""


def _sincronizar_deposito_nome() -> str:
    deposito = _obter_deposito_nome_persistido()
    st.session_state["deposito_nome"] = deposito
    st.session_state["deposito_nome_widget"] = deposito
    return deposito


def _resumo_rotina_site() -> dict[str, Any]:
    return {
        "origem_site_ativa": _origem_site_ativa(),
        "url_site": _url_site_atual(),
        "fonte_descoberta": _fonte_descoberta_label(st.session_state.get("site_busca_fonte_descoberta", "")),
        "diagnostico_descobertos": int(st.session_state.get("site_busca_diagnostico_total_descobertos", 0) or 0),
        "diagnostico_validos": int(st.session_state.get("site_busca_diagnostico_total_validos", 0) or 0),
        "diagnostico_rejeitados": int(st.session_state.get("site_busca_diagnostico_total_rejeitados", 0) or 0),
        "auto_mode": st.session_state.get("bling_sync_auto_mode", "manual"),
        "interval_value": st.session_state.get("bling_sync_interval_value", 15),
        "interval_unit": st.session_state.get("bling_sync_interval_unit", "minutos"),
        "loop_ativo": bool(st.session_state.get("site_auto_loop_ativo", False)),
        "loop_status": str(st.session_state.get("site_auto_status", "inativo") or "inativo"),
        "ultima_execucao": str(st.session_state.get("site_auto_ultima_execucao", "") or ""),
    }


def _inicializar_estado_preview() -> None:
    defaults = {
        "bling_sync_strategy": "inteligente",
        "bling_sync_auto_mode": "manual",
        "bling_sync_interval_value": 15,
        "bling_sync_interval_unit": "minutos",
        "bling_conectado": False,
        "bling_status_texto": "Desconectado",
        "bling_envio_resultado": None,
        "preview_download_realizado": False,
        "preview_validacao_ok": False,
        "preview_hash_df_final": "",
        "preview_envio_em_execucao": False,
        "preview_envio_logs": [],
        "preview_envio_resumo": {},
    }
    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


def _hash_df_visual(df: pd.DataFrame) -> str:
    try:
        if not isinstance(df, pd.DataFrame):
            return ""

        partes = ["|".join([str(c) for c in df.columns.tolist()])]
        amostra = df.head(30).fillna("").astype(str)
        for _, row in amostra.iterrows():
            partes.append("|".join(row.tolist()))
        return str(hash("\n".join(partes)))
    except Exception:
        return ""


def _resetar_status_envio_visual() -> None:
    st.session_state["preview_envio_em_execucao"] = False
    st.session_state["preview_envio_logs"] = []
    st.session_state["preview_envio_resumo"] = {}


def _sincronizar_estado_quando_df_mudar(df_final: pd.DataFrame) -> None:
    hash_atual = _hash_df_visual(df_final)
    hash_anterior = str(st.session_state.get("preview_hash_df_final", "") or "")

    if hash_atual != hash_anterior:
        st.session_state["preview_download_realizado"] = False
        st.session_state["bling_envio_resultado"] = None
        st.session_state["preview_hash_df_final"] = hash_atual
        _resetar_status_envio_visual()
        log_debug("df_final alterado no preview; confirmação de download e resultado de envio foram resetados.", nivel="INFO")


def _obter_status_conexao_bling() -> tuple[bool, str]:
    bling_auth = _safe_import_bling_auth()
    if bling_auth is None:
        return False, "OAuth indisponível"

    try:
        obter_resumo_conexao = bling_auth.get("obter_resumo_conexao")
        if callable(obter_resumo_conexao):
            resumo = obter_resumo_conexao()
            conectado = bool(resumo.get("conectado", False))
            status = str(resumo.get("status", "Desconectado") or "Desconectado")
            return conectado, status

        usuario_conectado_bling = bling_auth.get("usuario_conectado_bling")
        tem_token_valido = bling_auth.get("tem_token_valido")
        if callable(usuario_conectado_bling) and callable(tem_token_valido):
            conectado = bool(usuario_conectado_bling()) and bool(tem_token_valido())
            return conectado, "Conectado" if conectado else "Desconectado"
    except Exception as exc:
        log_debug(f"Falha ao obter status da conexão Bling: {exc}", nivel="ERRO")

    return False, "Desconectado"


def _render_conexao_bling(liberado: bool) -> None:
    if not liberado:
        st.warning(
            "A conexão com o Bling só é liberada depois que o resultado final estiver validado, "
            "o download for confirmado e, quando for origem por site, a varredura estiver concluída."
        )
        return

    bling_auth = _safe_import_bling_auth()
    if bling_auth is None:
        st.error("Módulo de autenticação do Bling não disponível nesta execução.")
        return

    render_conectar_bling = bling_auth.get("render_conectar_bling")
    if callable(render_conectar_bling):
        try:
            render_conectar_bling()
            return
        except Exception as exc:
            st.error(f"Falha ao renderizar conexão com o Bling: {exc}")
            log_debug(f"Falha ao renderizar conexão com o Bling: {exc}", nivel="ERRO")
            return

    st.error("Função de conexão OAuth do Bling não encontrada.")


def _append_envio_log(msg: str) -> None:
    logs = list(st.session_state.get("preview_envio_logs", []))
    logs.append(msg)
    st.session_state["preview_envio_logs"] = logs[-50:]


def _enviar_para_bling(df_final: pd.DataFrame, tipo_operacao: str, deposito_nome: str) -> None:
    estrategia = st.session_state.get("bling_sync_strategy", "inteligente")
    auto_mode = st.session_state.get("bling_sync_auto_mode", "manual")
    interval_value = st.session_state.get("bling_sync_interval_value", 15)
    interval_unit = st.session_state.get("bling_sync_interval_unit", "minutos")

    bling_sync = _safe_import_bling_sync()
    if bling_sync is None:
        st.error("Serviço de sincronização do Bling não foi carregado.")
        return

    st.session_state["preview_envio_em_execucao"] = True
    st.session_state["bling_envio_resultado"] = None
    st.session_state["preview_envio_resumo"] = {
        "total": int(len(df_final)),
        "processados": 0,
        "criados": 0,
        "atualizados": 0,
        "ignorados": 0,
        "erros": 0,
        "status_texto": "Preparando envio...",
    }
    st.session_state["preview_envio_logs"] = []

    box_status = st.empty()
    box_metricas = st.empty()
    box_log = st.empty()
    progress = st.progress(0)

    def _render_metricas() -> None:
        resumo = st.session_state.get("preview_envio_resumo", {})
        with box_metricas.container():
            c1, c2, c3, c4, c5 = st.columns(5)
            with c1:
                st.metric("Total", int(resumo.get("total", 0) or 0))
            with c2:
                st.metric("Processados", int(resumo.get("processados", 0) or 0))
            with c3:
                st.metric("Criados", int(resumo.get("criados", 0) or 0))
            with c4:
                st.metric("Atualizados", int(resumo.get("atualizados", 0) or 0))
            with c5:
                st.metric("Erros", int(resumo.get("erros", 0) or 0))

    def _render_logs() -> None:
        logs = list(st.session_state.get("preview_envio_logs", []))
        if logs:
            box_log.code("\n".join(logs[-12:]), language="text")

    def _status_callback(evento: dict[str, Any]) -> None:
        fase = str(evento.get("phase", "") or "")
        resumo = dict(st.session_state.get("preview_envio_resumo", {}))
        total = int(evento.get("total", resumo.get("total", 0) or 0))
        processados = int(evento.get("processed", resumo.get("processados", 0) or 0))

        resumo["total"] = total or resumo.get("total", 0)
        resumo["processados"] = processados
        resumo["criados"] = int(evento.get("total_criados", resumo.get("criados", 0) or 0))
        resumo["atualizados"] = int(evento.get("total_atualizados", resumo.get("atualizados", 0) or 0))
        resumo["ignorados"] = int(evento.get("total_ignorados", resumo.get("ignorados", 0) or 0))
        resumo["erros"] = int(evento.get("total_erros", resumo.get("erros", 0) or 0))

        if fase == "start":
            resumo["status_texto"] = "Iniciando envio real ao Bling..."
            box_status.info(resumo["status_texto"])
            progress.progress(0)
        elif fase == "item_start":
            codigo = str(evento.get("codigo", "") or "").strip()
            descricao = str(evento.get("descricao", "") or "").strip()
            resumo["status_texto"] = f"Enviando {int(evento.get('index', 0))}/{total} • {codigo or descricao or 'item sem identificação'}"
            box_status.info(resumo["status_texto"])
            percentual = int(((max(processados, 0)) / max(total, 1)) * 100)
            progress.progress(min(percentual, 100))
        elif fase == "item_result":
            item = evento.get("item", {}) or {}
            status_item = str(item.get("status", "") or "").strip().upper()
            codigo = str(item.get("codigo", "") or "").strip()
            mensagem = str(item.get("mensagem", "") or "").strip()
            resumo["status_texto"] = f"Processado {processados}/{total}"
            box_status.info(resumo["status_texto"])
            percentual = int((processados / max(total, 1)) * 100)
            progress.progress(min(percentual, 100))
            _append_envio_log(f"[{status_item}] {codigo or 'SEM-CODIGO'} - {mensagem}")
        elif fase == "finish":
            summary = evento.get("summary", {}) or {}
            resumo["status_texto"] = str(summary.get("mensagem", "") or "Envio finalizado.")
            resumo["processados"] = int(summary.get("total_processados", resumo.get("processados", 0) or 0))
            resumo["criados"] = int(summary.get("total_criados", resumo.get("criados", 0) or 0))
            resumo["atualizados"] = int(summary.get("total_atualizados", resumo.get("atualizados", 0) or 0))
            resumo["ignorados"] = int(summary.get("total_ignorados", resumo.get("ignorados", 0) or 0))
            resumo["erros"] = int(summary.get("total_erros", resumo.get("erros", 0) or 0))
            progress.progress(100)

            if str(summary.get("modo", "") or "") == "real":
                if bool(summary.get("ok", False)):
                    box_status.success(resumo["status_texto"])
                else:
                    box_status.warning(resumo["status_texto"])
            else:
                box_status.error("Envio não foi real. O sistema caiu em simulação.")

        st.session_state["preview_envio_resumo"] = resumo
        _render_metricas()
        _render_logs()

    try:
        resultado = bling_sync.sincronizar_produtos_bling(
            df_final=df_final.copy(),
            tipo_operacao=tipo_operacao,
            deposito_nome=deposito_nome,
            strategy=estrategia,
            auto_mode=auto_mode,
            interval_value=interval_value,
            interval_unit=interval_unit,
            dry_run=False,
            status_callback=_status_callback,
        )
        st.session_state["bling_envio_resultado"] = resultado
        st.session_state["preview_envio_em_execucao"] = False

        if bool(resultado.get("ok", False)) and str(resultado.get("modo", "")) == "real":
            st.success("Envio real ao Bling executado com sucesso.")
            log_debug("Envio real ao Bling executado com sucesso.", nivel="INFO")
        elif str(resultado.get("modo", "")) != "real":
            st.error("O envio terminou em simulação. Verifique a conexão OAuth/token antes de reenviar.")
            log_debug(
                f"Envio terminou em simulação: {json.dumps(resultado, ensure_ascii=False)}",
                nivel="ERRO",
            )
        else:
            st.warning("O envio foi executado, mas retornou alertas ou erros.")
            log_debug(
                f"Envio ao Bling retornou alertas/erros: {json.dumps(resultado, ensure_ascii=False)}",
                nivel="ERRO",
            )
    except Exception as exc:
        st.session_state["preview_envio_em_execucao"] = False
        st.session_state["bling_envio_resultado"] = {
            "ok": False,
            "modo": "erro_execucao",
            "mensagem": str(exc),
            "tipo_operacao": tipo_operacao,
            "deposito_nome": deposito_nome,
            "site_fallback": _resumo_rotina_site(),
        }
        box_status.error(f"Falha no envio ao Bling: {exc}")
        log_debug(f"Falha no envio ao Bling: {exc}", nivel="ERRO")


def _render_origem_site_metadata() -> None:
    with st.expander("Origem da descoberta", expanded=False):
        if not _origem_site_ativa():
            st.caption("A origem atual não veio da busca por site do fornecedor.")
            return

        url_site = _url_site_atual()
        fonte = _fonte_descoberta_label(st.session_state.get("site_busca_fonte_descoberta", ""))
        total_descobertos = int(st.session_state.get("site_busca_diagnostico_total_descobertos", 0) or 0)
        total_validos = int(st.session_state.get("site_busca_diagnostico_total_validos", 0) or 0)
        total_rejeitados = int(st.session_state.get("site_busca_diagnostico_total_rejeitados", 0) or 0)

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Fonte descoberta", fonte)
        with c2:
            st.metric("Descobertos", total_descobertos)
        with c3:
            st.metric("Válidos", total_validos)
        with c4:
            st.metric("Rejeitados", total_rejeitados)

        if url_site:
            st.write(f"**URL monitorada:** {url_site}")


def _render_resumo_validacao(df_final: pd.DataFrame, tipo_operacao: str) -> tuple[bool, list[str]]:
    df_final = _garantir_df_final_canonico(
        df=df_final,
        tipo_operacao=tipo_operacao,
        deposito_nome=_obter_deposito_nome_persistido(),
    )
    resumo = _montar_resumo(df_final)
    valido, erros = validar_df_para_download(df_final, tipo_operacao)
    st.session_state["preview_validacao_ok"] = bool(valido)

    st.markdown("### Validação do resultado final")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Linhas", resumo["linhas"])
    with c2:
        st.metric("Colunas", resumo["colunas"])
    with c3:
        st.metric("Com código", resumo["codigo_ok"])
    with c4:
        st.metric("Com descrição", resumo["descricao_ok"])

    c5, c6, c7 = st.columns(3)
    with c5:
        st.metric("Com preço", resumo["preco_ok"])
    with c6:
        st.metric("Com GTIN", resumo["gtin_ok"])
    with c7:
        st.metric("Validação", "OK" if valido else "Ajustes pendentes")

    if erros:
        st.error("Existem pendências obrigatórias antes do download e do envio.")
        for erro in erros:
            st.write(f"- {erro}")
        log_debug(f"Validação final com pendências: {' | '.join(erros)}", nivel="ERRO")
    else:
        st.success("A planilha final passou na validação principal.")
        log_debug("Validação final aprovada.", nivel="INFO")

    return valido, erros


def _render_colunas_detectadas_sync(df_final: pd.DataFrame) -> None:
    resumo = _montar_resumo(df_final)

    with st.expander("Colunas que o envio vai usar", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            st.write(f"**Código detectado:** {resumo['codigo_col'] or 'não encontrado'}")
            st.write(f"**Descrição detectada:** {resumo['descricao_col'] or 'não encontrada'}")
        with c2:
            st.write(f"**Preço detectado:** {resumo['preco_col'] or 'não encontrado'}")
            st.write(f"**GTIN detectado:** {resumo['gtin_col'] or 'não encontrado'}")

        if not resumo["codigo_col"] or not resumo["descricao_col"]:
            st.warning("O sincronizador do Bling pode falhar no envio se código ou descrição não forem detectados corretamente.")


def _render_preview_dataframe(df_final: pd.DataFrame) -> None:
    st.markdown("### Preview final")
    if df_final.empty:
        st.dataframe(pd.DataFrame(columns=df_final.columns), use_container_width=True)
        return

    st.dataframe(df_final.head(80), use_container_width=True)
    with st.expander("Ver preview ampliado", expanded=False):
        st.dataframe(df_final.head(250), use_container_width=True)


def _render_download(df_final: pd.DataFrame, validacao_ok: bool) -> None:
    st.markdown("### Download da planilha padrão Bling")

    csv_bytes = dataframe_para_csv_bytes(df_final)
    st.download_button(
        label="📥 Baixar CSV final",
        data=csv_bytes,
        file_name="bling_saida_final.csv",
        mime="text/csv",
        use_container_width=True,
        disabled=not validacao_ok,
        key="btn_download_csv_final_preview",
    )

    if validacao_ok:
        if st.button(
            "✅ Já baixei / seguir para conexão e envio",
            use_container_width=True,
            key="btn_confirmar_download_preview",
        ):
            st.session_state["preview_download_realizado"] = True
            log_debug("Usuário confirmou a etapa de download e avançou para conexão/envio.", nivel="INFO")
            st.rerun()
    else:
        st.info("Ajuste a validação antes de liberar o download e o envio.")


def _render_bloco_fluxo_site() -> None:
    with st.expander("Varredura do site e conversão GPT", expanded=False):
        if not _origem_site_ativa():
            st.caption("A origem atual não veio da busca por site.")
            return

        url_site = _url_site_atual()
        modo_auto = st.session_state.get("bling_sync_auto_mode", "manual")
        interval_value = st.session_state.get("bling_sync_interval_value", 15)
        interval_unit = st.session_state.get("bling_sync_interval_unit", "minutos")
        loop_ativo = bool(st.session_state.get("site_auto_loop_ativo", False))
        loop_status = str(st.session_state.get("site_auto_status", "inativo") or "inativo")
        ultima_execucao = str(st.session_state.get("site_auto_ultima_execucao", "") or "")
        fonte_descoberta = _fonte_descoberta_label(st.session_state.get("site_busca_fonte_descoberta", ""))

        if _varredura_site_concluida():
            st.success("Varredura do site concluída. Produtos localizados e prontos para seguir para o Bling.")
        else:
            st.warning("A conexão OAuth e o envio só serão liberados depois da varredura do site terminar com dados válidos.")

        if url_site:
            st.write(f"**URL monitorada:** {url_site}")

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Loop", "Ativo" if loop_ativo else "Inativo")
        with c2:
            st.metric("Status", loop_status.title())
        with c3:
            st.metric("Última busca", ultima_execucao if ultima_execucao else "-")
        with c4:
            st.metric("Fonte descoberta", fonte_descoberta)

        if modo_auto == "periodico":
            st.info(f"Modo periódico configurado: **{interval_value} {interval_unit}**.")


def _render_resultado_envio_visual(resultado: dict[str, Any]) -> None:
    if not isinstance(resultado, dict) or not resultado:
        return

    st.markdown("#### Resultado do envio")

    modo = str(resultado.get("modo", "") or "")
    ok = bool(resultado.get("ok", False))
    mensagem = str(resultado.get("mensagem", "") or "").strip()

    if modo == "real":
        if ok:
            st.success(mensagem or "Envio real concluído com sucesso.")
        else:
            st.warning(mensagem or "Envio real concluído com pendências.")
    elif modo == "simulacao":
        st.error("O retorno abaixo é de SIMULAÇÃO. Nada foi enviado ao Bling.")
    else:
        st.warning(mensagem or "O envio terminou com retorno técnico.")

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("Total", int(resultado.get("total_itens", 0) or 0))
    with c2:
        st.metric("Criados", int(resultado.get("total_criados", 0) or 0))
    with c3:
        st.metric("Atualizados", int(resultado.get("total_atualizados", 0) or 0))
    with c4:
        st.metric("Ignorados", int(resultado.get("total_ignorados", 0) or 0))
    with c5:
        st.metric("Erros", int(resultado.get("total_erros", 0) or 0))

    st.caption(
        f"Modo: {modo or '-'} • Processado em: {resultado.get('processado_em', '-') or '-'} "
        f"• Próxima execução: {resultado.get('proxima_execucao', '-') or '-'}"
    )

    resultados = resultado.get("resultados", [])
    if isinstance(resultados, list) and resultados:
        df_resultados = pd.DataFrame(resultados)
        if not df_resultados.empty:
            erros_df = df_resultados[df_resultados["status"].astype(str).str.lower().eq("erro")] if "status" in df_resultados.columns else pd.DataFrame()
            with st.expander("Últimos itens processados", expanded=False):
                st.dataframe(df_resultados.tail(100), use_container_width=True)
            if not erros_df.empty:
                with st.expander("Itens com erro", expanded=False):
                    st.dataframe(erros_df, use_container_width=True)

    with st.expander("JSON técnico do retorno", expanded=False):
        st.code(json.dumps(resultado, ensure_ascii=False, indent=2), language="json")


def _render_painel_bling(df_final: pd.DataFrame, tipo_operacao: str, deposito_nome: str, validacao_ok: bool) -> None:
    st.markdown("### Conectar e enviar ao Bling")

    oauth_liberado = _oauth_liberado(validacao_ok)
    conectado, status = _obter_status_conexao_bling()

    st.session_state["bling_conectado"] = conectado
    st.session_state["bling_status_texto"] = status

    c1, c2 = st.columns([1, 1])
    with c1:
        st.info(f"Status da conexão: **{status}**")
    with c2:
        if not conectado:
            _render_conexao_bling(oauth_liberado)
        else:
            st.success("Conta Bling pronta para envio real.")

    if not st.session_state.get("preview_download_realizado", False):
        st.warning("Confirme primeiro o download da planilha final para liberar a conexão e o envio.")
        return

    if not validacao_ok:
        st.warning("A validação final precisa estar OK para liberar o envio ao Bling.")
        return

    if _origem_site_ativa() and not _varredura_site_concluida():
        st.warning("Finalize a varredura do site do fornecedor antes de conectar e enviar ao Bling.")
        return

    st.markdown("#### Estratégia de sincronização")
    st.radio(
        "Como deseja enviar os produtos?",
        options=["inteligente", "cadastrar_novos", "atualizar_existentes"],
        format_func=lambda x: {
            "inteligente": "Cadastrar novos e atualizar existentes",
            "cadastrar_novos": "Cadastrar apenas novos",
            "atualizar_existentes": "Atualizar apenas existentes",
        }.get(x, x),
        key="bling_sync_strategy",
    )

    st.markdown("#### Atualização automática")
    modo_auto = st.radio(
        "Modo de atualização",
        options=["manual", "instantaneo", "periodico"],
        format_func=lambda x: {
            "manual": "Manual",
            "instantaneo": "Instantânea",
            "periodico": "Periódica",
        }.get(x, x),
        horizontal=True,
        key="bling_sync_auto_mode",
    )

    if modo_auto == "periodico":
        cc1, cc2 = st.columns(2)
        with cc1:
            st.number_input("Intervalo", min_value=1, step=1, key="bling_sync_interval_value")
        with cc2:
            st.selectbox("Unidade", options=["minutos", "horas", "dias"], key="bling_sync_interval_unit")

    if _origem_site_ativa():
        st.caption(
            "Quando a origem vier do site do fornecedor, o envio respeita a sequência: "
            "captura/validação → download → conexão Bling → envio por API."
        )

    liberar_envio = bool(conectado and oauth_liberado)

    if st.button(
        "🚀 Enviar produtos ao Bling",
        use_container_width=True,
        key="btn_enviar_produtos_bling",
        disabled=not liberar_envio or bool(st.session_state.get("preview_envio_em_execucao", False)),
    ):
        _enviar_para_bling(
            df_final=df_final.copy(),
            tipo_operacao=tipo_operacao,
            deposito_nome=deposito_nome,
        )

    if not conectado:
        st.caption("Depois da validação e da confirmação do download, conecte sua conta do Bling para liberar o envio real.")
    elif not liberar_envio:
        st.caption("Ainda existem pré-requisitos pendentes antes do envio.")

    resultado = st.session_state.get("bling_envio_resultado")
    if resultado:
        _render_resultado_envio_visual(resultado)


def render_preview_final() -> None:
    _garantir_etapa_preview_ativa()
    _inicializar_estado_preview()

    st.subheader("4. Preview Final")

    tipo_operacao = normalizar_texto(st.session_state.get("tipo_operacao") or "cadastro") or "cadastro"
    deposito_nome = _sincronizar_deposito_nome()
    df_final = _obter_df_final_exclusivo()

    if not safe_df_estrutura(df_final):
        st.warning("O resultado final ainda não foi gerado.")
        if st.button("⬅️ Voltar para mapeamento", use_container_width=True, key="btn_voltar_preview_sem_df"):
            st.session_state["_ultima_etapa_sincronizada_url"] = "mapeamento"
            voltar_etapa_anterior()
        return

    df_final = _garantir_df_final_canonico(
        df=df_final,
        tipo_operacao=tipo_operacao,
        deposito_nome=deposito_nome,
    )
    st.session_state["df_final"] = df_final
    _sincronizar_estado_quando_df_mudar(df_final)

    validacao_ok, _ = _render_resumo_validacao(df_final, tipo_operacao)
    _render_preview_dataframe(df_final)
    _render_download(df_final, validacao_ok)
    _render_painel_bling(df_final, tipo_operacao, deposito_nome, validacao_ok)
    _render_colunas_detectadas_sync(df_final)
    _render_origem_site_metadata()
    _render_bloco_fluxo_site()

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ Voltar para mapeamento", use_container_width=True, key="btn_voltar_preview"):
            st.session_state["_ultima_etapa_sincronizada_url"] = "mapeamento"
            voltar_etapa_anterior()
    with col2:
        if st.button("↺ Reabrir origem", use_container_width=True, key="btn_ir_origem_preview"):
            st.session_state["_ultima_etapa_sincronizada_url"] = "origem"
            ir_para_etapa("origem")
