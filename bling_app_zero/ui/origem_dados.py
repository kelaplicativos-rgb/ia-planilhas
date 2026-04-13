from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import (
    log_debug,
    safe_df_dados,
    safe_df_estrutura,
)


# ==========================================================
# ESTADO
# ==========================================================
def garantir_estado_origem() -> None:
    defaults = {
        "tipo_operacao": "Cadastro de Produtos",
        "tipo_operacao_bling": "cadastro",
        "origem_dados_tipo": "planilha",
        "site_processado": False,
        "df_origem": None,
        "df_saida": None,
        "df_final": None,
        "df_precificado": None,
        "df_calc_precificado": None,
        "deposito_nome": "",
        "coluna_precificacao_resultado": "",
    }
    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


def set_etapa_origem(etapa: str) -> None:
    etapa = str(etapa or "origem").strip().lower()
    st.session_state["etapa_origem"] = etapa
    st.session_state["etapa"] = etapa
    st.session_state["etapa_fluxo"] = etapa


def _sincronizar_tipo_operacao(operacao: str) -> None:
    st.session_state["tipo_operacao"] = operacao
    st.session_state["tipo_operacao_bling"] = (
        "cadastro" if operacao == "Cadastro de Produtos" else "estoque"
    )


# ==========================================================
# HELPERS
# ==========================================================
def _render_header_fluxo() -> None:
    st.subheader("Origem dos dados")
    st.caption(
        "Você quer cadastrar produto ou atualizar o estoque? "
        "Carregue a origem e o sistema prepara automaticamente a base para o Bling."
    )


def _obter_origem_atual() -> str:
    return str(st.session_state.get("origem_dados_tipo") or "planilha").strip().lower()


def _ler_planilha(upload) -> pd.DataFrame | None:
    if upload is None:
        return None

    nome = str(getattr(upload, "name", "") or "").lower()

    try:
        if nome.endswith(".csv"):
            try:
                return pd.read_csv(upload, sep=None, engine="python")
            except Exception:
                upload.seek(0)
                return pd.read_csv(upload, sep=";")

        if nome.endswith(".xlsx") or nome.endswith(".xls"):
            return pd.read_excel(upload)

        if nome.endswith(".xml"):
            try:
                tabelas = pd.read_xml(upload)
                if isinstance(tabelas, pd.DataFrame):
                    return tabelas
            except Exception:
                return None

    except Exception as e:
        log_debug(f"[ORIGEM_DADOS] erro ao ler arquivo: {e}", "ERROR")
        return None

    return None


def render_origem_entrada(on_change_callback=None):
    origem = st.radio(
        "Origem dos dados",
        ["Planilha / CSV / XML", "Buscar em site"],
        horizontal=True,
        key="origem_dados_radio",
    )

    origem_valor = "site" if "site" in origem.lower() else "planilha"
    st.session_state["origem_dados_tipo"] = origem_valor

    if callable(on_change_callback):
        try:
            on_change_callback(origem_valor)
        except Exception:
            pass

    if origem_valor == "site":
        st.info("Modo site ativo. Execute a busca do site para continuar.")
        return st.session_state.get("df_origem")

    arquivo = st.file_uploader(
        "Anexe sua planilha ou XML",
        type=["xlsx", "xls", "csv", "xml"],
        key="upload_origem_dados",
    )

    df_origem = _ler_planilha(arquivo)
    if safe_df_dados(df_origem):
        return df_origem

    return st.session_state.get("df_origem")


def controlar_troca_origem(origem: str, log_fn=None):
    try:
        if callable(log_fn):
            log_fn(f"[ORIGEM_DADOS] origem selecionada: {origem}", "INFO")
    except Exception:
        pass


def sincronizar_estado_com_origem(df_origem: pd.DataFrame, log_fn=None) -> None:
    try:
        st.session_state["df_origem"] = df_origem.copy()
        if callable(log_fn):
            log_fn(
                f"[ORIGEM_DADOS] df_origem sincronizado com {len(df_origem)} linha(s)",
                "INFO",
            )
    except Exception as e:
        if callable(log_fn):
            log_fn(f"[ORIGEM_DADOS] erro ao sincronizar origem: {e}", "ERROR")


def obter_modelo_ativo():
    if st.session_state.get("tipo_operacao_bling") == "estoque":
        return st.session_state.get("df_modelo_estoque")
    return st.session_state.get("df_modelo_cadastro")


def _modelo_tem_estrutura(df_modelo) -> bool:
    return safe_df_estrutura(df_modelo)


def render_modelo_bling(operacao: str) -> None:
    st.caption(f"Modelo ativo: {operacao}")


def obter_df_base_prioritaria(df_origem: pd.DataFrame, origem_atual: str) -> pd.DataFrame:
    df_prec = st.session_state.get("df_precificado")
    df_calc = st.session_state.get("df_calc_precificado")
    if safe_df_estrutura(df_prec):
        return df_prec.copy()
    if safe_df_estrutura(df_calc):
        return df_calc.copy()
    return df_origem.copy()


