from __future__ import annotations

import io
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import (
    log_debug,
    safe_df_dados,
    safe_df_estrutura,
)


# ==========================================================
# ESTADO
# ==========================================================
def garantir_estado_origem() -> None:
    defaults = {
        "tipo_operacao": "Cadastro de Produtos",
        "tipo_operacao_radio": "Cadastro de Produtos",
        "tipo_operacao_bling": "cadastro",
        "origem_dados_tipo": "planilha",
        "site_processado": False,
        "df_origem": None,
        "df_saida": None,
        "df_final": None,
        "df_precificado": None,
        "df_calc_precificado": None,
        "deposito_nome": "",
        "coluna_precificacao_resultado": "",
        "site_url": "",
        "site_usuario": "",
        "site_senha": "",
        "site_precisa_login": False,
        "site_modo_sincronizacao": "manual",
        "site_delay_segundos": 300,
        "site_estoque_padrao_disponivel": 1,
    }

    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor

    if _safe_str(st.session_state.get("tipo_operacao_radio")) not in {
        "Cadastro de Produtos",
        "Atualização de Estoque",
    }:
        st.session_state["tipo_operacao_radio"] = "Cadastro de Produtos"

    if _safe_str(st.session_state.get("tipo_operacao")) not in {
        "Cadastro de Produtos",
        "Atualização de Estoque",
    }:
        st.session_state["tipo_operacao"] = "Cadastro de Produtos"

    if _safe_str(st.session_state.get("tipo_operacao_bling")) not in {
        "cadastro",
        "estoque",
    }:
        st.session_state["tipo_operacao_bling"] = "cadastro"


def set_etapa_origem(etapa: str) -> None:
    etapa = str(etapa or "origem").strip().lower()
    st.session_state["etapa_origem"] = etapa
    st.session_state["etapa"] = etapa
    st.session_state["etapa_fluxo"] = etapa


def _sincronizar_tipo_operacao(operacao: str) -> None:
    operacao = str(operacao or "Cadastro de Produtos").strip()

    # IMPORTANTE:
    # Não escrever mais em uma key de widget ativa.
    # O radio usa "tipo_operacao_radio". Aqui sincronizamos apenas o estado lógico.
    st.session_state["tipo_operacao"] = operacao
    st.session_state["tipo_operacao_bling"] = (
        "cadastro" if operacao == "Cadastro de Produtos" else "estoque"
    )


# ==========================================================
# HELPERS
# ==========================================================
def _safe_str(valor: Any) -> str:
    try:
        return str(valor or "").strip()
    except Exception:
        return ""


def _safe_int(valor: Any, default: int = 0) -> int:
    try:
        return int(valor)
    except Exception:
        return int(default)


def _render_header_fluxo() -> None:
    st.subheader("Origem dos dados")
    st.caption(
        "Defina se você quer cadastrar produtos ou atualizar o estoque, "
        "depois escolha a origem dos dados para o sistema preparar a base do Bling."
    )


def _obter_origem_atual() -> str:
    return str(st.session_state.get("origem_dados_tipo") or "planilha").strip().lower()


def _reset_site_processado() -> None:
    st.session_state["site_processado"] = False


def _ler_csv_robusto(upload) -> pd.DataFrame | None:
    try:
        conteudo = upload.read()
        if not conteudo:
            return None

        candidatos = [
            ("utf-8-sig", None),
            ("utf-8", None),
            ("latin1", None),
            ("cp1252", None),
            ("utf-8-sig", ";"),
            ("utf-8", ";"),
            ("latin1", ";"),
            ("cp1252", ";"),
        ]

        for encoding, sep in candidatos:
            try:
                buffer = io.BytesIO(conteudo)
                if sep is None:
                    return pd.read_csv(buffer, sep=None, engine="python", encoding=encoding)
                return pd.read_csv(buffer, sep=sep, encoding=encoding)
            except Exception:
                continue

    except Exception as e:
        log_debug(f"[ORIGEM_DADOS] erro ao ler CSV: {e}", "ERROR")

    return None


