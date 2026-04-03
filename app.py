import streamlit as st
import pandas as pd
import zipfile
import io
import os
import re
import time
import hashlib
from datetime import datetime

# =========================
# DEPLOY LEVE
# =========================
APP_VERSION = "2026.04.03.05"


def gerar_assinatura_deploy():
    return hashlib.md5(APP_VERSION.encode("utf-8")).hexdigest()


def executar_boot_deploy():
    assinatura_atual = gerar_assinatura_deploy()
    assinatura_anterior = st.session_state.get("deploy_assinatura")

    if assinatura_anterior is None:
        st.session_state["deploy_assinatura"] = assinatura_atual
        return

    if assinatura_anterior != assinatura_atual:
        try:
            st.cache_data.clear()
        except:
            pass

        try:
            st.cache_resource.clear()
        except:
            pass

        st.session_state.clear()
        st.session_state["deploy_assinatura"] = assinatura_atual
        st.rerun()


def reset_total_sistema():
    assinatura_atual = gerar_assinatura_deploy()

    try:
        st.cache_data.clear()
    except:
        pass

    try:
        st.cache_resource.clear()
    except:
        pass

    st.session_state.clear()
    st.session_state["deploy_assinatura"] = assinatura_atual
    st.rerun()


executar_boot_deploy()

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="🔥 BLING FORMATO ORIGINAL", layout="wide")
st.title("🔥 BLING FORMATO ORIGINAL + LIMPEZA TOTAL")

# =========================
# TOPO DEPLOY
# =========================
dep1, dep2, dep3 = st.columns([1.3, 1, 1])

with dep1:
    st.caption(f"Versão do app: {APP_VERSION}")

with dep2:
    if st.button("🔄 Reset total do sistema", use_container_width=True):
        reset_total_sistema()

with dep3:
    st.caption("Modo leve ativo")

# =========================
# SESSION
# =========================
PADRAO_SESSION = {
    "logs": [],
    "df_origem_estoque": None,
    "df_origem_cadastro": None,
    "df_modelo_estoque": None,
    "df_modelo_cadastro": None,
    "df_final_estoque": None,
    "df_final_cadastro": None,
    "nome_origem_estoque": None,
    "nome_origem_cadastro": None,
    "nome_modelo_estoque": None,
    "nome_modelo_cadastro": None,
    "ext_modelo_estoque": None,
    "ext_modelo_cadastro": None,
}

for k, v in PADRAO_SESSION.items():
    if k not in st.session_state:
        if isinstance(v, list):
            st.session_state[k] = []
        else:
            st.session_state[k] = v

# =========================
# LOG
# =========================
def log(msg):
    horario = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    st.session_state["logs"].append(f"[{horario}] {msg}")


def limpar_estado():
    for k, v in PADRAO_SESSION.items():
        if isinstance(v, list):
            st.session_state[k] = []
        else:
            st.session_state[k] = v


# =========================
# TEXTO
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
    texto = texto.replace("\ufeff", "")
    texto = texto.replace("\u200b", "")
    texto = texto.replace("\xa0", " ")
    texto = texto.replace("\r", " ")
    texto = texto.replace("\n", " ")
    texto = texto.replace("\t", " ")
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def slug_coluna(texto):
    texto = normalizar_texto(texto).lower()

    trocas = {
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

    for antigo, novo in trocas.items():
        texto = texto.replace(antigo, novo)

    texto = re.sub(r"[^a-z0-9_ ]", "", texto)
    texto = texto.replace(" ", "_")
    texto = re.sub(r"_+", "_", texto).strip("_")
    return texto


def buscar_coluna(df, aliases):
    mapa = {slug_coluna(col): col for col in df.columns}
    for alias in aliases:
        chave = slug_coluna(alias)
        if chave in mapa:
            return mapa[chave]
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

    texto = texto.replace("R$", "").replace("r$", "").replace("%", "").replace(" ", "")

    try:
        return float(texto)
    except:
        pass

    texto2 = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto2)
    except:
        return None


def corrigir_preco(valor):
    numero = para_float(valor)
    if numero is None:
        return 0.0

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
# LIMPEZA
# =========================
def coluna_vazia(serie):
    for valor in serie:
        if normalizar_texto(valor) != "":
            return False
    return True


