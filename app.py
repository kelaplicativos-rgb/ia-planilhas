import re
import unicodedata
import pandas as pd
import streamlit as st

from bling_app_zero.core.leitor import carregar_planilha
from bling_app_zero.core.mapeamento_bling import (
    detectar_colunas,
    mapear_cadastro_bling,
    mapear_estoque_bling,
)
from bling_app_zero.core.validacao_bling import (
    validar_cadastro_bling,
    validar_estoque_bling,
)
from bling_app_zero.utils.excel import (
    ler_planilha,
    salvar_excel_bytes,
    salvar_txt_bytes,
    bloco_toggle,
)


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
        "ultima_chave_arquivo": "",
        "validacao_erros": [],
        "validacao_avisos": [],
        "validacao_ok": False,
        "ultimo_mapeamento_auto": {},
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def log(msg: str) -> None:
    st.session_state.logs.append(str(msg))


def resetar_validacao() -> None:
    st.session_state["validacao_erros"] = []
    st.session_state["validacao_avisos"] = []
    st.session_state["validacao_ok"] = False


def limpar_tudo() -> None:
    chaves_base = {
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
        "ultima_chave_arquivo": "",
        "validacao_erros": [],
        "validacao_avisos": [],
        "validacao_ok": False,
        "ultimo_mapeamento_auto": {},
    }

    for chave, valor in chaves_base.items():
        st.session_state[chave] = valor

    for chave in list(st.session_state.keys()):
        if chave.startswith("map_") or chave.startswith("toggle_"):
            del st.session_state[chave]


# =========================================================
# HELPERS
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


def carregar_modelo_bling(arquivo):
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
        st.error(f"Erro ao ler modelo Bling: {e}")
        return None


def montar_opcoes_colunas(df: pd.DataFrame):
    if df is None or df.empty:
        return [""]
    return [""] + list(df.columns)


def select_coluna(label: str, opcoes, valor_atual, key: str) -> str:
    valor_atual = valor_atual if valor_atual in opcoes else ""
    idx = opcoes.index(valor_atual) if valor_atual in opcoes else 0
    return st.selectbox(label, options=opcoes, index=idx, key=key)


def construir_mapa_manual(df: pd.DataFrame, mapa_auto: dict) -> dict:
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
            "Descrição curta (descrição real do produto)",
            opcoes,
            mapa_auto.get("descricao_curta"),
            "map_descricao_curta",
        )
        mapa_manual["categoria"] = select_coluna(
            "Categoria", opcoes, mapa_auto.get("categoria"), "map_categoria"
        )
        mapa_manual["gtin"] = select_coluna(
            "GTIN / EAN", opcoes, mapa_auto.get("gtin"), "map_gtin"
        )

    with c2:
        mapa_manual["preco"] = select_coluna(
            "Preço", opcoes, mapa_auto.get("preco"), "map_preco"
        )
        mapa_manual["marca"] = select_coluna(
            "Marca", opcoes, mapa_auto.get("marca"), "map_marca"
        )
        mapa_manual["imagem"] = select_coluna(
            "Imagem principal", opcoes, mapa_auto.get("imagem"), "map_imagem"
        )
        mapa_manual["situacao"] = select_coluna(
            "Situação", opcoes, mapa_auto.get("situacao"), "map_situacao"
        )
        mapa_manual["unidade"] = select_coluna(
            "Unidade", opcoes, mapa_auto.get("unidade"), "map_unidade"
        )

    with c3:
        mapa_manual["estoque"] = select_coluna(
            "Estoque / Quantidade", opcoes, mapa_auto.get("estoque"), "map_estoque"
        )
        mapa_manual["peso"] = select_coluna(
            "Peso", opcoes, mapa_auto.get("peso"), "map_peso"
        )
        mapa_manual["link_externo"] = select_coluna(
            "Link externo (será ignorado e ficará vazio)",
            opcoes,
            mapa_auto.get("link_externo"),
            "map_link_externo",
        )

    return {k: (v if limpar_texto(v) else None) for k, v in mapa_manual.items()}


def montar_df_colunas_automaticas(mapa_auto: dict) -> pd.DataFrame:
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
        "categoria": "Categoria",
        "gtin": "GTIN / EAN",
        "peso": "Peso",
    }

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
        "categoria",
        "gtin",
        "peso",
    ]

    linhas = []
    for campo in ordem:
        linhas.append(
            {
                "Campo": nomes_exibicao.get(campo, campo),
                "Coluna detectada": mapa_auto.get(campo) or "",
            }
        )

    return pd.DataFrame(linhas)


