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

    # Ajustes para o restante do sistema entender melhor o XML
    if "vuncom" in df.columns and "custo_total_item_xml" not in df.columns:
        df["custo_total_item_xml"] = df["vuncom"]

    return df


def _ler_arquivo_upload(arquivo) -> tuple[pd.DataFrame, str]:
    nome_arquivo = str(getattr(arquivo, "name", "")).lower()

    if nome_arquivo.endswith(".xml"):
        xml_bytes = arquivo.getvalue()

        try:
            return _parse_nfe_xml_produtos(xml_bytes), "XML NF-e"
        except Exception:
            arquivo.seek(0)
            try:
                return pd.read_xml(io.BytesIO(xml_bytes)), "XML genérico"
            except Exception as e:
                raise ValueError(f"Não foi possível ler o XML: {e}") from e

    if nome_arquivo.endswith(".csv"):
        try:
            return pd.read_csv(arquivo), "CSV"
        except UnicodeDecodeError:
            arquivo.seek(0)
            return pd.read_csv(arquivo, encoding="latin1"), "CSV"

    return pd.read_excel(arquivo), "Planilha"


def _montar_df_saida(df_origem: pd.DataFrame, mapeamento_manual: dict) -> pd.DataFrame:
    df_saida = pd.DataFrame()

    for origem, destino in mapeamento_manual.items():
        if origem in df_origem.columns and destino:
            df_saida[destino] = df_origem[origem]

    return df_saida


def _limpar_estado_geracao() -> None:
    st.session_state.pop("df_saida", None)
    st.session_state.pop("df_saida_preview_hash", None)
    st.session_state.pop("excel_saida_bytes", None)
    st.session_state.pop("excel_saida_nome", None)


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

    # Se mudou o arquivo, limpa a geração anterior
    if st.session_state.get("df_origem_hash") != origem_hash:
        _limpar_estado_geracao()

    st.session_state["df_origem"] = df.copy()
    st.session_state["origem_atual"] = origem_atual
    st.session_state["origem_arquivo_nome"] = nome_arquivo

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

    df_preview = _montar_df_saida(
        df_origem=df,
        mapeamento_manual=st.session_state.get("mapeamento_manual", {}),
    )

    if not df_preview.empty:
        st.dataframe(df_preview.head(3), use_container_width=True)
    else:
        st.info("Nenhum campo foi mapeado automaticamente até o momento.")

    if st.button("Gerar automático", use_container_width=True):
        try:
            df_saida = _montar_df_saida(
                df_origem=df,
                mapeamento_manual=st.session_state.get("mapeamento_manual", {}),
            )

            if df_saida.empty:
                st.warning(
                    "Nenhum dado pôde ser gerado porque não houve mapeamento válido."
                )
                _limpar_estado_geracao()
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

            excel_bytes = df_to_excel_bytes(df_saida)

            st.session_state["df_saida"] = df_saida.copy()
            st.session_state["df_saida_preview_hash"] = origem_hash
            st.session_state["excel_saida_bytes"] = excel_bytes
            st.session_state["excel_saida_nome"] = "bling_auto.xlsx"

            st.success("Arquivo gerado. Confira o preview final antes de baixar.")

        except Exception as e:
            st.error(f"Erro ao gerar arquivo: {e}")
            _limpar_estado_geracao()

    df_saida_state = st.session_state.get("df_saida")
    df_saida_hash = st.session_state.get("df_saida_preview_hash")
    excel_saida_bytes = st.session_state.get("excel_saida_bytes")
    excel_saida_nome = st.session_state.get("excel_saida_nome", "bling_auto.xlsx")

    if (
        isinstance(df_saida_state, pd.DataFrame)
        and not df_saida_state.empty
        and df_saida_hash == origem_hash
        and excel_saida_bytes
    ):
        st.subheader("Preview final do arquivo que será baixado")
        st.caption(
            f"{len(df_saida_state)} linhas × {len(df_saida_state.columns)} colunas"
        )
        st.dataframe(df_saida_state.head(20), use_container_width=True)

        st.download_button(
            "Baixar arquivo final",
            data=excel_saida_bytes,
            file_name=excel_saida_nome,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )


def tela_origem_dados() -> None:
    render_origem_dados()
