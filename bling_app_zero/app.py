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
        "nome_arquivo": "",
        "mapa_manual": {},
        "ultimo_tipo_processamento": "Cadastro de produtos",
        "preview_aberto": False,
        "ajuste_manual_aberto": True,
        "mapeamento_final_aberto": True,
        "colunas_auto_aberto": False,
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
    st.session_state["nome_arquivo"] = ""
    st.session_state["mapa_manual"] = {}
    st.session_state["ultimo_tipo_processamento"] = "Cadastro de produtos"
    st.session_state["preview_aberto"] = False
    st.session_state["ajuste_manual_aberto"] = True
    st.session_state["mapeamento_final_aberto"] = True
    st.session_state["colunas_auto_aberto"] = False


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


def limpar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
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


# =========================================================
# LEITURA DE ARQUIVO
# =========================================================
def ler_planilha(arquivo) -> pd.DataFrame:
    nome = arquivo.name.lower()

    if nome.endswith(".csv"):
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
                df = limpar_dataframe(df)
                if len(df.columns) > 0:
                    return df
            except Exception as e:
                ultimo_erro = e

        raise ValueError(f"Erro ao ler CSV: {ultimo_erro}")

    arquivo.seek(0)
    try:
        df = pd.read_excel(arquivo, dtype=str)
        return limpar_dataframe(df)
    except Exception as e:
        raise ValueError(f"Erro ao ler planilha Excel: {e}")


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
        ["nome", "produto", "titulo", "título", "nome produto", "descricao"]
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
            "imagem", "imagem 1", "url imagem", "url da imagem", "foto",
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
    Regra fixa do usuário:
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
# VALIDAÇÃO
# =========================================================
def validar_saida_cadastro(df_saida: pd.DataFrame) -> Tuple[List[str], List[str]]:
    erros = []
    avisos = []

    if df_saida.empty:
        erros.append("A planilha final de cadastro ficou vazia.")
        return erros, avisos

    obrigatorias = ["codigo", "nome", "descricao curta"]
    for col in obrigatorias:
        if col not in df_saida.columns:
            erros.append(f"Coluna obrigatória ausente na saída: {col}")

    if "codigo" in df_saida.columns:
        vazios = int((df_saida["codigo"].astype(str).str.strip() == "").sum())
        if vazios > 0:
            erros.append(f"Existem {vazios} linhas sem código.")

    if "nome" in df_saida.columns:
        vazios = int((df_saida["nome"].astype(str).str.strip() == "").sum())
        if vazios > 0:
            erros.append(f"Existem {vazios} linhas sem nome.")

    if "descricao curta" in df_saida.columns:
        vazios = int((df_saida["descricao curta"].astype(str).str.strip() == "").sum())
        if vazios > 0:
            avisos.append(f"Existem {vazios} linhas sem descrição curta.")

    for col in ["imagem 1", "imagem 2", "imagem 3", "imagem 4", "imagem 5"]:
        if col in df_saida.columns:
            invalidas = df_saida[col].astype(str).apply(
                lambda x: bool(x.strip()) and not re.match(r"^https?://", x.strip(), flags=re.IGNORECASE)
            ).sum()
            if invalidas > 0:
                erros.append(f"A coluna {col} possui {int(invalidas)} valores que não são URL.")

    return erros, avisos


def validar_saida_estoque(df_saida: pd.DataFrame) -> Tuple[List[str], List[str]]:
    erros = []
    avisos = []

    if df_saida.empty:
        erros.append("A planilha final de estoque ficou vazia.")
        return erros, avisos

    obrigatorias = ["codigo", "deposito", "estoque"]
    for col in obrigatorias:
        if col not in df_saida.columns:
            erros.append(f"Coluna obrigatória ausente na saída: {col}")

    if "codigo" in df_saida.columns:
        vazios = int((df_saida["codigo"].astype(str).str.strip() == "").sum())
        if vazios > 0:
            erros.append(f"Existem {vazios} linhas sem código.")

    if "deposito" in df_saida.columns:
        vazios = int((df_saida["deposito"].astype(str).str.strip() == "").sum())
        if vazios > 0:
            erros.append("O depósito ficou vazio em uma ou mais linhas.")

    if "estoque" in df_saida.columns:
        negativos = int((pd.to_numeric(df_saida["estoque"], errors="coerce").fillna(0) < 0).sum())
        if negativos > 0:
            avisos.append(f"Existem {negativos} linhas com estoque negativo.")

    return erros, avisos


