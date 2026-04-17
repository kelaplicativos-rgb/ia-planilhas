
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
    normalizar_imagens_pipe,
    normalizar_texto,
    safe_df_dados,
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
        from bling_app_zero.core import bling_auth  # type: ignore
        return bling_auth
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


def _obter_df_final_preferencial() -> pd.DataFrame:
    for chave in ["df_final", "df_saida", "df_mapeado", "df_precificado"]:
        df = st.session_state.get(chave)
        if safe_df_estrutura(df):
            return df.copy()
    return pd.DataFrame()


def _coluna_codigo(df: pd.DataFrame) -> str:
    for nome in ["Código", "codigo", "Código do produto", "SKU", "Sku", "sku"]:
        if nome in df.columns:
            return nome
    return ""


def _coluna_preco(df: pd.DataFrame) -> str:
    for nome in [
        "Preço de venda",
        "Preço unitário (OBRIGATÓRIO)",
        "Preço calculado",
        "preco",
        "preço",
    ]:
        if nome in df.columns:
            return nome
    return ""


def _coluna_gtin(df: pd.DataFrame) -> str:
    for nome in ["GTIN/EAN", "GTIN", "EAN", "gtin", "ean"]:
        if nome in df.columns:
            return nome
    return ""


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
    preco_col = _coluna_preco(df)
    gtin_col = _coluna_gtin(df)

    return {
        "linhas": int(len(df.index)) if isinstance(df, pd.DataFrame) else 0,
        "colunas": int(len(df.columns)) if isinstance(df, pd.DataFrame) else 0,
        "codigo_col": codigo_col,
        "preco_col": preco_col,
        "gtin_col": gtin_col,
        "codigo_ok": _contar_preenchidos(df, codigo_col),
        "preco_ok": _contar_preenchidos(df, preco_col),
        "gtin_ok": _contar_preenchidos(df, gtin_col),
    }


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
    }

    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


# ============================================================
# CONEXÃO BLING
# ============================================================

def _obter_status_conexao_bling() -> tuple[bool, str]:
    bling_auth = _safe_import_bling_auth()

    if bling_auth is not None:
        try:
            if hasattr(bling_auth, "obter_resumo_conexao"):
                resumo = bling_auth.obter_resumo_conexao()
                conectado = bool(resumo.get("conectado", False))
                status = str(resumo.get("status", "Desconectado") or "Desconectado")
                return conectado, status

            if hasattr(bling_auth, "usuario_conectado_bling") and hasattr(bling_auth, "tem_token_valido"):
                conectado = bool(bling_auth.usuario_conectado_bling()) and bool(bling_auth.tem_token_valido())
                return conectado, "Conectado" if conectado else "Desconectado"
        except Exception:
            pass

    conectado = bool(st.session_state.get("bling_conectado", False))
    status = "Conectado" if conectado else "Desconectado"
    return conectado, status


def _render_conexao_bling() -> None:
    bling_auth = _safe_import_bling_auth()

    if bling_auth is not None and hasattr(bling_auth, "render_conectar_bling"):
        try:
            bling_auth.render_conectar_bling()
            return
        except Exception as exc:
            st.error(f"Falha ao renderizar conexão com o Bling: {exc}")
            return

    if st.button("🔗 Conectar com Bling", use_container_width=True, key="btn_conectar_bling_preview"):
        st.session_state["bling_conectado"] = True
        st.session_state["bling_status_texto"] = "Conectado em modo local"
        st.warning("Conexão simulada. O backend do OAuth ainda não está plugado nesta execução.")


# ============================================================
# ENVIO AO BLING
# ============================================================

