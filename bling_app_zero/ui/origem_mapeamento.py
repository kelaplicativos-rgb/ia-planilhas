from __future__ import annotations

from io import BytesIO
import re

import pandas as pd
import streamlit as st

from bling_app_zero.core.mapeamento_auto import sugestao_automatica


# ==========================================================
# HELPERS
# ==========================================================
def _safe_dataframe_preview(df: pd.DataFrame, rows: int = 20):
    if df is None:
        return pd.DataFrame()
    try:
        if len(df.columns) == 0:
            return pd.DataFrame()
        if df.empty:
            return pd.DataFrame(columns=df.columns)
        return df.head(rows)
    except Exception:
        return pd.DataFrame()


def _build_log():
    logs = st.session_state.get("logs", [])
    texto = "\n".join(logs) if logs else "Sem logs"
    return texto


def _safe_df_dados(df):
    try:
        if df is None:
            return None
        if len(df.columns) == 0:
            return None
        if df.empty:
            return None
        return df
    except Exception:
        return None


def _safe_df_modelo(df):
    try:
        if df is None:
            return None
        if len(df.columns) == 0:
            return None
        return df
    except Exception:
        return None


def _normalizar_nome(texto: str) -> str:
    texto = str(texto or "").strip().lower()
    texto = re.sub(r"\s+", " ", texto)
    return texto


def _slug(texto: str) -> str:
    texto = _normalizar_nome(texto)
    texto = (
        texto.replace("á", "a")
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
        .replace("ç", "c")
    )
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _obter_modelo_ativo() -> pd.DataFrame | None:
    operacao = st.session_state.get("tipo_operacao_bling", "cadastro")
    if operacao == "cadastro":
        return _safe_df_modelo(st.session_state.get("df_modelo_cadastro"))
    return _safe_df_modelo(st.session_state.get("df_modelo_estoque"))


def _obter_nome_modelo_ativo() -> str:
    operacao = st.session_state.get("tipo_operacao_bling", "cadastro")
    if operacao == "cadastro":
        return st.session_state.get("modelo_cadastro_nome", "")
    return st.session_state.get("modelo_estoque_nome", "")


def _coluna_modelo_parece_deposito(nome_coluna: str) -> bool:
    nome = _slug(nome_coluna)
    return "deposito" in nome


def _coluna_modelo_parece_preco_venda(nome_coluna: str) -> bool:
    nome = _slug(nome_coluna)
    return "preco" in nome and "venda" in nome


def _coluna_modelo_parece_descricao(nome_coluna: str) -> bool:
    nome = _slug(nome_coluna)
    return nome == "descricao"


def _coluna_modelo_parece_descricao_curta(nome_coluna: str) -> bool:
    nome = _slug(nome_coluna)
    return "descricao curta" in nome


def _coluna_modelo_parece_situacao(nome_coluna: str) -> bool:
    nome = _slug(nome_coluna)
    return nome == "situacao"


def _coluna_modelo_parece_marca(nome_coluna: str) -> bool:
    nome = _slug(nome_coluna)
    return nome == "marca"


def _coluna_modelo_parece_codigo(nome_coluna: str) -> bool:
    nome = _slug(nome_coluna)
    return nome in {"codigo", "codigo sku", "sku", "codigo produto"}


def _coluna_modelo_parece_preco(nome_coluna: str) -> bool:
    nome = _slug(nome_coluna)
    return "preco" in nome


def _obter_deposito_manual() -> str:
    for key in [
        "deposito_nome_manual",
        "deposito_manual",
        "deposito",
        "nome_deposito",
    ]:
        valor = str(st.session_state.get(key, "")).strip()
        if valor:
            return valor
    return ""


