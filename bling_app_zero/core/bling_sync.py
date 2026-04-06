from __future__ import annotations

import time
from typing import Any, Dict, List, Tuple

from bling_app_zero.core.bling_api import BlingAPIClient


MAX_RETRY = 3
RETRY_DELAY_SECONDS = 1.2


def _mensagem_padronizada(payload: Any) -> str:
    if payload is None:
        return "Sem retorno da API."

    if isinstance(payload, str):
        texto = payload.strip()
        return texto or "Retorno vazio da API."

    if isinstance(payload, dict):
        for chave in [
            "message",
            "mensagem",
            "erro",
            "error",
            "detail",
            "descricao",
            "description",
        ]:
            valor = payload.get(chave)
            if valor not in (None, ""):
                return str(valor).strip()

        return str(payload)

    if isinstance(payload, list):
        if not payload:
            return "Lista de retorno vazia."
        return str(payload[0])

    return str(payload)


class BlingSyncService:
    def __init__(self, *, user_key: str = "default") -> None:
        self.user_key = user_key
        self.client = BlingAPIClient(user_key=user_key)

    def sync_products(
        self,
        rows: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        sucessos: List[Dict[str, Any]] = []
        erros: List[Dict[str, Any]] = []

        for indice, row in enumerate(rows, start=1):
            inicio_item = time.perf_counter()
            ultima_resposta: Any = None
            tentativa_final = 0
            ok_final = False

            for tentativa in range(1, MAX_RETRY + 1):
                tentativa_final = tentativa
                try:
                    ok, payload = self.client.upsert_product(row)
                    ultima_resposta = payload

                    if ok:
                        duracao = round(time.perf_counter() - inicio_item, 4)
                        item = {
                            "linha": indice,
                            "codigo": row.get("codigo"),
                            "nome": row.get("nome"),
                            "tentativas": tentativa,
                            "tempo_segundos": duracao,
                            "mensagem": _mensagem_padronizada(payload),
                            "retorno": payload,
                        }
                        sucessos.append(item)
                        ok_final = True
                        break

                except Exception as e:
                    ultima_resposta = {"error": str(e)}

                if tentativa < MAX_RETRY:
                    time.sleep(RETRY_DELAY_SECONDS)

            if not ok_final:
                duracao = round(time.perf_counter() - inicio_item, 4)
                item = {
                    "linha": indice,
                    "codigo": row.get("codigo"),
                    "nome": row.get("nome"),
                    "tentativas": tentativa_final,
                    "tempo_segundos": duracao,
                    "mensagem": _mensagem_padronizada(ultima_resposta),
                    "erro": ultima_resposta,
                }
                erros.append(item)

        return sucessos, erros

    def sync_stocks(
        self,
        rows: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        sucessos: List[Dict[str, Any]] = []
        erros: List[Dict[str, Any]] = []

        for indice, row in enumerate(rows, start=1):
            codigo = str(row.get("codigo") or "").strip()
            estoque = row.get("estoque")
            deposito_id = row.get("deposito_id")
            preco = row.get("preco")

            try:
                estoque_float = float(estoque or 0)
            except (TypeError, ValueError):
                estoque_float = 0.0

            try:
                preco_float = float(preco) if preco not in (None, "") else None
            except (TypeError, ValueError):
                preco_float = None

            deposito_final = (
                str(deposito_id).strip()
                if deposito_id not in (None, "")
                else None
            )

            inicio_item = time.perf_counter()
            ultima_resposta: Any = None
            tentativa_final = 0
            ok_final = False

            for tentativa in range(1, MAX_RETRY + 1):
                tentativa_final = tentativa
                try:
                    ok, payload = self.client.update_stock(
                        codigo=codigo,
                        estoque=estoque_float,
                        deposito_id=deposito_final,
                        preco=preco_float,
                    )
                    ultima_resposta = payload

                    if ok:
                        duracao = round(time.perf_counter() - inicio_item, 4)
                        item = {
                            "linha": indice,
                            "codigo": codigo,
                            "estoque": estoque_float,
                            "deposito_id": deposito_final,
                            "preco": preco_float,
                            "tentativas": tentativa,
                            "tempo_segundos": duracao,
                            "mensagem": _mensagem_padronizada(payload),
                            "retorno": payload,
                        }
                        sucessos.append(item)
                        ok_final = True
                        break

                except Exception as e:
                    ultima_resposta = {"error": str(e)}

                if tentativa < MAX_RETRY:
                    time.sleep(RETRY_DELAY_SECONDS)

            if not ok_final:
                duracao = round(time.perf_counter() - inicio_item, 4)
                item = {
                    "linha": indice,
                    "codigo": codigo,
                    "estoque": estoque_float,
                    "deposito_id": deposito_final,
                    "preco": preco_float,
                    "tentativas": tentativa_final,
                    "tempo_segundos": duracao,
                    "mensagem": _mensagem_padronizada(ultima_resposta),
                    "erro": ultima_resposta,
                }
                erros.append(item)

        return sucessos, erros


def sync_products(
    rows: List[Dict[str, Any]],
    *,
    user_key: str = "default",
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    service = BlingSyncService(user_key=user_key)
    return service.sync_products(rows)


def sync_stocks(
    rows: List[Dict[str, Any]],
    *,
    user_key: str = "default",
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    service = BlingSyncService(user_key=user_key)
    return service.sync_stocks(rows)
