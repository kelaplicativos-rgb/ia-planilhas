import streamlit as st
import pandas as pd
import zipfile
import io
import os
from datetime import datetime

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="📦 Modo Final Completo", layout="wide")
st.title("📦 Upload Final Completo - Estoque + Cadastro")

# =========================
# SESSION STATE
# =========================
if "df_estoque" not in st.session_state:
    st.session_state["df_estoque"] = None

if "df_cadastro" not in st.session_state:
    st.session_state["df_cadastro"] = None

if "nome_estoque" not in st.session_state:
    st.session_state["nome_estoque"] = None

if "nome_cadastro" not in st.session_state:
    st.session_state["nome_cadastro"] = None

if "logs_processamento" not in st.session_state:
    st.session_state["logs_processamento"] = []

# =========================
# FUNÇÕES
# =========================
def adicionar_log(texto):
    horario = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    st.session_state["logs_processamento"].append(f"[{horario}] {texto}")

def limpar_estado():
    st.session_state["df_estoque"] = None
    st.session_state["df_cadastro"] = None
    st.session_state["nome_estoque"] = None
    st.session_state["nome_cadastro"] = None
    st.session_state["logs_processamento"] = []

def ler_planilha_bytes(nome_arquivo, dados_bytes):
    ext = os.path.splitext(nome_arquivo.lower())[1]

    if ext == ".csv":
        try:
            return pd.read_csv(
                io.BytesIO(dados_bytes),
                sep=None,
                engine="python",
                encoding="utf-8",
                on_bad_lines="skip"
            )
        except:
            return pd.read_csv(
                io.BytesIO(dados_bytes),
                sep=None,
                engine="python",
                encoding="latin-1",
                on_bad_lines="skip"
            )

    elif ext in [".xlsx", ".xls"]:
        return pd.read_excel(io.BytesIO(dados_bytes))

    else:
        raise ValueError(f"Formato não suportado: {nome_arquivo}")

def ler_planilha_upload(arquivo):
    nome = arquivo.name.lower()

    if nome.endswith(".csv"):
        try:
            return pd.read_csv(
                arquivo,
                sep=None,
                engine="python",
                encoding="utf-8",
                on_bad_lines="skip"
            )
        except:
            arquivo.seek(0)
            return pd.read_csv(
                arquivo,
                sep=None,
                engine="python",
                encoding="latin-1",
                on_bad_lines="skip"
            )

    elif nome.endswith((".xlsx", ".xls")):
        arquivo.seek(0)
        return pd.read_excel(arquivo)

    else:
        raise ValueError(f"Formato não suportado: {arquivo.name}")

def identificar_por_nome(nome):
    nome = nome.lower()

    if "estoque" in nome:
        return "estoque"

    if "cadastro" in nome:
        return "cadastro"

    return None

def identificar_por_colunas(df):
    colunas = [str(c).strip().lower() for c in df.columns]

    colunas_estoque = [
        "estoque", "saldo", "quantidade", "qtde", "qtd",
        "estoque atual", "saldo estoque", "estoque fisico"
    ]

    colunas_cadastro = [
        "descricao", "descrição", "nome", "produto", "marca", "sku",
        "descrição curta", "descricao curta", "preco", "preço",
        "categoria", "unidade", "codigo", "código"
    ]

    pontos_estoque = sum(1 for c in colunas if c in colunas_estoque)
    pontos_cadastro = sum(1 for c in colunas if c in colunas_cadastro)

    if pontos_estoque > pontos_cadastro and pontos_estoque > 0:
        return "estoque"

    if pontos_cadastro > pontos_estoque and pontos_cadastro > 0:
        return "cadastro"

    return None

def extrair_planilhas_do_zip(zip_file, progress_bar=None, status_text=None):
    arquivo_estoque = None
    arquivo_cadastro = None
    df_estoque = None
    df_cadastro = None
    logs = []

    with zipfile.ZipFile(zip_file, "r") as z:
        nomes_internos = z.namelist()

        planilhas_validas = [
            nome for nome in nomes_internos
            if not nome.endswith("/")
            and os.path.splitext(nome.lower())[1] in [".xlsx", ".xls", ".csv"]
        ]

        if not planilhas_validas:
            raise ValueError("Nenhuma planilha válida encontrada dentro do ZIP.")

        candidatos = []
        total = len(planilhas_validas)

        for i, nome in enumerate(planilhas_validas, start=1):
            if progress_bar is not None:
                progresso = int((i / total) * 100)
                progress_bar.progress(progresso)

            if status_text is not None:
                status_text.write(f"🔄 Lendo arquivo {i}/{total}: {nome}")

            try:
                dados = z.read(nome)
                df = ler_planilha_bytes(nome, dados)

                tipo_nome = identificar_por_nome(nome)
                tipo_coluna = identificar_por_colunas(df)

                candidatos.append({
                    "nome": nome,
                    "df": df,
                    "tipo_nome": tipo_nome,
                    "tipo_coluna": tipo_coluna
                })

                logs.append(f"✅ Lido: {nome} | nome={tipo_nome} | colunas={tipo_coluna}")

            except Exception as e:
                logs.append(f"❌ Erro ao ler {nome}: {e}")

        for item in candidatos:
            if item["tipo_nome"] == "estoque" and df_estoque is None:
                arquivo_estoque = item["nome"]
                df_estoque = item["df"]

            elif item["tipo_nome"] == "cadastro" and df_cadastro is None:
                arquivo_cadastro = item["nome"]
                df_cadastro = item["df"]

        for item in candidatos:
            if df_estoque is None and item["tipo_coluna"] == "estoque":
                arquivo_estoque = item["nome"]
                df_estoque = item["df"]

            elif df_cadastro is None and item["tipo_coluna"] == "cadastro":
                arquivo_cadastro = item["nome"]
                df_cadastro = item["df"]

    return {
        "arquivo_estoque": arquivo_estoque,
        "arquivo_cadastro": arquivo_cadastro,
        "df_estoque": df_estoque,
        "df_cadastro": df_cadastro,
        "logs": logs,
        "arquivos_encontrados": planilhas_validas
    }

