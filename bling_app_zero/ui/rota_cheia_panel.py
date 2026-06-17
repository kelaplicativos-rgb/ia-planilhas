from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.caronas.blablacar_public import (
    CARPOOL_START_URL,
    PRIMARY_ACCOUNT,
    STRICT_NOT_CONFIRMED,
    BlaValidationResult,
    build_recommendations,
    fetch_public_search,
    parse_public_search_mhtml,
    trips_to_table,
)
from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/rota_cheia_panel.py'
RESULT_KEY = 'rota_cheia_last_validation_result_v1'
RECOMMENDATION_KEY = 'rota_cheia_last_recommendations_v1'


def _result_context_table(result: BlaValidationResult) -> pd.DataFrame:
    context = result.context
    return pd.DataFrame(
        [
            {
                'origem': context.origin,
                'destino': context.destination,
                'data': context.date,
                'assentos': context.seats,
                'status de validação': result.status,
                'fonte': result.source,
            }
        ]
    )


def _recommendations_df(result: BlaValidationResult) -> pd.DataFrame:
    recommendations = build_recommendations(result, preferred_account=PRIMARY_ACCOUNT)
    rows = [item.to_dict() for item in recommendations]
    st.session_state[RECOMMENDATION_KEY] = rows
    return pd.DataFrame(rows)


def _trips_df(result: BlaValidationResult) -> pd.DataFrame:
    return pd.DataFrame(trips_to_table(result.trips))


def _download_csv_button(label: str, df: pd.DataFrame, filename: str, key: str) -> None:
    if df.empty:
        return
    csv = df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
    st.download_button(
        label,
        data=csv,
        file_name=filename,
        mime='text/csv; charset=utf-8',
        use_container_width=True,
        key=key,
    )


def _store_result(result: BlaValidationResult) -> None:
    st.session_state[RESULT_KEY] = result
    add_audit_event(
        'rota_cheia_public_search_validated',
        area='ROTA_CHEIA',
        status='OK' if result.validated else 'AVISO',
        details={
            'validated': result.validated,
            'source': result.source,
            'trips': len(result.trips),
            'own_trips': len(result.own_trips),
            'date': result.context.date,
            'origin': result.context.origin,
            'destination': result.context.destination,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def _render_validation_result(result: BlaValidationResult) -> None:
    if not result.validated:
        st.error(STRICT_NOT_CONFIRMED)
        if result.message:
            st.caption(result.message)
        return

    st.success(result.status)
    if result.message:
        st.caption(result.message)

    own_names = ', '.join(trip.driver_name for trip in result.own_trips) or 'nenhum'
    c1, c2, c3 = st.columns(3)
    c1.metric('viagens', len(result.trips))
    c2.metric('minhas contas', len(result.own_trips))
    c3.metric('Ezequiel/Barbosa', own_names)

    st.caption('Contexto validado pela busca pública')
    st.dataframe(_result_context_table(result), use_container_width=True, hide_index=True, height=80)

    rec_df = _recommendations_df(result)
    st.caption('Ação operacional')
    st.dataframe(rec_df, use_container_width=True, hide_index=True, height=min(220, 80 + 42 * max(len(rec_df), 1)))
    _download_csv_button('⬇️ Baixar ação SCAN BLA', rec_df, 'scan_bla_acao.csv', 'download_rota_cheia_recommendations')

    trips_df = _trips_df(result)
    with st.expander('Ver viagens públicas extraídas', expanded=False):
        if trips_df.empty:
            st.info('Nenhuma viagem pública extraída.')
        else:
            st.dataframe(trips_df, use_container_width=True, hide_index=True, height=360)
            _download_csv_button('⬇️ Baixar viagens públicas', trips_df, 'scan_bla_viagens_publicas.csv', 'download_rota_cheia_trips')

    with st.expander('Chamada pública / v9 detectada', expanded=False):
        st.caption('Ponto inicial obrigatório')
        st.code(CARPOOL_START_URL)
        st.caption('Link público da busca validada')
        st.code(result.context.search_url or 'não encontrado')
        if result.api_candidates:
            st.caption('URLs candidatas contendo v9/API encontradas no HTML/MHTML')
            for url in result.api_candidates[:8]:
                st.code(url)
        else:
            st.info('Nenhuma URL v9/API ficou exposta no arquivo salvo. A validação foi feita pelos cards públicos da busca por data.')


def _parse_uploaded_files(uploaded_files: list[object]) -> BlaValidationResult | None:
    latest_result: BlaValidationResult | None = None
    for uploaded in uploaded_files:
        try:
            raw = uploaded.getvalue()
            latest_result = parse_public_search_mhtml(raw, source=f'mhtml_upload:{uploaded.name}')
            _store_result(latest_result)
        except Exception as exc:
            add_audit_event(
                'rota_cheia_mhtml_parse_failed',
                area='ROTA_CHEIA',
                status='ERRO',
                details={'error': str(exc), 'file_name': getattr(uploaded, 'name', ''), 'responsible_file': RESPONSIBLE_FILE},
            )
            st.error(f'Falha ao analisar {getattr(uploaded, "name", "arquivo")}: {exc}')
    return latest_result


def render_rota_cheia_panel() -> None:
    with st.sidebar.expander('🚗 SCAN BLA / Rota Cheia', expanded=False):
        st.caption('Valida rota + data no público antes de sugerir CRIAR, MANTER, ALTERAR ou EXCLUIR.')
        st.link_button('Abrir ponto inicial público', CARPOOL_START_URL, use_container_width=True)

        uploaded_files = st.file_uploader(
            'Anexar busca pública salva (.mht/.mhtml/html)',
            type=['mht', 'mhtml', 'html', 'htm'],
            accept_multiple_files=True,
            key='rota_cheia_mhtml_upload',
        )
        if uploaded_files:
            result = _parse_uploaded_files(list(uploaded_files))
            if result is not None:
                _render_validation_result(result)
            return

        search_url = st.text_input(
            'Ou cole o link público já com data',
            value='',
            placeholder='https://www.blablacar.com.br/search?...&db=2026-06-20&...',
            key='rota_cheia_public_search_url',
        )
        if st.button('Validar link público agora', use_container_width=True, key='rota_cheia_validate_public_url'):
            if not search_url.strip():
                st.error(STRICT_NOT_CONFIRMED)
            else:
                result = fetch_public_search(search_url.strip())
                _store_result(result)
                _render_validation_result(result)
            return

        stored = st.session_state.get(RESULT_KEY)
        if isinstance(stored, BlaValidationResult):
            _render_validation_result(stored)
        else:
            st.info(STRICT_NOT_CONFIRMED)


__all__ = ['render_rota_cheia_panel']