def limpar_dataframe_extremo(df, nome_arquivo="arquivo"):
    if df is None:
        log(f"{nome_arquivo}: dataframe inexistente.")
        return df

    df = df.copy()
    linhas_antes = len(df)
    colunas_antes = len(df.columns)

    df.columns = [normalizar_texto(c) for c in df.columns]

    colunas_validas = []
    unnamed_removidas = 0
    for col in df.columns:
        if slug_coluna(col).startswith("unnamed"):
            unnamed_removidas += 1
            continue
        colunas_validas.append(col)

    df = df[colunas_validas]

    cols_remover = []
    for col in df.columns:
        if coluna_vazia(df[col]):
            cols_remover.append(col)

    if cols_remover:
        df = df.drop(columns=cols_remover)

    for col in df.columns:
        try:
            if df[col].dtype == "object":
                df[col] = df[col].apply(normalizar_texto)
            else:
                df[col] = df[col].apply(lambda x: normalizar_texto(x) if isinstance(x, str) else x)
        except:
            pass

    for col in df.columns:
        df[col] = df[col].apply(lambda x: pd.NA if normalizar_texto(x) == "" else x)

    df = df.dropna(how="all")
    df = df.drop_duplicates()
    df = df.fillna("")
    df = df.reset_index(drop=True)

    log(
        f"{nome_arquivo}: limpeza concluída | linhas {linhas_antes}->{len(df)} | "
        f"colunas {colunas_antes}->{len(df.columns)} | unnamed removidas={unnamed_removidas}"
    )

    return df


# =========================
# LEITURA
# =========================
def obter_extensao(nome_arquivo):
    return os.path.splitext(nome_arquivo.lower())[1]


def ler_planilha_upload(arquivo):
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

    return limpar_dataframe_extremo(df, arquivo.name)


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

    return limpar_dataframe_extremo(df, nome_arquivo)


# =========================
# IDENTIFICAÇÃO
# =========================
def identificar_tipo(nome, df):
    nome_lower = nome.lower()
    cols = [slug_coluna(c) for c in df.columns]

    if "atualizar_estoque" in nome_lower:
        return "modelo_estoque"

    if "cadastrar_produtos" in nome_lower:
        return "modelo_cadastro"

    if "modelo_estoque" in nome_lower:
        return "modelo_estoque"

    if "modelo_cadastro" in nome_lower:
        return "modelo_cadastro"

    if "estoque" in nome_lower and "atualizar" not in nome_lower:
        return "origem_estoque"

    if "cadastro" in nome_lower and "cadastrar" not in nome_lower:
        return "origem_cadastro"

    if "produto" in nome_lower and "cadastrar" not in nome_lower:
        return "origem_cadastro"

    if "deposito" in cols and "estoque" in cols and "codigo" in cols:
        return "modelo_estoque"

    if "descricao" in cols and "unidade" in cols and "preco" in cols and "situacao" in cols:
        return "modelo_cadastro"

    if "balanco_obrigatorio" in cols or "codigo_produto" in cols:
        return "origem_estoque"

    if "link_externo" in cols or "descricao_curta" in cols:
        return "origem_cadastro"

    if "codigo" in cols and "descricao" in cols:
        return "origem_cadastro"

    return None


# =========================
# PROGRESSO + ETA
# =========================
class ProgressoTempo:
    def __init__(self, total, progress_widget, status_widget):
        self.total = max(1, total)
        self.atual = 0
        self.inicio = time.time()
        self.progress_widget = progress_widget
        self.status_widget = status_widget

    def atualizar(self, mensagem):
        self.atual += 1
        self.atual = min(self.atual, self.total)

        percentual = int((self.atual / self.total) * 100)
        agora = time.time()
        decorrido = agora - self.inicio

        if self.atual > 0:
            medio = decorrido / self.atual
            restante = max(0, int(round((self.total - self.atual) * medio)))
        else:
            restante = 0

        self.progress_widget.progress(percentual)
        self.status_widget.write(
            f"**{percentual}%** — {mensagem}  \n"
            f"⏱️ Decorrido: {int(decorrido)}s | ⌛ Restante estimado: {restante}s"
        )


