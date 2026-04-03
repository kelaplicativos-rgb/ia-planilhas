import hashlib
import pandas as pd
import streamlit as st

from .core.leitor import (
    carregar_planilha,
    preview,
    validar_planilha_basica,
)
from .core.mapeamento_bling import (
    detectar_colunas,
    mapear_cadastro_bling,
    mapear_estoque_bling,
    validar_cadastro_bling,
    validar_estoque_bling,
)
from .utils.excel import salvar_excel_bytes


# =========================================================
# CONFIGURAÇÃO DA PÁGINA
# =========================================================
def configurar_pagina():
    st.set_page_config(
        page_title="Bling App Zero",
        layout="wide"
    )
    st.title("📦 Bling App Zero")
    st.caption("Preparação inteligente de planilhas no padrão Bling.")


# =========================================================
# HELPERS DE ESTADO
# =========================================================
def set_default(chave, valor):
    if chave not in st.session_state:
        st.session_state[chave] = valor


def get_state(chave, default=None):
    return st.session_state.get(chave, default)


def set_state(chave, valor):
    st.session_state[chave] = valor


def gerar_hash_arquivo(uploaded_file):
    if uploaded_file is None:
        return ""

    try:
        conteudo = uploaded_file.getvalue()
        return hashlib.md5(conteudo).hexdigest()
    except Exception:
        return uploaded_file.name


# =========================================================
# ESTADO INICIAL BLINDADO
# =========================================================
def iniciar_estado():
    defaults = {
        "arquivo_hash": "",
        "arquivo_nome": "",
        "df_planilha": None,
        "tipo_planilha": "cadastro",
        "colunas_detectadas": {},
        "mapeamento_manual": {},
        "mapeamento_final": {},
        "df_saida": None,
        "validacao_ok": False,
        "validacao_erros": [],
        "painel_real_ajuste_manual_aberto": False,
        "painel_real_mapeamento_final_aberto": False,
        "sidebar_tipo_planilha": "cadastro",
        "upload_planilha_principal": None,
    }

    for chave, valor in defaults.items():
        set_default(chave, valor)


# =========================================================
# RESETS
# =========================================================
def resetar_apenas_resultados():
    set_state("colunas_detectadas", {})
    set_state("mapeamento_manual", {})
    set_state("mapeamento_final", {})
    set_state("df_saida", None)
    set_state("validacao_ok", False)
    set_state("validacao_erros", [])
    set_state("painel_real_ajuste_manual_aberto", False)
    set_state("painel_real_mapeamento_final_aberto", False)

    for chave in list(st.session_state.keys()):
        if (
            chave.endswith("_preview_aberto")
            or chave.endswith("_colunas_aberto")
            or chave.endswith("_ajuste_manual_aberto")
            or chave.endswith("_mapeamento_final_aberto")
        ):
            st.session_state[chave] = False


def resetar_tudo():
    for chave in list(st.session_state.keys()):
        del st.session_state[chave]


def resetar_estado_quando_trocar_arquivo(arquivo_hash_novo, arquivo_nome_novo):
    arquivo_hash_atual = get_state("arquivo_hash", "")

    if arquivo_hash_novo != arquivo_hash_atual:
        set_state("arquivo_hash", arquivo_hash_novo)
        set_state("arquivo_nome", arquivo_nome_novo)
        set_state("df_planilha", None)
        resetar_apenas_resultados()

        for chave in list(st.session_state.keys()):
            if chave.startswith("select_manual_"):
                del st.session_state[chave]


# =========================================================
# BARRA LATERAL
# =========================================================
def barra_lateral():
    with st.sidebar:
        st.header("⚙️ Configurações")

        tipo = st.radio(
            "Tipo de planilha de saída",
            options=["cadastro", "estoque"],
            index=0 if get_state("tipo_planilha", "cadastro") == "cadastro" else 1,
            key="sidebar_tipo_planilha"
        )
        set_state("tipo_planilha", tipo)

        st.divider()

        if st.button("🧹 Limpar processamento", use_container_width=True):
            resetar_apenas_resultados()
            st.success("Processamento limpo com sucesso.")
            st.rerun()

        if st.button("♻️ Resetar tudo", use_container_width=True):
            resetar_tudo()
            st.rerun()


