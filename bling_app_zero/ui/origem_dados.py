import csv
import hashlib
import io
import re
import unicodedata
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st
from openpyxl.styles import numbers
from pandas.errors import ParserError


OPERACOES = {
    "cadastro": {
        "label": "Cadastro / atualização de produtos",
        "arquivo_saida": "bling_cadastro.xlsx",
    },
    "estoque": {
        "label": "Atualização de estoque",
        "arquivo_saida": "bling_estoque.xlsx",
    },
}


# ==========================================================
# LOG
# ==========================================================
def _log(msg: str) -> None:
    if "logs" not in st.session_state:
        st.session_state["logs"] = []
    st.session_state["logs"].append(str(msg))


# ==========================================================
# TEXTO / NOME DE COLUNAS
# ==========================================================
def _normalizar_texto(texto: str) -> str:
    texto = str(texto or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ascii", "ignore").decode("utf-8")
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(col).strip() for col in df.columns]
    return df


def _mapa_colunas_normalizadas(colunas: List[str]) -> Dict[str, str]:
    return {_normalizar_texto(col): col for col in colunas}


def _render_lista_colunas_simples(colunas: List[str]) -> None:
    if not colunas:
        st.caption("Sem colunas para exibir.")
        return

    st.code("\n".join(str(c) for c in colunas if str(c).strip()), language=None)


# ==========================================================
# HASH / ESTADO
# ==========================================================
def _gerar_hash_texto(texto: str) -> str:
    return hashlib.md5(texto.encode("utf-8")).hexdigest()


def _limpar_estado_geracao(modo: str | None = None) -> None:
    for chave in [
        "df_saida",
        "df_saida_preview_hash",
        "excel_saida_bytes",
        "excel_saida_nome",
        "df_origem_hash",
        "coluna_preco_base_widget",
        "coluna_preco_destino_widget",
        "deposito_nome_widget",
        "calc_margem_lucro",
        "calc_impostos",
        "calc_taxa_extra",
        "calc_custo_fixo",
        "validacao_erros_saida",
        "validacao_avisos_saida",
        "gtin_logs_saida",
        "gtin_invalidos_saida",
    ]:
        st.session_state.pop(chave, None)

    if modo:
        st.session_state.pop(f"mapeamento_manual_{modo}", None)


# ==========================================================
# CONVERSORES
# ==========================================================
def _to_text(valor) -> str:
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except Exception:
        pass
    texto = str(valor).strip()
    return "" if texto.lower() == "nan" else texto


def _to_float(valor) -> float:
    if valor is None:
        return 0.0

    try:
        if pd.isna(valor):
            return 0.0
    except Exception:
        pass

    texto = str(valor).strip()
    if not texto:
        return 0.0

    texto = (
        texto.replace("R$", "")
        .replace("r$", "")
        .replace("\u00a0", "")
        .replace(" ", "")
    )

    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        texto = texto.replace(".", "").replace(",", ".")

    try:
        return float(texto)
    except Exception:
        return 0.0


def _serie_texto(df: pd.DataFrame, coluna: str) -> pd.Series:
    if coluna not in df.columns:
        return pd.Series([""] * len(df), index=df.index, dtype="string")

    return (
        df[coluna]
        .apply(_to_text)
        .astype("string")
        .fillna("")
        .str.strip()
    )


def _serie_float(df: pd.DataFrame, coluna: str, default: float = 0.0) -> pd.Series:
    if coluna not in df.columns:
        return pd.Series([default] * len(df), index=df.index, dtype="float64")

    serie = df[coluna].apply(_to_float)
    serie = pd.to_numeric(serie, errors="coerce").fillna(default).astype("float64")
    return serie


# ==========================================================
# LEITURA XML
# ==========================================================
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
        for child in list(det):
            if _local_name(child.tag) == "prod":
                prod = child
                break

        if prod is None:
            continue

        itens.append(
            {
                "codigo": _find_child_text(prod, "cProd"),
                "gtin": _find_child_text(prod, "cEAN"),
                "descricao": _find_child_text(prod, "xProd"),
                "ncm": _find_child_text(prod, "NCM"),
                "unidade": _find_child_text(prod, "uCom"),
                "quantidade": _find_child_text(prod, "qCom"),
                "preco_custo": _find_child_text(prod, "vUnCom"),
                "valor_total": _find_child_text(prod, "vProd"),
            }
        )

    if not itens:
        raise ValueError("Nenhum produto foi encontrado no XML da NF-e.")

    return _normalizar_colunas(pd.DataFrame(itens))


