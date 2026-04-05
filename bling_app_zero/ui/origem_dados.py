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

    if sep:
        kwargs["sep"] = sep

    if tolerante:
        kwargs["on_bad_lines"] = "skip"

    try:
        return pd.read_csv(io.StringIO(texto), **kwargs)
    except ParserError:
        if not tolerante:
            return _tentar_ler_csv_com_config(texto, sep, tolerante=True)
        raise


def _ler_csv_robusto(uploaded_file) -> pd.DataFrame:
    raw_bytes = uploaded_file.getvalue()
    encoding = _detectar_encoding(raw_bytes)
    texto = raw_bytes.decode(encoding, errors="replace")

    sep = _detectar_separador(texto)
    df = _tentar_ler_csv_com_config(texto, sep=sep, tolerante=False)

    if len(df.columns) <= 1 and sep != ";":
        try:
            df2 = _tentar_ler_csv_com_config(texto, sep=";", tolerante=True)
            if len(df2.columns) > len(df.columns):
                df = df2
        except Exception:
            pass

    if len(df.columns) <= 1 and sep != ",":
        try:
            df2 = _tentar_ler_csv_com_config(texto, sep=",", tolerante=True)
            if len(df2.columns) > len(df.columns):
                df = df2
        except Exception:
            pass

    if len(df.columns) <= 1:
        raise ValueError(
            "Não foi possível separar as colunas do CSV. "
            "Verifique se o arquivo está em CSV delimitado por vírgula ou ponto e vírgula."
        )

    return _normalizar_colunas(df)


# ==========================================================
# LEITURA PLANILHAS / XML
# ==========================================================
def _ler_arquivo_upload(uploaded_file):
    if uploaded_file is None:
        return None

    nome = str(uploaded_file.name).lower()

    try:
        if nome.endswith(".csv"):
            return _ler_csv_robusto(uploaded_file)

        if nome.endswith(".xml"):
            return _parse_nfe_xml_produtos(uploaded_file.getvalue())

        return _normalizar_colunas(pd.read_excel(uploaded_file, dtype=str))
    except Exception as e:
        raise ValueError(f"Falha ao ler arquivo '{uploaded_file.name}': {e}") from e


def _ler_planilha_modelo(upload_modelo, modo: str) -> Tuple[pd.DataFrame | None, List[str], str]:
    if upload_modelo is None:
        return None, [], "modelo não anexado"

    try:
        df_modelo = _ler_arquivo_upload(upload_modelo)
        if df_modelo is None:
            return None, [], "modelo não anexado"

        colunas = [str(c).strip() for c in df_modelo.columns if str(c).strip()]
        origem = f"modelo anexado: {upload_modelo.name}"
        return df_modelo, colunas, origem
    except Exception as e:
        st.error(f"Erro ao ler modelo de {modo}: {e}")
        _log(f"Erro ao ler modelo de {modo}: {e}")
        return None, [], f"erro ao ler modelo de {modo}"


# ==========================================================
# SUGESTÕES DE MAPEAMENTO
# ==========================================================
def _sugestoes_basicas_para_modelo(colunas_modelo: List[str], colunas_origem: List[str]) -> Dict[str, str]:
    mapa_origem = _mapa_colunas_normalizadas(colunas_origem)
    sugestoes = {}

    aliases = {
        "codigo": ["codigo", "código", "sku", "referencia", "referência", "cod", "id"],
        "descricao": ["descricao", "descrição", "produto", "nome", "titulo", "título"],
        "preco": ["preco", "preço", "valor", "valor venda", "preco venda", "preço venda"],
        "preco custo": ["preco custo", "preço custo", "custo", "valor custo", "preco compra", "preço compra"],
        "gtin ean": ["gtin", "ean", "codigo de barras", "código de barras", "cbarra"],
        "ncm": ["ncm"],
        "estoque": ["estoque", "saldo", "quantidade", "qtd", "qtde"],
        "deposito": ["deposito", "depósito", "armazem", "armazém", "local estoque"],
    }

    for coluna_modelo in colunas_modelo:
        chave = _normalizar_texto(coluna_modelo)
        origem_escolhida = ""

        if chave in mapa_origem:
            origem_escolhida = mapa_origem[chave]
        else:
            for alias_chave, possibilidades in aliases.items():
                if alias_chave in chave:
                    for possibilidade in possibilidades:
                        if possibilidade in mapa_origem:
                            origem_escolhida = mapa_origem[possibilidade]
                            break
                if origem_escolhida:
                    break

        sugestoes[coluna_modelo] = origem_escolhida

    return sugestoes


