from __future__ import annotations

import hashlib
from io import BytesIO
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.mapeamento_auto import sugestao_automatica
from bling_app_zero.core.precificacao import calcular_preco_compra_automatico_df
from bling_app_zero.utils.gtin import aplicar_limpeza_gtin_ean_df_saida


def _hash_df(df: pd.DataFrame) -> str:
    return hashlib.md5(
        pd.util.hash_pandas_object(df, index=True).values.tobytes()
    ).hexdigest()


def _exportar_df_exato_para_excel_bytes(df: pd.DataFrame) -> bytes:
    if df is None or df.empty:
        raise ValueError("DataFrame vazio para exportação.")

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    buffer.seek(0)
    return buffer.read()


def _ler_arquivo_tabela(arquivo) -> pd.DataFrame:
    nome = (getattr(arquivo, "name", "") or "").lower()

    if nome.endswith(".csv"):
        try:
            return pd.read_csv(arquivo)
        except Exception:
            arquivo.seek(0)
            return pd.read_csv(arquivo, sep=";", encoding="utf-8")

    arquivo.seek(0)
    return pd.read_excel(arquivo)


def _safe_dataframe_preview(df: pd.DataFrame, rows: int = 20) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()
    return df.head(rows).copy()


def render_origem_dados() -> None:
    st.subheader("Origem dos dados")

    origem = st.selectbox(
        "Selecione a origem",
        ["Planilha", "XML", "Site"],
        key="origem_tipo",
    )

    df_origem: pd.DataFrame | None = None

    if origem == "Planilha":
        arquivo = st.file_uploader(
            "Envie a planilha",
            type=["xlsx", "csv"],
            key="arquivo_origem_planilha",
        )
        if arquivo:
            try:
                df_origem = _ler_arquivo_tabela(arquivo)
            except Exception as e:
                st.error(f"Erro ao ler a planilha: {e}")
                return

    elif origem == "XML":
        arquivo = st.file_uploader(
            "Envie o XML",
            type=["xml"],
            key="arquivo_origem_xml",
        )
        if arquivo:
            st.warning("Leitura de XML em processamento...")
            return

    elif origem == "Site":
        url = st.text_input("URL do site", key="url_origem_site")
        if url:
            st.info("Captura do site em processamento...")
            return

    if df_origem is None or df_origem.empty:
        return

    origem_hash = _hash_df(df_origem)

    modo = st.radio(
        "Selecione a operação",
        ["cadastro", "estoque"],
        horizontal=True,
        key="modo_operacao",
    )

    modelo_cadastro = st.file_uploader(
        "Modelo Cadastro",
        type=["xlsx"],
        key="modelo_cadastro",
    )
    modelo_estoque = st.file_uploader(
        "Modelo Estoque",
        type=["xlsx"],
        key="modelo_estoque",
    )

    if modo == "cadastro" and modelo_cadastro:
        try:
            df_modelo = pd.read_excel(modelo_cadastro)
        except Exception as e:
            st.error(f"Erro ao ler o modelo de cadastro: {e}")
            return
    elif modo == "estoque" and modelo_estoque:
        try:
            df_modelo = pd.read_excel(modelo_estoque)
        except Exception as e:
            st.error(f"Erro ao ler o modelo de estoque: {e}")
            return
    else:
        st.warning("Anexe o modelo correspondente para continuar.")
        return

    colunas_modelo_ativas = list(df_modelo.columns)

    try:
        sugestoes = sugestao_automatica(df_origem, colunas_modelo_ativas)
    except Exception:
        sugestoes = {}

    if not isinstance(st.session_state.get("mapeamento_manual"), dict):
        st.session_state["mapeamento_manual"] = {}

    if sugestoes and not st.session_state["mapeamento_manual"]:
        try:
            st.session_state["mapeamento_manual"] = dict(sugestoes)
        except Exception:
            st.session_state["mapeamento_manual"] = {}

    st.markdown("### Preview da origem")
    st.dataframe(_safe_dataframe_preview(df_origem, 10), width="stretch")

    st.markdown("### Mapeamento manual")

    mapa_atual: dict[str, str] = dict(st.session_state.get("mapeamento_manual", {}))
    opcoes_origem = [""] + list(df_origem.columns)

    col1, col2 = st.columns([1, 1])

    with col1:
        for idx, coluna_destino in enumerate(colunas_modelo_ativas[::2]):
            chave = f"map_{modo}_{idx}_esq_{coluna_destino}"
            valor_inicial = mapa_atual.get(coluna_destino, "")
            if valor_inicial not in opcoes_origem:
                valor_inicial = ""

            selecionado = st.selectbox(
                coluna_destino,
                opcoes_origem,
                index=opcoes_origem.index(valor_inicial),
                key=chave,
            )
            mapa_atual[coluna_destino] = selecionado

    with col2:
        for idx, coluna_destino in enumerate(colunas_modelo_ativas[1::2]):
            chave = f"map_{modo}_{idx}_dir_{coluna_destino}"
            valor_inicial = mapa_atual.get(coluna_destino, "")
            if valor_inicial not in opcoes_origem:
                valor_inicial = ""

            selecionado = st.selectbox(
                coluna_destino,
                opcoes_origem,
                index=opcoes_origem.index(valor_inicial),
                key=chave,
            )
            mapa_atual[coluna_destino] = selecionado

    st.session_state["mapeamento_manual"] = mapa_atual

    calculadora_cfg: dict[str, Any] = {}
    try:
        _ = calcular_preco_compra_automatico_df(df_origem.copy())
    except Exception:
        pass

    estoque_cfg: dict[str, Any] | None = None
    if modo == "estoque":
        deposito = st.text_input("Nome do depósito", key="deposito_nome")
        estoque_cfg = {"deposito": deposito}

    def montar_df_saida_exato_modelo(
        df_base: pd.DataFrame,
        colunas_modelo: list[str],
        mapeamento_manual: dict[str, str],
        calculadora_cfg: dict[str, Any],
        estoque_cfg: dict[str, Any] | None,
        modo_atual: str,
    ) -> pd.DataFrame:
        df_saida = pd.DataFrame(index=df_base.index)

        for col in colunas_modelo:
            origem_col = (mapeamento_manual.get(col) or "").strip()
            if origem_col and origem_col in df_base.columns:
                df_saida[col] = df_base[origem_col]
            else:
                df_saida[col] = ""

        if modo_atual == "estoque" and estoque_cfg:
            if "Depósito" in df_saida.columns:
                df_saida["Depósito"] = estoque_cfg.get("deposito", "")

        return df_saida[colunas_modelo].copy()

    def validar_saida_bling(df_validacao: pd.DataFrame, modo_atual: str) -> tuple[list[str], list[str]]:
        erros: list[str] = []
        avisos: list[str] = []

        if df_validacao is None or df_validacao.empty:
            erros.append("Arquivo vazio.")

        if modo_atual == "estoque" and "Depósito" in df_validacao.columns:
            if (
                "deposito_nome" in st.session_state
                and not str(st.session_state.get("deposito_nome", "")).strip()
            ):
                avisos.append("O campo de depósito está vazio.")

        return erros, avisos

    st.divider()
    st.markdown("### Preview do que será baixado")

    try:
        df_preview_saida = montar_df_saida_exato_modelo(
            df_base=df_origem,
            colunas_modelo=colunas_modelo_ativas,
            mapeamento_manual=st.session_state["mapeamento_manual"],
            calculadora_cfg=calculadora_cfg,
            estoque_cfg=estoque_cfg,
            modo_atual=modo,
        )
    except Exception as e:
        st.error(f"Erro ao montar preview da saída: {e}")
        return

    erros_preview, avisos_preview = validar_saida_bling(df_preview_saida, modo)
    st.session_state["validacao_erros_saida"] = erros_preview
    st.session_state["validacao_avisos_saida"] = avisos_preview

    st.dataframe(_safe_dataframe_preview(df_preview_saida, 20), width="stretch")

    if erros_preview:
        st.error("Pendências antes do download:\n\n- " + "\n- ".join(erros_preview))
    elif avisos_preview:
        st.warning("Avisos:\n\n- " + "\n- ".join(avisos_preview))
    else:
        st.success("Preview válido para gerar o arquivo final.")

    b1, b2, b3 = st.columns(3)

    with b1:
        gerar_preview_final = st.button("Gerar preview final", width="stretch")

    with b2:
        limpar_gtin = st.button("Limpar GTIN/EAN inválido", width="stretch")

    with b3:
        limpar_mapeamento = st.button("Limpar mapeamento", width="stretch")

    if limpar_mapeamento:
        st.session_state["mapeamento_manual"] = {}
        st.session_state.pop("df_saida", None)
        st.session_state.pop("df_saida_preview_hash", None)
        st.session_state.pop("excel_saida_bytes", None)
        st.session_state.pop("excel_saida_nome", None)
        st.session_state.pop("logs_gtin_saida", None)
        st.rerun()

    if gerar_preview_final or limpar_gtin:
        try:
            df_saida_final = montar_df_saida_exato_modelo(
                df_base=df_origem,
                colunas_modelo=colunas_modelo_ativas,
                mapeamento_manual=st.session_state["mapeamento_manual"],
                calculadora_cfg=calculadora_cfg,
                estoque_cfg=estoque_cfg,
                modo_atual=modo,
            )
        except Exception as e:
            st.error(f"Erro ao gerar preview final: {e}")
            return

        logs_gtin: list[str] = []
        total_limpados = 0

        try:
            resultado_limpeza = aplicar_limpeza_gtin_ean_df_saida(df_saida_final)

            if isinstance(resultado_limpeza, tuple):
                if len(resultado_limpeza) >= 1 and isinstance(resultado_limpeza[0], pd.DataFrame):
                    df_saida_final = resultado_limpeza[0]
                if len(resultado_limpeza) >= 2 and isinstance(resultado_limpeza[1], int):
                    total_limpados = resultado_limpeza[1]
                if len(resultado_limpeza) >= 3 and isinstance(resultado_limpeza[2], list):
                    logs_gtin = resultado_limpeza[2]
            elif isinstance(resultado_limpeza, pd.DataFrame):
                df_saida_final = resultado_limpeza
        except Exception as e:
            st.error(f"Erro ao limpar GTIN/EAN inválido: {e}")
            return

        erros_final, avisos_final = validar_saida_bling(df_saida_final, modo)
        st.session_state["validacao_erros_saida"] = erros_final
        st.session_state["validacao_avisos_saida"] = avisos_final
        st.session_state["logs_gtin_saida"] = logs_gtin

        if erros_final:
            st.error("Não foi possível liberar o download porque ainda existem pendências.")
            return

        try:
            excel_bytes = _exportar_df_exato_para_excel_bytes(df_saida_final)
        except Exception as e:
            st.error(f"Erro ao gerar o arquivo Excel: {e}")
            return

        arquivo_saida = (
            "cadastro_produtos.xlsx"
            if modo == "cadastro"
            else "estoque_produtos.xlsx"
        )

        st.session_state["df_saida"] = df_saida_final.copy()
        st.session_state["df_saida_preview_hash"] = origem_hash
        st.session_state["excel_saida_bytes"] = excel_bytes
        st.session_state["excel_saida_nome"] = arquivo_saida

        if total_limpados > 0:
            st.success(
                f"Preview final gerado com sucesso. "
                f"{total_limpados} GTIN/EAN inválido(s) foram deixados em branco."
            )
        else:
            st.success("Preview final gerado com sucesso.")

    logs_gtin_saida = st.session_state.get("logs_gtin_saida", [])
    if isinstance(logs_gtin_saida, list) and logs_gtin_saida:
        st.caption("Validação de GTIN/EAN aplicada na saída:")
        for item in logs_gtin_saida:
            st.caption(f"- {item}")

    df_saida_state = st.session_state.get("df_saida")
    df_saida_hash = st.session_state.get("df_saida_preview_hash")
    excel_saida_bytes = st.session_state.get("excel_saida_bytes")
    excel_saida_nome = st.session_state.get("excel_saida_nome", "saida.xlsx")

    if (
        isinstance(df_saida_state, pd.DataFrame)
        and not df_saida_state.empty
        and df_saida_hash == origem_hash
        and excel_saida_bytes
    ):
        st.divider()
        st.markdown("### Preview final validado para download")
        st.caption(f"{len(df_saida_state)} linhas × {len(df_saida_state.columns)} colunas")
        st.dataframe(_safe_dataframe_preview(df_saida_state, 50), width="stretch")

        st.download_button(
            label=f"Baixar arquivo de {'Cadastro' if modo == 'cadastro' else 'Estoque'}",
            data=excel_saida_bytes,
            file_name=excel_saida_nome,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )
