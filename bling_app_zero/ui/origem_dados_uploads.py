from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.ui.origem_dados_estado import (
    safe_df_dados,
    tem_upload_ativo,
)
from bling_app_zero.ui.origem_dados_site import render_origem_site
from bling_app_zero.utils.excel import (
    ler_planilha_segura,
    safe_df_dados as safe_df_dados_excel,
)
from bling_app_zero.utils.excel_helpers import (
    arquivo_planilha_permitido,
    hash_arquivo_upload,
    nome_arquivo,
    texto_extensoes_planilha,
)
from bling_app_zero.utils.excel_logs import log_debug
from bling_app_zero.utils.xml_nfe import (
    arquivo_parece_xml_nfe,
    ler_xml_nfe,
)


def _safe_str(valor: Any) -> str:
    try:
        if pd.isna(valor):
            return ""
        return str(valor).strip()
    except Exception:
        return ""


def _somente_digitos(valor: Any) -> str:
    try:
        return "".join(ch for ch in str(valor or "") if ch.isdigit())
    except Exception:
        return ""


def _safe_float(valor: Any, default: float = 0.0) -> float:
    try:
        texto = str(valor or "").strip()
        if not texto:
            return default

        texto = texto.replace("R$", "").replace("r$", "").strip()
        texto = texto.replace(" ", "")

        if "," in texto and "." in texto:
            if texto.rfind(",") > texto.rfind("."):
                texto = texto.replace(".", "").replace(",", ".")
            else:
                texto = texto.replace(",", "")
        else:
            texto = texto.replace(",", ".")

        return float(texto)
    except Exception:
        return default


def _df_preview_seguro(df: pd.DataFrame | None) -> pd.DataFrame | None:
    try:
        if not safe_df_dados(df):
            return df

        df_preview = df.copy()

        for col in df_preview.columns:
            try:
                df_preview[col] = df_preview[col].apply(_safe_str)
            except Exception:
                try:
                    df_preview[col] = df_preview[col].astype(str)
                except Exception:
                    pass

        return df_preview.replace(
            {
                "nan": "",
                "None": "",
                "<NA>": "",
                "NaT": "",
            }
        )
    except Exception:
        return df


def _limpar_gtin_invalido(df: pd.DataFrame) -> pd.DataFrame:
    try:
        if not safe_df_dados(df):
            return df

        df = df.copy()

        for col in df.columns:
            nome_col = str(col).strip().lower()
            if (
                "gtin" in nome_col
                or "ean" in nome_col
                or "codigo de barras" in nome_col
                or "código de barras" in nome_col
            ):
                df[col] = df[col].apply(
                    lambda x: _somente_digitos(x)
                    if len(_somente_digitos(x)) in [8, 12, 13, 14]
                    else ""
                )

        return df
    except Exception:
        return df


def _normalizar_df_xml(df: pd.DataFrame) -> pd.DataFrame:
    try:
        if not safe_df_dados(df):
            return df

        df = df.copy()

        for col in df.columns:
            try:
                df[col] = df[col].apply(_safe_str)
            except Exception:
                pass

        cols = {str(c).strip().lower(): c for c in df.columns}

        for nome in ["código", "codigo", "sku", "referencia", "referência"]:
            if nome in cols:
                col = cols[nome]
                df[col] = df[col].apply(lambda x: _safe_str(x).replace(".0", ""))

        for nome in [
            "gtin",
            "ean",
            "codigo de barras",
            "código de barras",
            "gtin tributario",
            "gtin tributário",
        ]:
            if nome in cols:
                col = cols[nome]
                df[col] = df[col].apply(_somente_digitos)

        for nome in ["ncm", "cest"]:
            if nome in cols:
                col = cols[nome]
                df[col] = df[col].apply(_somente_digitos)

        candidatos_preco = [
            "preco_compra_xml",
            "preço de custo",
            "preco de custo",
            "preço compra",
            "preco compra",
            "valor unitário",
            "valor unitario",
            "preço",
            "preco",
            "valor",
            "vprod",
        ]

        preco_encontrado = False
        for nome in candidatos_preco:
            if nome in cols:
                col = cols[nome]
                df["preco_compra_xml"] = df[col].apply(_safe_float)
                preco_encontrado = True
                break

        if not preco_encontrado:
            df["preco_compra_xml"] = 0.0

        df = df.replace(
            {
                "nan": "",
                "None": "",
                "<NA>": "",
                "NaT": "",
            }
        )

        return df
    except Exception:
        return df