def processar_uploads_soltos(arquivos, progress_bar=None, status_text=None):
    arquivo_estoque = None
    arquivo_cadastro = None
    df_estoque = None
    df_cadastro = None
    logs = []

    total = len(arquivos)

    for i, arquivo in enumerate(arquivos, start=1):
        if progress_bar is not None:
            progresso = int((i / total) * 100)
            progress_bar.progress(progresso)

        if status_text is not None:
            status_text.write(f"🔄 Lendo arquivo {i}/{total}: {arquivo.name}")

        try:
            df = ler_planilha_upload(arquivo)
            tipo_nome = identificar_por_nome(arquivo.name)
            tipo_coluna = identificar_por_colunas(df)

            logs.append(f"✅ Lido: {arquivo.name} | nome={tipo_nome} | colunas={tipo_coluna}")

            if tipo_nome == "estoque" and df_estoque is None:
                df_estoque = df
                arquivo_estoque = arquivo.name

            elif tipo_nome == "cadastro" and df_cadastro is None:
                df_cadastro = df
                arquivo_cadastro = arquivo.name

            elif tipo_nome is None:
                if tipo_coluna == "estoque" and df_estoque is None:
                    df_estoque = df
                    arquivo_estoque = arquivo.name

                elif tipo_coluna == "cadastro" and df_cadastro is None:
                    df_cadastro = df
                    arquivo_cadastro = arquivo.name

        except Exception as e:
            logs.append(f"❌ Erro ao ler {arquivo.name}: {e}")

    return {
        "arquivo_estoque": arquivo_estoque,
        "arquivo_cadastro": arquivo_cadastro,
        "df_estoque": df_estoque,
        "df_cadastro": df_cadastro,
        "logs": logs
    }

