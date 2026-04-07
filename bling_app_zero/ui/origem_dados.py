from __future__ import annotations

import hashlib

import pandas as pd
import streamlit as st

from bling_app_zero.core.precificacao import aplicar_precificacao_automatica
from bling_app_zero.ui.origem_dados_helpers import (
    ler_planilha_segura,
    log_debug,
)
from bling_app_zero.ui.origem_dados_site import render_origem_site
from bling_app_zero.utils.xml_nfe import (
    arquivo_parece_xml_nfe,
    ler_xml_nfe,
)


def _safe_df_dados(df) -> bool:
    try:
        if df is None:
            return False
        if not hasattr(df, "columns"):
            return False
        if len(df.columns) == 0:
            return False
        if getattr(df, "empty", True):
            return False
        return True
    except Exception:
        return False


def _safe_float(valor, default: float = 0.0) -> float:
    try:
        if valor is None or valor == "":
            return default
        return float(valor)
    except Exception:
        return default


def _coletar_parametros_precificacao():
    return {
        "percentual_impostos": _safe_float(st.session_state.get("perc_impostos", 0)),
        "margem_lucro": _safe_float(st.session_state.get("margem_lucro", 0)),
        "custo_fixo": _safe_float(st.session_state.get("custo_fixo", 0)),
        "taxa_extra": _safe_float(st.session_state.get("taxa_extra", 0)),
    }


def _aplicar_precificacao_com_fallback(df_base, coluna_preco):
    kwargs = _coletar_parametros_precificacao()

    try:
        return aplicar_precificacao_automatica(
            df_base.copy(),
            coluna_preco=coluna_preco,
            **kwargs,
        )
    except TypeError:
        return aplicar_precificacao_automatica(
            df_base.copy(),
            **kwargs,
        )


def _fingerprint_df(df) -> str:
    """
    Gera uma assinatura mais robusta da origem.
    Isso evita reaproveitar estado antigo quando o usuário troca o arquivo
    por outro com mesmas colunas e mesma quantidade de linhas.
    """
    try:
        if not _safe_df_dados(df):
            return ""

        df_base = df.copy()

        try:
            head_registros = (
                df_base.head(10)
                .fillna("")
                .astype(str)
                .to_dict(orient="records")
            )
        except Exception:
            head_registros = []

        base = f"{list(df_base.columns)}|{len(df_base)}|{head_registros}"
        return hashlib.md5(base.encode("utf-8")).hexdigest()
    except Exception:
        return ""


def _limpar_mapeamento_widgets() -> None:
    try:
        for chave in list(st.session_state.keys()):
            if str(chave).startswith("map_"):
                st.session_state.pop(chave, None)
    except Exception:
        pass


def _resetar_estado_fluxo(manter_modelos: bool = True) -> None:
    chaves_reset = [
        "df_origem",
        "df_saida",
        "df_final",
        "df_precificado",
        "bloquear_campos_auto",
        "mapeamento_automatico",
        "mapeamento_manual",
        "mapeamento_manual_cadastro",
        "mapeamento_manual_estoque",
        "coluna_preco_base",
        "origem_dados_fingerprint",
        "df_origem_site",
        "df_origem_xml",
    ]

    for chave in chaves_reset:
        st.session_state.pop(chave, None)

    _limpar_mapeamento_widgets()

    if not manter_modelos:
        st.session_state.pop("df_modelo_cadastro", None)
        st.session_state.pop("modelo_cadastro_nome", None)
        st.session_state.pop("df_modelo_estoque", None)
        st.session_state.pop("modelo_estoque_nome", None)


def _controlar_troca_operacao(operacao: str) -> None:
    operacao_anterior = st.session_state.get("_operacao_anterior_origem_dados")

    if operacao_anterior is None:
        st.session_state["_operacao_anterior_origem_dados"] = operacao
        return

    if operacao_anterior != operacao:
        log_debug(
            f"Operação alterada de '{operacao_anterior}' para '{operacao}'. "
            "Resetando estados transitórios do fluxo."
        )
        _resetar_estado_fluxo(manter_modelos=True)
        st.session_state["etapa_origem"] = None
        st.session_state["_operacao_anterior_origem_dados"] = operacao


