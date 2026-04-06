from __future__ import annotations

import hashlib
import re
from io import BytesIO
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.mapeamento_auto import sugestao_automatica
from bling_app_zero.core.precificacao import calcular_preco_compra_automatico_df


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


def _somente_digitos(valor: Any) -> str:
    return re.sub(r"\D+", "", str(valor or ""))


def _validar_gtin_checksum(gtin: str) -> bool:
    if not gtin or not gtin.isdigit():
        return False

    if len(gtin) not in {8, 12, 13, 14}:
        return False

    digitos = [int(d) for d in gtin]
    digito_verificador = digitos[-1]
    corpo = digitos[:-1]

    soma = 0
    peso = 3
    for numero in reversed(corpo):
        soma += numero * peso
        peso = 1 if peso == 3 else 3

    calculado = (10 - (soma % 10)) % 10
    return calculado == digito_verificador


def _aplicar_limpeza_gtin_ean_df_saida(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, int, list[str]]:
    if df is None or df.empty:
        return pd.DataFrame(), 0, []

    df_saida = df.copy()
    logs: list[str] = []
    total_limpados = 0

    colunas_alvo = [
        col
        for col in df_saida.columns
        if str(col).strip().lower()
        in {
            "gtin",
            "ean",
            "codigo de barras",
            "código de barras",
            "gtin/ean",
            "cean",
            "ceantrib",
            "gtin tributário",
            "gtin tributario",
        }
    ]

    if not colunas_alvo:
        return df_saida, 0, logs

    for coluna in colunas_alvo:
        novos_valores: list[str] = []

        for idx, valor in enumerate(df_saida[coluna].tolist(), start=1):
            gtin = _somente_digitos(valor)

            if not gtin:
                novos_valores.append("")
                continue

            if _validar_gtin_checksum(gtin):
                novos_valores.append(gtin)
            else:
                novos_valores.append("")
                total_limpados += 1
                logs.append(f"Linha {idx} | Coluna {coluna}: GTIN inválido zerado ({valor})")

        df_saida[coluna] = novos_valores

    return df_saida, total_limpados, logs


def _ler_arquivo_tabela(arquivo) -> pd.DataFrame:
    nome = (getattr(arquivo, "name", "") or "").lower()

    if hasattr(arquivo, "seek"):
        arquivo.seek(0)

    if nome.endswith(".csv"):
        try:
            return pd.read_csv(arquivo, dtype=str, keep_default_na=False)
        except Exception:
            if hasattr(arquivo, "seek"):
                arquivo.seek(0)
            return pd.read_csv(
                arquivo,
                sep=";",
                encoding="utf-8",
                dtype=str,
                keep_default_na=False,
            )

    if hasattr(arquivo, "seek"):
        arquivo.seek(0)

    return pd.read_excel(arquivo, dtype=str).fillna("")


def _safe_dataframe_preview(df: pd.DataFrame, rows: int = 20) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()
    return df.head(rows).copy()


def _normalizar_nome_coluna(valor: str) -> str:
    texto = str(valor or "").strip().lower()
    texto = re.sub(r"[^a-z0-9]+", "_", texto)
    return re.sub(r"_+", "_", texto).strip("_")


def _gerar_sugestoes_mapeamento(
    df_origem: pd.DataFrame,
    colunas_modelo_ativas: list[str],
) -> dict[str, str]:
    if df_origem is None or df_origem.empty or not colunas_modelo_ativas:
        return {}

    sugestoes: dict[str, str] = {}

    mapa_slug_para_origem: dict[str, str] = {}
    for coluna_origem in df_origem.columns:
        try:
            slug = sugestao_automatica(str(coluna_origem))
        except Exception:
            slug = ""
        if slug and slug not in mapa_slug_para_origem:
            mapa_slug_para_origem[slug] = coluna_origem

    aliases_destino = {
        "codigo": {"codigo", "código", "sku", "referencia", "referência"},
        "nome": {"nome", "descricao", "descrição", "titulo", "título", "produto"},
        "descricao_curta": {"descricao_curta", "descrição_curta", "descricao curta", "descrição curta"},
        "preco": {"preco", "preço", "preco_venda", "preço_venda", "preco de venda", "preço de venda"},
        "preco_custo": {"preco_custo", "preço_custo", "custo", "preco de custo", "preço de custo", "compra"},
        "estoque": {"estoque", "saldo", "quantidade", "qtd"},
        "gtin": {"gtin", "ean", "codigo de barras", "código de barras"},
        "marca": {"marca", "fabricante"},
        "categoria": {"categoria", "departamento", "seção", "secao"},
        "ncm": {"ncm"},
        "cest": {"cest"},
        "cfop": {"cfop"},
        "unidade": {"unidade", "und", "un"},
        "fornecedor": {"fornecedor"},
        "cnpj_fornecedor": {"cnpj", "cnpj_fornecedor"},
        "numero_nfe": {"nfe", "nf-e", "numero_nfe", "número_nfe", "nota"},
        "data_emissao": {"data_emissao", "data_emissão", "emissao", "emissão"},
        "imagens": {"imagem", "imagens", "foto"},
        "deposito_id": {"deposito", "depósito", "deposito_id", "depósito_id"},
        "origem": {"origem"},
    }

    for coluna_destino in colunas_modelo_ativas:
        destino_norm = _normalizar_nome_coluna(coluna_destino)

        for slug, nomes_aceitos in aliases_destino.items():
            if destino_norm in {_normalizar_nome_coluna(x) for x in nomes_aceitos}:
                coluna_origem = mapa_slug_para_origem.get(slug)
                if coluna_origem:
                    sugestoes[coluna_destino] = coluna_origem
                break

    return sugestoes


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
            df_modelo = pd.read_excel(modelo_cadastro, dtype=str).fillna("")
        except Exception as e:
            st.error(f"Erro ao ler o modelo de cadastro: {e}")
            return
    elif modo == "estoque" and modelo_estoque:
        try:
            df_modelo = pd.read_excel(modelo_estoque, dtype=str).fillna("")
        except Exception as e:
            st.error(f"Erro ao ler o modelo de estoque: {e}")
            return
    else:
        st.warning("Anexe o modelo correspondente para continuar.")
        return

    colunas_modelo_ativas = list(df_modelo.columns)

    sugestoes = _gerar_sugestoes_mapeamento(df_origem, colunas_modelo_ativas)

    if not isinstance(st.session_state.get("mapeamento_manual"), dict):
        st.session_state["mapeamento_manual"] = {}

    if sugestoes and not st.session_state["mapeamento_manual"]:
        st.session_state["mapeamento_manual"] = dict(sugestoes)

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
            elif "Deposito" in df_saida.columns:
                df_saida["Deposito"] = estoque_cfg.get("deposito", "")

        return df_saida[colunas_modelo].copy()

    def validar_saida_bling(
        df_validacao: pd.DataFrame,
        modo_atual: str,
    ) -> tuple[list[str], list[str]]:
        erros: list[str] = []
        avisos: list[str] = []

        if df_validacao is None or df_validacao.empty:
            erros.append("Arquivo vazio.")

        if modo_atual == "estoque":
            coluna_deposito = None
            if "Depósito" in df_validacao.columns:
                coluna_deposito = "Depósito"
            elif "Deposito" in df_validacao.columns:
                coluna_deposito = "Deposito"

            if coluna_deposito:
                if not str(st.session_state.get("deposito_nome", "")).strip():
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
            df_saida_final, total_limpados, logs_gtin = _aplicar_limpeza_gtin_ean_df_saida(
                df_saida_final
            )
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