# ==========================================================
# LEITURA CSV ROBUSTA
# ==========================================================
def _detectar_encoding(raw_bytes: bytes) -> str:
    for enc in ["utf-8-sig", "utf-8", "cp1252", "latin1"]:
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
    return melhor if contagens[melhor] > 0 else None


def _tentar_ler_csv_com_config(texto: str, sep: str | None, tolerante: bool = False) -> pd.DataFrame:
    kwargs = {
        "engine": "python",
        "dtype": str,
        "keep_default_na": False,
    }

    kwargs["sep"] = sep if sep else None

    if tolerante:
        kwargs["on_bad_lines"] = "skip"

    return pd.read_csv(io.StringIO(texto), **kwargs)


def _ler_csv_robusto(arquivo) -> Tuple[pd.DataFrame, str]:
    raw_bytes = arquivo.getvalue()
    encoding = _detectar_encoding(raw_bytes)
    texto = raw_bytes.decode(encoding, errors="replace")
    separador = _detectar_separador(texto)

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
        except ParserError:
            continue
        except Exception:
            continue

    if melhor_df is None or melhor_df.empty:
        raise ValueError("Não foi possível ler o CSV.")

    _log(
        f"CSV lido com encoding {encoding} e estratégia {melhor_rotulo}"
        + (f" | separador detectado: {repr(separador)}" if separador else "")
    )

    return melhor_df, f"CSV ({encoding})"


# ==========================================================
# LEITURA GERAL
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
                return _normalizar_colunas(pd.read_xml(io.BytesIO(xml_bytes))), "XML genérico"
            except Exception as e:
                raise ValueError(f"Não foi possível ler o XML: {e}") from e

    if nome_arquivo.endswith(".csv"):
        return _ler_csv_robusto(arquivo)

    return _normalizar_colunas(pd.read_excel(arquivo, dtype=str)), "Planilha"


def _ler_planilha_modelo(upload_modelo, modo: str) -> Tuple[pd.DataFrame | None, List[str], str]:
    if not upload_modelo:
        return None, [], ""

    try:
        df_modelo, origem_modelo = _ler_arquivo_upload(upload_modelo)
        colunas_modelo = [str(c).strip() for c in df_modelo.columns if str(c).strip()]
        return df_modelo, colunas_modelo, origem_modelo
    except Exception as e:
        st.warning(f"Não foi possível ler a planilha modelo de {OPERACOES[modo]['label']}: {e}")
        _log(f"Falha ao ler modelo {modo}: {e}")
        return None, [], ""


# ==========================================================
# GTIN
# ==========================================================
PREFIXOS_GTIN_REJEITADOS_BLING = {
    "687",  # prefixo rejeitado pelo importador do Bling no caso real validado
}

def _somente_digitos(valor: str) -> str:
    return re.sub(r"\D", "", str(valor or ""))


def _gtin_checksum_valido(gtin: str) -> bool:
    if len(gtin) not in (8, 12, 13, 14):
        return False
    if not gtin.isdigit():
        return False
    if set(gtin) == {"0"}:
        return False

    digitos = [int(c) for c in gtin]
    check = digitos[-1]
    corpo = digitos[:-1]

    soma = 0
    peso = 3
    for n in reversed(corpo):
        soma += n * peso
        peso = 1 if peso == 3 else 3

    calculado = (10 - (soma % 10)) % 10
    return calculado == check


def _gtin_prefixo_rejeitado_bling(gtin: str) -> bool:
    if not gtin:
        return False

    for prefixo in PREFIXOS_GTIN_REJEITADOS_BLING:
        if gtin.startswith(prefixo):
            return True

    return False


