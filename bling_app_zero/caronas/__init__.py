"""Ferramentas do Carona AI para previsão de demanda e validação pública de caronas."""

from __future__ import annotations

from bling_app_zero.caronas.blablacar_public import (
    CARPOOL_START_URL,
    PRIMARY_ACCOUNT,
    SECONDARY_ACCOUNT,
    STRICT_NOT_CONFIRMED,
    VALIDATION_OK,
    BlaRecommendation,
    BlaSearchContext,
    BlaTrip,
    BlaValidationResult,
    build_public_search_url,
    build_recommendations,
    fetch_public_search,
    parse_public_search_mhtml,
    trips_to_table,
)
from bling_app_zero.caronas.carona_ai_forecast import (
    DemandForecastRow,
    PREDICTION_STATUS,
    auto_scan_best_predicted_dates,
    forecast_demand_without_dates,
    generate_candidate_dates,
)
from bling_app_zero.caronas.carona_ai_llm import AIDemandInsight, analyze_destination_demand_with_ai, is_openai_configured
from bling_app_zero.caronas.rota_cheia_strategy import CityDayScore, parse_event_agenda, rank_best_days

__all__ = [
    'AIDemandInsight',
    'BlaRecommendation',
    'BlaSearchContext',
    'BlaTrip',
    'BlaValidationResult',
    'CARPOOL_START_URL',
    'CityDayScore',
    'DemandForecastRow',
    'PREDICTION_STATUS',
    'PRIMARY_ACCOUNT',
    'SECONDARY_ACCOUNT',
    'STRICT_NOT_CONFIRMED',
    'VALIDATION_OK',
    'analyze_destination_demand_with_ai',
    'auto_scan_best_predicted_dates',
    'build_public_search_url',
    'build_recommendations',
    'fetch_public_search',
    'forecast_demand_without_dates',
    'generate_candidate_dates',
    'is_openai_configured',
    'parse_event_agenda',
    'parse_public_search_mhtml',
    'rank_best_days',
    'trips_to_table',
]