def _controlar_troca_origem(origem: str) -> None:
    origem_anterior = st.session_state.get("_origem_anterior_origem_dados")

    if origem_anterior is None:
        st.session_state["_origem_anterior_origem_dados"] = origem
        return

    if origem_anterior != origem:
        log_debug(
            f"Origem alterada de '{origem_anterior}' para '{origem}'. "
            "Resetando estados transitórios do fluxo."
        )
        _resetar_estado_fluxo(manter_modelos=True)
        st.session_state["etapa_origem"] = None
        st.session_state["_origem_anterior_origem_dados"] = origem


def _carregar_modelo_bling(arquivo, tipo_modelo: str) -> bool:
    if arquivo is None:
        return False

    try:
        df_modelo = ler_planilha_segura(arquivo)

        if not _safe_df_dados(df_modelo):
            st.error("Não foi possível ler o modelo Bling anexado.")
            return False

        if tipo_modelo == "cadastro":
            st.session_state["df_modelo_cadastro"] = df_modelo.copy()
            st.session_state["modelo_cadastro_nome"] = getattr(
                arquivo, "name", "modelo_cadastro"
            )
            log_debug(
                f"Modelo de cadastro carregado: {getattr(arquivo, 'name', 'arquivo')} "
                f"({len(df_modelo)} linha(s), {len(df_modelo.columns)} coluna(s))"
            )
        else:
            st.session_state["df_modelo_estoque"] = df_modelo.copy()
            st.session_state["modelo_estoque_nome"] = getattr(
                arquivo, "name", "modelo_estoque"
            )
            log_debug(
                f"Modelo de estoque carregado: {getattr(arquivo, 'name', 'arquivo')} "
                f"({len(df_modelo)} linha(s), {len(df_modelo.columns)} coluna(s))"
            )

        return True
    except Exception as e:
        st.error("Erro ao carregar o modelo Bling.")
        log_debug(f"Erro ao carregar modelo Bling ({tipo_modelo}): {e}", "ERRO")
        return False


def _obter_modelo_ativo():
    tipo = st.session_state.get("tipo_operacao_bling")
    if tipo == "cadastro":
        return st.session_state.get("df_modelo_cadastro")
    return st.session_state.get("df_modelo_estoque")


def _modelo_ativo_esta_ok() -> bool:
    tipo = st.session_state.get("tipo_operacao_bling")
    if tipo == "cadastro":
        return _safe_df_dados(st.session_state.get("df_modelo_cadastro"))
    return _safe_df_dados(st.session_state.get("df_modelo_estoque"))


def _render_modelo_bling(operacao: str) -> None:
    st.markdown("### Modelos Bling")

    if operacao == "Cadastro de Produtos":
        arquivo_modelo = st.file_uploader(
            "Anexar modelo de cadastro",
            type=["xlsx", "xls", "xlsm", "xlsb", "csv"],
            key="modelo_cadastro",
        )

        if arquivo_modelo is not None:
            _carregar_modelo_bling(arquivo_modelo, "cadastro")

        df_modelo = st.session_state.get("df_modelo_cadastro")
        if _safe_df_dados(df_modelo):
            with st.expander(" Prévia do modelo de cadastro", expanded=False):
                st.dataframe(df_modelo.head(5), use_container_width=True)

    else:
        arquivo_modelo = st.file_uploader(
            "Anexar modelo de estoque",
            type=["xlsx", "xls", "xlsm", "xlsb", "csv"],
            key="modelo_estoque",
        )

        if arquivo_modelo is not None:
            _carregar_modelo_bling(arquivo_modelo, "estoque")

        df_modelo = st.session_state.get("df_modelo_estoque")
        if _safe_df_dados(df_modelo):
            with st.expander(" Prévia do modelo de estoque", expanded=False):
                st.dataframe(df_modelo.head(5), use_container_width=True)


def _ler_origem_xml(arquivo_xml):
    if arquivo_xml is None:
        return None

    try:
        if not arquivo_parece_xml_nfe(arquivo_xml):
            st.error("O arquivo anexado não parece ser um XML de NFe válido.")
            log_debug(
                f"Arquivo XML inválido ou não reconhecido: "
                f"{getattr(arquivo_xml, 'name', 'arquivo_xml')}",
                "ERRO",
            )
            return None

        df_xml = ler_xml_nfe(arquivo_xml)

        if not _safe_df_dados(df_xml):
            st.error("Não foi possível extrair dados do XML.")
            log_debug(
                f"XML sem dados aproveitáveis: "
                f"{getattr(arquivo_xml, 'name', 'arquivo_xml')}",
                "ERRO",
            )
            return None

        st.session_state["df_origem_xml"] = df_xml.copy()
        log_debug(
            f"XML de origem carregado: {getattr(arquivo_xml, 'name', 'arquivo_xml')} "
            f"({len(df_xml)} linha(s), {len(df_xml.columns)} coluna(s))"
        )
        return df_xml
    except Exception as e:
        log_debug(f"Erro ao ler XML de origem: {e}", "ERRO")
        st.error("Não foi possível ler o XML enviado.")
        return None