def _limpar_gtin_invalido_serie(
    serie: pd.Series,
    nome_coluna: str = "GTIN/EAN",
) -> Tuple[pd.Series, List[str], int]:
    logs: List[str] = []
    total_invalidos = 0

    def _limpar(valor: str, linha_idx: int) -> str:
        nonlocal total_invalidos

        texto_original = _to_text(valor)
        codigo = _somente_digitos(texto_original)

        if not codigo:
            return ""

        if _gtin_prefixo_rejeitado_bling(codigo):
            total_invalidos += 1
            logs.append(
                f"Linha {linha_idx}: coluna '{nome_coluna}' removida por prefixo rejeitado pelo Bling ({codigo})"
            )
            return ""

        if _gtin_checksum_valido(codigo):
            return codigo

        total_invalidos += 1
        logs.append(
            f"Linha {linha_idx}: coluna '{nome_coluna}' removida por GTIN/EAN inválido ({codigo})"
        )
        return ""

    valores = [
        _limpar(valor, idx + 1)
        for idx, valor in enumerate(serie.tolist())
    ]

    return pd.Series(valores, index=serie.index, dtype="string"), logs, total_invalidos


# ==========================================================
# SUGESTÕES / MAPEAMENTO
# ==========================================================
def _sugerir_por_nome_modelo(colunas_origem: List[str], colunas_modelo: List[str]) -> Dict[str, str]:
    mapa_origem = _mapa_colunas_normalizadas(colunas_origem)
    resultado: Dict[str, str] = {}

    sinonimos = {
        "codigo": ["codigo", "código", "sku", "referencia", "ref"],
        "descricao": ["descricao", "descrição", "nome", "produto", "titulo"],
        "unidade": ["unidade", "un", "und"],
        "ncm": ["ncm"],
        "marca": ["marca", "fabricante"],
        "categoria": ["categoria", "departamento", "grupo"],
        "gtin": ["gtin", "ean", "codigo barras", "codigo de barras"],
        "preco unitario": ["preco", "preço", "valor", "valor venda", "preco venda", "preco de venda"],
        "preco de custo": ["custo", "preco custo", "preço custo", "valor custo", "preco de custo"],
        "balanco": ["estoque", "quantidade", "qtd", "saldo", "balanco", "balanço"],
        "deposito": ["deposito", "depósito"],
        "peso": ["peso", "peso liquido", "peso líquido", "peso bruto"],
    }

    for col_modelo in colunas_modelo:
        chave = _normalizar_texto(col_modelo)

        if chave in mapa_origem:
            resultado[col_modelo] = mapa_origem[chave]
            continue

        for destino, termos in sinonimos.items():
            if destino in chave:
                for termo in termos:
                    termo_norm = _normalizar_texto(termo)
                    if termo_norm in mapa_origem:
                        resultado[col_modelo] = mapa_origem[termo_norm]
                        break
            if col_modelo in resultado:
                break

        if col_modelo not in resultado:
            for origem in colunas_origem:
                origem_norm = _normalizar_texto(origem)
                if origem_norm in chave or chave in origem_norm:
                    resultado[col_modelo] = origem
                    break

    return resultado


def _render_mapeamento_manual(
    df_origem: pd.DataFrame,
    colunas_destino: List[str],
    state_key: str,
) -> Dict[str, str]:
    st.subheader("Mapeamento manual")
    st.caption("Relacione manualmente as colunas da origem com as colunas reais do modelo final.")

    if state_key not in st.session_state:
        st.session_state[state_key] = _sugerir_por_nome_modelo(list(df_origem.columns), colunas_destino)

    mapeamento = dict(st.session_state.get(state_key, {}))
    colunas_origem = list(df_origem.columns)
    usados = set()

    cab1, cab2, cab3 = st.columns([1.3, 1.7, 2.0])
    with cab1:
        st.markdown("**Coluna do modelo**")
    with cab2:
        st.markdown("**Coluna da origem**")
    with cab3:
        st.markdown("**Exemplo**")

    for destino in colunas_destino:
        atual = str(mapeamento.get(destino, "") or "").strip()
        if atual:
            usados.add(atual)

        c1, c2, c3 = st.columns([1.3, 1.7, 2.0])

        with c1:
            st.markdown(f"`{destino}`")

        with c2:
            opcoes = [""]
            for col in colunas_origem:
                if col == atual or col not in (usados - ({atual} if atual else set())):
                    opcoes.append(col)

            indice = opcoes.index(atual) if atual in opcoes else 0

            novo_valor = st.selectbox(
                f"Origem para {destino}",
                opcoes,
                index=indice,
                key=f"map_{state_key}_{destino}",
                label_visibility="collapsed",
            )
            mapeamento[destino] = novo_valor or ""

        with c3:
            origem_exemplo = mapeamento.get(destino, "")
            if origem_exemplo and origem_exemplo in df_origem.columns:
                serie = _serie_texto(df_origem, origem_exemplo)
                serie = serie[serie != ""]
                exemplo = serie.iloc[0] if not serie.empty else ""
                st.caption(str(exemplo)[:120] if exemplo else "—")
            else:
                st.caption("—")

    st.session_state[state_key] = mapeamento
    return mapeamento


