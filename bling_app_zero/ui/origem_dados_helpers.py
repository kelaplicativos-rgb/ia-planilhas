from __future__ import annotations

import re
from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st


# ==========================================================
# LOG
# ==========================================================
def log_debug(msg: str, nivel: str = "INFO") -> None:
    try:
        if "logs" not in st.session_state:
            st.session_state["logs"] = []

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        linha = f"[{timestamp}] [{nivel}] {msg}"
        st.session_state["logs"].append(linha)
    except Exception:
        pass


def baixar_logs_txt() -> bytes:
    try:
        logs = st.session_state.get("logs", [])
        return "\n".join(logs).encode("utf-8")
    except Exception:
        return b""


# ==========================================================
# HELPERS GERAIS
# ==========================================================
def _safe_df(df: pd.DataFrame | None) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0
    except Exception:
        return False


def _valor_vazio(valor) -> bool:
    try:
        if valor is None:
            return True

        if pd.isna(valor):
            return True

        texto = str(valor).strip().lower()
        return texto in {"", "nan", "none", "null", "<na>"}
    except Exception:
        return True


def _normalizar_nome_coluna(nome: str) -> str:
    try:
        return str(nome).strip().lower()
    except Exception:
        return ""


# ==========================================================
# GTIN LIMPEZA (🔥 CRÍTICO PRA BLING)
# ==========================================================
def _apenas_digitos(valor) -> str:
    try:
        if _valor_vazio(valor):
            return ""
        return re.sub(r"\D+", "", str(valor))
    except Exception:
        return ""


def _ean_checksum_valido(numero: str) -> bool:
    """
    Valida GTIN-8 / GTIN-12 / GTIN-13 / GTIN-14.
    """
    try:
        if not numero or not numero.isdigit():
            return False

        if len(numero) not in {8, 12, 13, 14}:
            return False

        corpo = numero[:-1]
        digito_informado = int(numero[-1])

        soma = 0
        peso_tres = True

        for dig in reversed(corpo):
            soma += int(dig) * (3 if peso_tres else 1)
            peso_tres = not peso_tres

        digito_calculado = (10 - (soma % 10)) % 10
        return digito_calculado == digito_informado
    except Exception:
        return False


def limpar_gtin_invalido(df: pd.DataFrame) -> pd.DataFrame:
    try:
        if not _safe_df(df) or df.empty:
            return df

        df_limpo = df.copy()
        colunas_gtin = []

        for col in df_limpo.columns:
            nome = _normalizar_nome_coluna(col)
            if "gtin" in nome or "ean" in nome:
                colunas_gtin.append(col)

        if not colunas_gtin:
            return df_limpo

        for col in colunas_gtin:
            def validar(v):
                numero = _apenas_digitos(v)

                if not numero:
                    return ""

                if len(numero) not in {8, 12, 13, 14}:
                    return ""

                if not _ean_checksum_valido(numero):
                    return ""

                return numero

            df_limpo[col] = df_limpo[col].apply(validar)

        log_debug(
            f"GTIN inválido limpo com sucesso em {len(colunas_gtin)} coluna(s)",
            "SUCCESS",
        )
        return df_limpo

    except Exception as e:
        log_debug(f"Erro ao limpar GTIN: {e}", "ERROR")
        return df


# ==========================================================
# VALIDAÇÃO OBRIGATÓRIA (🔥 BLOQUEIO DOWNLOAD)
# ==========================================================
def validar_campos_obrigatorios(df: pd.DataFrame) -> bool:
    try:
        if not _safe_df(df) or df.empty:
            st.error("A planilha final está vazia.")
            return False

        colunas_originais = list(df.columns)
        colunas_norm = [_normalizar_nome_coluna(c) for c in colunas_originais]

        def encontrar_coluna(candidatos: list[str]) -> str | None:
            for idx, nome in enumerate(colunas_norm):
                for candidato in candidatos:
                    if candidato in nome:
                        return colunas_originais[idx]
            return None

        coluna_descricao = encontrar_coluna(["descricao", "descrição"])
        coluna_preco = encontrar_coluna(
            [
                "preco de venda",
                "preço de venda",
                "preco",
                "preço",
                "valor",
            ]
        )

        faltantes_estrutura = []
        if coluna_descricao is None:
            faltantes_estrutura.append("Descrição")
        if coluna_preco is None:
            faltantes_estrutura.append("Preço")

        if faltantes_estrutura:
            st.error(
                "Campo obrigatório ausente: " + ", ".join(faltantes_estrutura)
            )
            return False

        if coluna_descricao is not None:
            serie_desc = df[coluna_descricao]
            if serie_desc.apply(_valor_vazio).all():
                st.error("O campo obrigatório 'Descrição' está vazio.")
                return False

        if coluna_preco is not None:
            serie_preco = (
                df[coluna_preco]
                .astype(str)
                .str.replace(".", "", regex=False)
                .str.replace(",", ".", regex=False)
                .str.replace(r"[^\d\.\-]", "", regex=True)
                .str.strip()
            )

            valores_validos = pd.to_numeric(serie_preco, errors="coerce")
            if valores_validos.isna().all():
                st.error("O campo obrigatório de preço está vazio ou inválido.")
                return False

        return True

    except Exception as e:
        log_debug(f"Erro validação: {e}", "ERROR")
        return False


