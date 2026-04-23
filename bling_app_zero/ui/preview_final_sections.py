from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import (
    dataframe_para_csv_bytes,
    log_debug,
    validar_df_para_download,
)
from bling_app_zero.ui.preview_final_data import (
    garantir_df_final_canonico,
    montar_resumo,
    zerar_colunas_video,
)
from bling_app_zero.ui.preview_final_state import (
    fonte_descoberta_label,
    obter_deposito_nome_persistido,
    origem_site_ativa,
    url_site_atual,
    varredura_site_concluida,
)
from bling_app_zero.utils.gtin import (
    contar_gtins_invalidos_df,
    contar_gtins_suspeitos_df,
)


def render_resumo_validacao(df_final: pd.DataFrame, tipo_operacao: str) -> tuple[bool, list[str]]:
    df_final = garantir_df_final_canonico(
        df=df_final,
        tipo_operacao=tipo_operacao,
        deposito_nome=obter_deposito_nome_persistido(),
    )
    resumo = montar_resumo(df_final)
    valido, erros = validar_df_para_download(df_final, tipo_operacao)
    st.session_state["preview_validacao_ok"] = bool(valido)
    st.session_state["preview_validacao_erros"] = list(erros)

    st.markdown("### Validação do resultado final")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Linhas", resumo["linhas"])
    with c2:
        st.metric("Colunas", resumo["colunas"])
    with c3:
        st.metric("Com código", resumo["codigo_ok"])
    with c4:
        st.metric("Com descrição", resumo["descricao_ok"])

    c5, c6, c7 = st.columns(3)
    with c5:
        st.metric("Com preço", resumo["preco_ok"])
    with c6:
        st.metric("Com GTIN", resumo["gtin_ok"])
    with c7:
        st.metric("Validação", "OK" if valido else "Ajustes pendentes")

    gtins_invalidos_total = contar_gtins_invalidos_df(df_final)
    gtins_suspeitos = contar_gtins_suspeitos_df(df_final)
    gtins_invalidos_reais = max(int(gtins_invalidos_total) - int(gtins_suspeitos), 0)

    st.session_state["preview_validacao_ok"] = bool(valido)
    st.session_state["preview_validacao_erros"] = list(erros)

    if erros:
        st.error("Existem pendências obrigatórias antes do download e do envio.")
        for erro in erros:
            st.write(f"- {erro}")
        log_debug(f"Validação final com pendências: {' | '.join(erros)}", nivel="ERRO")
    else:
        st.success("A planilha final passou na validação principal.")
        log_debug("Validação final aprovada.", nivel="INFO")

    if gtins_invalidos_reais > 0 or gtins_suspeitos > 0:
        mensagem_gtin = (
            f"Existem {gtins_invalidos_reais} GTIN(s) inválido(s) e "
            f"{gtins_suspeitos} GTIN(s) suspeito(s). "
            "Corrija na etapa anterior se desejar. O preview final não bloqueia mais o download por GTIN."
        )
        st.warning(mensagem_gtin)
        log_debug(mensagem_gtin, nivel="AVISO")

    return valido, erros