# ==========================================================
# CALCULADORA
# ==========================================================
def _detectar_coluna_preco_base(colunas_origem: List[str]) -> str:
    prioridades = [
        "custo",
        "preco custo",
        "preço custo",
        "preco de custo",
        "valor custo",
        "valor",
        "preco",
        "preço",
        "vuncom",
        "vprod",
    ]
    mapa = _mapa_colunas_normalizadas(colunas_origem)

    for chave in prioridades:
        chave_norm = _normalizar_texto(chave)
        if chave_norm in mapa:
            return mapa[chave_norm]

    for col in colunas_origem:
        cl = _normalizar_texto(col)
        if "custo" in cl or "preco" in cl or "valor" in cl:
            return col

    return ""


def _detectar_coluna_preco_destino(colunas_destino: List[str], modo: str) -> str:
    prioridades_estoque = [
        "preco unitario",
        "preço unitário",
        "preco unitário",
        "preço unitario",
    ]
    prioridades_gerais = [
        "preco",
        "preço",
        "preco venda",
        "preço venda",
        "preco de venda",
        "preço de venda",
        "valor de venda",
    ]

    mapa = _mapa_colunas_normalizadas(colunas_destino)

    if modo == "estoque":
        for chave in prioridades_estoque + prioridades_gerais:
            chave_norm = _normalizar_texto(chave)
            if chave_norm in mapa:
                return mapa[chave_norm]

    for chave in prioridades_gerais + prioridades_estoque:
        chave_norm = _normalizar_texto(chave)
        if chave_norm in mapa:
            return mapa[chave_norm]

    for col in colunas_destino:
        cl = _normalizar_texto(col)
        if "preco" in cl or "preço" in cl:
            return col

    return ""


def _calcular_preco_venda_unitario(
    preco_compra: float,
    percentual_impostos: float,
    margem_lucro: float,
    custo_fixo: float,
    taxa_extra: float,
) -> float:
    base = float(preco_compra or 0.0) + float(custo_fixo or 0.0)
    impostos = float(percentual_impostos or 0.0) / 100.0
    lucro = float(margem_lucro or 0.0) / 100.0
    taxa = float(taxa_extra or 0.0) / 100.0

    denominador = 1.0 - impostos - lucro - taxa
    if denominador <= 0:
        return 0.0

    resultado = base / denominador
    return round(resultado if resultado > 0 else 0.0, 2)


