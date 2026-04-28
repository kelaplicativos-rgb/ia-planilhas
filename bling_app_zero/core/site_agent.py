"""
SITE AGENT — ORQUESTRADOR GLOBAL MODULAR

BLINGFIX CRAWLER:
- Mantém fornecedor específico como fallback.
- Adiciona Instant Scraper como prioridade.
- Prioriza detecção de marca no título do produto.
- Se não achar no título, busca na descrição curta/completa.
- Se não detectar marca real nesses campos, deixa marca vazia.
- Corrige o carregamento do crawler genérico.
- Remove import silencioso que escondia erro real.
- Registra diagnóstico detalhado se crawler_engine falhar.
- Mantém compatibilidade com:
  - SiteAgent
  - get_site_agent()
  - buscar_produtos_site()
  - buscar_produtos_site_df()
  - buscar_produtos_site_com_gpt()
  - buscar_dataframe()
  - buscar_produtos()
  - para_dataframe()
"""

from __future__ import annotations

import importlib
import re
import time
import traceback
from html import unescape
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

try:
    import streamlit as st
except Exception:  # pragma: no cover
    st = None

try:
    from bling_app_zero.core.suppliers.registry import SupplierRegistry, get_registry
except Exception:  # pragma: no cover
    SupplierRegistry = Any

    def get_registry():
        return None


RUN_CRAWLER_IMPORT_ERROR = ""


def _carregar_run_crawler() -> Optional[Callable[..., pd.DataFrame]]:
    global RUN_CRAWLER_IMPORT_ERROR

    caminhos = [
        "bling_app_zero.core.site_crawler.crawler_engine",
        "bling_app_zero.core.site_crawler_engine",
        "bling_app_zero.core.site_crawler",
    ]

    erros: List[str] = []

    for caminho in caminhos:
        try:
            modulo = importlib.import_module(caminho)
            funcao = getattr(modulo, "run_crawler", None)

            if callable(funcao):
                RUN_CRAWLER_IMPORT_ERROR = ""
                return funcao

            erros.append(f"{caminho}: atributo run_crawler não encontrado.")
        except Exception as exc:
            erros.append(
                f"{caminho}: {exc.__class__.__name__}: {exc}\n"
                f"{traceback.format_exc(limit=4)}"
            )

    RUN_CRAWLER_IMPORT_ERROR = "\n\n".join(erros)
    return None


run_crawler = _carregar_run_crawler()


