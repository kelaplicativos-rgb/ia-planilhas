"""
SITE AGENT (ORQUESTRADOR GLOBAL)

Responsável por:
- Escolher o fornecedor correto
- Aplicar fallback inteligente
- Garantir captura de ESTOQUE (prioridade máxima)
- Expor função pública compatível com a UI: buscar_produtos_site_com_gpt()
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import pandas as pd

try:
    import streamlit as st
except Exception:  # pragma: no cover
    st = None

from bling_app_zero.core.suppliers.registry import SupplierRegistry, get_registry


class SiteAgent:
    def __init__(self) -> None:
        self.registry: SupplierRegistry = get_registry()

    # -------------------------------
    # EXECUÇÃO PRINCIPAL
    # -------------------------------
    def executar(self, url: str, **kwargs) -> List[Dict[str, Any]]:
        url = self._normalizar_url(url)
        if not url:
            return []

        fornecedor = self._detectar_fornecedor(url)
        produtos: List[Dict[str, Any]] = []

        kwargs_limpos = self._filtrar_kwargs_fornecedor(kwargs)

        # ===============================
        # 1. EXECUTAR FORNECEDOR DETECTADO
        # ===============================
        if fornecedor is not None:
            try:
                produtos = fornecedor.fetch(url, **kwargs_limpos)
                produtos = self._validar_com_fornecedor(fornecedor, produtos)
            except Exception as exc:
                self._log(f"[ERRO fornecedor específico] {exc}")

        # ===============================
        # 2. FALLBACK GENÉRICO
        # ===============================
        if not produtos:
            fornecedor_generico = self._obter_fornecedor_generico()

            if fornecedor_generico is not None and fornecedor_generico is not fornecedor:
                self._log("[FALLBACK] usando GenericSupplier")
                try:
                    produtos = fornecedor_generico.fetch(url, **kwargs_limpos)
                    produtos = self._validar_com_fornecedor(fornecedor_generico, produtos)
                except Exception as exc:
                    self._log(f"[ERRO fallback] {exc}")

        # ===============================
        # 3. PÓS-PROCESSAMENTO (CRÍTICO)
        # ===============================
        produtos = self._padronizar(produtos)

        return produtos

    # -------------------------------
    # DETECTAR FORNECEDOR
    # -------------------------------
    def _detectar_fornecedor(self, url: str):
        try:
            return self.registry.detectar(url)
        except Exception:
            return None

    def _obter_fornecedor_generico(self):
        for supplier in getattr(self.registry, "suppliers", []):
            try:
                nome = str(getattr(supplier, "nome", "") or "").strip().lower()
                classe = supplier.__class__.__name__.strip().lower()
                if "genérico" in nome or "generico" in nome or "generic" in classe:
                    return supplier
            except Exception:
                continue
        return None

    def _validar_com_fornecedor(self, fornecedor: Any, produtos: Any) -> List[Dict[str, Any]]:
        if not isinstance(produtos, list):
            return []

        try:
            if hasattr(fornecedor, "validar_produtos"):
                produtos = fornecedor.validar_produtos(produtos)
        except Exception:
            pass

        return produtos if isinstance(produtos, list) else []

    # -------------------------------
    # PADRONIZAÇÃO FINAL
    # -------------------------------
    def _padronizar(self, produtos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        resultado: List[Dict[str, Any]] = []

        for p in produtos:
            if not isinstance(p, dict):
                continue

            nome = self._texto_limpo(p.get("nome"))
            url_produto = self._texto_limpo(p.get("url_produto"))
            sku = self._texto_limpo(p.get("sku"))
            marca = self._texto_limpo(p.get("marca"))
            categoria = self._texto_limpo(p.get("categoria"))
            gtin = self._texto_limpo(p.get("gtin"))
            descricao = self._texto_limpo(p.get("descricao"))

            estoque = self._normalizar_estoque(p.get("estoque"))
            preco = self._normalizar_preco(p.get("preco"))
            imagens = self._normalizar_imagens(p.get("imagens"))

            if not nome and not url_produto:
                continue

            resultado.append(
                {
                    "url_produto": url_produto,
                    "nome": nome,
                    "sku": sku,
                    "marca": marca,
                    "categoria": categoria,
                    "estoque": estoque,
                    "preco": preco,
                    "gtin": gtin,
                    "descricao": descricao,
                    "imagens": imagens,
                }
            )

        return self._deduplicar(resultado)

    # -------------------------------
    # NORMALIZA ESTOQUE (REGRA GLOBAL)
    # -------------------------------
    def _normalizar_estoque(self, valor: Any) -> int:
        if valor is None:
            return 0

        if isinstance(valor, bool):
            return int(valor)

        if isinstance(valor, (int, float)):
            valor_int = int(valor)
            return max(valor_int, 0)

        texto = self._texto_limpo(valor).lower()
        if not texto:
            return 0

        if any(
            termo in texto
            for termo in [
                "esgotado",
                "sem estoque",
                "indisponível",
                "indisponivel",
                "zerado",
                "out of stock",
            ]
        ):
            return 0

        match = re.search(r"(\d+)", texto)
        if match:
            try:
                return max(int(match.group(1)), 0)
            except Exception:
                return 0

        if any(
            termo in texto
            for termo in [
                "disponível",
                "disponivel",
                "em estoque",
                "available",
                "in stock",
            ]
        ):
            return 1

        return 0

    # -------------------------------
    # NORMALIZA PREÇO
    # -------------------------------
    def _normalizar_preco(self, valor: Any) -> float:
        if valor is None:
            return 0.0

        if isinstance(valor, (int, float)):
            return float(valor)

        texto = self._texto_limpo(valor)
        if not texto:
            return 0.0

        texto = texto.replace("R$", "").replace("r$", "").strip()
        texto = re.sub(r"[^\d,.\-]", "", texto)

        if texto.count(",") > 0 and texto.count(".") > 0:
            texto = texto.replace(".", "").replace(",", ".")
        elif texto.count(",") > 0:
            texto = texto.replace(",", ".")

        try:
            return float(texto)
        except Exception:
            return 0.0

    # -------------------------------
    # NORMALIZA IMAGENS
    # -------------------------------
    def _normalizar_imagens(self, imagens: Any) -> str:
        if not imagens:
            return ""

        lista_final: List[str] = []

        if isinstance(imagens, list):
            itens = imagens
        else:
            bruto = str(imagens).replace(";", "|").replace(",", "|")
            itens = bruto.split("|")

        vistos = set()
        for item in itens:
            valor = self._texto_limpo(item)
            if not valor:
                continue
            if valor in vistos:
                continue
            vistos.add(valor)
            lista_final.append(valor)

        return "|".join(lista_final)

    # -------------------------------
    # HELPERS
    # -------------------------------
    def _texto_limpo(self, valor: Any) -> str:
        texto = str(valor or "").strip()
        if texto.lower() in {"nan", "none", "null"}:
            return ""
        return texto

    def _normalizar_url(self, url: str) -> str:
        texto = self._texto_limpo(url)
        if not texto:
            return ""
        if not texto.startswith(("http://", "https://")):
            texto = f"https://{texto}"
        return texto

    def _filtrar_kwargs_fornecedor(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        removidos = {
            "base_url",
            "diagnostico",
            "auth_context",
            "termo",
            "limite_links",
        }
        return {k: v for k, v in kwargs.items() if k not in removidos}

    def _deduplicar(self, produtos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        vistos = set()
        resultado: List[Dict[str, Any]] = []

        for p in produtos:
            chave = (
                self._texto_limpo(p.get("url_produto"))
                or self._texto_limpo(p.get("sku"))
                or self._texto_limpo(p.get("nome"))
            )
            if not chave:
                continue
            if chave in vistos:
                continue
            vistos.add(chave)
            resultado.append(p)

        return resultado

    def _log(self, mensagem: str) -> None:
        try:
            print(mensagem)
        except Exception:
            pass

    # -------------------------------
    # DATAFRAME
    # -------------------------------
    def para_dataframe(self, produtos: List[Dict[str, Any]]) -> pd.DataFrame:
        produtos = self._padronizar(produtos)
        if not produtos:
            return pd.DataFrame(
                columns=[
                    "url_produto",
                    "nome",
                    "sku",
                    "marca",
                    "categoria",
                    "estoque",
                    "preco",
                    "gtin",
                    "descricao",
                    "imagens",
                ]
            )

        df = pd.DataFrame(produtos).fillna("")
        for col in ["estoque"]:
            if col in df.columns:
                df[col] = df[col].apply(self._normalizar_estoque)
        for col in ["preco"]:
            if col in df.columns:
                df[col] = df[col].apply(self._normalizar_preco)
        for col in ["imagens"]:
            if col in df.columns:
                df[col] = df[col].apply(self._normalizar_imagens)

        return df

    # -------------------------------
    # DIAGNÓSTICO / STREAMLIT
    # -------------------------------
    def _diagnostico_basico(
        self,
        *,
        url: str,
        fornecedor: Any,
        produtos: List[Dict[str, Any]],
        auth_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        nome_fornecedor = ""
        try:
            nome_fornecedor = str(getattr(fornecedor, "nome", "") or "").strip()
        except Exception:
            nome_fornecedor = ""

        fonte = "crawler_links"
        if nome_fornecedor.lower().startswith("fornecedor gen"):
            fonte = "sitemap"
        elif "mega center" in nome_fornecedor.lower():
            fonte = "crawler_links"
        elif "atacadum" in nome_fornecedor.lower():
            fonte = "sitemap"

        df_diag = pd.DataFrame(produtos).copy() if produtos else pd.DataFrame()
        if not df_diag.empty:
            df_diag["valido"] = True

        return {
            "url": url,
            "fornecedor": nome_fornecedor or "Fornecedor Genérico",
            "fonte_descoberta": fonte,
            "diagnostico_df": df_diag,
            "total_descobertos": int(len(produtos)),
            "total_validos": int(len(produtos)),
            "total_rejeitados": 0,
            "login_status": {
                "status": "session_ready" if bool((auth_context or {}).get("session_ready")) else "publico",
                "mensagem": "Sessão autenticada disponível."
                if bool((auth_context or {}).get("session_ready"))
                else "Busca pública.",
            },
        }

    def _aplicar_diagnostico_streamlit(self, diagnostico: Dict[str, Any]) -> None:
        if st is None:
            return
        try:
            st.session_state["site_busca_diagnostico_df"] = diagnostico.get("diagnostico_df", pd.DataFrame())
            st.session_state["site_busca_diagnostico_total_descobertos"] = int(
                diagnostico.get("total_descobertos", 0) or 0
            )
            st.session_state["site_busca_diagnostico_total_validos"] = int(
                diagnostico.get("total_validos", 0) or 0
            )
            st.session_state["site_busca_diagnostico_total_rejeitados"] = int(
                diagnostico.get("total_rejeitados", 0) or 0
            )
            st.session_state["site_busca_login_status"] = diagnostico.get("login_status", {}) or {}
            st.session_state["site_busca_fonte_descoberta"] = str(
                diagnostico.get("fonte_descoberta", "") or ""
            ).strip()
        except Exception:
            pass

    # -------------------------------
    # BUSCA PÚBLICA COMPATÍVEL COM A UI
    # -------------------------------
    def buscar_dataframe(
        self,
        *,
        base_url: str,
        diagnostico: bool = False,
        auth_context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> pd.DataFrame:
        url = self._normalizar_url(base_url)
        fornecedor = self._detectar_fornecedor(url)

        produtos = self.executar(url, **kwargs)
        df = self.para_dataframe(produtos)

        if diagnostico:
            diag = self._diagnostico_basico(
                url=url,
                fornecedor=fornecedor,
                produtos=produtos,
                auth_context=auth_context,
            )
            self._aplicar_diagnostico_streamlit(diag)

        return df


# -------------------------------
# INSTÂNCIA GLOBAL
# -------------------------------
_site_agent_instance: Optional[SiteAgent] = None


def get_site_agent() -> SiteAgent:
    global _site_agent_instance
    if _site_agent_instance is None:
        _site_agent_instance = SiteAgent()
    return _site_agent_instance


# -------------------------------
# FUNÇÕES PÚBLICAS USADAS PELA UI
# -------------------------------
def buscar_produtos_site(url: str, **kwargs) -> List[Dict[str, Any]]:
    agent = get_site_agent()
    return agent.executar(url, **kwargs)


def buscar_produtos_site_df(url: str, **kwargs) -> pd.DataFrame:
    agent = get_site_agent()
    return agent.buscar_dataframe(base_url=url, **kwargs)


def buscar_produtos_site_com_gpt(
    *,
    base_url: str,
    termo: str = "",
    limite_links: Optional[int] = None,
    diagnostico: bool = False,
    auth_context: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> pd.DataFrame:
    """
    Função pública compatível com a UI atual em origem_dados.py.

    Parâmetros extras como termo/auth_context/limite_links são aceitos
    para compatibilidade com o fluxo atual, mesmo quando não forem usados
    diretamente pelo fornecedor específico.
    """
    agent = get_site_agent()

    kwargs_execucao = dict(kwargs)
    if limite_links is not None and "limite" not in kwargs_execucao:
        kwargs_execucao["limite"] = limite_links

    return agent.buscar_dataframe(
        base_url=base_url,
        diagnostico=diagnostico,
        auth_context=auth_context,
        **kwargs_execucao,
    )
