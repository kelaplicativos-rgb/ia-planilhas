import os
import time
import traceback
import pandas as pd
import streamlit as st

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="IA Planilhas Bling PRO", layout="wide")
st.title("🔥 IA Planilhas Bling PRO")

# =========================
# ESTADO
# =========================
if "stop_process" not in st.session_state:
    st.session_state.stop_process = False

if "logs_execucao" not in st.session_state:
    st.session_state.logs_execucao = []


def log(msg: str) -> None:
    st.session_state.logs_execucao.append(msg)


def resetar_logs() -> None:
    st.session_state.logs_execucao = []


def parar_processamento() -> None:
    st.session_state.stop_process = True


def iniciar_processamento() -> None:
    st.session_state.stop_process = False
    resetar_logs()


# =========================
# MODELO BLING
# =========================
@st.cache_data
def carregar_modelo_bling() -> pd.DataFrame:
    caminho = "modelos/modelo_produtos.csv"
    if not os.path.exists(caminho):
        raise FileNotFoundError("Arquivo modelos/modelo_produtos.csv não encontrado.")
    return pd.read_csv(caminho)


# =========================
# LEITURA ROBUSTA
# =========================
def ler_csv_seguro(arquivo) -> pd.DataFrame:
    tentativas = [
        {"sep": None, "engine": "python", "encoding": "utf-8", "on_bad_lines": "skip"},
        {"sep": ";", "engine": "python", "encoding": "utf-8", "on_bad_lines": "skip"},
        {"sep": ";", "engine": "python", "encoding": "latin1", "on_bad_lines": "skip"},
        {"sep": ",", "engine": "python", "encoding": "latin1", "on_bad_lines": "skip"},
    ]

    ultimo_erro = None
    for kwargs in tentativas:
        try:
            arquivo.seek(0)
            df = pd.read_csv(arquivo, **kwargs)
            if len(df.columns) > 0:
                return df
        except Exception as e:
            ultimo_erro = e

    raise ultimo_erro


def ler_arquivo(arquivo) -> pd.DataFrame:
    nome = arquivo.name.lower()

    if nome.endswith(".csv"):
        return ler_csv_seguro(arquivo)

    if nome.endswith(".xlsx") or nome.endswith(".xls"):
        return pd.read_excel(arquivo)

    raise ValueError("Formato não suportado. Envie CSV, XLSX ou XLS.")


# =========================
# NORMALIZAÇÃO
# =========================
def normalizar_nome_coluna(coluna: str) -> str:
    return (
        str(coluna)
        .strip()
        .lower()
        .replace("ç", "c")
        .replace("ã", "a")
        .replace("á", "a")
        .replace("à", "a")
        .replace("â", "a")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ô", "o")
        .replace("õ", "o")
        .replace("ú", "u")
        .replace(" ", "_")
    )


def detectar_colunas(df: pd.DataFrame) -> dict:
    mapa = {}

    for col in df.columns:
        nome = normalizar_nome_coluna(col)

        if any(x in nome for x in ["nome", "produto", "titulo", "title"]):
            mapa.setdefault("nome", col)

        elif any(x in nome for x in ["sku", "codigo", "cod", "referencia", "ref"]):
            mapa.setdefault("codigo", col)

        elif any(x in nome for x in ["preco", "valor", "price"]):
            mapa.setdefault("preco", col)

        elif any(x in nome for x in ["estoque", "quantidade", "saldo", "qtd", "stock"]):
            mapa.setdefault("estoque", col)

        elif any(x in nome for x in ["marca", "brand", "fabricante"]):
            mapa.setdefault("marca", col)

        elif any(x in nome for x in ["categoria", "departamento", "category"]):
            mapa.setdefault("categoria", col)

        elif any(x in nome for x in ["descricao", "descrição", "desc"]):
            mapa.setdefault("descricao_curta", col)

        elif any(x in nome for x in ["gtin", "ean", "barra", "codigo_de_barras", "codigo_barras"]):
            mapa.setdefault("gtin", col)

    return mapa


# =========================
# HELPERS
# =========================
def valor_linha(row: pd.Series, coluna: str):
    if not coluna:
        return ""
    try:
        valor = row.get(coluna, "")
        if pd.isna(valor):
            return ""
        return valor
    except Exception:
        return ""


def normalizar_preco(valor):
    valor = str(valor).strip()
    if valor == "":
        return ""
    valor = valor.replace(".", "").replace(",", ".")
    valor = "".join(ch for ch in valor if ch.isdigit() or ch == ".")
    try:
        return float(valor)
    except Exception:
        return ""