def _render_calculadora(
    df_origem: pd.DataFrame,
    colunas_destino_ativas: List[str],
    modo: str,
) -> Dict[str, object]:
    st.divider()
    st.subheader("Calculadora de preço")
    st.caption("O preço gerado será gravado na coluna real de preço do modelo final.")

    colunas_origem = list(df_origem.columns)

    base_default = st.session_state.get("coluna_preco_base_widget", "")
    if not base_default or base_default not in colunas_origem:
        base_default = _detectar_coluna_preco_base(colunas_origem)

    destino_default = st.session_state.get("coluna_preco_destino_widget", "")
    if not destino_default or destino_default not in colunas_destino_ativas:
        destino_default = _detectar_coluna_preco_destino(colunas_destino_ativas, modo)

    csel1, csel2 = st.columns(2)

    with csel1:
        opcoes_origem = [""] + colunas_origem
        idx_origem = opcoes_origem.index(base_default) if base_default in opcoes_origem else 0
        coluna_preco_base = st.selectbox(
            "Coluna da fornecedora usada como preço base",
            options=opcoes_origem,
            index=idx_origem,
            key="coluna_preco_base_widget",
        )

    with csel2:
        opcoes_destino = [""] + colunas_destino_ativas
        idx_destino = opcoes_destino.index(destino_default) if destino_default in opcoes_destino else 0
        coluna_preco_destino = st.selectbox(
            "Coluna do modelo final que receberá o preço gerado",
            options=opcoes_destino,
            index=idx_destino,
            key="coluna_preco_destino_widget",
        )

    preco_base_medio = 0.0
    exemplo_base = ""

    if coluna_preco_base and coluna_preco_base in df_origem.columns:
        serie_exemplo = _serie_texto(df_origem, coluna_preco_base)
        serie_exemplo = serie_exemplo[serie_exemplo != ""]
        exemplo_base = serie_exemplo.iloc[0] if not serie_exemplo.empty else ""

        precos = _serie_float(df_origem, coluna_preco_base, default=0.0)
        precos = precos[precos > 0]
        preco_base_medio = float(precos.mean()) if not precos.empty else 0.0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        margem = st.number_input("Lucro (%)", min_value=0.0, max_value=100.0, value=float(st.session_state.get("calc_margem_lucro", 30.0)), step=1.0, key="calc_margem_lucro")
    with c2:
        impostos = st.number_input("Impostos (%)", min_value=0.0, max_value=100.0, value=float(st.session_state.get("calc_impostos", 0.0)), step=1.0, key="calc_impostos")
    with c3:
        taxa_extra = st.number_input("Taxas extras (%)", min_value=0.0, max_value=100.0, value=float(st.session_state.get("calc_taxa_extra", 15.0)), step=1.0, key="calc_taxa_extra")
    with c4:
        custo_fixo = st.number_input("Custo fixo (R$)", min_value=0.0, value=float(st.session_state.get("calc_custo_fixo", 0.0)), step=1.0, key="calc_custo_fixo")

    preco_sugerido = _calcular_preco_venda_unitario(
        preco_compra=preco_base_medio,
        percentual_impostos=impostos,
        margem_lucro=margem,
        custo_fixo=custo_fixo,
        taxa_extra=taxa_extra,
    )

    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Preço base médio detectado", f"R$ {preco_base_medio:.2f}")
    with m2:
        st.metric("Preço gerado", f"R$ {preco_sugerido:.2f}")
    with m3:
        st.metric("Exemplo da coluna base", str(exemplo_base) if exemplo_base else "—")

    if margem + impostos + taxa_extra >= 100:
        st.warning("A soma de lucro + impostos + taxas extras precisa ser menor que 100%.")

    return {
        "coluna_preco_base": coluna_preco_base,
        "coluna_preco_destino": coluna_preco_destino,
        "margem": margem,
        "impostos": impostos,
        "taxa_extra": taxa_extra,
        "custo_fixo": custo_fixo,
    }


# ==========================================================
# CAMPOS FIXOS DO ESTOQUE
# ==========================================================
def _detectar_coluna_deposito(colunas_modelo: List[str]) -> str:
    mapa = _mapa_colunas_normalizadas(colunas_modelo)

    for chave in ["deposito", "depósito", "deposito obrigatorio", "depósito obrigatório"]:
        chave_norm = _normalizar_texto(chave)
        if chave_norm in mapa:
            return mapa[chave_norm]

    for col in colunas_modelo:
        cl = _normalizar_texto(col)
        if "deposito" in cl or "depósito" in cl:
            return col

    return ""


def _render_campos_fixos_estoque(colunas_modelo: List[str]) -> Dict[str, str]:
    st.divider()
    st.subheader("Campos fixos do estoque")

    coluna_deposito = _detectar_coluna_deposito(colunas_modelo)

    if coluna_deposito:
        deposito_nome = st.text_input(
            f"Nome do depósito para preencher a coluna '{coluna_deposito}'",
            value=st.session_state.get("deposito_nome_widget", ""),
            key="deposito_nome_widget",
            placeholder="Ex.: Geral, Loja 1, Principal...",
        )
    else:
        deposito_nome = ""

    return {
        "coluna_deposito": coluna_deposito,
        "deposito_nome": deposito_nome,
    }