# ==========================================================
# PREÇO
# ==========================================================
def _calcular_preco_venda(
    custo: float,
    margem_lucro: float,
    impostos: float,
    taxa_extra: float,
    custo_fixo: float,
) -> float:
    custo = max(_to_float(custo), 0.0)
    margem = max(_to_float(margem_lucro), 0.0) / 100.0
    impostos_pct = max(_to_float(impostos), 0.0) / 100.0
    taxa = max(_to_float(taxa_extra), 0.0) / 100.0
    custo_fixo_valor = max(_to_float(custo_fixo), 0.0)

    denominador = 1.0 - margem - impostos_pct - taxa
    if denominador <= 0:
        return 0.0

    preco = (custo + custo_fixo_valor) / denominador
    return round(max(preco, 0.0), 2)


def _aplicar_calculadora_preco(
    df_saida: pd.DataFrame,
    colunas_modelo_ativas: List[str],
) -> pd.DataFrame:
    df_saida = df_saida.copy()

    coluna_preco_destino = st.session_state.get("coluna_preco_destino_widget", "")
    coluna_preco_base = st.session_state.get("coluna_preco_base_widget", "")

    margem = st.session_state.get("calc_margem_lucro", 0.0)
    impostos = st.session_state.get("calc_impostos", 0.0)
    taxa_extra = st.session_state.get("calc_taxa_extra", 0.0)
    custo_fixo = st.session_state.get("calc_custo_fixo", 0.0)

    if coluna_preco_destino and coluna_preco_destino in colunas_modelo_ativas:
        if coluna_preco_base and coluna_preco_base in df_saida.columns:
            custos = _serie_float(df_saida, coluna_preco_base, default=0.0)
            df_saida[coluna_preco_destino] = custos.apply(
                lambda custo: _calcular_preco_venda(
                    custo=custo,
                    margem_lucro=margem,
                    impostos=impostos,
                    taxa_extra=taxa_extra,
                    custo_fixo=custo_fixo,
                )
            )
        elif coluna_preco_destino not in df_saida.columns:
            df_saida[coluna_preco_destino] = ""

    return df_saida


# ==========================================================
# GTIN
# ==========================================================
PREFIXOS_GTIN_REJEITADOS_BLING = {
    "687",
}


def _somente_digitos(valor: str) -> str:
    return re.sub(r"\D", "", str(valor or ""))


def _gtin_checksum_valido(gtin: str) -> bool:
    if not gtin or not gtin.isdigit():
        return False

    if len(gtin) not in (8, 12, 13, 14):
        return False

    numeros = [int(d) for d in gtin]
    check = numeros[-1]
    corpo = numeros[:-1][::-1]

    soma = 0
    for i, n in enumerate(corpo):
        soma += n * (3 if i % 2 == 0 else 1)

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
            f"Linha {linha_idx}: coluna '{nome_coluna}' removida por GTIN inválido ({codigo})"
        )
        return ""

    valores = []
    for pos, valor in enumerate(serie.tolist(), start=2):
        valores.append(_limpar(valor, pos))

    return pd.Series(valores, index=serie.index, dtype="string"), logs, total_invalidos


