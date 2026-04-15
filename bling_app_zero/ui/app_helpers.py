
from __future__ import annotations

import csv
import io
import re
import unicodedata
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st


ETAPAS_VALIDAS = {"origem", "precificacao", "mapeamento", "final"}
MAX_DEBUG_LOGS = 500
MAX_DEBUG_LOGS_EXIBICAO = 200


def _agora() -> str:
    try:
        return datetime.now().strftime("%H:%M:%S")
    except Exception:
        return ""


def log_debug(mensagem: str, nivel: str = "INFO") -> None:
    try:
        linha = f"[{_agora()}] [{str(nivel).upper()}] {mensagem}"
        logs = st.session_state.get("_debug_logs")
        if not isinstance(logs, list):
            logs = []
        logs.append(linha)
        st.session_state["_debug_logs"] = logs[-MAX_DEBUG_LOGS:]
    except Exception:
        pass


def _get_debug_logs() -> list[str]:
    try:
        logs = st.session_state.get("_debug_logs", [])
        if not isinstance(logs, list):
            return []
        return [str(item) for item in logs if str(item).strip()]
    except Exception:
        return []


def _get_debug_logs_texto() -> str:
    try:
        logs = _get_debug_logs()
        if not logs:
            return "Sem logs até o momento.\n"
        return "\n".join(logs[-MAX_DEBUG_LOGS:])
    except Exception:
        return "Sem logs até o momento.\n"


def render_debug_panel() -> None:
    try:
        logs = _get_debug_logs()
        texto_logs = _get_debug_logs_texto()

        if not logs:
            st.caption("Sem logs até o momento.")
        else:
            st.text("\n".join(logs[-MAX_DEBUG_LOGS_EXIBICAO:]))

        col1, col2 = st.columns(2)

        with col1:
            st.download_button(
                label="Baixar log TXT",
                data=texto_logs.encode("utf-8"),
                file_name=f"debug_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                use_container_width=True,
                key="download_debug_log_txt",
            )

        with col2:
            if st.button(
                "Limpar log",
                use_container_width=True,
                key="limpar_debug_log",
            ):
                st.session_state["_debug_logs"] = []
                st.rerun()
    except Exception as e:
        log_debug(f"Erro render_debug_panel: {e}", "ERROR")


def _normalizar_etapa(valor: object) -> str:
    try:
        etapa = str(valor or "origem").strip().lower()
    except Exception:
        etapa = "origem"

    if etapa not in ETAPAS_VALIDAS:
        return "origem"
    return etapa


def obter_etapa_global() -> str:
    try:
        for chave in ("etapa_fluxo", "etapa_origem", "etapa"):
            valor = st.session_state.get(chave)
            if valor:
                return _normalizar_etapa(valor)
    except Exception:
        pass
    return "origem"


def sincronizar_etapa_global(etapa: str) -> str:
    etapa_normalizada = _normalizar_etapa(etapa)
    st.session_state["etapa_fluxo"] = etapa_normalizada
    st.session_state["etapa_origem"] = etapa_normalizada
    st.session_state["etapa"] = etapa_normalizada
    return etapa_normalizada


def ir_para_etapa(etapa: str) -> None:
    sincronizar_etapa_global(etapa)
    st.rerun()


def garantir_estado_base() -> None:
    defaults = {
        "etapa_origem": "origem",
        "etapa": "origem",
        "etapa_fluxo": "origem",
        "df_origem": None,
        "df_saida": None,
        "df_final": None,
        "df_precificado": None,
        "df_calc_precificado": None,
        "df_preview_mapeamento": None,
        "mapping_origem": {},
        "mapping_origem_rascunho": {},
        "mapping_origem_defaults": {},
        "deposito_nome": "",
        "tipo_operacao": "Cadastro de Produtos",
        "tipo_operacao_bling": "cadastro",
        "_debug_logs": [],
        "_cache_log": "",
        "preview_final_valido": False,
        "campos_obrigatorios_faltantes": [],
        "campos_obrigatorios_alertas": [],
        "site_processado": False,
        "site_autoavanco_realizado": False,
        "mapeamento_retorno_preservado": False,
    }

    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor

    for chave in ("etapa_origem", "etapa", "etapa_fluxo"):
        st.session_state[chave] = _normalizar_etapa(st.session_state.get(chave))


def _safe_str(valor: Any) -> str:
    try:
        if valor is None:
            return ""
        if pd.isna(valor):
            return ""
    except Exception:
        pass

    try:
        texto = str(valor).strip()
    except Exception:
        return ""

    if texto.lower() in {"none", "nan", "nat"}:
        return ""
    return texto


