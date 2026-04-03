import io
import re
import unicodedata

import pandas as pd
import streamlit as st


# =========================================================
# CONFIG
# =========================================================
st.set_page_config(page_title="🔥 Bling Automação PRO", layout="wide")


# =========================================================
# ESTADO
# =========================================================
def init_state():
    defaults = {
        "logs": [],
        "df_origem": None,
        "df_saida": None,
        "nome_arquivo": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def log(msg: str):
    st.session_state.logs.append(str(msg))


def limpar_tudo():
    st.session_state["logs"] = []
    st.session_state["df_origem"] = None
    st.session_state["df_saida"] = None
    st.session_state["nome_arquivo"] = ""


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
            {"sep": None, "engine": "python", "encoding": "latin-1"},
            {"sep": ";", "engine": "python", "encoding": "latin-1"},
            {"sep": ",", "engine": "python", "encoding": "latin-1"},
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
                return limpar_dataframe(df)
            except Exception as e:
                ultimo_erro = e

        raise ValueError(f"Erro ao ler CSV: {ultimo_erro}")

    arquivo.seek(0)
    df = pd.read_excel(arquivo, dtype=str)
    return limpar_dataframe(df)


# =========================================================
# EXPORTAÇÃO
# =========================================================
def salvar_excel_bytes(df: pd.DataFrame, nome_aba="Dados") -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=nome_aba)
    buffer.seek(0)
    return buffer.getvalue()


def salvar_txt_bytes(texto: str) -> bytes:
    return texto.encode("utf-8")


# =========================================================
# LOCALIZAR COLUNAS
# =========================================================
def encontrar_coluna(df: pd.DataFrame, candidatos: list[str]) -> str | None:
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


def detectar_colunas(df: pd.DataFrame) -> dict:
    m = {}

    m["codigo"] = encontrar_coluna(
        df,
        [
            "codigo", "código", "sku", "ref", "referencia", "referência",
            "cod produto", "codigo produto", "id produto", "part number"
        ],
    )

    m["nome"] = encontrar_coluna(
        df,
        [
            "nome", "produto", "titulo", "título",
            "nome produto"
        ],
    )

    m["descricao_curta"] = encontrar_coluna(
        df,
        [
            "descricao curta", "descrição curta",
            "descricao", "descrição",
            "detalhes", "resumo", "informacoes", "informações",
            "descricao produto", "descrição produto"
        ],
    )

    m["preco"] = encontrar_coluna(
        df,
        [
            "preco", "preço", "valor", "valor venda", "preco venda",
            "preço venda", "preco final"
        ],
    )

    m["marca"] = encontrar_coluna(
        df,
        ["marca", "fabricante", "brand"],
    )

    m["imagem"] = encontrar_coluna(
        df,
        [
            "imagem", "imagem 1", "url imagem", "url da imagem",
            "foto", "link imagem", "url imagens externas"
        ],
    )

    m["link_externo"] = encontrar_coluna(
        df,
        [
            "link externo", "url produto", "link produto", "produto url",
            "link", "url"
        ],
    )

    m["estoque"] = encontrar_coluna(
        df,
        [
            "estoque", "saldo", "qtd", "quantidade", "quantidade estoque",
            "saldo atual", "balanco", "balanço"
        ],
    )

    m["situacao"] = encontrar_coluna(
        df,
        ["situacao", "situação", "status", "ativo"],
    )

    m["unidade"] = encontrar_coluna(
        df,
        ["unidade", "und", "un"],
    )

    return m


# =========================================================
# AJUSTES DE DADOS
# =========================================================
def corrigir_preco(valor) -> str:
    texto = limpar_texto(valor)

    if not texto:
        return ""

    texto = texto.replace("R$", "").replace("r$", "").strip()

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

    texto = texto.replace(".", "").replace(",", ".")
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


# =========================================================
# MAPEAMENTO BLING
# =========================================================
def mapear_cadastro_bling(df: pd.DataFrame, mapa: dict) -> pd.DataFrame:
    saida = pd.DataFrame()

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
    saida["codigo"] = df[codigo_col] if codigo_col else ""
    saida["nome"] = df[nome_col] if nome_col else ""
    saida["unidade"] = df[unidade_col] if unidade_col else "UN"
    saida["preco"] = df[preco_col] if preco_col else ""
    saida["situacao"] = df[situacao_col] if situacao_col else "Ativo"
    saida["marca"] = df[marca_col] if marca_col else ""
    saida["descricao curta"] = df[desc_col] if desc_col else ""
    saida["descricao"] = ""
    saida["video"] = ""
    saida["imagem 1"] = df[imagem_col] if imagem_col else ""
    saida["imagem 2"] = ""
    saida["imagem 3"] = ""
    saida["imagem 4"] = ""
    saida["imagem 5"] = ""
    saida["link externo"] = df[link_col] if link_col else ""

    for col in saida.columns:
        if col == "preco":
            continue
        saida[col] = saida[col].apply(limpar_texto)

    saida["preco"] = saida["preco"].apply(corrigir_preco)
    saida["situacao"] = saida["situacao"].apply(normalizar_situacao)
    saida["unidade"] = saida["unidade"].replace("", "UN")

    # regra: descrição da planilha sempre vai para descrição curta
    vazia = saida["descricao curta"].astype(str).str.strip() == ""
    saida.loc[vazia, "descricao curta"] = saida.loc[vazia, "nome"]

    # se codigo vier vazio, usa nome como fallback temporário
    codigo_vazio = saida["codigo"].astype(str).str.strip() == ""
    saida.loc[codigo_vazio, "codigo"] = saida.loc[codigo_vazio, "nome"]

    saida = saida[saida["codigo"].astype(str).str.strip() != ""].copy()
    saida = saida.drop_duplicates(subset=["codigo"], keep="first").reset_index(drop=True)

    return saida