def _enviar_para_bling(df_final: pd.DataFrame, tipo_operacao: str, deposito_nome: str) -> None:
    estrategia = st.session_state.get("bling_sync_strategy", "inteligente")
    auto_mode = st.session_state.get("bling_sync_auto_mode", "manual")
    interval_value = st.session_state.get("bling_sync_interval_value", 15)
    interval_unit = st.session_state.get("bling_sync_interval_unit", "minutos")

    bling_sync = _safe_import_bling_sync()

    if bling_sync is not None:
        try:
            if hasattr(bling_sync, "sincronizar_produtos_bling"):
                resultado = bling_sync.sincronizar_produtos_bling(
                    df_final=df_final,
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
                else:
                    st.warning("O envio foi executado, mas retornou alertas ou erros.")

                return

            if hasattr(bling_sync, "enviar_produtos"):
                resultado = bling_sync.enviar_produtos(
                    df_final=df_final,
                    tipo_operacao=tipo_operacao,
                    deposito_nome=deposito_nome,
                    strategy=estrategia,
                )
                st.session_state["bling_envio_resultado"] = resultado
                st.success("Envio ao Bling executado com sucesso.")
                return
        except Exception as exc:
            st.error(f"Falha no envio ao Bling: {exc}")
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
    }
    st.session_state["bling_envio_resultado"] = resumo_local
    st.warning("O envio foi registrado apenas em simulação local.")


# ============================================================
# RENDERIZAÇÃO DOS BLOCOS
# ============================================================

def _render_resumo_validacao(df_final: pd.DataFrame, tipo_operacao: str) -> None:
    resumo = _montar_resumo(df_final)
    valido, erros = validar_df_para_download(df_final, tipo_operacao)

    st.markdown("### Resumo do resultado final")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Linhas", resumo["linhas"])
    with c2:
        st.metric("Colunas", resumo["colunas"])
    with c3:
        st.metric("Com código", resumo["codigo_ok"])
    with c4:
        st.metric("Com preço", resumo["preco_ok"])

    c5, c6 = st.columns(2)
    with c5:
        st.metric("Com GTIN", resumo["gtin_ok"])
    with c6:
        st.metric("Validação", "OK" if valido else "Ajustes pendentes")

    if erros:
        st.warning("Existem pontos para revisão antes do download ou envio.")
        for erro in erros:
            st.write(f"- {erro}")
    else:
        st.success("A planilha final passou na validação principal.")


def _render_preview_dataframe(df_final: pd.DataFrame) -> None:
    st.markdown("### Preview final")

    if df_final.empty:
        st.dataframe(pd.DataFrame(columns=df_final.columns), use_container_width=True)
        return

    st.dataframe(df_final.head(100), use_container_width=True)

    with st.expander("Ver preview ampliado", expanded=False):
        st.dataframe(df_final.head(300), use_container_width=True)


def _render_download(df_final: pd.DataFrame) -> None:
    st.markdown("### Download")

    csv_bytes = dataframe_para_csv_bytes(df_final)

    st.download_button(
        label="📥 Baixar CSV final",
        data=csv_bytes,
        file_name="bling_saida_final.csv",
        mime="text/csv",
        use_container_width=True,
    )


def _render_painel_bling(df_final: pd.DataFrame, tipo_operacao: str, deposito_nome: str) -> None:
    st.markdown("### Bling")

    conectado, status = _obter_status_conexao_bling()
    st.session_state["bling_conectado"] = conectado
    st.session_state["bling_status_texto"] = status

    c1, c2 = st.columns([1, 1])
    with c1:
        st.info(f"Status da conexão: **{status}**")
    with c2:
        if not conectado:
            _render_conexao_bling()
        else:
            st.success("Conta Bling pronta para envio.")

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

    if st.button(
        "🚀 Enviar produtos ao Bling",
        use_container_width=True,
        key="btn_enviar_produtos_bling",
        disabled=not conectado,
    ):
        _enviar_para_bling(
            df_final=df_final,
            tipo_operacao=tipo_operacao,
            deposito_nome=deposito_nome,
        )

    if not conectado:
        st.caption("Conecte ao Bling para liberar o envio dos produtos.")

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
    st.caption("Confira o resultado final, baixe o arquivo e envie ao Bling a partir desta etapa.")

    tipo_operacao = normalizar_texto(st.session_state.get("tipo_operacao") or "cadastro") or "cadastro"
    deposito_nome = normalizar_texto(st.session_state.get("deposito_nome", ""))

    df_final = _obter_df_final_preferencial()

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

    _render_resumo_validacao(df_final, tipo_operacao)
    _render_preview_dataframe(df_final)
    _render_download(df_final)
    _render_painel_bling(df_final, tipo_operacao, deposito_nome)

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
            
