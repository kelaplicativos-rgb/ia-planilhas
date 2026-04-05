import json
import time
import traceback
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

import streamlit as st

from bling_app_zero.ui.state import init_state
from bling_app_zero.ui import origem_dados as origem_dados_ui
from bling_app_zero.ui.bling_panel import (
    render_bling_import_panel,
    render_bling_panel,
)

APP_VERSION = "1.0.2"
REMOTE_VERSION_URL = "https://raw.githubusercontent.com/kelaplicativos-rgb/ia-planilhas/main/version.json"
UPDATE_CHECK_TIMEOUT_SECONDS = 3
AUTO_RERUN_LIMIT = 2

st.set_page_config(
    page_title="Bling Manual PRO",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def log(msg):
    if "logs" not in st.session_state:
        st.session_state["logs"] = []
    st.session_state["logs"].append(str(msg))


def aplicar_estilo_global() -> None:
    st.markdown(
        """
        <style>
        </style>
        """,
        unsafe_allow_html=True,
    )


def _normalizar_versao(valor: str) -> list[int]:
    partes = str(valor or "").strip().split(".")
    numeros: list[int] = []

    for parte in partes:
        digitos = "".join(ch for ch in parte if ch.isdigit())
        numeros.append(int(digitos or "0"))

    while len(numeros) < 3:
        numeros.append(0)

    return numeros[:3]


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
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        TimeoutError,
        json.JSONDecodeError,
        ValueError,
    ):
        return None


def _render_verificacao_de_atualizacao() -> None:
    if "update_auto_reruns" not in st.session_state:
        st.session_state["update_auto_reruns"] = 0

    remoto = _buscar_versao_remota()
    if not remoto:
        return

    versao_remota = remoto["version"]
    mensagem_remota = remoto.get("message") or "Há uma nova versão disponível do sistema."

    if not _versao_remota_eh_maior(APP_VERSION, versao_remota):
        st.session_state["update_auto_reruns"] = 0
        return

    st.warning(
        f"{mensagem_remota}\n\n"
        f"Versão atual: {APP_VERSION} | Versão disponível: {versao_remota}"
    )

    if st.session_state["update_auto_reruns"] < AUTO_RERUN_LIMIT:
        st.session_state["update_auto_reruns"] += 1
        time.sleep(0.4)
        st.rerun()

    if st.button("Atualizar agora", key="btn_atualizar_agora_app"):
        _buscar_versao_remota.clear()
        st.rerun()


def _obter_render_origem_dados():
    if hasattr(origem_dados_ui, "render_origem_dados"):
        return origem_dados_ui.render_origem_dados

    if hasattr(origem_dados_ui, "tela_origem_dados"):
        return origem_dados_ui.tela_origem_dados

    nomes_disponiveis = [nome for nome in dir(origem_dados_ui) if not nome.startswith("_")]
    raise AttributeError(
        "O módulo 'bling_app_zero.ui.origem_dados' não possui "
        "'render_origem_dados' nem 'tela_origem_dados'. "
        f"Nomes encontrados: {nomes_disponiveis}"
    )


def executar_seguro(func, nome):
    try:
        func()
    except Exception as e:
        erro = f"Erro em {nome}: {e}"
        log(erro)
        log(traceback.format_exc())
        st.error(f"❌ {erro}")
        with st.expander("Detalhes do erro"):
            st.code(traceback.format_exc())


def main() -> None:
    init_state()
    aplicar_estilo_global()
    _render_verificacao_de_atualizacao()

    st.title("Bling Manual PRO")

    aba1, aba2 = st.tabs(
        [
            "Origem dos dados",
            "Integração Bling",
        ]
    )

    render_origem = _obter_render_origem_dados()

    with aba1:
        executar_seguro(render_origem, "Origem dos dados")

    with aba2:
        executar_seguro(render_bling_panel, "Painel Bling")
        st.divider()
        executar_seguro(render_bling_import_panel, "Importação Bling")
        st.divider()

        with st.expander("Logs do sistema"):
            logs = st.session_state.get("logs", [])
            if logs:
                st.text_area("Logs", "\n".join(logs), height=200)
            else:
                st.write("Sem logs ainda.")


if __name__ == "__main__":
    main()
