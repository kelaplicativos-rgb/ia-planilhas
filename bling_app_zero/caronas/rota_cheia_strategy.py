from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from bling_app_zero.caronas.blablacar_public import (
    PRIMARY_ACCOUNT,
    SECONDARY_ACCOUNT,
    STRICT_NOT_CONFIRMED,
    VALIDATION_OK,
    BlaValidationResult,
    clean_text,
    detect_account,
    normalize_key,
    suggested_price_text,
)

DATE_ISO_RE = re.compile(r'\b(20\d{2}-\d{2}-\d{2})\b')
DATE_BR_RE = re.compile(r'\b(\d{1,2})/(\d{1,2})/(20\d{2})\b')
TIME_RE = re.compile(r'\b([01]?\d|2[0-3]):([0-5]\d)\b')

EVENT_KEYWORD_WEIGHTS: dict[str, int] = {
    'festival': 22,
    'show': 18,
    'festa': 16,
    'evento': 14,
    'feriado': 18,
    'lua cheia': 14,
    'encontro': 14,
    'congresso': 12,
    'corrida': 10,
    'carnaval': 26,
    'reveillon': 26,
    'réveillon': 26,
    'temporada': 12,
    'exposição': 10,
    'exposicao': 10,
}

CITY_ALIASES: dict[str, tuple[str, ...]] = {
    'sao tome das letras': ('sao tome', 'sao thome', 'sao tome das letras', 'sao thome das letras', 'sobradinho'),
    'tres coracoes': ('tres coracoes', 'três corações'),
    'varginha': ('varginha',),
    'pouso alegre': ('pouso alegre',),
    'extrema': ('extrema',),
    'cambuquira': ('cambuquira',),
    'campanha': ('campanha',),
}


@dataclass(frozen=True)
class CityDayScore:
    acao: str
    conta: str
    origem: str
    destino_final: str
    intermediarias: str
    data: str
    horario: str
    preco_sugerido: str
    risco_de_conflito: str
    status_de_validacao: str
    pontuacao: int
    nivel: str
    sinais_de_passageiros: str
    sinais_de_eventos: str
    motivo: str

    def to_dict(self) -> dict[str, object]:
        return {
            'ação': self.acao,
            'conta': self.conta,
            'origem': self.origem,
            'destino final': self.destino_final,
            'intermediárias': self.intermediarias,
            'data': self.data,
            'horário': self.horario,
            'preço sugerido': self.preco_sugerido,
            'risco de conflito': self.risco_de_conflito,
            'status de validação': self.status_de_validacao,
            'pontuação': self.pontuacao,
            'nível': self.nivel,
            'sinais de passageiros': self.sinais_de_passageiros,
            'sinais de eventos': self.sinais_de_eventos,
            'motivo': self.motivo,
        }


def _parse_date_token(value: str) -> str:
    text = clean_text(value)
    iso = DATE_ISO_RE.search(text)
    if iso:
        return iso.group(1)
    br = DATE_BR_RE.search(text)
    if br:
        day, month, year = br.groups()
        return f'{int(year):04d}-{int(month):02d}-{int(day):02d}'
    return ''


def _aliases_for_destination(destination: str) -> tuple[str, ...]:
    key = normalize_key(destination)
    aliases: set[str] = {key} if key else set()
    for canonical, known_aliases in CITY_ALIASES.items():
        if canonical in key or any(alias in key for alias in known_aliases):
            aliases.add(canonical)
            aliases.update(normalize_key(alias) for alias in known_aliases)
    return tuple(sorted(alias for alias in aliases if alias))


def _matches_destination(text: str, destination: str) -> bool:
    key = normalize_key(text)
    aliases = _aliases_for_destination(destination)
    return not aliases or any(alias in key for alias in aliases)


def parse_event_agenda(events_text: str, target_destination: str) -> dict[str, list[str]]:
    """Lê uma agenda colada pelo usuário e agrupa eventos por data ISO.

    Exemplo aceito: "2026-06-20 - São Thomé - Festival de inverno" ou "20/06/2026 show".
    Linhas sem data são ignoradas para evitar recomendar dia sem validação objetiva.
    """
    events_by_date: dict[str, list[str]] = defaultdict(list)
    for raw_line in str(events_text or '').splitlines():
        line = clean_text(raw_line)
        if not line:
            continue
        event_date = _parse_date_token(line)
        if not event_date:
            continue
        if target_destination and not _matches_destination(line, target_destination):
            continue
        events_by_date[event_date].append(line)
    return dict(events_by_date)


