from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pandas as pd
import streamlit as st

from bling_app_zero.ui.origem_dados_estado import safe_df_dados, tem_upload_ativo
from bling_app_zero.ui.origem_dados_helpers import ler_planilha_segura, log_debug
from bling_app_zero.ui.origem_dados_site import render_origem_site
from bling_app_zero.utils.xml_nfe import (
    arquivo_parece_xml_nfe,
    ler_xml_nfe,
)


_EXTENSOES_PLANILHA_PERMITIDAS = {".xlsx", ".xls", ".csv", ".xlsm", ".xlsb"}
_EXTENSOES_XML_PERMITIDAS = {".xml"}


def _somente_digitos(valor) -> str:
    return re.sub(r"\D+", "", str(valor or "").strip())


def _safe_str(valor) -> str:
    try:
        return "" if pd.isna(valor) else str(valor).strip()
    except Exception:
        return ""


def _safe_float(valor, default: float = 0.0) -> float:
    try:
        texto = str(valor or "").strip()
        if not texto:
            return default

        texto = texto.replace("R$", "").replace("r$", "").strip()
        texto = texto.replace(" ", "")

        if texto.count(",") == 1 and texto.count(".") > 1:
            texto = texto.replace(".", "").replace(",", ".")
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

        df_preview = df_preview.replace(
            {
                "nan": "",
                "None": "",
                "<NA>": "",
                "NaT": "",
            }
        )

        return df_preview
    except Exception:
        return df


def _normalizar_df_xml(df: pd.DataFrame) -> pd.DataFrame:
    try:
        if not safe_df_dados(df):
            return df

        df = df.copy()

        for col in df.columns:
            df[col] = df[col].apply(_safe_str)

        df = df.replace({"nan": "", "None": "", "<NA>": "", "NaT": ""})

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

        for nome in candidatos_preco:
            if nome in cols:
                col = cols[nome]
                df["preco_compra_xml"] = df[col].apply(_safe_float)
                break

        if "preco_compra_xml" not in df.columns:
            df["preco_compra_xml"] = 0.0

        return df
    except Exception:
        return df


def _limpar_gtin_invalido(df: pd.DataFrame) -> pd.DataFrame:
    try:
        if not safe_df_dados(df):
            return df

        df = df.copy()

        for col in df.columns:
            nome = str(col).strip().lower()
            if (
                "gtin" in nome
                or "ean" in nome
                or "codigo de barras" in nome
                or "código de barras" in nome
            ):
                df[col] = df[col].apply(
                    lambda x: _somente_digitos(x)
                    if len(_somente_digitos(x)) in [8, 12, 13, 14]
                    else ""
                )

        return df
    except Exception:
        return df


def nome_arquivo(arquivo) -> str:
    try:
        return str(getattr(arquivo, "name", "") or "").strip()
    except Exception:
        return ""


def extensao_arquivo(arquivo) -> str:
    try:
        return Path(nome_arquivo(arquivo)).suffix.lower().strip()
    except Exception:
        return ""


def arquivo_planilha_permitido(arquivo) -> bool:
    return extensao_arquivo(arquivo) in _EXTENSOES_PLANILHA_PERMITIDAS


def arquivo_xml_permitido(arquivo) -> bool:
    return extensao_arquivo(arquivo) in _EXTENSOES_XML_PERMITIDAS


def texto_extensoes_planilha() -> str:
    return ", ".join(sorted(_EXTENSOES_PLANILHA_PERMITIDAS))


def hash_arquivo_upload(arquivo) -> str:
    try:
        if arquivo is None:
            return ""

        nome = nome_arquivo(arquivo)
        size = getattr(arquivo, "size", None)

        if hasattr(arquivo, "seek"):
            try:
                arquivo.seek(0)
            except Exception:
                pass

        conteudo = b""
        if hasattr(arquivo, "getvalue"):
            try:
                conteudo = arquivo.getvalue() or b""
            except Exception:
                conteudo = b""
        elif hasattr(arquivo, "read"):
            try:
                conteudo = arquivo.read() or b""
            except Exception:
                conteudo = b""

        if hasattr(arquivo, "seek"):
            try:
                arquivo.seek(0)
            except Exception:
                pass

        base = f"{nome}|{size}|".encode("utf-8") + conteudo
        return hashlib.md5(base).hexdigest()
    except Exception:
        return ""


def carregar_modelo_bling(arquivo, tipo_modelo: str) -> bool:
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

        if hash_atual and hash_atual == hash_anterior:
            return True

        df_modelo = ler_planilha_segura(arquivo)

        if not safe_df_dados(df_modelo):
            st.error("Não foi possível ler o modelo Bling anexado.")
            return False

        if tipo_modelo == "cadastro":
            st.session_state["df_modelo_cadastro"] = df_modelo.copy()
            st.session_state["modelo_cadastro_nome"] = getattr(
                arquivo, "name", "modelo_cadastro"
            )
            st.session_state["modelo_cadastro_hash"] = hash_atual
            log_debug(
                f"Modelo de cadastro carregado: {getattr(arquivo, 'name', 'arquivo')} "
                f"({len(df_modelo)} linha(s), {len(df_modelo.columns)} coluna(s))"
            )
        else:
            st.session_state["df_modelo_estoque"] = df_modelo.copy()
            st.session_state["modelo_estoque_nome"] = getattr(
                arquivo, "name", "modelo_estoque"
            )
            st.session_state["modelo_estoque_hash"] = hash_atual
            log_debug(
                f"Modelo de estoque carregado: {getattr(arquivo, 'name', 'arquivo')} "
                f"({len(df_modelo)} linha(s), {len(df_modelo.columns)} coluna(s))"
            )

        return True
    except Exception as e:
        st.error("Erro ao carregar o modelo Bling.")
        log_debug(f"Erro ao carregar modelo Bling ({tipo_modelo}): {e}", "ERRO")
        return False


