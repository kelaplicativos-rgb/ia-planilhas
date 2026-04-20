
from __future__ import annotations

import inspect
import io
from pathlib import Path
import xml.etree.ElementTree as ET

import pandas as pd
import streamlit as st

try:
    from bling_app_zero.core.site_agent import buscar_produtos_site_com_gpt
except Exception:
    buscar_produtos_site_com_gpt = None

try:
    from bling_app_zero.core.site_auth import (
        apply_inspection_to_state,
        auth_state_to_session,
        clear_auth_state_session,
        get_auth_headers_and_cookies,
        get_profile_for_url,
        inspect_site_auth,
        try_requests_login,
    )
except Exception:
    def apply_inspection_to_state(resultado) -> None:
        return None

    def auth_state_to_session(st_module=None) -> dict:
        return {}

    def clear_auth_state_session(st_module=None) -> None:
        return None

    def get_auth_headers_and_cookies() -> dict:
        return {}

    def inspect_site_auth(url_site: str):
        class _Dummy:
            provider_slug = "generic_public"
            status = "inativo"
        return _Dummy()

    def try_requests_login(**kwargs):
        class _Dummy:
            ok = False
            status = "indisponivel"
            message = "Fluxo de login requests indisponível."
            provider_slug = "generic_public"
        return _Dummy()

    def get_profile_for_url(url_site: str):
        class _Dummy:
            slug = "generic_public"
            nome = "Genérico"
            login_required = False
            login_url = url_site
            products_url = url_site
        return _Dummy()


try:
    from bling_app_zero.core.session_manager import (
        STATUS_LOGIN_CAPTCHA_DETECTADO,
        STATUS_LOGIN_REQUERIDO,
        STATUS_SESSAO_PRONTA,
        iniciar_login_assistido,
        montar_auth_context,
        obter_status_login_da_sessao,
        salvar_status_login_em_sessao,
        sessao_esta_pronta,
    )
except Exception:
    STATUS_LOGIN_CAPTCHA_DETECTADO = "login_captcha_detectado"
    STATUS_LOGIN_REQUERIDO = "login_required"
    STATUS_SESSAO_PRONTA = "session_ready"

    def iniciar_login_assistido(
        *,
        base_url: str,
        fornecedor: str = "",
        login_url: str = "",
        products_url: str = "",
        timeout_ms: int = 300000,
        headless: bool = False,
    ) -> dict:
        return {
            "ok": False,
            "status": "erro",
            "mensagem": "Login assistido indisponível neste ambiente.",
        }

    def montar_auth_context(base_url: str, fornecedor: str = "") -> dict:
        return {}

    def obter_status_login_da_sessao() -> dict:
        return {}

    def salvar_status_login_em_sessao(
        *,
        base_url: str,
        status: str,
        mensagem: str = "",
        exige_login: bool = False,
        captcha_detectado: bool = False,
        fornecedor: str = "",
    ) -> None:
        return None

    def sessao_esta_pronta(base_url: str, fornecedor: str = "") -> bool:
        return False


from bling_app_zero.ui.app_helpers import (
    ir_para_etapa,
    log_debug,
    safe_df_dados,
    safe_df_estrutura,
)

EXTENSOES_ORIGEM = {".csv", ".xlsx", ".xls", ".xml", ".pdf"}
EXTENSOES_MODELO = {".csv", ".xlsx", ".xls"}


def _extensao(upload) -> str:
    nome = str(getattr(upload, "name", "") or "").strip().lower()
    return Path(nome).suffix.lower()


def _eh_excel_familia(ext: str) -> bool:
    return ext in {".csv", ".xlsx", ".xls"}