# ==========================================================
# VALIDAÇÃO
# ==========================================================
def _validar_saida(
    df_saida: pd.DataFrame,
    colunas_modelo_ativas: List[str],
    modo: str,
) -> Tuple[List[str], List[str]]:
    erros = []
    avisos = []

    colunas_obrigatorias = ["codigo"]

    if modo == "cadastro":
        colunas_obrigatorias.append("descricao")

    mapa_modelo = _mapa_colunas_normalizadas(colunas_modelo_ativas)

    for obrigatoria in colunas_obrigatorias:
        if obrigatoria not in mapa_modelo:
            continue

        coluna_real = mapa_modelo[obrigatoria]
        if coluna_real not in df_saida.columns:
            erros.append(f"Coluna obrigatória ausente no resultado: {coluna_real}")
            continue

        serie = _serie_texto(df_saida, coluna_real)
        if serie.eq("").all():
            erros.append(f"Coluna obrigatória sem valores: {coluna_real}")

    if "gtin ean" in mapa_modelo:
        coluna_gtin = mapa_modelo["gtin ean"]
        if coluna_gtin in df_saida.columns:
            serie_gtin = _serie_texto(df_saida, coluna_gtin)
            if serie_gtin.eq("").all():
                avisos.append(
                    "Todos os GTIN/EAN ficaram vazios após a limpeza. "
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
    st.caption(
        "Anexe os modelos oficiais. O arquivo final será baixado exatamente com as colunas "
        "e a ordem do modelo correspondente."
    )

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

    df_modelo_cadastro, colunas_modelo_cadastro, origem_modelo_cadastro = _ler_planilha_modelo(
        upload_modelo_cadastro, "cadastro"
    )
    df_modelo_estoque, colunas_modelo_estoque, origem_modelo_estoque = _ler_planilha_modelo(
        upload_modelo_estoque, "estoque"
    )

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
        f"Arquivo final esperado: **{arquivo_saida}**."
    )

    st.write("### Origem dos dados")

    tipo_entrada = st.radio(
        "Escolha a origem principal",
        options=["planilha", "xml"],
        format_func=lambda x: "Planilha do fornecedor / site" if x == "planilha" else "XML da NF-e",
        horizontal=True,
        key="tipo_entrada_origem",
    )

    if tipo_entrada == "planilha":
        upload_origem = st.file_uploader(
            "Anexe a planilha do fornecedor / site",
            type=["xlsx", "xls", "csv"],
            key="upload_origem_planilha",
        )
    else:
        upload_origem = st.file_uploader(
            "Anexe o XML da NF-e",
            type=["xml"],
            key="upload_origem_xml",
        )

    if upload_origem is None:
        st.caption("Aguardando arquivo de origem.")
        return

    try:
        df_origem = _ler_arquivo_upload(upload_origem)
    except Exception as e:
        st.error(str(e))
        _log(str(e))
        return

    if df_origem is None or df_origem.empty:
        st.warning("O arquivo de origem não possui dados.")
        return

    st.success(f"Arquivo de origem carregado: {upload_origem.name}")
    st.caption(f"Modelo ativo: {origem_modelo_ativo}")

    hash_atual_origem = _gerar_hash_texto(
        f"{modo}|{upload_origem.name}|{list(df_origem.columns)}|{len(df_origem)}|{nome_modelo_ativo}"
    )
    hash_anterior = st.session_state.get("df_origem_hash")
    if hash_anterior != hash_atual_origem:
        _limpar_estado_geracao(modo)
        st.session_state["df_origem_hash"] = hash_atual_origem

    st.write("### Colunas lidas do arquivo de origem")
    _render_lista_colunas_simples(list(df_origem.columns))

    if df_modelo_ativo is None or not colunas_modelo_ativas:
        st.warning(
            "Anexe o modelo oficial da operação selecionada para habilitar o preview e o download exato."
        )
        return

    st.write("### Colunas do modelo ativo")
    _render_lista_colunas_simples(colunas_modelo_ativas)

    sugestoes = _sugestoes_basicas_para_modelo(
        colunas_modelo=colunas_modelo_ativas,
        colunas_origem=list(df_origem.columns),
    )

    chave_mapa = f"mapeamento_manual_{modo}"
    if chave_mapa not in st.session_state:
        st.session_state[chave_mapa] = sugestoes.copy()

    st.write("### Mapeamento manual")
    st.caption(
        "Escolha, para cada coluna do modelo ativo, qual coluna do arquivo de origem deve preencher o valor."
    )

    opcoes = [""] + list(df_origem.columns)
    usados = set()

    for coluna_modelo in colunas_modelo_ativas:
        valor_atual = st.session_state[chave_mapa].get(coluna_modelo, "")
        if valor_atual in usados:
            valor_atual = ""

        alternativas = [""] + [c for c in df_origem.columns if c not in usados or c == valor_atual]

        try:
            index_atual = alternativas.index(valor_atual)
        except ValueError:
            index_atual = 0

        escolhido = st.selectbox(
            f"{coluna_modelo}",
            options=alternativas,
            index=index_atual,
            key=f"map_{modo}_{coluna_modelo}",
        )

        st.session_state[chave_mapa][coluna_modelo] = escolhido
        if escolhido:
            usados.add(escolhido)

    st.write("### Calculadora de preço")

    mapa_modelo = _mapa_colunas_normalizadas(colunas_modelo_ativas)

    sugestao_preco_destino = ""
    for chave in ["preco", "preco venda", "valor venda"]:
        if chave in mapa_modelo:
            sugestao_preco_destino = mapa_modelo[chave]
            break

    if "coluna_preco_destino_widget" not in st.session_state:
        st.session_state["coluna_preco_destino_widget"] = sugestao_preco_destino

    if "coluna_preco_base_widget" not in st.session_state:
        colunas_base_sugeridas = [
            "preco_custo",
            "custo",
            "preco",
            "valor",
            "valor_unitario",
        ]
        escolhida = ""
        for c in colunas_base_sugeridas:
            if c in df_origem.columns:
                escolhida = c
                break
        st.session_state["coluna_preco_base_widget"] = escolhida

    c1, c2 = st.columns(2)

    with c1:
        st.selectbox(
            "Coluna base de custo/preço vinda do fornecedor",
            options=[""] + list(df_origem.columns),
            key="coluna_preco_base_widget",
        )

        st.number_input(
            "Margem de lucro (%)",
            min_value=0.0,
            step=0.1,
            key="calc_margem_lucro",
        )

        st.number_input(
            "Impostos (%)",
            min_value=0.0,
            step=0.1,
            key="calc_impostos",
        )

    with c2:
        st.selectbox(
            "Coluna de destino do preço no modelo",
            options=[""] + colunas_modelo_ativas,
            key="coluna_preco_destino_widget",
        )

        st.number_input(
            "Taxa extra (%)",
            min_value=0.0,
            step=0.1,
            key="calc_taxa_extra",
        )

        st.number_input(
            "Custo fixo (R$)",
            min_value=0.0,
            step=0.1,
            key="calc_custo_fixo",
        )

    if modo == "estoque":
        st.text_input(
            "Nome do depósito para a planilha de estoque",
            key="deposito_nome_widget",
            placeholder="Ex.: Depósito principal",
        )

    if st.button("Gerar preview final", type="primary"):
        try:
            df_saida = pd.DataFrame(index=df_origem.index)

            for coluna_modelo in colunas_modelo_ativas:
                coluna_origem = st.session_state[chave_mapa].get(coluna_modelo, "")
                if coluna_origem and coluna_origem in df_origem.columns:
                    df_saida[coluna_modelo] = df_origem[coluna_origem]
                else:
                    df_saida[coluna_modelo] = ""

            if modo == "estoque":
                mapa_saida = _mapa_colunas_normalizadas(list(df_saida.columns))
                coluna_deposito = ""
                for chave in ["deposito", "depósito"]:
                    if chave in mapa_saida:
                        coluna_deposito = mapa_saida[chave]
                        break
                if coluna_deposito:
                    df_saida[coluna_deposito] = _to_text(
                        st.session_state.get("deposito_nome_widget", "")
                    )

            df_saida = _aplicar_calculadora_preco(df_saida, colunas_modelo_ativas)

            mapa_saida = _mapa_colunas_normalizadas(list(df_saida.columns))
            coluna_gtin = ""
            for chave in ["gtin ean", "gtin", "ean", "codigo de barras", "código de barras"]:
                if chave in mapa_saida:
                    coluna_gtin = mapa_saida[chave]
                    break

            gtin_logs = []
            gtin_invalidos = 0
            if coluna_gtin:
                serie_limpa, gtin_logs, gtin_invalidos = _limpar_gtin_invalido_serie(
                    _serie_texto(df_saida, coluna_gtin),
                    nome_coluna=coluna_gtin,
                )
                df_saida[coluna_gtin] = serie_limpa

            erros, avisos = _validar_saida(df_saida, colunas_modelo_ativas, modo)

            excel_bytes = _exportar_df_exato_para_excel_bytes(df_saida)

            st.session_state["df_saida"] = df_saida
            st.session_state["df_saida_preview_hash"] = _gerar_hash_texto(
                f"{modo}|{df_saida.head(50).to_csv(index=False)}"
            )
            st.session_state["excel_saida_bytes"] = excel_bytes
            st.session_state["excel_saida_nome"] = arquivo_saida
            st.session_state["validacao_erros_saida"] = erros
            st.session_state["validacao_avisos_saida"] = avisos
            st.session_state["gtin_logs_saida"] = gtin_logs
            st.session_state["gtin_invalidos_saida"] = gtin_invalidos

            st.success("Preview final gerado com sucesso.")
        except Exception as e:
            st.error(f"Falha ao gerar preview final: {e}")
            _log(f"Falha ao gerar preview final: {e}")
            return

    df_saida = st.session_state.get("df_saida")
    excel_saida_bytes = st.session_state.get("excel_saida_bytes")
    excel_saida_nome = st.session_state.get("excel_saida_nome", arquivo_saida)
    erros = st.session_state.get("validacao_erros_saida", [])
    avisos = st.session_state.get("validacao_avisos_saida", [])
    gtin_logs = st.session_state.get("gtin_logs_saida", [])
    gtin_invalidos = st.session_state.get("gtin_invalidos_saida", 0)

    if df_saida is None or excel_saida_bytes is None:
        return

    st.write("### Preview final do que será baixado")
    st.dataframe(df_saida.head(50), width="stretch")

    if gtin_invalidos:
        st.warning(
            f"{gtin_invalidos} GTIN/EAN inválido(s) foram limpos automaticamente e ficaram vazios no download."
        )
        with st.expander("Ver log da limpeza de GTIN"):
            for item in gtin_logs:
                st.write(f"- {item}")

    if erros:
        st.error("Erros encontrados na validação final:")
        for erro in erros:
            st.write(f"- {erro}")

    if avisos:
        st.warning("Avisos da validação final:")
        for aviso in avisos:
            st.write(f"- {aviso}")

    st.download_button(
        label=f"Baixar {excel_saida_nome}",
        data=excel_saida_bytes,
        file_name=excel_saida_nome,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        disabled=bool(erros),
        width="stretch",
    )
