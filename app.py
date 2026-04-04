import json
import os
import re
import unicodedata
from io import BytesIO
from pathlib import Path
from typing import Optional, Dict, List

import pandas as pd
import streamlit as st

from bling_app_zero.core.leitor import carregar_planilha
from bling_app_zero.utils.excel import ler_planilha, salvar_excel_bytes


# =========================================================
# CONFIG
# =========================================================
st.set_page_config(page_title="Bling Cadastro Manual PRO", layout="wide")


# =========================================================
# CAMINHOS
# =========================================================
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "bling_app_zero" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

MAPEAMENTOS_FILE = DATA_DIR / "mapeamentos_fornecedor.json"


# =========================================================
# ESTADO
# =========================================================
def init_state() -> None:
    defaults = {
        "df_origem": None,
        "df_modelo": None,
        "df_saida": None,
        "nome_arquivo_origem": "",
        "nome_modelo_cadastro": "",
        "ultima_chave_origem": "",
        "ultima_chave_modelo": "",
        "mapeamento_manual": {},
        "fornecedor_id": "",
        "logs": [],
        "precificacao_habilitada": False,
        "precificacao_config": {},
        "campos_sem_vinculo": [],
        "campos_obrigatorios_sem_vinculo": [],
    }

    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def log(msg: str) -> None:
    st.session_state.logs.append(str(msg))


def limpar_tudo() -> None:
    chaves_base = {
        "df_origem": None,
        "df_modelo": None,
        "df_saida": None,
        "nome_arquivo_origem": "",
        "nome_modelo_cadastro": "",
        "ultima_chave_origem": "",
        "ultima_chave_modelo": "",
        "mapeamento_manual": {},
        "fornecedor_id": "",
        "logs": [],
        "precificacao_habilitada": False,
        "precificacao_config": {},
        "campos_sem_vinculo": [],
        "campos_obrigatorios_sem_vinculo": [],
    }

    for chave, valor in chaves_base.items():
        st.session_state[chave] = valor

    for chave in list(st.session_state.keys()):
        if chave.startswith("map_") or chave.startswith("cfg_"):
            del st.session_state[chave]


def zerar_mapeamento_visual() -> None:
    st.session_state["mapeamento_manual"] = {}
    for chave in list(st.session_state.keys()):
        if chave.startswith("map_"):
            del st.session_state[chave]


# =========================================================
# HELPERS TEXTO
# =========================================================
def limpar_texto(valor) -> str:
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except Exception:
        pass

    texto = str(valor)
    texto = texto.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def remover_acentos(texto: str) -> str:
    texto = str(texto)
    return "".join(
        c for c in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(c)
    )


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


def fornecedor_id_por_nome(nome_arquivo: str) -> str:
    base = Path(nome_arquivo).stem
    base = slug_coluna(base)
    return base or "fornecedor_sem_nome"


def normalizar_valor_numerico(valor) -> float:
    if valor is None:
        return 0.0

    if isinstance(valor, (int, float)) and not pd.isna(valor):
        return float(valor)

    texto = limpar_texto(valor)
    if not texto:
        return 0.0

    texto = texto.replace("R$", "").replace("%", "").strip()

    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    else:
        if "," in texto:
            texto = texto.replace(".", "").replace(",", ".")

    texto = re.sub(r"[^0-9.\-]", "", texto)

    try:
        return float(texto)
    except Exception:
        return 0.0


def formatar_preview_valor(valor) -> str:
    texto = limpar_texto(valor)
    if not texto:
        return ""
    if len(texto) > 80:
        return texto[:77] + "..."
    return texto


# =========================================================
# HELPERS ARQUIVO
# =========================================================
def carregar_modelo_bling(arquivo) -> Optional[pd.DataFrame]:
    if arquivo is None:
        return None

    try:
        df = ler_planilha(arquivo)
        if df is None or df.empty:
            return None

        df = df.copy()
        df.columns = [str(c).strip() for c in df.columns]
        df = df.dropna(axis=0, how="all").reset_index(drop=True)
        return df
    except Exception as e:
        st.error(f"Erro ao ler modelo de cadastro do Bling: {e}")
        return None