def _limpar_estado_origem() -> None:
    chaves = [
        "df_origem",
        "df_origem_xml",
        "df_saida",
        "df_final",
        "df_mapeado",
        "mapeamento_colunas",
        "mapeamento_manual",
        "mapeamento_auto",
        "colunas_mapeadas",
        "arquivo_origem_hash",
        "arquivo_origem_nome",
        "origem_dados_hash",
        "origem_dados_nome",
        "origem_arquivo_nome",
        "origem_arquivo_hash",
        "url_origem_site",
    ]

    for chave in chaves:
        try:
            st.session_state.pop(chave, None)
        except Exception:
            pass


def _salvar_df_origem(
    df: pd.DataFrame,
    origem: str,
    nome_ref: str = "",
    hash_ref: str = "",
) -> pd.DataFrame:
    try:
        df_salvo = df.copy()

        st.session_state["df_origem"] = df_salvo.copy()
        st.session_state["df_saida"] = df_salvo.copy()
        st.session_state["df_final"] = df_salvo.copy()

        if origem.lower() == "xml":
            st.session_state["df_origem_xml"] = df_salvo.copy()

        if nome_ref:
            st.session_state["origem_arquivo_nome"] = nome_ref
            st.session_state["arquivo_origem_nome"] = nome_ref
            st.session_state["origem_dados_nome"] = nome_ref

        if hash_ref:
            st.session_state["origem_arquivo_hash"] = hash_ref
            st.session_state["arquivo_origem_hash"] = hash_ref
            st.session_state["origem_dados_hash"] = hash_ref

        return df_salvo
    except Exception:
        return df


def carregar_modelo_bling(arquivo: Any, tipo_modelo: str) -> bool:
    if arquivo is None:
        return False

    if not arquivo_planilha_permitido(arquivo):
        st.error(
            f"Formato não suportado para o modelo Bling. "
            f"Envie um arquivo em: {texto_extensoes_planilha()}."
        )
        log_debug(
            f"Modelo Bling recusado por extensão: {nome_arquivo(arquivo)}",
            "ERROR",
        )
        return False

    try:
        hash_atual = hash_arquivo_upload(arquivo)
        chave_hash = (
            "modelo_cadastro_hash" if tipo_modelo == "cadastro" else "modelo_estoque_hash"
        )

        hash_anterior = st.session_state.get(chave_hash, "")

        nome_atual = getattr(arquivo, "name", "")
        chave_nome = (
            "modelo_cadastro_nome" if tipo_modelo == "cadastro" else "modelo_estoque_nome"
        )
        nome_anterior = st.session_state.get(chave_nome, "")

        if hash_atual and hash_atual == hash_anterior and nome_atual == nome_anterior:
            return True

        df_modelo = ler_planilha_segura(arquivo)

        if not (safe_df_dados(df_modelo) or safe_df_dados_excel(df_modelo)):
            st.error("Não foi possível ler o modelo Bling anexado.")
            return False

        df_modelo = df_modelo.copy()
        df_modelo.columns = [str(c).strip() for c in df_modelo.columns]

        if tipo_modelo == "cadastro":
            st.session_state.pop("df_modelo_cadastro", None)
        else:
            st.session_state.pop("df_modelo_estoque", None)

        if tipo_modelo == "cadastro":
            st.session_state["df_modelo_cadastro"] = df_modelo.copy()
            st.session_state["modelo_cadastro_nome"] = nome_atual
            st.session_state["modelo_cadastro_hash"] = hash_atual

            st.session_state.pop("df_saida", None)
            st.session_state.pop("df_final", None)

            log_debug(
                f"Modelo de cadastro carregado: {nome_atual} "
                f"({len(df_modelo)} linha(s), {len(df_modelo.columns)} coluna(s))"
            )
        else:
            st.session_state["df_modelo_estoque"] = df_modelo.copy()
            st.session_state["modelo_estoque_nome"] = nome_atual
            st.session_state["modelo_estoque_hash"] = hash_atual

            st.session_state.pop("df_saida", None)
            st.session_state.pop("df_final", None)

            log_debug(
                f"Modelo de estoque carregado: {nome_atual} "
                f"({len(df_modelo)} linha(s), {len(df_modelo.columns)} coluna(s))"
            )

        return True

    except Exception as e:
        st.error("Erro ao carregar o modelo Bling.")
        log_debug(f"Erro ao carregar modelo Bling ({tipo_modelo}): {e}", "ERROR")
        return False