def safe_df_estrutura(df: Any) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0
    except Exception:
        return False


def safe_df_dados(df: Any) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0
    except Exception:
        return False


def _normalizar_coluna(nome: Any) -> str:
    texto = _safe_str(nome).lower()
    if not texto:
        return ""

    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _so_digitos(valor: Any) -> str:
    return re.sub(r"\D+", "", _safe_str(valor))


def _checksum_gtin_ok(gtin: str) -> bool:
    if len(gtin) not in {8, 12, 13, 14}:
        return False

    try:
        numeros = [int(c) for c in gtin]
        corpo = numeros[:-1]
        verificador = numeros[-1]

        soma = 0
        peso3 = True
        for numero in reversed(corpo):
            soma += numero * (3 if peso3 else 1)
            peso3 = not peso3

        calculado = (10 - (soma % 10)) % 10
        return calculado == verificador
    except Exception:
        return False


def _is_coluna_gtin(nome_coluna: str) -> bool:
    nome = _normalizar_coluna(nome_coluna)
    return any(
        token in nome
        for token in ("gtin", "ean", "codigo de barras", "codigo barras")
    )


def limpar_gtin_invalido(df: pd.DataFrame) -> pd.DataFrame:
    try:
        if not isinstance(df, pd.DataFrame):
            return pd.DataFrame()

        df_limpo = df.copy()

        for col in df_limpo.columns:
            if _is_coluna_gtin(str(col)):
                df_limpo[col] = df_limpo[col].apply(
                    lambda v: (_so_digitos(v) if _checksum_gtin_ok(_so_digitos(v)) else "")
                )

        return df_limpo
    except Exception as e:
        log_debug(f"Erro limpar_gtin_invalido: {e}", "ERROR")
        return df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()


def _normalizar_urls_imagem(valor: Any) -> str:
    texto = _safe_str(valor)
    if not texto:
        return ""

    texto = (
        texto.replace("\n", "|")
        .replace("\r", "|")
        .replace(";", "|")
    )

    partes = [parte.strip() for parte in texto.split("|") if parte.strip()]

    unicos: list[str] = []
    vistos: set[str] = set()

    for item in partes:
        if item not in vistos:
            vistos.add(item)
            unicos.append(item)

    return "|".join(unicos)


def _aplicar_tratamento_imagens(df: pd.DataFrame) -> pd.DataFrame:
    try:
        df_out = df.copy()
        for col in df_out.columns:
            nome = _normalizar_coluna(col)
            if "imagem" in nome or "url" in nome:
                df_out[col] = df_out[col].apply(_normalizar_urls_imagem)
        return df_out
    except Exception as e:
        log_debug(f"Erro _aplicar_tratamento_imagens: {e}", "ERROR")
        return df.copy()


def _normalizar_situacao(valor: Any) -> str:
    texto = _safe_str(valor).lower()

    if not texto:
        return "Ativo"

    if texto in {"inativo", "inactive", "0", "false", "nao", "não"}:
        return "Ativo"

    if texto in {"ativo", "active", "1", "true", "sim", "yes"}:
        return "Ativo"

    return "Ativo"


def _aplicar_tratamento_situacao(df: pd.DataFrame) -> pd.DataFrame:
    try:
        df_out = df.copy()
        for col in df_out.columns:
            nome = _normalizar_coluna(col)
            if "situacao" in nome:
                df_out[col] = df_out[col].apply(_normalizar_situacao)
        return df_out
    except Exception as e:
        log_debug(f"Erro _aplicar_tratamento_situacao: {e}", "ERROR")
        return df.copy()


def sanitizar_dados_reais(df: pd.DataFrame) -> pd.DataFrame:
    try:
        if not isinstance(df, pd.DataFrame):
            return pd.DataFrame()

        df_out = df.copy()
        df_out = df_out.replace({None: ""}).fillna("")

        for col in df_out.columns:
            df_out[col] = df_out[col].apply(
                lambda v: "" if _safe_str(v).lower() == "nan" else v
            )

        return df_out
    except Exception as e:
        log_debug(f"Erro sanitizar_dados_reais: {e}", "ERROR")
        return df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()


def _sanitizar_df_para_csv(df: pd.DataFrame) -> pd.DataFrame:
    try:
        df_out = df.copy()
        for col in df_out.columns:
            df_out[col] = df_out[col].apply(_safe_str)
        return df_out
    except Exception as e:
        log_debug(f"Erro ao sanitizar DataFrame para CSV: {e}", "ERROR")
        return df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()