def render_colunas_detectadas_sync(df_final: pd.DataFrame) -> None:
    resumo = montar_resumo(df_final)

    with st.expander("Colunas que o envio vai usar", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            st.write(f"**Código detectado:** {resumo['codigo_col'] or 'não encontrado'}")
            st.write(f"**Descrição detectada:** {resumo['descricao_col'] or 'não encontrada'}")
        with c2:
            st.write(f"**Preço detectado:** {resumo['preco_col'] or 'não encontrado'}")
            st.write(f"**GTIN detectado:** {resumo['gtin_col'] or 'não encontrado'}")

        if not resumo["codigo_col"] or not resumo["descricao_col"]:
            st.warning(
                "O sincronizador do Bling pode falhar no envio se código ou descrição não forem detectados corretamente."
            )


def render_preview_dataframe(df_final: pd.DataFrame) -> None:
    st.markdown("### Preview final")

    df_final = zerar_colunas_video(df_final)

    if df_final.empty:
        st.dataframe(pd.DataFrame(columns=df_final.columns), use_container_width=True)
        return

    st.dataframe(df_final.head(80), use_container_width=True)
    with st.expander("Ver preview ampliado", expanded=False):
        st.dataframe(df_final.head(250), use_container_width=True)


def render_download(df_final: pd.DataFrame, validacao_ok: bool) -> None:
    st.markdown("### Download da planilha padrão Bling")

    df_final = zerar_colunas_video(df_final)
    csv_bytes = dataframe_para_csv_bytes(df_final)

    gtins_invalidos_total = contar_gtins_invalidos_df(df_final)
    gtins_suspeitos = contar_gtins_suspeitos_df(df_final)
    gtins_invalidos_reais = max(int(gtins_invalidos_total) - int(gtins_suspeitos), 0)

    download_liberado = bool(validacao_ok)

    st.download_button(
        label="📥 Baixar CSV final",
        data=csv_bytes,
        file_name="bling_saida_final.csv",
        mime="text/csv",
        use_container_width=True,
        disabled=not download_liberado,
        key="btn_download_csv_final_preview",
    )

    if download_liberado:
        if gtins_invalidos_reais > 0 or gtins_suspeitos > 0:
            st.info(
                f"O download está liberado. Ainda existem {gtins_invalidos_reais} GTIN(s) inválido(s) "
                f"e {gtins_suspeitos} GTIN(s) suspeito(s), mas essa correção ficou centralizada na etapa anterior."
            )

        if st.session_state.get("preview_download_realizado", False):
            st.success("Download já confirmado. Conexão e envio ao Bling liberados.")
        elif st.button(
            "✅ Já baixei / seguir para conexão e envio",
            use_container_width=True,
            key="btn_confirmar_download_preview",
        ):
            st.session_state["preview_download_realizado"] = True
            log_debug("Usuário confirmou a etapa de download e avançou para conexão/envio.", nivel="INFO")
            st.rerun()
    else:
        st.info("Ajuste a validação principal antes de liberar o download e o envio.")


def render_origem_site_metadata() -> None:
    with st.expander("Origem da descoberta", expanded=False):
        if not origem_site_ativa():
            st.caption("A origem atual não veio da busca por site do fornecedor.")
            return

        url_site = url_site_atual()
        fonte = fonte_descoberta_label(st.session_state.get("site_busca_fonte_descoberta", ""))
        total_descobertos = int(st.session_state.get("site_busca_diagnostico_total_descobertos", 0) or 0)
        total_validos = int(st.session_state.get("site_busca_diagnostico_total_validos", 0) or 0)
        total_rejeitados = int(st.session_state.get("site_busca_diagnostico_total_rejeitados", 0) or 0)

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Fonte descoberta", fonte)
        with c2:
            st.metric("Descobertos", total_descobertos)
        with c3:
            st.metric("Válidos", total_validos)
        with c4:
            st.metric("Rejeitados", total_rejeitados)

        if url_site:
            st.write(f"**URL monitorada:** {url_site}")


def render_bloco_fluxo_site() -> None:
    with st.expander("Varredura do site e conversão GPT", expanded=False):
        if not origem_site_ativa():
            st.caption("A origem atual não veio da busca por site.")
            return

        url_site = url_site_atual()
        modo_auto = st.session_state.get("bling_sync_auto_mode", "manual")
        interval_value = st.session_state.get("bling_sync_interval_value", 15)
        interval_unit = st.session_state.get("bling_sync_interval_unit", "minutos")
        loop_ativo = bool(st.session_state.get("site_auto_loop_ativo", False))
        loop_status = str(st.session_state.get("site_auto_status", "inativo") or "inativo")
        ultima_execucao = str(st.session_state.get("site_auto_ultima_execucao", "") or "")
        fonte_descoberta = fonte_descoberta_label(st.session_state.get("site_busca_fonte_descoberta", ""))

        if varredura_site_concluida():
            st.success("Varredura do site concluída. Produtos localizados e prontos para seguir para o Bling.")
        else:
            st.warning(
                "A conexão OAuth e o envio só serão liberados depois da varredura do site terminar com dados válidos."
            )

        if url_site:
            st.write(f"**URL monitorada:** {url_site}")

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Loop", "Ativo" if loop_ativo else "Inativo")
        with c2:
            st.metric("Status", loop_status.title())
        with c3:
            st.metric("Última busca", ultima_execucao if ultima_execucao else "-")
        with c4:
            st.metric("Fonte descoberta", fonte_descoberta)

        if modo_auto == "periodico":
            st.info(f"Modo periódico configurado: **{interval_value} {interval_unit}**.")