# =========================
# VALIDAÇÃO ORIGEM
# =========================
def validar_origem_estoque(df):
    erros = []

    if df is None or df.empty:
        erros.append("Planilha de origem de estoque está vazia.")
        return erros

    col_codigo = buscar_coluna(df, [
        "Codigo produto *", "Codigo produto", "codigo_produto",
        "Código", "Codigo", "codigo"
    ])

    col_estoque = buscar_coluna(df, [
        "Balanço (OBRIGATÓRIO)", "Balanco (OBRIGATÓRIO)",
        "Balanço", "Balanco", "Estoque", "estoque", "balanco"
    ])

    if not col_codigo:
        erros.append("Não encontrei coluna de código na origem de estoque.")

    if not col_estoque:
        erros.append("Não encontrei coluna de estoque/balanço na origem de estoque.")

    return erros


def validar_origem_cadastro(df):
    erros = []

    if df is None or df.empty:
        erros.append("Planilha de origem de cadastro está vazia.")
        return erros

    col_codigo = buscar_coluna(df, ["Código", "Codigo", "codigo"])
    col_descricao = buscar_coluna(df, ["Descrição", "Descricao", "descricao"])

    if not col_codigo:
        erros.append("Não encontrei coluna de código na origem de cadastro.")

    if not col_descricao:
        erros.append("Não encontrei coluna de descrição na origem de cadastro.")

    return erros


# =========================
# DADOS NOVOS
# =========================
def gerar_novos_dados_estoque(df):
    col_codigo = buscar_coluna(df, [
        "Codigo produto *", "Codigo produto", "codigo_produto",
        "Código", "Codigo", "codigo"
    ])

    col_estoque = buscar_coluna(df, [
        "Balanço (OBRIGATÓRIO)", "Balanco (OBRIGATÓRIO)",
        "Balanço", "Balanco", "Estoque", "estoque", "balanco"
    ])

    novo = pd.DataFrame()
    novo["Código"] = df[col_codigo] if col_codigo else ""
    novo["Depósito"] = "Geral"
    novo["Estoque"] = df[col_estoque] if col_estoque else 0

    novo["Código"] = novo["Código"].apply(normalizar_texto)
    novo["Depósito"] = novo["Depósito"].apply(normalizar_texto)
    novo["Estoque"] = novo["Estoque"].apply(para_int)

    novo = novo[novo["Código"].astype(str).str.strip() != ""].copy()
    novo = novo.drop_duplicates(subset=["Código"], keep="first").reset_index(drop=True)

    log(f"Novos dados de estoque gerados com {len(novo)} linhas.")
    return novo


def gerar_novos_dados_cadastro(df):
    col_codigo = buscar_coluna(df, ["Código", "Codigo", "codigo"])
    col_descricao = buscar_coluna(df, ["Descrição", "Descricao", "descricao"])
    col_unidade = buscar_coluna(df, ["Unidade", "unidade"])
    col_preco = buscar_coluna(df, ["Preço", "Preco", "preco"])
    col_situacao = buscar_coluna(df, ["Situação", "Situacao", "situacao"])
    col_marca = buscar_coluna(df, ["Marca", "marca"])
    col_desc_curta = buscar_coluna(df, ["Descrição Curta", "Descricao Curta", "descricao_curta"])
    col_url = buscar_coluna(df, ["URL Imagens Externas", "Url Imagens Externas", "url_imagens_externas"])
    col_link = buscar_coluna(df, ["Link Externo", "link_externo"])

    novo = pd.DataFrame()
    novo["Código"] = df[col_codigo] if col_codigo else ""
    novo["Descrição"] = df[col_descricao] if col_descricao else ""
    novo["Unidade"] = df[col_unidade] if col_unidade else "UN"
    novo["Preço"] = df[col_preco] if col_preco else 0
    novo["Situação"] = df[col_situacao] if col_situacao else "Ativo"
    novo["Marca"] = df[col_marca] if col_marca else ""
    novo["Descrição Curta"] = df[col_desc_curta] if col_desc_curta else ""
    novo["URL Imagens Externas"] = df[col_url] if col_url else ""
    novo["Link Externo"] = df[col_link] if col_link else ""

    for col in [
        "Código", "Descrição", "Unidade", "Situação", "Marca",
        "Descrição Curta", "URL Imagens Externas", "Link Externo"
    ]:
        novo[col] = novo[col].apply(normalizar_texto)

    novo["Preço"] = novo["Preço"].apply(corrigir_preco)
    novo["Unidade"] = novo["Unidade"].replace("", "UN")

    def norm_situacao(v):
        t = normalizar_texto(v).lower()
        if t in ["", "ativo", "1", "sim", "s", "true"]:
            return "Ativo"
        if t in ["inativo", "0", "nao", "não", "n", "false"]:
            return "Inativo"
        if "inativo" in t:
            return "Inativo"
        return "Ativo"

    novo["Situação"] = novo["Situação"].apply(norm_situacao)

    mask_codigo_vazio = novo["Código"].astype(str).str.strip() == ""
    novo.loc[mask_codigo_vazio, "Código"] = novo.loc[mask_codigo_vazio, "Descrição"]

    mask_desc_curta_vazia = novo["Descrição Curta"].astype(str).str.strip() == ""
    novo.loc[mask_desc_curta_vazia, "Descrição Curta"] = novo.loc[mask_desc_curta_vazia, "Descrição"]

    novo = novo[novo["Código"].astype(str).str.strip() != ""].copy()
    novo = novo.drop_duplicates(subset=["Código"], keep="first").reset_index(drop=True)

    log(f"Novos dados de cadastro gerados com {len(novo)} linhas.")
    return novo


