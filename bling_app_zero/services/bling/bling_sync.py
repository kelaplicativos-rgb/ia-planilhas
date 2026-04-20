
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import requests


BLING_API_BASE = "https://www.bling.com.br/Api/v3"


# ============================================================
# HELPERS BÁSICOS
# ============================================================

def _agora_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _normalizar_texto(valor: Any) -> str:
    if valor is None:
        return ""
    texto = str(valor).strip()
    if texto.lower() in {"nan", "none", "nat"}:
        return ""
    return texto


def _safe_lower(valor: Any) -> str:
    return _normalizar_texto(valor).lower()


def _to_float(valor: Any, default: float = 0.0) -> float:
    if valor is None:
        return default

    texto = _normalizar_texto(valor)
    if not texto:
        return default

    texto = texto.replace("R$", "").replace("r$", "").replace(" ", "")

    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(",", ".")

    try:
        return float(texto)
    except Exception:
        return default


def _to_int(valor: Any, default: int = 0) -> int:
    try:
        return int(round(_to_float(valor, float(default))))
    except Exception:
        return default


def _somente_digitos(valor: Any) -> str:
    return "".join(ch for ch in _normalizar_texto(valor) if ch.isdigit())


def _safe_df(df: Any) -> pd.DataFrame:
    if isinstance(df, pd.DataFrame):
        return df.copy()
    return pd.DataFrame()


def _safe_df_dados(df: Any) -> bool:
    return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0


def _streamlit_ctx():
    try:
        import streamlit as st
        return st
    except Exception:
        return None


def _log_debug(msg: str, nivel: str = "INFO") -> None:
    try:
        from bling_app_zero.ui.app_helpers import log_debug  # type: ignore
        log_debug(msg, nivel=nivel)
    except Exception:
        pass


# ============================================================
# DETECÇÃO DE COLUNAS
# ============================================================

def _coluna_existente(df: pd.DataFrame, nomes: list[str]) -> str:
    mapa = {_safe_lower(c): str(c) for c in df.columns}
    for nome in nomes:
        if _safe_lower(nome) in mapa:
            return mapa[_safe_lower(nome)]
    return ""


def _coluna_por_parcial(df: pd.DataFrame, termos: list[str]) -> str:
    if df is None or len(df.columns) == 0:
        return ""

    for col in df.columns:
        nome = _safe_lower(col)
        if any(termo in nome for termo in termos):
            return str(col)
    return ""


def _coluna_codigo(df: pd.DataFrame) -> str:
    col = _coluna_existente(df, ["Código", "codigo", "Código do produto", "SKU", "sku"])
    if col:
        return col

    col = _coluna_por_parcial(df, ["codigo", "código", "cod", "sku", "referencia", "referência", "id produto"])
    if col:
        _log_debug(f"Coluna de código detectada por aproximação: {col}", nivel="INFO")
        return col

    if len(df.columns) > 0:
        fallback = str(df.columns[0])
        _log_debug(
            f"Coluna de código não encontrada por nome exato; usando fallback da primeira coluna: {fallback}",
            nivel="ERRO",
        )
        return fallback

    return ""


def _coluna_descricao(df: pd.DataFrame) -> str:
    col = _coluna_existente(
        df,
        ["Descrição", "descricao", "Descrição do produto", "Nome", "nome", "Título", "titulo"],
    )
    if col:
        return col

    col = _coluna_por_parcial(df, ["descricao", "descrição", "nome", "titulo", "título", "produto"])
    if col:
        _log_debug(f"Coluna de descrição detectada por aproximação: {col}", nivel="INFO")
        return col

    return ""


def _coluna_descricao_curta(df: pd.DataFrame) -> str:
    col = _coluna_existente(df, ["Descrição Curta", "descricao curta", "Descrição curta"])
    if col:
        return col

    return _coluna_por_parcial(df, ["descricao curta", "descrição curta", "resumo"])


def _coluna_preco_venda(df: pd.DataFrame) -> str:
    col = _coluna_existente(df, ["Preço de venda", "preço de venda", "Preço calculado"])
    if col:
        return col

    return _coluna_por_parcial(df, ["preco", "preço", "valor", "venda"])


def _coluna_preco_estoque(df: pd.DataFrame) -> str:
    col = _coluna_existente(df, ["Preço unitário (OBRIGATÓRIO)", "preço unitário (obrigatório)"])
    if col:
        return col

    return _coluna_por_parcial(df, ["preco unitario", "preço unitário", "preco", "preço", "valor unitario", "valor unitário"])


