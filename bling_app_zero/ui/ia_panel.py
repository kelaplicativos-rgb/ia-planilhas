
from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.ia_orchestrator import (
    IAPlanoExecucao,
    aplicar_plano_no_session_state,
    executar_fonte_por_plano,
    interpretar_comando_usuario,
    plano_para_json,
)
from bling_app_zero.ui.app_helpers import (
    log_debug,
    normalizar_coluna_busca,
    safe_df_dados,
    sincronizar_etapa_global,
)

try:
    from bling_app_zero.core.site_crawler import executar_crawler_site
except Exception:
    executar_crawler_site = None

try:
    from bling_app_zero.core.xml_nfe import converter_upload_xml_para_dataframe
except Exception:
    converter_upload_xml_para_dataframe = None

try:
    from bling_app_zero.core.fetch_router import buscar_produtos_fornecedor
except Exception:
    buscar_produtos_fornecedor = None


# ============================================================
# HELPERS
# ============================================================

def _safe_str(valor) -> str:
    if valor is None:
        return ""
    texto = str(valor).strip()
    if texto.lower() in {"none", "nan", "nat"}:
        return ""
    return texto


def _to_float_brasil(valor) -> float:
    texto = _safe_str(valor)
    if not texto:
        return 0.0

    texto = texto.replace("R$", "").replace(" ", "")
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(",", ".")

    try:
        return float(texto)
    except Exception:
        return 0.0


def _formatar_numero_bling(valor) -> str:
    return f"{_to_float_brasil(valor):.2f}".replace(".", ",")


def _primeira_coluna_existente(df: pd.DataFrame, candidatos: list[str]) -> str:
    mapa = {normalizar_coluna_busca(col): col for col in df.columns}

    for candidato in candidatos:
        chave = normalizar_coluna_busca(candidato)
        if chave in mapa:
            return mapa[chave]

    for col in df.columns:
        ncol = normalizar_coluna_busca(col)
        for candidato in candidatos:
            if normalizar_coluna_busca(candidato) in ncol:
                return col

    return ""