def _event_score(lines: Iterable[str]) -> tuple[int, str]:
    score = 0
    detected: list[str] = []
    for line in lines:
        line_key = normalize_key(line)
        line_score = 8
        matched_keywords: list[str] = []
        for keyword, weight in EVENT_KEYWORD_WEIGHTS.items():
            if normalize_key(keyword) in line_key:
                line_score += weight
                matched_keywords.append(keyword)
        score += min(line_score, 38)
        detected.append(f'{line} ({", ".join(matched_keywords) if matched_keywords else "evento informado"})')
    return min(score, 45), ' | '.join(detected)


def _weekday_bonus(result: BlaValidationResult, target_destination: str) -> tuple[int, str]:
    try:
        weekday = datetime.strptime(result.context.date, '%Y-%m-%d').weekday()
    except Exception:
        return 0, ''
    origin_key = normalize_key(result.context.origin)
    destination_key = normalize_key(result.context.destination or target_destination)
    sp_to_mg = any(city in origin_key for city in ('santo andre', 'sao paulo')) and not any(
        city in destination_key for city in ('santo andre', 'sao paulo')
    )
    mg_to_sp = any(city in destination_key for city in ('santo andre', 'sao paulo'))
    if sp_to_mg and weekday == 3:
        return 10, 'quinta à noite costuma encaixar ida 17:30'
    if sp_to_mg and weekday == 4:
        return 14, 'sexta à noite costuma encaixar ida 20:30'
    if sp_to_mg and weekday == 5:
        return 7, 'sábado à noite só vale com demanda/evento'
    if mg_to_sp and weekday == 4:
        return 8, 'sexta de manhã costuma encaixar volta'
    if mg_to_sp and weekday == 6:
        return 12, 'domingo por volta de 11:00 costuma encaixar volta'
    return 0, ''


def _driver_matches_user(driver_name: str, platform_username: str) -> bool:
    driver_key = normalize_key(driver_name)
    user_key = normalize_key(platform_username)
    if not driver_key or not user_key:
        return False
    return driver_key == user_key


def _own_trips_for_user(result: BlaValidationResult, platform_username: str):
    return tuple(trip for trip in result.trips if _driver_matches_user(trip.driver_name, platform_username))


def _best_times(result: BlaValidationResult) -> str:
    weighted: dict[str, int] = defaultdict(int)
    for trip in result.trips:
        if not trip.departure_time:
            continue
        weight = 2
        if trip.is_scarce:
            weight += 4
        if trip.is_full:
            weight += 5
        if trip.arrival_station and _matches_destination(trip.arrival_station, result.context.destination):
            weight += 1
        weighted[trip.departure_time] += weight
    if not weighted:
        bonus, reason = _weekday_bonus(result, result.context.destination)
        if '17:30' in reason:
            return '17:30'
        if '20:30' in reason:
            return '20:30'
        if '11:00' in reason:
            return '11:00'
        return 'validar horário pela busca pública'
    ordered = sorted(weighted.items(), key=lambda item: (-item[1], item[0]))
    return ' / '.join(time for time, _score in ordered[:3])


def _passenger_score(result: BlaValidationResult, target_destination: str) -> tuple[int, str]:
    matching = [trip for trip in result.trips if _matches_destination(trip.arrival_station or result.context.destination, target_destination)]
    trips = matching or list(result.trips)
    total = len(trips)
    scarce = sum(1 for trip in trips if trip.is_scarce)
    full = sum(1 for trip in trips if trip.is_full)
    available = sum(1 for trip in trips if not trip.is_full)
    score = min(total * 4, 28) + scarce * 12 + full * 10 + min(available * 2, 10)
    if total >= 8:
        score += 8
    if scarce or full:
        score += 10
    score = min(score, 65)
    parts = [f'{total} viagem(ns) pública(s) no destino/data']
    if scarce:
        parts.append(f'{scarce} com esgotará em breve')
    if full:
        parts.append(f'{full} cheia(s)')
    if available:
        parts.append(f'{available} ainda com vaga')
    return score, '; '.join(parts)


