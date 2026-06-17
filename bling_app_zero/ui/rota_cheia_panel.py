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
from bling_app_zero.caronas.rota_cheia_strategy import rank_best_days
from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/rota_cheia_panel.py'
RESULT_KEY = 'rota_cheia_last_validation_result_v1'
RESULTS_KEY = 'rota_cheia_validation_results_v2'
RECOMMENDATION_KEY = 'rota_cheia_last_recommendations_v1'
BEST_DAYS_KEY = 'rota_cheia_best_days_v1'


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


def _recommendations_df(result: BlaValidationResult, platform_username: str = PRIMARY_ACCOUNT) -> pd.DataFrame:
    recommendations = build_recommendations(result, preferred_account=platform_username or PRIMARY_ACCOUNT)
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


def _as_results_list(value: object) -> list[BlaValidationResult]:
    if isinstance(value, BlaValidationResult):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, BlaValidationResult)]
    if isinstance(value, tuple):
        return [item for item in value if isinstance(item, BlaValidationResult)]
    return []


def _store_result(result: BlaValidationResult) -> None:
    existing = _as_results_list(st.session_state.get(RESULTS_KEY))
    key = (result.context.search_url, result.context.date, result.context.origin, result.context.destination, result.source)
    filtered = [
        item
        for item in existing
        if (item.context.search_url, item.context.date, item.context.origin, item.context.destination, item.source) != key
    ]
    filtered.append(result)
    st.session_state[RESULT_KEY] = result
    st.session_state[RESULTS_KEY] = filtered[-30:]
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
            'total_results_in_session': len(filtered[-30:]),
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def _render_validation_result(result: BlaValidationResult, *, platform_username: str = PRIMARY_ACCOUNT) -> None:
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
    c2.metric('Ezequiel/Barbosa', len(result.own_trips))
    c3.metric('nomes encontrados', own_names)

    st.caption('Contexto validado pela busca pública')
    st.dataframe(_result_context_table(result), use_container_width=True, hide_index=True, height=80)

    rec_df = _recommendations_df(result, platform_username=platform_username)
    st.caption('Ação operacional da busca selecionada')
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


def _parse_uploaded_files(uploaded_files: list[object]) -> list[BlaValidationResult]:
    parsed_results: list[BlaValidationResult] = []
    for uploaded in uploaded_files:
        try:
            raw = uploaded.getvalue()
            result = parse_public_search_mhtml(raw, source=f'mhtml_upload:{uploaded.name}')
            parsed_results.append(result)
            _store_result(result)
        except Exception as exc:
            add_audit_event(
                'rota_cheia_mhtml_parse_failed',
                area='ROTA_CHEIA',
                status='ERRO',
                details={'error': str(exc), 'file_name': getattr(uploaded, 'name', ''), 'responsible_file': RESPONSIBLE_FILE},
            )
            st.error(f'Falha ao analisar {getattr(uploaded, "name", "arquivo")}: {exc}')
    return parsed_results


def _render_best_days_panel(results: list[BlaValidationResult], *, platform_username: str, target_destination: str, events_text: str) -> None:
    ranking = rank_best_days(
        results,
        platform_username=platform_username,
        target_destination=target_destination,
        events_text=events_text,
    )
    rows = [item.to_dict() for item in ranking]
    st.session_state[BEST_DAYS_KEY] = rows
    df = pd.DataFrame(rows)
    st.caption('Ranking de melhores dias para o destino informado')
    st.dataframe(df, use_container_width=True, hide_index=True, height=min(420, 92 + 42 * max(len(df), 1)))
    _download_csv_button('⬇️ Baixar ranking de melhores dias', df, 'scan_bla_melhores_dias.csv', 'download_rota_cheia_best_days')


def _render_results_inventory(results: list[BlaValidationResult]) -> None:
    if not results:
        return
    rows = []
    for result in results:
        rows.append(
            {
                'data': result.context.date,
                'origem': result.context.origin,
                'destino': result.context.destination,
                'viagens': len(result.trips),
                'minhas contas fixas': len(result.own_trips),
                'status': result.status,
                'fonte': result.source,
            }
        )
    with st.expander('Buscas públicas carregadas na sessão', expanded=False):
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=min(320, 80 + 40 * len(rows)))
        if st.button('Limpar buscas carregadas', use_container_width=True, key='rota_cheia_clear_loaded_results'):
            st.session_state.pop(RESULT_KEY, None)
            st.session_state.pop(RESULTS_KEY, None)
            st.session_state.pop(BEST_DAYS_KEY, None)
            st.rerun()


def render_rota_cheia_panel() -> None:
    with st.sidebar.expander('🚗 SCAN BLA / Rota Cheia', expanded=False):
        st.caption('Valida rota + data no público antes de sugerir CRIAR, MANTER, ALTERAR ou EXCLUIR.')
        st.link_button('Abrir ponto inicial público', CARPOOL_START_URL, use_container_width=True)

        platform_username = st.text_input(
            'Nome do usuário na plataforma',
            value=st.session_state.get('rota_cheia_platform_username', PRIMARY_ACCOUNT) or PRIMARY_ACCOUNT,
            placeholder='Ex.: Ezequiel S ou Barbosa',
            key='rota_cheia_platform_username',
        )
        target_destination = st.text_input(
            'Destino que ele vai',
            value=st.session_state.get('rota_cheia_target_destination', ''),
            placeholder='Ex.: São Thomé das Letras, Três Corações, Varginha...',
            key='rota_cheia_target_destination',
        )
        events_text = st.text_area(
            'Eventos/agenda da cidade com data',
            value=st.session_state.get('rota_cheia_events_text', ''),
            placeholder='Ex.: 2026-06-20 - São Thomé das Letras - Festival/show/feriado\n21/06/2026 - São Thomé - evento local',
            height=92,
            key='rota_cheia_events_text',
        )

        uploaded_files = st.file_uploader(
            'Anexar buscas públicas salvas por data (.mht/.mhtml/html)',
            type=['mht', 'mhtml', 'html', 'htm'],
            accept_multiple_files=True,
            key='rota_cheia_mhtml_upload',
        )
        parsed_now: list[BlaValidationResult] = []
        if uploaded_files:
            parsed_now = _parse_uploaded_files(list(uploaded_files))

        search_url = st.text_input(
            'Ou cole um link público já com data',
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
                parsed_now = [result]

        results = _as_results_list(st.session_state.get(RESULTS_KEY))
        _render_results_inventory(results)

        if results:
            if target_destination.strip():
                _render_best_days_panel(
                    results,
                    platform_username=platform_username,
                    target_destination=target_destination,
                    events_text=events_text,
                )
            else:
                st.warning('Informe o destino que ele vai para gerar o ranking dos melhores dias.')

        result_to_show = parsed_now[-1] if parsed_now else st.session_state.get(RESULT_KEY)
        if isinstance(result_to_show, BlaValidationResult):
            _render_validation_result(result_to_show, platform_username=platform_username)
        elif not results:
            st.info(STRICT_NOT_CONFIRMED)


__all__ = ['render_rota_cheia_panel']
