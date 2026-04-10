from __future__ import annotations

import time
import hashlib
from typing import Any, Dict, List, Tuple

from bling_app_zero.core.bling_services import BlingServices


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


def _hash_row(row: Dict[str, Any]) -> str:
    try:
        base = str(sorted(row.items()))
        return hashlib.md5(base.encode()).hexdigest()
    except Exception:
        return ""


class BlingSyncService:
    def __init__(self, *, user_key: str = "default") -> None:
        self.user_key = user_key
        self.services = BlingServices(user_key=user_key)

        # 🔥 CONTROLE GLOBAL
        self._processados: set[str] = set()

    # =========================
    # PRODUTOS
    # =========================
    def sync_products(
        self,
        rows: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:

        sucessos: List[Dict[str, Any]] = []
        erros: List[Dict[str, Any]] = []

        for indice, row in enumerate(rows, start=1):
            hash_row = _hash_row(row)

            # 🔥 ANTI DUPLICIDADE GLOBAL
            if hash_row in self._processados:
                continue

            self._processados.add(hash_row)

            inicio_item = time.perf_counter()
            ultima_resposta: Any = None
            tentativa_final = 0
            ok_final = False

            for tentativa in range(1, MAX_RETRY + 1):
                tentativa_final = tentativa

                try:
                    result = self.services.enviar_produtos(
                        [row],
                        delay=0,
                    )

                    if result["sucesso"] > 0:
                        payload = {"ok": True}
                        ultima_resposta = payload

                        duracao = round(time.perf_counter() - inicio_item, 4)

                        item = {
                            "linha": indice,
                            "codigo": row.get("codigo"),
                            "nome": row.get("nome"),
                            "tentativas": tentativa,
                            "tempo_segundos": duracao,
                            "mensagem": "Enviado com sucesso",
                            "retorno": payload,
                        }

                        sucessos.append(item)
                        ok_final = True
                        break

                    else:
                        ultima_resposta = result

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

    # =========================
    # ESTOQUE
    # =========================
    def sync_stocks(
        self,
        rows: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:

        sucessos: List[Dict[str, Any]] = []
        erros: List[Dict[str, Any]] = []

        for indice, row in enumerate(rows, start=1):
            hash_row = _hash_row(row)

            if hash_row in self._processados:
                continue

            self._processados.add(hash_row)

            codigo = str(row.get("codigo") or "").strip()
            estoque = row.get("estoque")
            deposito_id = row.get("deposito_id")
            preco = row.get("preco")

            try:
                estoque_float = float(estoque or 0)
            except Exception:
                estoque_float = 0.0

            try:
                preco_float = float(preco) if preco not in (None, "") else None
            except Exception:
                preco_float = None

            inicio_item = time.perf_counter()
            ultima_resposta: Any = None
            tentativa_final = 0
            ok_final = False

            for tentativa in range(1, MAX_RETRY + 1):
                tentativa_final = tentativa

                try:
                    result = self.services.enviar_estoque(
                        [row],
                        deposito_id=deposito_id,
                        delay=0,
                    )

                    if result["sucesso"] > 0:
                        payload = {"ok": True}
                        ultima_resposta = payload

                        duracao = round(time.perf_counter() - inicio_item, 4)

                        item = {
                            "linha": indice,
                            "codigo": codigo,
                            "estoque": estoque_float,
                            "deposito_id": deposito_id,
                            "preco": preco_float,
                            "tentativas": tentativa,
                            "tempo_segundos": duracao,
                            "mensagem": "Estoque atualizado",
                            "retorno": payload,
                        }

                        sucessos.append(item)
                        ok_final = True
                        break

                    else:
                        ultima_resposta = result

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
                    "deposito_id": deposito_id,
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