# ==========================================================
# MONTAGEM DA SAÍDA
# ==========================================================
def _montar_df_saida_exato_modelo(
    df_origem: pd.DataFrame,
    colunas_modelo: List[str],
    mapeamento_manual: Dict[str, str],
    calculadora_cfg: Dict[str, object] | None,
    estoque_cfg: Dict[str, str] | None,
    modo: str,
) -> pd.DataFrame:
    df_saida = pd.DataFrame(index=df_origem.index)

    for col_modelo in colunas_modelo:
        origem = str(mapeamento_manual.get(col_modelo, "") or "").strip()
        if origem and origem in df_origem.columns:
            df_saida[col_modelo] = df_origem[origem]
        else:
            df_saida[col_modelo] = ""

    # Preço calculado no cadastro e no estoque
    if calculadora_cfg:
        col_base = str(calculadora_cfg.get("coluna_preco_base", "") or "").strip()
        col_destino = str(calculadora_cfg.get("coluna_preco_destino", "") or "").strip()

        if col_base and col_base in df_origem.columns and col_destino:
            base = _serie_float(df_origem, col_base, default=0.0)
            df_saida[col_destino] = base.apply(
                lambda valor: _calcular_preco_venda_unitario(
                    preco_compra=valor,
                    percentual_impostos=float(calculadora_cfg.get("impostos", 0.0)),
                    margem_lucro=float(calculadora_cfg.get("margem", 0.0)),
                    custo_fixo=float(calculadora_cfg.get("custo_fixo", 0.0)),
                    taxa_extra=float(calculadora_cfg.get("taxa_extra", 0.0)),
                )
                if float(valor) > 0
                else 0.0
            )

            coluna_custo_modelo = _buscar_coluna_por_alias(
                colunas_modelo,
                ["preco de custo", "preço de custo", "custo", "valor custo"],
            )
            if coluna_custo_modelo:
                df_saida[coluna_custo_modelo] = base

    # Depósito manual no estoque
    if modo == "estoque" and estoque_cfg:
        coluna_deposito = str(estoque_cfg.get("coluna_deposito", "") or "").strip()
        deposito_nome = str(estoque_cfg.get("deposito_nome", "") or "").strip()

        if coluna_deposito:
            df_saida[coluna_deposito] = deposito_nome

    # Limpeza de GTIN inválido em qualquer coluna GTIN/EAN do modelo
    gtin_logs: List[str] = []
    total_gtins_invalidos = 0

    for col in df_saida.columns:
        col_norm = _normalizar_texto(col)
        if "gtin" in col_norm or "ean" in col_norm:
            serie_limpa, logs_coluna, total_invalidos_coluna = _limpar_gtin_invalido_serie(
                _serie_texto(df_saida, col),
                nome_coluna=col,
            )
            df_saida[col] = serie_limpa
            gtin_logs.extend(logs_coluna)
            total_gtins_invalidos += total_invalidos_coluna

    st.session_state["gtin_logs_saida"] = gtin_logs
    st.session_state["gtin_invalidos_saida"] = total_gtins_invalidos

    return df_saida


# ==========================================================
# VALIDAÇÃO
# ==========================================================
def _buscar_coluna_por_alias(colunas: List[str], aliases: List[str]) -> str:
    mapa = _mapa_colunas_normalizadas(colunas)
    for alias in aliases:
        alias_norm = _normalizar_texto(alias)
        if alias_norm in mapa:
            return mapa[alias_norm]

    for col in colunas:
        cl = _normalizar_texto(col)
        for alias in aliases:
            alias_norm = _normalizar_texto(alias)
            if alias_norm in cl:
                return col

    return ""