def _render_origem_entrada():
    origem = st.selectbox(
        "Selecione a origem",
        ["Planilha", "XML", "Site"],
        key="origem_tipo",
    )

    _controlar_troca_origem(origem)
    df_origem = None

    if origem == "Planilha":
        arquivo = st.file_uploader(
            "Envie a planilha",
            type=["xlsx", "xls", "csv", "xlsm", "xlsb"],
            key="arquivo_origem_planilha",
        )

        if arquivo:
            try:
                df_origem = ler_planilha_segura(arquivo)

                if _safe_df_dados(df_origem):
                    log_debug(
                        f"Planilha de origem carregada: {getattr(arquivo, 'name', 'arquivo')} "
                        f"({len(df_origem)} linha(s), {len(df_origem.columns)} coluna(s))"
                    )
                else:
                    st.error("Não foi possível ler a planilha enviada.")
                    return None
            except Exception as e:
                log_debug(f"Erro ao ler planilha de origem: {e}", "ERRO")
                st.error("Não foi possível ler a planilha enviada.")
                return None

    elif origem == "Site":
        try:
            df_origem = render_origem_site()
        except Exception as e:
            log_debug(f"Erro na origem por site: {e}", "ERRO")
            st.error("Erro ao buscar dados do site.")
            return None

    elif origem == "XML":
        arquivo_xml = st.file_uploader(
            "Envie o XML da nota fiscal",
            type=["xml"],
            key="arquivo_origem_xml",
        )

        if arquivo_xml is not None:
            df_origem = _ler_origem_xml(arquivo_xml)

    return df_origem


def _sincronizar_estado_com_origem(df_origem) -> None:
    if not _safe_df_dados(df_origem):
        return

    novo_fingerprint = _fingerprint_df(df_origem)
    fingerprint_atual = st.session_state.get("origem_dados_fingerprint", "")

    if fingerprint_atual != novo_fingerprint:
        log_debug("Nova origem detectada. Sincronizando estados do fluxo.")
        st.session_state["origem_dados_fingerprint"] = novo_fingerprint
        st.session_state["df_origem"] = df_origem.copy()
        st.session_state["df_saida"] = df_origem.copy()
        st.session_state["df_final"] = df_origem.copy()
        st.session_state.pop("df_precificado", None)
        st.session_state["bloquear_campos_auto"] = {}
        st.session_state.pop("mapeamento_manual_cadastro", None)
        st.session_state.pop("mapeamento_manual_estoque", None)
        _limpar_mapeamento_widgets()
    else:
        st.session_state["df_origem"] = df_origem.copy()

        if not _safe_df_dados(st.session_state.get("df_saida")):
            st.session_state["df_saida"] = df_origem.copy()

        if not _safe_df_dados(st.session_state.get("df_final")):
            st.session_state["df_final"] = st.session_state["df_saida"].copy()


