import csv
import hashlib
import io
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st
from pandas.errors import ParserError

from bling_app_zero.core.mapeamento_ia import mapear_colunas_ia
from bling_app_zero.core.memoria_fornecedor import (
    recuperar_mapeamento,
    salvar_mapeamento,
)
from bling_app_zero.core.precificacao import calcular_preco_compra_automatico_df
from bling_app_zero.utils.excel import df_to_excel_bytes


# ==========================================================
# CONFIGURAÇÃO DAS OPERAÇÕES
# ==========================================================
OPERACOES = {
    "cadastro": {
        "label": "Cadastro de produtos",
        "arquivo_saida": "bling_cadastro.xlsx",
        "colunas_destino": [
            "sku",
            "nome",
            "gtin",
            "ncm",
            "marca",
            "categoria",
            "preco",
            "custo",
            "estoque",
            "peso",
        ],
        "defaults": {},
    },
    "estoque": {
        "label": "Atualização de estoque",
        "arquivo_saida": "bling_estoque.xlsx",
        "colunas_destino": [
            "sku",
            "estoque",
        ],
        "defaults": {},
    },
}


# ==========================================================
# UTILITÁRIOS
# ==========================================================
def _log(msg: str) -> None:
    if "logs" not in st.session_state:
        st.session_state["logs"] = []
    st.session_state["logs"].append(str(msg))


def _gerar_hash_arquivo(df: pd.DataFrame, nome_arquivo: str) -> str:
    base = f"{nome_arquivo}|{'|'.join(map(str, df.columns))}|{len(df)}"
    return hashlib.md5(base.encode("utf-8")).hexdigest()


def _normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(col).strip() for col in df.columns]
    return df


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _find_child_text(element: ET.Element, child_name: str) -> str:
    for child in list(element):
        if _local_name(child.tag) == child_name:
            return (child.text or "").strip()
    return ""


# ==========================================================
# XML
# ==========================================================
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

    return _normalizar_colunas(df)


# ==========================================================
# CSV ROBUSTO
# ==========================================================
def _detectar_encoding(raw_bytes: bytes) -> str:
    candidatos = ["utf-8-sig", "utf-8", "cp1252", "latin1"]

    for enc in candidatos:
        try:
            raw_bytes.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue

    return "latin1"


def _detectar_separador(texto: str) -> str | None:
    amostra = "\n".join(texto.splitlines()[:20]).strip()
    if not amostra:
        return None

    try:
        dialect = csv.Sniffer().sniff(amostra, delimiters=[",", ";", "\t", "|"])
        return dialect.delimiter
    except Exception:
        pass

    contagens = {
        ";": amostra.count(";"),
        ",": amostra.count(","),
        "\t": amostra.count("\t"),
        "|": amostra.count("|"),
    }

    melhor = max(contagens, key=contagens.get)
    if contagens[melhor] > 0:
        return melhor

    return None


def _tentar_ler_csv_com_config(
    texto: str,
    sep: str | None,
    tolerante: bool = False,
) -> pd.DataFrame:
    kwargs = {
        "engine": "python",
        "dtype": str,
        "keep_default_na": False,
    }

    if sep:
        kwargs["sep"] = sep
    else:
        kwargs["sep"] = None

    if tolerante:
        kwargs["on_bad_lines"] = "skip"

    return pd.read_csv(io.StringIO(texto), **kwargs)


