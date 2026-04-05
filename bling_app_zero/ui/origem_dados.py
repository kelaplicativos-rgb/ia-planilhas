import csv
import hashlib
import io
import xml.etree.ElementTree as ET

import pandas as pd
import streamlit as st

from bling_app_zero.core.mapeamento_ia import mapear_colunas_ia
from bling_app_zero.core.memoria_fornecedor import (
    recuperar_mapeamento,
    salvar_mapeamento,
)
from bling_app_zero.core.precificacao import calcular_preco_compra_automatico_df
from bling_app_zero.utils.excel import df_to_excel_bytes


COLUNAS_DESTINO = [
    "nome",
    "preco",
    "custo",
    "sku",
    "gtin",
    "ncm",
    "marca",
    "estoque",
    "categoria",
    "peso",
]


def _gerar_hash_arquivo(df: pd.DataFrame, nome_arquivo: str) -> str:
    base = f"{nome_arquivo}|{'|'.join(map(str, df.columns))}|{len(df)}"
    return hashlib.md5(base.encode("utf-8")).hexdigest()


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _find_child_text(element: ET.Element, child_name: str) -> str:
    for child in list(element):
        if _local_name(child.tag) == child_name:
            return (child.text or "").strip()
    return ""


def _parse_nfe_xml_produtos(xml_bytes: bytes) -> pd.DataFrame:
    root = ET.fromstring(xml_bytes)
    itens = []

    for det in root.iter():
        if _local_name(det.tag) != "det":
            continue

        prod = None
        imposto = None

        for child in list(det):
            nome = _local_name(child.tag)
            if nome == "prod":
                prod = child
            elif nome == "imposto":
                imposto = child

        if prod is None:
            continue

        item = {
            "cprod": _find_child_text(prod, "cProd"),
            "cean": _find_child_text(prod, "cEAN"),
            "xprod": _find_child_text(prod, "xProd"),
            "ncm": _find_child_text(prod, "NCM"),
            "cfop": _find_child_text(prod, "CFOP"),
            "ucom": _find_child_text(prod, "uCom"),
            "qcom": _find_child_text(prod, "qCom"),
            "vuncom": _find_child_text(prod, "vUnCom"),
            "vprod": _find_child_text(prod, "vProd"),
            "ceantrib": _find_child_text(prod, "cEANTrib"),
            "utrib": _find_child_text(prod, "uTrib"),
            "qtrib": _find_child_text(prod, "qTrib"),
            "vuntrib": _find_child_text(prod, "vUnTrib"),
        }

        if imposto is not None:
            item["vtottrib"] = _find_child_text(imposto, "vTotTrib")
        else:
            item["vtottrib"] = ""

        itens.append(item)

    if not itens:
        raise ValueError("Nenhum produto foi encontrado no XML da NF-e.")

    df = pd.DataFrame(itens)

    if "vuncom" in df.columns and "custo_total_item_xml" not in df.columns:
        df["custo_total_item_xml"] = df["vuncom"]

    return df


def _detectar_encoding(raw_bytes: bytes) -> str:
    candidatos = ["utf-8", "utf-8-sig", "cp1252", "latin1"]

    for enc in candidatos:
        try:
            raw_bytes.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue

    return "latin1"


def _detectar_separador(texto: str) -> str:
    amostra = "\n".join(texto.splitlines()[:20]).strip()

    if not amostra:
        return ","

    try:
        dialect = csv.Sniffer().sniff(amostra, delimiters=[",", ";", "\t", "|"])
        return dialect.delimiter
    except Exception:
        contagens = {
            ";": amostra.count(";"),
            ",": amostra.count(","),
            "\t": amostra.count("\t"),
            "|": amostra.count("|"),
        }
        return max(contagens, key=contagens.get) if any(contagens.values()) else ","