def _ler_excel_robusto(upload) -> pd.DataFrame | None:
    try:
        conteudo = upload.read()
        if not conteudo:
            return None

        for engine in [None, "openpyxl", "xlrd"]:
            try:
                buffer = io.BytesIO(conteudo)
                if engine:
                    return pd.read_excel(buffer, engine=engine)
                return pd.read_excel(buffer)
            except Exception:
                continue
    except Exception as e:
        log_debug(f"[ORIGEM_DADOS] erro ao ler Excel: {e}", "ERROR")

    return None


def _ler_xml_robusto(upload) -> pd.DataFrame | None:
    try:
        conteudo = upload.read()
        if not conteudo:
            return None

        for parser in [None, "lxml", "etree"]:
            try:
                buffer = io.BytesIO(conteudo)
                if parser:
                    df = pd.read_xml(buffer, parser=parser)
                else:
                    df = pd.read_xml(buffer)

                if isinstance(df, pd.DataFrame):
                    return df
            except Exception:
                continue
    except Exception as e:
        log_debug(f"[ORIGEM_DADOS] erro ao ler XML: {e}", "ERROR")

    return None


def _ler_planilha(upload) -> pd.DataFrame | None:
    if upload is None:
        return None

    nome = str(getattr(upload, "name", "") or "").lower()

    try:
        if nome.endswith(".csv"):
            return _ler_csv_robusto(upload)

        if nome.endswith(".xlsx") or nome.endswith(".xls"):
            return _ler_excel_robusto(upload)

        if nome.endswith(".xml"):
            return _ler_xml_robusto(upload)

    except Exception as e:
        log_debug(f"[ORIGEM_DADOS] erro ao ler arquivo: {e}", "ERROR")

    return None


def _aplicar_normalizacao_basica(df: pd.DataFrame) -> pd.DataFrame:
    try:
        if not isinstance(df, pd.DataFrame):
            return pd.DataFrame()

        df_out = df.copy()

        colunas_finais = []
        for col in df_out.columns:
            nome = _safe_str(col)
            nome = nome.replace("\ufeff", "").replace("\n", " ").replace("\r", " ").strip()
            colunas_finais.append(nome if nome else "Coluna")

        df_out.columns = colunas_finais
        df_out = df_out.replace({None: ""}).fillna("")

        return df_out
    except Exception as e:
        log_debug(f"[ORIGEM_DADOS] erro na normalização básica: {e}", "ERROR")
        return df


def _render_config_site() -> None:
    st.markdown("### Busca em site")

    st.text_input(
        "URL do site ou da categoria",
        key="site_url",
        placeholder="https://exemplo.com/categoria/produtos",
        help="Informe a URL base para busca dos produtos.",
    )

    st.checkbox(
        "Este site precisa de login e senha",
        key="site_precisa_login",
        help="Ative quando o site exigir autenticação antes de exibir os produtos.",
    )

    if st.session_state.get("site_precisa_login"):
        col1, col2 = st.columns(2)
        with col1:
            st.text_input(
                "Usuário / e-mail do site",
                key="site_usuario",
                placeholder="login@site.com",
            )
        with col2:
            st.text_input(
                "Senha do site",
                key="site_senha",
                type="password",
                placeholder="••••••••",
            )

        st.info(
            "Os campos de login já ficam preparados no estado da aplicação para uso pelo crawler autenticado."
        )

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.selectbox(
            "Modo de sincronização desejado",
            [
                "manual",
                "instantaneo",
                "delay",
            ],
            key="site_modo_sincronizacao",
            help=(
                "Manual: processa quando você mandar. "
                "Instantâneo: pronto para envio logo após a captura. "
                "Delay: prepara a configuração de intervalo."
            ),
        )

    with col2:
        st.number_input(
            "Delay em segundos",
            min_value=5,
            value=_safe_int(st.session_state.get("site_delay_segundos"), 300),
            step=5,
            key="site_delay_segundos",
            help="Usado quando o modo de sincronização por delay estiver ativo.",
        )

    if st.session_state.get("tipo_operacao_bling") == "estoque":
        st.number_input(
            "Estoque padrão para item disponível",
            min_value=0,
            value=_safe_int(st.session_state.get("site_estoque_padrao_disponivel"), 1),
            step=1,
            key="site_estoque_padrao_disponivel",
            help="Fallback para itens disponíveis quando o site não informar o estoque real.",
        )

    st.warning(
        "Nesta tela, a configuração do site já fica preparada. "
        "A execução autenticada depende do módulo de captura/fetcher usar esses campos."
    )


