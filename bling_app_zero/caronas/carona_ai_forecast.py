from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable

from bling_app_zero.caronas.blablacar_public import (
    PRIMARY_ACCOUNT,
    STRICT_NOT_CONFIRMED,
    VALIDATION_OK,
    BlaValidationResult,
    build_public_search_url,
    fetch_public_search,
    normalize_key,
)
from bling_app_zero.caronas.rota_cheia_strategy import parse_event_agenda, rank_best_days

PREDICTION_STATUS = 'previsão de demanda / pendente validar busca pública por data'


@dataclass(frozen=True)
class DemandForecastRow:
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
    link_busca_publica: str

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
            'link busca pública': self.link_busca_publica,
        }


def _level(score: int) -> str:
    if score >= 80:
        return 'MUITO ALTO'
    if score >= 60:
        return 'ALTO'
    if score >= 40:
        return 'MÉDIO'
    return 'BAIXO'


def _is_sp_origin(origin: str) -> bool:
    key = normalize_key(origin)
    return any(city in key for city in ('santo andre', 'sao paulo', 'sp'))


def _is_sp_destination(destination: str) -> bool:
    key = normalize_key(destination)
    return any(city in key for city in ('santo andre', 'sao paulo', 'sp'))


def _intermediarias(destination: str) -> str:
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


def _base_time_and_score(target_date: date, origin: str, destination: str) -> tuple[str, int, str]:
    weekday = target_date.weekday()
    sp_to_mg = _is_sp_origin(origin) and not _is_sp_destination(destination)
    mg_to_sp = _is_sp_destination(destination)
    if sp_to_mg and weekday == 3:
        return '17:30', 56, 'quinta à noite tende a antecipar ida com boa chance de reserva'
    if sp_to_mg and weekday == 4:
        return '20:30', 68, 'sexta à noite costuma concentrar ida de passageiros'
    if sp_to_mg and weekday == 5:
        return 'noite', 42, 'sábado à noite só vale quando evento ou demanda justificar'
    if mg_to_sp and weekday == 4:
        return 'manhã', 48, 'sexta de manhã encaixa volta curta depois da ida de quinta'
    if mg_to_sp and weekday == 6:
        return '11:00', 64, 'domingo por volta de 11:00 costuma concentrar retorno'
    if weekday in (0, 1, 2):
        return 'validar horário', 24, 'dia útil com demanda normalmente menor; validar antes de publicar'
    return 'validar horário', 34, 'data precisa de validação pública para confirmar demanda'


def _event_boost(target_date: date, events_by_date: dict[str, list[str]]) -> tuple[int, str]:
    lines = events_by_date.get(target_date.isoformat(), [])
    if not lines:
        return 0, 'sem evento informado para esta data'
    text = ' | '.join(lines)
    key = normalize_key(text)
    boost = 18 + min(len(lines) * 6, 16)
    if any(word in key for word in ('festival', 'show', 'feriado', 'festa', 'carnaval', 'reveillon', 'lua cheia')):
        boost += 18
    return min(boost, 42), text


def generate_candidate_dates(*, days_ahead: int = 21, start: date | None = None) -> list[date]:
    start = start or date.today()
    return [start + timedelta(days=offset) for offset in range(0, max(1, int(days_ahead)))]


def forecast_demand_without_dates(
    *,
    platform_username: str,
    origin: str,
    destination: str,
    events_text: str = '',
    days_ahead: int = 21,
    ai_recommended_dates: Iterable[str] = (),
) -> list[DemandForecastRow]:
    user = platform_username.strip() or PRIMARY_ACCOUNT
    events_by_date = parse_event_agenda(events_text, destination)
    ai_dates = {str(item).strip() for item in ai_recommended_dates if str(item).strip()}
    rows: list[DemandForecastRow] = []
    for target_date in generate_candidate_dates(days_ahead=days_ahead):
        time_hint, score, day_reason = _base_time_and_score(target_date, origin, destination)
        boost, event_signal = _event_boost(target_date, events_by_date)
        score += boost
        if target_date.isoformat() in ai_dates:
            score += 18
            day_reason += ' + IA externa marcou esta data como promissora'
        score = max(0, min(score, 100))
        rows.append(
            DemandForecastRow(
                acao='VALIDAR BUSCA PÚBLICA',
                conta=user,
                origem=origin,
                destino_final=destination,
                intermediarias=_intermediarias(destination),
                data=target_date.isoformat(),
                horario=time_hint,
                preco_sugerido='após validação pública por data',
                risco_de_conflito='validar antes de publicar' if 'tres coracoes' in normalize_key(destination) else 'baixo',
                status_de_validacao=PREDICTION_STATUS,
                pontuacao=score,
                nivel=_level(score),
                sinais_de_passageiros='previsão inicial; clique para validar datas públicas',
                sinais_de_eventos=event_signal,
                motivo=day_reason,
                link_busca_publica=build_public_search_url(origin=origin, destination=destination, travel_date=target_date),
            )
        )
    rows.sort(key=lambda item: (-item.pontuacao, item.data))
    return rows


def auto_scan_best_predicted_dates(
    forecast_rows: Iterable[DemandForecastRow],
    *,
    limit: int = 7,
) -> list[BlaValidationResult]:
    results: list[BlaValidationResult] = []
    for row in list(forecast_rows)[: max(1, int(limit))]:
        if not row.link_busca_publica:
            continue
        results.append(fetch_public_search(row.link_busca_publica))
    return results


def merge_validated_ranking(
    validated_results: Iterable[BlaValidationResult],
    *,
    platform_username: str,
    destination: str,
    events_text: str = '',
) -> list[dict[str, object]]:
    ranking = rank_best_days(
        validated_results,
        platform_username=platform_username,
        target_destination=destination,
        events_text=events_text,
    )
    rows: list[dict[str, object]] = []
    for item in ranking:
        row = item.to_dict()
        if row.get('status de validação') != VALIDATION_OK:
            row['status de validação'] = STRICT_NOT_CONFIRMED
        rows.append(row)
    return rows


__all__ = [
    'DemandForecastRow',
    'PREDICTION_STATUS',
    'auto_scan_best_predicted_dates',
    'forecast_demand_without_dates',
    'generate_candidate_dates',
    'merge_validated_ranking',
]