def render_modelo_bling(operacao: str) -> None:
    st.markdown("### Modelos Bling")

    if operacao == "Cadastro de Produtos":
        arquivo_modelo = st.file_uploader(
            "Anexar modelo de cadastro",
            key="modelo_cadastro",
            help=(
                "No celular, o seletor de arquivos pode bloquear formatos quando há "
                "filtro direto no upload. "
                f"Formatos aceitos: {texto_extensoes_planilha()}."
            ),
        )

        if arquivo_modelo is not None:
            carregar_modelo_bling(arquivo_modelo, "cadastro")

        df_modelo = st.session_state.get("df_modelo_cadastro")
        if safe_df_dados(df_modelo):
            with st.expander("Prévia do modelo de cadastro", expanded=False):
                try:
                    st.dataframe(
                        _df_preview_seguro(df_modelo).head(5),
                        use_container_width=True,
                        hide_index=True,
                    )
                except Exception as e:
                    log_debug(
                        f"Erro ao renderizar prévia do modelo de cadastro: {e}",
                        "ERROR",
                    )
                    st.write(_df_preview_seguro(df_modelo).head(5))
    else:
        arquivo_modelo = st.file_uploader(
            "Anexar modelo de estoque",
            key="modelo_estoque",
            help=(
                "No celular, o seletor de arquivos pode bloquear formatos quando há "
                "filtro direto no upload. "
                f"Formatos aceitos: {texto_extensoes_planilha()}."
            ),
        )

        if arquivo_modelo is not None:
            carregar_modelo_bling(arquivo_modelo, "estoque")

        df_modelo = st.session_state.get("df_modelo_estoque")
        if safe_df_dados(df_modelo):
            with st.expander("Prévia do modelo de estoque", expanded=False):
                try:
                    st.dataframe(
                        _df_preview_seguro(df_modelo).head(5),
                        use_container_width=True,
                        hide_index=True,
                    )
                except Exception as e:
                    log_debug(
                        f"Erro ao renderizar prévia do modelo de estoque: {e}",
                        "ERROR",
                    )
                    st.write(_df_preview_seguro(df_modelo).head(5))


def _processar_upload_planilha(arquivo_planilha: Any) -> pd.DataFrame | None:
    try:
        if arquivo_planilha is None:
            return st.session_state.get("df_origem")

        if not arquivo_planilha_permitido(arquivo_planilha):
            st.error(
                f"Formato não suportado. Envie um arquivo em: {texto_extensoes_planilha()}."
            )
            log_debug(
                f"Arquivo de origem recusado por extensão: {nome_arquivo(arquivo_planilha)}",
                "ERROR",
            )
            return None

        hash_atual = hash_arquivo_upload(arquivo_planilha)
        nome_atual = nome_arquivo(arquivo_planilha)

        hash_anterior = st.session_state.get("arquivo_origem_hash", "")
        nome_anterior = st.session_state.get("arquivo_origem_nome", "")

        if hash_atual != hash_anterior or nome_atual != nome_anterior:
            _limpar_estado_origem()

        df_origem = ler_planilha_segura(arquivo_planilha)

        if not (safe_df_dados(df_origem) or safe_df_dados_excel(df_origem)):
            st.error("Não foi possível ler a planilha anexada.")
            return None

        df_origem = df_origem.copy()
        df_origem.columns = [str(c).strip() for c in df_origem.columns]

        _salvar_df_origem(
            df_origem,
            origem="planilha",
            nome_ref=nome_atual,
            hash_ref=hash_atual,
        )

        log_debug(
            f"Planilha de origem carregada: {nome_atual} "
            f"({len(df_origem)} linha(s), {len(df_origem.columns)} coluna(s))"
        )
        return df_origem

    except Exception as e:
        st.error("Erro ao carregar a planilha de origem.")
        log_debug(f"Erro ao carregar planilha de origem: {e}", "ERROR")
        return None