def render_origem_entrada(on_change_callback=None):
    origem = st.radio(
        "Escolha a origem dos dados",
        ["Planilha / CSV / XML", "Buscar em site"],
        horizontal=True,
        key="origem_dados_radio",
    )

    origem_valor = "site" if "site" in origem.lower() else "planilha"

    origem_anterior = _safe_str(st.session_state.get("origem_dados_tipo")).lower()
    st.session_state["origem_dados_tipo"] = origem_valor

    if origem_anterior != origem_valor:
        _reset_site_processado()

    if callable(on_change_callback):
        try:
            on_change_callback(origem_valor)
        except Exception:
            pass

    if origem_valor == "site":
        _render_config_site()

        if st.session_state.get("site_processado") and safe_df_dados(st.session_state.get("df_origem")):
            st.success("Dados do site já carregados nesta sessão.")
            return st.session_state.get("df_origem")

        st.info(
            "Configure a URL do site acima. "
            "Após a busca do crawler, os dados carregados aparecerão aqui automaticamente."
        )
        return st.session_state.get("df_origem")

    arquivo = st.file_uploader(
        "Anexe sua planilha ou XML",
        type=["xlsx", "xls", "csv", "xml"],
        key="upload_origem_dados",
        help="Formatos aceitos: XLSX, XLS, CSV e XML.",
    )

    df_origem = _ler_planilha(arquivo)
    if safe_df_dados(df_origem):
        df_origem = _aplicar_normalizacao_basica(df_origem)
        return df_origem

    return st.session_state.get("df_origem")


def controlar_troca_origem(origem: str, log_fn=None):
    try:
        if callable(log_fn):
            log_fn(f"[ORIGEM_DADOS] origem selecionada: {origem}", "INFO")
    except Exception:
        pass


def sincronizar_estado_com_origem(df_origem: pd.DataFrame, log_fn=None) -> None:
    try:
        df_limpo = _aplicar_normalizacao_basica(df_origem)
        st.session_state["df_origem"] = df_limpo.copy()

        if callable(log_fn):
            log_fn(
                f"[ORIGEM_DADOS] df_origem sincronizado com {len(df_limpo)} linha(s)",
                "INFO",
            )
    except Exception as e:
        if callable(log_fn):
            log_fn(f"[ORIGEM_DADOS] erro ao sincronizar origem: {e}", "ERROR")


def obter_modelo_ativo():
    if st.session_state.get("tipo_operacao_bling") == "estoque":
        return st.session_state.get("df_modelo_estoque")
    return st.session_state.get("df_modelo_cadastro")


def _modelo_tem_estrutura(df_modelo) -> bool:
    return safe_df_estrutura(df_modelo)


def render_modelo_bling(operacao: str) -> None:
    st.caption(f"Modelo ativo: {operacao}")


def obter_df_base_prioritaria(df_origem: pd.DataFrame, origem_atual: str) -> pd.DataFrame:
    _ = origem_atual

    df_prec = st.session_state.get("df_precificado")
    df_calc = st.session_state.get("df_calc_precificado")

    if safe_df_estrutura(df_prec):
        return df_prec.copy()

    if safe_df_estrutura(df_calc):
        return df_calc.copy()

    return df_origem.copy()


def _aplicar_bloco_estoque(df_saida: pd.DataFrame, origem_atual: str) -> pd.DataFrame:
    try:
        df_out = df_saida.copy()

        qtd_padrao = 0 if "site" in _safe_str(origem_atual).lower() else 1
        qtd_padrao = _safe_int(
            st.session_state.get("site_estoque_padrao_disponivel"),
            qtd_padrao,
        )

        if "Quantidade" not in df_out.columns:
            df_out["Quantidade"] = qtd_padrao
        else:
            serie = pd.to_numeric(df_out["Quantidade"], errors="coerce")
            df_out["Quantidade"] = serie.fillna(qtd_padrao)

        deposito_nome = _safe_str(st.session_state.get("deposito_nome"))
        if deposito_nome:
            if "Depósito (OBRIGATÓRIO)" not in df_out.columns:
                df_out["Depósito (OBRIGATÓRIO)"] = deposito_nome
            else:
                df_out["Depósito (OBRIGATÓRIO)"] = (
                    df_out["Depósito (OBRIGATÓRIO)"]
                    .replace({None: ""})
                    .fillna("")
                    .astype(str)
                    .str.strip()
                )
                df_out.loc[
                    df_out["Depósito (OBRIGATÓRIO)"].eq(""),
                    "Depósito (OBRIGATÓRIO)",
                ] = deposito_nome

        if "Balanço (OBRIGATÓRIO)" not in df_out.columns:
            df_out["Balanço (OBRIGATÓRIO)"] = "S"

        return df_out
    except Exception as e:
        log_debug(f"[ORIGEM_DADOS] erro bloco estoque: {e}", "ERROR")
        return df_saida