def blindar_df_para_download(df: pd.DataFrame) -> pd.DataFrame:
    try:
        if not isinstance(df, pd.DataFrame):
            return pd.DataFrame()

        df_blindado = df.copy()
        df_blindado = limpar_gtin_invalido(df_blindado)
        df_blindado = _aplicar_tratamento_imagens(df_blindado)
        df_blindado = _aplicar_tratamento_situacao(df_blindado)
        df_blindado = sanitizar_dados_reais(df_blindado)
        df_blindado = df_blindado.replace({None: ""}).fillna("")
        df_blindado = _sanitizar_df_para_csv(df_blindado)
        return df_blindado
    except Exception as e:
        log_debug(f"Erro em blindar_df_para_download: {e}", "ERROR")
        return df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()


def _encontrar_primeira_coluna(df: pd.DataFrame, aliases: list[str]) -> str | None:
    colunas_normalizadas = {str(col): _normalizar_coluna(col) for col in df.columns}

    for col_real, col_norm in colunas_normalizadas.items():
        if any(alias in col_norm for alias in aliases):
            return col_real

    return None


def _coluna_tem_algum_valor(df: pd.DataFrame, coluna: str) -> bool:
    try:
        serie = df[coluna].fillna("").astype(str).str.strip()
        return not serie.eq("").all()
    except Exception:
        return False


def validar_campos_obrigatorios(df: pd.DataFrame) -> dict[str, Any]:
    try:
        if not isinstance(df, pd.DataFrame) or df.empty:
            resultado = {
                "ok": False,
                "faltantes": ["DataFrame vazio"],
                "alertas": ["Nenhum dado disponível para validar."],
            }
            st.session_state["preview_final_valido"] = False
            st.session_state["campos_obrigatorios_faltantes"] = resultado["faltantes"]
            st.session_state["campos_obrigatorios_alertas"] = resultado["alertas"]
            return resultado

        tipo_operacao = _safe_str(st.session_state.get("tipo_operacao_bling")).lower()

        candidatos: dict[str, list[str]] = {
            "Descrição": ["descricao", "descrição"],
        }

        if tipo_operacao == "estoque":
            candidatos["Depósito (OBRIGATÓRIO)"] = ["deposito", "depósito"]
            candidatos["Balanço (OBRIGATÓRIO)"] = ["balanco", "balanço"]
        else:
            candidatos["Descrição Curta"] = ["descricao curta", "descrição curta"]

        faltantes: list[str] = []
        alertas: list[str] = []

        for nome_campo, aliases in candidatos.items():
            col_encontrada = _encontrar_primeira_coluna(df, aliases)

            if col_encontrada is None:
                faltantes.append(nome_campo)
                alertas.append(f"Coluna obrigatória ausente: {nome_campo}")
                continue

            if not _coluna_tem_algum_valor(df, col_encontrada):
                faltantes.append(nome_campo)
                alertas.append(f"Coluna obrigatória vazia: {nome_campo}")

        ok = len(faltantes) == 0

        st.session_state["preview_final_valido"] = ok
        st.session_state["campos_obrigatorios_faltantes"] = faltantes
        st.session_state["campos_obrigatorios_alertas"] = alertas

        return {
            "ok": ok,
            "faltantes": faltantes,
            "alertas": alertas,
        }
    except Exception as e:
        log_debug(f"Erro validar_campos_obrigatorios: {e}", "ERROR")
        st.session_state["preview_final_valido"] = False
        st.session_state["campos_obrigatorios_faltantes"] = ["Falha na validação"]
        st.session_state["campos_obrigatorios_alertas"] = [
            "Erro interno durante a validação dos campos obrigatórios."
        ]
        return {
            "ok": False,
            "faltantes": ["Falha na validação"],
            "alertas": ["Erro interno durante a validação dos campos obrigatórios."],
        }


def exportar_csv_bytes(df: pd.DataFrame) -> bytes:
    try:
        df_download = blindar_df_para_download(df)

        if not isinstance(df_download, pd.DataFrame):
            return b""

        if len(df_download.columns) == 0:
            return b""

        csv_buffer = io.StringIO()
        df_download.to_csv(
            csv_buffer,
            index=False,
            sep=";",
            lineterminator="\r\n",
            quoting=csv.QUOTE_MINIMAL,
        )
        return csv_buffer.getvalue().encode("utf-8-sig")
    except Exception as e:
        log_debug(f"Erro ao exportar CSV: {e}", "ERROR")
        return b""


def gerar_nome_arquivo_download() -> str:
    tipo_operacao = _safe_str(st.session_state.get("tipo_operacao_bling")).lower()

    if tipo_operacao == "estoque":
        return "bling_export_estoque.csv"

    if tipo_operacao == "cadastro":
        return "bling_export_cadastro.csv"

    return "bling_export.csv"