def mapear_estoque_bling(df: pd.DataFrame, mapa: dict, deposito: str) -> pd.DataFrame:
    saida = pd.DataFrame()

    codigo_col = mapa.get("codigo")
    estoque_col = mapa.get("estoque")
    nome_col = mapa.get("nome")

    saida["codigo"] = df[codigo_col] if codigo_col else ""
    saida["nome"] = df[nome_col] if nome_col else ""
    saida["deposito"] = limpar_texto(deposito)
    saida["estoque"] = df[estoque_col] if estoque_col else 0

    saida["codigo"] = saida["codigo"].apply(limpar_texto)
    saida["nome"] = saida["nome"].apply(limpar_texto)
    saida["deposito"] = saida["deposito"].apply(limpar_texto)
    saida["estoque"] = saida["estoque"].apply(corrigir_estoque)

    codigo_vazio = saida["codigo"].astype(str).str.strip() == ""
    saida.loc[codigo_vazio, "codigo"] = saida.loc[codigo_vazio, "nome"]

    saida = saida[saida["codigo"].astype(str).str.strip() != ""].copy()
    saida = saida.drop_duplicates(subset=["codigo"], keep="first").reset_index(drop=True)

    return saida


# =========================================================
# APP
# =========================================================
def main():
    init_state()

    st.title("🔥 Bling Automação PRO")
    st.subheader("🧠 Leitura automática para vários fornecedores")

    with st.sidebar:
        st.header("⚙️ Configurações")

        tipo_processamento = st.radio(
            "Tipo de saída",
            ["Cadastro de produtos", "Atualização de estoque"],
            index=0,
        )

        deposito = ""
        if tipo_processamento == "Atualização de estoque":
            deposito = st.text_input(
                "Em qual estoque será lançado?",
                placeholder="Ex: Geral, Loja, CD",
            )

        st.divider()

        if st.button("🧹 Limpar tudo", use_container_width=True):
            limpar_tudo()
            st.rerun()

    st.subheader("📤 Envio da planilha")

    arquivo = st.file_uploader(
        "Selecione sua planilha",
        type=["xlsx", "xls", "csv"],
    )

    if arquivo is not None:
        try:
            df = ler_planilha(arquivo)
            st.session_state["df_origem"] = df
            st.session_state["nome_arquivo"] = arquivo.name
            log(f"Arquivo carregado: {arquivo.name}")
            log(f"Linhas: {len(df)} | Colunas: {len(df.columns)}")
        except Exception as e:
            st.error(f"Erro ao ler arquivo: {e}")
            log(f"Erro ao ler arquivo: {e}")
            return

    df = st.session_state["df_origem"]

    if df is not None:
        st.success(f"✅ Arquivo carregado: {st.session_state['nome_arquivo']}")

        c1, c2 = st.columns(2)
        with c1:
            st.metric("Linhas", len(df))
        with c2:
            st.metric("Colunas", len(df.columns))

        with st.expander("👀 Preview", expanded=False):
            st.dataframe(df.head(1), use_container_width=True)

        mapa = detectar_colunas(df)
        log(f"Mapeamento automático: {mapa}")

        with st.expander("🔎 Colunas identificadas automaticamente", expanded=False):
            st.json(mapa)

        with st.expander("🛠️ Ajuste manual das colunas", expanded=False):
            st.info("Nesta fase estamos usando o mapeamento automático estável.")

        if tipo_processamento == "Cadastro de produtos":
            if st.button("🚀 Gerar planilha de cadastro", use_container_width=True):
                try:
                    saida = mapear_cadastro_bling(df, mapa)
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
                if st.button("🚀 Gerar planilha de estoque", use_container_width=True):
                    try:
                        saida = mapear_estoque_bling(df, mapa, deposito)
                        st.session_state["df_saida"] = saida
                        log(f"Estoque gerado com {len(saida)} linhas. Depósito: {deposito}")
                        st.success("✅ Planilha de estoque gerada com sucesso.")
                    except Exception as e:
                        st.error(f"Erro ao gerar estoque: {e}")
                        log(f"Erro ao gerar estoque: {e}")

    df_saida = st.session_state["df_saida"]

    if df_saida is not None:
        with st.expander("✅ Mapeamento final que será usado", expanded=False):
            st.dataframe(df_saida.head(20), use_container_width=True)

        nome_saida = "bling_saida.xlsx"
        if tipo_processamento == "Cadastro de produtos":
            nome_saida = "bling_cadastro_produtos.xlsx"
        else:
            nome_saida = "bling_atualizacao_estoque.xlsx"

        arquivo_excel = salvar_excel_bytes(df_saida)
        st.download_button(
            "📦 Baixar planilha final",
            data=arquivo_excel,
            file_name=nome_saida,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    st.divider()

    with st.expander("🧾 Logs", expanded=False):
        logs_txt = "\n".join(st.session_state["logs"]) if st.session_state["logs"] else "Nenhum log gerado."
        st.text_area("Log de processamento", value=logs_txt, height=250)

        st.download_button(
            "📥 Baixar log",
            data=salvar_txt_bytes(logs_txt),
            file_name="log_processamento.txt",
            mime="text/plain",
            use_container_width=True,
        )


if __name__ == "__main__":
    main()