# ==========================================================
# IA / SUGESTÃO AVANÇADA
# ==========================================================
def _aliases_por_coluna_modelo() -> dict[str, list[str]]:
    return {
        "descricao": [
            "descricao", "descrição", "nome", "produto", "titulo", "título", "nome produto"
        ],
        "descricao_curta": [
            "descricao curta", "descrição curta", "descricao", "descrição", "resumo", "detalhes"
        ],
        "marca": [
            "marca", "fabricante", "brand"
        ],
        "codigo": [
            "codigo", "código", "sku", "ref", "referencia", "referência", "cod produto"
        ],
        "preco": [
            "preco", "preço", "valor", "valor venda", "preco venda", "preço venda",
            "valor unitario", "valor unitário", "custo", "preco custo", "preço custo"
        ],
        "estoque": [
            "estoque", "quantidade", "saldo", "qtd", "qtde"
        ],
        "gtin": [
            "gtin", "ean", "codigo de barras", "código de barras", "barcode"
        ],
        "ncm": [
            "ncm"
        ],
        "deposito": [
            "deposito", "depósito"
        ],
        "situacao": [
            "situacao", "situação", "status", "ativo", "status produto"
        ],
    }


def _classificar_coluna_modelo(nome_coluna: str) -> str:
    nome = _slug(nome_coluna)

    if "descricao curta" in nome:
        return "descricao_curta"
    if nome == "descricao":
        return "descricao"
    if "marca" == nome:
        return "marca"
    if nome in {"codigo", "codigo sku", "sku", "codigo produto"}:
        return "codigo"
    if "deposito" in nome:
        return "deposito"
    if nome == "situacao":
        return "situacao"
    if "gtin" in nome or "ean" in nome or "codigo de barras" in nome:
        return "gtin"
    if nome == "ncm":
        return "ncm"
    if "estoque" in nome or "quantidade" in nome or "saldo" in nome:
        return "estoque"
    if "preco" in nome or "valor" in nome:
        return "preco"

    return ""


def _sugestao_por_alias(df_origem: pd.DataFrame, df_modelo: pd.DataFrame) -> dict[str, str]:
    aliases = _aliases_por_coluna_modelo()
    resultado: dict[str, str] = {}

    colunas_origem = [str(c) for c in df_origem.columns]

    for col_destino in df_modelo.columns:
        classe = _classificar_coluna_modelo(str(col_destino))
        if not classe:
            continue

        possiveis = aliases.get(classe, [])
        for col_origem in colunas_origem:
            nome_origem = _slug(col_origem)
            if any(alias in nome_origem for alias in possiveis):
                resultado[str(col_destino)] = str(col_origem)
                break

    return resultado


def _obter_sugestoes(df_origem: pd.DataFrame, df_modelo: pd.DataFrame) -> dict[str, str]:
    try:
        sugestoes = sugestao_automatica(df_origem, list(df_modelo.columns))
        if isinstance(sugestoes, dict):
            return {str(k): str(v) for k, v in sugestoes.items() if k and v}
    except Exception:
        pass
    return {}


def _converter_sugestoes_origem_para_destino(
    sugestoes_origem_destino: dict[str, str],
    colunas_modelo: list[str],
) -> dict[str, str]:
    destino_origem = {}
    alvos_validos = set(map(str, colunas_modelo))

    for origem, destino in sugestoes_origem_destino.items():
        if str(destino) in alvos_validos and str(destino) not in destino_origem:
            destino_origem[str(destino)] = str(origem)

    return destino_origem


def _mesclar_sugestoes(
    sugestoes_ia: dict[str, str],
    sugestoes_alias: dict[str, str],
) -> dict[str, str]:
    final = {}

    for destino, origem in sugestoes_alias.items():
        if destino not in final:
            final[destino] = origem

    for destino, origem in sugestoes_ia.items():
        if destino not in final:
            final[destino] = origem

    return final


# ==========================================================
# PREENCHIMENTO INTELIGENTE
# ==========================================================
def _preencher_defaults_inteligentes(saida: pd.DataFrame, operacao: str) -> pd.DataFrame:
    if saida is None or saida.empty:
        return saida

    df = saida.copy()

    for col in df.columns:
        if _coluna_modelo_parece_situacao(col):
            df[col] = df[col].replace("", pd.NA)
            df[col] = df[col].fillna("Ativo")

        if _coluna_modelo_parece_descricao_curta(col):
            if col in df.columns:
                df[col] = df[col].replace("", pd.NA)
                col_desc = None
                for c2 in df.columns:
                    if _coluna_modelo_parece_descricao(c2):
                        col_desc = c2
                        break
                if col_desc:
                    df[col] = df[col].fillna(df[col_desc])

        if operacao == "estoque" and _coluna_modelo_parece_deposito(col):
            deposito_manual = _obter_deposito_manual().strip()
            if deposito_manual:
                df[col] = deposito_manual

    return df