def _ler_csv_robusto(arquivo) -> Tuple[pd.DataFrame, str]:
    raw_bytes = arquivo.getvalue()
    encoding = _detectar_encoding(raw_bytes)
    texto = raw_bytes.decode(encoding, errors="replace")
    separador = _detectar_separador(texto)

    tentativas = []

    configuracoes = [
        {"sep": separador, "tolerante": False, "rotulo": "detecção automática"},
        {"sep": ";", "tolerante": False, "rotulo": "separador ;"},
        {"sep": ",", "tolerante": False, "rotulo": "separador ,"},
        {"sep": "\t", "tolerante": False, "rotulo": "separador TAB"},
        {"sep": "|", "tolerante": False, "rotulo": "separador |"},
        {"sep": separador, "tolerante": True, "rotulo": "modo tolerante"},
        {"sep": ";", "tolerante": True, "rotulo": "modo tolerante ;"},
        {"sep": ",", "tolerante": True, "rotulo": "modo tolerante ,"},
    ]

    melhor_df = None
    melhor_rotulo = ""

    for cfg in configuracoes:
        try:
            df = _tentar_ler_csv_com_config(
                texto=texto,
                sep=cfg["sep"],
                tolerante=cfg["tolerante"],
            )
            df = _normalizar_colunas(df)

            if df is not None and not df.empty and len(df.columns) >= 2:
                melhor_df = df
                melhor_rotulo = cfg["rotulo"]
                break

        except ParserError as e:
            tentativas.append(f"{cfg['rotulo']}: {e}")
        except Exception as e:
            tentativas.append(f"{cfg['rotulo']}: {e}")

    if melhor_df is None or melhor_df.empty:
        detalhes = " | ".join(tentativas[-4:]) if tentativas else "sem detalhes"
        raise ValueError(f"Não foi possível ler o CSV. Tentativas: {detalhes}")

    _log(
        f"CSV lido com encoding {encoding} e estratégia {melhor_rotulo}"
        + (f" | separador detectado: {repr(separador)}" if separador else "")
    )

    return melhor_df, f"CSV ({encoding})"


# ==========================================================
# LEITURA DE ARQUIVO
# ==========================================================
def _ler_arquivo_upload(arquivo) -> Tuple[pd.DataFrame, str]:
    nome_arquivo = str(getattr(arquivo, "name", "")).lower()

    if nome_arquivo.endswith(".xml"):
        xml_bytes = arquivo.getvalue()

        try:
            return _parse_nfe_xml_produtos(xml_bytes), "XML NF-e"
        except Exception:
            arquivo.seek(0)
            try:
                df_xml = pd.read_xml(io.BytesIO(xml_bytes))
                return _normalizar_colunas(df_xml), "XML genérico"
            except Exception as e:
                raise ValueError(f"Não foi possível ler o XML: {e}") from e

    if nome_arquivo.endswith(".csv"):
        return _ler_csv_robusto(arquivo)

    df_excel = pd.read_excel(arquivo, dtype=str)
    return _normalizar_colunas(df_excel), "Planilha"


# ==========================================================
# MAPEAMENTO / GERAÇÃO
# ==========================================================
def _limpar_estado_geracao(modo: str | None = None) -> None:
    chaves_base = [
        "df_saida",
        "df_saida_preview_hash",
        "excel_saida_bytes",
        "excel_saida_nome",
        "df_origem_hash",
    ]
    for chave in chaves_base:
        st.session_state.pop(chave, None)

    if modo:
        st.session_state.pop(f"mapeamento_manual_{modo}", None)


def _montar_df_saida(
    df_origem: pd.DataFrame,
    colunas_destino: List[str],
    mapeamento_manual: Dict[str, str],
    defaults: Dict[str, object] | None = None,
) -> pd.DataFrame:
    defaults = defaults or {}
    df_saida = pd.DataFrame(index=df_origem.index)

    for destino in colunas_destino:
        origem_selecionada = str(mapeamento_manual.get(destino, "") or "").strip()

        if origem_selecionada and origem_selecionada in df_origem.columns:
            df_saida[destino] = df_origem[origem_selecionada]
        else:
            valor_padrao = defaults.get(destino, "")
            df_saida[destino] = valor_padrao

    return df_saida


def _sugerir_mapeamento_inicial(
    colunas_origem: List[str],
    colunas_destino: List[str],
    memoria: Dict,
) -> Dict[str, str]:
    mapeamento_manual: Dict[str, str] = {}

    try:
        mapeamento_memoria = recuperar_mapeamento(memoria, colunas_origem)
    except Exception:
        mapeamento_memoria = {}

    if mapeamento_memoria:
        for origem, destino in mapeamento_memoria.items():
            if destino in colunas_destino and origem in colunas_origem:
                if destino not in mapeamento_manual:
                    mapeamento_manual[destino] = origem

    try:
        mapa_ia = mapear_colunas_ia(colunas_origem, colunas_destino)
    except Exception:
        mapa_ia = {}

    for origem, dados in mapa_ia.items():
        destino = str(dados.get("destino", "") or "").strip()
        score = float(dados.get("score", 0) or 0)

        if (
            destino
            and destino in colunas_destino
            and origem in colunas_origem
            and score >= 0.60
            and destino not in mapeamento_manual
        ):
            mapeamento_manual[destino] = origem

    return mapeamento_manual


