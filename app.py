from __future__ import annotations

import streamlit as st
from datetime import datetime

# =========================
# 🔥 VERSIONAMENTO
# =========================
APP_VERSION = "1.0.6"


# =========================
# 🔥 LOG GLOBAL
# =========================
if "logs" not in st.session_state:
    st.session_state["logs"] = []


def log_debug(msg: str, nivel: str = "INFO") -> None:
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        linha = f"[{timestamp}] [{nivel}] {msg}"
        st.session_state["logs"].append(linha)
    except Exception:
        pass


# =========================
# 🔥 IA DEBUG
# =========================
def analisar_logs_com_ia(logs: list[str]) -> dict:
    if not logs:
        return {}

    texto = "\n".join(logs[-50:]).lower()

    diagnostico = {
        "tipo": "",
        "problema": "",
        "solucao": ""
    }

    if "unicode" in texto or "decode" in texto:
        diagnostico["tipo"] = "Erro de encoding (CSV)"
        diagnostico["problema"] = "Arquivo CSV com encoding incompatível"
        diagnostico["solucao"] = "Salvar CSV como UTF-8"

    elif "vazia" in texto or "empty" in texto:
        diagnostico["tipo"] = "Planilha vazia"
        diagnostico["problema"] = "Arquivo sem dados válidos"
        diagnostico["solucao"] = "Verifique conteúdo da planilha"

    elif "colunas" in texto and "erro" in texto:
        diagnostico["tipo"] = "Erro de colunas"
        diagnostico["problema"] = "Cabeçalho não identificado"
        diagnostico["solucao"] = "Revisar cabeçalho da planilha"

    elif "gtin" in texto or "ean" in texto:
        diagnostico["tipo"] = "Problema com GTIN/EAN"
        diagnostico["problema"] = "Valores inválidos detectados"
        diagnostico["solucao"] = "Sistema limpa automaticamente"

    elif "excel" in texto and "erro" in texto:
        diagnostico["tipo"] = "Erro ao gerar Excel"
        diagnostico["problema"] = "Falha na exportação"
        diagnostico["solucao"] = "Verifique dados inválidos"

    elif "import" in texto and "erro" in texto:
        diagnostico["tipo"] = "Erro de importação"
        diagnostico["problema"] = "Falha em módulos do sistema"
        diagnostico["solucao"] = "Verificar arquivos do projeto"

    else:
        diagnostico["tipo"] = "Não identificado"
        diagnostico["problema"] = "IA não detectou erro claro"
        diagnostico["solucao"] = "Verifique o log manual"

    return diagnostico


# =========================
# 🔥 PROTEÇÃO GLOBAL
# =========================
def executar_com_log(func, nome: str):
    try:
        log_debug(f"Iniciando: {nome}")
        func()
        log_debug(f"Finalizado: {nome}", "SUCCESS")
    except Exception as e:
        erro = f"Erro em {nome}: {str(e)}"
        log_debug(erro, "ERROR")
        st.error(erro)


# =========================
# 🔥 IMPORTS DO SISTEMA
# =========================
try:
    from bling_app_zero.ui.origem_dados import render_origem_dados
    log_debug("Import origem_dados OK")
except Exception as e:
    log_debug(f"Erro import origem_dados: {e}", "ERROR")

try:
    from bling_app_zero.ui.origem_mapeamento import render_origem_mapeamento
    log_debug("Import origem_mapeamento OK")
except Exception as e:
    log_debug(f"Erro import origem_mapeamento: {e}", "ERROR")

try:
    from bling_app_zero.ui.bling_panel import render_bling_panel
    log_debug("Import bling_panel OK")
except Exception as e:
    log_debug(f"Erro import bling_panel: {e}", "ERROR")


# =========================
# 🔥 CONFIG PAGE
# =========================
st.set_page_config(
    page_title="IA Planilhas Bling",
    layout="wide"
)


# =========================
# 🔥 HEADER
# =========================
st.title("IA Planilhas → Bling")
st.caption(f"Versão: {APP_VERSION}")


# =========================
# 🔥 FLUXO PRINCIPAL
# =========================
try:
    executar_com_log(render_origem_dados, "Origem dos Dados")
except:
    pass


# =========================
# 🔥 DEBUG (OCULTO)
# =========================
with st.expander("🔍 Debug do sistema", expanded=False):

    st.markdown("### Logs em tempo real")

    logs = st.session_state.get("logs", [])

    if logs:
        for l in reversed(logs[-50:]):
            st.text(l)
    else:
        st.info("Nenhum log ainda.")

    st.markdown("---")

    # DOWNLOAD LOG
    log_texto = "\n".join(logs) if logs else "Sem logs disponíveis"

    st.download_button(
        label="📥 Baixar log completo",
        data=log_texto.encode("utf-8"),
        file_name="debug_sistema.txt",
        mime="text/plain",
        use_container_width=True,
    )

    st.markdown("---")

    # =========================
    # 🧠 IA DEBUG
    # =========================
    st.markdown("### 🧠 Diagnóstico automático")

    diagnostico = analisar_logs_com_ia(logs)

    if diagnostico:
        st.warning(f"Tipo: {diagnostico.get('tipo')}")
        st.write(f"Problema: {diagnostico.get('problema')}")
        st.success(f"Solução: {diagnostico.get('solucao')}")