def _processar_upload_xml(arquivo_xml: Any) -> pd.DataFrame | None:
    try:
        if arquivo_xml is None:
            return st.session_state.get("df_origem_xml") or st.session_state.get("df_origem")

        nome_xml = nome_arquivo(arquivo_xml)
        hash_xml = hash_arquivo_upload(arquivo_xml)

        hash_anterior = st.session_state.get("arquivo_origem_hash", "")
        nome_anterior = st.session_state.get("arquivo_origem_nome", "")

        if hash_xml != hash_anterior or nome_xml != nome_anterior:
            _limpar_estado_origem()

        if not arquivo_parece_xml_nfe(arquivo_xml):
            st.warning("O arquivo enviado não parece ser um XML de nota fiscal válido.")

        df_xml = ler_xml_nfe(arquivo_xml)

        if not safe_df_dados(df_xml):
            st.error("Não foi possível ler o XML da nota fiscal.")
            return None

        df_xml = _normalizar_df_xml(df_xml)
        df_xml = _limpar_gtin_invalido(df_xml)

        _salvar_df_origem(
            df_xml,
            origem="xml",
            nome_ref=nome_xml,
            hash_ref=hash_xml,
        )

        log_debug(
            f"XML de origem carregado: {nome_xml} "
            f"({len(df_xml)} linha(s), {len(df_xml.columns)} coluna(s))"
        )
        return df_xml

    except Exception as e:
        st.error("Erro ao carregar o XML da nota fiscal.")
        log_debug(f"Erro ao carregar XML de origem: {e}", "ERROR")
        return None


def render_origem_entrada(on_change=None) -> pd.DataFrame | None:
    st.markdown("### Entrada dos dados")

    opcoes = [
        "Buscar em site",
        "Anexar planilha",
        "Anexar XML da nota fiscal",
    ]

    origem_escolhida = st.radio(
        "Selecione a origem dos dados",
        opcoes,
        key="origem_dados_radio",
    )

    mapa_origem = {
        "Buscar em site": "site",
        "Anexar planilha": "planilha",
        "Anexar XML da nota fiscal": "xml",
    }
    origem_atual = mapa_origem.get(origem_escolhida, "")

    origem_anterior = str(st.session_state.get("origem_dados", "") or "").strip().lower()
    st.session_state["origem_dados"] = origem_atual

    if origem_atual != origem_anterior and callable(on_change):
        try:
            on_change(origem_atual)
        except Exception as e:
            log_debug(f"Erro no callback de troca de origem: {e}", "ERROR")

    df_origem: pd.DataFrame | None = None

    if origem_atual == "site":
        df_site = render_origem_site()
        if safe_df_dados(df_site):
            _salvar_df_origem(df_site, origem="site")
            df_origem = df_site
    elif origem_atual == "planilha":
        arquivo_planilha = st.file_uploader(
            "Anexar planilha do fornecedor",
            key="arquivo_origem_planilha",
            help=f"Formatos aceitos: {texto_extensoes_planilha()}.",
        )
        df_origem = _processar_upload_planilha(arquivo_planilha)
    elif origem_atual == "xml":
        arquivo_xml = st.file_uploader(
            "Anexar XML da nota fiscal",
            type=["xml"],
            key="arquivo_origem_xml",
        )
        df_origem = _processar_upload_xml(arquivo_xml)

    if not safe_df_dados(df_origem):
        df_origem = st.session_state.get("df_origem")

    if tem_upload_ativo() and safe_df_dados(df_origem):
        with st.expander("Prévia rápida da origem", expanded=False):
            try:
                st.dataframe(
                    _df_preview_seguro(df_origem).head(5),
                    use_container_width=True,
                    hide_index=True,
                )
            except Exception:
                st.write(_df_preview_seguro(df_origem).head(5))

    return df_origem
