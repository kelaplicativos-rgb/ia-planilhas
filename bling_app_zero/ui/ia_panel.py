
from __future__ import annotations

import io
import re
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st


# ============================================================
# LEITURA DE ARQUIVOS
# ============================================================


def _ler_arquivo(upload) -> Optional[pd.DataFrame]:
    if upload is None:
        return None

    nome = (upload.name or "").lower()
    bruto = upload.getvalue()

    try:
        if nome.endswith(".csv"):
            for enc in ("utf-8", "utf-8-sig", "latin1"):
                for sep in (None, ";", ",", "\t", "|"):
                    try:
                        df = pd.read_csv(
                            io.BytesIO(bruto),
                            encoding=enc,
                            sep=sep,
                            engine="python",
                        )
                        if df is not None and not df.empty:
                            return df
                    except Exception:
                        continue

        if nome.endswith(".xlsx") or nome.endswith(".xls"):
            try:
                return pd.read_excel(io.BytesIO(bruto), engine="openpyxl")
            except Exception:
                return pd.read_excel(io.BytesIO(bruto))

    except Exception:
        return None

    return None


# ============================================================
# HELPERS
# ============================================================


def _normalizar_texto(valor: Any) -> str:
    if valor is None:
        return ""
    texto = str(valor).strip()
    if texto.lower() in {"nan", "none", "nat"}:
        return ""
    return texto


def _slug(valor: str) -> str:
    texto = _normalizar_texto(valor).lower()
    texto = re.sub(r"[^a-z0-9]+", "_", texto)
    return texto.strip("_")


def _tem_df(valor: Any) -> bool:
    try:
        return valor is not None and hasattr(valor, "empty") and not valor.empty
    except Exception:
        return False


def _normalizar_coluna(coluna: str) -> str:
    texto = _normalizar_texto(coluna).lower()
    texto = (
        texto.replace("ç", "c")
        .replace("á", "a")
        .replace("à", "a")
        .replace("ã", "a")
        .replace("â", "a")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ô", "o")
        .replace("õ", "o")
        .replace("ú", "u")
    )
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def _detectar_operacao(prompt: str, radio_operacao: str) -> str:
    base = _normalizar_coluna(prompt)

    if "estoque" in base or "deposito" in base or "depósito" in base:
        return "estoque"
    if "cadastro" in base or "cadastrar" in base or "produto" in base:
        return "cadastro"

    return "cadastro" if "Cadastro" in radio_operacao else "estoque"


def _detectar_origem(prompt: str, url_site: str, arquivo_origem) -> str:
    texto = _normalizar_coluna(prompt)

    if _normalizar_texto(url_site):
        return "site"
    if arquivo_origem is not None:
        return "planilha"
    if "site" in texto or "buscar no site" in texto or "url" in texto:
        return "site"
    return "planilha"


def _extrair_deposito(prompt: str, deposito_digitado: str) -> str:
    if _normalizar_texto(deposito_digitado):
        return _normalizar_texto(deposito_digitado)

    texto = _normalizar_texto(prompt)
    match = re.search(r"dep[oó]sito\s*[:=-]?\s*([A-Za-z0-9 _\-/]+)", texto, re.IGNORECASE)
    if match:
        return _normalizar_texto(match.group(1))

    return ""


def _coluna_por_candidatos(colunas: List[str], candidatos: List[str]) -> str:
    mapa = {_normalizar_coluna(col): col for col in colunas}

    for candidato in candidatos:
        chave = _normalizar_coluna(candidato)
        if chave in mapa:
            return mapa[chave]

    for col in colunas:
        ncol = _normalizar_coluna(col)
        for candidato in candidatos:
            if _normalizar_coluna(candidato) in ncol:
                return col

    return ""