def _coluna_gtin(df: pd.DataFrame) -> str:
    col = _coluna_existente(df, ["GTIN/EAN", "GTIN", "EAN", "gtin", "ean"])
    if col:
        return col

    return _coluna_por_parcial(df, ["gtin", "ean", "codigo de barras", "código de barras"])


def _coluna_categoria(df: pd.DataFrame) -> str:
    col = _coluna_existente(df, ["Categoria", "categoria"])
    if col:
        return col

    return _coluna_por_parcial(df, ["categoria", "departamento", "secao", "seção"])


def _coluna_imagens(df: pd.DataFrame) -> str:
    for col in df.columns:
        nome = _safe_lower(col)
        if nome in {"url imagens", "url imagem", "imagens", "imagem"} or "imagem" in nome:
            return str(col)
    return ""


def _coluna_situacao(df: pd.DataFrame) -> str:
    col = _coluna_existente(df, ["Situação", "situacao"])
    if col:
        return col

    return _coluna_por_parcial(df, ["situacao", "situação", "status"])


def _coluna_estoque(df: pd.DataFrame) -> str:
    col = _coluna_existente(
        df,
        [
            "Balanço (OBRIGATÓRIO)",
            "balanço (obrigatório)",
            "Quantidade",
            "quantidade",
            "Estoque",
            "estoque",
        ],
    )
    if col:
        return col

    return _coluna_por_parcial(df, ["balanco", "balanço", "quantidade", "estoque", "saldo", "qtd"])


def _coluna_deposito(df: pd.DataFrame) -> str:
    col = _coluna_existente(df, ["Depósito (OBRIGATÓRIO)", "depósito (obrigatório)", "Deposito"])
    if col:
        return col

    return _coluna_por_parcial(df, ["deposito", "depósito", "almoxarifado"])


def _coluna_url_produto(df: pd.DataFrame) -> str:
    col = _coluna_existente(df, ["URL Produto", "url produto", "url_produto", "Link Produto"])
    if col:
        return col

    return _coluna_por_parcial(df, ["url produto", "url_produto", "link produto", "produto url", "link"])


def _coluna_ncm(df: pd.DataFrame) -> str:
    col = _coluna_existente(df, ["NCM", "ncm"])
    if col:
        return col

    return _coluna_por_parcial(df, ["ncm"])


def _split_imagens(valor: Any) -> list[str]:
    texto = _normalizar_texto(valor)
    if not texto:
        return []

    bruto = texto.replace("\n", "|").replace("\r", "|").replace(";", "|").replace(",", "|")
    itens = []
    vistos: set[str] = set()

    for parte in bruto.split("|"):
        parte_limpa = _normalizar_texto(parte)
        if parte_limpa and parte_limpa not in vistos:
            vistos.add(parte_limpa)
            itens.append(parte_limpa)

    return itens


# ============================================================
# CONFIG
# ============================================================

@dataclass
class SyncConfig:
    tipo_operacao: str
    deposito_nome: str
    strategy: str
    auto_mode: str
    interval_value: int
    interval_unit: str
    dry_run: bool = False


# ============================================================
# IMPORTS SEGUROS
# ============================================================

def _safe_import_bling_auth():
    try:
        from bling_app_zero.core.bling_auth import BlingAuthManager  # type: ignore
        return {"BlingAuthManager": BlingAuthManager}
    except Exception:
        return None


def _safe_import_bling_user_session():
    try:
        from bling_app_zero.core.bling_user_session import get_current_user_key  # type: ignore
        return {"get_current_user_key": get_current_user_key}
    except Exception:
        return None


def _safe_import_site_agent():
    try:
        from bling_app_zero.core.site_agent import buscar_produtos_site_com_gpt  # type: ignore
        return buscar_produtos_site_com_gpt
    except Exception:
        return None


# ============================================================
# TOKEN / CLIENT
# ============================================================

def _obter_access_token() -> str:
    bling_auth = _safe_import_bling_auth()
    if bling_auth is not None:
        manager_cls = bling_auth.get("BlingAuthManager")
        if manager_cls is not None:
            try:
                user_key = "default"
                bling_user_session = _safe_import_bling_user_session()
                if bling_user_session is not None:
                    get_current_user_key = bling_user_session.get("get_current_user_key")
                    if callable(get_current_user_key):
                        user_key = _normalizar_texto(get_current_user_key()) or "default"

                auth = manager_cls(user_key=user_key)
                ok, token_or_msg = auth.get_valid_access_token()
                if ok:
                    token = _normalizar_texto(token_or_msg)
                    if token:
                        return token
            except Exception:
                pass

    return ""