# =========================================================
# MAPEAMENTO BLING
# =========================================================
def mapear_cadastro_bling(
    df: pd.DataFrame,
    mapa: Dict[str, Optional[str]],
    colunas_imagem_extras: List[str],
) -> pd.DataFrame:
    saida = pd.DataFrame(index=df.index)

    codigo_col = mapa.get("codigo")
    nome_col = mapa.get("nome")
    desc_col = mapa.get("descricao_curta")
    preco_col = mapa.get("preco")
    marca_col = mapa.get("marca")
    imagem_col = mapa.get("imagem")
    link_col = mapa.get("link_externo")
    situacao_col = mapa.get("situacao")
    unidade_col = mapa.get("unidade")

    saida["id"] = ""
    saida["codigo"] = df[codigo_col] if codigo_col and codigo_col in df.columns else ""
    saida["nome"] = df[nome_col] if nome_col and nome_col in df.columns else ""
    saida["unidade"] = df[unidade_col] if unidade_col and unidade_col in df.columns else "UN"
    saida["preco"] = df[preco_col] if preco_col and preco_col in df.columns else ""
    saida["situacao"] = df[situacao_col] if situacao_col and situacao_col in df.columns else "Ativo"
    saida["marca"] = df[marca_col] if marca_col and marca_col in df.columns else ""

    saida["descricao curta"] = df[desc_col] if desc_col and desc_col in df.columns else ""
    saida["descricao"] = ""
    saida["video"] = ""

    imagens_1 = []
    imagens_2 = []
    imagens_3 = []
    imagens_4 = []
    imagens_5 = []

    for _, row in df.iterrows():
        urls = extrair_imagens_da_linha(row, imagem_col, colunas_imagem_extras)
        imagens_1.append(urls[0] if len(urls) > 0 else "")
        imagens_2.append(urls[1] if len(urls) > 1 else "")
        imagens_3.append(urls[2] if len(urls) > 2 else "")
        imagens_4.append(urls[3] if len(urls) > 3 else "")
        imagens_5.append(urls[4] if len(urls) > 4 else "")

    saida["imagem 1"] = imagens_1
    saida["imagem 2"] = imagens_2
    saida["imagem 3"] = imagens_3
    saida["imagem 4"] = imagens_4
    saida["imagem 5"] = imagens_5

    if link_col and link_col in df.columns:
        saida["link externo"] = df[link_col].apply(limpar_link_externo)
    else:
        saida["link externo"] = ""

    for col in saida.columns:
        if col == "preco":
            continue
        saida[col] = saida[col].apply(limpar_texto)

    saida["preco"] = saida["preco"].apply(corrigir_preco)
    saida["situacao"] = saida["situacao"].apply(normalizar_situacao)
    saida["unidade"] = saida["unidade"].replace("", "UN")

    vazia = saida["descricao curta"].astype(str).str.strip() == ""
    saida.loc[vazia, "descricao curta"] = saida.loc[vazia, "nome"]

    antes = len(saida)
    saida = saida[saida["codigo"].astype(str).str.strip() != ""].copy()
    removidas_sem_codigo = antes - len(saida)
    if removidas_sem_codigo > 0:
        log(f"Cadastro: removidas {removidas_sem_codigo} linhas sem código.")

    antes_dup = len(saida)
    saida = saida.drop_duplicates(subset=["codigo"], keep="first").reset_index(drop=True)
    removidas_duplicadas = antes_dup - len(saida)
    if removidas_duplicadas > 0:
        log(f"Cadastro: removidas {removidas_duplicadas} linhas com código duplicado.")

    for col in ["imagem 1", "imagem 2", "imagem 3", "imagem 4", "imagem 5"]:
        limpas = saida[col].astype(str).apply(
            lambda x: x if (not x.strip() or re.match(r"^https?://", x.strip(), flags=re.IGNORECASE)) else ""
        )
        saida[col] = limpas

    return saida