# =========================
# PRESERVAR MODELO EXATO
# =========================
def limpar_modelo_e_inserir_exato(modelo_df, novos_dados_df, nome_tipo="modelo"):
    if modelo_df is None or modelo_df.empty:
        log(f"{nome_tipo}: sem modelo enviado, gerando arquivo direto pelos novos dados.")
        return novos_dados_df.copy()

    colunas_modelo = list(modelo_df.columns)
    log(f"{nome_tipo}: modelo carregado com {len(modelo_df)} linhas antigas. Conteúdo será apagado.")

    final = pd.DataFrame(columns=colunas_modelo)
    mapa_novos = {slug_coluna(col): col for col in novos_dados_df.columns}

    for col_modelo in colunas_modelo:
        chave = slug_coluna(col_modelo)
        if chave in mapa_novos:
            col_nova = mapa_novos[chave]
            final[col_modelo] = novos_dados_df[col_nova]
        else:
            final[col_modelo] = ""

    final = final.fillna("").reset_index(drop=True)

    log(f"{nome_tipo}: conteúdo antigo apagado e {len(final)} linhas novas inseridas.")
    return final


# =========================
# EXPORTAÇÃO
# =========================
def dataframe_para_excel_bytes(df, sheet_name="Dados"):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    output.seek(0)
    return output.getvalue()


def detectar_separador_csv(df):
    candidatos = [",", ";", "\t"]
    melhor_sep = ";"
    maior_score = -1

    for sep in candidatos:
        try:
            preview = df.head(20).to_csv(index=False, sep=sep)
            score = preview.count(sep)
            if score > maior_score:
                maior_score = score
                melhor_sep = sep
        except:
            pass

    return melhor_sep


def dataframe_para_csv_bytes(df):
    sep = detectar_separador_csv(df)
    csv_text = df.to_csv(index=False, sep=sep, encoding="utf-8")
    return csv_text.encode("utf-8")