def _render_precificacao(df_base):
    st.markdown("### Precificação")

    if not _safe_df_dados(df_base):
        return

    colunas = list(df_base.columns)
    if not colunas:
        return

    coluna_preco_default = 0
    candidatos = [
        "preco de custo",
        "preço de custo",
        "preco_custo",
        "preço_custo",
        "custo",
        "valor custo",
        "valor_custo",
        "preco compra",
        "preço compra",
        "preco_compra_xml",
        "preco",
        "preço",
        "valor",
    ]
    colunas_lower = [str(c).strip().lower() for c in colunas]

    for candidato in candidatos:
        for i, nome_col in enumerate(colunas_lower):
            if candidato == nome_col or candidato in nome_col:
                coluna_preco_default = i
                break
        else:
            continue
        break

    coluna_preco = st.selectbox(
        "Selecione a coluna de PREÇO DE CUSTO",
        options=colunas,
        index=coluna_preco_default,
        key="coluna_preco_base",
    )

    col1, col2 = st.columns(2)

    with col1:
        st.number_input("Margem (%)", min_value=0.0, key="margem_lucro")
        st.number_input("Impostos (%)", min_value=0.0, key="perc_impostos")

    with col2:
        st.number_input("Custo fixo", min_value=0.0, key="custo_fixo")
        st.number_input("Taxa extra (%)", min_value=0.0, key="taxa_extra")

    recalcular = st.button(
        " Aplicar precificação",
        use_container_width=True,
        key="btn_aplicar_precificacao",
    )

    if recalcular:
        try:
            df_precificado = _aplicar_precificacao_com_fallback(df_base, coluna_preco)

            if _safe_df_dados(df_precificado):
                st.session_state["df_precificado"] = df_precificado.copy()
                st.session_state["df_saida"] = df_precificado.copy()
                st.session_state["df_final"] = df_precificado.copy()
                st.session_state["bloquear_campos_auto"] = {"preco": True}
                log_debug(
                    f"Precificação aplicada com sucesso usando a coluna '{coluna_preco}'"
                )
            else:
                st.error("A precificação não retornou dados válidos.")
                log_debug("Precificação retornou DataFrame inválido", "ERRO")
        except Exception as e:
            log_debug(f"Erro na precificação: {e}", "ERRO")
            st.error("Erro ao aplicar a precificação.")

    df_preview_precificacao = st.session_state.get("df_precificado")
    if _safe_df_dados(df_preview_precificacao):
        with st.expander("️ Prévia da precificação", expanded=False):
            st.dataframe(df_preview_precificacao.head(10), use_container_width=True)


def _validar_antes_mapeamento() -> tuple[bool, list[str]]:
    erros: list[str] = []

    if not _safe_df_dados(st.session_state.get("df_origem")):
        erros.append("A origem dos dados não está carregada.")

    if not _safe_df_dados(st.session_state.get("df_saida")):
        erros.append("A base de saída ainda não foi preparada.")

    if not _modelo_ativo_esta_ok():
        tipo = st.session_state.get("tipo_operacao_bling")
        if tipo == "cadastro":
            erros.append("Anexe o modelo oficial de cadastro do Bling.")
        else:
            erros.append("Anexe o modelo oficial de estoque do Bling.")

    return len(erros) == 0, erros


def render_origem_dados() -> None:
    etapa_atual = st.session_state.get("etapa_origem")
    if etapa_atual in ["mapeamento", "final"]:
        return

    st.subheader("Origem dos dados")

    operacao = st.radio(
        "Selecione a operação",
        ["Cadastro de Produtos", "Atualização de Estoque"],
        key="tipo_operacao",
    )

    _controlar_troca_operacao(operacao)

    if operacao == "Cadastro de Produtos":
        st.session_state["tipo_operacao_bling"] = "cadastro"
    else:
        st.session_state["tipo_operacao_bling"] = "estoque"

    _render_modelo_bling(operacao)

    df_origem = _render_origem_entrada()
    if not _safe_df_dados(df_origem):
        return

    _sincronizar_estado_com_origem(df_origem)

    with st.expander(" Prévia da planilha do fornecedor", expanded=False):
        st.dataframe(df_origem.head(10), use_container_width=True)

    _render_precificacao(df_origem)

    df_saida = st.session_state.get("df_saida")
    if not _safe_df_dados(df_saida):
        df_saida = df_origem.copy()
        st.session_state["df_saida"] = df_saida.copy()
        st.session_state["df_final"] = df_saida.copy()
    else:
        df_saida = df_saida.copy()
        st.session_state["df_final"] = df_saida.copy()

    modelo_ativo = _obter_modelo_ativo()
    if not _safe_df_dados(modelo_ativo):
        st.warning("Anexe o modelo oficial do Bling antes de continuar para o mapeamento.")
        return

    valido, erros = _validar_antes_mapeamento()
    if not valido:
        for erro in erros:
            st.warning(erro)
        return

    if st.button(
        "➡️ Continuar para mapeamento",
        use_container_width=True,
        key="btn_continuar_mapeamento",
    ):
        try:
            st.session_state["df_final"] = df_saida.copy()
            st.session_state["df_saida"] = df_saida.copy()
            st.session_state["etapa_origem"] = "mapeamento"
            log_debug("Fluxo enviado para etapa de mapeamento")
            st.rerun()
        except Exception as e:
            log_debug(f"Erro ao continuar para o mapeamento: {e}", "ERRO")
            st.error("Não foi possível seguir para o mapeamento.")