# ==========================================================
# VALIDAÇÃO
# ==========================================================
def _campos_obrigatorios_por_operacao(df_modelo: pd.DataFrame, operacao: str) -> list[str]:
    obrigatorios = []

    for col in df_modelo.columns:
        nome = str(col)

        if operacao == "cadastro":
            if (
                _coluna_modelo_parece_descricao(nome)
                or _coluna_modelo_parece_codigo(nome)
                or _coluna_modelo_parece_preco(nome)
            ):
                obrigatorios.append(nome)
        else:
            if (
                _coluna_modelo_parece_codigo(nome)
                or "estoque" in _slug(nome)
                or _coluna_modelo_parece_deposito(nome)
            ):
                obrigatorios.append(nome)

    obrigatorios_unicos = []
    for c in obrigatorios:
        if c not in obrigatorios_unicos:
            obrigatorios_unicos.append(c)

    return obrigatorios_unicos


def _coluna_vazia_ou_invalida(serie: pd.Series) -> bool:
    try:
        serie_txt = serie.astype(str).fillna("").str.strip()
        return bool((serie_txt == "").all())
    except Exception:
        return True


def _validar_df_saida(df_saida: pd.DataFrame, df_modelo: pd.DataFrame, operacao: str) -> tuple[bool, list[str]]:
    erros = []

    if df_saida is None or df_saida.empty:
        return False, ["A planilha final está vazia."]

    obrigatorios = _campos_obrigatorios_por_operacao(df_modelo, operacao)

    for col in obrigatorios:
        if col not in df_saida.columns:
            erros.append(f"Coluna obrigatória ausente: {col}")
            continue

        if _coluna_vazia_ou_invalida(df_saida[col]):
            erros.append(f"Campo obrigatório sem preenchimento: {col}")

    if operacao == "estoque":
        deposito_manual = _obter_deposito_manual().strip()
        if not deposito_manual:
            erros.append("Depósito manual não foi preenchido.")

    return len(erros) == 0, erros


# ==========================================================
# MONTAGEM DA SAÍDA
# ==========================================================
def _montar_saida_no_formato_modelo(
    df_origem: pd.DataFrame,
    df_modelo: pd.DataFrame,
    mapeamento_destino_origem: dict[str, str],
) -> pd.DataFrame:
    saida = pd.DataFrame(index=range(len(df_origem)), columns=list(df_modelo.columns))

    if len(df_modelo) > 0:
        primeira_linha = df_modelo.iloc[0]
        for col in saida.columns:
            valor_padrao = primeira_linha.get(col, None)
            if pd.notna(valor_padrao) and str(valor_padrao).strip() != "":
                saida[col] = valor_padrao

    for col_destino in saida.columns:
        col_origem = mapeamento_destino_origem.get(col_destino, "")
        if col_origem and col_origem in df_origem.columns:
            saida[col_destino] = df_origem[col_origem].values

    deposito_manual = _obter_deposito_manual().strip()
    if deposito_manual:
        for col in saida.columns:
            if _coluna_modelo_parece_deposito(col):
                saida[col] = deposito_manual

    operacao = st.session_state.get("tipo_operacao_bling", "cadastro")
    saida = _preencher_defaults_inteligentes(saida, operacao)

    return saida