def bytes_no_formato(df, ext, sheet_name="Dados"):
    ext = (ext or "").lower()

    if ext == ".csv":
        return dataframe_para_csv_bytes(df), "text/csv"

    return (
        dataframe_para_excel_bytes(df, sheet_name),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def nome_saida(base, ext):
    ext = (ext or "").lower()
    if ext not in [".csv", ".xlsx", ".xls"]:
        ext = ".xlsx"

    if ext == ".xls":
        ext = ".xlsx"

    return f"{base}{ext}"


def gerar_zip_final(df_estoque, df_cadastro, ext_estoque, ext_cadastro, logs):
    mem = io.BytesIO()

    nome_est = nome_saida("atualizar_estoque", ext_estoque)
    nome_cad = nome_saida("cadastrar_produtos", ext_cadastro)

    with zipfile.ZipFile(mem, "w", compression=zipfile.ZIP_DEFLATED) as z:
        if df_estoque is not None and not df_estoque.empty:
            bytes_est, _ = bytes_no_formato(df_estoque, ext_estoque, "Estoque")
            z.writestr(nome_est, bytes_est)

        if df_cadastro is not None and not df_cadastro.empty:
            bytes_cad, _ = bytes_no_formato(df_cadastro, ext_cadastro, "Cadastro")
            z.writestr(nome_cad, bytes_cad)

        z.writestr("log_processamento.txt", "\n".join(logs) if logs else "Sem logs.")

    mem.seek(0)
    return mem.getvalue(), nome_est, nome_cad


# =========================
# PROCESSAMENTO
# =========================
def processar_lista_arquivos(lista_arquivos, progresso, origem="upload"):
    saida = {
        "df_origem_estoque": None,
        "df_origem_cadastro": None,
        "df_modelo_estoque": None,
        "df_modelo_cadastro": None,
        "nome_origem_estoque": None,
        "nome_origem_cadastro": None,
        "nome_modelo_estoque": None,
        "nome_modelo_cadastro": None,
        "ext_modelo_estoque": None,
        "ext_modelo_cadastro": None,
    }

    for arquivo in lista_arquivos:
        progresso.atualizar(f"Lendo {origem}: {arquivo['nome']}")

        if arquivo["tipo_obj"] == "upload":
            df = ler_planilha_upload(arquivo["obj"])
        else:
            df = ler_planilha_bytes(arquivo["nome"], arquivo["bytes"])

        tipo = identificar_tipo(arquivo["nome"], df)
        ext = obter_extensao(arquivo["nome"])
        log(f"{arquivo['nome']}: tipo identificado = {tipo}")

        if tipo == "origem_estoque" and saida["df_origem_estoque"] is None:
            saida["df_origem_estoque"] = df
            saida["nome_origem_estoque"] = arquivo["nome"]

        elif tipo == "origem_cadastro" and saida["df_origem_cadastro"] is None:
            saida["df_origem_cadastro"] = df
            saida["nome_origem_cadastro"] = arquivo["nome"]

        elif tipo == "modelo_estoque" and saida["df_modelo_estoque"] is None:
            saida["df_modelo_estoque"] = df
            saida["nome_modelo_estoque"] = arquivo["nome"]
            saida["ext_modelo_estoque"] = ext

        elif tipo == "modelo_cadastro" and saida["df_modelo_cadastro"] is None:
            saida["df_modelo_cadastro"] = df
            saida["nome_modelo_cadastro"] = arquivo["nome"]
            saida["ext_modelo_cadastro"] = ext

    return saida


def extrair_arquivos_do_zip(zip_file):
    arquivos = []

    with zipfile.ZipFile(zip_file, "r") as z:
        nomes = z.namelist()

        for nome in nomes:
            if nome.endswith("/"):
                continue
            if not nome.lower().endswith((".csv", ".xlsx", ".xls")):
                continue

            arquivos.append({
                "nome": os.path.basename(nome),
                "bytes": z.read(nome),
                "tipo_obj": "bytes"
            })

    return arquivos


# =========================
# AÇÕES RÁPIDAS
# =========================
a1, a2 = st.columns(2)

with a1:
    if st.button("🗑️ Limpar tudo", use_container_width=True):
        limpar_estado()
        st.success("Estado limpo com sucesso.")

with a2:
    st.info("Se o modelo vier em CSV, o resultado sai em CSV. Se vier em XLSX/XLS, sai em XLSX.")


# =========================
# FORMULÁRIO
# =========================
with st.form("form_processamento"):
    modo_envio = st.radio(
        "📥 Como deseja enviar?",
        ["Arquivos soltos", "ZIP com tudo junto"],
        horizontal=True
    )

    if modo_envio == "Arquivos soltos":
        arquivos_soltos = st.file_uploader(
            "Envie os arquivos",
            type=["csv", "xlsx", "xls"],
            accept_multiple_files=True,
            key="arquivos_soltos"
        )
        zip_unico = None
    else:
        zip_unico = st.file_uploader(
            "Envie 1 ZIP com tudo dentro",
            type=["zip"],
            key="zip_unico"
        )
        arquivos_soltos = None

    processar = st.form_submit_button("🚀 Processar agora", use_container_width=True)

progress_bar = st.progress(0)
status_box = st.empty()


# =========================
# PROCESSAR
# =========================
pode_processar = (arquivos_soltos and len(arquivos_soltos) > 0) or (zip_unico is not None)

if processar and pode_processar:
    try:
        limpar_estado()

        lista_arquivos = []

        if arquivos_soltos:
            for arq in arquivos_soltos:
                lista_arquivos.append({
                    "nome": arq.name,
                    "obj": arq,
                    "tipo_obj": "upload"
                })

        if zip_unico is not None:
            lista_arquivos = extrair_arquivos_do_zip(zip_unico)
            log(f"ZIP lido com {len(lista_arquivos)} arquivos válidos.")

        total_etapas = len(lista_arquivos) + 9
        progresso = ProgressoTempo(total_etapas, progress_bar, status_box)

        progresso.atualizar("Preparando processamento")
        log("Início do processamento.")

        resultado = processar_lista_arquivos(
            lista_arquivos,
            progresso,
            origem="ZIP" if zip_unico is not None else "arquivos soltos"
        )

        for chave, valor in resultado.items():
            st.session_state[chave] = valor

        progresso.atualizar("Validando origens")
        erros = []

        if st.session_state["df_origem_estoque"] is not None:
            erros += validar_origem_estoque(st.session_state["df_origem_estoque"])
        else:
            erros.append("Arquivo de origem de estoque não foi identificado.")

        if st.session_state["df_origem_cadastro"] is not None:
            erros += validar_origem_cadastro(st.session_state["df_origem_cadastro"])
        else:
            erros.append("Arquivo de origem de cadastro não foi identificado.")

        progresso.atualizar("Gerando novos dados de estoque")
        novos_estoque = gerar_novos_dados_estoque(st.session_state["df_origem_estoque"]) if st.session_state["df_origem_estoque"] is not None else pd.DataFrame()

        progresso.atualizar("Gerando novos dados de cadastro")
        novos_cadastro = gerar_novos_dados_cadastro(st.session_state["df_origem_cadastro"]) if st.session_state["df_origem_cadastro"] is not None else pd.DataFrame()

        progresso.atualizar("Limpando conteúdo antigo do modelo de estoque")
        final_estoque = limpar_modelo_e_inserir_exato(
            st.session_state["df_modelo_estoque"],
            novos_estoque,
            "modelo_estoque"
        )

        progresso.atualizar("Limpando conteúdo antigo do modelo de cadastro")
        final_cadastro = limpar_modelo_e_inserir_exato(
            st.session_state["df_modelo_cadastro"],
            novos_cadastro,
            "modelo_cadastro"
        )

        progresso.atualizar("Aplicando limpeza final no estoque")
        final_estoque = limpar_dataframe_extremo(final_estoque, "final_estoque")

        progresso.atualizar("Aplicando limpeza final no cadastro")
        final_cadastro = limpar_dataframe_extremo(final_cadastro, "final_cadastro")

        progresso.atualizar("Salvando resultados")
        st.session_state["df_final_estoque"] = final_estoque
        st.session_state["df_final_cadastro"] = final_cadastro

        if erros:
            for erro in erros:
                st.error(erro)
                log(erro)
        else:
            st.success("✅ Processamento concluído com sucesso.")
            log("Processamento concluído com sucesso.")

        progresso.atualizar("Concluído")

    except Exception as e:
        st.error(f"Erro no processamento: {e}")
        log(f"Erro no processamento: {e}")


# =========================
# STATUS
# =========================
st.subheader("📌 Status atual")

c1, c2 = st.columns(2)

with c1:
    st.write(f"**Origem estoque:** {st.session_state['nome_origem_estoque'] or 'Não carregado'}")
    st.write(f"**Modelo estoque:** {st.session_state['nome_modelo_estoque'] or 'Não enviado'}")
    st.write(f"**Formato modelo estoque:** {st.session_state['ext_modelo_estoque'] or 'Padrão .xlsx'}")

with c2:
    st.write(f"**Origem cadastro:** {st.session_state['nome_origem_cadastro'] or 'Não carregado'}")
    st.write(f"**Modelo cadastro:** {st.session_state['nome_modelo_cadastro'] or 'Não enviado'}")
    st.write(f"**Formato modelo cadastro:** {st.session_state['ext_modelo_cadastro'] or 'Padrão .xlsx'}")


# =========================
# PRÉVIAS FECHADAS
# =========================
with st.expander("📦 Prévia origem - estoque", expanded=False):
    if st.session_state["df_origem_estoque"] is not None:
        st.dataframe(st.session_state["df_origem_estoque"].head(20), use_container_width=True)

with st.expander("📋 Prévia origem - cadastro", expanded=False):
    if st.session_state["df_origem_cadastro"] is not None:
        st.dataframe(st.session_state["df_origem_cadastro"].head(20), use_container_width=True)

with st.expander("🧩 Prévia modelo - atualizar_estoque", expanded=False):
    if st.session_state["df_modelo_estoque"] is not None:
        st.dataframe(st.session_state["df_modelo_estoque"].head(20), use_container_width=True)

with st.expander("🧩 Prévia modelo - cadastrar_produtos", expanded=False):
    if st.session_state["df_modelo_cadastro"] is not None:
        st.dataframe(st.session_state["df_modelo_cadastro"].head(20), use_container_width=True)

with st.expander("📦 Prévia final - atualizar_estoque", expanded=False):
    if st.session_state["df_final_estoque"] is not None and not st.session_state["df_final_estoque"].empty:
        st.dataframe(st.session_state["df_final_estoque"].head(20), use_container_width=True)

with st.expander("📋 Prévia final - cadastrar_produtos", expanded=False):
    if st.session_state["df_final_cadastro"] is not None and not st.session_state["df_final_cadastro"].empty:
        st.dataframe(st.session_state["df_final_cadastro"].head(20), use_container_width=True)


# =========================
# DOWNLOADS
# =========================
df_final_estoque = st.session_state["df_final_estoque"]
df_final_cadastro = st.session_state["df_final_cadastro"]

ext_modelo_estoque = st.session_state["ext_modelo_estoque"] or ".xlsx"
ext_modelo_cadastro = st.session_state["ext_modelo_cadastro"] or ".xlsx"

if (
    (df_final_estoque is not None and not df_final_estoque.empty) or
    (df_final_cadastro is not None and not df_final_cadastro.empty)
):
    st.subheader("⬇️ Downloads")

    nome_est = nome_saida("atualizar_estoque", ext_modelo_estoque)
    nome_cad = nome_saida("cadastrar_produtos", ext_modelo_cadastro)

    d1, d2, d3 = st.columns(3)

    with d1:
        if df_final_estoque is not None and not df_final_estoque.empty:
            data_est, mime_est = bytes_no_formato(df_final_estoque, ext_modelo_estoque, "Estoque")
            st.download_button(
                label=f"📦 Baixar {nome_est}",
                data=data_est,
                file_name=nome_est,
                mime=mime_est,
                use_container_width=True
            )

    with d2:
        if df_final_cadastro is not None and not df_final_cadastro.empty:
            data_cad, mime_cad = bytes_no_formato(df_final_cadastro, ext_modelo_cadastro, "Cadastro")
            st.download_button(
                label=f"📋 Baixar {nome_cad}",
                data=data_cad,
                file_name=nome_cad,
                mime=mime_cad,
                use_container_width=True
            )

    with d3:
        zip_final, nome_zip_est, nome_zip_cad = gerar_zip_final(
            df_final_estoque,
            df_final_cadastro,
            ext_modelo_estoque,
            ext_modelo_cadastro,
            st.session_state["logs"]
        )

        st.download_button(
            label="📦 Baixar bling_final.zip",
            data=zip_final,
            file_name="bling_final.zip",
            mime="application/zip",
            use_container_width=True
        )


# =========================
# LOGS FECHADOS
# =========================
with st.expander("🧾 Logs", expanded=False):
    if st.session_state["logs"]:
        st.text_area(
            "Log de processamento",
            value="\n".join(st.session_state["logs"]),
            height=320
        )
    else:
        st.info("Nenhum log gerado ainda.")
