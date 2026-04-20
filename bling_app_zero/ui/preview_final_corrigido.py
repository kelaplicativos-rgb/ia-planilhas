

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


# ============================================================
# BLINDAGEM DE ETAPA
# ============================================================

def _garantir_etapa_preview_ativa() -> None:
    if get_etapa() != "preview_final":
        sincronizar_etapa_global("preview_final")

    st.session_state["_etapa_url_inicializada"] = True
    st.session_state["_ultima_etapa_sincronizada_url"] = "preview_final"


# ============================================================
# IMPORTS SEGUROS
# ============================================================

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


# ============================================================
# HELPERS DE DATAFRAME
# ============================================================

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


# ============================================================
# HELPERS DE FLUXO
# ============================================================

def _origem_site_ativa() -> bool:
    modo_origem = safe_lower(st.session_state.get("modo_origem", ""))
    origem_tipo = safe_lower(st.session_state.get("origem_upload_tipo", ""))
    origem_nome = safe_lower(st.session_state.get("origem_upload_nome", ""))

    return (
        "site" in modo_origem
        or "site_gpt" in origem_tipo
        or "varredura_site_" in origem_nome
    )


def _url_site_atual() -> str:
    return str(st.session_state.get("site_fornecedor_url", "") or "").strip()


def _varredura_site_concluida() -> bool:
    if not _origem_site_ativa():
        return False

    df_origem = st.session_state.get("df_origem")
    return isinstance(df_origem, pd.DataFrame) and not df_origem.empty


def _oauth_liberado(validacao_ok: bool) -> bool:
    if not validacao_ok:
        return False

    if _origem_site_ativa():
        return bool(_varredura_site_concluida() and _destino_bling_selecionado())

    return True


def _resumo_rotina_site() -> dict[str, Any]:
    return {
        "origem_site_ativa": _origem_site_ativa(),
        "url_site": _url_site_atual(),
        "auto_mode": st.session_state.get("bling_sync_auto_mode", "manual"),
        "interval_value": st.session_state.get("bling_sync_interval_value", 15),
        "interval_unit": st.session_state.get("bling_sync_interval_unit", "minutos"),
        "loop_ativo": bool(st.session_state.get("site_auto_loop_ativo", False)),
        "loop_status": str(st.session_state.get("site_auto_status", "inativo") or "inativo"),
        "ultima_execucao": str(st.session_state.get("site_auto_ultima_execucao", "") or ""),
    }


def _destino_site_selecionado() -> str:
    return str(st.session_state.get("preview_destino_pos_analise", "") or "").strip()


def _destino_bling_selecionado() -> bool:
    return _destino_site_selecionado() in {"bling_cadastro", "bling_estoque"}


def _tipo_operacao_destino(tipo_operacao_atual: str) -> str:
    destino = _destino_site_selecionado()
    if destino == "bling_estoque":
        return "estoque"
    if destino == "bling_cadastro":
        return "cadastro"
    return tipo_operacao_atual


# ============================================================
# ESTADO DA TELA
# ============================================================

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
        "preview_destino_pos_analise": "",
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


def _sincronizar_estado_quando_df_mudar(df_final: pd.DataFrame) -> None:
    hash_atual = _hash_df_visual(df_final)
    hash_anterior = str(st.session_state.get("preview_hash_df_final", "") or "")

    if hash_atual != hash_anterior:
        st.session_state["preview_download_realizado"] = False
        st.session_state["bling_envio_resultado"] = None
        st.session_state["preview_hash_df_final"] = hash_atual
        log_debug("df_final alterado no preview; confirmação de download e resultado de envio foram resetados.", nivel="INFO")


# ============================================================
# CONEXÃO BLING
# ============================================================

def _obter_status_conexao_bling() -> tuple[bool, str]:
    bling_auth = _safe_import_bling_auth()

    if bling_auth is not None:
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

    conectado = bool(st.session_state.get("bling_conectado", False))
    status = str(st.session_state.get("bling_status_texto", "Desconectado") or "Desconectado")
    return conectado, status


