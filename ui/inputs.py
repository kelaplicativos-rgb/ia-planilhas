import streamlit as st


def render_inputs():
    modo_coleta = st.radio(
        "📥 Fonte dos dados",
        ["Planilha + Site", "Só Planilha", "Só Site"],
        horizontal=True,
    )

    url_base = st.text_input("🌐 Site:", "https://megacentereletronicos.com.br/").strip()

    arquivo_dados = st.file_uploader(
        "📄 Planilha de dados",
        type=["xlsx", "xls", "csv"],
        help="Se estiver no celular e o arquivo não aparecer, renomeie para algo simples como dados.csv",
    )

    modelo_estoque_file = st.file_uploader(
        "📦 Modelo ESTOQUE",
        type=["xlsx", "xls", "csv"],
    )

    modelo_cadastro_file = st.file_uploader(
        "📋 Modelo CADASTRO",
        type=["xlsx", "xls", "csv"],
    )

    filtro = st.text_input("🔎 Filtrar produto:", "").strip()

    estoque_padrao = st.number_input(
        "📦 Estoque padrão",
        value=10,
        min_value=0,
        step=1,
    )

    depositos_input = st.text_input(
        "🏬 IDs dos depósitos (separados por vírgula)",
        "14888207145",
    )
    depositos = [d.strip() for d in depositos_input.split(",") if d.strip()]

    executar = st.button("🚀 EXECUTAR")

    return {
        "modo_coleta": modo_coleta,
        "url_base": url_base,
        "arquivo_dados": arquivo_dados,
        "modelo_estoque_file": modelo_estoque_file,
        "modelo_cadastro_file": modelo_cadastro_file,
        "filtro": filtro,
        "estoque_padrao": estoque_padrao,
        "depositos": depositos,
        "executar": executar,
    }
