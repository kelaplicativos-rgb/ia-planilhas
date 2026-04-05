import json
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

import streamlit as st

from bling_app_zero.ui.state import init_state
from bling_app_zero.ui.origem_dados import render_origem_dados

from bling_app_zero.ui.bling_panel import (
    render_bling_panel,
    render_bling_import_panel,
)
from bling_app_zero.ui.precificacao_panel import render_precificacao_panel
from bling_app_zero.ui.envio_panel import render_send_panel


APP_VERSION = "1.0.0"
REMOTE_VERSION_URL = "https://raw.githubusercontent.com/kelaplicativos-rgb/ia-planilhas/main/version.json"
UPDATE_CHECK_TIMEOUT_SECONDS = 3
AUTO_RERUN_LIMIT = 2


st.set_page_config(page_title="Bling Manual PRO", layout="wide")


def _normalizar_versao(valor: str) -> list[int]:
    partes = str(valor or "").strip().split(".")
    resultado: list[int] = []
    for parte in partes:
        digitos = "".join(ch for ch in parte if ch.isdigit())
        resultado.append(int(digitos or "0"))
    while len(resultado) < 3:
        resultado.append(0)
    return resultado[:3]


def _versao_remota_eh_maior(local: str, remota: str) -> bool:
    return _normalizar_versao(remota) > _normalizar_versao(local)


@st.cache_data(ttl=30, show_spinner=False)
def _buscar_versao_remota() -> Optional[Dict[str, Any]]:
    try:
        req = urllib.request.Request(
            REMOTE_VERSION_URL,
            headers={
                "User-Agent": f"ia-planilhas/{APP_VERSION}",
                "Cache-Control": "no-cache",
            },
        )
        with urllib.request.urlopen(req, timeout=UPDATE_CHECK_TIMEOUT_SECONDS) as resp:
            payload = resp.read().decode("utf-8")
        data = json.loads(payload)
        if not isinstance(data, dict):
            return None
        versao = str(data.get("version", "")).strip()
        if not versao:
            return None
        return {
            "version": versao,
            "message": str(data.get("message", "")).strip(),
        }
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, ValueError):
        return None


def _render_verificacao_de_atualizacao() -> None:
    if "update_auto_reruns" not in st.session_state:
        st.session_state.update_auto_reruns = 0

    remoto = _buscar_versao_remota()
    if not remoto:
        return

    versao_remota = remoto["version"]
    mensagem_remota = remoto.get("message") or "Há uma nova versão disponível do sistema."

    if not _versao_remota_eh_maior(APP_VERSION, versao_remota):
        return

    st.warning(
        f"{mensagem_remota}\n\n"
        f"Versão atual: {APP_VERSION} | Versão disponível: {versao_remota}"
    )

    if st.session_state.update_auto_reruns < AUTO_RERUN_LIMIT:
        st.session_state.update_auto_reruns += 1
        time.sleep(0.4)
        st.rerun()

    if st.button("Atualizar agora", key="btn_atualizar_agora_app"):
        _buscar_versao_remota.clear()
        st.rerun()


def main() -> None:
    init_state()
    _render_verificacao_de_atualizacao()

    st.title("Bling Manual PRO")

    aba1, aba2, aba3, aba4 = st.tabs(
        [
            "Origem dos dados",
            "Integração Bling",
            "Precificação",
            "Envio",
        ]
    )

    with aba1:
        render_origem_dados()

    with aba2:
        render_bling_panel()
        st.divider()
        render_bling_import_panel()

    with aba3:
        render_precificacao_panel()

    with aba4:
        render_send_panel()


if __name__ == "__main__":
    main()
