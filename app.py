import streamlit as st
import pandas as pd
import zipfile
import io
import os
import re
import math
from datetime import datetime

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="🔥 BLING LIMPEZA EXTREMA", layout="wide")
st.title("🔥 BLING LIMPEZA EXTREMA")

# =========================
# SESSION STATE
# =========================
if "logs" not in st.session_state:
    st.session_state["logs"] = []

if "df_estoque_original" not in st.session_state:
    st.session_state["df_estoque_original"] = None

if "df_cadastro_original" not in st.session_state:
    st.session_state["df_cadastro_original"] = None

if "df_estoque_bling" not in st.session_state:
    st.session_state["df_estoque_bling"] = None

if "df_cadastro_bling" not in st.session_state:
    st.session_state["df_cadastro_bling"] = None

if "nome_arquivo_estoque" not in st.session_state:
    st.session_state["nome_arquivo_estoque"] = None

if "nome_arquivo_cadastro" not in st.session_state:
    st.session_state["nome_arquivo_cadastro"] = None


# =========================
# LOG
# =========================
def log(msg):
    horario = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    st.session_state["logs"].append(f"[{horario}] {msg}")


def limpar_estado():
    st.session_state["logs"] = []
    st.session_state["df_estoque_original"] = None
    st.session_state["df_cadastro_original"] = None
    st.session_state["df_estoque_bling"] = None
    st.session_state["df_cadastro_bling"] = None
    st.session_state["nome_arquivo_estoque"] = None
    st.session_state["nome_arquivo_cadastro"] = None


# =========================
# TEXTO / NORMALIZAÇÃO
# =========================
def normalizar_texto(valor):
    if valor is None:
        return ""

    try:
        if pd.isna(valor):
            return ""
    except:
        pass

    texto = str(valor)

    # remove BOM e caracteres invisíveis comuns
    texto = texto.replace("\ufeff", "")
    texto = texto.replace("\u200b", "")
    texto = texto.replace("\xa0", " ")

    # troca quebras
    texto = texto.replace("\r", " ")
    texto = texto.replace("\n", " ")
    texto = texto.replace("\t", " ")

    # compacta espaços
    texto = re.sub(r"\s+", " ", texto)

    return texto.strip()


def slug_coluna(texto):
    texto = normalizar_texto(texto).lower()

    mapa = {
        "ç": "c",
        "á": "a",
        "à": "a",
        "â": "a",
        "ã": "a",
        "é": "e",
        "ê": "e",
        "í": "i",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "ú": "u",
        "/": "_",
        "-": "_",
        "(": "",
        ")": "",
        "[": "",
        "]": "",
        "{": "",
        "}": "",
        "*": "",
        ":": "",
        ";": "",
        ",": "",
        ".": "",
    }

    for antigo, novo in mapa.items():
        texto = texto.replace(antigo, novo)

    texto = re.sub(r"[^a-z0-9_ ]", "", texto)
    texto = texto.replace(" ", "_")
    texto = re.sub(r"_+", "_", texto).strip("_")

    return texto


def coluna_vazia_serie(serie):
    for valor in serie:
        txt = normalizar_texto(valor)
        if txt != "":
            return False
    return True


def buscar_coluna(df, aliases):
    mapa = {slug_coluna(col): col for col in df.columns}

    for alias in aliases:
        alias_slug = slug_coluna(alias)
        if alias_slug in mapa:
            return mapa[alias_slug]

    return None


# =========================
# NUMÉRICOS
# =========================
def para_float(valor):
    if valor is None:
        return None

    try:
        if pd.isna(valor):
            return None
    except:
        pass

    texto = normalizar_texto(valor)

    if texto == "":
        return None

    texto = texto.replace("R$", "").replace("r$", "")
    texto = texto.replace("%", "")
    texto = texto.replace(" ", "")

    # primeira tentativa direta
    try:
        return float(texto)
    except:
        pass

    # formato brasileiro
    texto2 = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto2)
    except:
        return None