class SiteAgent:
    MARCAS_LOJA_BLOQUEADAS = {
        "mega center",
        "mega center eletrônicos",
        "mega center eletronicos",
        "megacenter",
        "megacenter eletrônicos",
        "megacenter eletronicos",
        "loja mega center",
    }

    MARCAS_CONHECIDAS = [
        "Samsung", "Apple", "Motorola", "Xiaomi", "Redmi", "Poco", "Realme",
        "Infinix", "Nokia", "LG", "Sony", "Philips", "Multilaser", "Multi",
        "Positivo", "Lenovo", "Dell", "HP", "Acer", "Asus", "Intelbras",
        "Elgin", "Mondial", "Britânia", "Britania", "Oster", "Cadence",
        "Agratto", "Midea", "Electrolux", "Consul", "Brastemp", "JBL",
        "Amvox", "Tomate", "Knup", "Hrebos", "Sumexr", "Baseus", "Hoco",
        "Inova", "Aiwa", "Pulse", "Aquário", "Aquario", "Elsys", "TCL",
        "AOC", "Philco", "Hayom", "Exbom", "Ugreen", "Geonav", "I2GO",
        "C3Tech", "Leadership", "Goldentec", "Gshield", "Gorila Shield",
        "Kingston", "Sandisk", "Western Digital", "Seagate", "Crucial",
        "Logitech", "Microsoft", "Google", "Amazon", "Epson", "Canon",
        "Brother", "Zebra", "Dymo", "Mercusys", "TP-Link", "Tenda",
        "D-Link", "Huawei", "ZTE", "AMD", "Nvidia", "Radeon", "Geforce",
        "X-Cell", "Pineng", "Kaidi", "Kimaster", "Lelong", "Kross",
        "Roadstar", "First Option",
    ]

    def __init__(self) -> None:
        try:
            self.registry: Optional[SupplierRegistry] = get_registry()
        except Exception as exc:
            self.registry = None
            self._log(f"[SITE_AGENT ERRO] registry indisponível: {exc}")

    def executar(
        self,
        url: str,
        *,
        auth_context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        url = self._normalizar_url(url)
        if not url:
            return []

        df = self.buscar_dataframe(
            base_url=url,
            diagnostico=bool(kwargs.pop("diagnostico", False)),
            auth_context=auth_context,
            **kwargs,
        )

        if not isinstance(df, pd.DataFrame) or df.empty:
            return []

        return df.fillna("").to_dict(orient="records")

    def buscar_produtos(self, base_url: str, **kwargs) -> pd.DataFrame:
        return self.buscar_dataframe(base_url=base_url, **kwargs)

    def buscar_dataframe(
        self,
        *,
        base_url: str,
        diagnostico: bool = False,
        auth_context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> pd.DataFrame:
        url = self._normalizar_url(base_url)
        if not url:
            return self.para_dataframe([])

        fornecedor = self._detectar_fornecedor(url)

        varrer_site_completo = self._bool_compat(
            kwargs.get(
                "varrer_site_completo",
                kwargs.get("varredura_completa", kwargs.get("site_completo")),
            ),
            default=True,
        )

        sitemap_completo = self._bool_compat(
            kwargs.get("sitemap_completo", kwargs.get("varrer_sitemap_completo")),
            default=varrer_site_completo,
        )

        max_workers = self._int_compat(kwargs.get("max_workers"), 12)
        limite = kwargs.get("limite", kwargs.get("limite_links", None))
        limite_paginas = kwargs.get("limite_paginas", None)

        self._log(
            "[SITE_AGENT] iniciado "
            f"| url={url} "
            f"| fornecedor={self._nome_fornecedor(fornecedor)} "
            f"| varrer_site_completo={varrer_site_completo} "
            f"| sitemap_completo={sitemap_completo} "
            f"| max_workers={max_workers}"
        )

        df = pd.DataFrame()

        df = self._executar_instant_scraper(
            url=url,
            kwargs=kwargs,
            limite=limite,
            limite_paginas=limite_paginas,
        )

        if not isinstance(df, pd.DataFrame) or df.empty:
            df = self._executar_fornecedor_especifico(
                fornecedor=fornecedor,
                url=url,
                auth_context=auth_context,
                kwargs=kwargs,
                limite=limite,
                limite_paginas=limite_paginas,
                max_workers=max_workers,
            )

        if not isinstance(df, pd.DataFrame) or df.empty:
            self._log("[SITE_AGENT] fornecedor específico vazio/indisponível; usando crawler genérico.")
            df = self._executar_crawler_generico(
                url=url,
                auth_context=auth_context,
                varrer_site_completo=varrer_site_completo,
                sitemap_completo=sitemap_completo,
                max_workers=max_workers,
                limite=limite,
                limite_paginas=limite_paginas,
                kwargs=kwargs,
            )

        df = self._normalizar_dataframe_saida(df)

        if diagnostico:
            produtos = df.fillna("").to_dict(orient="records") if not df.empty else []
            diag = self._diagnostico_basico(
                url=url,
                fornecedor=fornecedor,
                produtos=produtos,
                auth_context=auth_context,
            )
            self._aplicar_diagnostico_streamlit(diag)

        self._log(f"[SITE_AGENT] total final no DataFrame: {len(df)} produto(s)")
        return df

    def _executar_instant_scraper(
        self,
        *,
        url: str,
        kwargs: Dict[str, Any],
        limite: Any = None,
        limite_paginas: Any = None,
    ) -> pd.DataFrame:
        usar_instant = self._bool_compat(kwargs.get("usar_instant_scraper", True), default=True)

        if not usar_instant:
            self._log("[SITE_AGENT] InstantScraper desativado por parâmetro.")
            return pd.DataFrame()

        try:
            from bling_app_zero.core.instant_scraper.runner import run_scraper

            max_pages = self._int_compat(
                kwargs.get("instant_max_pages", limite_paginas or kwargs.get("max_pages", 5)),
                5,
            )

            if limite is not None:
                try:
                    limite_int = int(limite)
                    if limite_int > 0:
                        max_pages = min(max_pages, max(1, limite_int))
                except Exception:
                    pass

            self._log(f"[SITE_AGENT] tentando InstantScraper | max_pages={max_pages}")

            df = run_scraper(url, max_pages=max_pages)

            if isinstance(df, pd.DataFrame) and not df.empty:
                self._log(f"[SITE_AGENT] InstantScraper retornou {len(df)} produto(s).")
                return df

            self._log("[SITE_AGENT] InstantScraper não encontrou produto útil.")
            return pd.DataFrame()

        except Exception as exc:
            self._log(f"[SITE_AGENT ERRO] InstantScraper falhou: {exc}")
            return pd.DataFrame()

    def _executar_fornecedor_especifico(
        self,
        *,
        fornecedor: Any,
        url: str,
        auth_context: Optional[Dict[str, Any]],
        kwargs: Dict[str, Any],
        limite: Any,
        limite_paginas: Any,
        max_workers: int,
    ) -> pd.DataFrame:
        if fornecedor is None:
            return pd.DataFrame()

        nome = self._nome_fornecedor(fornecedor)
        nome_l = nome.lower()

        if "gen" in nome_l and "mega" not in nome_l:
            self._log(f"[SITE_AGENT] fornecedor genérico detectado; pulando prioridade específica: {nome}")
            return pd.DataFrame()

        self._log(f"[SITE_AGENT] usando fornecedor específico: {nome}")

        kwargs_supplier = dict(kwargs)
        kwargs_supplier.setdefault("auth_context", auth_context)
        kwargs_supplier.setdefault("limite", limite)
        kwargs_supplier.setdefault("limite_links", limite)
        kwargs_supplier.setdefault("limite_paginas", limite_paginas)
        kwargs_supplier.setdefault("max_workers", max_workers)

        try:
            if hasattr(fornecedor, "fetch"):
                produtos = fornecedor.fetch(url, **kwargs_supplier)

                if hasattr(fornecedor, "validar_produtos"):
                    try:
                        produtos = fornecedor.validar_produtos(produtos)
                    except Exception as exc:
                        self._log(f"[SITE_AGENT] validar_produtos fornecedor falhou: {exc}")

                if hasattr(fornecedor, "to_dataframe"):
                    df = fornecedor.to_dataframe(produtos)
                else:
                    df = pd.DataFrame(produtos or [])

                if isinstance(df, pd.DataFrame) and not df.empty:
                    self._log(f"[SITE_AGENT] fornecedor específico retornou {len(df)} produto(s).")
                    return df

        except Exception as exc:
            self._log(f"[SITE_AGENT] fornecedor específico falhou: {nome} → {exc}")

        return pd.DataFrame()

    def _obter_run_crawler_runtime(self) -> Optional[Callable[..., pd.DataFrame]]:
        global run_crawler

        if callable(run_crawler):
            return run_crawler

        self._log("[SITE_AGENT] tentando recarregar crawler genérico em runtime.")
        run_crawler = _carregar_run_crawler()

        if callable(run_crawler):
            self._log("[SITE_AGENT] crawler genérico recarregado com sucesso.")
            return run_crawler

        return None

    def _executar_crawler_generico(
        self,
        *,
        url: str,
        auth_context: Optional[Dict[str, Any]],
        varrer_site_completo: bool,
        sitemap_completo: bool,
        max_workers: int,
        limite: Any,
        limite_paginas: Any,
        kwargs: Dict[str, Any],
    ) -> pd.DataFrame:
        crawler = self._obter_run_crawler_runtime()

        if crawler is None:
            self._log("[SITE_AGENT ERRO] run_crawler indisponível.")
            if RUN_CRAWLER_IMPORT_ERROR:
                self._log(f"[SITE_AGENT ERRO DETALHE] {RUN_CRAWLER_IMPORT_ERROR}")
            return pd.DataFrame()

        parametros = {
            "auth_context": auth_context,
            "varrer_site_completo": varrer_site_completo,
            "sitemap_completo": sitemap_completo,
            "max_workers": max_workers,
            "limite": limite,
            "limite_paginas": limite_paginas,
            "usar_sitemap": bool(kwargs.get("usar_sitemap", True)),
            "usar_home": bool(kwargs.get("usar_home", True)),
            "usar_categoria": bool(kwargs.get("usar_categoria", True)),
            "modo": kwargs.get("modo", "completo" if varrer_site_completo else "padrao"),
            "preferir_playwright": bool(kwargs.get("preferir_playwright", False)),
        }

        try:
            df = crawler(url, **parametros)
            if isinstance(df, pd.DataFrame):
                return df
            if isinstance(df, list):
                return pd.DataFrame(df)
            if isinstance(df, dict):
                for chave in ["df", "dataframe", "produtos", "items", "dados"]:
                    valor = df.get(chave)
                    if isinstance(valor, pd.DataFrame):
                        return valor
                    if isinstance(valor, list):
                        return pd.DataFrame(valor)
            return pd.DataFrame()
        except TypeError as exc:
            self._log(f"[SITE_AGENT] assinatura completa do crawler falhou; tentando modo compatível: {exc}")

            try:
                df = crawler(
                    url,
                    auth_context=auth_context,
                    varrer_site_completo=varrer_site_completo,
                    sitemap_completo=sitemap_completo,
                    max_workers=max_workers,
                )
                if isinstance(df, pd.DataFrame):
                    return df
                if isinstance(df, list):
                    return pd.DataFrame(df)
                return pd.DataFrame()
            except Exception as exc2:
                self._log(f"[SITE_AGENT ERRO] crawler_engine falhou no fallback: {exc2}")
                return pd.DataFrame()
        except Exception as exc:
            self._log(f"[SITE_AGENT ERRO] crawler_engine falhou: {exc}")
            return pd.DataFrame()

    def _nome_fornecedor(self, fornecedor: Any) -> str:
        try:
            return str(getattr(fornecedor, "nome", "") or fornecedor.__class__.__name__).strip()
        except Exception:
            return ""

    def _detectar_fornecedor(self, url: str):
        try:
            if self.registry is not None and hasattr(self.registry, "detectar"):
                return self.registry.detectar(url)
        except Exception as exc:
            self._log(f"[SITE_AGENT ERRO] falha ao detectar fornecedor: {exc}")
            return None
        return None

    def para_dataframe(self, produtos: List[Dict[str, Any]]) -> pd.DataFrame:
        if not isinstance(produtos, list):
            produtos = []
        df = pd.DataFrame(produtos)
        return self._normalizar_dataframe_saida(df)

    def _normalizar_dataframe_saida(self, df: Any) -> pd.DataFrame:
        colunas = [
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

        if not isinstance(df, pd.DataFrame):
            df = pd.DataFrame()

        df = df.copy().fillna("")

        aliases = {
            "URL": "url_produto",
            "Url": "url_produto",
            "url": "url_produto",
            "link": "url_produto",
            "Link": "url_produto",
            "Nome": "nome",
            "Produto": "nome",
            "produto": "nome",
            "Descrição": "descricao",
            "Descricao": "descricao",
            "description": "descricao",
            "descricao_curta": "descricao",
            "descrição curta": "descricao",
            "Descrição Curta": "descricao",
            "descricao_completa": "descricao",
            "descrição completa": "descricao",
            "Descrição Completa": "descricao",
            "Preço": "preco",
            "Preco": "preco",
            "price": "preco",
            "SKU": "sku",
            "Sku": "sku",
            "Código": "sku",
            "Codigo": "sku",
            "Marca": "marca",
            "brand": "marca",
            "Categoria": "categoria",
            "category": "categoria",
            "Estoque": "estoque",
            "stock": "estoque",
            "quantidade": "estoque",
            "quantidade_real": "estoque",
            "GTIN": "gtin",
            "EAN": "gtin",
            "ean": "gtin",
            "Imagem": "imagens",
            "Imagens": "imagens",
            "image": "imagens",
            "images": "imagens",
        }

        for origem, destino in aliases.items():
            if origem in df.columns and destino not in df.columns:
                df[destino] = df[origem]

        for col in colunas:
            if col not in df.columns:
                df[col] = ""

        df["url_produto"] = df["url_produto"].apply(self._texto_limpo)
        df["nome"] = df["nome"].apply(self._limpar_nome_produto)
        df["sku"] = df["sku"].apply(self._texto_limpo)
        df["descricao"] = df["descricao"].apply(self._texto_limpo)
        df["categoria"] = df["categoria"].apply(self._texto_limpo)
        df["estoque"] = df["estoque"].apply(self._normalizar_estoque)
        df["preco"] = df["preco"].apply(self._normalizar_preco)
        df["gtin"] = df["gtin"].apply(self._normalizar_gtin)
        df["imagens"] = df["imagens"].apply(self._normalizar_imagens)

        df["marca"] = df.apply(
            lambda row: self._normalizar_marca(
                row.get("marca", ""),
                nome=row.get("nome", ""),
                descricao=row.get("descricao", ""),
            ),
            axis=1,
        )

        df = df[
            (df["nome"].astype(str).str.strip() != "")
            | (df["url_produto"].astype(str).str.strip() != "")
        ]

        df = self._deduplicar_dataframe(df)

        return df[colunas].reset_index(drop=True)

    def _deduplicar_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        if not isinstance(df, pd.DataFrame) or df.empty:
            return pd.DataFrame(columns=list(df.columns) if isinstance(df, pd.DataFrame) else [])

        base = df.copy()
        chaves = []

        for _, row in base.iterrows():
            chave = (
                self._texto_limpo(row.get("url_produto"))
                or self._texto_limpo(row.get("sku"))
                or self._texto_limpo(row.get("gtin"))
                or self._texto_limpo(row.get("nome"))
            ).lower()
            chaves.append(chave)

        base["_chave_dedupe"] = chaves
        base = base[base["_chave_dedupe"] != ""]
        base = base.drop_duplicates(subset=["_chave_dedupe"], keep="first")
        base = base.drop(columns=["_chave_dedupe"], errors="ignore")
        return base

    def _diagnostico_basico(
        self,
        *,
        url: str,
        fornecedor: Any,
        produtos: List[Dict[str, Any]],
        auth_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        nome_fornecedor = self._nome_fornecedor(fornecedor)

        fonte = "instant_scraper_ou_crawler_modular"
        nome_fornecedor_l = nome_fornecedor.lower()

        if nome_fornecedor_l.startswith("fornecedor gen") or "gen" in nome_fornecedor_l:
            fonte = "generic_supplier"
        elif "mega center" in nome_fornecedor_l:
            fonte = "fornecedor_especifico_mega_center"
        elif "atacadum" in nome_fornecedor_l:
            fonte = "fornecedor_especifico_atacadum"

        df_diag = pd.DataFrame(produtos).copy() if produtos else pd.DataFrame()

        if not df_diag.empty:
            df_diag["score"] = df_diag.apply(lambda row: self._score_produto(row.to_dict()), axis=1)
            df_diag["valido"] = df_diag["score"] >= 3

        total_descobertos = int(len(produtos))
        total_validos = int(sum(1 for p in produtos if self._score_produto(p) >= 3))
        total_rejeitados = int(sum(1 for p in produtos if self._score_produto(p) < 3))

        return {
            "url": url,
            "fornecedor": nome_fornecedor or "Fornecedor Genérico",
            "fonte_descoberta": fonte,
            "diagnostico_df": df_diag,
            "total_descobertos": total_descobertos,
            "total_validos": total_validos,
            "total_rejeitados": total_rejeitados,
            "login_status": {
                "status": "session_ready" if bool((auth_context or {}).get("session_ready")) else "publico",
                "mensagem": (
                    "Sessão autenticada aplicada à busca."
                    if bool((auth_context or {}).get("session_ready"))
                    else "Busca pública."
                ),
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

    def _score_produto(self, produto: Dict[str, Any]) -> int:
        if not isinstance(produto, dict):
            return 0

        score = 0
        nome = self._texto_limpo(produto.get("nome") or produto.get("Nome") or produto.get("Produto"))
        preco = produto.get("preco") or produto.get("Preço") or produto.get("Preco")
        url_produto = self._texto_limpo(produto.get("url_produto") or produto.get("URL") or produto.get("url"))
        sku = self._texto_limpo(produto.get("sku") or produto.get("SKU") or produto.get("Código"))
        gtin = self._texto_limpo(produto.get("gtin") or produto.get("GTIN") or produto.get("EAN"))
        descricao = self._texto_limpo(produto.get("descricao") or produto.get("Descrição"))
        imagens = produto.get("imagens") or produto.get("Imagem") or produto.get("Imagens")
        categoria = self._texto_limpo(produto.get("categoria") or produto.get("Categoria"))
        estoque = produto.get("estoque") or produto.get("Estoque")

        if nome and len(nome) >= 4:
            score += 2
        if url_produto:
            score += 1
        if sku:
            score += 1
        if gtin:
            score += 1
        if descricao and len(descricao) >= 20:
            score += 1
        if categoria:
            score += 1
        if imagens:
            score += 1
        if self._normalizar_preco(preco) > 0:
            score += 2
        if self._normalizar_estoque(estoque) >= 0:
            score += 1

        return score

    def _normalizar_estoque(self, valor: Any) -> int:
        if valor is None:
            return 0

        if isinstance(valor, bool):
            return int(valor)

        if isinstance(valor, (int, float)):
            return max(int(valor), 0)

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

    def _normalizar_gtin(self, valor: Any) -> str:
        numeros = re.sub(r"\D", "", self._texto_limpo(valor))
        if len(numeros) in (8, 12, 13, 14):
            return numeros
        return ""

    def _normalizar_imagens(self, imagens: Any) -> str:
        if not imagens:
            return ""

        if isinstance(imagens, list):
            itens = imagens
        else:
            bruto = str(imagens).replace(";", "|").replace(",", "|")
            itens = bruto.split("|")

        lista_final: List[str] = []
        vistos = set()

        for item in itens:
            valor = self._texto_limpo(item)
            if not valor:
                continue
            if valor in vistos:
                continue
            vistos.add(valor)
            lista_final.append(valor)

        return "|".join(lista_final[:12])

    def _texto_limpo(self, valor: Any) -> str:
        texto = str(valor or "").strip()
        if texto.lower() in {"nan", "none", "null"}:
            return ""

        texto = unescape(texto)
        texto = texto.replace("\ufeff", "").replace("\x00", "")
        texto = re.sub(r"[\r\n\t]+", " ", texto)
        texto = re.sub(r"\s+", " ", texto).strip()
        return texto

    def _normalizar_url(self, url: Any) -> str:
        texto = self._texto_limpo(url)
        if not texto:
            return ""

        if texto.startswith("//"):
            texto = f"https:{texto}"

        if not texto.startswith(("http://", "https://")):
            texto = f"https://{texto}"

        return texto

    def _limpar_nome_produto(self, valor: Any) -> str:
        texto = self._texto_limpo(valor)
        texto = re.sub(r"\s*[-|]\s*Mega Center.*$", "", texto, flags=re.I)
        texto = re.sub(r"\s*[-|]\s*Comprar.*$", "", texto, flags=re.I)
        return texto.strip()

    def _normalizar_marca(self, marca: Any, *, nome: str = "", descricao: str = "") -> str:
        marca_txt = self._texto_limpo(marca)
        marca_txt = re.sub(r"\s+", " ", marca_txt).strip(" -|:/")

        if self._marca_invalida(marca_txt):
            marca_txt = ""

        if not marca_txt:
            marca_txt = self._inferir_marca(nome=nome, descricao=descricao)

        if self._marca_invalida(marca_txt):
            return ""

        return marca_txt[:80]

    def _marca_invalida(self, marca: str) -> bool:
        marca_l = self._sem_acentos(self._texto_limpo(marca)).lower()
        if not marca_l:
            return True

        bloqueadas = {self._sem_acentos(x).lower() for x in self.MARCAS_LOJA_BLOQUEADAS}
        if marca_l in bloqueadas:
            return True

        if "mega center" in marca_l or "megacenter" in marca_l:
            return True

        if len(marca_l) > 80:
            return True

        return False

    def _inferir_marca(self, *, nome: str = "", descricao: str = "") -> str:
        nome_limpo = self._texto_limpo(nome)
        descricao_limpa = self._texto_limpo(descricao)

        nome_norm = self._sem_acentos(nome_limpo).lower()
        descricao_norm = self._sem_acentos(descricao_limpa).lower()

        for marca in self.MARCAS_CONHECIDAS:
            marca_norm = self._sem_acentos(marca).lower()
            if re.search(rf"(?<![a-z0-9]){re.escape(marca_norm)}(?![a-z0-9])", nome_norm):
                return marca

        for marca in self.MARCAS_CONHECIDAS:
            marca_norm = self._sem_acentos(marca).lower()
            if re.search(rf"(?<![a-z0-9]){re.escape(marca_norm)}(?![a-z0-9])", descricao_norm):
                return marca

        return ""

    def _sem_acentos(self, texto: str) -> str:
        mapa = str.maketrans(
            "áàâãäéèêëíìîïóòôõöúùûüçÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ",
            "aaaaaeeeeiiiiooooouuuucAAAAAEEEEIIIIOOOOOUUUUC",
        )
        return (texto or "").translate(mapa)

    def _bool_compat(self, valor: Any, default: bool = False) -> bool:
        if valor is None:
            return default

        if isinstance(valor, bool):
            return valor

        texto = self._texto_limpo(valor).lower()
        if not texto:
            return default

        if texto in {"1", "true", "sim", "yes", "on", "s"}:
            return True

        if texto in {"0", "false", "nao", "não", "no", "off", "n"}:
            return False

        return default

    def _int_compat(self, valor: Any, default: int) -> int:
        try:
            if valor is None or valor == "":
                return int(default)
            return int(valor)
        except Exception:
            return int(default)

    def _log(self, mensagem: str) -> None:
        try:
            print(mensagem)
        except Exception:
            pass

        if st is not None:
            try:
                if "logs" not in st.session_state:
                    st.session_state["logs"] = []
                st.session_state["logs"].append(f"{time.strftime('%H:%M:%S')} {mensagem}")
            except Exception:
                pass


_site_agent_instance: Optional[SiteAgent] = None


def get_site_agent() -> SiteAgent:
    global _site_agent_instance
    if _site_agent_instance is None:
        _site_agent_instance = SiteAgent()
    return _site_agent_instance


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