def mapear_estoque_bling(
    df: pd.DataFrame,
    mapa: Dict[str, Optional[str]],
    deposito: str,
) -> pd.DataFrame:
    saida = pd.DataFrame(index=df.index)

    codigo_col = mapa.get("codigo")
    estoque_col = mapa.get("estoque")
    nome_col = mapa.get("nome")

    saida["codigo"] = df[codigo_col] if codigo_col and codigo_col in df.columns else ""
    saida["nome"] = df[nome_col] if nome_col and nome_col in df.columns else ""
    saida["deposito"] = limpar_texto(deposito)
    saida["estoque"] = df[estoque_col] if estoque_col and estoque_col in df.columns else 0

    saida["codigo"] = saida["codigo"].apply(limpar_texto)
    saida["nome"] = saida["nome"].apply(limpar_texto)
    saida["deposito"] = saida["deposito"].apply(limpar_texto)
    saida["estoque"] = saida["estoque"].apply(corrigir_estoque)

    antes = len(saida)
    saida = saida[saida["codigo"].astype(str).str.strip() != ""].copy()
    removidas_sem_codigo = antes - len(saida)
    if removidas_sem_codigo > 0:
        log(f"Estoque: removidas {removidas_sem_codigo} linhas sem código.")

    antes_dup = len(saida)
    saida = saida.drop_duplicates(subset=["codigo"], keep="first").reset_index(drop=True)
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
            "situacao",
            "unidade",
        ]
    else:
        ordem = [
            "codigo",
            "nome",
            "estoque",
        ]

    linhas = []
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

    st.subheader("Envio da planilha")
    arquivo = st.file_uploader(
        "Selecione sua planilha",
        type=["xlsx", "xls", "csv"],
    )

    if arquivo is not None:
        try:
            df = ler_planilha(arquivo)
            st.session_state["df_origem"] = df
            st.session_state["nome_arquivo"] = arquivo.name
            st.session_state["df_saida"] = None
            log(f"Arquivo carregado: {arquivo.name}")
            log(f"Linhas: {len(df)} | Colunas: {len(df.columns)}")
        except Exception as e:
            st.error(f"Erro ao ler arquivo: {e}")
            log(f"Erro ao ler arquivo: {e}")
            return

    df = st.session_state["df_origem"]

    if df is None:
        return

    st.success(f"✅ Arquivo carregado: {st.session_state['nome_arquivo']}")

    c1, c2 = st.columns(2)
    with c1:
        st.metric("Linhas", len(df))
    with c2:
        st.metric("Colunas", len(df.columns))

    mapa_auto = detectar_colunas(df)
    colunas_imagem_auto = encontrar_colunas_imagem(df)
    log(f"Mapeamento automático: {mapa_auto}")
    log(f"Colunas de imagem detectadas: {colunas_imagem_auto}")

    with st.expander("👀 Preview", expanded=st.session_state["preview_aberto"]):
        st.dataframe(df.head(1), use_container_width=True)

    with st.expander("🛠️ Ajuste manual das colunas", expanded=st.session_state["ajuste_manual_aberto"]):
        st.caption("Se alguma coluna foi identificada errado, ajuste aqui manualmente.")
        mapa_final_temp = construir_mapa_manual(df, mapa_auto)
        st.session_state["mapa_manual"] = mapa_final_temp

        st.info(
            "Regra fixa do sistema: a descrição da planilha de dados sempre vai para "
            "'descricao curta'. A coluna 'descricao' fica vazia. A coluna 'video' também fica vazia."
        )

    mapa_final = st.session_state.get("mapa_manual") or mapa_auto
    imagem_principal = mapa_final.get("imagem")
    colunas_imagem_extras = [c for c in colunas_imagem_auto if c != imagem_principal]

    with st.expander("✅ Mapeamento final que será usado", expanded=st.session_state["mapeamento_final_aberto"]):
        df_mapeamento_final = montar_df_mapeamento_final(
            tipo_processamento=tipo_processamento,
            mapa_final=mapa_final,
            imagem_principal=imagem_principal,
            colunas_imagem_extras=colunas_imagem_extras,
        )
        st.dataframe(df_mapeamento_final, use_container_width=True, hide_index=True)

        if st.session_state["df_saida"] is not None:
            st.dataframe(st.session_state["df_saida"].head(20), use_container_width=True)

    with st.expander("🔎 Colunas identificadas automaticamente", expanded=st.session_state["colunas_auto_aberto"]):
        df_auto = montar_df_colunas_automaticas(mapa_auto, colunas_imagem_auto)
        st.dataframe(df_auto, use_container_width=True, hide_index=True)

    if tipo_processamento == "Cadastro de produtos":
        if st.button("Gerar planilha de cadastro", use_container_width=True):
            try:
                saida = mapear_cadastro_bling(df, mapa_final, colunas_imagem_extras)
                erros, avisos = validar_saida_cadastro(saida)

                for aviso in avisos:
                    st.warning(aviso)
                    log(f"Aviso: {aviso}")

                if erros:
                    for erro in erros:
                        st.error(erro)
                        log(f"Erro de validação: {erro}")
                else:
                    st.session_state["df_saida"] = saida
                    log(f"Cadastro gerado com {len(saida)} linhas.")
                    st.success("✅ Planilha de cadastro gerada com sucesso.")

            except Exception as e:
                st.error(f"Erro ao gerar cadastro: {e}")
                log(f"Erro ao gerar cadastro: {e}")

    else:
        if not limpar_texto(deposito):
            st.warning("⚠️ Digite em qual estoque será lançado.")
        else:
            if st.button("Gerar planilha de estoque", use_container_width=True):
                try:
                    saida = mapear_estoque_bling(df, mapa_final, deposito)
                    erros, avisos = validar_saida_estoque(saida)

                    for aviso in avisos:
                        st.warning(aviso)
                        log(f"Aviso: {aviso}")

                    if erros:
                        for erro in erros:
                            st.error(erro)
                            log(f"Erro de validação: {erro}")
                    else:
                        st.session_state["df_saida"] = saida
                        log(f"Estoque gerado com {len(saida)} linhas. Depósito: {deposito}")
                        st.success("✅ Planilha de estoque gerada com sucesso.")

                except Exception as e:
                    st.error(f"Erro ao gerar estoque: {e}")
                    log(f"Erro ao gerar estoque: {e}")

    df_saida = st.session_state["df_saida"]

    if df_saida is not None:
        nome_saida = (
            "bling_cadastro_produtos.xlsx"
            if tipo_processamento == "Cadastro de produtos"
            else "bling_atualizacao_estoque.xlsx"
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
