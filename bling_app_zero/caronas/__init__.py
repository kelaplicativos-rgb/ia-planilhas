"""Ferramentas do Rota Cheia para validação pública de caronas."""

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

__all__ = [
    'BlaRecommendation',
    'BlaSearchContext',
    'BlaTrip',
    'BlaValidationResult',
    'CARPOOL_START_URL',
    'PRIMARY_ACCOUNT',
    'SECONDARY_ACCOUNT',
    'STRICT_NOT_CONFIRMED',
    'VALIDATION_OK',
    'build_public_search_url',
    'build_recommendations',
    'fetch_public_search',
    'parse_public_search_mhtml',
    'trips_to_table',
]