# ==========================================================
# MAIN
# ==========================================================
def render_origem_mapeamento():
    df_origem = _safe_df_dados(st.session_state.get("df_origem"))
    df_fluxo = _safe_df_dados(st.session_state.get("df_saida"))
    df_modelo = _obter_modelo_ativo()
    operacao = st.session_state.get("tipo_operacao_bling", "cadastro")
    operacao_label = (
        "Cadastro / atualização de produtos"
        if operacao == "cadastro"
        else "Atualização de estoque"
    )

    if df_origem is None:
        st.warning("Nenhum dado disponível para mapeamento.")
        return

    if df_fluxo is None:
        st.session_state["df_saida"] = df_origem.copy()
        df_fluxo = df_origem.copy()

    st.success(f"Fluxo selecionado: {operacao_label}")

    if df_modelo is None:
        st.warning("Anexe primeiro a planilha modelo da operação escolhida para continuar.")
        if st.button("⬅️ Voltar", width="stretch", key="btn_voltar_sem_modelo"):
            st.session_state["etapa_origem"] = "upload"
            st.rerun()
        return

    nome_modelo = _obter_nome_modelo_ativo()
    if nome_modelo:
        st.info(f"Modelo ativo: {nome_modelo}")

    deposito_manual = _obter_deposito_manual()
    if operacao == "estoque":
        if deposito_manual:
            st.info(f"Depósito manual detectado: {deposito_manual}")
        else:
            st.warning("O depósito manual ainda não foi identificado no estado da sessão.")

    st.markdown("### Preview da origem")
    st.dataframe(_safe_dataframe_preview(df_origem), width="stretch")

    st.markdown("### Preview do modelo")
    st.dataframe(_safe_dataframe_preview(df_modelo), width="stretch")

    st.divider()
    st.markdown("### Mapeamento automático e manual")

    sugestoes_auto_ia = _obter_sugestoes(df_origem, df_modelo)
    sugestoes_destino_ia = _converter_sugestoes_origem_para_destino(
        sugestoes_auto_ia,
        list(df_modelo.columns),
    )
    sugestoes_destino_alias = _sugestao_por_alias(df_origem, df_modelo)
    sugestoes_destino_origem = _mesclar_sugestoes(
        sugestoes_destino_ia,
        sugestoes_destino_alias,
    )

    opcoes_origem = [""] + [str(c) for c in df_origem.columns]
    mapeamento_final_destino_origem: dict[str, str] = {}

    for col_destino in df_modelo.columns:
        valor_inicial = sugestoes_destino_origem.get(str(col_destino), "")
        if valor_inicial not in opcoes_origem:
            valor_inicial = ""

        escolha = st.selectbox(
            f"{col_destino}",
            options=opcoes_origem,
            index=opcoes_origem.index(valor_inicial) if valor_inicial in opcoes_origem else 0,
            key=f"map_destino_{col_destino}",
        )

        if escolha:
            mapeamento_final_destino_origem[str(col_destino)] = str(escolha)

    st.session_state["mapeamento_manual"] = mapeamento_final_destino_origem

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        if st.button("✅ Gerar saída no formato do modelo", width="stretch"):
            try:
                df_saida_final = _montar_saida_no_formato_modelo(
                    df_origem=df_origem,
                    df_modelo=df_modelo,
                    mapeamento_destino_origem=mapeamento_final_destino_origem,
                )

                st.session_state["df_saida"] = df_saida_final
                st.success("Saída gerada com sucesso no formato do modelo.")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao gerar saída: {e}")

    with col2:
        if st.button("⬅️ Voltar", width="stretch", key="btn_voltar_mapeamento"):
            st.session_state["etapa_origem"] = "upload"
            st.rerun()

    df_saida_final = _safe_df_modelo(st.session_state.get("df_saida"))

    if df_saida_final is not None:
        valido, erros_validacao = _validar_df_saida(df_saida_final, df_modelo, operacao)

        st.divider()
        st.markdown("### Preview final no formato do modelo")
        st.dataframe(_safe_dataframe_preview(df_saida_final), width="stretch")

        st.markdown("### Validação antes do download")
        if valido:
            st.success("Validação OK. A planilha está apta para download.")
        else:
            st.error("Download bloqueado até corrigir os campos obrigatórios.")
            for erro in erros_validacao:
                st.warning(erro)

        col3, col4 = st.columns(2)

        with col3:
            try:
                buffer = BytesIO()
                df_saida_final.to_excel(buffer, index=False)
                buffer.seek(0)

                nome_arquivo = "saida.xlsx"
                if operacao == "cadastro":
                    nome_arquivo = "cadastro_bling.xlsx"
                elif operacao == "estoque":
                    nome_arquivo = "estoque_bling.xlsx"

                st.download_button(
                    "⬇️ Baixar planilha final",
                    buffer,
                    nome_arquivo,
                    width="stretch",
                    key="btn_download_planilha_final",
                    disabled=not valido,
                )
            except Exception as e:
                st.error(f"Erro ao gerar Excel: {e}")

        with col4:
            st.download_button(
                "📄 Baixar log",
                _build_log(),
                "log.txt",
                width="stretch",
                key="btn_download_log_mapeamento",
            )
