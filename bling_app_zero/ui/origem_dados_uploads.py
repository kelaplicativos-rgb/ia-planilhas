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


ETAPAS_VALIDAS_ORIGEM = {"origem", "mapeamento"}


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


def _set_if_changed(key: str, value: Any) -> None:
    try:
        if st.session_state.get(key) != value:
            st.session_state[key] = value
    except Exception:
        pass


def _garantir_etapa_origem_valida() -> None:
    """
    Impede que o fluxo fique preso em etapa inválida como 'upload'.
    """
    try:
        etapa = str(st.session_state.get("etapa_origem", "origem") or "origem").strip().lower()
        if etapa not in ETAPAS_VALIDAS_ORIGEM:
            log_debug(f"Etapa desconhecida: {etapa}", "ERROR")
            st.session_state["etapa_origem"] = "origem"
    except Exception:
        st.session_state["etapa_origem"] = "origem"


def _resetar_fluxo_para_origem() -> None:
    """
    Sempre que uma nova origem é carregada/trocada, o fluxo volta
    para a tela base da origem, sem derrubar a sessão.
    """
    try:
        st.session_state["etapa_origem"] = "origem"
        st.session_state.pop("coluna_em_mapeamento", None)
        st.session_state.pop("campo_destino_mapeamento", None)
        st.session_state.pop("preview_mapeamento_coluna", None)
    except Exception:
        st.session_state["etapa_origem"] = "origem"


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


def _gtin_valido_basico(valor: Any) -> str:
    try:
        digitos = _somente_digitos(valor)

        if not digitos:
            return ""

        if set(digitos) == {"0"}:
            return ""

        if len(digitos) in [8, 12, 13, 14]:
            return digitos

        return ""
    except Exception:
        return ""


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
                df[col] = df[col].apply(_gtin_valido_basico)

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
                df[col] = df[col].apply(_gtin_valido_basico)

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
    """
    Limpa apenas estados transitórios da origem atual,
    sem destruir modelos do Bling nem caches desnecessários.
    """
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
        "df_precificado",
        "origem_dados_fingerprint",
    ]

    for chave in chaves:
        try:
            st.session_state.pop(chave, None)
        except Exception:
            pass

    _resetar_fluxo_para_origem()


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

        _resetar_fluxo_para_origem()
        return df_salvo
    except Exception:
        _resetar_fluxo_para_origem()
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


def _obter_config_modelo(operacao: str) -> tuple[str, str, str, str]:
    if operacao == "Cadastro de Produtos":
        return (
            "cadastro",
            "modelo_cadastro",
            "Anexar modelo de cadastro",
            "Prévia do modelo de cadastro",
        )

    return (
        "estoque",
        "modelo_estoque",
        "Anexar modelo de estoque",
        "Prévia do modelo de estoque",
    )


def _obter_df_modelo_por_tipo(tipo_modelo: str) -> pd.DataFrame | None:
    if tipo_modelo == "cadastro":
        return st.session_state.get("df_modelo_cadastro")
    return st.session_state.get("df_modelo_estoque")


def render_modelo_bling(operacao: str) -> None:
    tipo_modelo, uploader_key, label_upload, label_preview = _obter_config_modelo(operacao)

    arquivo_modelo = st.file_uploader(
        label_upload,
        key=uploader_key,
        help=(
            "No celular, o seletor de arquivos pode bloquear formatos quando há "
            "filtro direto no upload. "
            f"Formatos aceitos: {texto_extensoes_planilha()}."
        ),
    )

    if arquivo_modelo is not None:
        carregar_modelo_bling(arquivo_modelo, tipo_modelo)

    df_modelo = _obter_df_modelo_por_tipo(tipo_modelo)
    if safe_df_dados(df_modelo):
        with st.expander(label_preview, expanded=False):
            try:
                st.dataframe(
                    _df_preview_seguro(df_modelo).head(5),
                    use_container_width=True,
                    hide_index=True,
                )
            except Exception as e:
                log_debug(
                    f"Erro ao renderizar {label_preview.lower()}: {e}",
                    "ERROR",
                )
                st.write(_df_preview_seguro(df_modelo).head(5))


def _processar_upload_planilha(arquivo_planilha: Any) -> pd.DataFrame | None:
    try:
        _garantir_etapa_origem_valida()

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
        df_origem = _limpar_gtin_invalido(df_origem)

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
        _garantir_etapa_origem_valida()

        if arquivo_xml is None:
            df_xml_mem = st.session_state.get("df_origem_xml")
            if safe_df_dados(df_xml_mem):
                return df_xml_mem
            return st.session_state.get("df_origem")

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
    _garantir_etapa_origem_valida()

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
        horizontal=False,
    )

    mapa_origem = {
        "Buscar em site": "site",
        "Anexar planilha": "planilha",
        "Anexar XML da nota fiscal": "xml",
    }
    origem_atual = mapa_origem.get(origem_escolhida, "")

    origem_anterior = str(st.session_state.get("origem_dados", "") or "").strip().lower()
    _set_if_changed("origem_dados", origem_atual)

    if origem_atual != origem_anterior:
        _resetar_fluxo_para_origem()

        if callable(on_change):
            try:
                on_change(origem_atual)
            except Exception as e:
                log_debug(f"Erro no callback de troca de origem: {e}", "ERROR")

    df_origem: pd.DataFrame | None = None

    if origem_atual == "site":
        df_site = render_origem_site()
        if safe_df_dados(df_site):
            df_site = _limpar_gtin_invalido(df_site)
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