def _nome_coluna_preco_saida() -> str:
    return (
        "Preço unitário (OBRIGATÓRIO)"
        if st.session_state.get("tipo_operacao_bling") == "estoque"
        else "Preço de venda"
    )


def _to_numeric_series(serie: pd.Series) -> pd.Series:
    try:
        texto = (
            serie.replace({None: ""})
            .fillna("")
            .astype(str)
            .str.replace("R$", "", regex=False)
            .str.replace(" ", "", regex=False)
        )

        possui_virgula = texto.str.contains(",", regex=False)
        possui_ponto = texto.str.contains(".", regex=False)

        texto = texto.where(~(possui_virgula & possui_ponto), texto.str.replace(".", "", regex=False))
        texto = texto.str.replace(",", ".", regex=False)

        return pd.to_numeric(texto, errors="coerce").fillna(0.0)
    except Exception:
        return pd.to_numeric(serie, errors="coerce").fillna(0.0)


def render_precificacao(df_origem: pd.DataFrame) -> None:
    st.caption("Precificação")

    opcoes = [""] + [str(c) for c in df_origem.columns]
    coluna_custo = st.selectbox(
        "Qual coluna de origem deve ser usada como base do preço?",
        opcoes,
        key="coluna_precificacao_resultado",
        help="Escolha a coluna de custo/preço base para gerar o preço automático.",
    )

    col1, col2 = st.columns(2)
    with col1:
        margem = st.number_input(
            "Margem (%)",
            min_value=0.0,
            value=float(st.session_state.get("margem_bling", 0.0) or 0.0),
            step=1.0,
            key="margem_bling",
        )
        impostos = st.number_input(
            "Impostos (%)",
            min_value=0.0,
            value=float(st.session_state.get("impostos_bling", 0.0) or 0.0),
            step=1.0,
            key="impostos_bling",
        )

    with col2:
        custo_fixo = st.number_input(
            "Custo fixo",
            min_value=0.0,
            value=float(st.session_state.get("custofixo_bling", 0.0) or 0.0),
            step=1.0,
            key="custofixo_bling",
        )
        taxa_extra = st.number_input(
            "Taxa extra",
            min_value=0.0,
            value=float(st.session_state.get("taxaextra_bling", 0.0) or 0.0),
            step=1.0,
            key="taxaextra_bling",
        )

    if not coluna_custo or coluna_custo not in df_origem.columns:
        st.session_state["df_calc_precificado"] = None
        return

    try:
        base = _to_numeric_series(df_origem[coluna_custo])
        fator_percentual = 1 + (margem / 100.0) + (impostos / 100.0)
        preco = (base * fator_percentual) + custo_fixo + taxa_extra

        df_prec = df_origem.copy()
        nome_preco = _nome_coluna_preco_saida()
        df_prec[nome_preco] = preco.round(2)

        st.session_state["df_calc_precificado"] = df_prec.copy()
        st.session_state["df_precificado"] = df_prec.copy()

        st.success(f"Preço automático gerado na coluna: {nome_preco}")

    except Exception as e:
        log_debug(f"[ORIGEM_DADOS] erro na precificação: {e}", "ERROR")
        st.session_state["df_calc_precificado"] = None


def validar_antes_mapeamento():
    erros = []

    df_origem = st.session_state.get("df_origem")
    if not safe_df_dados(df_origem):
        erros.append("Carregue os dados de origem antes de continuar.")

    origem_atual = _obter_origem_atual()
    if "site" in origem_atual:
        url = _safe_str(st.session_state.get("site_url"))
        if not url:
            erros.append("Informe a URL do site.")
        if not st.session_state.get("site_processado") and not safe_df_dados(df_origem):
            erros.append("Execute a busca do site antes de continuar.")

    return len(erros) == 0, erros