def corrigir_preco(valor):
    numero = para_float(valor)

    if numero is None:
        return 0.0

    # correção de preços multiplicados por 100
    if numero >= 1000:
        numero = numero / 100

    return round(float(numero), 2)


def para_int(valor):
    numero = para_float(valor)

    if numero is None:
        return 0

    try:
        return int(round(numero))
    except:
        return 0


# =========================
# LIMPEZA NÍVEL EXTREMO
# =========================
def limpar_dataframe_extremo(df, nome_arquivo="arquivo"):
    if df is None:
        log(f"{nome_arquivo}: dataframe inexistente.")
        return df

    df = df.copy()
    linhas_antes = len(df)
    colunas_antes = len(df.columns)

    # remove BOM dos nomes das colunas
    df.columns = [normalizar_texto(col) for col in df.columns]

    # remove colunas unnamed
    colunas_validas = []
    removidas_unnamed = 0
    for col in df.columns:
        if slug_coluna(col).startswith("unnamed"):
            removidas_unnamed += 1
            continue
        colunas_validas.append(col)
    df = df[colunas_validas]

    # remove colunas totalmente vazias
    cols_remover = []
    for col in df.columns:
        if coluna_vazia_serie(df[col]):
            cols_remover.append(col)
    if cols_remover:
        df = df.drop(columns=cols_remover)

    # limpa textos
    for col in df.columns:
        try:
            if df[col].dtype == "object":
                df[col] = df[col].apply(normalizar_texto)
            else:
                # mesmo colunas não-object podem conter sujeira visual ao serem convertidas
                df[col] = df[col].apply(lambda x: normalizar_texto(x) if isinstance(x, str) else x)
        except:
            pass

    # transforma strings vazias em NA temporariamente
    for col in df.columns:
        df[col] = df[col].apply(lambda x: pd.NA if normalizar_texto(x) == "" else x)

    # remove linhas totalmente vazias
    df = df.dropna(how="all")

    # remove duplicidade exata de linhas
    df = df.drop_duplicates()

    # preenche de volta vazios como string vazia
    df = df.fillna("")

    # remove colunas duplicadas pelo nome após normalização
    nomes_slug = []
    colunas_finais = []
    duplicadas_nome = 0
    for col in df.columns:
        s = slug_coluna(col)
        if s in nomes_slug:
            duplicadas_nome += 1
            continue
        nomes_slug.append(s)
        colunas_finais.append(col)
    df = df[colunas_finais]

    # remove linhas que viraram "só espaços" depois da limpeza
    linhas_validas = []
    for _, row in df.iterrows():
        tem_valor = False
        for valor in row.tolist():
            if normalizar_texto(valor) != "":
                tem_valor = True
                break
        linhas_validas.append(tem_valor)

    if len(linhas_validas) == len(df):
        df = df.loc[linhas_validas].copy()

    # reset índice
    df = df.reset_index(drop=True)

    linhas_depois = len(df)
    colunas_depois = len(df.columns)

    log(
        f"{nome_arquivo}: limpeza extrema concluída | "
        f"linhas {linhas_antes}->{linhas_depois} | "
        f"colunas {colunas_antes}->{colunas_depois} | "
        f"unnamed removidas={removidas_unnamed} | "
        f"nomes duplicados removidos={duplicadas_nome}"
    )

    return df


# =========================
# LEITURA
# =========================
def ler_planilha(arquivo):
    nome = arquivo.name.lower()

    if nome.endswith(".csv"):
        try:
            arquivo.seek(0)
            df = pd.read_csv(
                arquivo,
                sep=None,
                engine="python",
                encoding="utf-8",
                on_bad_lines="skip"
            )
        except:
            arquivo.seek(0)
            df = pd.read_csv(
                arquivo,
                sep=None,
                engine="python",
                encoding="latin-1",
                on_bad_lines="skip"
            )
    elif nome.endswith(".xlsx") or nome.endswith(".xls"):
        arquivo.seek(0)
        df = pd.read_excel(arquivo)
    else:
        raise ValueError(f"Formato não suportado: {arquivo.name}")

    df = limpar_dataframe_extremo(df, arquivo.name)
    return df


