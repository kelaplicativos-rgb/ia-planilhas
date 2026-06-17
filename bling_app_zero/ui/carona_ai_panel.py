from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.caronas.blablacar_public import (
    CARPOOL_START_URL,
    PRIMARY_ACCOUNT,
    STRICT_NOT_CONFIRMED,
    BlaValidationResult,
    fetch_public_search,
    parse_public_search_mhtml,
    trips_to_table,
)
from bling_app_zero.caronas.carona_ai_forecast import auto_scan_best_predicted_dates, forecast_demand_without_dates
from bling_app_zero.caronas.carona_ai_llm import analyze_destination_demand_with_ai, is_openai_configured
from bling_app_zero.caronas.rota_cheia_strategy import rank_best_days
from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/carona_ai_panel.py'
RESULT_KEY = 'carona_ai_last_validation_result_v1'
RESULTS_KEY = 'carona_ai_validation_results_v1'
FORECAST_KEY = 'carona_ai_forecast_rows_v1'
AI_INSIGHT_KEY = 'carona_ai_last_ai_insight_v1'


def _as_results_list(value: object) -> list[BlaValidationResult]:
    if isinstance(value, BlaValidationResult):
        return [value]
    if isinstance(value, (list, tuple)):
        return [item for item in value if isinstance(item, BlaValidationResult)]
    return []


def _download_csv(label: str, rows: list[dict[str, object]], filename: str, key: str) -> None:
    if not rows:
        return
    df = pd.DataFrame(rows)
    csv = df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
    st.download_button(label, data=csv, file_name=filename, mime='text/csv; charset=utf-8', use_container_width=True, key=key)


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
    st.session_state[RESULTS_KEY] = filtered[-60:]
    add_audit_event(
        'carona_ai_public_search_validated',
        area='CARONA_AI',
        status='OK' if result.validated else 'AVISO',
        details={
            'validated': result.validated,
            'trips': len(result.trips),
            'own_trips': len(result.own_trips),
            'date': result.context.date,
            'origin': result.context.origin,
            'destination': result.context.destination,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def _store_results(results: list[BlaValidationResult]) -> None:
    for result in results:
        _store_result(result)


def _public_signals(results: list[BlaValidationResult]) -> list[dict[str, object]]:
    signals: list[dict[str, object]] = []
    for result in results:
        signals.append(
            {
                'date': result.context.date,
                'origin': result.context.origin,
                'destination': result.context.destination,
                'validated': result.validated,
                'trips': len(result.trips),
                'scarce': sum(1 for trip in result.trips if trip.is_scarce),
                'full': sum(1 for trip in result.trips if trip.is_full),
            }
        )
    return signals


def _run_forecast(
    *,
    platform_username: str,
    origin: str,
    destination: str,
    events_text: str,
    days_ahead: int,
    use_external_ai: bool,
    auto_validate_top: int,
) -> None:
    if not origin.strip() or not destination.strip():
        st.warning('Informe origem e destino para o Carona AI prever a demanda.')
        return

    existing_results = _as_results_list(st.session_state.get(RESULTS_KEY))
    ai_dates: tuple[str, ...] = ()
    if use_external_ai:
        insight = analyze_destination_demand_with_ai(
            origin=origin,
            destination=destination,
            horizon_days=days_ahead,
            events_text=events_text,
            public_signals=_public_signals(existing_results),
        )
        st.session_state[AI_INSIGHT_KEY] = insight
        ai_dates = insight.recommended_dates

    forecast = forecast_demand_without_dates(
        platform_username=platform_username,
        origin=origin,
        destination=destination,
        events_text=events_text,
        days_ahead=days_ahead,
        ai_recommended_dates=ai_dates,
    )
    st.session_state[FORECAST_KEY] = [row.to_dict() for row in forecast]

    if auto_validate_top > 0:
        _store_results(auto_scan_best_predicted_dates(forecast, limit=auto_validate_top))

    add_audit_event(
        'carona_ai_forecast_generated',
        area='CARONA_AI',
        status='OK',
        details={
            'origin': origin,
            'destination': destination,
            'days_ahead': days_ahead,
            'use_external_ai': use_external_ai,
            'auto_validate_top': auto_validate_top,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def _render_forecast() -> None:
    rows = st.session_state.get(FORECAST_KEY)
    if not isinstance(rows, list) or not rows:
        return
    st.caption('Previsão automática de alta demanda — o usuário não precisa informar datas')
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True, height=min(440, 92 + 38 * len(df)))
    _download_csv('⬇️ Baixar previsão Carona AI', rows, 'carona_ai_previsao_demanda.csv', 'download_carona_ai_forecast')


def _render_loaded_searches(results: list[BlaValidationResult]) -> None:
    if not results:
        return
    rows = [
        {
            'data': item.context.date,
            'origem': item.context.origin,
            'destino': item.context.destination,
            'viagens': len(item.trips),
            'minhas contas fixas': len(item.own_trips),
            'status': item.status,
            'fonte': item.source,
        }
        for item in results
    ]
    with st.expander('Buscas públicas carregadas/validadas', expanded=False):
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=min(320, 80 + 40 * len(rows)))
        if st.button('Limpar dados carregados', use_container_width=True, key='carona_ai_clear_all'):
            for key in (RESULT_KEY, RESULTS_KEY, FORECAST_KEY, AI_INSIGHT_KEY):
                st.session_state.pop(key, None)
            st.rerun()


def _render_confirmed_ranking(results: list[BlaValidationResult], *, username: str, destination: str, events_text: str) -> None:
    if not results or not destination.strip():
        return
    ranking = rank_best_days(results, platform_username=username, target_destination=destination, events_text=events_text)
    rows = [item.to_dict() for item in ranking]
    st.caption('Ranking confirmado por busca pública por data')
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=min(420, 92 + 42 * len(rows)))
    _download_csv('⬇️ Baixar ranking confirmado', rows, 'carona_ai_ranking_confirmado.csv', 'download_carona_ai_confirmed')


def _render_last_result(result: BlaValidationResult) -> None:
    if not result.validated:
        st.error(STRICT_NOT_CONFIRMED)
        st.caption(result.message)
        return
    st.success(result.status)
    rows = trips_to_table(result.trips)
    st.caption('Última busca pública validada')
    st.dataframe(
        pd.DataFrame(
            [
                {
                    'origem': result.context.origin,
                    'destino': result.context.destination,
                    'data': result.context.date,
                    'viagens': len(result.trips),
                    'minhas contas': len(result.own_trips),
                    'fonte': result.source,
                }
            ]
        ),
        use_container_width=True,
        hide_index=True,
        height=80,
    )
    with st.expander('Ver viagens públicas da última busca', expanded=False):
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=320)