def _render_preview_origem(df_origem: pd.DataFrame) -> None:
    try:
        with st.expander("Prévia da origem", expanded=False):
            st.dataframe(df_origem.head(20), use_container_width=True)
    except Exception as e:
        log_debug(f"[ORIGEM_DADOS] erro preview origem: {e}", "ERROR")


# ==========================================================
# RENDER
# ==========================================================
def render_origem_dados() -> None:
    garantir_estado_origem()
    _render_header_fluxo()

    etapa = str(st.session_state.get("etapa_origem", "origem") or "origem").strip().lower()

    if etapa == "mapeamento":
        if st.button("⬅️ Voltar para origem", use_container_width=True):
            set_etapa_origem("origem")
            st.rerun()
        return

    labels_operacao = ["Cadastro de Produtos", "Atualização de Estoque"]
    valor_radio = _safe_str(st.session_state.get("tipo_operacao_radio"))
    if valor_radio not in labels_operacao:
        st.session_state["tipo_operacao_radio"] = "Cadastro de Produtos"
        valor_radio = "Cadastro de Produtos"

    index_operacao = labels_operacao.index(valor_radio)

    operacao = st.radio(
        "Você quer cadastrar produto ou atualizar o estoque?",
        labels_operacao,
        key="tipo_operacao_radio",
        horizontal=True,
        index=index_operacao,
    )
    _sincronizar_tipo_operacao(operacao)

    if st.session_state.get("tipo_operacao_bling") == "estoque":
        st.text_input(
            "Nome do depósito",
            key="deposito_nome",
            placeholder="Ex: Depósito principal",
            help="Este valor será propagado para a base de estoque quando necessário.",
        )

    st.markdown("---")

    df_origem = render_origem_entrada(
        lambda origem: controlar_troca_origem(origem, log_debug)
    )
    origem_atual = _obter_origem_atual()

    if "site" in origem_atual and not st.session_state.get("site_processado"):
        if not safe_df_dados(df_origem):
            st.info("Configure o site e execute a busca para continuar.")
            return

    if not safe_df_dados(df_origem):
        st.info("Selecione a origem e carregue os dados para continuar.")
        return

    df_origem = _aplicar_normalizacao_basica(df_origem)
    st.session_state["df_origem"] = df_origem.copy()
    sincronizar_estado_com_origem(df_origem, log_debug)

    st.markdown("---")
    render_modelo_bling(operacao)

    modelo_ativo = obter_modelo_ativo()
    if modelo_ativo is not None and not _modelo_tem_estrutura(modelo_ativo):
        st.warning("⚠️ Modelo do Bling não encontrado.")
        return

    df_saida = obter_df_base_prioritaria(df_origem, origem_atual)

    if st.session_state.get("tipo_operacao_bling") == "estoque":
        df_saida = _aplicar_bloco_estoque(df_saida, origem_atual)

    st.session_state["df_saida"] = df_saida.copy()
    st.session_state["df_final"] = df_saida.copy()

    _render_preview_origem(df_origem)

    st.markdown("---")
    render_precificacao(df_origem)

    df_prec = st.session_state.get("df_calc_precificado")
    if safe_df_estrutura(df_prec):
        st.session_state["df_precificado"] = df_prec.copy()

        nome_preco = _nome_coluna_preco_saida()
        df_saida_prec = df_prec.copy()

        if st.session_state.get("tipo_operacao_bling") == "estoque":
            df_saida_prec = _aplicar_bloco_estoque(df_saida_prec, origem_atual)

        if nome_preco in df_saida_prec.columns:
            st.session_state["df_saida"] = df_saida_prec.copy()
            st.session_state["df_final"] = df_saida_prec.copy()

    st.markdown("---")

    if st.button("➡️ Continuar para mapeamento", use_container_width=True, type="primary"):
        valido, erros = validar_antes_mapeamento()

        if not valido:
            for erro in erros:
                st.warning(erro)
            return

        if safe_df_estrutura(st.session_state.get("df_saida")):
            st.session_state["df_final"] = st.session_state["df_saida"].copy()

        set_etapa_origem("mapeamento")
        st.rerun()