def ler_planilha_bytes(nome_arquivo, dados_bytes):
    nome = nome_arquivo.lower()

    if nome.endswith(".csv"):
        try:
            df = pd.read_csv(
                io.BytesIO(dados_bytes),
                sep=None,
                engine="python",
                encoding="utf-8",
                on_bad_lines="skip"
            )
        except:
            df = pd.read_csv(
                io.BytesIO(dados_bytes),
                sep=None,
                engine="python",
                encoding="latin-1",
                on_bad_lines="skip"
            )
    elif nome.endswith(".xlsx") or nome.endswith(".xls"):
        df = pd.read_excel(io.BytesIO(dados_bytes))
    else:
        raise ValueError(f"Formato não suportado: {nome_arquivo}")

    df = limpar_dataframe_extremo(df, nome_arquivo)
    return df


# =========================
# IDENTIFICAÇÃO
# =========================
def identificar_tipo(nome_arquivo, df):
    nome = nome_arquivo.lower()
    colunas_slug = [slug_coluna(c) for c in df.columns]

    if "estoque" in nome:
        return "estoque"

    if "cadastro" in nome or "produto" in nome:
        return "cadastro"

    if "balanco_obrigatorio" in colunas_slug:
        return "estoque"

    if "codigo" in colunas_slug and "descricao" in colunas_slug:
        return "cadastro"

    if "link_externo" in colunas_slug:
        return "cadastro"

    return None


# =========================
# VALIDAÇÃO BASE
# =========================
def validar_original_estoque(df):
    erros = []

    if df is None or df.empty:
        erros.append("Planilha original de estoque está vazia.")
        return erros

    col_codigo = buscar_coluna(df, [
        "Codigo produto *", "Codigo produto", "codigo_produto",
        "Código", "Codigo", "codigo"
    ])

    col_balanco = buscar_coluna(df, [
        "Balanço (OBRIGATÓRIO)", "Balanco (OBRIGATÓRIO)",
        "Balanço", "Balanco", "balanco_obrigatorio", "balanco"
    ])

    if not col_codigo:
        erros.append("Não encontrei coluna de código na planilha de estoque.")
    if not col_balanco:
        erros.append("Não encontrei coluna de estoque/balanço na planilha de estoque.")

    return erros


def validar_original_cadastro(df):
    erros = []

    if df is None or df.empty:
        erros.append("Planilha original de cadastro está vazia.")
        return erros

    col_codigo = buscar_coluna(df, ["Código", "Codigo", "codigo"])
    col_descricao = buscar_coluna(df, ["Descrição", "Descricao", "descricao"])

    if not col_codigo:
        erros.append("Não encontrei coluna de código na planilha de cadastro.")
    if not col_descricao:
        erros.append("Não encontrei coluna de descrição na planilha de cadastro.")

    return erros


# =========================
# GERAÇÃO BLING - ESTOQUE
# =========================
def gerar_estoque_bling(df):
    if df is None or df.empty:
        return pd.DataFrame()

    col_codigo = buscar_coluna(df, [
        "Codigo produto *", "Codigo produto", "codigo_produto",
        "Código", "Codigo", "codigo"
    ])

    col_balanco = buscar_coluna(df, [
        "Balanço (OBRIGATÓRIO)", "Balanco (OBRIGATÓRIO)",
        "Balanço", "Balanco", "balanco_obrigatorio", "balanco"
    ])

    resultado = pd.DataFrame()
    resultado["Código"] = df[col_codigo] if col_codigo else ""
    resultado["Depósito"] = "Geral"
    resultado["Estoque"] = df[col_balanco] if col_balanco else 0

    resultado["Código"] = resultado["Código"].apply(normalizar_texto)
    resultado["Depósito"] = resultado["Depósito"].apply(normalizar_texto)
    resultado["Estoque"] = resultado["Estoque"].apply(para_int)

    # remove linhas vazias
    resultado = resultado[resultado["Código"].astype(str).str.strip() != ""].copy()

    # remove duplicados por código
    resultado = resultado.drop_duplicates(subset=["Código"], keep="first").reset_index(drop=True)

    log(f"estoque_bling gerado com {len(resultado)} linhas.")
    return resultado