def _render_mapeamento_manual(
    df_origem: pd.DataFrame,
    colunas_destino: List[str],
    state_key: str,
) -> Dict[str, str]:
    st.subheader("Mapeamento manual")
    st.caption("Defina manualmente o que vai para o arquivo final antes de gerar o preview final.")

    if state_key not in st.session_state:
        st.session_state[state_key] = {}

    mapeamento = dict(st.session_state.get(state_key, {}))
    colunas_origem = list(df_origem.columns)

    cab1, cab2, cab3 = st.columns([1.2, 1.8, 2.0])
    with cab1:
        st.markdown("**Coluna final**")
    with cab2:
        st.markdown("**Coluna da origem**")
    with cab3:
        st.markdown("**Exemplo**")

    usados = set()

    for destino in colunas_destino:
        atual = str(mapeamento.get(destino, "") or "").strip()
        if atual:
            usados.add(atual)

        c1, c2, c3 = st.columns([1.2, 1.8, 2.0])

        with c1:
            st.markdown(f"`{destino}`")

        with c2:
            opcoes = [""]
            for col in colunas_origem:
                if col == atual or col not in (usados - ({atual} if atual else set())):
                    opcoes.append(col)

            index = opcoes.index(atual) if atual in opcoes else 0

            novo_valor = st.selectbox(
                f"Origem para {destino}",
                opcoes,
                index=index,
                key=f"map_{state_key}_{destino}",
                label_visibility="collapsed",
            )

            mapeamento[destino] = novo_valor or ""

        with c3:
            origem_exemplo = mapeamento.get(destino, "")
            if origem_exemplo and origem_exemplo in df_origem.columns:
                serie = df_origem[origem_exemplo].astype(str).replace("nan", "").replace("None", "")
                serie = serie[serie.str.strip() != ""]
                exemplo = serie.iloc[0] if not serie.empty else ""
                st.caption(str(exemplo)[:120] if exemplo else "—")
            else:
                st.caption("—")

    st.session_state[state_key] = mapeamento
    return mapeamento