def _conflict_risk(result: BlaValidationResult, platform_username: str, target_destination: str) -> str:
    target_key = normalize_key(target_destination or result.context.destination)
    if 'tres coracoes' not in target_key:
        return 'baixo'
    account = detect_account(platform_username, platform_username or PRIMARY_ACCOUNT)
    other = SECONDARY_ACCOUNT if account == PRIMARY_ACCOUNT else PRIMARY_ACCOUNT
    other_present = any(detect_account(trip.driver_name, '') == other for trip in result.trips)
    if other_present:
        return f'ALTO: {other} já aparece na busca para Três Corações nesta data.'
    return f'atenção: não publicar {other} para Três Corações no mesmo dia.'


def _level(score: int) -> str:
    if score >= 80:
        return 'MUITO ALTO'
    if score >= 60:
        return 'ALTO'
    if score >= 40:
        return 'MÉDIO'
    return 'BAIXO'


def _intermediarias_for_destination(destination: str) -> str:
    key = normalize_key(destination)
    if any(city in key for city in ('sao tome', 'sao thome', 'sobradinho')):
        return 'Extrema / Pouso Alegre / Três Corações conforme demanda'
    if any(city in key for city in ('varginha', 'cambuquira', 'campanha')):
        return 'Extrema / Pouso Alegre / Três Corações'
    if 'tres coracoes' in key:
        return 'Extrema / Pouso Alegre'
    if 'pouso alegre' in key:
        return 'Extrema'
    return 'sem intermediárias obrigatórias'


def rank_best_days(
    results: Iterable[BlaValidationResult],
    *,
    platform_username: str,
    target_destination: str,
    events_text: str = '',
) -> list[CityDayScore]:
    events_by_date = parse_event_agenda(events_text, target_destination)
    rows: list[CityDayScore] = []
    clean_user = clean_text(platform_username) or PRIMARY_ACCOUNT
    clean_destination = clean_text(target_destination)

    for result in results:
        if not result.validated:
            continue
        if clean_destination and not _matches_destination(result.context.destination, clean_destination):
            continue

        passenger_score, passenger_signals = _passenger_score(result, clean_destination or result.context.destination)
        event_score, event_signals = _event_score(events_by_date.get(result.context.date, []))
        weekday_score, weekday_reason = _weekday_bonus(result, clean_destination or result.context.destination)
        own_trips = _own_trips_for_user(result, clean_user)
        score = passenger_score + event_score + weekday_score
        action = 'CRIAR / PUBLICAR'
        if own_trips:
            score += 5
            action = 'MANTER / NÃO DUPLICAR'
        if _conflict_risk(result, clean_user, clean_destination or result.context.destination).startswith('ALTO'):
            score = max(score - 25, 0)
            action = 'NÃO PUBLICAR / CONFLITO'
        score = max(0, min(int(score), 100))

        reasons = [passenger_signals]
        if event_signals:
            reasons.append(event_signals)
        if weekday_reason:
            reasons.append(weekday_reason)
        if own_trips:
            reasons.append(f'{clean_user} já aparece publicado nesta rota/data')

        rows.append(
            CityDayScore(
                acao=action,
                conta=clean_user,
                origem=result.context.origin,
                destino_final=clean_destination or result.context.destination,
                intermediarias=_intermediarias_for_destination(clean_destination or result.context.destination),
                data=result.context.date,
                horario=_best_times(result),
                preco_sugerido=suggested_price_text(result.trips),
                risco_de_conflito=_conflict_risk(result, clean_user, clean_destination or result.context.destination),
                status_de_validacao=VALIDATION_OK,
                pontuacao=score,
                nivel=_level(score),
                sinais_de_passageiros=passenger_signals,
                sinais_de_eventos=event_signals or 'nenhum evento informado para esta data',
                motivo=' | '.join(reason for reason in reasons if reason),
            )
        )

    rows.sort(key=lambda item: (-item.pontuacao, item.data, item.horario))
    if rows:
        return rows
    return [
        CityDayScore(
            acao=STRICT_NOT_CONFIRMED,
            conta=clean_user,
            origem='',
            destino_final=clean_destination,
            intermediarias='',
            data='',
            horario='',
            preco_sugerido='',
            risco_de_conflito='indefinido',
            status_de_validacao=STRICT_NOT_CONFIRMED,
            pontuacao=0,
            nivel='SEM DADOS',
            sinais_de_passageiros='sem busca pública validada para o destino',
            sinais_de_eventos='sem eventos com data reconhecida',
            motivo='Anexe buscas públicas por rota + data ou cole link público validado antes de recomendar ação.',
        )
    ]


__all__ = ['CityDayScore', 'parse_event_agenda', 'rank_best_days']