def render_carona_ai_panel() -> None:
    with st.sidebar.expander('🚗 Carona AI', expanded=False):
        st.caption('Previsão de alta demanda + validação pública BlaBlaCar por data antes de publicar.')
        st.link_button('Abrir ponto inicial público', CARPOOL_START_URL, use_container_width=True)

        username = st.text_input('Nome do usuário na plataforma', value=PRIMARY_ACCOUNT, placeholder='Ex.: Ezequiel S ou Barbosa', key='carona_ai_username')
        origin = st.text_input('Origem base', value='Santo André, SP, Brasil', placeholder='Ex.: Santo André, SP ou São Paulo, SP', key='carona_ai_origin')
        destination = st.text_input('Destino/localidade', value='', placeholder='Ex.: São Thomé das Letras, Três Corações, Varginha...', key='carona_ai_destination')
        days_ahead = int(st.slider('Horizonte automático', min_value=7, max_value=45, value=21, step=7, key='carona_ai_days_ahead'))
        events_text = st.text_area(
            'Eventos/agenda da cidade',
            value='',
            placeholder='Ex.: 2026-06-20 - São Thomé - festival/show/feriado\n21/06/2026 - São Thomé - evento local',
            height=92,
            key='carona_ai_events_text',
        )
        use_external_ai = st.checkbox('Refinar com IA externa configurada', value=False, key='carona_ai_use_external')
        if use_external_ai and not is_openai_configured():
            st.info('Chave de IA não configurada. O sistema usará previsão interna + validação pública.')
        auto_validate_top = int(
            st.selectbox(
                'Validar no público as melhores datas agora',
                options=[0, 3, 5, 7, 10],
                index=0,
                key='carona_ai_auto_validate_top',
            )
        )
        if st.button('Gerar previsão Carona AI', use_container_width=True, key='carona_ai_generate_forecast'):
            _run_forecast(
                platform_username=username,
                origin=origin,
                destination=destination,
                events_text=events_text,
                days_ahead=days_ahead,
                use_external_ai=use_external_ai,
                auto_validate_top=auto_validate_top,
            )

        insight = st.session_state.get(AI_INSIGHT_KEY)
        if insight is not None:
            st.caption(getattr(insight, 'status', ''))
            summary = getattr(insight, 'summary', '')
            if summary:
                st.info(summary)

        _render_forecast()

        uploaded_files = st.file_uploader(
            'Anexar buscas públicas salvas por data (.mht/.mhtml/html)',
            type=['mht', 'mhtml', 'html', 'htm'],
            accept_multiple_files=True,
            key='carona_ai_mhtml_upload',
        )
        if uploaded_files:
            for uploaded in uploaded_files:
                try:
                    _store_result(parse_public_search_mhtml(uploaded.getvalue(), source=f'mhtml_upload:{uploaded.name}'))
                except Exception as exc:
                    st.error(f'Falha ao analisar {getattr(uploaded, "name", "arquivo")}: {exc}')

        search_url = st.text_input('Validar link público específico com data', value='', placeholder='https://www.blablacar.com.br/search?...&db=2026-06-20', key='carona_ai_public_url')
        if st.button('Validar link público agora', use_container_width=True, key='carona_ai_validate_public_url'):
            if not search_url.strip():
                st.error(STRICT_NOT_CONFIRMED)
            else:
                _store_result(fetch_public_search(search_url.strip()))

        results = _as_results_list(st.session_state.get(RESULTS_KEY))
        _render_loaded_searches(results)
        _render_confirmed_ranking(results, username=username, destination=destination, events_text=events_text)

        last = st.session_state.get(RESULT_KEY)
        if isinstance(last, BlaValidationResult):
            _render_last_result(last)
        elif not st.session_state.get(FORECAST_KEY):
            st.info('Informe origem e destino. O Carona AI escolhe as datas automaticamente e gera os links públicos para validar.')


__all__ = ['render_carona_ai_panel']