def render_modelo_bling(operacao: str) -> None:
    st.markdown("### Modelos Bling")

    if operacao == "Cadastro de Produtos":
        arquivo_modelo = st.file_uploader(
            "Anexar modelo de cadastro",
            key="modelo_cadastro",
            help=(
                "No celular, o seletor de arquivos pode bloquear formatos quando há "
                "filtro direto no upload. Por isso a validação é feita após a seleção. "
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
                    )
                except Exception as e:
                    log_debug(
                        f"Erro ao renderizar prévia do modelo de cadastro: {e}",
                        "ERRO",
                    )
                    st.write(_df_preview_seguro(df_modelo).head(5))

    else:
        arquivo_modelo = st.file_uploader(
            "Anexar modelo de estoque",
            key="modelo_estoque",
            help=(
                "No celular, o seletor de arquivos pode bloquear formatos quando há "
                "filtro direto no upload. Por isso a validação é feita após a seleção. "
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
                    )
                except Exception as e:
                    log_debug(
                        f"Erro ao renderizar prévia do modelo de estoque: {e}",
                        "ERRO",
                    )
                    st.write(_df_preview_seguro(df_modelo).head(5))


def ler_origem_xml(arquivo_xml):
    if arquivo_xml is None:
        return None

    if not arquivo_xml_permitido(arquivo_xml):
        st.error("Envie um arquivo XML válido (.xml).")
        log_debug(
            f"Arquivo XML recusado por extensão: {nome_arquivo(arquivo_xml)}",
            "ERROR",
        )
        return None

    try:
        if not arquivo_parece_xml_nfe(arquivo_xml):
            st.error("O arquivo anexado não parece ser um XML de NFe válido.")
            log_debug(
                f"Arquivo XML inválido ou não reconhecido: "
                f"{getattr(arquivo_xml, 'name', 'arquivo_xml')}",
                "ERRO",
            )
            return None

        df_xml = ler_xml_nfe(arquivo_xml)

        if not safe_df_dados(df_xml):
            st.error("Não foi possível extrair dados do XML.")
            log_debug(
                f"XML sem dados aproveitáveis: "
                f"{getattr(arquivo_xml, 'name', 'arquivo_xml')}",
                "ERRO",
            )
            return None

        df_xml = _normalizar_df_xml(df_xml)
        df_xml = _limpar_gtin_invalido(df_xml)

        st.session_state["df_origem_xml"] = df_xml.copy()
        log_debug(
            f"XML de origem carregado e normalizado: {getattr(arquivo_xml, 'name', 'arquivo_xml')} "
            f"({len(df_xml)} linha(s), {len(df_xml.columns)} coluna(s))"
        )
        return df_xml
    except Exception as e:
        log_debug(f"Erro ao ler XML de origem: {e}", "ERRO")
        st.error("Não foi possível ler o XML enviado.")
        return None


def render_origem_entrada(controlar_troca_origem_fn):
    origem = st.selectbox(
        "Selecione a origem",
        ["Planilha", "XML", "Site"],
        key="origem_tipo",
    )

    if not tem_upload_ativo():
        controlar_troca_origem_fn(origem)

    df_origem = None

    if origem == "Planilha":
        arquivo = st.file_uploader(
            "Envie a planilha",
            key="arquivo_origem_planilha",
            help=(
                "No Android, alguns gerenciadores de arquivos deixam a planilha "
                "acinzentada quando o uploader filtra por extensão. Aqui a seleção "
                "fica livre e a validação acontece depois. "
                f"Formatos aceitos: {texto_extensoes_planilha()}."
            ),
        )

        if arquivo is not None:
            if not arquivo_planilha_permitido(arquivo):
                st.error(
                    f"Formato não suportado. Envie um arquivo em: "
                    f"{texto_extensoes_planilha()}."
                )
                log_debug(
                    f"Arquivo de origem recusado por extensão: {nome_arquivo(arquivo)}",
                    "ERROR",
                )
                return None

            try:
                hash_atual = hash_arquivo_upload(arquivo)
                hash_anterior = st.session_state.get("arquivo_origem_hash", "")

                if hash_atual and hash_atual == hash_anterior:
                    df_salvo = st.session_state.get("df_origem")
                    if safe_df_dados(df_salvo):
                        return df_salvo.copy()

                df_origem = ler_planilha_segura(arquivo)

                if safe_df_dados(df_origem):
                    st.session_state["arquivo_origem_hash"] = hash_atual
                    st.session_state["arquivo_origem_nome"] = nome_arquivo(arquivo)
                    log_debug(
                        f"Planilha de origem carregada: {getattr(arquivo, 'name', 'arquivo')} "
                        f"({len(df_origem)} linha(s), {len(df_origem.columns)} coluna(s))"
                    )
                else:
                    st.error("Não foi possível ler a planilha enviada.")
                    return None
            except Exception as e:
                log_debug(f"Erro ao ler planilha de origem: {e}", "ERRO")
                st.error("Não foi possível ler a planilha enviada.")
                return None

    elif origem == "Site":
        try:
            df_origem = render_origem_site()
        except Exception as e:
            log_debug(f"Erro na origem por site: {e}", "ERRO")
            st.error("Erro ao buscar dados do site.")
            return None

    elif origem == "XML":
        arquivo_xml = st.file_uploader(
            "Envie o XML da nota fiscal",
            key="arquivo_origem_xml",
            help=(
                "No celular, a seleção fica livre para evitar bloqueio do seletor. "
                "A validação do XML é feita após a escolha."
            ),
        )

        if arquivo_xml is not None:
            df_origem = ler_origem_xml(arquivo_xml)

    return df_origem