def _aplicar_bloco_estoque(df_saida: pd.DataFrame, origem_atual: str) -> pd.DataFrame:
    try:
        df_out = df_saida.copy()
        qtd = 0 if "site" in origem_atual else 1

        if "Quantidade" not in df_out.columns:
            df_out["Quantidade"] = qtd
        else:
            df_out["Quantidade"] = df_out["Quantidade"].fillna(qtd)

        return df_out
    except Exception as e:
        log_debug(f"[ORIGEM_DADOS] erro bloco estoque: {e}", "ERROR")
        return df_saida


def render_precificacao(df_origem: pd.DataFrame) -> None:
    st.caption("Precificação")
    opcoes = [""] + [str(c) for c in df_origem.columns]

    coluna_custo = st.selectbox(
        "Qual coluna está sendo precificada?",
        opcoes,
        key="coluna_precificacao_resultado",
    )

    margem = st.number_input("Margem (%)", min_value=0.0, value=0.0, step=1.0, key="margem_bling")
    impostos = st.number_input("Impostos (%)", min_value=0.0, value=0.0, step=1.0, key="impostos_bling")
    custo_fixo = st.number_input("Custo fixo", min_value=0.0, value=0.0, step=1.0, key="custofixo_bling")
    taxa_extra = st.number_input("Taxa extra", min_value=0.0, value=0.0, step=1.0, key="taxaextra_bling")

    if coluna_custo and coluna_custo in df_origem.columns:
        try:
            base = pd.to_numeric(df_origem[coluna_custo], errors="coerce").fillna(0.0)
            preco = base * (1 + margem / 100.0 + impostos / 100.0) + custo_fixo + taxa_extra

            df_prec = df_origem.copy()
            nome_preco = (
                "Preço unitário (OBRIGATÓRIO)"
                if st.session_state.get("tipo_operacao_bling") == "estoque"
                else "Preço de venda"
            )
            df_prec[nome_preco] = preco.round(2)

            st.session_state["df_calc_precificado"] = df_prec.copy()
            st.session_state["df_precificado"] = df_prec.copy()
        except Exception as e:
            log_debug(f"[ORIGEM_DADOS] erro na precificação: {e}", "ERROR")


def validar_antes_mapeamento():
    erros = []
    df_origem = st.session_state.get("df_origem")
    if not safe_df_dados(df_origem):
        erros.append("Carregue os dados de origem antes de continuar.")
    return len(erros) == 0, erros


# ==========================================================
# RENDER
# ==========================================================
def render_origem_dados() -> None:
    garantir_estado_origem()
    _render_header_fluxo()

    etapa = str(st.session_state.get("etapa_origem", "origem") or "origem").strip().lower()
    if etapa == "mapeamento":
        if st.button("⬅️ Voltar para origem", use_container_width=True):
            set_etapa_origem("origem")
            st.rerun()
        return

    df_origem = render_origem_entrada(
        lambda origem: controlar_troca_origem(origem, log_debug)
    )
    origem_atual = _obter_origem_atual()

    if "site" in origem_atual and not st.session_state.get("site_processado"):
        if not safe_df_dados(df_origem):
            st.info("Execute a busca do site para continuar.")
            return

    if not safe_df_dados(df_origem):
        st.info("Selecione a origem e carregue os dados para continuar.")
        return

    st.session_state["df_origem"] = df_origem.copy()
    sincronizar_estado_com_origem(df_origem, log_debug)

    st.markdown("---")

    operacao = st.radio(
        "Você quer cadastrar produto ou atualizar o estoque?",
        ["Cadastro de Produtos", "Atualização de Estoque"],
        key="tipo_operacao",
        horizontal=True,
    )
    _sincronizar_tipo_operacao(operacao)

    st.markdown("---")
    render_modelo_bling(operacao)

    modelo_ativo = obter_modelo_ativo()
    if modelo_ativo is not None and not _modelo_tem_estrutura(modelo_ativo):
        st.warning("⚠️ Modelo do Bling não encontrado.")
        return

    df_saida = obter_df_base_prioritaria(df_origem, origem_atual)

    if st.session_state.get("tipo_operacao_bling") == "estoque":
        df_saida = _aplicar_bloco_estoque(df_saida, origem_atual)

    st.session_state["df_saida"] = df_saida.copy()
    st.session_state["df_final"] = df_saida.copy()

    st.markdown("---")
    render_precificacao(df_origem)

    df_prec = st.session_state.get("df_calc_precificado")
    if safe_df_estrutura(df_prec):
        st.session_state["df_precificado"] = df_prec.copy()

    st.markdown("---")
    if st.button("➡️ Continuar para mapeamento", use_container_width=True, type="primary"):
        valido, erros = validar_antes_mapeamento()
        if not valido:
            for erro in erros:
                st.warning(erro)
            return

        if safe_df_estrutura(st.session_state.get("df_saida")):
            st.session_state["df_final"] = st.session_state["df_saida"].copy()

        set_etapa_origem("mapeamento")
        st.rerun()