def _validar_saida_bling(df_saida: pd.DataFrame, modo: str) -> Tuple[List[str], List[str]]:
    erros: List[str] = []
    avisos: List[str] = []

    if df_saida is None or df_saida.empty:
        erros.append("Nenhum dado foi gerado.")
        return erros, avisos

    if modo == "cadastro":
        col_codigo = _buscar_coluna_por_alias(list(df_saida.columns), ["codigo", "código"])
        col_descricao = _buscar_coluna_por_alias(list(df_saida.columns), ["descricao", "descrição", "nome"])
        col_unidade = _buscar_coluna_por_alias(list(df_saida.columns), ["unidade", "un"])
        col_ncm = _buscar_coluna_por_alias(list(df_saida.columns), ["ncm"])

        obrigatorias = [
            ("Código", col_codigo),
            ("Descrição", col_descricao),
            ("Unidade", col_unidade),
            ("NCM", col_ncm),
        ]
    else:
        col_codigo = _buscar_coluna_por_alias(list(df_saida.columns), ["codigo", "código"])
        col_deposito = _buscar_coluna_por_alias(list(df_saida.columns), ["deposito", "depósito"])
        col_balanco = _buscar_coluna_por_alias(list(df_saida.columns), ["balanco", "balanço", "estoque", "saldo"])

        obrigatorias = [
            ("Código", col_codigo),
            ("Depósito", col_deposito),
            ("Balanço", col_balanco),
        ]

    for nome, col_real in obrigatorias:
        if not col_real:
            erros.append(f"Coluna obrigatória ausente no modelo: {nome}")
            continue

        serie = _serie_texto(df_saida, col_real)
        vazios = int((serie == "").sum())
        if vazios > 0:
            erros.append(f"Coluna obrigatória '{col_real}' possui {vazios} linha(s) vazia(s).")

    total_gtins_invalidos = int(st.session_state.get("gtin_invalidos_saida", 0) or 0)
    if total_gtins_invalidos > 0:
        erros.append(
            f"Foram detectados {total_gtins_invalidos} GTIN/EAN inválido(s) removido(s). "
            "Revise o preview antes de liberar o download."
        )

    return erros, avisos


# ==========================================================
# EXPORTAÇÃO EXATA
# ==========================================================
def _exportar_df_exato_para_excel_bytes(df: pd.DataFrame) -> bytes:
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Produtos")
        ws = writer.sheets["Produtos"]

        texto_alvos = {"codigo", "código", "ean", "gtin", "ncm"}
        mapa_headers = {cell.value: cell.column_letter for cell in ws[1]}

        for header, col_letter in mapa_headers.items():
            if _normalizar_texto(header) in {_normalizar_texto(x) for x in texto_alvos}:
                for cell in ws[col_letter]:
                    cell.number_format = numbers.FORMAT_TEXT

    output.seek(0)
    return output.getvalue()


