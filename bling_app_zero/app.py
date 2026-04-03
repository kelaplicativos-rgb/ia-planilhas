import io
import re
import unicodedata
from typing import Optional, List, Dict, Tuple

import pandas as pd
import streamlit as st


# =========================================================
# CONFIG
# =========================================================
st.set_page_config(page_title="Bling Automação PRO", layout="wide")


# =========================================================
# ESTADO
# =========================================================
def init_state() -> None:
    defaults = {
        "logs": [],
        "df_origem": None,
        "df_saida": None,
        "nome_arquivo_origem": "",
        "nome_modelo_cadastro": "",
        "nome_modelo_estoque": "",
        "modelo_cadastro_raw": None,
        "modelo_estoque_raw": None,
        "mapa_manual": {},
        "ultimo_tipo_processamento": "Cadastro de produtos",
        "preview_aberto": False,
        "ajuste_manual_aberto": True,
        "mapeamento_final_aberto": True,
        "colunas_auto_aberto": False,
        "ultima_chave_arquivo": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def log(msg: str) -> None:
    st.session_state.logs.append(str(msg))


def limpar_tudo() -> None:
    st.session_state["logs"] = []
    st.session_state["df_origem"] = None
    st.session_state["df_saida"] = None
    st.session_state["nome_arquivo_origem"] = ""
    st.session_state["nome_modelo_cadastro"] = ""
    st.session_state["nome_modelo_estoque"] = ""
    st.session_state["modelo_cadastro_raw"] = None
    st.session_state["modelo_estoque_raw"] = None
    st.session_state["mapa_manual"] = {}
    st.session_state["ultimo_tipo_processamento"] = "Cadastro de produtos"
    st.session_state["preview_aberto"] = False
    st.session_state["ajuste_manual_aberto"] = True
    st.session_state["mapeamento_final_aberto"] = True
    st.session_state["colunas_auto_aberto"] = False
    st.session_state["ultima_chave_arquivo"] = ""

    for k in list(st.session_state.keys()):
        if k.startswith("map_"):
            del st.session_state[k]


# =========================================================
# TEXTO / NORMALIZAÇÃO
# =========================================================
def remover_acentos(texto: str) -> str:
    texto = str(texto)
    return "".join(
        c for c in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(c)
    )


def limpar_texto(valor) -> str:
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except Exception:
        pass

    texto = str(valor)
    texto = texto.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def slug_coluna(nome: str) -> str:
    nome = limpar_texto(nome)
    nome = remover_acentos(nome).lower()
    nome = nome.replace("/", " ")
    nome = nome.replace("\\", " ")
    nome = nome.replace("-", " ")
    nome = nome.replace("_", " ")
    nome = re.sub(r"[^a-z0-9 ]+", "", nome)
    nome = re.sub(r"\s+", " ", nome).strip()
    return nome


def normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    novas = []
    usados = {}

    for c in df.columns:
        base = slug_coluna(c)
        if not base:
            base = "coluna"

        if base not in usados:
            usados[base] = 1
            novas.append(base)
        else:
            usados[base] += 1
            novas.append(f"{base}_{usados[base]}")

    df.columns = novas
    return df


def limpar_dataframe_origem(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    df = normalizar_colunas(df)

    for col in df.columns:
        df[col] = df[col].apply(limpar_texto)

    df = df.replace("", pd.NA)
    df = df.dropna(axis=0, how="all")
    df = df.dropna(axis=1, how="all")
    df = df.fillna("")
    df = df.reset_index(drop=True)
    return df


def limpar_dataframe_modelo(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(axis=0, how="all")
    df = df.reset_index(drop=True)
    return df


# =========================================================
# LEITURA DE ARQUIVO
# =========================================================
def _ler_csv_com_tentativas(arquivo, limpar: bool) -> pd.DataFrame:
    tentativas = [
        {"sep": None, "engine": "python", "encoding": "utf-8"},
        {"sep": ";", "engine": "python", "encoding": "utf-8"},
        {"sep": ",", "engine": "python", "encoding": "utf-8"},
        {"sep": "\t", "engine": "python", "encoding": "utf-8"},
        {"sep": None, "engine": "python", "encoding": "latin-1"},
        {"sep": ";", "engine": "python", "encoding": "latin-1"},
        {"sep": ",", "engine": "python", "encoding": "latin-1"},
        {"sep": "\t", "engine": "python", "encoding": "latin-1"},
    ]

    ultimo_erro = None
    for t in tentativas:
        try:
            arquivo.seek(0)
            df = pd.read_csv(
                arquivo,
                sep=t["sep"],
                engine=t["engine"],
                encoding=t["encoding"],
                dtype=str,
                on_bad_lines="skip",
            )
            if limpar:
                df = limpar_dataframe_origem(df)
            else:
                df = limpar_dataframe_modelo(df)
            if len(df.columns) > 0:
                return df
        except Exception as e:
            ultimo_erro = e

    raise ValueError(f"Erro ao ler CSV: {ultimo_erro}")


def ler_planilha_origem(arquivo) -> pd.DataFrame:
    nome = arquivo.name.lower()

    if nome.endswith(".csv"):
        return _ler_csv_com_tentativas(arquivo, limpar=True)

    arquivo.seek(0)
    try:
        df = pd.read_excel(arquivo, dtype=str)
        return limpar_dataframe_origem(df)
    except Exception as e:
        raise ValueError(f"Erro ao ler planilha de origem: {e}")


def ler_modelo_bling(arquivo) -> pd.DataFrame:
    nome = arquivo.name.lower()

    if nome.endswith(".csv"):
        return _ler_csv_com_tentativas(arquivo, limpar=False)

    arquivo.seek(0)
    try:
        df = pd.read_excel(arquivo, dtype=str)
        return limpar_dataframe_modelo(df)
    except Exception as e:
        raise ValueError(f"Erro ao ler modelo Bling: {e}")


# =========================================================
# EXPORTAÇÃO
# =========================================================
def salvar_excel_bytes(df: pd.DataFrame, nome_aba: str = "Dados") -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=nome_aba)
    buffer.seek(0)
    return buffer.getvalue()


def salvar_txt_bytes(texto: str) -> bytes:
    return texto.encode("utf-8")


# =========================================================
# DETECÇÃO DE COLUNAS
# =========================================================
def encontrar_coluna(df: pd.DataFrame, candidatos: List[str]) -> Optional[str]:
    mapa = {slug_coluna(c): c for c in df.columns}

    for cand in candidatos:
        s = slug_coluna(cand)
        if s in mapa:
            return mapa[s]

    for cand in candidatos:
        s = slug_coluna(cand)
        for col in df.columns:
            if s and s in slug_coluna(col):
                return col

    return None


def encontrar_colunas_imagem(df: pd.DataFrame) -> List[str]:
    colunas_imagem = []
    chaves = [
        "imagem", "imagens", "foto", "fotos", "url imagem", "url imagens",
        "link imagem", "link imagens", "image", "images", "gallery",
        "imagem 1", "imagem1", "imagem principal", "url da imagem",
        "url imagens externas"
    ]

    for col in df.columns:
        s = slug_coluna(col)
        if any(ch in s for ch in [slug_coluna(x) for x in chaves]):
            colunas_imagem.append(col)

    vistas = set()
    final = []
    for c in colunas_imagem:
        if c not in vistas:
            vistas.add(c)
            final.append(c)

    return final[:10]


def detectar_colunas(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    m = {}
    m["codigo"] = encontrar_coluna(
        df,
        [
            "codigo", "código", "sku", "ref", "referencia", "referência",
            "cod produto", "codigo produto", "id produto", "part number",
            "ean", "gtin", "cod", "codigo sku"
        ],
    )
    m["nome"] = encontrar_coluna(
        df,
        ["nome", "produto", "titulo", "título", "nome produto", "descricao", "descrição"]
    )
    m["descricao_curta"] = encontrar_coluna(
        df,
        [
            "descricao curta", "descrição curta", "descricao", "descrição",
            "detalhes", "resumo", "informacoes", "informações",
            "descricao produto", "descrição produto",
            "descricao complementar", "descrição complementar"
        ],
    )
    m["preco"] = encontrar_coluna(
        df,
        [
            "preco", "preço", "valor", "valor venda", "preco venda",
            "preço venda", "preco final", "preco de venda"
        ],
    )
    m["marca"] = encontrar_coluna(df, ["marca", "fabricante", "brand"])
    m["imagem"] = encontrar_coluna(
        df,
        [
            "imagem", "imagens", "imagem 1", "url imagem", "url da imagem", "foto",
            "link imagem", "url imagens externas"
        ],
    )
    m["link_externo"] = encontrar_coluna(
        df,
        ["link externo", "url produto", "link produto", "produto url", "link", "url"]
    )
    m["estoque"] = encontrar_coluna(
        df,
        [
            "estoque", "saldo", "qtd", "quantidade", "quantidade estoque",
            "saldo atual", "balanco", "balanço"
        ],
    )
    m["situacao"] = encontrar_coluna(df, ["situacao", "situação", "status", "ativo"])
    m["unidade"] = encontrar_coluna(df, ["unidade", "und", "un"])

    return m


# =========================================================
# AJUSTES DE DADOS
# =========================================================
def corrigir_preco(valor) -> str:
    texto = limpar_texto(valor)
    if not texto:
        return ""

    texto = texto.replace("R$", "").replace("r$", "").strip()
    texto = texto.replace(" ", "")

    if texto.count(",") > 0 and texto.count(".") > 0:
        texto = texto.replace(".", "").replace(",", ".")
    elif texto.count(",") > 0:
        texto = texto.replace(",", ".")

    try:
        numero = float(texto)
        return f"{numero:.2f}"
    except Exception:
        return ""


def corrigir_estoque(valor) -> int:
    texto = limpar_texto(valor)
    if not texto:
        return 0

    texto = texto.replace(" ", "")

    if texto.count(",") > 0 and texto.count(".") > 0:
        texto = texto.replace(".", "").replace(",", ".")
    elif texto.count(",") > 0:
        texto = texto.replace(",", ".")

    try:
        return int(float(texto))
    except Exception:
        return 0


def normalizar_situacao(valor) -> str:
    t = slug_coluna(valor)

    if t in ["", "ativo", "1", "sim", "s", "true"]:
        return "Ativo"

    if t in ["inativo", "0", "nao", "n", "false"]:
        return "Inativo"

    if "inativo" in t:
        return "Inativo"

    return "Ativo"


def eh_texto_numerico_sem_url(texto: str) -> bool:
    texto = limpar_texto(texto)
    if not texto:
        return False
    return bool(re.fullmatch(r"[0-9.,]+", texto))


def extrair_urls_validas(texto: str) -> List[str]:
    texto = limpar_texto(texto)
    if not texto:
        return []

    if eh_texto_numerico_sem_url(texto):
        return []

    urls = re.findall(r"https?://[^\s,;|]+", texto, flags=re.IGNORECASE)

    if not urls and texto.startswith("www."):
        urls = [f"https://{texto}"]

    final = []
    vistas = set()

    for url in urls:
        url = limpar_texto(url)
        if not url:
            continue
        if eh_texto_numerico_sem_url(url):
            continue
        if not re.match(r"^https?://", url, flags=re.IGNORECASE):
            continue
        if url not in vistas:
            vistas.add(url)
            final.append(url)

    return final


def quebrar_urls_imagem(texto: str) -> List[str]:
    """
    Regra fixa do projeto:
    múltiplas imagens na mesma célula devem vir separadas por |
    """
    texto = limpar_texto(texto)

    if not texto:
        return []

    if eh_texto_numerico_sem_url(texto):
        return []

    partes = texto.split("|")
    urls = []

    for parte in partes:
        p = limpar_texto(parte)
        if not p:
            continue
        if eh_texto_numerico_sem_url(p):
            continue

        urls.extend(extrair_urls_validas(p))

    vistas = set()
    final = []

    for u in urls:
        if u not in vistas:
            vistas.add(u)
            final.append(u)

    return final[:5]


def limpar_link_externo(valor: str) -> str:
    urls = extrair_urls_validas(valor)
    return urls[0] if urls else ""


def extrair_imagens_da_linha(
    row: pd.Series,
    coluna_imagem_principal: Optional[str],
    colunas_imagem_extras: List[str],
) -> List[str]:
    urls = []

    if coluna_imagem_principal and coluna_imagem_principal in row.index:
        urls.extend(quebrar_urls_imagem(row[coluna_imagem_principal]))

    for col in colunas_imagem_extras:
        if col in row.index:
            urls.extend(quebrar_urls_imagem(row[col]))

    vistas = set()
    final = []
    for u in urls:
        u = limpar_texto(u)
        if u and u not in vistas:
            vistas.add(u)
            final.append(u)

    return final[:5]


# =========================================================
# MODELO BLING
# =========================================================
def encontrar_coluna_modelo(modelo_df: pd.DataFrame, candidatos: List[str]) -> Optional[str]:
    for col in modelo_df.columns:
        col_slug = slug_coluna(col)
        for cand in candidatos:
            if col_slug == slug_coluna(cand):
                return col

    for col in modelo_df.columns:
        col_slug = slug_coluna(col)
        for cand in candidatos:
            cand_slug = slug_coluna(cand)
            if cand_slug and cand_slug in col_slug:
                return col

    return None


def criar_saida_no_modelo(modelo_df: pd.DataFrame, quantidade_linhas: int) -> pd.DataFrame:
    return pd.DataFrame("", index=range(quantidade_linhas), columns=list(modelo_df.columns))


def localizar_campos_modelo_cadastro(modelo_df: pd.DataFrame) -> Dict[str, Optional[str]]:
    return {
        "id": encontrar_coluna_modelo(modelo_df, ["id", "codigo pai", "código pai"]),
        "codigo": encontrar_coluna_modelo(modelo_df, ["codigo", "código", "sku"]),
        "nome": encontrar_coluna_modelo(modelo_df, ["nome", "nome produto", "produto"]),
        "unidade": encontrar_coluna_modelo(modelo_df, ["unidade", "und", "un"]),
        "preco": encontrar_coluna_modelo(modelo_df, ["preco", "preço", "valor", "preco venda"]),
        "situacao": encontrar_coluna_modelo(modelo_df, ["situacao", "situação", "status"]),
        "marca": encontrar_coluna_modelo(modelo_df, ["marca", "fabricante"]),
        "descricao_curta": encontrar_coluna_modelo(modelo_df, ["descricao curta", "descrição curta"]),
        "descricao": encontrar_coluna_modelo(modelo_df, ["descricao", "descrição"]),
        "video": encontrar_coluna_modelo(modelo_df, ["video", "vídeo"]),
        "imagem_1": encontrar_coluna_modelo(modelo_df, ["imagem 1", "imagem1"]),
        "imagem_2": encontrar_coluna_modelo(modelo_df, ["imagem 2", "imagem2"]),
        "imagem_3": encontrar_coluna_modelo(modelo_df, ["imagem 3", "imagem3"]),
        "imagem_4": encontrar_coluna_modelo(modelo_df, ["imagem 4", "imagem4"]),
        "imagem_5": encontrar_coluna_modelo(modelo_df, ["imagem 5", "imagem5"]),
        "imagem_unica": encontrar_coluna_modelo(modelo_df, ["imagem", "imagens"]),
        "link_externo": encontrar_coluna_modelo(modelo_df, ["link externo", "url produto", "link produto", "url"]),
        "estoque": encontrar_coluna_modelo(modelo_df, ["estoque", "saldo"]),
    }


def localizar_campos_modelo_estoque(modelo_df: pd.DataFrame) -> Dict[str, Optional[str]]:
    return {
        "id": encontrar_coluna_modelo(modelo_df, ["id"]),
        "codigo": encontrar_coluna_modelo(modelo_df, ["codigo", "código", "sku"]),
        "nome": encontrar_coluna_modelo(modelo_df, ["nome", "nome produto", "produto"]),
        "deposito": encontrar_coluna_modelo(modelo_df, ["deposito", "depósito", "almoxarifado"]),
        "estoque": encontrar_coluna_modelo(modelo_df, ["estoque", "saldo", "quantidade"]),
        "preco_unitario": encontrar_coluna_modelo(modelo_df, ["preco unitario", "preço unitário", "preco", "preço"]),
    }


# =========================================================
# VALIDAÇÃO
# =========================================================
def validar_saida_cadastro(df_saida: pd.DataFrame, modelo_df: pd.DataFrame) -> Tuple[List[str], List[str]]:
    erros = []
    avisos = []

    if df_saida.empty:
        erros.append("A planilha final de cadastro ficou vazia.")
        return erros, avisos

    col_codigo = encontrar_coluna_modelo(modelo_df, ["codigo", "código", "sku"])
    col_nome = encontrar_coluna_modelo(modelo_df, ["nome", "nome produto", "produto"])
    col_desc_curta = encontrar_coluna_modelo(modelo_df, ["descricao curta", "descrição curta"])

    if not col_codigo:
        erros.append("O modelo de cadastro do Bling não possui coluna de código/SKU.")
    if not col_nome:
        erros.append("O modelo de cadastro do Bling não possui coluna de nome.")
    if not col_desc_curta:
        avisos.append("O modelo de cadastro do Bling não possui coluna de descrição curta.")

    if col_codigo and col_codigo in df_saida.columns:
        vazios = int((df_saida[col_codigo].astype(str).str.strip() == "").sum())
        if vazios > 0:
            erros.append(f"Existem {vazios} linhas sem código.")

    if col_nome and col_nome in df_saida.columns:
        vazios = int((df_saida[col_nome].astype(str).str.strip() == "").sum())
        if vazios > 0:
            erros.append(f"Existem {vazios} linhas sem nome.")

    return erros, avisos


def validar_saida_estoque(df_saida: pd.DataFrame, modelo_df: pd.DataFrame) -> Tuple[List[str], List[str]]:
    erros = []
    avisos = []

    if df_saida.empty:
        erros.append("A planilha final de estoque ficou vazia.")
        return erros, avisos

    campos = localizar_campos_modelo_estoque(modelo_df)

    if not campos["codigo"]:
        erros.append("O modelo de estoque do Bling não possui coluna de código/SKU.")
    if not campos["deposito"]:
        erros.append("O modelo de estoque do Bling não possui coluna de depósito.")
    if not campos["estoque"]:
        erros.append("O modelo de estoque do Bling não possui coluna de estoque.")

    if campos["codigo"] and campos["codigo"] in df_saida.columns:
        vazios = int((df_saida[campos["codigo"]].astype(str).str.strip() == "").sum())
        if vazios > 0:
            erros.append(f"Existem {vazios} linhas sem código.")

    if campos["deposito"] and campos["deposito"] in df_saida.columns:
        vazios = int((df_saida[campos["deposito"]].astype(str).str.strip() == "").sum())
        if vazios > 0:
            erros.append("O depósito ficou vazio em uma ou mais linhas.")

    return erros, avisos


# =========================================================
# MAPEAMENTO BLING DENTRO DO MODELO
# =========================================================
def mapear_cadastro_no_modelo_bling(
    df: pd.DataFrame,
    mapa: Dict[str, Optional[str]],
    colunas_imagem_extras: List[str],
    modelo_df: pd.DataFrame,
) -> pd.DataFrame:
    campos_modelo = localizar_campos_modelo_cadastro(modelo_df)
    saida = criar_saida_no_modelo(modelo_df, len(df))

    codigo_col = mapa.get("codigo")
    nome_col = mapa.get("nome")
    desc_col = mapa.get("descricao_curta")
    preco_col = mapa.get("preco")
    marca_col = mapa.get("marca")
    imagem_col = mapa.get("imagem")
    link_col = mapa.get("link_externo")
    situacao_col = mapa.get("situacao")
    unidade_col = mapa.get("unidade")
    estoque_col = mapa.get("estoque")

    if campos_modelo["id"]:
        saida[campos_modelo["id"]] = ""

    if campos_modelo["codigo"]:
        saida[campos_modelo["codigo"]] = df[codigo_col] if codigo_col and codigo_col in df.columns else ""

    if campos_modelo["nome"]:
        saida[campos_modelo["nome"]] = df[nome_col] if nome_col and nome_col in df.columns else ""

    if campos_modelo["unidade"]:
        saida[campos_modelo["unidade"]] = df[unidade_col] if unidade_col and unidade_col in df.columns else "UN"

    if campos_modelo["preco"]:
        saida[campos_modelo["preco"]] = df[preco_col] if preco_col and preco_col in df.columns else ""

    if campos_modelo["situacao"]:
        saida[campos_modelo["situacao"]] = df[situacao_col] if situacao_col and situacao_col in df.columns else "Ativo"

    if campos_modelo["marca"]:
        saida[campos_modelo["marca"]] = df[marca_col] if marca_col and marca_col in df.columns else ""

    if campos_modelo["descricao_curta"]:
        saida[campos_modelo["descricao_curta"]] = df[desc_col] if desc_col and desc_col in df.columns else ""

    if campos_modelo["descricao"]:
        saida[campos_modelo["descricao"]] = ""

    if campos_modelo["video"]:
        saida[campos_modelo["video"]] = ""

    if campos_modelo["estoque"]:
        saida[campos_modelo["estoque"]] = df[estoque_col] if estoque_col and estoque_col in df.columns else ""

    imagens_linhas = []
    for _, row in df.iterrows():
        imagens_linhas.append(extrair_imagens_da_linha(row, imagem_col, colunas_imagem_extras))

    colunas_multiplas = [
        campos_modelo["imagem_1"],
        campos_modelo["imagem_2"],
        campos_modelo["imagem_3"],
        campos_modelo["imagem_4"],
        campos_modelo["imagem_5"],
    ]
    tem_colunas_multiplas = any(colunas_multiplas)

    if tem_colunas_multiplas:
        for idx, imagens in enumerate(imagens_linhas):
            for pos, campo in enumerate(colunas_multiplas):
                if campo:
                    saida.at[idx, campo] = imagens[pos] if pos < len(imagens) else ""
    elif campos_modelo["imagem_unica"]:
        saida[campos_modelo["imagem_unica"]] = ["|".join(imagens) for imagens in imagens_linhas]

    if campos_modelo["link_externo"]:
        if link_col and link_col in df.columns:
            saida[campos_modelo["link_externo"]] = df[link_col].apply(limpar_link_externo)
        else:
            saida[campos_modelo["link_externo"]] = ""

    for col in saida.columns:
        if col == campos_modelo["preco"]:
            continue
        saida[col] = saida[col].apply(limpar_texto)

    if campos_modelo["preco"]:
        saida[campos_modelo["preco"]] = saida[campos_modelo["preco"]].apply(corrigir_preco)

    if campos_modelo["situacao"]:
        saida[campos_modelo["situacao"]] = saida[campos_modelo["situacao"]].apply(normalizar_situacao)

    if campos_modelo["unidade"]:
        saida[campos_modelo["unidade"]] = saida[campos_modelo["unidade"]].replace("", "UN")

    if campos_modelo["descricao_curta"] and campos_modelo["nome"]:
        vazia = saida[campos_modelo["descricao_curta"]].astype(str).str.strip() == ""
        saida.loc[vazia, campos_modelo["descricao_curta"]] = saida.loc[vazia, campos_modelo["nome"]]

    if campos_modelo["codigo"]:
        antes = len(saida)
        saida = saida[saida[campos_modelo["codigo"]].astype(str).str.strip() != ""].copy()
        removidas_sem_codigo = antes - len(saida)
        if removidas_sem_codigo > 0:
            log(f"Cadastro: removidas {removidas_sem_codigo} linhas sem código.")

        antes_dup = len(saida)
        saida = saida.drop_duplicates(subset=[campos_modelo["codigo"]], keep="first").reset_index(drop=True)
        removidas_duplicadas = antes_dup - len(saida)
        if removidas_duplicadas > 0:
            log(f"Cadastro: removidas {removidas_duplicadas} linhas com código duplicado.")

    return saida


def mapear_estoque_no_modelo_bling(
    df: pd.DataFrame,
    mapa: Dict[str, Optional[str]],
    deposito: str,
    modelo_df: pd.DataFrame,
) -> pd.DataFrame:
    campos_modelo = localizar_campos_modelo_estoque(modelo_df)
    saida = criar_saida_no_modelo(modelo_df, len(df))

    codigo_col = mapa.get("codigo")
    estoque_col_origem = mapa.get("estoque")
    nome_col = mapa.get("nome")
    preco_col = mapa.get("preco")

    if campos_modelo["id"]:
        saida[campos_modelo["id"]] = ""

    if campos_modelo["codigo"]:
        saida[campos_modelo["codigo"]] = df[codigo_col] if codigo_col and codigo_col in df.columns else ""

    if campos_modelo["nome"]:
        saida[campos_modelo["nome"]] = df[nome_col] if nome_col and nome_col in df.columns else ""

    if campos_modelo["deposito"]:
        saida[campos_modelo["deposito"]] = limpar_texto(deposito)

    if campos_modelo["estoque"]:
        origem = df[estoque_col_origem] if estoque_col_origem and estoque_col_origem in df.columns else 0
        saida[campos_modelo["estoque"]] = pd.Series(origem).apply(corrigir_estoque)

    if campos_modelo["preco_unitario"]:
        origem_preco = df[preco_col] if preco_col and preco_col in df.columns else ""
        saida[campos_modelo["preco_unitario"]] = pd.Series(origem_preco).apply(corrigir_preco)

    for col in saida.columns:
        if col in [campos_modelo["estoque"], campos_modelo["preco_unitario"]]:
            continue
        saida[col] = saida[col].apply(limpar_texto)

    if campos_modelo["codigo"]:
        antes = len(saida)
        saida = saida[saida[campos_modelo["codigo"]].astype(str).str.strip() != ""].copy()
        removidas_sem_codigo = antes - len(saida)
        if removidas_sem_codigo > 0:
            log(f"Estoque: removidas {removidas_sem_codigo} linhas sem código.")

        antes_dup = len(saida)
        saida = saida.drop_duplicates(subset=[campos_modelo["codigo"]], keep="first").reset_index(drop=True)
        removidas_duplicadas = antes_dup - len(saida)
        if removidas_duplicadas > 0:
            log(f"Estoque: removidas {removidas_duplicadas} linhas com código duplicado.")

    return saida


# =========================================================
# UI DE MAPEAMENTO MANUAL
# =========================================================
def montar_opcoes_colunas(df: pd.DataFrame) -> List[str]:
    return [""] + list(df.columns)


def select_coluna(label: str, opcoes: List[str], valor_atual: Optional[str], key: str) -> str:
    valor_atual = valor_atual if valor_atual in opcoes else ""
    idx = opcoes.index(valor_atual) if valor_atual in opcoes else 0
    return st.selectbox(label, options=opcoes, index=idx, key=key)


def construir_mapa_manual(
    df: pd.DataFrame,
    mapa_auto: Dict[str, Optional[str]],
) -> Dict[str, Optional[str]]:
    opcoes = montar_opcoes_colunas(df)
    mapa_manual = dict(mapa_auto)

    c1, c2, c3 = st.columns(3)

    with c1:
        mapa_manual["codigo"] = select_coluna(
            "Código / SKU", opcoes, mapa_auto.get("codigo"), "map_codigo"
        )
        mapa_manual["nome"] = select_coluna(
            "Nome do produto", opcoes, mapa_auto.get("nome"), "map_nome"
        )
        mapa_manual["descricao_curta"] = select_coluna(
            "Descrição curta", opcoes, mapa_auto.get("descricao_curta"), "map_descricao_curta"
        )

    with c2:
        mapa_manual["preco"] = select_coluna(
            "Preço", opcoes, mapa_auto.get("preco"), "map_preco"
        )
        mapa_manual["marca"] = select_coluna(
            "Marca", opcoes, mapa_auto.get("marca"), "map_marca"
        )
        mapa_manual["imagem"] = select_coluna(
            "Coluna principal de imagem", opcoes, mapa_auto.get("imagem"), "map_imagem"
        )

    with c3:
        mapa_manual["link_externo"] = select_coluna(
            "Link externo", opcoes, mapa_auto.get("link_externo"), "map_link_externo"
        )
        mapa_manual["estoque"] = select_coluna(
            "Estoque / Quantidade", opcoes, mapa_auto.get("estoque"), "map_estoque"
        )
        mapa_manual["situacao"] = select_coluna(
            "Situação", opcoes, mapa_auto.get("situacao"), "map_situacao"
        )

    mapa_manual["unidade"] = st.selectbox(
        "Unidade",
        options=opcoes,
        index=opcoes.index(mapa_auto.get("unidade")) if mapa_auto.get("unidade") in opcoes else 0,
        key="map_unidade",
    )

    return {k: (v if limpar_texto(v) else None) for k, v in mapa_manual.items()}


def montar_df_colunas_automaticas(
    mapa_auto: Dict[str, Optional[str]],
    colunas_imagem_auto: List[str],
) -> pd.DataFrame:
    linhas = []

    ordem = [
        "codigo",
        "nome",
        "descricao_curta",
        "preco",
        "marca",
        "imagem",
        "link_externo",
        "estoque",
        "situacao",
        "unidade",
    ]

    nomes_exibicao = {
        "codigo": "Código / SKU",
        "nome": "Nome do produto",
        "descricao_curta": "Descrição curta",
        "preco": "Preço",
        "marca": "Marca",
        "imagem": "Imagem principal",
        "link_externo": "Link externo",
        "estoque": "Estoque / Quantidade",
        "situacao": "Situação",
        "unidade": "Unidade",
    }

    for campo in ordem:
        linhas.append(
            {
                "Campo Bling": nomes_exibicao.get(campo, campo),
                "Coluna detectada": mapa_auto.get(campo) or "",
            }
        )

    if colunas_imagem_auto:
        linhas.append(
            {
                "Campo Bling": "Outras colunas de imagem detectadas",
                "Coluna detectada": " | ".join(colunas_imagem_auto),
            }
        )

    return pd.DataFrame(linhas)


def montar_df_mapeamento_final(
    tipo_processamento: str,
    mapa_final: Dict[str, Optional[str]],
    imagem_principal: Optional[str],
    colunas_imagem_extras: List[str],
    modelo_nome: str,
) -> pd.DataFrame:
    nomes_exibicao = {
        "codigo": "Código / SKU",
        "nome": "Nome do produto",
        "descricao_curta": "Descrição curta",
        "preco": "Preço",
        "marca": "Marca",
        "imagem": "Imagem principal",
        "link_externo": "Link externo",
        "estoque": "Estoque / Quantidade",
        "situacao": "Situação",
        "unidade": "Unidade",
    }

    if tipo_processamento == "Cadastro de produtos":
        ordem = [
            "codigo",
            "nome",
            "descricao_curta",
            "preco",
            "marca",
            "imagem",
            "link_externo",
            "estoque",
            "situacao",
            "unidade",
        ]
    else:
        ordem = [
            "codigo",
            "nome",
            "estoque",
            "preco",
        ]

    linhas = []
    linhas.append({"Campo Bling": "Modelo Bling anexado", "Coluna escolhida": modelo_nome})

    for campo in ordem:
        linhas.append(
            {
                "Campo Bling": nomes_exibicao.get(campo, campo),
                "Coluna escolhida": mapa_final.get(campo) or "",
            }
        )

    linhas.append(
        {
            "Campo Bling": "Imagem principal usada",
            "Coluna escolhida": imagem_principal or "",
        }
    )
    linhas.append(
        {
            "Campo Bling": "Colunas extras de imagem",
            "Coluna escolhida": " | ".join(colunas_imagem_extras) if colunas_imagem_extras else "",
        }
    )
    linhas.append(
        {
            "Campo Bling": "Regra fixa",
            "Coluna escolhida": "Descrição do fornecedor -> descrição curta | descrição -> vazio | vídeo -> vazio",
        }
    )

    return pd.DataFrame(linhas)


# =========================================================
# APP
# =========================================================
def main() -> None:
    init_state()

    st.title("Bling Automação PRO")
    st.subheader("Leitura automática para vários fornecedores")

    with st.sidebar:
        st.header("⚙️ Configurações")

        tipo_processamento = st.radio(
            "Tipo de saída",
            ["Cadastro de produtos", "Atualização de estoque"],
            index=0 if st.session_state["ultimo_tipo_processamento"] == "Cadastro de produtos" else 1,
        )
        st.session_state["ultimo_tipo_processamento"] = tipo_processamento

        deposito = ""
        if tipo_processamento == "Atualização de estoque":
            deposito = st.text_input(
                "Em qual estoque será lançado?",
                placeholder="Ex: Geral, Loja, CD",
            )

        st.divider()

        if st.button("Limpar tudo", use_container_width=True):
            limpar_tudo()
            st.rerun()

    st.subheader("Envio dos arquivos")

    arquivo_origem = st.file_uploader(
        "1) Planilha do fornecedor",
        type=["xlsx", "xls", "csv"],
        key="upload_origem",
    )

    col_modelo_1, col_modelo_2 = st.columns(2)

    with col_modelo_1:
        modelo_cadastro = st.file_uploader(
            "2) Modelo de cadastro do Bling",
            type=["xlsx", "xls", "csv"],
            key="upload_modelo_cadastro",
        )

    with col_modelo_2:
        modelo_estoque = st.file_uploader(
            "3) Modelo de estoque do Bling",
            type=["xlsx", "xls", "csv"],
            key="upload_modelo_estoque",
        )

    if arquivo_origem is not None:
        chave_atual = f"{arquivo_origem.name}-{getattr(arquivo_origem, 'size', 0)}"
        if st.session_state["ultima_chave_arquivo"] != chave_atual:
            try:
                df = ler_planilha_origem(arquivo_origem)
                st.session_state["df_origem"] = df
                st.session_state["nome_arquivo_origem"] = arquivo_origem.name
                st.session_state["df_saida"] = None
                st.session_state["mapa_manual"] = {}
                st.session_state["ultima_chave_arquivo"] = chave_atual

                for k in list(st.session_state.keys()):
                    if k.startswith("map_"):
                        del st.session_state[k]

                log(f"Arquivo de origem carregado: {arquivo_origem.name}")
                log(f"Linhas: {len(df)} | Colunas: {len(df.columns)}")
            except Exception as e:
                st.error(f"Erro ao ler arquivo de origem: {e}")
                log(f"Erro ao ler arquivo de origem: {e}")
                return

    if modelo_cadastro is not None:
        try:
            modelo_df = ler_modelo_bling(modelo_cadastro)
            st.session_state["modelo_cadastro_raw"] = modelo_df
            st.session_state["nome_modelo_cadastro"] = modelo_cadastro.name
        except Exception as e:
            st.error(f"Erro ao ler modelo de cadastro: {e}")
            log(f"Erro ao ler modelo de cadastro: {e}")
            return

    if modelo_estoque is not None:
        try:
            modelo_df = ler_modelo_bling(modelo_estoque)
            st.session_state["modelo_estoque_raw"] = modelo_df
            st.session_state["nome_modelo_estoque"] = modelo_estoque.name
        except Exception as e:
            st.error(f"Erro ao ler modelo de estoque: {e}")
            log(f"Erro ao ler modelo de estoque: {e}")
            return

    df = st.session_state["df_origem"]

    if df is None:
        st.info("Anexe a planilha do fornecedor para começar.")
        return

    st.success(f"✅ Arquivo de origem carregado: {st.session_state['nome_arquivo_origem']}")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Linhas", len(df))
    with c2:
        st.metric("Colunas", len(df.columns))
    with c3:
        st.metric("Campos detectados", len([v for v in detectar_colunas(df).values() if v]))

    mapa_auto = detectar_colunas(df)
    colunas_imagem_auto = encontrar_colunas_imagem(df)

    with st.expander("👀 Preview", expanded=st.session_state["preview_aberto"]):
        st.dataframe(df.head(1), use_container_width=True)

    with st.expander("🛠️ Ajuste manual das colunas", expanded=st.session_state["ajuste_manual_aberto"]):
        st.caption("Se alguma coluna foi identificada errado, ajuste aqui manualmente.")
        mapa_final_temp = construir_mapa_manual(df, mapa_auto)
        st.session_state["mapa_manual"] = mapa_final_temp

        st.info(
            "Regra fixa do sistema: a descrição da planilha de dados sempre vai para "
            "'descrição curta'. A coluna 'descrição' fica vazia. A coluna 'vídeo' também fica vazia."
        )

    mapa_final = st.session_state.get("mapa_manual") or mapa_auto
    imagem_principal = mapa_final.get("imagem")
    colunas_imagem_extras = [c for c in colunas_imagem_auto if c != imagem_principal]

    modelo_nome_exibicao = (
        st.session_state["nome_modelo_cadastro"]
        if tipo_processamento == "Cadastro de produtos"
        else st.session_state["nome_modelo_estoque"]
    )

    with st.expander("✅ Mapeamento final que será usado", expanded=st.session_state["mapeamento_final_aberto"]):
        df_mapeamento_final = montar_df_mapeamento_final(
            tipo_processamento=tipo_processamento,
            mapa_final=mapa_final,
            imagem_principal=imagem_principal,
            colunas_imagem_extras=colunas_imagem_extras,
            modelo_nome=modelo_nome_exibicao or "",
        )
        st.dataframe(df_mapeamento_final, use_container_width=True, hide_index=True)

        if st.session_state["df_saida"] is not None:
            st.dataframe(st.session_state["df_saida"].head(20), use_container_width=True)

    with st.expander("🔎 Colunas identificadas automaticamente", expanded=st.session_state["colunas_auto_aberto"]):
        df_auto = montar_df_colunas_automaticas(mapa_auto, colunas_imagem_auto)
        st.dataframe(df_auto, use_container_width=True, hide_index=True)

    if tipo_processamento == "Cadastro de produtos":
        modelo_cadastro_df = st.session_state["modelo_cadastro_raw"]

        if modelo_cadastro_df is None:
            st.warning("⚠️ Anexe o modelo de cadastro do Bling.")
        else:
            if st.button("Gerar planilha de cadastro", use_container_width=True):
                try:
                    saida = mapear_cadastro_no_modelo_bling(
                        df=df,
                        mapa=mapa_final,
                        colunas_imagem_extras=colunas_imagem_extras,
                        modelo_df=modelo_cadastro_df,
                    )
                    erros, avisos = validar_saida_cadastro(saida, modelo_cadastro_df)

                    for aviso in avisos:
                        st.warning(aviso)
                        log(f"Aviso: {aviso}")

                    if erros:
                        for erro in erros:
                            st.error(erro)
                            log(f"Erro de validação: {erro}")
                    else:
                        st.session_state["df_saida"] = saida
                        log(f"Cadastro gerado no modelo Bling com {len(saida)} linhas.")
                        log(f"Modelo de cadastro usado: {st.session_state['nome_modelo_cadastro']}")
                        st.success("✅ Planilha de cadastro gerada no modelo real do Bling.")

                except Exception as e:
                    st.error(f"Erro ao gerar cadastro: {e}")
                    log(f"Erro ao gerar cadastro: {e}")

    else:
        modelo_estoque_df = st.session_state["modelo_estoque_raw"]

        if modelo_estoque_df is None:
            st.warning("⚠️ Anexe o modelo de estoque do Bling.")
        elif not limpar_texto(deposito):
            st.warning("⚠️ Digite em qual estoque será lançado.")
        else:
            if st.button("Gerar planilha de estoque", use_container_width=True):
                try:
                    saida = mapear_estoque_no_modelo_bling(
                        df=df,
                        mapa=mapa_final,
                        deposito=deposito,
                        modelo_df=modelo_estoque_df,
                    )
                    erros, avisos = validar_saida_estoque(saida, modelo_estoque_df)

                    for aviso in avisos:
                        st.warning(aviso)
                        log(f"Aviso: {aviso}")

                    if erros:
                        for erro in erros:
                            st.error(erro)
                            log(f"Erro de validação: {erro}")
                    else:
                        st.session_state["df_saida"] = saida
                        log(f"Estoque gerado no modelo Bling com {len(saida)} linhas.")
                        log(f"Modelo de estoque usado: {st.session_state['nome_modelo_estoque']}")
                        log(f"Depósito informado: {deposito}")
                        st.success("✅ Planilha de estoque gerada no modelo real do Bling.")

                except Exception as e:
                    st.error(f"Erro ao gerar estoque: {e}")
                    log(f"Erro ao gerar estoque: {e}")

    df_saida = st.session_state["df_saida"]

    if df_saida is not None:
        nome_saida = (
            "bling_cadastro_produtos_modelo_real.xlsx"
            if tipo_processamento == "Cadastro de produtos"
            else "bling_atualizacao_estoque_modelo_real.xlsx"
        )

        arquivo_excel = salvar_excel_bytes(df_saida)

        st.download_button(
            "📥 Baixar planilha final",
            data=arquivo_excel,
            file_name=nome_saida,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    st.divider()

    with st.expander("📄 Logs", expanded=False):
        logs_txt = "\n".join(st.session_state["logs"]) if st.session_state["logs"] else "Nenhum log gerado."
        st.text_area("Log de processamento", value=logs_txt, height=250)
        st.download_button(
            "⬇️ Baixar log",
            data=salvar_txt_bytes(logs_txt),
            file_name="log_processamento.txt",
            mime="text/plain",
            use_container_width=True,
        )


if __name__ == "__main__":
    main()
