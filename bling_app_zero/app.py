import streamlit as st
import pandas as pd

from .core.leitor import (
    carregar_planilha,
    preview,
    validar_planilha_basica,
)
from .utils.excel import salvar_excel_bytes


# =========================================================
# CONFIG
# =========================================================
def configurar_pagina():
    st.set_page_config(
        page_title="Bling App Zero",
        layout="wide"
    )
    st.title("📦 Bling App Zero")
    st.caption("Importação, análise e preparação de planilhas no padrão Bling.")


# =========================================================
# ESTADO INICIAL
# =========================================================
def iniciar_estado():
    if "df_planilha" not in st.session_state:
        st.session_state.df_planilha = None

    if "arquivo_nome" not in st.session_state:
        st.session_state.arquivo_nome = ""

    if "colunas_detectadas" not in st.session_state:
        st.session_state.colunas_detectadas = []

    if "mapeamento_manual" not in st.session_state:
        st.session_state.mapeamento_manual = {}

    if "mapeamento_final" not in st.session_state:
        st.session_state.mapeamento_final = {}

    if "tipo_planilha" not in st.session_state:
        st.session_state.tipo_planilha = "cadastro"


# =========================================================
# HELPERS
# =========================================================
def detectar_colunas_basico(df: pd.DataFrame) -> dict:
    resultado = {}

    for col in df.columns:
        nome = str(col).strip().lower()

        if any(x in nome for x in ["sku", "codigo", "código", "referencia", "referência"]):
            resultado["codigo"] = col
        elif any(x in nome for x in ["nome", "produto", "titulo", "título"]):
            resultado["nome"] = col
        elif any(x in nome for x in ["descricao_curta", "descrição_curta", "descricao", "descrição"]):
            resultado["descricao_curta"] = col
        elif any(x in nome for x in ["marca"]):
            resultado["marca"] = col
        elif any(x in nome for x in ["preco", "preço", "valor"]):
            resultado["preco"] = col
        elif any(x in nome for x in ["estoque", "saldo", "quantidade", "qtde"]):
            resultado["estoque"] = col
        elif any(x in nome for x in ["imagem", "img", "foto"]):
            resultado["imagem"] = col
        elif any(x in nome for x in ["link", "url", "site"]):
            resultado["link_externo"] = col
        elif any(x in nome for x in ["categoria"]):
            resultado["categoria"] = col
        elif any(x in nome for x in ["peso"]):
            resultado["peso"] = col
        elif any(x in nome for x in ["gtin", "ean", "barcode", "codigo_barras", "código_barras"]):
            resultado["gtin"] = col

    return resultado


def montar_mapeamento_final(df: pd.DataFrame, mapeamento_manual: dict) -> dict:
    automatico = detectar_colunas_basico(df)

    final = automatico.copy()
    for campo, coluna in mapeamento_manual.items():
        if coluna and coluna != "__nenhuma__":
            final[campo] = coluna

    return final


def montar_planilha_saida(df: pd.DataFrame, mapeamento_final: dict, tipo_planilha: str) -> pd.DataFrame:
    saida = pd.DataFrame()

    def pegar_coluna(campo, default=""):
        col = mapeamento_final.get(campo)
        if col and col in df.columns:
            return df[col]
        return pd.Series([default] * len(df))

    if tipo_planilha == "cadastro":
        # Estrutura base segura para cadastro no Bling
        saida["id"] = ""
        saida["codigo"] = pegar_coluna("codigo")
        saida["nome"] = pegar_coluna("nome")
        saida["unidade"] = "UN"
        saida["preco"] = pegar_coluna("preco")
        saida["situacao"] = "Ativo"
        saida["marca"] = pegar_coluna("marca")

        # REGRA DO USUÁRIO:
        # descrição vai apenas em descrição curta
        saida["descricao_curta"] = pegar_coluna("descricao_curta")
        saida["descricao"] = ""

        # REGRA DO USUÁRIO:
        # vídeo não recebe link
        saida["video"] = ""

        # links apenas nas colunas de imagem
        saida["imagem_1"] = pegar_coluna("imagem")
        saida["imagem_2"] = ""
        saida["imagem_3"] = ""
        saida["imagem_4"] = ""
        saida["imagem_5"] = ""

        saida["link_externo"] = pegar_coluna("link_externo")
        saida["categoria"] = pegar_coluna("categoria")
        saida["peso_liquido"] = pegar_coluna("peso")
        saida["gtin"] = pegar_coluna("gtin")

    else:
        # Estrutura base segura para estoque
        saida["id"] = ""
        saida["codigo"] = pegar_coluna("codigo")
        saida["nome"] = pegar_coluna("nome")
        saida["estoque"] = pegar_coluna("estoque", 0)

    return saida


# =========================================================
# UPLOAD
# =========================================================
def bloco_upload():
    st.subheader("📤 Envio da planilha")

    col1, col2 = st.columns([2, 1])

    with col1:
        arquivo = st.file_uploader(
            "Selecione a planilha",
            type=["xlsx", "xls", "csv"],
            key="uploader_planilha"
        )

    with col2:
        tipo_planilha = st.selectbox(
            "Tipo de saída",
            options=["cadastro", "estoque"],
            index=0 if st.session_state.tipo_planilha == "cadastro" else 1
        )
        st.session_state.tipo_planilha = tipo_planilha

    if arquivo is not None:
        df = carregar_planilha(arquivo)
        ok, msg = validar_planilha_basica(df)

        if not ok:
            st.error(msg)
            return

        st.session_state.df_planilha = df
        st.session_state.arquivo_nome = arquivo.name
        st.session_state.colunas_detectadas = list(df.columns)
        st.session_state.mapeamento_manual = {}
        st.session_state.mapeamento_final = montar_mapeamento_final(df, {})

        st.success(f"✅ Planilha carregada com sucesso: {arquivo.name}")