def _render_conexao_bling(liberado: bool) -> None:
    if not liberado:
        st.warning(
            "A conexão com o Bling só é liberada depois que o resultado final estiver validado, "
            "o download for confirmado e, quando for origem por site, a varredura estiver concluída."
        )
        return

    bling_auth = _safe_import_bling_auth()

    if bling_auth is not None:
        render_conectar_bling = bling_auth.get("render_conectar_bling")
        if callable(render_conectar_bling):
            try:
                render_conectar_bling()
                return
            except Exception as exc:
                st.error(f"Falha ao renderizar conexão com o Bling: {exc}")
                log_debug(f"Falha ao renderizar conexão com o Bling: {exc}", nivel="ERRO")
                return

    if st.button("🔗 Conectar com Bling", use_container_width=True, key="btn_conectar_bling_preview"):
        st.session_state["bling_conectado"] = True
        st.session_state["bling_status_texto"] = "Conectado em modo local"
        st.warning("Conexão simulada. O backend do OAuth ainda não está plugado nesta execução.")
        log_debug("Conexão com Bling acionada em modo local/simulado.", nivel="INFO")


# ============================================================
# ENVIO AO BLING
# ============================================================

def _enviar_para_bling(df_final: pd.DataFrame, tipo_operacao: str, deposito_nome: str) -> None:
    estrategia = st.session_state.get("bling_sync_strategy", "inteligente")
    auto_mode = st.session_state.get("bling_sync_auto_mode", "manual")
    interval_value = st.session_state.get("bling_sync_interval_value", 15)
    interval_unit = st.session_state.get("bling_sync_interval_unit", "minutos")

    bling_sync = _safe_import_bling_sync()

    log_debug(
        f"Disparando envio ao Bling | strategy={estrategia} | auto_mode={auto_mode} | "
        f"interval={interval_value} {interval_unit} | linhas={len(df_final)}",
        nivel="INFO",
    )

    if bling_sync is not None:
        try:
            if hasattr(bling_sync, "sincronizar_produtos_bling"):
                resultado = bling_sync.sincronizar_produtos_bling(
                    df_final=df_final.copy(),
                    tipo_operacao=tipo_operacao,
                    deposito_nome=deposito_nome,
                    strategy=estrategia,
                    auto_mode=auto_mode,
                    interval_value=interval_value,
                    interval_unit=interval_unit,
                    dry_run=False,
                )
                st.session_state["bling_envio_resultado"] = resultado

                if bool(resultado.get("ok", False)):
                    st.success("Envio ao Bling executado com sucesso.")
                    log_debug("Envio ao Bling executado com sucesso.", nivel="INFO")
                else:
                    st.warning("O envio foi executado, mas retornou alertas ou erros.")
                    log_debug(
                        f"Envio ao Bling retornou alertas/erros: {json.dumps(resultado, ensure_ascii=False)}",
                        nivel="ERRO",
                    )
                return

            if hasattr(bling_sync, "enviar_produtos"):
                resultado = bling_sync.enviar_produtos(
                    df_final=df_final.copy(),
                    tipo_operacao=tipo_operacao,
                    deposito_nome=deposito_nome,
                    strategy=estrategia,
                )
                st.session_state["bling_envio_resultado"] = resultado
                st.success("Envio ao Bling executado com sucesso.")
                log_debug("Envio ao Bling executado com sucesso via enviar_produtos.", nivel="INFO")
                return
        except Exception as exc:
            st.error(f"Falha no envio ao Bling: {exc}")
            log_debug(f"Falha no envio ao Bling: {exc}", nivel="ERRO")
            return

    resumo_local = {
        "ok": False,
        "modo": "simulacao_local",
        "mensagem": "Serviço real de sincronização ainda não disponível.",
        "tipo_operacao": tipo_operacao,
        "deposito_nome": deposito_nome,
        "strategy": estrategia,
        "auto_mode": auto_mode,
        "interval_value": interval_value,
        "interval_unit": interval_unit,
        "total_itens": int(len(df_final)),
        "site_fallback": _resumo_rotina_site(),
    }
    st.session_state["bling_envio_resultado"] = resumo_local
    st.warning("O envio foi registrado apenas em simulação local.")
    log_debug(
        f"Envio caiu em simulação local: {json.dumps(resumo_local, ensure_ascii=False)}",
        nivel="INFO",
    )


