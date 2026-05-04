from __future__ import annotations

from typing import Any

from bling_app_zero.core.bling_categories import normalizar_categoria_bling


def _safe_str(valor: Any) -> str:
    if valor is None:
        return ""
    texto = str(valor).strip()
    if texto.lower() in {"nan", "none", "null", "nat"}:
        return ""
    return texto


def _extrair_lista_data(resposta: dict[str, Any]) -> list[dict[str, Any]]:
    data = resposta.get("data", []) if isinstance(resposta, dict) else []
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def _nome_categoria_api(item: dict[str, Any]) -> str:
    return _safe_str(item.get("descricao") or item.get("nome") or item.get("name"))


def _id_categoria_api(item: dict[str, Any]) -> Any:
    return item.get("id") or item.get("idCategoria") or item.get("codigo")


class BlingCategoriaService:
    def __init__(self, client: Any) -> None:
        self.client = client
        self._cache_por_nome: dict[str, Any] = {}
        self._carregado = False

    def _request(self, method: str, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        if not self.client or not getattr(self.client, "disponivel", False):
            raise RuntimeError("Cliente Bling indisponível para categorias.")
        return self.client._request(method, endpoint, **kwargs)

    def listar_categorias(self) -> list[dict[str, Any]]:
        categorias: list[dict[str, Any]] = []
        pagina = 1
        while pagina <= 50:
            resposta = self._request("GET", "/categorias/produtos", params={"pagina": pagina, "limite": 100})
            itens = _extrair_lista_data(resposta)
            if not itens:
                break
            categorias.extend(itens)
            if len(itens) < 100:
                break
            pagina += 1
        return categorias

    def carregar_cache(self, force: bool = False) -> None:
        if self._carregado and not force:
            return
        self._cache_por_nome.clear()
        try:
            for item in self.listar_categorias():
                nome = normalizar_categoria_bling(_nome_categoria_api(item))
                categoria_id = _id_categoria_api(item)
                if nome and categoria_id:
                    self._cache_por_nome[nome.casefold()] = categoria_id
        finally:
            self._carregado = True

    def obter_id_por_nome(self, categoria: str) -> Any:
        categoria_norm = normalizar_categoria_bling(categoria)
        if not categoria_norm:
            return None
        self.carregar_cache()
        return self._cache_por_nome.get(categoria_norm.casefold())

    def criar_categoria(self, categoria: str, categoria_pai_id: Any | None = None) -> Any:
        categoria_norm = normalizar_categoria_bling(categoria)
        if not categoria_norm:
            return None
        payload: dict[str, Any] = {"descricao": categoria_norm.split(">>")[-1]}
        if categoria_pai_id:
            payload["categoriaPai"] = {"id": categoria_pai_id}
        resposta = self._request("POST", "/categorias/produtos", json_payload=payload)
        itens = _extrair_lista_data(resposta)
        categoria_id = None
        if itens:
            categoria_id = _id_categoria_api(itens[0])
        if categoria_id is None and isinstance(resposta, dict):
            categoria_id = _id_categoria_api(resposta)
        if categoria_id:
            self._cache_por_nome[categoria_norm.casefold()] = categoria_id
        return categoria_id

    def garantir_categoria_hierarquica(self, categoria: str) -> Any:
        categoria_norm = normalizar_categoria_bling(categoria)
        if not categoria_norm:
            return None
        existente = self.obter_id_por_nome(categoria_norm)
        if existente:
            return existente

        partes = [p.strip() for p in categoria_norm.split(">>") if p.strip()]
        pai_id = None
        caminho = ""
        for parte in partes:
            caminho = parte if not caminho else f"{caminho}>>{parte}"
            encontrado = self.obter_id_por_nome(caminho)
            if encontrado:
                pai_id = encontrado
                continue
            criado = self.criar_categoria(caminho, categoria_pai_id=pai_id)
            if not criado:
                return pai_id
            pai_id = criado
        return pai_id


def garantir_categorias_df(client: Any, df: Any, coluna_categoria: str) -> dict[str, Any]:
    try:
        import pandas as pd
    except Exception:
        pd = None

    if pd is None or not isinstance(df, pd.DataFrame) or df.empty or not coluna_categoria or coluna_categoria not in df.columns:
        return {"ok": True, "criadas": 0, "existentes": 0, "erros": 0, "detalhes": []}

    service = BlingCategoriaService(client)
    detalhes: list[dict[str, Any]] = []
    criadas = 0
    existentes = 0
    erros = 0

    categorias = []
    for valor in df[coluna_categoria].fillna("").tolist():
        cat = normalizar_categoria_bling(valor)
        if cat and cat not in categorias:
            categorias.append(cat)

    for categoria in categorias:
        try:
            antes = service.obter_id_por_nome(categoria)
            categoria_id = antes or service.garantir_categoria_hierarquica(categoria)
            if antes:
                existentes += 1
                status = "existente"
            else:
                criadas += 1 if categoria_id else 0
                status = "criada" if categoria_id else "nao_criada"
            detalhes.append({"categoria": categoria, "id": categoria_id, "status": status, "erro": ""})
        except Exception as exc:
            erros += 1
            detalhes.append({"categoria": categoria, "id": None, "status": "erro", "erro": str(exc)})

    return {"ok": erros == 0, "criadas": criadas, "existentes": existentes, "erros": erros, "detalhes": detalhes}