def _normalizar_df_csv(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    colunas_invalidas = [col for col in df.columns if str(col).startswith("Unnamed:")]
    if colunas_invalidas and len(colunas_invalidas) == len(df.columns):
        df.columns = [f"coluna_{i + 1}" for i in range(len(df.columns))]

    df = df.dropna(axis=0, how="all")
    df = df.dropna(axis=1, how="all")

    return df


def _ler_csv_robusto(arquivo) -> pd.DataFrame:
    raw_bytes = arquivo.getvalue()
    if not raw_bytes:
        raise ValueError("O CSV enviado está vazio.")

    encoding = _detectar_encoding(raw_bytes)
    texto = raw_bytes.decode(encoding, errors="replace")
    separador = _detectar_separador(texto)

    tentativas = [
        {
            "sep": separador,
            "engine": "python",
            "dtype": str,
            "keep_default_na": False,
            "on_bad_lines": "warn",
            "quotechar": '"',
            "skip_blank_lines": True,
        },
        {
            "sep": separador,
            "engine": "python",
            "dtype": str,
            "keep_default_na": False,
            "on_bad_lines": "skip",
            "quotechar": '"',
            "skip_blank_lines": True,
        },
        {
            "sep": None,
            "engine": "python",
            "dtype": str,
            "keep_default_na": False,
            "on_bad_lines": "warn",
            "quotechar": '"',
            "skip_blank_lines": True,
        },
    ]

    ultimo_erro = None

    for kwargs in tentativas:
        try:
            df = pd.read_csv(io.StringIO(texto), **kwargs)
            df = _normalizar_df_csv(df)

            if df is not None and not df.empty and len(df.columns) > 0:
                st.session_state["csv_encoding_detectado"] = encoding
                st.session_state["csv_separador_detectado"] = (
                    kwargs["sep"] if kwargs["sep"] is not None else "auto"
                )
                return df
        except Exception as e:
            ultimo_erro = e

    raise ValueError(
        "Não foi possível ler o CSV automaticamente. "
        f"Separador detectado: '{separador}' | encoding: '{encoding}'. "
        f"Detalhe técnico: {ultimo_erro}"
    )


def _ler_arquivo_upload(arquivo) -> tuple[pd.DataFrame, str]:
    nome_arquivo = str(getattr(arquivo, "name", "")).lower()

    if nome_arquivo.endswith(".xml"):
        xml_bytes = arquivo.getvalue()
        try:
            return _parse_nfe_xml_produtos(xml_bytes), "XML NF-e"
        except Exception:
            try:
                return pd.read_xml(io.BytesIO(xml_bytes)), "XML genérico"
            except Exception as e:
                raise ValueError(f"Não foi possível ler o XML: {e}") from e

    if nome_arquivo.endswith(".csv"):
        return _ler_csv_robusto(arquivo), "CSV"

    return pd.read_excel(arquivo), "Planilha"


def render_origem_dados() -> None:
    st.title("IA Automática com Memória")

    arquivo = st.file_uploader(
        "Anexar planilha ou XML",
        type=["xlsx", "xls", "csv", "xml"],
    )

    if not arquivo:
        return

    try:
        df, origem_atual = _ler_arquivo_upload(arquivo)
    except Exception as e:
        st.error(f"Erro ao ler arquivo: {e}")
        return

    if df is None or df.empty:
        st.warning("O arquivo foi lido, mas não possui dados para processar.")
        return

    nome_arquivo = str(getattr(arquivo, "name", "arquivo"))
    origem_hash = _gerar_hash_arquivo(df, nome_arquivo)

    st.session_state["df_origem"] = df.copy()
    st.session_state["origem_atual"] = origem_atual
    st.session_state["origem_arquivo_nome"] = nome_arquivo

    if origem_atual == "CSV":
        encoding_detectado = st.session_state.get("csv_encoding_detectado")
        separador_detectado = st.session_state.get("csv_separador_detectado")
        if encoding_detectado or separador_detectado:
            st.caption(
                f"CSV lido com encoding `{encoding_detectado or 'n/d'}` "
                f"e separador `{separador_detectado or 'n/d'}`."
            )

    colunas_origem = list(df.columns)
    memoria = st.session_state.get("mapeamento_memoria", {})
    mapeamento_memoria = recuperar_mapeamento(memoria, colunas_origem)

    if mapeamento_memoria:
        st.success("⚡ Mapeamento recuperado automaticamente (memória)")
        mapeamento_final = dict(mapeamento_memoria)
    else:
        mapa_ia = mapear_colunas_ia(colunas_origem, COLUNAS_DESTINO)
        mapeamento_final = {}

        for col, dados in mapa_ia.items():
            destino = dados.get("destino")
            score = float(dados.get("score", 0) or 0)
            if destino and score >= 0.6:
                mapeamento_final[col] = destino

    if (
        "mapeamento_manual" not in st.session_state
        or st.session_state.get("df_origem_hash") != origem_hash
    ):
        st.session_state["mapeamento_manual"] = dict(mapeamento_final)
        st.session_state["df_origem_hash"] = origem_hash

    st.subheader("Preview do mapeamento")

    df_preview = pd.DataFrame()
    for origem, destino in st.session_state.get("mapeamento_manual", {}).items():
        if origem in df.columns:
            df_preview[destino] = df[origem]

    if not df_preview.empty:
        st.dataframe(df_preview.head(3), use_container_width=True)
    else:
        st.info("Nenhum campo foi mapeado automaticamente até o momento.")
        st.dataframe(df.head(5), use_container_width=True)

    if st.button("Gerar automático", use_container_width=True):
        try:
            df_saida = pd.DataFrame()

            for origem, destino in st.session_state.get("mapeamento_manual", {}).items():
                if origem in df.columns:
                    df_saida[destino] = df[origem]

            if df_saida.empty:
                st.warning(
                    "Nenhum dado pôde ser gerado porque não houve mapeamento válido."
                )
                return

            preco_compra = calcular_preco_compra_automatico_df(df_saida)
            st.session_state["preco_compra_modulo_precificacao"] = float(
                preco_compra or 0.0
            )

            if "custo" not in df_saida.columns and preco_compra:
                df_saida["custo"] = float(preco_compra)

            salvar_mapeamento(
                memoria,
                colunas_origem,
                st.session_state["mapeamento_manual"],
            )
            st.session_state["mapeamento_memoria"] = memoria
            st.session_state["df_saida"] = df_saida.copy()

            excel_bytes = df_to_excel_bytes(df_saida)

            st.download_button(
                "Baixar",
                data=excel_bytes,
                file_name="bling_auto.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

            st.success("Aprendido e gerado automaticamente.")

        except Exception as e:
            st.error(f"Erro ao gerar arquivo: {e}")


def tela_origem_dados() -> None:
    render_origem_dados()