# ============================================================
# RENDERIZAÇÃO DOS BLOCOS
# ============================================================

def _render_resumo_validacao(df_final: pd.DataFrame, tipo_operacao: str) -> tuple[bool, list[str]]:
    resumo = _montar_resumo(df_final)
    valido, erros = validar_df_para_download(df_final, tipo_operacao)
    st.session_state["preview_validacao_ok"] = bool(valido)

    st.markdown("### 1. Validação do resultado final")

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
        log_debug(
            f"Validação final com pendências: {' | '.join(erros)}",
            nivel="ERRO",
        )
    else:
        st.success("A planilha final passou na validação principal.")
        log_debug("Validação final aprovada.", nivel="INFO")

    return valido, erros


def _render_colunas_detectadas_sync(df_final: pd.DataFrame) -> None:
    resumo = _montar_resumo(df_final)

    st.markdown("### 2. Colunas que o envio vai usar")
    c1, c2 = st.columns(2)

    with c1:
        st.write(f"**Código detectado:** {resumo['codigo_col'] or 'não encontrado'}")
        st.write(f"**Descrição detectada:** {resumo['descricao_col'] or 'não encontrada'}")

    with c2:
        st.write(f"**Preço detectado:** {resumo['preco_col'] or 'não encontrado'}")
        st.write(f"**GTIN detectado:** {resumo['gtin_col'] or 'não encontrado'}")

    if not resumo["codigo_col"] or not resumo["descricao_col"]:
        st.warning(
            "O sincronizador do Bling pode falhar no envio se código ou descrição não forem detectados corretamente."
        )


def _render_preview_dataframe(df_final: pd.DataFrame) -> None:
    st.markdown("### 3. Preview final")

    if df_final.empty:
        st.dataframe(pd.DataFrame(columns=df_final.columns), use_container_width=True)
        return

    st.dataframe(df_final.head(100), use_container_width=True)

    with st.expander("Ver preview ampliado", expanded=False):
        st.dataframe(df_final.head(300), use_container_width=True)


def _render_escolha_destino(tipo_operacao: str, validacao_ok: bool) -> str:
    st.markdown("### 4. O que deseja fazer com o resultado?")

    if not _origem_site_ativa():
        st.caption("Para origens que não vieram do site, o fluxo segue normalmente com download e, se desejar, envio ao Bling.")
        return "fluxo_padrao"

    if not _varredura_site_concluida():
        st.info("Conclua primeiro a análise do site para escolher o destino dos dados.")
        return ""

    opcoes = ["planilha_bling", "bling_cadastro", "bling_estoque"]
    mapa_rotulos = {
        "planilha_bling": "Gerar planilha pronta para importação no Bling",
        "bling_cadastro": "Enviar ao Bling para cadastro de produtos",
        "bling_estoque": "Enviar ao Bling para atualização de estoque",
    }

    destino_atual = _destino_site_selecionado()
    if destino_atual not in opcoes:
        if tipo_operacao == "estoque":
            destino_atual = "bling_estoque"
        elif tipo_operacao == "cadastro":
            destino_atual = "bling_cadastro"
        else:
            destino_atual = "planilha_bling"
        st.session_state["preview_destino_pos_analise"] = destino_atual

    escolha = st.radio(
        "Após a análise, escolha como deseja seguir",
        options=opcoes,
        index=opcoes.index(st.session_state["preview_destino_pos_analise"]),
        format_func=lambda x: mapa_rotulos.get(x, x),
        key="preview_destino_pos_analise_radio",
    )
    st.session_state["preview_destino_pos_analise"] = escolha

    if escolha == "bling_cadastro":
        st.session_state["tipo_operacao"] = "cadastro"
        st.session_state["tipo_operacao_bling"] = "cadastro"
    elif escolha == "bling_estoque":
        st.session_state["tipo_operacao"] = "estoque"
        st.session_state["tipo_operacao_bling"] = "estoque"

    if escolha == "planilha_bling":
        st.success("Destino selecionado: gerar planilha de importação pronta para o Bling.")
    elif escolha == "bling_cadastro":
        st.success("Destino selecionado: enviar ao Bling para cadastro de produtos.")
    else:
        st.success("Destino selecionado: enviar ao Bling para atualização de estoque.")

    if not validacao_ok:
        st.caption("A validação ainda precisa ficar OK antes do download da planilha ou do envio ao Bling.")

    return escolha