# =========================
# GERAÇÃO BLING - CADASTRO
# =========================
def gerar_cadastro_bling(df):
    if df is None or df.empty:
        return pd.DataFrame()

    col_codigo = buscar_coluna(df, ["Código", "Codigo", "codigo"])
    col_descricao = buscar_coluna(df, ["Descrição", "Descricao", "descricao"])
    col_unidade = buscar_coluna(df, ["Unidade", "unidade"])
    col_preco = buscar_coluna(df, ["Preço", "Preco", "preco"])
    col_situacao = buscar_coluna(df, ["Situação", "Situacao", "situacao"])
    col_descricao_curta = buscar_coluna(df, ["Descrição Curta", "Descricao Curta", "descricao_curta"])
    col_url = buscar_coluna(df, ["URL Imagens Externas", "Url Imagens Externas", "url_imagens_externas"])
    col_link = buscar_coluna(df, ["Link Externo", "link_externo"])
    col_marca = buscar_coluna(df, ["Marca", "marca"])

    resultado = pd.DataFrame()
    resultado["Código"] = df[col_codigo] if col_codigo else ""
    resultado["Descrição"] = df[col_descricao] if col_descricao else ""
    resultado["Unidade"] = df[col_unidade] if col_unidade else "UN"
    resultado["Preço"] = df[col_preco] if col_preco else 0
    resultado["Situação"] = df[col_situacao] if col_situacao else "Ativo"
    resultado["Marca"] = df[col_marca] if col_marca else ""
    resultado["Descrição Curta"] = df[col_descricao_curta] if col_descricao_curta else ""
    resultado["URL Imagens Externas"] = df[col_url] if col_url else ""
    resultado["Link Externo"] = df[col_link] if col_link else ""

    # limpeza
    for col in [
        "Código", "Descrição", "Unidade", "Situação", "Marca",
        "Descrição Curta", "URL Imagens Externas", "Link Externo"
    ]:
        resultado[col] = resultado[col].apply(normalizar_texto)

    resultado["Preço"] = resultado["Preço"].apply(corrigir_preco)

    # fallbacks
    resultado["Unidade"] = resultado["Unidade"].replace("", "UN")

    def normalizar_situacao(valor):
        v = normalizar_texto(valor).lower()

        if v in ["", "ativo", "1", "sim", "s", "true"]:
            return "Ativo"

        if v in ["inativo", "0", "nao", "não", "n", "false"]:
            return "Inativo"

        if "inativo" in v:
            return "Inativo"

        return "Ativo"

    resultado["Situação"] = resultado["Situação"].apply(normalizar_situacao)

    mascara_codigo_vazio = resultado["Código"].astype(str).str.strip() == ""
    resultado.loc[mascara_codigo_vazio, "Código"] = resultado.loc[mascara_codigo_vazio, "Descrição"]

    mascara_desc_curta_vazia = resultado["Descrição Curta"].astype(str).str.strip() == ""
    resultado.loc[mascara_desc_curta_vazia, "Descrição Curta"] = resultado.loc[mascara_desc_curta_vazia, "Descrição"]

    # remove linhas vazias
    resultado = resultado[resultado["Código"].astype(str).str.strip() != ""].copy()

    # remove duplicados
    resultado = resultado.drop_duplicates(subset=["Código"], keep="first").reset_index(drop=True)

    log(f"cadastro_bling gerado com {len(resultado)} linhas.")
    return resultado


# =========================
# VALIDAÇÃO FINAL BLING
# =========================
def validar_bling_estoque(df):
    erros = []

    if df is None or df.empty:
        erros.append("Arquivo final de estoque ficou vazio.")
        return erros

    obrigatorias = ["Código", "Depósito", "Estoque"]
    for col in obrigatorias:
        if col not in df.columns:
            erros.append(f"Falta a coluna obrigatória no estoque final: {col}")

    return erros