def montar_df_mapeamento_final(
    tipo_processamento: str,
    mapa_final: dict,
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
        "categoria": "Categoria",
        "gtin": "GTIN / EAN",
        "peso": "Peso",
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
            "categoria",
            "gtin",
            "peso",
        ]
    else:
        ordem = ["codigo", "nome", "estoque", "preco"]

    linhas = [{"Campo": "Modelo Bling anexado", "Coluna escolhida": modelo_nome or ""}]

    for campo in ordem:
        linhas.append(
            {
                "Campo": nomes_exibicao.get(campo, campo),
                "Coluna escolhida": mapa_final.get(campo) or "",
            }
        )

    linhas.append(
        {
            "Campo": "Regra fixa",
            "Coluna escolhida": (
                "descrição = título/nome do produto | "
                "descrição curta = descrição real do produto | "
                "vídeo = vazio | "
                "link externo = vazio"
            ),
        }
    )

    return pd.DataFrame(linhas)


def exibir_validacao() -> None:
    erros = st.session_state.get("validacao_erros", [])
    avisos = st.session_state.get("validacao_avisos", [])
    ok = st.session_state.get("validacao_ok", False)

    st.subheader("Validação antes do download")

    if ok:
        st.success("✅ Validação aprovada. A planilha está liberada para download.")

    for aviso in avisos:
        st.warning(aviso)

    if erros:
        st.error("❌ Download bloqueado. Corrija os pontos abaixo antes de baixar.")
        for erro in erros:
            st.error(f"- {erro}")


# =========================================================
# ADAPTAÇÃO AO MODELO REAL DO BLING
# =========================================================
def encontrar_coluna_modelo(modelo_df: pd.DataFrame, candidatos: list[str]):
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


def localizar_campos_modelo_cadastro(modelo_df: pd.DataFrame) -> dict:
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
        "categoria": encontrar_coluna_modelo(modelo_df, ["categoria", "grupo", "departamento"]),
        "peso_liquido": encontrar_coluna_modelo(modelo_df, ["peso liquido", "peso líquido", "peso"]),
        "gtin": encontrar_coluna_modelo(modelo_df, ["gtin", "ean", "codigo barras", "código barras"]),
    }


def localizar_campos_modelo_estoque(modelo_df: pd.DataFrame) -> dict:
    return {
        "id": encontrar_coluna_modelo(modelo_df, ["id"]),
        "codigo": encontrar_coluna_modelo(modelo_df, ["codigo", "código", "sku", "codigo produto"]),
        "nome": encontrar_coluna_modelo(modelo_df, ["nome", "nome produto", "produto", "descricao produto"]),
        "deposito": encontrar_coluna_modelo(modelo_df, ["deposito", "depósito", "almoxarifado"]),
        "estoque": encontrar_coluna_modelo(modelo_df, ["estoque", "saldo", "quantidade", "balanco", "balanço"]),
        "preco_unitario": encontrar_coluna_modelo(modelo_df, ["preco unitario", "preço unitário", "preco", "preço"]),
    }


def adaptar_cadastro_ao_modelo_real(df_base: pd.DataFrame, modelo_df: pd.DataFrame) -> pd.DataFrame:
    saida = pd.DataFrame("", index=range(len(df_base)), columns=list(modelo_df.columns))
    campos = localizar_campos_modelo_cadastro(modelo_df)

    mapeamento_base = {
        "codigo": "codigo",
        "nome": "nome",
        "unidade": "unidade",
        "preco": "preco",
        "situacao": "situacao",
        "marca": "marca",
        "descricao_curta": "descricao_curta",
        "descricao": "descricao",
        "video": "video",
        "imagem_1": "imagem_1",
        "imagem_2": "imagem_2",
        "imagem_3": "imagem_3",
        "imagem_4": "imagem_4",
        "imagem_5": "imagem_5",
        "link_externo": "link_externo",
        "categoria": "categoria",
        "peso_liquido": "peso_liquido",
        "gtin": "gtin",
    }

    for campo_modelo, campo_base in mapeamento_base.items():
        col_modelo = campos.get(campo_modelo)
        if col_modelo and campo_base in df_base.columns:
            saida[col_modelo] = df_base[campo_base].astype(str)

    if campos.get("id"):
        saida[campos["id"]] = ""

    if campos.get("video"):
        saida[campos["video"]] = ""

    if campos.get("link_externo"):
        saida[campos["link_externo"]] = ""

    return saida