# ==========================================================
# UI
# ==========================================================
def render_origem_dados() -> None:
    st.subheader("Planilhas modelo para o download")
    st.caption("Anexe os modelos oficiais. O arquivo final será baixado exatamente com as colunas e a ordem do modelo correspondente.")

    mc1, mc2 = st.columns(2)

    with mc1:
        upload_modelo_cadastro = st.file_uploader(
            "Modelo de cadastro / atualização de produtos",
            type=["xlsx", "xls", "csv"],
            key="upload_modelo_cadastro",
        )

    with mc2:
        upload_modelo_estoque = st.file_uploader(
            "Modelo de atualização de estoque",
            type=["xlsx", "xls", "csv"],
            key="upload_modelo_estoque",
        )

    df_modelo_cadastro, colunas_modelo_cadastro, origem_modelo_cadastro = _ler_planilha_modelo(upload_modelo_cadastro, "cadastro")
    df_modelo_estoque, colunas_modelo_estoque, origem_modelo_estoque = _ler_planilha_modelo(upload_modelo_estoque, "estoque")

    modo = st.radio(
        "Selecione a operação antes de tudo",
        options=["cadastro", "estoque"],
        format_func=lambda x: OPERACOES[x]["label"],
        horizontal=True,
        key="tipo_operacao_bling",
    )

    config = OPERACOES[modo]
    arquivo_saida = config["arquivo_saida"]

    if modo == "cadastro":
        df_modelo_ativo = df_modelo_cadastro
        colunas_modelo_ativas = colunas_modelo_cadastro
        origem_modelo_ativo = origem_modelo_cadastro
        nome_modelo_ativo = getattr(upload_modelo_cadastro, "name", "")
    else:
        df_modelo_ativo = df_modelo_estoque
        colunas_modelo_ativas = colunas_modelo_estoque
        origem_modelo_ativo = origem_modelo_estoque
        nome_modelo_ativo = getattr(upload_modelo_estoque, "name", "")

    st.info(
        f"Operação selecionada: **{config['label']}**. "
        "Você vai mapear manualmente, gerar o preview final e só depois baixar."
    )

    if nome_modelo_ativo:
        st.success(
            f"Modelo ativo carregado: **{nome_modelo_ativo}** "
            f"({origem_modelo_ativo}) com **{len(colunas_modelo_ativas)}** colunas."
        )
        with st.expander("Ver colunas do modelo ativo"):
            _render_lista_colunas_simples(colunas_modelo_ativas)
    else:
        st.warning("Anexe a planilha modelo da operação selecionada antes de gerar o download.")
        return

    arquivo = st.file_uploader(
        "Anexar planilha ou XML da fornecedora",
        type=["xlsx", "xls", "csv", "xml"],
        key=f"upload_origem_{modo}",
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
    assinatura_modelo = f"{modo}|{nome_modelo_ativo}|{'|'.join(colunas_modelo_ativas)}"
    origem_hash = _gerar_hash_texto(
        f"{nome_arquivo}|{'|'.join(map(str, df_origem.columns))}|{len(df_origem)}|{assinatura_modelo}"
    )

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

    state_key = f"mapeamento_manual_{modo}"
    mapeamento_manual = _render_mapeamento_manual(
        df_origem=df_origem,
        colunas_destino=colunas_modelo_ativas,
        state_key=state_key,
    )

    calculadora_cfg = _render_calculadora(
        df_origem=df_origem,
        colunas_destino_ativas=colunas_modelo_ativas,
        modo=modo,
    )

    estoque_cfg = None
    if modo == "estoque":
        estoque_cfg = _render_campos_fixos_estoque(colunas_modelo_ativas)

    st.divider()
    st.subheader("Preview do que será baixado")

    df_preview_saida = _montar_df_saida_exato_modelo(
        df_origem=df_origem,
        colunas_modelo=colunas_modelo_ativas,
        mapeamento_manual=mapeamento_manual,
        calculadora_cfg=calculadora_cfg,
        estoque_cfg=estoque_cfg,
        modo=modo,
    )

    erros_preview, avisos_preview = _validar_saida_bling(df_preview_saida, modo)
    st.session_state["validacao_erros_saida"] = erros_preview
    st.session_state["validacao_avisos_saida"] = avisos_preview

    st.dataframe(df_preview_saida.head(20), width="stretch")

    if erros_preview:
        st.error("Pendências antes do download:\n\n- " + "\n- ".join(erros_preview))
    elif avisos_preview:
        st.warning("Avisos:\n\n- " + "\n- ".join(avisos_preview))
    else:
        st.success("Preview válido para gerar o arquivo final.")

    gtin_logs_preview = st.session_state.get("gtin_logs_saida", []) or []
    if gtin_logs_preview:
        with st.expander("Ver ocorrências de GTIN/EAN limpos no preview"):
            st.code("\n".join(gtin_logs_preview), language=None)

    b1, b2 = st.columns(2)

    with b1:
        if st.button("Gerar preview final", width="stretch"):
            try:
                df_saida_final = _montar_df_saida_exato_modelo(
                    df_origem=df_origem,
                    colunas_modelo=colunas_modelo_ativas,
                    mapeamento_manual=mapeamento_manual,
                    calculadora_cfg=calculadora_cfg,
                    estoque_cfg=estoque_cfg,
                    modo=modo,
                )

                erros_final, avisos_final = _validar_saida_bling(df_saida_final, modo)
                st.session_state["validacao_erros_saida"] = erros_final
                st.session_state["validacao_avisos_saida"] = avisos_final

                if erros_final:
                    st.error("Não foi possível liberar o download porque ainda existem pendências.")
                    return

                excel_bytes = _exportar_df_exato_para_excel_bytes(df_saida_final)

                st.session_state["df_saida"] = df_saida_final.copy()
                st.session_state["df_saida_preview_hash"] = origem_hash
                st.session_state["excel_saida_bytes"] = excel_bytes
                st.session_state["excel_saida_nome"] = arquivo_saida

                st.success("Preview final gerado com sucesso. Revise abaixo antes de baixar.")

            except Exception as e:
                st.error(f"Erro ao gerar preview final: {e}")
                _log(f"Erro ao gerar preview final: {e}")

    with b2:
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