def validar_bling_cadastro(df):
    erros = []

    if df is None or df.empty:
        erros.append("Arquivo final de cadastro ficou vazio.")
        return erros

    obrigatorias = ["Código", "Descrição", "Unidade", "Preço", "Situação"]
    for col in obrigatorias:
        if col not in df.columns:
            erros.append(f"Falta a coluna obrigatória no cadastro final: {col}")

    return erros


# =========================
# EXPORTAÇÃO
# =========================
def dataframe_para_excel_bytes(df, aba="Dados"):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=aba)
    output.seek(0)
    return output.getvalue()


def gerar_zip_final(df_estoque, df_cadastro, logs):
    mem = io.BytesIO()

    with zipfile.ZipFile(mem, "w", compression=zipfile.ZIP_DEFLATED) as z:
        if df_estoque is not None and not df_estoque.empty:
            z.writestr(
                "atualizar_estoque.xlsx",
                dataframe_para_excel_bytes(df_estoque, "Estoque")
            )

        if df_cadastro is not None and not df_cadastro.empty:
            z.writestr(
                "cadastrar_produtos.xlsx",
                dataframe_para_excel_bytes(df_cadastro, "Cadastro")
            )

        z.writestr("log_processamento.txt", "\n".join(logs) if logs else "Sem logs.")

    mem.seek(0)
    return mem.getvalue()


# =========================
# PROCESSAMENTO ZIP
# =========================
def processar_zip(zip_file, progress_bar=None, status_box=None):
    df_estoque = None
    df_cadastro = None
    nome_estoque = None
    nome_cadastro = None
    arquivos_lidos = []

    with zipfile.ZipFile(zip_file, "r") as z:
        nomes = z.namelist()

        planilhas = [
            nome for nome in nomes
            if not nome.endswith("/") and nome.lower().endswith((".csv", ".xlsx", ".xls"))
        ]

        if not planilhas:
            raise ValueError("Nenhuma planilha válida encontrada dentro do ZIP.")

        total = len(planilhas)

        for i, nome in enumerate(planilhas, start=1):
            if progress_bar is not None:
                progress_bar.progress(int((i / total) * 100))

            if status_box is not None:
                status_box.write(f"🔄 Lendo {i}/{total}: {nome}")

            try:
                dados = z.read(nome)
                df = ler_planilha_bytes(nome, dados)
                tipo = identificar_tipo(nome, df)

                arquivos_lidos.append(nome)
                log(f"{nome}: tipo identificado = {tipo}")

                if tipo == "estoque" and df_estoque is None:
                    df_estoque = df
                    nome_estoque = nome

                elif tipo == "cadastro" and df_cadastro is None:
                    df_cadastro = df
                    nome_cadastro = nome

            except Exception as e:
                log(f"Erro ao ler {nome}: {e}")

    return df_estoque, df_cadastro, nome_estoque, nome_cadastro, arquivos_lidos


def processar_arquivos_soltos(arquivos, progress_bar=None, status_box=None):
    df_estoque = None
    df_cadastro = None
    nome_estoque = None
    nome_cadastro = None

    total = len(arquivos)

    for i, arquivo in enumerate(arquivos, start=1):
        if progress_bar is not None:
            progress_bar.progress(int((i / total) * 100))

        if status_box is not None:
            status_box.write(f"🔄 Lendo {i}/{total}: {arquivo.name}")

        try:
            df = ler_planilha(arquivo)
            tipo = identificar_tipo(arquivo.name, df)

            log(f"{arquivo.name}: tipo identificado = {tipo}")

            if tipo == "estoque" and df_estoque is None:
                df_estoque = df
                nome_estoque = arquivo.name

            elif tipo == "cadastro" and df_cadastro is None:
                df_cadastro = df
                nome_cadastro = arquivo.name

        except Exception as e:
            log(f"Erro ao ler {arquivo.name}: {e}")

    return df_estoque, df_cadastro, nome_estoque, nome_cadastro


# =========================
# TOPO
# =========================
top1, top2 = st.columns(2)

with top1:
    if st.button("🗑️ Limpar tudo", use_container_width=True):
        limpar_est