# ==========================================================
# DETECÇÃO CSV QUEBROU
# ==========================================================
def _corrigir_coluna_unica(df: pd.DataFrame) -> pd.DataFrame:
    try:
        if df is None or df.empty:
            return df

        if len(df.columns) > 1:
            return df

        log_debug("CSV em coluna única detectado", "WARNING")

        col = df.columns[0]
        sample = df[col].dropna().astype(str).head(5).tolist()
        texto = "\n".join(sample)

        if texto.count(";") > texto.count(","):
            sep = ";"
        elif "\t" in texto:
            sep = "\t"
        else:
            sep = ","

        novo_df = df[col].astype(str).str.split(sep, expand=True)

        if novo_df.empty:
            return df

        cabecalho = novo_df.iloc[0].fillna("").astype(str).tolist()
        novo_df.columns = cabecalho
        novo_df = novo_df[1:].reset_index(drop=True)

        novo_df = novo_df.dropna(how="all")
        return novo_df

    except Exception as e:
        log_debug(f"Erro CSV coluna única: {e}", "ERROR")
        return df


# ==========================================================
# TEXTO
# ==========================================================
_MOJIBAKE_TOKENS = ("Ã", "Â", "â€™", "â€œ", "â€", "�")


def _texto_parece_mojibake(texto: str) -> bool:
    return any(token in texto for token in _MOJIBAKE_TOKENS)


def _normalizar_texto(valor):
    if pd.isna(valor):
        return valor
    if not isinstance(valor, str):
        return valor

    texto = valor.replace("\ufeff", "").strip()

    if _texto_parece_mojibake(texto):
        try:
            texto = texto.encode("latin1", errors="ignore").decode("utf-8", errors="ignore")
        except Exception:
            pass

    return re.sub(r"[ \t]+", " ", texto).strip()


def _normalizar_df_texto(df: pd.DataFrame) -> pd.DataFrame:
    try:
        df_normalizado = df.copy()

        df_normalizado.columns = [_normalizar_texto(str(col)) for col in df_normalizado.columns]

        for col in df_normalizado.select_dtypes(include=["object"]).columns:
            df_normalizado[col] = df_normalizado[col].map(_normalizar_texto)

        return df_normalizado

    except Exception as e:
        log_debug(f"Erro normalização: {e}", "ERROR")
        return df


# ==========================================================
# CSV ROBUSTO
# ==========================================================
def _ler_csv_tentativas(arquivo) -> pd.DataFrame | None:
    try:
        conteudo = arquivo.getvalue()
    except Exception:
        return None

    for encoding in ["utf-8-sig", "utf-8", "cp1252", "latin1"]:
        try:
            df = pd.read_csv(
                BytesIO(conteudo),
                encoding=encoding,
                sep=None,
                engine="python",
            )

            if df is not None and not df.empty:
                log_debug(f"CSV OK ({encoding})", "SUCCESS")
                return _corrigir_coluna_unica(df)

        except Exception:
            continue

    return None


# ==========================================================
# LEITOR UNIVERSAL
# ==========================================================
def ler_planilha_segura(arquivo):
    try:
        nome = str(getattr(arquivo, "name", "")).lower().strip()
        log_debug(f"Lendo arquivo: {nome or 'arquivo_sem_nome'}")

        if nome.endswith(".csv"):
            df = _ler_csv_tentativas(arquivo)

        elif nome.endswith((".xlsx", ".xls", ".xlsm", ".xlsb")):
            df = pd.read_excel(arquivo)
            log_debug("Excel OK", "SUCCESS")

        else:
            st.error("Formato não suportado.")
            return None

        if df is None:
            st.error("Erro ao ler arquivo.")
            return None

        df = df.dropna(how="all")
        df = _normalizar_df_texto(df)

        log_debug(f"Shape final: {df.shape}", "INFO")
        return df

    except Exception as e:
        log_debug(f"Erro leitura: {e}", "ERROR")
        st.error("Erro ao ler arquivo.")
        return None


# ==========================================================
# EXPORT
# ==========================================================
def exportar_excel_bytes(df: pd.DataFrame) -> bytes:
    try:
        if df is None:
            return b""

        df_export = df.copy()

        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_export.to_excel(writer, index=False)
        buffer.seek(0)
        return buffer.read()

    except Exception as e:
        log_debug(f"Erro exportar excel: {e}", "ERROR")
        return b""


def safe_preview(df: pd.DataFrame, rows: int = 20) -> pd.DataFrame:
    try:
        if df is None or df.empty:
            return pd.DataFrame()
        return df.head(rows).copy()
    except Exception as e:
        log_debug(f"Erro preview: {e}", "ERROR")
        return pd.DataFrame()