# =========================================================
# AJUSTE MANUAL
# =========================================================
def bloco_ajuste_manual(df: pd.DataFrame):
    opcoes = ["__nenhuma__"] + list(df.columns)

    campos = [
        "codigo",
        "nome",
        "descricao_curta",
        "marca",
        "preco",
        "estoque",
        "imagem",
        "link_externo",
        "categoria",
        "peso",
        "gtin",
    ]

    mapeamento_atual = st.session_state.get("mapeamento_final", {})

    novo_mapeamento = {}

    st.write("Selecione manualmente apenas se quiser corrigir algo.")

    col1, col2 = st.columns(2)

    for i, campo in enumerate(campos):
        valor_atual = mapeamento_atual.get(campo, "__nenhuma__")
        if valor_atual not in opcoes:
            valor_atual = "__nenhuma__"

        index_atual = opcoes.index(valor_atual)

        with col1 if i % 2 == 0 else col2:
            novo_mapeamento[campo] = st.selectbox(
                f"Campo: {campo}",
                options=opcoes,
                index=index_atual,
                key=f"map_{campo}"
            )

    st.session_state.mapeamento_manual = novo_mapeamento

    if st.button("💾 Aplicar mapeamento manual", key="aplicar_mapeamento_manual"):
        st.session_state.mapeamento_final = montar_mapeamento_final(df, novo_mapeamento)
        st.success("✅ Mapeamento manual aplicado com sucesso.")


# =========================================================
# MAPEAMENTO FINAL
# =========================================================
def bloco_mapeamento_final():
    mapeamento_final = st.session_state.get("mapeamento_final", {})

    if not mapeamento_final:
        st.caption("Nenhum mapeamento final disponível.")
        return

    df_map = pd.DataFrame(
        [
            {"campo_destino": k, "coluna_origem": v}
            for k, v in mapeamento_final.items()
        ]
    )

    st.dataframe(df_map, use_container_width=True, hide_index=True)


# =========================================================
# DOWNLOAD
# =========================================================
def bloco_download(df: pd.DataFrame):
    st.subheader("📥 Geração da planilha final")

    mapeamento_final = st.session_state.get("mapeamento_final", {})
    tipo_planilha = st.session_state.get("tipo_planilha", "cadastro")

    if not mapeamento_final:
        st.warning("⚠️ Não há mapeamento final disponível.")
        return

    df_saida = montar_planilha_saida(df, mapeamento_final, tipo_planilha)

    st.success("✅ Planilha final gerada.")

    nome_arquivo = f"bling_{tipo_planilha}.xlsx"
    excel_bytes = salvar_excel_bytes(df_saida)

    st.download_button(
        label=f"⬇️ Baixar planilha {tipo_planilha}",
        data=excel_bytes,
        file_name=nome_arquivo,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="download_planilha_final"
    )


# =========================================================
# MAIN
# =========================================================
def main():
    configurar_pagina()
    iniciar_estado()
    bloco_upload()

    df = st.session_state.get("df_planilha")

    if df is None:
        st.info("Envie uma planilha para continuar.")
        return

    st.divider()

    # Preview controlado e fechado por padrão
    preview(
        df=df,
        nome="Planilha carregada",
        colunas_detectadas=st.session_state.get("colunas_detectadas", []),
        mapeamento_manual=st.session_state.get("mapeamento_manual", {}),
        mapeamento_final=st.session_state.get("mapeamento_final", {}),
    )

    st.divider()

    # Ajuste manual real, também fechado por padrão
    chave_ajuste_real = "bloco_real_ajuste_manual"

    if chave_ajuste_real not in st.session_state:
        st.session_state[chave_ajuste_real] = False

    col1, col2 = st.columns(2)

    with col1:
        if st.button("👁️ Mostrar painel real de ajuste manual", key="show_real_ajuste"):
            st.session_state[chave_ajuste_real] = True

    with col2:
        if st.button("❌ Ocultar painel real de ajuste manual", key="hide_real_ajuste"):
            st.session_state[chave_ajuste_real] = False

    if st.session_state[chave_ajuste_real]:
        st.subheader("🛠️ Painel real de ajuste manual")
        bloco_ajuste_manual(df)

    st.divider()

    # Mapeamento final real, também fechado por padrão
    chave_mapeamento_real = "bloco_real_mapeamento_final"

    if chave_mapeamento_real not in st.session_state:
        st.session_state[chave_mapeamento_real] = False

    col3, col4 = st.columns(2)

    with col3:
        if st.button("👁️ Mostrar painel real de mapeamento final", key="show_real_map_final"):
            st.session_state[chave_mapeamento_real] = True

    with col4:
        if st.button("❌ Ocultar painel real de mapeamento final", key="hide_real_map_final"):
            st.session_state[chave_mapeamento_real] = False

    if st.session_state[chave_mapeamento_real]:
        st.subheader("✅ Painel real de mapeamento final")
        bloco_mapeamento_final()

    st.divider()
    bloco_download(df)