def _gerar_mapeamento_sugerido(df_base_mapeamento: pd.DataFrame, tipo_operacao: str) -> Tuple[Dict[str, str], List[str]]:
    colunas = list(df_base_mapeamento.columns)
    mapping: Dict[str, str] = {}

    mapping["Código"] = _coluna_por_candidatos(
        colunas,
        ["codigo", "codigo produto", "codigo fornecedor", "sku", "ref", "referencia", "id"],
    )

    mapping["Descrição"] = _coluna_por_candidatos(
        colunas,
        ["descricao", "nome", "produto", "titulo", "descrição"],
    )

    if tipo_operacao == "estoque":
        mapping["Balanço (OBRIGATÓRIO)"] = _coluna_por_candidatos(
            colunas,
            ["estoque", "saldo", "quantidade", "qtde", "balanco", "balanço"],
        )
        mapping["Preço unitário (OBRIGATÓRIO)"] = _coluna_por_candidatos(
            colunas,
            ["preco", "valor", "preco venda", "preco unitario", "preço", "preço unitário"],
        )
        mapping["Depósito (OBRIGATÓRIO)"] = ""
    else:
        mapping["Descrição Curta"] = _coluna_por_candidatos(
            colunas,
            ["descricao curta", "descricao", "nome", "produto", "titulo"],
        )
        mapping["Preço de venda"] = _coluna_por_candidatos(
            colunas,
            ["preco", "valor", "preco venda", "preço", "valor venda"],
        )
        mapping["GTIN/EAN"] = _coluna_por_candidatos(
            colunas,
            ["gtin", "ean", "codigo barras", "codigo de barras"],
        )
        mapping["Categoria"] = _coluna_por_candidatos(
            colunas,
            ["categoria", "departamento", "grupo", "colecao", "coleção"],
        )
        mapping["URL Imagens"] = _coluna_por_candidatos(
            colunas,
            ["imagem", "imagens", "url imagem", "url imagens", "foto", "fotos"],
        )

    campos_pendentes = [campo for campo, origem in mapping.items() if not _normalizar_texto(origem)]
    return mapping, campos_pendentes


def _montar_plano(
    prompt: str,
    tipo_operacao: str,
    origem_tipo: str,
    deposito_nome: str,
    modelo_nome: str,
    origem_nome: str,
    url_site: str,
    mapping: Dict[str, str],
    campos_pendentes: List[str],
) -> Dict[str, Any]:
    proximas_acoes = [
        "Ler a origem",
        "Normalizar a base",
        "Aplicar defaults do fluxo",
        "Montar mapeamento inicial",
        "Perguntar campos pendentes",
        "Validar base final do Bling",
    ]

    return {
        "origem": origem_tipo,
        "operacao": tipo_operacao,
        "modelo_bling": modelo_nome,
        "arquivo_origem": origem_nome,
        "url_site": _normalizar_texto(url_site),
        "deposito": deposito_nome,
        "prompt_usuario": _normalizar_texto(prompt),
        "mapeamento_colunas": mapping,
        "campos_pendentes": campos_pendentes,
        "proximas_acoes": proximas_acoes,
    }


def _preview_mapping(mapping: Dict[str, str]) -> pd.DataFrame:
    linhas = []
    for campo, origem in mapping.items():
        linhas.append(
            {
                "Campo do modelo": campo,
                "Origem sugerida": origem or "PENDENTE",
            }
        )
    return pd.DataFrame(linhas)


# ============================================================
# MODELOS / ORIGEM
# ============================================================


def _render_modelos() -> Tuple[str, Optional[pd.DataFrame], str]:
    st.markdown("#### Modelos do Bling")

    tipo_operacao_label = st.radio(
        "Selecione o fluxo",
        ["Cadastro de produtos", "Atualização de estoque"],
        horizontal=False,
        key="tipo_operacao_radio",
    )

    tipo_operacao = "cadastro" if "Cadastro" in tipo_operacao_label else "estoque"
    st.session_state["tipo_operacao"] = tipo_operacao
    st.session_state["tipo_operacao_bling"] = tipo_operacao

    cadastro_upload = st.file_uploader(
        "Modelo do Bling para cadastro",
        type=["csv", "xlsx", "xls"],
        key="modelo_cadastro_upload",
    )

    estoque_upload = st.file_uploader(
        "Modelo do Bling para estoque",
        type=["csv", "xlsx", "xls"],
        key="modelo_estoque_upload",
    )

    df_cadastro = _ler_arquivo(cadastro_upload) if cadastro_upload else None
    df_estoque = _ler_arquivo(estoque_upload) if estoque_upload else None

    if cadastro_upload is not None:
        st.session_state["modelo_cadastro_nome"] = cadastro_upload.name
    if estoque_upload is not None:
        st.session_state["modelo_estoque_nome"] = estoque_upload.name

    df_modelo_base: Optional[pd.DataFrame] = None
    modelo_nome = ""

    if tipo_operacao == "cadastro" and df_cadastro is not None:
        df_modelo_base = df_cadastro.head(0).copy()
        modelo_nome = _normalizar_texto(cadastro_upload.name if cadastro_upload else "")
    elif tipo_operacao == "estoque" and df_estoque is not None:
        df_modelo_base = df_estoque.head(0).copy()
        modelo_nome = _normalizar_texto(estoque_upload.name if estoque_upload else "")

    if df_modelo_base is not None:
        st.session_state["df_modelo_base"] = df_modelo_base.copy()
        st.success("Modelo base carregado para o fluxo selecionado.")
        with st.expander("Ver colunas do modelo", expanded=False):
            st.dataframe(pd.DataFrame({"Colunas do modelo": list(df_modelo_base.columns)}), use_container_width=True)

    return tipo_operacao, df_modelo_base, modelo_nome