def adaptar_estoque_ao_modelo_real(df_base: pd.DataFrame, modelo_df: pd.DataFrame, deposito: str) -> pd.DataFrame:
    saida = pd.DataFrame("", index=range(len(df_base)), columns=list(modelo_df.columns))
    campos = localizar_campos_modelo_estoque(modelo_df)

    if campos.get("id"):
        saida[campos["id"]] = ""

    if campos.get("codigo") and "codigo" in df_base.columns:
        saida[campos["codigo"]] = df_base["codigo"].astype(str)

    if campos.get("nome") and "nome" in df_base.columns:
        saida[campos["nome"]] = df_base["nome"].astype(str)

    if campos.get("deposito"):
        saida[campos["deposito"]] = limpar_texto(deposito)

    if campos.get("estoque") and "estoque" in df_base.columns:
        saida[campos["estoque"]] = df_base["estoque"].astype(str)

    if campos.get("preco_unitario") and "preco" in df_base.columns:
        saida[campos["preco_unitario"]] = df_base["preco"].astype(str)

    return saida


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

    tipos_aceitos = ["xlsx", "xls", "csv", "zip"]

    arquivo_origem = st.file_uploader(
        "1) Planilha do fornecedor",
        type=tipos_aceitos,
        key="upload_origem",
    )

    col_modelo_1, col_modelo_2 = st.columns(2)

    with col_modelo_1:
        modelo_cadastro = st.file_uploader(
            "2) Modelo de cadastro do Bling",
            type=tipos_aceitos,
            key="upload_modelo_cadastro",
        )

    with col_modelo_2:
        modelo_estoque = st.file_uploader(
            "3) Modelo de estoque do Bling",
            type=tipos_aceitos,
            key="upload_modelo_estoque",
        )

    if arquivo_origem is not None:
        chave_atual = f"{arquivo_origem.name}-{getattr(arquivo_origem, 'size', 0)}"
        if st.session_state["ultima_chave_arquivo"] != chave_atual:
            df = carregar_planilha(arquivo_origem)

            if df is None or df.empty:
                st.error("Erro ao ler arquivo de origem.")
                log("Erro ao ler arquivo de origem.")
                return

            st.session_state["df_origem"] = df
            st.session_state["nome_arquivo_origem"] = arquivo_origem.name
            st.session_state["df_saida"] = None
            st.session_state["mapa_manual"] = {}
            st.session_state["ultima_chave_arquivo"] = chave_atual
            st.session_state["ultimo_mapeamento_auto"] = detectar_colunas(df)
            resetar_validacao()

            for k in list(st.session_state.keys()):
                if k.startswith("map_"):
                    del st.session_state[k]

            log(f"Arquivo de origem carregado: {arquivo_origem.name}")
            log(f"Linhas: {len(df)} | Colunas: {len(df.columns)}")

    if modelo_cadastro is not None:
        modelo_df = carregar_modelo_bling(modelo_cadastro)
        if modelo_df is None:
            st.error("Erro ao ler modelo de cadastro.")
            log("Erro ao ler modelo de cadastro.")
            return

        st.session_state["modelo_cadastro_raw"] = modelo_df
        st.session_state["nome_modelo_cadastro"] = modelo_cadastro.name
        resetar_validacao()

    if modelo_estoque is not None:
        modelo_df = carregar_modelo_bling(modelo_estoque)
        if modelo_df is None:
            st.error("Erro ao ler modelo de estoque.")
            log("Erro ao ler modelo de estoque.")
            return

        st.session_state["modelo_estoque_raw"] = modelo_df
        st.session_state["nome_modelo_estoque"] = modelo_estoque.name
        resetar_validacao()

    df = st.session_state["df_origem"]

    if df is None:
        st.info("Anexe a planilha do fornecedor para começar.")
        return

    mapa_auto = st.session_state.get("ultimo_mapeamento_auto") or detectar_colunas(df)

    st.success(f"✅ Arquivo de origem carregado: {st.session_state['nome_arquivo_origem']}")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Linhas", len(df))
    with c2:
        st.metric("Colunas", len(df.columns))
    with c3:
        st.metric("Campos detectados", len([v for v in mapa_auto.values() if v]))

    if bloco_toggle("Preview", "preview"):
        st.dataframe(df.head(1), use_container_width=True)

    if bloco_toggle("Ajuste manual das colunas", "ajuste_manual"):
        st.caption("Se alguma coluna foi identificada errado, ajuste aqui manualmente.")
        mapa_final_temp = construir_mapa_manual(df, mapa_auto)
        st.session_state["mapa_manual"] = mapa_final_temp
        resetar_validacao()

        st.info(
            "Regra fixa do sistema: a descrição real do produto vai para "
            "'descrição curta'. A coluna 'descrição' recebe o título/nome do produto. "
            "A coluna 'vídeo' fica vazia. A coluna 'link externo' também fica vazia."
        )

    mapa_final = st.session_state.get("mapa_manual") or mapa_auto
    mapa_final["link_externo"] = None

    modelo_nome_exibicao = (
        st.session_state["nome_modelo_cadastro"]
        if tipo_processamento == "Cadastro de produtos"
        else st.session_state["nome_modelo_estoque"]
    )

    if bloco_toggle("Mapeamento final que será usado", "mapeamento_final"):
        df_mapeamento_final = montar_df_mapeamento_final(
            tipo_processamento=tipo_processamento,
            mapa_final=mapa_final,
            modelo_nome=modelo_nome_exibicao or "",
        )
        st.dataframe(df_mapeamento_final, use_container_width=True, hide_index=True)

        if st.session_state["df_saida"] is not None:
            st.dataframe(st.session_state["df_saida"].head(20), use_container_width=True)

    if bloco_toggle("Colunas identificadas automaticamente", "colunas_auto"):
        df_auto = montar_df_colunas_automaticas(mapa_auto)
        st.dataframe(df_auto, use_container_width=True, hide_index=True)

    if tipo_processamento == "Cadastro de produtos":
        modelo_cadastro_df = st.session_state["modelo_cadastro_raw"]

        if modelo_cadastro_df is None:
            st.warning("⚠️ Anexe o modelo de cadastro do Bling.")
        else:
            if st.button("Gerar planilha de cadastro", use_container_width=True):
                try:
                    saida_base, _ = mapear_cadastro_bling(
                        df=df,
                        mapeamento_manual=mapa_final,
                    )
                    saida = adaptar_cadastro_ao_modelo_real(saida_base, modelo_cadastro_df)
                    erros, avisos = validar_cadastro_bling(saida)

                    st.session_state["df_saida"] = saida
                    st.session_state["validacao_erros"] = erros
                    st.session_state["validacao_avisos"] = avisos
                    st.session_state["validacao_ok"] = len(erros) == 0

                    for aviso in avisos:
                        log(f"Aviso: {aviso}")

                    for erro in erros:
                        log(f"Erro de validação: {erro}")

                    if erros:
                        st.error("❌ A planilha foi gerada, mas o download foi bloqueado pela validação.")
                    else:
                        log(f"Cadastro gerado com {len(saida)} linhas.")
                        log(f"Modelo de cadastro usado: {st.session_state['nome_modelo_cadastro']}")
                        st.success("✅ Planilha de cadastro gerada e validada com sucesso.")

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
                    saida_base, _ = mapear_estoque_bling(
                        df=df,
                        mapeamento_manual=mapa_final,
                    )
                    saida = adaptar_estoque_ao_modelo_real(saida_base, modelo_estoque_df, deposito)
                    erros, avisos = validar_estoque_bling(saida)

                    st.session_state["df_saida"] = saida
                    st.session_state["validacao_erros"] = erros
                    st.session_state["validacao_avisos"] = avisos
                    st.session_state["validacao_ok"] = len(erros) == 0

                    for aviso in avisos:
                        log(f"Aviso: {aviso}")

                    for erro in erros:
                        log(f"Erro de validação: {erro}")

                    if erros:
                        st.error("❌ A planilha foi gerada, mas o download foi bloqueado pela validação.")
                    else:
                        log(f"Estoque gerado com {len(saida)} linhas.")
                        log(f"Modelo de estoque usado: {st.session_state['nome_modelo_estoque']}")
                        log(f"Depósito informado: {deposito}")
                        st.success("✅ Planilha de estoque gerada e validada com sucesso.")

                except Exception as e:
                    st.error(f"Erro ao gerar estoque: {e}")
                    log(f"Erro ao gerar estoque: {e}")

    df_saida = st.session_state["df_saida"]

    if df_saida is not None:
        st.divider()
        exibir_validacao()

        if st.session_state.get("validacao_ok", False):
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

    logs_txt = "\n".join(st.session_state["logs"]) if st.session_state["logs"] else "Nenhum log gerado."

    if bloco_toggle("Logs", "logs"):
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