def dataframe_para_excel_bytes(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Dados")
    output.seek(0)
    return output.getvalue()

def dataframe_para_csv_bytes(df):
    csv_str = df.to_csv(index=False)
    return csv_str.encode("utf-8")

def gerar_zip_final(df_estoque, df_cadastro, logs, nome_estoque="estoque_processado.xlsx", nome_cadastro="cadastro_processado.xlsx"):
    memoria_zip = io.BytesIO()

    with zipfile.ZipFile(memoria_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        if df_estoque is not None:
            zf.writestr(nome_estoque, dataframe_para_excel_bytes(df_estoque))

        if df_cadastro is not None:
            zf.writestr(nome_cadastro, dataframe_para_excel_bytes(df_cadastro))

        log_texto = "\n".join(logs) if logs else "Sem logs."
        zf.writestr("log_processamento.txt", log_texto)

    memoria_zip.seek(0)
    return memoria_zip.getvalue()

# =========================
# BOTÃO LIMPAR
# =========================
col_a, col_b = st.columns([1, 1])

with col_a:
    if st.button("🗑️ Limpar arquivos carregados", use_container_width=True):
        limpar_estado()
        st.success("✅ Estado limpo com sucesso.")

with col_b:
    st.info("Você pode enviar 1 ZIP ou 2 planilhas soltas.")

# =========================
# MODO DE ENVIO
# =========================
modo_envio = st.radio(
    "📥 Escolha como deseja enviar os arquivos:",
    ["ZIP com as duas planilhas", "Duas planilhas soltas"],
    horizontal=True
)

progress_bar = st.progress(0)
status_text = st.empty()

# =========================
# MODO ZIP
# =========================
if modo_envio == "ZIP com as duas planilhas":
    zip_file = st.file_uploader(
        "📦 Envie um ZIP com Estoque + Cadastro",
        type=["zip"],
        key="zip_upload"
    )

    if zip_file is not None:
        try:
            limpar_estado()
            adicionar_log("Iniciando leitura do ZIP.")

            resultado = extrair_planilhas_do_zip(zip_file, progress_bar, status_text)

            for linha in resultado["logs"]:
                adicionar_log(linha)

            st.session_state["df_estoque"] = resultado["df_estoque"]
            st.session_state["df_cadastro"] = resultado["df_cadastro"]
            st.session_state["nome_estoque"] = resultado["arquivo_estoque"]
            st.session_state["nome_cadastro"] = resultado["arquivo_cadastro"]

            progress_bar.progress(100)
            status_text.write("✅ Processamento concluído.")

            st.subheader("📁 Arquivos encontrados no ZIP")
            for nome in resultado["arquivos_encontrados"]:
                st.write(f"- {nome}")

            if resultado["df_estoque"] is None or resultado["df_cadastro"] is None:
                st.error("⚠️ Não foi possível identificar as duas planilhas automaticamente.")
                st.info("Dica: use nomes como estoque.xlsx e cadastro.xlsx.")
            else:
                st.success("✅ Estoque e cadastro identificados com sucesso.")

        except Exception as e:
            st.error(f"Erro ao processar ZIP: {e}")
            adicionar_log(f"Erro ao processar ZIP: {e}")

# =========================
# MODO ARQUIVOS SOLTOS
# =========================
else:
    arquivos = st.file_uploader(
        "📂 Envie as duas planilhas juntas",
        type=["xlsx", "xls", "csv"],
        accept_multiple_files=True,
        key="arquivos_soltos"
    )

    if arquivos:
        try:
            limpar_estado()
            adicionar_log("Iniciando leitura de arquivos soltos.")

            resultado = processar_uploads_soltos(arquivos, progress_bar, status_text)

            for linha in resultado["logs"]:
                adicionar_log(linha)

            st.session_state["df_estoque"] = resultado["df_estoque"]
            st.session_state["df_cadastro"] = resultado["df_cadastro"]
            st.session_state["nome_estoque"] = resultado["arquivo_estoque"]
            st.session_state["nome_cadastro"] = resultado["arquivo_cadastro"]

            progress_bar.progress(100)
            status_text.write("✅ Processamento concluído.")

            if resultado["df_estoque"] is None or resultado["df_cadastro"] is None:
                st.error("⚠️ Não consegui identificar estoque e cadastro.")
                st.info("Dica: envie arquivos com nome contendo 'estoque' e 'cadastro'.")
            else:
                st.success("✅ As duas planilhas foram carregadas com sucesso.")

        except Exception as e:
            st.error(f"Erro ao processar arquivos: {e}")
            adicionar_log(f"Erro ao processar arquivos soltos: {e}")

# =========================
# DADOS CARREGADOS
# =========================
df_estoque = st.session_state.get("df_estoque")
df_cadastro = st.session_state.get("df_cadastro")
nome_estoque = st.session_state.get("nome_estoque")
nome_cadastro = st.session_state.get("nome_cadastro")
logs = st.session_state.get("logs_processamento", [])

# =========================
# STATUS
# =========================
st.subheader("📌 Status atual")

col1, col2 = st.columns(2)

with col1:
    st.write("**Arquivo de estoque:**", nome_estoque if nome_estoque else "Não carregado")
    if df_estoque is not None:
        st.success(f"Linhas carregadas: {len(df_estoque)}")
    else:
        st.warning("Sem planilha de estoque")

with col2:
    st.write("**Arquivo de cadastro:**", nome_cadastro if nome_cadastro else "Não carregado")
    if df_cadastro is not None:
        st.success(f"Linhas carregadas: {len(df_cadastro)}")
    else:
        st.warning("Sem planilha de cadastro")

# =========================
# PRÉVIAS
# =========================
if df_estoque is not None:
    st.subheader("📦 Prévia - Estoque")
    st.dataframe(df_estoque.head(20), use_container_width=True)

if df_cadastro is not None:
    st.subheader("📋 Prévia - Cadastro")
    st.dataframe(df_cadastro.head(20), use_container_width=True)

# =========================
# LOGS NA TELA
# =========================
st.subheader("🧾 Log de processamento")

if logs:
    st.text_area("Logs", value="\n".join(logs), height=250)
else:
    st.info("Nenhum log gerado ainda.")

# =========================
# DOWNLOADS INDIVIDUAIS
# =========================
if df_estoque is not None or df_cadastro is not None:
    st.subheader("⬇️ Downloads")

    col3, col4, col5 = st.columns(3)

    with col3:
        if df_estoque is not None:
            st.download_button(
                label="📦 Baixar Estoque.xlsx",
                data=dataframe_para_excel_bytes(df_estoque),
                file_name="estoque_processado.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

    with col4:
        if df_cadastro is not None:
            st.download_button(
                label="📋 Baixar Cadastro.xlsx",
                data=dataframe_para_excel_bytes(df_cadastro),
                file_name="cadastro_processado.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

    with col5:
        zip_final = gerar_zip_final(
            df_estoque=df_estoque,
            df_cadastro=df_cadastro,
            logs=logs,
            nome_estoque="estoque_processado.xlsx",
            nome_cadastro="cadastro_processado.xlsx"
        )

        st.download_button(
            label="📦 Baixar ZIP Final",
            data=zip_final,
            file_name="planilhas_processadas.zip",
            mime="application/zip",
            use_container_width=True
)