# =========================================================
# BLOCO DE ENVIO
# =========================================================
def bloco_upload():
    st.subheader("📤 Envio da planilha")

    arquivo = st.file_uploader(
        "Selecione sua planilha",
        type=["xlsx", "xls", "csv"],
        key="upload_planilha_principal"
    )

    if arquivo is None:
        return

    arquivo_hash = gerar_hash_arquivo(arquivo)
    resetar_estado_quando_trocar_arquivo(arquivo_hash, arquivo.name)

    if get_state("df_planilha") is not None:
        st.success(f"✅ Planilha carregada com sucesso: {get_state('arquivo_nome')}")
        return

    df = carregar_planilha(arquivo)
    ok, msg = validar_planilha_basica(df)

    if not ok:
        st.error(msg)
        return

    colunas_detectadas = detectar_colunas(df)
    mapeamento_final = colunas_detectadas.copy()

    set_state("df_planilha", df)
    set_state("arquivo_nome", arquivo.name)
    set_state("colunas_detectadas", colunas_detectadas)
    set_state("mapeamento_manual", {})
    set_state("mapeamento_final", mapeamento_final)

    st.success(f"✅ Planilha carregada com sucesso: {arquivo.name}")


# =========================================================
# PAINEL REAL DE AJUSTE MANUAL
# =========================================================
def painel_ajuste_manual(df: pd.DataFrame):
    st.subheader("🛠️ Painel real de ajuste manual")

    colunas_disponiveis = ["__nenhuma__"] + list(df.columns)

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

    mapeamento_base = get_state("mapeamento_final", {}).copy()
    novo_mapeamento = {}

    st.caption("Ajuste manual apenas se quiser corrigir a detecção automática.")

    col1, col2 = st.columns(2)

    for i, campo in enumerate(campos):
        valor_atual = mapeamento_base.get(campo, "__nenhuma__")

        if valor_atual not in colunas_disponiveis:
            valor_atual = "__nenhuma__"

        indice = colunas_disponiveis.index(valor_atual)
        container = col1 if i % 2 == 0 else col2

        with container:
            novo_mapeamento[campo] = st.selectbox(
                f"Campo destino: {campo}",
                options=colunas_disponiveis,
                index=indice,
                key=f"select_manual_{campo}"
            )

    if st.button("💾 Aplicar ajuste manual", key="btn_aplicar_ajuste_manual"):
        mapeamento_filtrado = {
            campo: coluna
            for campo, coluna in novo_mapeamento.items()
            if coluna and coluna != "__nenhuma__"
        }

        set_state("mapeamento_manual", mapeamento_filtrado)
        set_state("df_saida", None)
        set_state("validacao_ok", False)
        set_state("validacao_erros", [])
        st.success("✅ Ajuste manual aplicado com sucesso.")
        st.rerun()


# =========================================================
# PROCESSAMENTO
# =========================================================
def processar_planilha(df: pd.DataFrame):
    tipo = get_state("tipo_planilha", "cadastro")
    mapeamento_manual = get_state("mapeamento_manual", {})

    if tipo == "cadastro":
        df_saida, mapeamento_final = mapear_cadastro_bling(df, mapeamento_manual)
        validacao_ok, erros = validar_cadastro_bling(df_saida)
    else:
        df_saida, mapeamento_final = mapear_estoque_bling(df, mapeamento_manual)
        validacao_ok, erros = validar_estoque_bling(df_saida)

    set_state("df_saida", df_saida)
    set_state("mapeamento_final", mapeamento_final)
    set_state("validacao_ok", validacao_ok)
    set_state("validacao_erros", erros)