def _render_download(df_final: pd.DataFrame, validacao_ok: bool, destino_escolhido: str) -> None:
    st.markdown("### 5. Planilha padrão Bling")

    if _origem_site_ativa() and destino_escolhido not in {"planilha_bling", "fluxo_padrao"}:
        st.caption("Você escolheu seguir com envio ao Bling. A planilha final continua disponível apenas para conferência, sem bloquear o próximo passo.")
        return

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
        st.session_state["preview_download_realizado"] = True
        st.caption("A planilha acima já está pronta para importação no Bling.")
    else:
        st.info("Ajuste a validação antes de liberar a planilha final.")


def _render_bloco_fluxo_site() -> None:
    st.markdown("### 6. Análise automática do site")

    if not _origem_site_ativa():
        st.caption(
            "A origem atual não veio da busca por site. Quando a captura vier do site do fornecedor, "
            "o fluxo final passa a exigir a varredura/conversão antes da conexão com o Bling."
        )
        return

    url_site = _url_site_atual()
    modo_auto = st.session_state.get("bling_sync_auto_mode", "manual")
    interval_value = st.session_state.get("bling_sync_interval_value", 15)
    interval_unit = st.session_state.get("bling_sync_interval_unit", "minutos")
    loop_ativo = bool(st.session_state.get("site_auto_loop_ativo", False))
    loop_status = str(st.session_state.get("site_auto_status", "inativo") or "inativo")
    ultima_execucao = str(st.session_state.get("site_auto_ultima_execucao", "") or "")

    if _varredura_site_concluida():
        st.success("Análise do site concluída. Produtos localizados e organizados para o próximo passo.")
    else:
        st.warning("A escolha de destino e o envio ao Bling só serão liberados depois da análise do site terminar com dados válidos.")

    if url_site:
        st.write(f"**URL monitorada:** {url_site}")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Loop", "Ativo" if loop_ativo else "Inativo")
    with c2:
        st.metric("Status", loop_status.title())
    with c3:
        st.metric("Última busca", ultima_execucao if ultima_execucao else "-")

    if modo_auto == "manual":
        st.info("Modo manual: a análise atual do site será usada nesta execução.")
    elif modo_auto == "instantaneo":
        st.info("Modo instantâneo: antes do envio, o sistema pode refazer a análise do site e atualizar os dados automaticamente.")
    else:
        st.info(
            f"Modo periódico configurado: a rotina poderá analisar o site a cada "
            f"**{interval_value} {interval_unit}** e então atualizar os dados antes do envio."
        )

    st.caption(
        "Ordem correta do fluxo: analisar site → revisar resultado → escolher destino → baixar planilha ou conectar no Bling → concluir."
    )