def _normalizar_df(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()

    base = df.copy().fillna("")
    base.columns = [str(c).strip() for c in base.columns]
    return base


def _resetar_flag_avanco_origem() -> None:
    st.session_state["origem_pronta_para_avancar"] = False


def _limpar_estado_origem() -> None:
    for chave in [
        "df_origem",
        "origem_upload_nome",
        "origem_upload_bytes",
        "origem_upload_tipo",
        "origem_upload_ext",
        "site_busca_diagnostico_df",
        "site_busca_diagnostico_total_descobertos",
        "site_busca_diagnostico_total_validos",
        "site_busca_diagnostico_total_rejeitados",
        "site_busca_login_status",
    ]:
        st.session_state.pop(chave, None)

    _resetar_flag_avanco_origem()


def _limpar_estado_modelo() -> None:
    for chave in [
        "df_modelo",
        "modelo_upload_nome",
        "modelo_upload_bytes",
        "modelo_upload_tipo",
        "modelo_upload_ext",
    ]:
        st.session_state.pop(chave, None)

    _resetar_flag_avanco_origem()


def _guardar_upload_bruto(chave_prefixo: str, upload, tipo: str) -> None:
    st.session_state[f"{chave_prefixo}_nome"] = str(upload.name)
    st.session_state[f"{chave_prefixo}_bytes"] = upload.getvalue()
    st.session_state[f"{chave_prefixo}_tipo"] = tipo
    st.session_state[f"{chave_prefixo}_ext"] = _extensao(upload)
    _resetar_flag_avanco_origem()


def _ler_tabular(upload) -> pd.DataFrame:
    nome = str(upload.name).lower()

    if nome.endswith(".csv"):
        bruto = upload.getvalue()

        for encoding in ("utf-8", "utf-8-sig", "latin1"):
            for sep in (";", ",", "\t", "|"):
                try:
                    df = pd.read_csv(
                        io.BytesIO(bruto),
                        sep=sep,
                        dtype=str,
                        encoding=encoding,
                        engine="python",
                    ).fillna("")
                    df.columns = [str(c).strip() for c in df.columns if str(c).strip()]
                    if len(df.columns) > 0:
                        return df
                except Exception:
                    continue

        raise ValueError("Não foi possível ler o CSV.")

    if nome.endswith(".xlsx") or nome.endswith(".xls"):
        df = pd.read_excel(upload, dtype=str).fillna("")
        df.columns = [str(c).strip() for c in df.columns if str(c).strip()]
        return df

    raise ValueError("Arquivo tabular inválido.")


def _parse_xml_nfe(upload) -> pd.DataFrame:
    try:
        xml_bytes = upload.getvalue()
        root = ET.fromstring(xml_bytes)
    except Exception:
        return pd.DataFrame()

    ns = {"nfe": "http://www.portalfiscal.inf.br/nfe"}
    itens = root.findall(".//nfe:det", ns)
    rows = []

    for det in itens:
        prod = det.find(".//nfe:prod", ns)
        if prod is None:
            continue

        def get(tag: str) -> str:
            el = prod.find(f"nfe:{tag}", ns)
            return el.text.strip() if el is not None and el.text else ""

        gtin = get("cEAN")
        if gtin in {"SEM GTIN", "SEM EAN"}:
            gtin = ""

        rows.append(
            {
                "Código": get("cProd"),
                "Descrição": get("xProd"),
                "NCM": get("NCM"),
                "CFOP": get("CFOP"),
                "Unidade": get("uCom"),
                "Quantidade": get("qCom"),
                "Preço de custo": get("vUnCom"),
                "Valor total": get("vProd"),
                "GTIN": gtin,
            }
        )

    return pd.DataFrame(rows)


def _preview_dataframe(df: pd.DataFrame, titulo: str) -> None:
    st.markdown(f"**{titulo}**")

    if not isinstance(df, pd.DataFrame):
        st.info("Arquivo sem estrutura tabular.")
        return

    if len(df.columns) == 0:
        st.error("Nenhuma coluna encontrada no arquivo.")
        return

    if df.empty:
        st.success("Arquivo carregado corretamente, mas sem linhas de dados.")
        preview = pd.DataFrame(columns=df.columns)
        st.dataframe(preview, use_container_width=True)
        return

    st.dataframe(df.head(10), use_container_width=True)


def _processar_upload_origem(upload) -> None:
    if upload is None:
        return

    _limpar_estado_origem()
    ext = _extensao(upload)

    if ext not in EXTENSOES_ORIGEM:
        st.error("Arquivo de origem inválido. Envie CSV, XLSX, XLS, XML ou PDF.")
        return

    if _eh_excel_familia(ext):
        try:
            df = _normalizar_df(_ler_tabular(upload))
        except Exception as exc:
            st.error(f"Não foi possível ler a planilha de origem: {exc}")
            return

        if not safe_df_dados(df):
            st.error("A planilha de origem precisa ter linhas com dados.")
            return

        st.session_state["df_origem"] = df
        _guardar_upload_bruto("origem_upload", upload, "tabular")
        st.success(f"Arquivo de origem carregado: {upload.name}")
        _preview_dataframe(df, "Preview da origem")
        return

    if ext == ".xml":
        df = _parse_xml_nfe(upload)
        if not safe_df_dados(df):
            st.error("Não foi possível extrair dados do XML.")
            return

        st.session_state["df_origem"] = df
        _guardar_upload_bruto("origem_upload", upload, "xml")
        st.success("XML convertido com sucesso.")
        _preview_dataframe(df, "Preview do XML")
        return

    _guardar_upload_bruto("origem_upload", upload, "documento")
    st.warning("PDF ainda não processado automaticamente.")


def _processar_upload_modelo(upload) -> None:
    if upload is None:
        return

    _limpar_estado_modelo()
    ext = _extensao(upload)

    if ext not in EXTENSOES_MODELO:
        st.error("Arquivo modelo inválido. Envie CSV, XLSX ou XLS.")
        return

    try:
        df = _normalizar_df(_ler_tabular(upload))
    except Exception as exc:
        st.error(f"Não foi possível ler o modelo: {exc}")
        return

    if not safe_df_estrutura(df):
        st.error("O modelo precisa ter pelo menos os cabeçalhos/colunas.")
        return

    st.session_state["df_modelo"] = df
    _guardar_upload_bruto("modelo_upload", upload, "tabular")
    st.success(f"Modelo carregado: {upload.name}")
    _preview_dataframe(df, "Preview do modelo")


def _origem_pronta() -> bool:
    return safe_df_dados(st.session_state.get("df_origem"))


def _modelo_pronto() -> bool:
    return safe_df_estrutura(st.session_state.get("df_modelo"))


def _fornecedor_slug(url_site: str) -> str:
    valor = str(url_site or "").strip().lower()
    valor = valor.replace("https://", "").replace("http://", "").replace("www.", "")
    for ch in ["/", ".", "-", "?", "&", "="]:
        valor = valor.replace(ch, "_")
    while "__" in valor:
        valor = valor.replace("__", "_")
    return valor.strip("_") or "fornecedor"


def _auth_state_atual() -> dict:
    base = st.session_state.get("site_auth_state", {})
    if isinstance(base, dict):
        return dict(base)
    return {}


def _merge_auth_states(*states: dict) -> dict:
    merged: dict = {}
    for state in states:
        if isinstance(state, dict):
            merged.update(state)
    return merged


def _sync_auth_state_com_session_manager(url_site: str) -> dict:
    slug = _fornecedor_slug(url_site)
    estado_atual = _auth_state_atual()
    estado_site_auth = auth_state_to_session(st)

    contexto_salvo = montar_auth_context(base_url=url_site, fornecedor=slug)
    status_login = obter_status_login_da_sessao()

    estado_final = _merge_auth_states(estado_atual, estado_site_auth)

    if isinstance(status_login, dict) and status_login:
        estado_final["status"] = status_login.get("status", estado_final.get("status", "inativo"))
        estado_final["last_message"] = status_login.get("mensagem", estado_final.get("last_message", ""))
        estado_final["requires_login"] = bool(
            status_login.get("exige_login", estado_final.get("requires_login", False))
        )
        estado_final["captcha_detected"] = bool(
            status_login.get("captcha_detectado", estado_final.get("captcha_detected", False))
        )
        estado_final["session_ready"] = bool(
            status_login.get("session_ready", estado_final.get("session_ready", False))
        )
        estado_final["manual_mode"] = bool(
            status_login.get("manual_mode", estado_final.get("manual_mode", False))
        )

    if isinstance(contexto_salvo, dict) and contexto_salvo:
        estado_final["auth_context"] = contexto_salvo
        estado_final["products_url"] = str(
            contexto_salvo.get("products_url", estado_final.get("products_url", url_site))
        ).strip() or url_site
        estado_final["storage_state_path"] = str(contexto_salvo.get("storage_state_path", "") or "").strip()
        estado_final["session_ready"] = bool(
            contexto_salvo.get("session_ready", estado_final.get("session_ready", False))
        )
        estado_final["manual_mode"] = bool(
            contexto_salvo.get("manual_mode", estado_final.get("manual_mode", False))
        )
        estado_final["status"] = str(
            contexto_salvo.get("status", estado_final.get("status", "inativo"))
        ).strip() or "inativo"

    estado_final["provider_name"] = str(
        estado_final.get("provider_name") or estado_final.get("provider_slug") or _fornecedor_slug(url_site)
    ).strip()
    estado_final["provider_slug"] = str(
        estado_final.get("provider_slug") or _fornecedor_slug(url_site)
    ).strip()
    estado_final["auth_mode"] = "login" if bool(estado_final.get("requires_login", False)) else "public"

    st.session_state["site_auth_state"] = estado_final
    return estado_final


def _render_operacao() -> None:
    tipo_atual = st.session_state.get("tipo_operacao", "cadastro")
    opcoes = {
        "Cadastro de Produtos": "cadastro",
        "Atualização de Estoque": "estoque",
    }

    label_inicial = "Cadastro de Produtos"
    for label, valor in opcoes.items():
        if valor == tipo_atual:
            label_inicial = label
            break

    escolha = st.radio(
        "Escolha a operação",
        options=list(opcoes.keys()),
        index=list(opcoes.keys()).index(label_inicial),
        horizontal=True,
        key="tipo_operacao_visual",
    )

    novo_tipo = opcoes[escolha]
    tipo_anterior = st.session_state.get("tipo_operacao")

    if tipo_anterior != novo_tipo:
        _resetar_flag_avanco_origem()

    st.session_state["tipo_operacao"] = novo_tipo
    st.session_state["tipo_operacao_bling"] = novo_tipo


def _render_origem_arquivo() -> None:
    st.markdown("### Arquivo do fornecedor")

    upload_origem = st.file_uploader(
        "Toque para selecionar o arquivo do fornecedor",
        key="upload_origem",
    )

    if upload_origem is not None:
        _processar_upload_origem(upload_origem)


def _carimbar_execucao_site(total_produtos: int, url_site: str) -> None:
    from datetime import datetime

    st.session_state["site_auto_ultima_execucao"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state["site_auto_ultima_url"] = url_site
    st.session_state["site_auto_ultimo_total_produtos"] = int(total_produtos)
    st.session_state["site_auto_status"] = (
        "ativo" if st.session_state.get("site_auto_loop_ativo", False) else "inativo"
    )


def _contexto_login_manual_confirmado(url_site: str) -> dict:
    slug = _fornecedor_slug(url_site)
    estado = _sync_auth_state_com_session_manager(url_site)

    contexto_salvo = estado.get("auth_context", {}) if isinstance(estado, dict) else {}
    if isinstance(contexto_salvo, dict) and (contexto_salvo.get("session_ready") or contexto_salvo.get("manual_mode")):
        return contexto_salvo

    products_url = str(estado.get("products_url", "") or "").strip() or url_site

    return {
        "manual_mode": True,
        "session_ready": False,
        "fornecedor_slug": slug,
        "base_url": url_site,
        "products_url": products_url,
        "headers": {},
        "cookies": [],
    }


def _chamar_busca_site_compativel(url_site: str, intervalo: int):
    if buscar_produtos_site_com_gpt is None:
        raise RuntimeError("Módulo de busca por site indisponível.")

    estado_auth = _sync_auth_state_com_session_manager(url_site)
    auth_context = {}

    if bool(estado_auth.get("session_ready", False)) or bool(estado_auth.get("manual_mode", False)):
        auth_context = estado_auth.get("auth_context", {}) or {}
    else:
        auth_context = get_auth_headers_and_cookies() or {}

    if bool(st.session_state.get("site_login_manual_confirmado", False)):
        auth_context = _contexto_login_manual_confirmado(url_site)

    st.session_state["site_auth_context"] = auth_context

    kwargs = {
        "base_url": url_site,
        "diagnostico": True,
    }

    try:
        assinatura = inspect.signature(buscar_produtos_site_com_gpt)
        parametros = assinatura.parameters

        if "termo" in parametros:
            kwargs["termo"] = ""
        if "limite_links" in parametros:
            kwargs["limite_links"] = None
        if "modo_loop" in parametros:
            kwargs["modo_loop"] = False
        if "intervalo_segundos" in parametros:
            kwargs["intervalo_segundos"] = intervalo
        if "auth_context" in parametros:
            kwargs["auth_context"] = auth_context
    except Exception:
        pass

    return buscar_produtos_site_com_gpt(**kwargs)


def _executar_busca_site(url_site: str) -> None:
    if not url_site:
        st.error("Informe a URL base do fornecedor.")
        return

    if not buscar_produtos_site_com_gpt:
        st.error("Módulo de busca por site indisponível.")
        return

    estado_auth = _sync_auth_state_com_session_manager(url_site)
    requires_login = bool(estado_auth.get("requires_login", False))
    session_ready = bool(estado_auth.get("session_ready", False))
    manual_mode = bool(estado_auth.get("manual_mode", False))
    login_manual_confirmado = bool(st.session_state.get("site_login_manual_confirmado", False))

    if requires_login and not session_ready and not manual_mode and not login_manual_confirmado:
        st.error("Este fornecedor exige login. Faça o login assistido antes de iniciar a leitura do catálogo.")
        return

    intervalo = int(st.session_state.get("site_auto_intervalo_segundos", 60) or 60)
    st.session_state["site_auto_status"] = "executando"
    log_debug(
        f"Disparo manual do monitoramento do site | url={url_site} | intervalo={intervalo}s",
        nivel="INFO",
    )

    try:
        df_site = _chamar_busca_site_compativel(url_site, intervalo)
        _sync_auth_state_com_session_manager(url_site)

        if not isinstance(df_site, pd.DataFrame) or df_site.empty:
            estado_apos_busca = _sync_auth_state_com_session_manager(url_site)
            status_bloqueio = str(estado_apos_busca.get("status", "") or "").strip()

            if status_bloqueio in {STATUS_LOGIN_CAPTCHA_DETECTADO, STATUS_LOGIN_REQUERIDO}:
                st.warning(
                    "O fornecedor bloqueou a leitura automática. "
                    "Use o login assistido para salvar a sessão e tentar novamente."
                )
            else:
                st.warning("Nenhum produto encontrado.")

            st.session_state["site_auto_status"] = "erro"
            _carimbar_execucao_site(0, url_site)
            return

        st.session_state["df_origem"] = df_site
        st.session_state["origem_upload_tipo"] = "site_gpt"
        st.session_state["origem_upload_nome"] = f"varredura_site_{url_site}"
        st.session_state["origem_upload_ext"] = "site_gpt"

        total = int(len(df_site))
        _carimbar_execucao_site(total, url_site)

        st.success(f"{total} produtos encontrados")
        _preview_dataframe(df_site, "Preview do site")
        log_debug(f"Monitoramento manual executado com {total} produto(s).", nivel="INFO")

    except Exception as exc:
        st.session_state["site_auto_status"] = "erro"
        st.error(f"Falha ao executar busca no site: {exc}")
        log_debug(f"Falha ao executar monitoramento do site: {exc}", nivel="ERRO")


def _render_status_auth_cards(auth_state: dict) -> None:
    provider_name = str(auth_state.get("provider_name", "") or "").strip() or "Não identificado"
    status = str(auth_state.get("status", "inativo") or "inativo").strip()
    auth_mode = str(auth_state.get("auth_mode", "public") or "public").strip()
    requires_login = bool(auth_state.get("requires_login", False))
    session_ready = bool(auth_state.get("session_ready", False))
    manual_mode = bool(auth_state.get("manual_mode", False))
    login_manual_confirmado = bool(st.session_state.get("site_login_manual_confirmado", False))

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Fornecedor", provider_name)
    with c2:
        st.metric("Modo", "Login" if auth_mode == "login" else "Público")
    with c3:
        st.metric("Exige login", "Sim" if requires_login else "Não")
    with c4:
        status_sessao = "Sim" if session_ready else ("Manual" if (manual_mode or login_manual_confirmado) else "Não")
        st.metric("Sessão pronta", status_sessao)

    st.caption(f"Status atual: {status}")


def _render_bloco_inspecao_site(url_site: str) -> None:
    auth_state_to_session(st)
    auth_state = _sync_auth_state_com_session_manager(url_site)

    st.markdown("#### Diagnóstico de acesso do fornecedor")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔎 Inspecionar acesso do site", use_container_width=True, key="btn_inspecionar_auth_site"):
            resultado = inspect_site_auth(url_site)
            apply_inspection_to_state(resultado)
            _sync_auth_state_com_session_manager(url_site)
            log_debug(
                f"Inspeção de autenticação executada | provider={getattr(resultado, 'provider_slug', 'desconhecido')} | status={getattr(resultado, 'status', 'inativo')}",
                nivel="INFO",
            )
            st.rerun()

    with col2:
        if st.button("🧹 Limpar sessão do fornecedor", use_container_width=True, key="btn_limpar_auth_site"):
            clear_auth_state_session(st)
            st.session_state["site_login_manual_confirmado"] = False
            salvar_status_login_em_sessao(
                base_url=url_site,
                fornecedor=_fornecedor_slug(url_site),
                status="inativo",
                mensagem="Sessão do fornecedor foi limpa.",
                exige_login=False,
                captcha_detectado=False,
            )
            st.session_state["site_auth_state"] = {}
            log_debug("Sessão autenticada do fornecedor foi limpa.", nivel="INFO")
            st.rerun()

    auth_state = _sync_auth_state_com_session_manager(url_site)
    _render_status_auth_cards(auth_state)

    if auth_state.get("last_message"):
        st.info(str(auth_state.get("last_message")))

    if auth_state.get("captcha_detected"):
        st.warning(
            "Este fornecedor apresenta indício de captcha. "
            "Use o login assistido com sessão persistente antes de rodar o crawler."
        )


def _render_bloco_login_assistido(url_site: str, login_url: str, products_url: str) -> None:
    st.markdown("#### Login assistido do fornecedor")

    st.caption(
        "Use este fluxo quando o fornecedor exigir login ou captcha. "
        "Se o ambiente não abrir navegador automaticamente, o sistema vai orientar o login manual."
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔐 Fazer login assistido", use_container_width=True, key="btn_login_assistido_fornecedor"):
            resultado = iniciar_login_assistido(
                base_url=url_site,
                fornecedor=_fornecedor_slug(url_site),
                login_url=login_url,
                products_url=products_url,
                timeout_ms=300000,
                headless=False,
            )

            if bool(resultado.get("ok", False)):
                st.session_state["site_login_manual_confirmado"] = bool(resultado.get("manual_mode", False))

                mensagem = str(resultado.get("mensagem", "Sessão autenticada salva com sucesso."))
                salvar_status_login_em_sessao(
                    base_url=url_site,
                    fornecedor=_fornecedor_slug(url_site),
                    status=STATUS_SESSAO_PRONTA,
                    mensagem=mensagem,
                    exige_login=False,
                    captcha_detectado=False,
                )
                st.success(mensagem)

                log_debug(
                    f"Login assistido concluído | fornecedor={_fornecedor_slug(url_site)} | manual_mode={bool(resultado.get('manual_mode', False))}",
                    nivel="INFO",
                )
            else:
                status = str(resultado.get("status", "erro") or "erro").strip()
                mensagem = str(resultado.get("mensagem", "Falha ao executar login assistido.") or "").strip()
                salvar_status_login_em_sessao(
                    base_url=url_site,
                    fornecedor=_fornecedor_slug(url_site),
                    status=status,
                    mensagem=mensagem,
                    exige_login=True,
                    captcha_detectado=(status == STATUS_LOGIN_CAPTCHA_DETECTADO),
                )
                st.warning(mensagem or "Falha ao executar login assistido.")
                log_debug(
                    f"Falha no login assistido | fornecedor={_fornecedor_slug(url_site)} | status={status}",
                    nivel="ERRO",
                )

            _sync_auth_state_com_session_manager(url_site)
            st.rerun()

    with col2:
        if st.button("♻️ Recarregar sessão salva", use_container_width=True, key="btn_recarregar_sessao_assistida"):
            _sync_auth_state_com_session_manager(url_site)
            st.rerun()

    estado = _sync_auth_state_com_session_manager(url_site)
    if bool(estado.get("manual_mode", False)) or bool(st.session_state.get("site_login_manual_confirmado", False)):
        st.success("Login manual já confirmado. Você já pode tentar ler o catálogo do fornecedor.")


def _render_bloco_login_fornecedor(url_site: str) -> None:
    auth_state = _sync_auth_state_com_session_manager(url_site)
    profile = get_profile_for_url(url_site)

    login_url_default = str(auth_state.get("login_url", "") or "").strip() or profile.login_url
    products_url_default = str(auth_state.get("products_url", "") or "").strip() or profile.products_url or url_site

    st.markdown("#### Acesso autenticado do fornecedor")

    auth_strategy = st.radio(
        "Como deseja tratar o acesso?",
        options=[
            "Somente detectar se o site exige login",
            "Informar credenciais e tentar validar sessão",
            "Abrir login assistido no navegador",
        ],
        horizontal=False,
        key="site_auth_strategy",
    )

    login_url = st.text_input(
        "URL de login",
        value=login_url_default,
        key="site_login_url",
    ).strip()

    products_url = st.text_input(
        "URL da área de produtos",
        value=products_url_default,
        key="site_products_url",
    ).strip()

    if auth_strategy == "Informar credenciais e tentar validar sessão":
        username = st.text_input(
            "Usuário / e-mail do fornecedor",
            key="site_login_username",
        ).strip()

        password = st.text_input(
            "Senha do fornecedor",
            type="password",
            key="site_login_password",
        ).strip()

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔐 Validar sessão agora", use_container_width=True, key="btn_validar_sessao_fornecedor"):
                if not login_url:
                    st.error("Informe a URL de login.")
                    return

                if not products_url:
                    st.error("Informe a URL da área de produtos.")
                    return

                if not username:
                    st.error("Informe o usuário.")
                    return

                if not password:
                    st.error("Informe a senha.")
                    return

                resultado = try_requests_login(
                    login_url=login_url,
                    products_url=products_url,
                    username=username,
                    password=password,
                    profile=profile,
                )

                _sync_auth_state_com_session_manager(url_site)

                if resultado.ok:
                    st.session_state["site_login_manual_confirmado"] = False
                    st.success(resultado.message)
                    log_debug(
                        f"Sessão autenticada com sucesso | provider={resultado.provider_slug}",
                        nivel="INFO",
                    )
                else:
                    if resultado.status == "captcha_pendente":
                        st.warning(resultado.message)
                    else:
                        st.error(resultado.message)
                    log_debug(
                        f"Falha ao validar sessão | provider={resultado.provider_slug} | status={resultado.status}",
                        nivel="ERRO",
                    )

                st.rerun()

        with col2:
            if st.button("♻️ Recarregar status da sessão", use_container_width=True, key="btn_recarregar_status_sessao"):
                _sync_auth_state_com_session_manager(url_site)
                st.rerun()

    elif auth_strategy == "Abrir login assistido no navegador":
        _render_bloco_login_assistido(
            url_site=url_site,
            login_url=login_url,
            products_url=products_url,
        )

    auth_state = _sync_auth_state_com_session_manager(url_site)
    session_ready = bool(auth_state.get("session_ready", False))
    manual_mode = bool(auth_state.get("manual_mode", False))
    requires_login = bool(auth_state.get("requires_login", False))

    if requires_login and not session_ready and not manual_mode:
        st.warning("Fornecedor exige autenticação e a sessão ainda não está pronta.")

    if session_ready:
        st.success("Sessão autenticada pronta para leitura do catálogo.")

    if manual_mode:
        st.info("Login manual confirmado. Agora tente a leitura do catálogo.")


def _render_banner_status_login_site(url_site: str) -> None:
    auth_state = _sync_auth_state_com_session_manager(url_site)
    status = str(auth_state.get("status", "") or "").strip()
    session_ready = bool(auth_state.get("session_ready", False))
    manual_mode = bool(auth_state.get("manual_mode", False))
    login_manual_confirmado = bool(st.session_state.get("site_login_manual_confirmado", False))

    if session_ready:
        st.success("Sessão autenticada detectada e pronta para uso no crawler.")
        return

    if manual_mode or login_manual_confirmado:
        st.success("Login manual confirmado. Você já pode tentar a leitura do catálogo.")
        return

    if status == STATUS_LOGIN_CAPTCHA_DETECTADO:
        st.warning(
            "Fornecedor com login detectado e indício de captcha. "
            "Fluxo autenticado necessário."
        )
    elif status == STATUS_LOGIN_REQUERIDO:
        st.warning(
            "Fornecedor exige login antes da leitura do catálogo. "
            "Faça a autenticação para continuar."
        )


def _render_origem_site() -> None:
    st.markdown("### Busca no site do fornecedor")

    auth_state_to_session(st)

    url_site = st.text_input(
        "URL base do fornecedor",
        key="site_fornecedor_url",
    ).strip()

    if not url_site:
        st.info("Informe a URL para habilitar a busca, o diagnóstico e a autenticação do fornecedor.")
        return

    profile = get_profile_for_url(url_site)
    if profile.slug != "generic_public":
        st.caption(f"Perfil reconhecido: {profile.nome}")

    _sync_auth_state_com_session_manager(url_site)
    _render_bloco_inspecao_site(url_site)
    _render_banner_status_login_site(url_site)

    auth_state = _sync_auth_state_com_session_manager(url_site)
    requires_login = bool(auth_state.get("requires_login", False) or profile.login_required)
    session_ready = bool(auth_state.get("session_ready", False))
    manual_mode = bool(auth_state.get("manual_mode", False))
    status_auth = str(auth_state.get("status", "") or "").strip()

    if requires_login or status_auth in {STATUS_LOGIN_CAPTCHA_DETECTADO, STATUS_LOGIN_REQUERIDO}:
        st.markdown("---")
        _render_bloco_login_fornecedor(url_site)

    st.markdown("---")
    st.markdown("#### Leitura do catálogo")

    auth_state = _sync_auth_state_com_session_manager(url_site)
    session_ready = bool(auth_state.get("session_ready", False))
    manual_mode = bool(auth_state.get("manual_mode", False))
    effective_products_url = str(auth_state.get("products_url", "") or "").strip() or url_site
    effective_url = effective_products_url if (session_ready or manual_mode) else url_site

    if requires_login and not session_ready and not manual_mode:
        st.info(
            "Este fornecedor precisa de sessão autenticada. "
            "Depois que a sessão estiver pronta, a leitura será feita pela URL da área de produtos."
        )

    if manual_mode:
        st.info(
            "Login manual confirmado. Agora toque em ler catálogo para tentar a varredura."
        )

    col1, col2 = st.columns(2)

    with col1:
        label = "✨ Ler catálogo autenticado com GPT" if (requires_login or session_ready or manual_mode) else "✨ Varrer catálogo com GPT"
        if st.button(label, use_container_width=True, key="btn_varrer_site_gpt"):
            _executar_busca_site(effective_url)
            st.rerun()

    with col2:
        if st.button("🟢 Ativar monitoramento", use_container_width=True, key="btn_ativar_monitoramento_site"):
            if requires_login and not session_ready and not manual_mode:
                st.error("Antes de ativar o monitoramento, finalize o login assistido.")
            else:
                st.session_state["site_auto_loop_ativo"] = True
                st.session_state["site_auto_status"] = "ativo"
                st.success("Monitoramento automático ativado.")
                log_debug("Loop automático do site ativado.", nivel="INFO")
                st.rerun()

    origem_tipo = str(st.session_state.get("origem_upload_tipo", "") or "").strip().lower()
    origem_nome = str(st.session_state.get("origem_upload_nome", "") or "").strip().lower()
    site_ativo = "site_gpt" in origem_tipo or "varredura_site_" in origem_nome

    if site_ativo:
        st.markdown("---")
        with st.expander("⚙️ Automação do site", expanded=True):
            status = str(st.session_state.get("site_auto_status", "inativo") or "inativo")
            ultima_execucao = str(st.session_state.get("site_auto_ultima_execucao", "") or "").strip()
            ultimo_total = int(st.session_state.get("site_auto_ultimo_total_produtos", 0) or 0)

            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Loop automático", "Ativo" if st.session_state.get("site_auto_loop_ativo", False) else "Inativo")
            with c2:
                st.metric("Status", status.title())
            with c3:
                st.metric("Último total", ultimo_total)

            st.number_input(
                "Intervalo do monitoramento (segundos)",
                min_value=5,
                step=5,
                key="site_auto_intervalo_segundos",
                help="Define o intervalo base do monitoramento do site.",
            )

            st.write(f"**URL monitorada:** {effective_url}")
            if ultima_execucao:
                st.write(f"**Última execução:** {ultima_execucao}")

            b1, b2, b3 = st.columns(3)

            with b1:
                if st.button("▶️ Executar agora", use_container_width=True, key="btn_site_auto_executar_agora_origem"):
                    _executar_busca_site(effective_url)
                    st.rerun()

            with b2:
                if st.button("🟢 Ativar loop", use_container_width=True, key="btn_site_auto_ativar_origem"):
                    if requires_login and not session_ready and not manual_mode:
                        st.error("Valide a sessão autenticada antes de ativar o loop.")
                    else:
                        st.session_state["site_auto_loop_ativo"] = True
                        st.session_state["site_auto_status"] = "ativo"
                        st.success("Loop automático marcado como ativo.")
                        log_debug("Loop automático do site ativado.", nivel="INFO")
                        st.rerun()

            with b3:
                if st.button("⏹️ Parar loop", use_container_width=True, key="btn_site_auto_parar_origem"):
                    st.session_state["site_auto_loop_ativo"] = False
                    st.session_state["site_auto_status"] = "inativo"
                    st.info("Loop automático marcado como inativo.")
                    log_debug("Loop automático do site desativado.", nivel="INFO")
                    st.rerun()


def _render_modelo() -> None:
    upload_modelo = st.file_uploader("Enviar modelo", key="upload_modelo")

    if upload_modelo:
        _processar_upload_modelo(upload_modelo)


def _render_continuar() -> None:
    if _origem_pronta() and _modelo_pronto():
        if st.button("Continuar ➜", key="btn_continuar_origem"):
            ir_para_etapa("precificacao")


def render_origem_dados() -> None:
    st.subheader("1. Origem dos dados")

    _render_operacao()

    modo = st.radio(
        "Origem",
        ["Arquivo do fornecedor", "Buscar no site do fornecedor"],
        horizontal=True,
        key="modo_origem",
    )

    if modo == "Arquivo do fornecedor":
        _render_origem_arquivo()
    else:
        _render_origem_site()

    _render_modelo()
    _render_continuar()