class BlingApiClient:
    def __init__(self, access_token: str, timeout: int = 30) -> None:
        self.access_token = _normalizar_texto(access_token)
        self.timeout = timeout

    @property
    def disponivel(self) -> bool:
        return bool(self.access_token)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        json_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.disponivel:
            raise RuntimeError("Token do Bling não encontrado.")

        url = f"{BLING_API_BASE.rstrip('/')}/{endpoint.lstrip('/')}"

        response = requests.request(
            method=method.upper(),
            url=url,
            headers=self._headers(),
            params=params,
            json=json_payload,
            timeout=self.timeout,
        )

        try:
            conteudo = response.json()
        except Exception:
            conteudo = {"raw_text": response.text}

        if response.status_code >= 400:
            raise RuntimeError(
                f"Erro Bling {response.status_code} em {method.upper()} {endpoint}: {conteudo}"
            )

        return conteudo

    def buscar_produto_por_codigo(self, codigo: str) -> dict[str, Any] | None:
        codigo = _normalizar_texto(codigo)
        if not codigo:
            return None

        try:
            resposta = self._request("GET", "/produtos", params={"codigo": codigo, "limite": 100})
        except Exception:
            return None

        for item in resposta.get("data", []) or []:
            codigo_api = _normalizar_texto(item.get("codigo"))
            if codigo_api == codigo:
                return item

        return None

    def criar_produto(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/produtos", json_payload=payload)

    def atualizar_produto(self, produto_id: int | str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("PUT", f"/produtos/{produto_id}", json_payload=payload)


# ============================================================
# PAYLOAD
# ============================================================

def _montar_payload_produto(
    row: pd.Series,
    df: pd.DataFrame,
    config: SyncConfig,
) -> dict[str, Any]:
    codigo_col = _coluna_codigo(df)
    descricao_col = _coluna_descricao(df)
    descricao_curta_col = _coluna_descricao_curta(df)
    preco_venda_col = _coluna_preco_venda(df)
    preco_estoque_col = _coluna_preco_estoque(df)
    gtin_col = _coluna_gtin(df)
    categoria_col = _coluna_categoria(df)
    imagens_col = _coluna_imagens(df)
    situacao_col = _coluna_situacao(df)
    estoque_col = _coluna_estoque(df)
    deposito_col = _coluna_deposito(df)
    ncm_col = _coluna_ncm(df)

    codigo = _normalizar_texto(row.get(codigo_col))
    descricao = _normalizar_texto(row.get(descricao_col))
    descricao_curta = _normalizar_texto(row.get(descricao_curta_col))
    gtin = _somente_digitos(row.get(gtin_col))
    categoria = _normalizar_texto(row.get(categoria_col))
    situacao = _normalizar_texto(row.get(situacao_col)) or "Ativo"
    ncm = _somente_digitos(row.get(ncm_col))

    if config.tipo_operacao == "estoque":
        preco = _to_float(row.get(preco_estoque_col), 0.0)
    else:
        preco = _to_float(row.get(preco_venda_col), 0.0)

    saldo = _to_int(row.get(estoque_col), 0)
    deposito = _normalizar_texto(config.deposito_nome) or _normalizar_texto(row.get(deposito_col))
    imagens = _split_imagens(row.get(imagens_col))

    payload: dict[str, Any] = {
        "codigo": codigo,
        "nome": descricao,
    }

    if descricao_curta:
        payload["descricaoCurta"] = descricao_curta

    if preco > 0:
        payload["preco"] = preco

    if gtin:
        payload["gtin"] = gtin

    if ncm:
        payload["ncm"] = ncm

    if categoria:
        payload["categoria"] = {"descricao": categoria}

    if situacao:
        payload["situacao"] = situacao

    if imagens:
        payload["midias"] = [{"tipo": "URL", "url": url} for url in imagens]

    if deposito:
        payload["deposito"] = {"descricao": deposito}

    if saldo or config.tipo_operacao == "estoque":
        payload["estoque"] = {"saldoVirtualTotal": saldo}

    return payload


def _determinar_acao(strategy: str, produto_existente: dict[str, Any] | None) -> str:
    strategy = _safe_lower(strategy)

    if strategy == "cadastrar_novos":
        return "criar" if produto_existente is None else "ignorar"

    if strategy == "atualizar_existentes":
        return "atualizar" if produto_existente is not None else "ignorar"

    return "criar" if produto_existente is None else "atualizar"


# ============================================================
# AGENDAMENTO / FALLBACK SITE
# ============================================================

def _proxima_execucao(auto_mode: str, interval_value: int, interval_unit: str) -> str:
    auto_mode = _safe_lower(auto_mode)
    if auto_mode != "periodico":
        return ""

    valor = max(1, int(interval_value or 1))
    unidade = _safe_lower(interval_unit)

    agora = datetime.utcnow()
    if unidade == "horas":
        proxima = agora + timedelta(hours=valor)
    elif unidade == "dias":
        proxima = agora + timedelta(days=valor)
    else:
        proxima = agora + timedelta(minutes=valor)

    return proxima.replace(microsecond=0).isoformat() + "Z"


def _obter_metadata_site() -> dict[str, Any]:
    st = _streamlit_ctx()
    if st is None:
        return {
            "origem_site_ativa": False,
            "url_site": "",
            "modo_origem": "",
            "origem_upload_tipo": "",
            "origem_upload_nome": "",
        }

    modo_origem = _safe_lower(st.session_state.get("modo_origem", ""))
    origem_upload_tipo = _safe_lower(st.session_state.get("origem_upload_tipo", ""))
    origem_upload_nome = _safe_lower(st.session_state.get("origem_upload_nome", ""))
    url_site = _normalizar_texto(st.session_state.get("site_fornecedor_url", ""))

    origem_site_ativa = (
        "site" in modo_origem
        or "site_gpt" in origem_upload_tipo
        or "varredura_site_" in origem_upload_nome
    )

    return {
        "origem_site_ativa": origem_site_ativa,
        "url_site": url_site,
        "modo_origem": modo_origem,
        "origem_upload_tipo": origem_upload_tipo,
        "origem_upload_nome": origem_upload_nome,
    }


def _registrar_agendamento_local(config: SyncConfig, total_itens: int) -> dict[str, Any]:
    proxima_execucao = _proxima_execucao(
        config.auto_mode,
        config.interval_value,
        config.interval_unit,
    )

    info = {
        "ativo": config.auto_mode == "periodico",
        "modo": config.auto_mode,
        "interval_value": config.interval_value,
        "interval_unit": config.interval_unit,
        "proxima_execucao": proxima_execucao,
        "observacao": (
            "Configuração registrada na aplicação. Execução recorrente contínua depende do motor "
            "de agendamento/back-end da infraestrutura."
        ),
        "total_itens_referencia": int(total_itens),
    }

    st = _streamlit_ctx()
    if st is not None:
        st.session_state["bling_sync_periodico_config"] = info

    return info


def _executar_fallback_site_se_necessario(
    config: SyncConfig,
) -> dict[str, Any]:
    metadata_site = _obter_metadata_site()

    resultado = {
        "executado": False,
        "origem_site_ativa": bool(metadata_site.get("origem_site_ativa", False)),
        "url_site": _normalizar_texto(metadata_site.get("url_site")),
        "resultado_busca": None,
        "observacao": "",
    }

    if not resultado["origem_site_ativa"]:
        resultado["observacao"] = "Origem atual não veio da busca por site."
        return resultado

    resultado["observacao"] = (
        "Origem por site detectada. O fallback periódico/instantâneo está preparado para "
        "reutilizar a busca por site com GPT antes do envio ao Bling."
    )

    if config.auto_mode != "instantaneo":
        return resultado

    url_site = resultado["url_site"]
    buscar_produtos_site_com_gpt = _safe_import_site_agent()

    if not url_site or buscar_produtos_site_com_gpt is None:
        resultado["observacao"] = (
            "Modo instantâneo solicitado, mas a URL do site ou o serviço de busca GPT não está disponível."
        )
        return resultado

    try:
        _log_debug(
            f"Fallback do site acionado antes do envio | url={url_site} | modo={config.auto_mode}",
            nivel="INFO",
        )
        df_site = buscar_produtos_site_com_gpt(
            base_url=url_site,
            diagnostico=True,
        )
        resultado["executado"] = True
        resultado["resultado_busca"] = {
            "linhas_encontradas": int(len(df_site)) if isinstance(df_site, pd.DataFrame) else 0,
            "colunas_encontradas": int(len(df_site.columns)) if isinstance(df_site, pd.DataFrame) else 0,
        }
        resultado["observacao"] = (
            "Busca por site executada no modo instantâneo. A conversão GPT do crawler foi reutilizada antes do envio."
        )
    except Exception as exc:
        resultado["executado"] = False
        resultado["observacao"] = f"Falha ao executar fallback do site: {exc}"
        _log_debug(resultado["observacao"], nivel="ERRO")

    return resultado


# ============================================================
# RESULTADO E PERSISTÊNCIA
# ============================================================

def _persistir_resultado_sync(resumo: dict[str, Any]) -> None:
    st = _streamlit_ctx()
    if st is None:
        return

    st.session_state["bling_sync_last_result"] = resumo
    st.session_state["bling_sync_last_run_at"] = resumo.get("processado_em", "")
    st.session_state["bling_sync_next_run_at"] = resumo.get("proxima_execucao", "")


# ============================================================
# CORE SYNC
# ============================================================

def sincronizar_produtos_bling(
    df_final: pd.DataFrame,
    tipo_operacao: str = "cadastro",
    deposito_nome: str = "",
    strategy: str = "inteligente",
    auto_mode: str = "manual",
    interval_value: int = 15,
    interval_unit: str = "minutos",
    dry_run: bool = False,
) -> dict[str, Any]:
    df = _safe_df(df_final)

    config = SyncConfig(
        tipo_operacao=_safe_lower(tipo_operacao) or "cadastro",
        deposito_nome=_normalizar_texto(deposito_nome),
        strategy=_safe_lower(strategy) or "inteligente",
        auto_mode=_safe_lower(auto_mode) or "manual",
        interval_value=max(1, int(interval_value or 1)),
        interval_unit=_safe_lower(interval_unit) or "minutos",
        dry_run=bool(dry_run),
    )

    _log_debug(
        "Iniciando sincronização Bling | "
        f"tipo={config.tipo_operacao} | strategy={config.strategy} | auto_mode={config.auto_mode} | "
        f"interval={config.interval_value} {config.interval_unit} | dry_run={config.dry_run}",
        nivel="INFO",
    )

    if not _safe_df_dados(df):
        resumo = {
            "ok": False,
            "modo": "validacao",
            "mensagem": "DataFrame final vazio ou inválido.",
            "processado_em": _agora_iso(),
            "total_itens": 0,
            "resultados": [],
            "fallback_site": _executar_fallback_site_se_necessario(config),
            "agendamento": _registrar_agendamento_local(config, 0),
        }
        _persistir_resultado_sync(resumo)
        return resumo

    codigo_col = _coluna_codigo(df)
    descricao_col = _coluna_descricao(df)

    _log_debug(
        f"Colunas detectadas para sincronização | codigo={codigo_col or '-'} | descricao={descricao_col or '-'}",
        nivel="INFO",
    )

    if not codigo_col:
        resumo = {
            "ok": False,
            "modo": "validacao",
            "mensagem": "Coluna de código não encontrada na planilha final.",
            "processado_em": _agora_iso(),
            "total_itens": int(len(df)),
            "resultados": [],
            "fallback_site": _executar_fallback_site_se_necessario(config),
            "agendamento": _registrar_agendamento_local(config, int(len(df))),
        }
        _persistir_resultado_sync(resumo)
        return resumo

    if not descricao_col:
        resumo = {
            "ok": False,
            "modo": "validacao",
            "mensagem": "Coluna de descrição não encontrada na planilha final.",
            "processado_em": _agora_iso(),
            "total_itens": int(len(df)),
            "resultados": [],
            "fallback_site": _executar_fallback_site_se_necessario(config),
            "agendamento": _registrar_agendamento_local(config, int(len(df))),
        }
        _persistir_resultado_sync(resumo)
        return resumo

    access_token = _obter_access_token()
    client = BlingApiClient(access_token=access_token)

    fallback_site = _executar_fallback_site_se_necessario(config)

    resultados: list[dict[str, Any]] = []
    total_criados = 0
    total_atualizados = 0
    total_ignorados = 0
    total_erros = 0

    for indice, row in df.fillna("").iterrows():
        codigo = _normalizar_texto(row.get(codigo_col))
        descricao = _normalizar_texto(row.get(descricao_col))

        item_resultado: dict[str, Any] = {
            "linha": int(indice) + 1,
            "codigo": codigo,
            "descricao": descricao,
            "acao": "",
            "status": "",
            "produto_id": None,
            "mensagem": "",
        }

        if not codigo:
            item_resultado["status"] = "erro"
            item_resultado["mensagem"] = "Código vazio."
            resultados.append(item_resultado)
            total_erros += 1
            continue

        try:
            produto_existente = None
            if client.disponivel and not config.dry_run:
                produto_existente = client.buscar_produto_por_codigo(codigo)

            acao = _determinar_acao(config.strategy, produto_existente)
            item_resultado["acao"] = acao

            if acao == "ignorar":
                item_resultado["status"] = "ignorado"
                item_resultado["mensagem"] = "Item ignorado pela estratégia selecionada."
                resultados.append(item_resultado)
                total_ignorados += 1
                continue

            payload = _montar_payload_produto(row=row, df=df, config=config)

            if config.dry_run or not client.disponivel:
                item_resultado["status"] = "simulado"
                item_resultado["mensagem"] = (
                    "Simulação local executada."
                    if config.dry_run
                    else "Token do Bling não encontrado. Execução simulada."
                )
                item_resultado["payload"] = payload
                resultados.append(item_resultado)

                if acao == "criar":
                    total_criados += 1
                elif acao == "atualizar":
                    total_atualizados += 1
                continue

            if acao == "criar":
                resposta = client.criar_produto(payload)
                produto = resposta.get("data", {}) if isinstance(resposta, dict) else {}
                item_resultado["status"] = "criado"
                item_resultado["mensagem"] = "Produto cadastrado com sucesso."
                item_resultado["produto_id"] = produto.get("id")
                total_criados += 1
            else:
                produto_id = produto_existente.get("id") if isinstance(produto_existente, dict) else None
                resposta = client.atualizar_produto(produto_id, payload)
                produto = resposta.get("data", {}) if isinstance(resposta, dict) else {}
                item_resultado["status"] = "atualizado"
                item_resultado["mensagem"] = "Produto atualizado com sucesso."
                item_resultado["produto_id"] = produto.get("id") or produto_id
                total_atualizados += 1

            resultados.append(item_resultado)

        except Exception as exc:
            item_resultado["status"] = "erro"
            item_resultado["mensagem"] = str(exc)
            resultados.append(item_resultado)
            total_erros += 1

    ok = total_erros == 0
    agendamento = _registrar_agendamento_local(config, int(len(df)))

    resumo = {
        "ok": ok,
        "modo": "real" if client.disponivel and not config.dry_run else "simulacao",
        "processado_em": _agora_iso(),
        "tipo_operacao": config.tipo_operacao,
        "strategy": config.strategy,
        "auto_mode": config.auto_mode,
        "interval_value": config.interval_value,
        "interval_unit": config.interval_unit,
        "proxima_execucao": _proxima_execucao(
            config.auto_mode,
            config.interval_value,
            config.interval_unit,
        ),
        "deposito_nome": config.deposito_nome,
        "total_itens": int(len(df)),
        "total_criados": total_criados,
        "total_atualizados": total_atualizados,
        "total_ignorados": total_ignorados,
        "total_erros": total_erros,
        "resultados": resultados,
        "fallback_site": fallback_site,
        "agendamento": agendamento,
        "mensagem": (
            "Sincronização concluída com sucesso."
            if ok
            else "Sincronização concluída com pendências/erros."
        ),
    }

    _persistir_resultado_sync(resumo)

    _log_debug(
        "Sincronização finalizada | "
        f"modo={resumo['modo']} | total={resumo['total_itens']} | "
        f"criados={resumo['total_criados']} | atualizados={resumo['total_atualizados']} | "
        f"ignorados={resumo['total_ignorados']} | erros={resumo['total_erros']}",
        nivel="INFO" if ok else "ERRO",
    )

    return resumo


def enviar_produtos(
    df_final: pd.DataFrame,
    tipo_operacao: str = "cadastro",
    deposito_nome: str = "",
    strategy: str = "inteligente",
) -> dict[str, Any]:
    return sincronizar_produtos_bling(
        df_final=df_final,
        tipo_operacao=tipo_operacao,
        deposito_nome=deposito_nome,
        strategy=strategy,
        auto_mode="manual",
        interval_value=15,
        interval_unit="minutos",
        dry_run=False,
    )