# =========================================================
# BLOCO DE PROCESSAMENTO
# =========================================================
def bloco_processamento(df: pd.DataFrame):
    st.subheader("⚙️ Processamento")

    if st.button("🚀 Gerar planilha no padrão Bling", key="btn_gerar_planilha_bling"):
        processar_planilha(df)

        if get_state("validacao_ok", False):
            st.success("✅ Planilha processada com sucesso.")
        else:
            st.warning("⚠️ Planilha gerada, mas existem ajustes recomendados.")


# =========================================================
# BLOCO DE VALIDAÇÃO
# =========================================================
def bloco_validacao():
    st.subheader("✅ Validação")

    df_saida = get_state("df_saida")

    if df_saida is None:
        st.info("Processe a planilha para ver a validação.")
        return

    if get_state("validacao_ok", False):
        st.success("✅ Validação concluída sem erros críticos.")
    else:
        st.warning("⚠️ Foram encontrados pontos de atenção:")

    erros = get_state("validacao_erros", [])

    if erros:
        for erro in erros:
            st.write(f"- {erro}")
    else:
        st.caption("Nenhum erro encontrado.")


# =========================================================
# PAINEL REAL DE MAPEAMENTO FINAL
# =========================================================
def painel_mapeamento_final():
    st.subheader("✅ Painel real de mapeamento final")

    mapeamento_final = get_state("mapeamento_final", {})

    if not mapeamento_final:
        st.info("Nenhum mapeamento final disponível.")
        return

    df_map = pd.DataFrame(
        [
            {"campo_destino": campo, "coluna_origem": coluna}
            for campo, coluna in mapeamento_final.items()
        ]
    )

    st.dataframe(df_map, use_container_width=True, hide_index=True)


# =========================================================
# BLOCO DE DOWNLOAD
# =========================================================
def bloco_download():
    st.subheader("📥 Download da planilha final")

    df_saida = get_state("df_saida")
    tipo = get_state("tipo_planilha", "cadastro")

    if df_saida is None or df_saida.empty:
        st.info("Processe a planilha para liberar o download.")
        return

    nome_arquivo = f"bling_{tipo}.xlsx"
    excel_bytes = salvar_excel_bytes(df_saida)

    st.download_button(
        label=f"⬇️ Baixar planilha {tipo}",
        data=excel_bytes,
        file_name=nome_arquivo,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="btn_download_planilha_final"
    )


# =========================================================
# MAIN
# =========================================================
def main():
    configurar_pagina()
    iniciar_estado()
    barra_lateral()
    bloco_upload()

    df = get_state("df_planilha")

    if df is None:
        st.info("Envie uma planilha para começar.")
        return

    st.divider()

    preview(
        df=df,
        nome="Planilha carregada",
        colunas_detectadas=get_state("colunas_detectadas", {}),
        mapeamento_manual=get_state("mapeamento_manual", {}),
        mapeamento_final=get_state("mapeamento_final", {}),
    )

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        if st.button("👁️ Mostrar painel real de ajuste manual", key="btn_show_ajuste_real"):
            set_state("painel_real_ajuste_manual_aberto", True)

    with col2:
        if st.button("❌ Ocultar painel real de ajuste manual", key="btn_hide_ajuste_real"):
            set_state("painel_real_ajuste_manual_aberto", False)

    if get_state("painel_real_ajuste_manual_aberto", False):
        painel_ajuste_manual(df)

    st.divider()

    bloco_processamento(df)

    st.divider()

    bloco_validacao()

    st.divider()

    col3, col4 = st.columns(2)

    with col3:
        if st.button("👁️ Mostrar painel real de mapeamento final", key="btn_show_map_real"):
            set_state("painel_real_mapeamento_final_aberto", True)

    with col4:
        if st.button("❌ Ocultar painel real de mapeamento final", key="btn_hide_map_real"):
            set_state("painel_real_mapeamento_final_aberto", False)

    if get_state("painel_real_mapeamento_final_aberto", False):
        painel_mapeamento_final()

    st.divider()

    bloco_download()


if __name__ == "__main__":
    main()