def _render_painel_bling(df_final: pd.DataFrame, tipo_operacao: str, deposito_nome: str, validacao_ok: bool, destino_escolhido: str) -> None:
    st.markdown("### 7. Conectar e enviar ao Bling")

    oauth_liberado = _oauth_liberado(validacao_ok)
    conectado, status = _obter_status_conexao_bling()

    st.session_state["bling_conectado"] = conectado
    st.session_state["bling_status_texto"] = status

    if _origem_site_ativa() and destino_escolhido not in {"bling_cadastro", "bling_estoque"}:
        st.caption("Você escolheu gerar a planilha de importação. A conexão com o Bling fica oculta neste caminho.")
        return

    c1, c2 = st.columns([1, 1])
    with c1:
        st.info(f"Status da conexão: **{status}**")
    with c2:
        if not conectado:
            _render_conexao_bling(oauth_liberado)
        else:
            st.success("Conta Bling pronta para envio.")

    if not validacao_ok:
        st.warning("A validação final precisa estar OK para liberar o envio ao Bling.")
        return

    if _origem_site_ativa() and not _varredura_site_concluida():
        st.warning("Finalize a varredura do site do fornecedor antes de conectar e enviar ao Bling.")
        return

    st.markdown("#### Estratégia de sincronização")

    st.radio(
        "Como deseja enviar os produtos?",
        options=[
            "inteligente",
            "cadastrar_novos",
            "atualizar_existentes",
        ],
        format_func=lambda x: {
            "inteligente": "Cadastrar novos e atualizar existentes",
            "cadastrar_novos": "Cadastrar apenas novos",
            "atualizar_existentes": "Atualizar apenas existentes",
        }.get(x, x),
        horizontal=False,
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
            st.number_input(
                "Intervalo",
                min_value=1,
                step=1,
                key="bling_sync_interval_value",
            )
        with cc2:
            st.selectbox(
                "Unidade",
                options=["minutos", "horas", "dias"],
                key="bling_sync_interval_unit",
            )

    if _origem_site_ativa():
        st.markdown("#### Conversão GPT + fallback de busca por site")
        st.caption(
            "Como a origem veio do site do fornecedor, o envio usa a sequência correta: "
            "captura do site → conversão GPT → validação → conexão Bling → envio por API."
        )

    liberar_envio = bool(conectado and oauth_liberado)

    if st.button(
        "🚀 Enviar produtos ao Bling",
        use_container_width=True,
        key="btn_enviar_produtos_bling",
        disabled=not liberar_envio,
    ):
        _enviar_para_bling(
            df_final=df_final.copy(),
            tipo_operacao=tipo_operacao,
            deposito_nome=deposito_nome,
        )

    if not conectado:
        st.caption("Depois da validação e da escolha de envio ao Bling, faça a conexão OAuth para liberar o envio.")
    elif not liberar_envio:
        st.caption("Ainda existem pré-requisitos pendentes antes do envio ao Bling.")

    resultado = st.session_state.get("bling_envio_resultado")
    if resultado:
        st.markdown("#### Resultado do envio")
        st.code(json.dumps(resultado, ensure_ascii=False, indent=2), language="json")


# ============================================================
# TELA PRINCIPAL
# ============================================================

def render_preview_final() -> None:
    _garantir_etapa_preview_ativa()
    _inicializar_estado_preview()

    st.subheader("4. Preview Final")
    st.caption(
        "Fluxo final profissional: revisar o resultado, escolher o destino dos dados "
        "e então seguir com planilha de importação ou envio ao Bling."
    )

    tipo_operacao = normalizar_texto(st.session_state.get("tipo_operacao") or "cadastro") or "cadastro"
    deposito_nome = normalizar_texto(st.session_state.get("deposito_nome", ""))

    df_final = _obter_df_final_exclusivo()

    if not safe_df_estrutura(df_final):
        st.warning("O resultado final ainda não foi gerado.")
        if st.button("⬅️ Voltar para mapeamento", use_container_width=True, key="btn_voltar_preview_sem_df"):
            st.session_state["_ultima_etapa_sincronizada_url"] = "mapeamento"
            voltar_etapa_anterior()
        return

    df_final = _normalizar_df_visual(df_final)
    df_final = blindar_df_para_bling(
        df=df_final,
        tipo_operacao_bling=tipo_operacao,
        deposito_nome=deposito_nome,
    )

    st.session_state["df_final"] = df_final
    _sincronizar_estado_quando_df_mudar(df_final)

    validacao_ok, _ = _render_resumo_validacao(df_final, tipo_operacao)
    _render_colunas_detectadas_sync(df_final)
    _render_preview_dataframe(df_final)
    destino_escolhido = _render_escolha_destino(tipo_operacao, validacao_ok)
    tipo_operacao_envio = _tipo_operacao_destino(tipo_operacao)
    _render_download(df_final, validacao_ok, destino_escolhido)
    _render_bloco_fluxo_site()
    _render_painel_bling(df_final, tipo_operacao_envio, deposito_nome, validacao_ok, destino_escolhido)

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