def _render_origem() -> Tuple[Optional[pd.DataFrame], str, str]:
    st.markdown("#### Planilha de origem ou busca por site")

    modo_origem = st.radio(
        "Como deseja informar a origem?",
        ["Anexar planilha fornecedora", "Buscar pelo site"],
        horizontal=False,
        key="modo_origem_radio",
    )

    df_origem: Optional[pd.DataFrame] = None
    origem_nome = ""
    url_site = ""

    if "planilha" in modo_origem.lower():
        origem_upload = st.file_uploader(
            "Arquivo com os produtos da fornecedora",
            type=["csv", "xlsx", "xls"],
            key="arquivo_origem_upload",
        )

        if origem_upload is not None:
            df_origem = _ler_arquivo(origem_upload)
            if _tem_df(df_origem):
                st.session_state["df_origem"] = df_origem.copy()
                st.session_state["arquivo_origem_nome"] = origem_upload.name
                origem_nome = origem_upload.name
                st.success(f"Origem carregada com {len(df_origem)} linhas.")
                with st.expander("Ver origem", expanded=False):
                    st.dataframe(df_origem.head(50), use_container_width=True)
            else:
                st.error("Não foi possível ler a planilha de origem.")
    else:
        url_site = st.text_input(
            "URL do site ou da categoria",
            key="url_site_origem",
            placeholder="https://site-fornecedor.com/categoria ou página inicial",
        )

        st.info(
            "Quando a origem for por site, a IA interpreta o pedido e prepara o fluxo. "
            "A coleta real pode ser executada na próxima etapa do pipeline."
        )

        if _normalizar_texto(url_site):
            origem_nome = url_site
            st.session_state["url_site_origem"] = url_site

    return df_origem, origem_nome, url_site


# ============================================================
# IA PANEL
# ============================================================