def carregar_mapeamentos_salvos() -> Dict[str, dict]:
    if not MAPEAMENTOS_FILE.exists():
        return {}

    try:
        with open(MAPEAMENTOS_FILE, "r", encoding="utf-8") as f:
            conteudo = json.load(f)
            if isinstance(conteudo, dict):
                return conteudo
            return {}
    except Exception:
        return {}


def salvar_mapeamentos_salvos(dados: Dict[str, dict]) -> None:
    with open(MAPEAMENTOS_FILE, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def salvar_mapeamento_fornecedor(
    fornecedor_id: str,
    nome_arquivo_origem: str,
    nome_modelo: str,
    mapeamento_manual: dict,
    precificacao_config: dict,
) -> None:
    banco = carregar_mapeamentos_salvos()
    banco[fornecedor_id] = {
        "fornecedor_id": fornecedor_id,
        "nome_arquivo_origem": nome_arquivo_origem,
        "nome_modelo": nome_modelo,
        "mapeamento_manual": mapeamento_manual,
        "precificacao_config": precificacao_config,
    }
    salvar_mapeamentos_salvos(banco)


def carregar_mapeamento_fornecedor(fornecedor_id: str) -> Optional[dict]:
    banco = carregar_mapeamentos_salvos()
    return banco.get(fornecedor_id)


# =========================================================
# IDENTIFICAÇÃO DE CAMPOS
# =========================================================
def encontrar_colunas_por_palavras(colunas: List[str], palavras: List[str]) -> List[str]:
    resultado = []
    for col in colunas:
        col_slug = slug_coluna(col)
        for palavra in palavras:
            if slug_coluna(palavra) in col_slug:
                resultado.append(col)
                break
    return resultado


def detectar_campos_obrigatorios_modelo(modelo_df: pd.DataFrame) -> List[str]:
    if modelo_df is None or modelo_df.empty:
        return []

    colunas = list(modelo_df.columns)
    obrigatorios = []

    chaves = [
        ["codigo", "código", "sku"],
        ["nome", "produto", "titulo", "título", "descricao"],
        ["preco", "preço", "valor"],
        ["unidade", "und", "un"],
    ]

    for grupo in chaves:
        encontrados = encontrar_colunas_por_palavras(colunas, grupo)
        if encontrados:
            obrigatorios.append(encontrados[0])

    obrigatorios_unicos = []
    vistos = set()
    for c in obrigatorios:
        if c not in vistos:
            vistos.add(c)
            obrigatorios_unicos.append(c)

    return obrigatorios_unicos


def detectar_colunas_imagem_modelo(modelo_df: pd.DataFrame) -> List[str]:
    if modelo_df is None or modelo_df.empty:
        return []
    return encontrar_colunas_por_palavras(
        list(modelo_df.columns),
        ["imagem", "imagens", "foto", "fotos"],
    )


def detectar_coluna_preco_modelo(modelo_df: pd.DataFrame) -> Optional[str]:
    if modelo_df is None or modelo_df.empty:
        return None
    encontrados = encontrar_colunas_por_palavras(
        list(modelo_df.columns),
        ["preco", "preço", "valor"],
    )
    return encontrados[0] if encontrados else None


# =========================================================
# IMAGENS
# =========================================================
def extrair_lista_imagens(texto: str) -> List[str]:
    bruto = limpar_texto(texto)
    if not bruto:
        return []

    partes = re.split(r"[|,;\n\r\t]+", bruto)
    urls = []
    vistos = set()

    for parte in partes:
        url = limpar_texto(parte)
        if not url:
            continue

        chave = url.lower()
        if chave in vistos:
            continue

        vistos.add(chave)
        urls.append(url)

    return urls


def normalizar_coluna_imagens_pipe(serie: pd.Series) -> pd.Series:
    valores = []
    for valor in serie.fillna("").astype(str).tolist():
        imagens = extrair_lista_imagens(valor)
        valores.append("|".join(imagens))
    return pd.Series(valores, index=serie.index, dtype="object")


# =========================================================
# PRECIFICAÇÃO INTELIGENTE
# =========================================================
def calcular_preco_venda(
    custo: float,
    lucro_percentual: float,
    imposto_percentual: float,
    taxa_percentual: float,
    valor_fixo: float,
) -> float:
    custo = max(custo, 0.0)
    lucro_percentual = max(lucro_percentual, 0.0)
    imposto_percentual = max(imposto_percentual, 0.0)
    taxa_percentual = max(taxa_percentual, 0.0)
    valor_fixo = max(valor_fixo, 0.0)

    percentual_total = (lucro_percentual + imposto_percentual + taxa_percentual) / 100.0

    base = custo + valor_fixo

    if percentual_total >= 0.999:
        return round(base, 2)

    preco = base / (1.0 - percentual_total)
    return round(preco, 2)


def aplicar_precificacao_dataframe(
    df_saida: pd.DataFrame,
    df_origem: pd.DataFrame,
    coluna_preco_modelo: Optional[str],
    config: dict,
) -> pd.DataFrame:
    if df_saida is None or df_saida.empty:
        return df_saida

    if not coluna_preco_modelo:
        return df_saida

    if not config.get("habilitada", False):
        return df_saida

    coluna_custo_origem = config.get("coluna_custo_origem")
    if not coluna_custo_origem or coluna_custo_origem not in df_origem.columns:
        return df_saida

    lucro_percentual = normalizar_valor_numerico(config.get("lucro_percentual"))
    imposto_percentual = normalizar_valor_numerico(config.get("imposto_percentual"))
    taxa_percentual = normalizar_valor_numerico(config.get("taxa_percentual"))
    valor_fixo = normalizar_valor_numerico(config.get("valor_fixo"))

    custos = df_origem[coluna_custo_origem].fillna("").astype(str).tolist()
    precos = []

    for custo in custos[: len(df_saida)]:
        custo_float = normalizar_valor_numerico(custo)
        preco_venda = calcular_preco_venda(
            custo=custo_float,
            lucro_percentual=lucro_percentual,
            imposto_percentual=imposto_percentual,
            taxa_percentual=taxa_percentual,
            valor_fixo=valor_fixo,
        )
        precos.append(preco_venda)

    while len(precos) < len(df_saida):
        precos.append(0.0)

    df_saida[coluna_preco_modelo] = precos
    return df_saida


# =========================================================
# MAPEAMENTO VISUAL
# =========================================================
def montar_opcoes_colunas(df: pd.DataFrame) -> List[str]:
    if df is None or df.empty:
        return [""]
    return [""] + list(df.columns)


def aplicar_mapeamento_salvo_no_estado(mapeamento_salvo: dict) -> None:
    mapeamento_manual = mapeamento_salvo.get("mapeamento_manual") or {}
    precificacao_config = mapeamento_salvo.get("precificacao_config") or {}

    st.session_state["mapeamento_manual"] = mapeamento_manual
    st.session_state["precificacao_config"] = precificacao_config
    st.session_state["precificacao_habilitada"] = bool(precificacao_config.get("habilitada", False))

    for chave, valor in mapeamento_manual.items():
        estado_key = f"map_{slug_coluna(chave)}"
        st.session_state[estado_key] = valor or ""

    if precificacao_config:
        st.session_state["cfg_coluna_custo_origem"] = precificacao_config.get("coluna_custo_origem", "")
        st.session_state["cfg_lucro_percentual"] = precificacao_config.get("lucro_percentual", 0.0)
        st.session_state["cfg_imposto_percentual"] = precificacao_config.get("imposto_percentual", 0.0)
        st.session_state["cfg_taxa_percentual"] = precificacao_config.get("taxa_percentual", 0.0)
        st.session_state["cfg_valor_fixo"] = precificacao_config.get("valor_fixo", 0.0)


def construir_mapeamento_visual(
    df_origem: pd.DataFrame,
    modelo_df: pd.DataFrame,
    obrigatorios: List[str],
) -> dict:
    opcoes = montar_opcoes_colunas(df_origem)
    mapeamento = {}

    st.markdown("## Vinculação manual das colunas")

    header = st.columns([2.2, 0.8, 2.2, 2.8])
    header[0].markdown("**Campo do cadastro Bling**")
    header[1].markdown("**Obrigatório**")
    header[2].markdown("**Coluna do fornecedor**")
    header[3].markdown("**Prévia da coluna escolhida**")

    st.markdown("---")

    primeira_linha = df_origem.head(1).copy()

    for coluna_modelo in modelo_df.columns:
        obrigatorio = coluna_modelo in obrigatorios
        estado_key = f"map_{slug_coluna(coluna_modelo)}"

        valor_inicial = st.session_state.get("mapeamento_manual", {}).get(coluna_modelo, "")
        if valor_inicial not in opcoes:
            valor_inicial = ""

        if estado_key not in st.session_state:
            st.session_state[estado_key] = valor_inicial

        c1, c2, c3, c4 = st.columns([2.2, 0.8, 2.2, 2.8])

        with c1:
            if obrigatorio:
                st.markdown(f"**🔴 {coluna_modelo}**")
            else:
                st.markdown(f"{coluna_modelo}")

        with c2:
            st.markdown("**SIM**" if obrigatorio else "não")

        with c3:
            escolha = st.selectbox(
                label=f"Mapear {coluna_modelo}",
                options=opcoes,
                key=estado_key,
                label_visibility="collapsed",
            )

        with c4:
            preview = ""
            if escolha and escolha in primeira_linha.columns and not primeira_linha.empty:
                preview = formatar_preview_valor(primeira_linha.iloc[0][escolha])
            st.caption(preview or "-")

        mapeamento[coluna_modelo] = escolha or None

    return mapeamento


def analisar_vinculos(mapeamento_manual: dict, obrigatorios: List[str]) -> tuple[list, list]:
    sem_vinculo = [campo for campo, origem in mapeamento_manual.items() if not origem]
    obrigatorios_sem_vinculo = [campo for campo in obrigatorios if not mapeamento_manual.get(campo)]
    return sem_vinculo, obrigatorios_sem_vinculo


# =========================================================
# GERAÇÃO DA SAÍDA
# =========================================================
def gerar_planilha_saida(
    df_origem: pd.DataFrame,
    modelo_df: pd.DataFrame,
    mapeamento_manual: dict,
) -> pd.DataFrame:
    saida = pd.DataFrame("", index=range(len(df_origem)), columns=list(modelo_df.columns))

    colunas_imagem_modelo = detectar_colunas_imagem_modelo(modelo_df)

    for coluna_modelo in modelo_df.columns:
        coluna_origem = mapeamento_manual.get(coluna_modelo)

        if not coluna_origem:
            continue

        if coluna_origem not in df_origem.columns:
            continue

        serie_origem = df_origem[coluna_origem].fillna("").astype(str).reset_index(drop=True)

        if coluna_modelo in colunas_imagem_modelo:
            serie_origem = normalizar_coluna_imagens_pipe(serie_origem)

        saida[coluna_modelo] = serie_origem.values

    return saida


def gerar_excel_download(df_saida: pd.DataFrame) -> bytes:
    try:
        return salvar_excel_bytes(df_saida)
    except Exception:
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_saida.to_excel(writer, index=False)
        output.seek(0)
        return output.getvalue()


# =========================================================
# APP
# =========================================================
def main() -> None:
    init_state()

    st.title("Bling Cadastro Manual PRO")
    st.caption("Upload do fornecedor → vínculo manual → precificação → download")

    with st.sidebar:
        st.header("Ações")

        if st.button("🧹 Limpar tudo", use_container_width=True):
            limpar_tudo()
            st.rerun()

        if st.button("♻️ Zerar mapeamento", use_container_width=True):
            zerar_mapeamento_visual()
            st.rerun()

    st.markdown("## Envio dos arquivos")

    tipos_aceitos = ["xlsx", "xls", "csv", "zip"]

    arquivo_origem = st.file_uploader(
        "1) Planilha do fornecedor",
        type=tipos_aceitos,
        key="upload_origem",
    )

    modelo_cadastro = st.file_uploader(
        "2) Modelo de cadastro do Bling",
        type=tipos_aceitos,
        key="upload_modelo_cadastro",
    )

    # -----------------------------------------------------
    # CARREGA ORIGEM
    # -----------------------------------------------------
    if arquivo_origem is not None:
        chave_atual = f"{arquivo_origem.name}-{getattr(arquivo_origem, 'size', 0)}"
        if st.session_state["ultima_chave_origem"] != chave_atual:
            df_origem = carregar_planilha(arquivo_origem)

            if df_origem is None or df_origem.empty:
                st.error("Erro ao ler a planilha do fornecedor.")
                return

            df_origem = df_origem.copy()
            df_origem.columns = [str(c).strip() for c in df_origem.columns]

            st.session_state["df_origem"] = df_origem
            st.session_state["nome_arquivo_origem"] = arquivo_origem.name
            st.session_state["ultima_chave_origem"] = chave_atual
            st.session_state["df_saida"] = None

            fornecedor_id = fornecedor_id_por_nome(arquivo_origem.name)
            st.session_state["fornecedor_id"] = fornecedor_id

            log(f"Planilha do fornecedor carregada: {arquivo_origem.name}")

            mapeamento_salvo = carregar_mapeamento_fornecedor(fornecedor_id)
            if mapeamento_salvo:
                aplicar_mapeamento_salvo_no_estado(mapeamento_salvo)
                log(f"Mapeamento reaproveitado automaticamente para: {fornecedor_id}")

    # -----------------------------------------------------
    # CARREGA MODELO
    # -----------------------------------------------------
    if modelo_cadastro is not None:
        chave_modelo = f"{modelo_cadastro.name}-{getattr(modelo_cadastro, 'size', 0)}"
        if st.session_state["ultima_chave_modelo"] != chave_modelo:
            df_modelo = carregar_modelo_bling(modelo_cadastro)

            if df_modelo is None or df_modelo.empty:
                st.error("Erro ao ler o modelo de cadastro do Bling.")
                return

            st.session_state["df_modelo"] = df_modelo
            st.session_state["nome_modelo_cadastro"] = modelo_cadastro.name
            st.session_state["ultima_chave_modelo"] = chave_modelo
            st.session_state["df_saida"] = None

            log(f"Modelo de cadastro carregado: {modelo_cadastro.name}")

    df_origem = st.session_state["df_origem"]
    df_modelo = st.session_state["df_modelo"]

    if df_origem is None:
        st.info("Anexe a planilha do fornecedor para começar.")
        return

    st.success(f"✅ Fornecedor carregado: {st.session_state['nome_arquivo_origem']}")

    info_cols = st.columns(3)
    info_cols[0].metric("Linhas", len(df_origem))
    info_cols[1].metric("Colunas do fornecedor", len(df_origem.columns))
    info_cols[2].metric("Fornecedor ID", st.session_state["fornecedor_id"] or "-")

    if df_modelo is None:
        st.warning("Anexe o modelo de cadastro do Bling para liberar o vínculo manual.")
        return

    st.success(f"✅ Modelo carregado: {st.session_state['nome_modelo_cadastro']}")

    obrigatorios = detectar_campos_obrigatorios_modelo(df_modelo)

    if obrigatorios:
        st.info("Campos obrigatórios destacados em vermelho.")

    # -----------------------------------------------------
    # VÍNCULO MANUAL
    # -----------------------------------------------------
    mapeamento_manual = construir_mapeamento_visual(
        df_origem=df_origem,
        modelo_df=df_modelo,
        obrigatorios=obrigatorios,
    )

    st.session_state["mapeamento_manual"] = mapeamento_manual

    campos_sem_vinculo, obrigatorios_sem_vinculo = analisar_vinculos(mapeamento_manual, obrigatorios)
    st.session_state["campos_sem_vinculo"] = campos_sem_vinculo
    st.session_state["campos_obrigatorios_sem_vinculo"] = obrigatorios_sem_vinculo

    st.markdown("## Status do mapeamento")

    if obrigatorios_sem_vinculo:
        st.error(
            "Campos obrigatórios sem vínculo: "
            + ", ".join(obrigatorios_sem_vinculo)
        )
    else:
        st.success("Todos os campos obrigatórios detectados estão vinculados.")

    opcionais_sem_vinculo = [c for c in campos_sem_vinculo if c not in obrigatorios_sem_vinculo]
    if opcionais_sem_vinculo:
        st.warning(
            "Campos sem vínculo: "
            + ", ".join(opcionais_sem_vinculo)
        )

    # -----------------------------------------------------
    # PRECIFICAÇÃO
    # -----------------------------------------------------
    st.markdown("## Precificação inteligente")

    coluna_preco_modelo = detectar_coluna_preco_modelo(df_modelo)
    opcoes_origem = [""] + list(df_origem.columns)

    config_salva = st.session_state.get("precificacao_config", {}) or {}

    habilitada = st.checkbox(
        "Ativar precificação automática do preço de venda",
        value=st.session_state.get("precificacao_habilitada", False),
        key="cfg_precificacao_habilitada",
    )
    st.session_state["precificacao_habilitada"] = habilitada

    pc1, pc2, pc3, pc4, pc5 = st.columns(5)

    with pc1:
        coluna_custo_origem = st.selectbox(
            "Coluna de custo",
            options=opcoes_origem,
            index=opcoes_origem.index(config_salva.get("coluna_custo_origem", "")) if config_salva.get("coluna_custo_origem", "") in opcoes_origem else 0,
            key="cfg_coluna_custo_origem",
            disabled=not habilitada,
        )

    with pc2:
        lucro_percentual = st.number_input(
            "Lucro %",
            min_value=0.0,
            value=float(config_salva.get("lucro_percentual", 0.0)),
            step=0.1,
            key="cfg_lucro_percentual",
            disabled=not habilitada,
        )

    with pc3:
        imposto_percentual = st.number_input(
            "Impostos %",
            min_value=0.0,
            value=float(config_salva.get("imposto_percentual", 0.0)),
            step=0.1,
            key="cfg_imposto_percentual",
            disabled=not habilitada,
        )

    with pc4:
        taxa_percentual = st.number_input(
            "Taxas %",
            min_value=0.0,
            value=float(config_salva.get("taxa_percentual", 0.0)),
            step=0.1,
            key="cfg_taxa_percentual",
            disabled=not habilitada,
        )

    with pc5:
        valor_fixo = st.number_input(
            "Valor fixo",
            min_value=0.0,
            value=float(config_salva.get("valor_fixo", 0.0)),
            step=0.01,
            key="cfg_valor_fixo",
            disabled=not habilitada,
        )

    precificacao_config = {
        "habilitada": habilitada,
        "coluna_custo_origem": coluna_custo_origem,
        "lucro_percentual": float(lucro_percentual),
        "imposto_percentual": float(imposto_percentual),
        "taxa_percentual": float(taxa_percentual),
        "valor_fixo": float(valor_fixo),
    }
    st.session_state["precificacao_config"] = precificacao_config

    if habilitada:
        if not coluna_preco_modelo:
            st.warning("Não encontrei automaticamente a coluna de preço no modelo do Bling.")
        elif not coluna_custo_origem:
            st.warning("Selecione a coluna de custo para a precificação.")
        else:
            exemplo_custo = 100.0
            exemplo_preco = calcular_preco_venda(
                custo=exemplo_custo,
                lucro_percentual=lucro_percentual,
                imposto_percentual=imposto_percentual,
                taxa_percentual=taxa_percentual,
                valor_fixo=valor_fixo,
            )
            st.success(
                f"Exemplo de cálculo: custo {exemplo_custo:.2f} → venda {exemplo_preco:.2f}"
            )

    # -----------------------------------------------------
    # SALVAR MAPEAMENTO
    # -----------------------------------------------------
    st.markdown("## Reaproveitamento do fornecedor")

    c_save_1, c_save_2 = st.columns([1.2, 3])

    with c_save_1:
        if st.button("💾 Salvar mapeamento deste fornecedor", use_container_width=True):
            fornecedor_id = st.session_state["fornecedor_id"] or fornecedor_id_por_nome(
                st.session_state["nome_arquivo_origem"]
            )

            salvar_mapeamento_fornecedor(
                fornecedor_id=fornecedor_id,
                nome_arquivo_origem=st.session_state["nome_arquivo_origem"],
                nome_modelo=st.session_state["nome_modelo_cadastro"],
                mapeamento_manual=mapeamento_manual,
                precificacao_config=precificacao_config,
            )
            st.success("Mapeamento salvo com sucesso.")
            log(f"Mapeamento salvo para fornecedor: {fornecedor_id}")

    with c_save_2:
        st.caption(
            "Quando você subir novamente uma planilha do mesmo fornecedor, o sistema reaproveita o mapeamento salvo automaticamente."
        )

    # -----------------------------------------------------
    # GERAÇÃO
    # -----------------------------------------------------
    st.markdown("## Gerar planilha final")

    if st.button("📦 Gerar planilha de cadastro", use_container_width=True):
        try:
            df_saida = gerar_planilha_saida(
                df_origem=df_origem,
                modelo_df=df_modelo,
                mapeamento_manual=mapeamento_manual,
            )

            df_saida = aplicar_precificacao_dataframe(
                df_saida=df_saida,
                df_origem=df_origem,
                coluna_preco_modelo=coluna_preco_modelo,
                config=precificacao_config,
            )

            st.session_state["df_saida"] = df_saida
            log(f"Planilha final gerada com {len(df_saida)} linhas.")

            st.success("Planilha final gerada com sucesso.")

        except Exception as e:
            st.error(f"Erro ao gerar planilha final: {e}")
            log(f"Erro ao gerar planilha final: {e}")

    # -----------------------------------------------------
    # PRÉVIA E DOWNLOAD
    # -----------------------------------------------------
    df_saida = st.session_state.get("df_saida")

    if df_saida is not None and not df_saida.empty:
        st.markdown("## Prévia final")
        st.dataframe(df_saida.head(20), use_container_width=True)

        nome_saida = "bling_cadastro_manual_final.xlsx"
        arquivo_excel = gerar_excel_download(df_saida)

        st.download_button(
            "📥 Baixar planilha final",
            data=arquivo_excel,
            file_name=nome_saida,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    # -----------------------------------------------------
    # LOGS
    # -----------------------------------------------------
    if st.session_state["logs"]:
        with st.expander("Logs"):
            st.text_area(
                "Log",
                value="\n".join(st.session_state["logs"]),
                height=220,
            )


if __name__ == "__main__":
    main()