def _normalizar_df_para_fluxo(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()

    base = df.copy().fillna("")
    base.columns = [_safe_str(c) for c in base.columns]

    col_codigo = _primeira_coluna_existente(
        base,
        ["codigo_fornecedor", "codigo", "sku", "referencia", "ref", "cprod"],
    )
    col_descricao = _primeira_coluna_existente(
        base,
        ["descricao_fornecedor", "descricao", "produto", "nome", "xprod", "titulo"],
    )
    col_preco = _primeira_coluna_existente(
        base,
        ["preco_base", "preco", "valor", "vUnCom", "vuncom", "preco site"],
    )
    col_quantidade = _primeira_coluna_existente(
        base,
        ["quantidade_real", "quantidade", "estoque", "saldo", "qcom", "balanco"],
    )
    col_gtin = _primeira_coluna_existente(
        base,
        ["gtin", "ean", "gtin/ean", "codigo de barras", "cean"],
    )
    col_categoria = _primeira_coluna_existente(
        base,
        ["categoria", "departamento", "breadcrumb", "grupo"],
    )
    col_imagens = _primeira_coluna_existente(
        base,
        ["url_imagens", "imagem", "imagens", "url imagem", "url imagens"],
    )

    saida = pd.DataFrame(index=base.index)
    saida["codigo_fornecedor"] = base[col_codigo] if col_codigo else ""
    saida["descricao_fornecedor"] = base[col_descricao] if col_descricao else ""
    saida["preco_base"] = base[col_preco].apply(_formatar_numero_bling) if col_preco else ""
    saida["quantidade_real"] = base[col_quantidade] if col_quantidade else ""
    saida["gtin"] = base[col_gtin] if col_gtin else ""
    saida["categoria"] = base[col_categoria] if col_categoria else ""
    saida["url_imagens"] = base[col_imagens] if col_imagens else ""

    for col in base.columns:
        if col not in saida.columns:
            saida[col] = base[col]

    return saida.fillna("")


def _modelo_padrao_por_operacao(tipo_operacao_bling: str) -> pd.DataFrame:
    if str(tipo_operacao_bling).strip().lower() == "estoque":
        return pd.DataFrame(
            columns=[
                "Código",
                "Descrição",
                "Depósito (OBRIGATÓRIO)",
                "Balanço (OBRIGATÓRIO)",
                "Preço unitário (OBRIGATÓRIO)",
                "Situação",
            ]
        )
    return pd.DataFrame(
        columns=[
            "Código",
            "Descrição",
            "Descrição Curta",
            "Preço de venda",
            "GTIN/EAN",
            "Situação",
            "URL Imagens",
            "Categoria",
        ]
    )


def _aplicar_preco_inicial(df: pd.DataFrame, plano: IAPlanoExecucao) -> pd.DataFrame:
    if not safe_df_dados(df):
        return pd.DataFrame()

    base = df.copy()
    tipo = str(plano.operacao).strip().lower()

    if plano.manter_preco_original or not plano.usar_precificacao:
        base["Preço calculado"] = base["preco_base"].apply(_to_float_brasil)
    else:
        fator = 1 + (float(plano.margem) / 100.0) + (float(plano.impostos) / 100.0)
        base_num = base["preco_base"].apply(_to_float_brasil)
        base["Preço calculado"] = (
            (base_num * fator) + float(plano.custo_fixo) + float(plano.taxa_extra)
        ).round(2)

    if tipo == "estoque":
        base["Preço unitário (OBRIGATÓRIO)"] = base["Preço calculado"].apply(_formatar_numero_bling)
    else:
        base["Preço de venda"] = base["Preço calculado"].apply(_formatar_numero_bling)

    return base.fillna("")


def _executar_plano(plano: IAPlanoExecucao, arquivo_upload=None) -> tuple[pd.DataFrame, str]:
    df = executar_fonte_por_plano(
        plano=plano,
        arquivo_upload=arquivo_upload,
        fetch_router_func=buscar_produtos_fornecedor,
        crawler_func=executar_crawler_site,
        xml_reader_func=converter_upload_xml_para_dataframe,
    )

    if not safe_df_dados(df):
        return pd.DataFrame(), "Nenhum dado retornado pela origem selecionada."

    df = _normalizar_df_para_fluxo(df)
    if not safe_df_dados(df):
        return pd.DataFrame(), "A origem foi lida, mas não gerou base válida."

    df = _aplicar_preco_inicial(df, plano)
    return df, ""


# ============================================================
# RENDER
# ============================================================

def render_ia_panel() -> None:
    st.markdown("### IA Orquestrador")
    st.caption(
        "Descreva o que deseja fazer em linguagem natural. A IA monta o plano e prepara o fluxo automaticamente."
    )

    comando_padrao = _safe_str(
        st.session_state.get(
            "ia_comando_usuario",
            "Atualizar estoque do Mega Center no depósito iFood mantendo preço original",
        )
    )

    comando = st.text_area(
        "Digite seu comando",
        value=comando_padrao,
        height=120,
        key="ia_comando_usuario",
        placeholder=(
            "Ex.: Atualiza estoque do Mega Center no depósito iFood\n"
            "Ex.: Cadastra produtos do Atacadum com preço original\n"
            "Ex.: Ler XML e atualizar estoque"
        ),
    )

    upload_xml = st.file_uploader(
        "Se o comando envolver XML, envie o arquivo aqui",
        type=["xml"],
        key="ia_upload_xml",
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Interpretar comando", use_container_width=True):
            plano = interpretar_comando_usuario(comando)
            st.session_state["ia_plano_preview"] = plano.to_dict()
            log_debug(f"Plano IA interpretado: {plano.observacoes}", "INFO")
            st.rerun()

    with col2:
        if st.button("Executar com IA", use_container_width=True):
            plano = interpretar_comando_usuario(comando)
            st.session_state["ia_plano_preview"] = plano.to_dict()

            df_resultado, erro = _executar_plano(plano, arquivo_upload=upload_xml)
            if erro:
                st.session_state["ia_erro_execucao"] = erro
                log_debug(f"Erro na execução IA: {erro}", "ERROR")
                st.rerun()

            aplicar_plano_no_session_state(st.session_state, plano)

            st.session_state["df_origem"] = df_resultado.copy()
            st.session_state["df_saida"] = df_resultado.copy()
            st.session_state["df_precificado"] = df_resultado.copy()
            st.session_state["df_modelo_operacao"] = _modelo_padrao_por_operacao(plano.operacao)
            st.session_state["origem_tipo"] = plano.origem
            st.session_state["ia_erro_execucao"] = ""

            log_debug(
                f"Execução IA concluída com {len(df_resultado)} linha(s): {plano.observacoes}",
                "INFO",
            )
            sincronizar_etapa_global("mapeamento")
            st.rerun()

    plano_preview = st.session_state.get("ia_plano_preview")
    if plano_preview:
        st.markdown("#### Plano interpretado")
        st.code(plano_para_json(IAPlanoExecucao(**plano_preview)), language="json")

    erro = _safe_str(st.session_state.get("ia_erro_execucao"))
    if erro:
        st.error(erro)

    df_origem = st.session_state.get("df_origem")
    if safe_df_dados(df_origem):
        st.markdown("#### Base preparada pela IA")
        st.dataframe(df_origem.head(50), use_container_width=True)