def normalizar_estoque(valor):
    valor = str(valor).strip().replace(",", ".")
    valor = "".join(ch for ch in valor if ch.isdigit() or ch in [".", "-"])
    try:
        return float(valor)
    except Exception:
        return ""


# =========================
# MONTAR PLANILHA FINAL
# =========================
def montar_bling(df_origem: pd.DataFrame, modelo_bling: pd.DataFrame) -> pd.DataFrame:
    mapa = detectar_colunas(df_origem)
    log(f"Mapa detectado: {mapa}")

    colunas_modelo = list(modelo_bling.columns)
    resultado = []

    total = len(df_origem)
    progresso = st.progress(0)
    status = st.empty()
    inicio = time.time()

    for idx, (_, row) in enumerate(df_origem.iterrows(), start=1):
        if st.session_state.stop_process:
            log("Processamento interrompido pelo usuário.")
            st.warning("⛔ Processamento interrompido.")
            break

        nome = valor_linha(row, mapa.get("nome", ""))
        codigo = valor_linha(row, mapa.get("codigo", ""))
        preco = normalizar_preco(valor_linha(row, mapa.get("preco", "")))
        estoque = normalizar_estoque(valor_linha(row, mapa.get("estoque", "")))
        marca = valor_linha(row, mapa.get("marca", ""))
        categoria = valor_linha(row, mapa.get("categoria", ""))
        descricao_curta = valor_linha(row, mapa.get("descricao_curta", ""))
        gtin = valor_linha(row, mapa.get("gtin", ""))

        nova_linha = {col: "" for col in colunas_modelo}

        for col in colunas_modelo:
            col_lower = normalizar_nome_coluna(col)

            if col_lower == "nome":
                nova_linha[col] = nome

            elif col_lower == "codigo":
                nova_linha[col] = codigo

            elif col_lower == "preco":
                nova_linha[col] = preco

            elif col_lower == "estoque":
                nova_linha[col] = estoque

            elif col_lower == "marca":
                nova_linha[col] = marca

            elif col_lower == "categoria":
                nova_linha[col] = categoria

            elif col_lower == "descricao_curta":
                nova_linha[col] = descricao_curta

            elif col_lower == "gtin":
                nova_linha[col] = gtin

            elif col_lower == "situacao":
                nova_linha[col] = "Ativo"

            elif col_lower == "unidade":
                nova_linha[col] = "UN"

        resultado.append(nova_linha)

        pct = idx / total if total else 1
        progresso.progress(pct)

        decorrido = time.time() - inicio
        restante = (decorrido / idx) * (total - idx) if idx else 0
        status.text(f"Processando {idx}/{total} | ⏱ {int(restante)}s restantes")

    return pd.DataFrame(resultado)


# =========================
# UI
# =========================
col1, col2 = st.columns(2)

with col1:
    st.button("▶️ Iniciar novo processamento", on_click=iniciar_processamento)

with col2:
    st.button("🛑 Parar processamento", on_click=parar_processamento)

arquivo = st.file_uploader("📂 Envie sua planilha", type=["csv", "xlsx", "xls"])

if arquivo is not None:
    try:
        iniciar_processamento()

        log(f"Arquivo recebido: {arquivo.name}")

        modelo = carregar_modelo_bling()
        log(f"Modelo carregado com {len(modelo.columns)} coluna(s).")

        df = ler_arquivo(arquivo)
        log(f"Planilha carregada com {len(df)} linha(s) e {len(df.columns)} coluna(s).")

        st.success("✅ Arquivo carregado")
        st.subheader("Prévia da planilha recebida")
        st.dataframe(df.head())

        df_final = montar_bling(df, modelo)

        if not df_final.empty:
            st.success("✅ Planilha pronta para o Bling")
            st.subheader("Prévia da planilha final")
            st.dataframe(df_final.head())

            st.download_button(
                "⬇️ Baixar planilha Bling",
                data=df_final.to_csv(index=False).encode("utf-8"),
                file_name="bling_import.csv",
                mime="text/csv",
            )

    except Exception:
        erro = traceback.format_exc()
        st.error("❌ Erro detectado")
        st.code(erro)
        log(erro)

if st.session_state.logs_execucao:
    st.subheader("Logs")
    st.code("\n".join(st.session_state.logs_execucao))
