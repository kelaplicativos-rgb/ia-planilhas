from __future__ import annotations

from typing import Any, Callable

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import log_debug, limpar_gtin_invalido

# ==========================================================
# HELPERS
# ==========================================================


def _safe_df_com_linhas(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0
    except Exception:
        return False


def _safe_df_estrutura(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0
    except Exception:
        return False


def _normalizar_df(df: pd.DataFrame) -> pd.DataFrame:
    try:
        df = df.copy()
        df.columns = [str(col).strip() for col in df.columns]
        for col in df.columns:
            df[col] = df[col].replace({None: ""}).fillna("")
        return df
    except Exception:
        return df


def _set_if_changed(chave: str, valor) -> None:
    try:
        atual = st.session_state.get(chave)
        if atual != valor:
            st.session_state[chave] = valor
    except Exception:
        st.session_state[chave] = valor


def _garantir_etapa_origem_valida() -> None:
    try:
        etapa = str(st.session_state.get("etapa_origem") or "").strip().lower()
        if etapa not in {"origem", "mapeamento", "final"}:
            st.session_state["etapa_origem"] = "origem"
    except Exception:
        st.session_state["etapa_origem"] = "origem"


def _limpar_estado_origem() -> None:
    for chave in [
        "df_origem",
        "df_dados",
        "df_saida",
        "df_final",
        "df_precificado",
        "mapping_origem",
        "arquivo_origem_nome",
        "arquivo_origem_hash",
        "origem_dados_nome",
        "origem_dados_hash",
        "origem_dados_tipo_arquivo",
        "origem_pdf_texto",
        "origem_pdf_nome",
    ]:
        if chave in st.session_state:
            del st.session_state[chave]


def _resetar_fluxo_para_origem() -> None:
    try:
        for chave in ["df_saida", "df_final", "df_precificado", "mapping_origem"]:
            if chave in st.session_state:
                del st.session_state[chave]

        st.session_state["etapa_origem"] = "origem"
        st.session_state["etapa"] = "origem"
        st.session_state["etapa_fluxo"] = "origem"
    except Exception:
        pass


def _salvar_df_origem(
    df: pd.DataFrame,
    origem: str = "",
    nome_ref: str = "",
    hash_ref: str = "",
) -> None:
    try:
        df_copia = df.copy()
        origem_normalizada = str(origem or "").strip().lower()

        st.session_state["df_origem"] = df_copia
        st.session_state["df_dados"] = df_copia
        st.session_state["origem_dados"] = origem_normalizada
        st.session_state["arquivo_origem_nome"] = str(nome_ref or "")
        st.session_state["arquivo_origem_hash"] = str(hash_ref or "")
        st.session_state["origem_dados_nome"] = str(nome_ref or "")
        st.session_state["origem_dados_hash"] = str(hash_ref or "")
    except Exception:
        st.session_state["df_origem"] = df
        st.session_state["df_dados"] = df
        st.session_state["origem_dados"] = str(origem or "").strip().lower()
        st.session_state["arquivo_origem_nome"] = str(nome_ref or "")
        st.session_state["arquivo_origem_hash"] = str(hash_ref or "")
        st.session_state["origem_dados_nome"] = str(nome_ref or "")
        st.session_state["origem_dados_hash"] = str(hash_ref or "")


def _hash_arquivo_upload(uploaded_file) -> str:
    try:
        if uploaded_file is None:
            return ""
        pos = uploaded_file.tell()
        uploaded_file.seek(0)
        conteudo = uploaded_file.read()
        uploaded_file.seek(pos)
        return str(hash(conteudo))
    except Exception:
        return ""


def _nome_arquivo(uploaded_file) -> str:
    try:
        return str(getattr(uploaded_file, "name", "") or "").strip()
    except Exception:
        return ""


def _extensao_arquivo(uploaded_file) -> str:
    try:
        nome = _nome_arquivo(uploaded_file).lower()
        if "." not in nome:
            return ""
        return nome.rsplit(".", 1)[-1]
    except Exception:
        return ""


def texto_extensoes_planilha() -> str:
    return ".xlsx, .xls, .xlsb, .csv"


def texto_extensoes_upload_origem() -> str:
    return ".xlsx, .xls, .xlsb, .csv, .xml, .pdf"


def tem_upload_ativo() -> bool:
    try:
        return _safe_df_com_linhas(st.session_state.get("df_origem"))
    except Exception:
        return False


def _df_preview_seguro(df: pd.DataFrame) -> pd.DataFrame:
    try:
        return _normalizar_df(df).copy()
    except Exception:
        return df.copy()


def _df_preview_modelo(df: pd.DataFrame) -> pd.DataFrame:
    """
    Garante que a prévia do modelo nunca apareça como vazia
    quando o arquivo oficial tiver apenas cabeçalhos.
    """
    try:
        df = _normalizar_df(df)
        if not _safe_df_estrutura(df):
            return pd.DataFrame()

        if not df.empty:
            return df.head(5).copy()

        linha_vazia = {col: "" for col in df.columns}
        return pd.DataFrame([linha_vazia])
    except Exception:
        try:
            return df.head(5).copy()
        except Exception:
            return pd.DataFrame()


# ==========================================================
# LEITURA DE PLANILHAS
# ==========================================================


def _ler_planilha(uploaded_file) -> pd.DataFrame | None:
    if uploaded_file is None:
        return None

    nome = _nome_arquivo(uploaded_file).lower()

    try:
        if nome.endswith(".csv"):
            try:
                uploaded_file.seek(0)
                return pd.read_csv(uploaded_file)
            except Exception:
                uploaded_file.seek(0)
                return pd.read_csv(uploaded_file, sep=";", encoding="utf-8")

        if nome.endswith(".xlsb"):
            uploaded_file.seek(0)
            return pd.read_excel(uploaded_file, engine="pyxlsb")

        if nome.endswith(".xlsx") or nome.endswith(".xls"):
            uploaded_file.seek(0)
            return pd.read_excel(uploaded_file)

        return None
    except Exception as e:
        log_debug(f"Erro ao ler planilha {nome}: {e}", "ERRO")
        return None


def _processar_upload_planilha(arquivo_planilha) -> pd.DataFrame | None:
    try:
        if arquivo_planilha is None:
            return None

        nome_planilha = _nome_arquivo(arquivo_planilha)
        hash_planilha = _hash_arquivo_upload(arquivo_planilha)

        hash_anterior = st.session_state.get("arquivo_origem_hash", "")
        nome_anterior = st.session_state.get("arquivo_origem_nome", "")

        if hash_planilha != hash_anterior or nome_planilha != nome_anterior:
            _limpar_estado_origem()

        df_planilha = _ler_planilha(arquivo_planilha)

        if not _safe_df_com_linhas(df_planilha):
            st.error("Não foi possível ler a planilha do fornecedor.")
            return None

        df_planilha = _normalizar_df(df_planilha)
        df_planilha = limpar_gtin_invalido(df_planilha)

        _salvar_df_origem(
            df_planilha,
            origem="planilha",
            nome_ref=nome_planilha,
            hash_ref=hash_planilha,
        )

        log_debug(
            f"Planilha de origem carregada: {nome_planilha} "
            f"({len(df_planilha)} linha(s), {len(df_planilha.columns)} coluna(s))"
        )

        return df_planilha
    except Exception as e:
        st.error("Erro ao carregar a planilha do fornecedor.")
        log_debug(f"Erro ao carregar planilha de origem: {e}", "ERRO")
        return None


# ==========================================================
# LEITURA DE XML
# ==========================================================


def _processar_upload_xml(arquivo_xml) -> pd.DataFrame | None:
    try:
        if arquivo_xml is None:
            return None

        nome_xml = _nome_arquivo(arquivo_xml)
        hash_xml = _hash_arquivo_upload(arquivo_xml)

        hash_anterior = st.session_state.get("arquivo_origem_hash", "")
        nome_anterior = st.session_state.get("arquivo_origem_nome", "")

        if hash_xml != hash_anterior or nome_xml != nome_anterior:
            _limpar_estado_origem()

        try:
            arquivo_xml.seek(0)
            conteudo = arquivo_xml.read()
            if isinstance(conteudo, bytes):
                conteudo = conteudo.decode("utf-8", errors="ignore")
        except Exception:
            conteudo = ""

        if not conteudo.strip():
            st.error("Não foi possível ler o XML da nota fiscal.")
            return None

        df_xml = pd.DataFrame(
            [
                {
                    "Arquivo": nome_xml,
                    "Tipo": "XML",
                    "Conteúdo XML": conteudo[:5000],
                }
            ]
        )

        df_xml = _normalizar_df(df_xml)
        df_xml = limpar_gtin_invalido(df_xml)

        _salvar_df_origem(
            df_xml,
            origem="xml",
            nome_ref=nome_xml,
            hash_ref=hash_xml,
        )

        log_debug(
            f"XML de origem carregado: {nome_xml} "
            f"({len(df_xml)} linha(s), {len(df_xml.columns)} coluna(s))"
        )

        return df_xml
    except Exception as e:
        st.error("Erro ao carregar o XML da nota fiscal.")
        log_debug(f"Erro ao carregar XML de origem: {e}", "ERRO")
        return None


# ==========================================================
# LEITURA DE PDF
# ==========================================================


def _extrair_texto_pdf(uploaded_file) -> str:
    if uploaded_file is None:
        return ""

    conteudo_bytes = b""

    try:
        uploaded_file.seek(0)
        conteudo_bytes = uploaded_file.read()
    except Exception:
        conteudo_bytes = b""

    if not conteudo_bytes:
        return ""

    texto_total = ""

    try:
        from pypdf import PdfReader  # type: ignore

        from io import BytesIO

        reader = PdfReader(BytesIO(conteudo_bytes))
        textos = []

        for pagina in reader.pages:
            try:
                textos.append(pagina.extract_text() or "")
            except Exception:
                textos.append("")

        texto_total = "\n".join(textos).strip()
        if texto_total:
            return texto_total
    except Exception:
        pass

    try:
        import PyPDF2  # type: ignore

        from io import BytesIO

        reader = PyPDF2.PdfReader(BytesIO(conteudo_bytes))
        textos = []

        for pagina in reader.pages:
            try:
                textos.append(pagina.extract_text() or "")
            except Exception:
                textos.append("")

        texto_total = "\n".join(textos).strip()
        if texto_total:
            return texto_total
    except Exception:
        pass

    return ""


def _processar_upload_pdf(arquivo_pdf) -> pd.DataFrame | None:
    try:
        if arquivo_pdf is None:
            return None

        nome_pdf = _nome_arquivo(arquivo_pdf)
        hash_pdf = _hash_arquivo_upload(arquivo_pdf)

        hash_anterior = st.session_state.get("arquivo_origem_hash", "")
        nome_anterior = st.session_state.get("arquivo_origem_nome", "")

        if hash_pdf != hash_anterior or nome_pdf != nome_anterior:
            _limpar_estado_origem()

        texto_pdf = _extrair_texto_pdf(arquivo_pdf)

        if not str(texto_pdf).strip():
            st.error("Não foi possível extrair texto do PDF.")
            return None

        texto_limpo = texto_pdf.replace("\x00", " ").strip()

        df_pdf = pd.DataFrame(
            [
                {
                    "Arquivo": nome_pdf,
                    "Tipo": "PDF",
                    "Texto PDF": texto_limpo[:5000],
                }
            ]
        )

        df_pdf = _normalizar_df(df_pdf)

        _salvar_df_origem(
            df_pdf,
            origem="pdf",
            nome_ref=nome_pdf,
            hash_ref=hash_pdf,
        )

        st.session_state["origem_pdf_texto"] = texto_limpo
        st.session_state["origem_pdf_nome"] = nome_pdf

        log_debug(
            f"PDF de origem carregado: {nome_pdf} "
            f"({len(df_pdf)} linha(s), {len(df_pdf.columns)} coluna(s))"
        )

        return df_pdf
    except Exception as e:
        st.error("Erro ao carregar o PDF.")
        log_debug(f"Erro ao carregar PDF de origem: {e}", "ERRO")
        return None


# ==========================================================
# SITE
# ==========================================================


def render_origem_site() -> pd.DataFrame | None:
    st.info("Origem por site disponível para integração.")
    return st.session_state.get("df_origem")


# ==========================================================
# MODELO BLING
# ==========================================================


def _carregar_modelo(uploaded_file) -> pd.DataFrame | None:
    try:
        df = _ler_planilha(uploaded_file)
        if not _safe_df_estrutura(df):
            return None
        return _normalizar_df(df)
    except Exception as e:
        log_debug(f"Erro ao carregar modelo Bling: {e}", "ERRO")
        return None


def render_modelo_bling(operacao: str | None = None) -> None:
    st.markdown("### Modelo oficial do Bling")

    operacao_normalizada = str(operacao or "").strip().lower()

    if "cadastro" in operacao_normalizada:
        tipo = "cadastro"
    elif "estoque" in operacao_normalizada:
        tipo = "estoque"
    else:
        tipo = str(st.session_state.get("tipo_operacao_bling") or "").strip().lower()

    if tipo == "estoque":
        arquivo_modelo = st.file_uploader(
            "Anexar modelo oficial do estoque",
            type=["xlsx", "xls", "xlsb", "csv"],
            key="upload_modelo_estoque",
        )

        if arquivo_modelo is not None:
            df_modelo = _carregar_modelo(arquivo_modelo)

            if _safe_df_estrutura(df_modelo):
                st.session_state["df_modelo_estoque"] = df_modelo.copy()
                st.session_state["df_modelo_mapeamento"] = df_modelo.copy()

                st.success("Modelo de estoque carregado com sucesso.")

                with st.expander("Prévia do modelo de estoque", expanded=False):
                    st.dataframe(
                        _df_preview_modelo(df_modelo),
                        use_container_width=True,
                        hide_index=True,
                    )
            else:
                st.error("Não foi possível ler o modelo de estoque.")
    else:
        arquivo_modelo = st.file_uploader(
            "Anexar modelo oficial do cadastro",
            type=["xlsx", "xls", "xlsb", "csv"],
            key="upload_modelo_cadastro",
        )

        if arquivo_modelo is not None:
            df_modelo = _carregar_modelo(arquivo_modelo)

            if _safe_df_estrutura(df_modelo):
                st.session_state["df_modelo_cadastro"] = df_modelo.copy()
                st.session_state["df_modelo_mapeamento"] = df_modelo.copy()

                st.success("Modelo de cadastro carregado com sucesso.")

                with st.expander("Prévia do modelo de cadastro", expanded=False):
                    st.dataframe(
                        _df_preview_modelo(df_modelo),
                        use_container_width=True,
                        hide_index=True,
                    )
            else:
                st.error("Não foi possível ler o modelo de cadastro.")


# ==========================================================
# ORIGEM UNIFICADA
# ==========================================================


def _rotulo_tipo_detectado(tipo: str) -> str:
    mapa = {
        "planilha": "Planilha",
        "xml": "XML",
        "pdf": "PDF",
        "site": "Site",
        "arquivo": "Arquivo",
    }
    return mapa.get(str(tipo or "").strip().lower(), "Arquivo")


def _detectar_tipo_origem_por_arquivo(uploaded_file) -> str:
    ext = _extensao_arquivo(uploaded_file)

    if ext in {"xlsx", "xls", "xlsb", "csv"}:
        return "planilha"
    if ext == "xml":
        return "xml"
    if ext == "pdf":
        return "pdf"
    return ""


def _processar_upload_arquivo_unificado(uploaded_file) -> tuple[pd.DataFrame | None, str]:
    if uploaded_file is None:
        return None, ""

    tipo_detectado = _detectar_tipo_origem_por_arquivo(uploaded_file)

    if tipo_detectado == "planilha":
        return _processar_upload_planilha(uploaded_file), tipo_detectado

    if tipo_detectado == "xml":
        return _processar_upload_xml(uploaded_file), tipo_detectado

    if tipo_detectado == "pdf":
        return _processar_upload_pdf(uploaded_file), tipo_detectado

    st.error("Formato não suportado para a origem dos dados.")
    return None, ""


def render_origem_entrada(on_change: Callable[[str], None] | None = None) -> pd.DataFrame | None:
    _garantir_etapa_origem_valida()

    opcoes = [
        "Buscar em site",
        "Upload de arquivos",
    ]

    origem_escolhida = st.radio(
        "Selecione a origem dos dados",
        opcoes,
        key="origem_dados_radio",
        horizontal=False,
    )

    df_origem: pd.DataFrame | None = None
    origem_atual = "site" if origem_escolhida == "Buscar em site" else "arquivo"

    if origem_escolhida == "Buscar em site":
        origem_anterior = str(st.session_state.get("origem_dados", "") or "").strip().lower()

        _set_if_changed("origem_dados", "site")

        if origem_anterior != "site":
            _resetar_fluxo_para_origem()
            if callable(on_change):
                try:
                    on_change("site")
                except Exception as e:
                    log_debug(f"Erro no callback de troca de origem: {e}", "ERRO")

        df_site = render_origem_site()

        if _safe_df_com_linhas(df_site):
            df_site = limpar_gtin_invalido(df_site)
            _salvar_df_origem(df_site, origem="site")
            df_origem = df_site

    else:
        st.markdown("### Upload de arquivos")

        arquivo_origem = st.file_uploader(
            "Anexar arquivo da origem",
            type=["xlsx", "xls", "xlsb", "csv", "xml", "pdf"],
            key="arquivo_origem_unificado",
            help=f"Formatos aceitos: {texto_extensoes_upload_origem()}.",
        )

        if arquivo_origem is not None:
            tipo_detectado = _detectar_tipo_origem_por_arquivo(arquivo_origem)

            if tipo_detectado:
                st.caption(f"Tipo detectado: {_rotulo_tipo_detectado(tipo_detectado)}")
                origem_atual = tipo_detectado
                st.session_state["origem_dados_tipo_arquivo"] = tipo_detectado

                origem_anterior = str(st.session_state.get("origem_dados", "") or "").strip().lower()

                if origem_anterior != tipo_detectado:
                    _resetar_fluxo_para_origem()
                    if callable(on_change):
                        try:
                            on_change(tipo_detectado)
                        except Exception as e:
                            log_debug(f"Erro no callback de troca de origem: {e}", "ERRO")

                df_origem, tipo_processado = _processar_upload_arquivo_unificado(arquivo_origem)

                if tipo_processado:
                    _set_if_changed("origem_dados", tipo_processado)
            else:
                st.error("Não foi possível detectar o tipo do arquivo enviado.")
        else:
            _set_if_changed("origem_dados", "arquivo")

    if not _safe_df_com_linhas(df_origem):
        df_origem = st.session_state.get("df_origem")

    if tem_upload_ativo() and _safe_df_com_linhas(df_origem):
        with st.expander("Prévia rápida da origem", expanded=False):
            try:
                st.dataframe(
                    _df_preview_seguro(df_orig