# ==========================================================
# UI
# ==========================================================
def render_origem_dados() -> None:
    st.title("Origem dos dados")

    modo = st.radio(
        "Selecione a operação antes de tudo",
        options=["cadastro", "estoque"],
        format_func=lambda x: OPERACOES[x]["label"],
        horizontal=True,
        key="tipo_operacao_bling",
    )

    config = OPERACOES[modo]
    colunas_destino = config["colunas_destino"]
    arquivo_saida = config["arquivo_saida"]
    defaults = config.get("defaults", {})

    st.info(
        f"Operação selecionada: **{config['label']}**. "
        "Você vai mapear manualmente, gerar o preview final e só depois baixar."
    )

    arquivo = st.file_uploader(
        "Anexar planilha ou XML",
        type=["xlsx", "xls", "csv", "xml"],
        key=f"upload_{modo}",
    )

    if not arquivo:
        return

    try:
        df_origem, origem_atual = _ler_arquivo_upload(arquivo)
    except Exception as e:
        st.error(f"Erro ao ler arquivo: {e}")
        _log(f"Erro ao ler arquivo {getattr(arquivo, 'name', 'arquivo')}: {e}")
        return

    if df_origem is None or df_origem.empty:
        st.warning("O arquivo foi lido, mas não possui dados para processar.")
        return

    nome_arquivo = str(getattr(arquivo, "name", "arquivo"))
    origem_hash = _gerar_hash_arquivo(df_origem, f"{modo}|{nome_arquivo}")

    if st.session_state.get("df_origem_hash") != origem_hash:
        _limpar_estado_geracao()
        st.session_state.pop(f"mapeamento_manual_{modo}", None)

    st.session_state["df_origem"] = df_origem.copy()
    st.session_state["origem_atual"] = origem_atual
    st.session_state["origem_arquivo_nome"] = nome_arquivo
    st.session_state["df_origem_hash"] = origem_hash

    st.caption(f"Arquivo lido: `{nome_arquivo}` | Origem detectada: `{origem_atual}`")

    st.subheader("Preview da origem")
    st.dataframe(df_origem.head(10), width="stretch")

    memoria = st.session_state.get("mapeamento_memoria", {})
    state_key = f"mapeamento_manual_{modo}"

    if state_key not in st.session_state:
        st.session_state[state_key] = _sugerir_mapeamento_inicial(
            colunas_origem=list(df_origem.columns),
            colunas_destino=colunas_destino,
            memoria=memoria,
        )

    mapeamento_manual = _render_mapeamento_manual(
        df_origem=df_origem,
        colunas_destino=colunas_destino,
        state_key=state_key,
    )

    st.divider()

    st.subheader("Preview do que será baixado")
    df_preview_saida = _montar_df_saida(
        df_origem=df_origem,
        colunas_destino=colunas_destino,
        mapeamento_manual=mapeamento_manual,
        defaults=defaults,
    )
    st.dataframe(df_preview_saida.head(20), width="stretch")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Gerar preview final", width="stretch"):
            try:
                df_saida = _montar_df_saida(
                    df_origem=df_origem,
                    colunas_destino=colunas_destino,
                    mapeamento_manual=mapeamento_manual,
                    defaults=defaults,
                )

                if df_saida.empty:
                    st.warning("Nenhum dado foi gerado.")
                    return

                try:
                    preco_compra = calcular_preco_compra_automatico_df(df_saida)
                    st.session_state["preco_compra_modulo_precificacao"] = float(preco_compra or 0.0)

                    if "custo" in df_saida.columns:
                        custo_serie = df_saida["custo"].astype(str).fillna("").str.strip()
                        if custo_serie.eq("").all() and preco_compra:
                            df_saida["custo"] = float(preco_compra)
                except Exception as e:
                    _log(f"Falha na precificação automática: {e}")

                mapa_para_memoria = {}
                for destino, origem in mapeamento_manual.items():
                    if origem:
                        mapa_para_memoria[origem] = destino

                try:
                    salvar_mapeamento(
                        memoria,
                        list(df_origem.columns),
                        mapa_para_memoria,
                    )
                    st.session_state["mapeamento_memoria"] = memoria
                except Exception as e:
                    _log(f"Falha ao salvar memória de mapeamento: {e}")

                excel_bytes = df_to_excel_bytes(df_saida)

                st.session_state["df_saida"] = df_saida.copy()
                st.session_state["df_saida_preview_hash"] = origem_hash
                st.session_state["excel_saida_bytes"] = excel_bytes
                st.session_state["excel_saida_nome"] = arquivo_saida

                st.success("Preview final gerado com sucesso. Revise abaixo antes de baixar.")

            except Exception as e:
                st.error(f"Erro ao gerar preview final: {e}")
                _log(f"Erro ao gerar preview final: {e}")

    with col2:
        if st.button("Limpar mapeamento", width="stretch"):
            st.session_state[state_key] = {}
            st.session_state.pop("df_saida", None)
            st.session_state.pop("df_saida_preview_hash", None)
            st.session_state.pop("excel_saida_bytes", None)
            st.session_state.pop("excel_saida_nome", None)
            st.rerun()

    df_saida_state = st.session_state.get("df_saida")
    df_saida_hash = st.session_state.get("df_saida_preview_hash")
    excel_saida_bytes = st.session_state.get("excel_saida_bytes")
    excel_saida_nome = st.session_state.get("excel_saida_nome", arquivo_saida)

    if (
        isinstance(df_saida_state, pd.DataFrame)
        and not df_saida_state.empty
        and df_saida_hash == origem_hash
        and excel_saida_bytes
    ):
        st.divider()
        st.subheader("Preview final validado para download")
        st.caption(f"{len(df_saida_state)} linhas × {len(df_saida_state.columns)} colunas")
        st.dataframe(df_saida_state.head(50), width="stretch")

        st.download_button(
            f"Baixar arquivo de {config['label']}",
            data=excel_saida_bytes,
            file_name=excel_saida_nome,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )


def tela_origem_dados() -> None:
    render_origem_dados()
