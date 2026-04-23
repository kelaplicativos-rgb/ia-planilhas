from __future__ import annotations

import json
from typing import Any

import pandas as pd
import streamlit as st


def append_envio_log(msg: str) -> None:
    logs = list(st.session_state.get("preview_envio_logs", []))
    logs.append(msg)
    st.session_state["preview_envio_logs"] = logs[-50:]


def render_resultado_envio_visual(resultado: dict[str, Any]) -> None:
    if not isinstance(resultado, dict) or not resultado:
        return

    st.markdown("#### Resultado do envio")

    modo = str(resultado.get("modo", "") or "")
    ok = bool(resultado.get("ok", False))
    mensagem = str(resultado.get("mensagem", "") or "").strip()

    if modo == "real":
        if ok:
            st.success(mensagem or "Envio real concluído com sucesso.")
        else:
            st.warning(mensagem or "Envio real concluído com pendências.")
    elif modo == "simulacao":
        st.error("O retorno abaixo é de SIMULAÇÃO. Nada foi enviado ao Bling.")
    else:
        st.warning(mensagem or "O envio terminou com retorno técnico.")

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("Total", int(resultado.get("total_itens", 0) or 0))
    with c2:
        st.metric("Criados", int(resultado.get("total_criados", 0) or 0))
    with c3:
        st.metric("Atualizados", int(resultado.get("total_atualizados", 0) or 0))
    with c4:
        st.metric("Ignorados", int(resultado.get("total_ignorados", 0) or 0))
    with c5:
        st.metric("Erros", int(resultado.get("total_erros", 0) or 0))

    st.caption(
        f"Modo: {modo or '-'} • Processado em: {resultado.get('processado_em', '-') or '-'} "
        f"• Próxima execução: {resultado.get('proxima_execucao', '-') or '-'}"
    )

    resultados = resultado.get("resultados", [])
    if isinstance(resultados, list) and resultados:
        df_resultados = pd.DataFrame(resultados)
        if not df_resultados.empty:
            erros_df = (
                df_resultados[df_resultados["status"].astype(str).str.lower().eq("erro")]
                if "status" in df_resultados.columns
                else pd.DataFrame()
            )
            with st.expander("Últimos itens processados", expanded=False):
                st.dataframe(df_resultados.tail(100), use_container_width=True)
            if not erros_df.empty:
                with st.expander("Itens com erro", expanded=False):
                    st.dataframe(erros_df, use_container_width=True)

    with st.expander("JSON técnico do retorno", expanded=False):
        st.code(json.dumps(resultado, ensure_ascii=False, indent=2), language="json")