def render_ia_panel() -> None:
    st.markdown("### Origem dos dados")
    st.caption(
        "Aqui a IA interpreta o pedido, recebe a base fornecedora, o modelo do Bling "
        "e já prepara o mapeamento inicial para cadastro ou atualização de estoque."
    )

    with st.container(border=True):
        st.markdown("#### Comando da IA")
        prompt = st.text_area(
            "Descreva o que deseja fazer",
            key="ia_prompt_home",
            height=180,
            placeholder=(
                "Exemplo:\n"
                "Quero atualizar estoque da Mega Center usando a planilha fornecedora, "
                "mapear automaticamente com o modelo do Bling e perguntar só os campos pendentes. "
                "Depósito: iFood."
            ),
        )

        deposito_digitado = st.text_input(
            "Nome do depósito",
            key="deposito_nome_input",
            placeholder="Ex.: iFood, CD Principal, Loja 1",
        )

    with st.container(border=True):
        tipo_operacao, df_modelo_base, modelo_nome = _render_modelos()

    with st.container(border=True):
        df_origem, origem_nome, url_site = _render_origem()

    with st.container(border=True):
        st.markdown("#### Ação da IA")
        st.caption(
            "A IA monta o plano do fluxo, identifica a operação, prepara a base de mapeamento "
            "e aponta os campos que ainda precisam de confirmação manual."
        )

        pode_interpretar = bool(
            _normalizar_texto(prompt)
            or _tem_df(df_origem)
            or _normalizar_texto(url_site)
        )

        interpretar = st.button(
            "Rodar IA e preparar mapeamento",
            use_container_width=True,
            disabled=not pode_interpretar,
        )

    if interpretar:
        tipo_operacao_detectado = _detectar_operacao(prompt, st.session_state.get("tipo_operacao_radio", ""))
        origem_tipo = _detectar_origem(prompt, url_site, st.session_state.get("arquivo_origem_upload"))
        deposito_nome = _extrair_deposito(prompt, deposito_digitado)

        st.session_state["tipo_operacao"] = tipo_operacao_detectado
        st.session_state["tipo_operacao_bling"] = tipo_operacao_detectado
        st.session_state["deposito_nome"] = deposito_nome

        df_base_mapeamento: Optional[pd.DataFrame] = None

        if _tem_df(df_origem):
            df_base_mapeamento = df_origem.copy()
        elif _normalizar_texto(url_site):
            df_base_mapeamento = pd.DataFrame()
        else:
            df_base_mapeamento = None

        mapping: Dict[str, str] = {}
        campos_pendentes: List[str] = []

        if _tem_df(df_base_mapeamento):
            mapping, campos_pendentes = _gerar_mapeamento_sugerido(
                df_base_mapeamento=df_base_mapeamento,
                tipo_operacao=tipo_operacao_detectado,
            )
            st.session_state["df_base_mapeamento"] = df_base_mapeamento.copy()
        else:
            st.session_state["df_base_mapeamento"] = pd.DataFrame()

        st.session_state["mapeamento_colunas"] = mapping.copy()
        st.session_state["campos_pendentes"] = campos_pendentes.copy()

        plano = _montar_plano(
            prompt=prompt,
            tipo_operacao=tipo_operacao_detectado,
            origem_tipo=origem_tipo,
            deposito_nome=deposito_nome,
            modelo_nome=modelo_nome,
            origem_nome=origem_nome,
            url_site=url_site,
            mapping=mapping,
            campos_pendentes=campos_pendentes,
        )

        st.session_state["agent_plan"] = plano
        st.session_state["agent_outputs"] = {
            "mapeamento_colunas": mapping.copy(),
            "campos_pendentes": campos_pendentes.copy(),
            "df_base_mapeamento": "df_base_mapeamento",
            "resultado": plano,
        }

        st.success("IA executada. Plano interpretado e mapeamento inicial preparado.")

    plano_salvo = st.session_state.get("agent_plan")
    mapping_salvo = st.session_state.get("mapeamento_colunas", {})
    campos_pendentes_salvos = st.session_state.get("campos_pendentes", [])
    df_base_salvo = st.session_state.get("df_base_mapeamento")

    if plano_salvo:
        with st.container(border=True):
            st.markdown("#### Plano interpretado")
            st.json(plano_salvo)

    if isinstance(mapping_salvo, dict) and mapping_salvo:
        with st.container(border=True):
            st.markdown("#### Mapeamento inicial da IA")
            st.dataframe(_preview_mapping(mapping_salvo), use_container_width=True)

    if isinstance(campos_pendentes_salvos, list):
        with st.container(border=True):
            st.markdown("#### Campos pendentes")
            if campos_pendentes_salvos:
                for campo in campos_pendentes_salvos:
                    st.warning(f"A IA ainda precisa que você confirme este campo: {campo}")
            else:
                st.success("A IA conseguiu sugerir todos os campos principais do modelo.")

    if _tem_df(df_base_salvo):
        with st.container(border=True):
            st.markdown("#### Preview da base para mapeamento")
            st.dataframe(df_base_salvo.head(30), use_container_width=True)

    with st.container(border=True):
        st.markdown("#### Regras do fluxo")
        st.caption("Na próxima etapa, a precificação só avança quando todos os campos obrigatórios forem preenchidos.")
        st.caption("Depois disso, o sistema pergunta para onde vão os campos que ele não conseguir mapear sozinho.")
        st.caption("Antes do download, haverá um preview final para confirmação.")
