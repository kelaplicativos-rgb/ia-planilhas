from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import date, datetime
from email import policy
from email.parser import BytesParser
from statistics import median
from typing import Iterable
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

CARPOOL_START_URL = 'https://www.blablacar.com.br/carpool'
SEARCH_BASE_URL = 'https://www.blablacar.com.br/search'
STRICT_NOT_CONFIRMED = 'não confirmado / busca pública por data não validada'
VALIDATION_OK = 'validado / busca pública por data validada'

PRIMARY_ACCOUNT = 'Ezequiel S'
SECONDARY_ACCOUNT = 'Barbosa'
OWN_DRIVER_NAMES = (PRIMARY_ACCOUNT, SECONDARY_ACCOUNT)
FORBIDDEN_IDENTIFIER_TOKENS = (
    '4.9',
    '4,9',
    'super driver',
    'embaixador',
    'expert',
)
IGNORED_DESTINATIONS = ('caxambu',)
CONFLICT_DESTINATION = 'tres coracoes'

_V9_OR_API_RE = re.compile(r'https?://[^\s"\'<>]+(?:v9|search-car-sharing|api)[^\s"\'<>]*', re.IGNORECASE)
_MULTISPACE_RE = re.compile(r'\s+')
_PRICE_NUMBER_RE = re.compile(r'(\d{1,4})(?:\s*,\s*(\d{2}))?')


@dataclass(frozen=True)
class BlaSearchContext:
    search_url: str = ''
    public_start_url: str = CARPOOL_START_URL
    origin: str = ''
    destination: str = ''
    date: str = ''
    seats: str = '1'
    from_place_id: str = ''
    to_place_id: str = ''
    search_origin: str = ''

    def is_complete(self) -> bool:
        return bool(self.search_url and self.origin and self.destination and self.date)


@dataclass(frozen=True)
class BlaTrip:
    departure_time: str = ''
    duration: str = ''
    departure_station: str = ''
    arrival_time: str = ''
    arrival_station: str = ''
    price_text: str = ''
    price_value: float | None = None
    scarcity: str = ''
    not_available: str = ''
    driver_name: str = ''
    rating: str = ''
    amenities: str = ''
    link: str = ''
    raw_text: str = ''

    @property
    def is_full(self) -> bool:
        return 'cheio' in normalize_key(self.not_available)

    @property
    def is_scarce(self) -> bool:
        return bool(self.scarcity.strip())

    @property
    def is_own_driver(self) -> bool:
        return is_own_driver_name(self.driver_name)


@dataclass(frozen=True)
class BlaValidationResult:
    context: BlaSearchContext
    trips: tuple[BlaTrip, ...]
    api_candidates: tuple[str, ...]
    status: str
    source: str
    message: str = ''

    @property
    def validated(self) -> bool:
        return self.status == VALIDATION_OK

    @property
    def own_trips(self) -> tuple[BlaTrip, ...]:
        return tuple(trip for trip in self.trips if trip.is_own_driver)


@dataclass(frozen=True)
class BlaRecommendation:
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

    def to_dict(self) -> dict[str, str]:
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
        }


def normalize_key(value: object) -> str:
    text = str(value or '').strip().lower()
    replacements = {
        'á': 'a',
        'à': 'a',
        'ã': 'a',
        'â': 'a',
        'ä': 'a',
        'é': 'e',
        'è': 'e',
        'ê': 'e',
        'ë': 'e',
        'í': 'i',
        'ì': 'i',
        'î': 'i',
        'ï': 'i',
        'ó': 'o',
        'ò': 'o',
        'õ': 'o',
        'ô': 'o',
        'ö': 'o',
        'ú': 'u',
        'ù': 'u',
        'û': 'u',
        'ü': 'u',
        'ç': 'c',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return _MULTISPACE_RE.sub(' ', text).strip()


def clean_text(value: object) -> str:
    return _MULTISPACE_RE.sub(' ', str(value or '').replace('\xa0', ' ')).strip()


def is_own_driver_name(driver_name: str) -> bool:
    key = normalize_key(driver_name)
    if not key:
        return False
    if any(token in key for token in FORBIDDEN_IDENTIFIER_TOKENS):
        return False
    return key in {normalize_key(name) for name in OWN_DRIVER_NAMES}


def detect_account(driver_name: str, default: str = PRIMARY_ACCOUNT) -> str:
    key = normalize_key(driver_name)
    for name in OWN_DRIVER_NAMES:
        if key == normalize_key(name):
            return name
    return default


def read_mhtml_html(raw: bytes) -> str:
    """Extrai o HTML principal de .mht/.mhtml salvo pelo navegador."""
    message = BytesParser(policy=policy.default).parsebytes(raw)
    html_parts: list[str] = []
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() != 'text/html':
                continue
            payload = part.get_payload(decode=True) or b''
            charset = part.get_content_charset() or 'utf-8'
            html_parts.append(payload.decode(charset, 'replace'))
    else:
        payload = message.get_payload(decode=True) or raw
        charset = message.get_content_charset() or 'utf-8'
        html_parts.append(payload.decode(charset, 'replace'))
    if html_parts:
        return max(html_parts, key=len)
    return raw.decode('utf-8', 'replace')


def extract_snapshot_search_url(raw: bytes) -> str:
    message = BytesParser(policy=policy.default).parsebytes(raw)
    value = message.get('Snapshot-Content-Location') or message.get('Content-Location') or ''
    if value:
        return clean_text(value)
    text = raw.decode('utf-8', 'replace')
    match = re.search(r'(?im)^Snapshot-Content-Location:\s*(.+)$', text)
    return clean_text(match.group(1)) if match else ''


def parse_search_context(search_url: str) -> BlaSearchContext:
    if not search_url:
        return BlaSearchContext()
    parsed = urlparse(search_url)
    params = parse_qs(parsed.query)

    def first(name: str, fallback: str = '') -> str:
        values = params.get(name) or []
        return clean_text(values[0] if values else fallback)

    return BlaSearchContext(
        search_url=search_url,
        origin=first('fn'),
        destination=first('tn'),
        date=first('db'),
        seats=first('seats', '1') or '1',
        from_place_id=first('from_place_id'),
        to_place_id=first('to_place_id'),
        search_origin=first('search_origin'),
    )


def build_public_search_url(
    *,
    origin: str,
    destination: str,
    travel_date: str | date,
    seats: int = 1,
    from_place_id: str = '',
    to_place_id: str = '',
    search_origin: str = 'SEARCH',
) -> str:
    if isinstance(travel_date, date):
        travel_date = travel_date.isoformat()
    params: dict[str, str | int] = {
        'fn': origin,
        'tn': destination,
        'db': str(travel_date),
        'seats': max(int(seats or 1), 1),
        'search_origin': search_origin or 'SEARCH',
    }
    if from_place_id:
        params['from_place_id'] = from_place_id
    if to_place_id:
        params['to_place_id'] = to_place_id
    params['p0[ac]'] = 'adult'
    return f'{SEARCH_BASE_URL}?{urlencode(params, doseq=False)}'


def extract_api_candidates(raw_or_html: bytes | str) -> tuple[str, ...]:
    text = raw_or_html.decode('utf-8', 'replace') if isinstance(raw_or_html, bytes) else raw_or_html
    decoded = text.replace('\\u002F', '/').replace('&amp;', '&')
    candidates: list[str] = []
    for match in _V9_OR_API_RE.finditer(decoded):
        url = match.group(0).rstrip('.,);]')
        if url not in candidates:
            candidates.append(url)
    return tuple(candidates[:20])


def _text_by_testid(parent: BeautifulSoup, testid: str) -> str:
    node = parent.select_one(f'[data-testid="{testid}"]')
    return clean_text(node.get_text(' ', strip=True)) if node else ''


def _absolute_blablacar_url(href: str) -> str:
    if not href:
        return ''
    return urljoin('https://www.blablacar.com.br', href)


def normalize_price(price_text: str) -> tuple[str, float | None]:
    text = clean_text(price_text)
    if not text:
        return '', None
    match = _PRICE_NUMBER_RE.search(text.replace('.', ''))
    if not match:
        return text, None
    reais = int(match.group(1))
    centavos = int(match.group(2) or 0)
    value = reais + centavos / 100
    return f'R$ {reais},{centavos:02d}', value


def parse_trip_cards_from_html(html: str) -> tuple[BlaTrip, ...]:
    soup = BeautifulSoup(html or '', 'html.parser')
    cards = soup.select('[data-testid="e2e-srp-card"]')
    trips: list[BlaTrip] = []
    for card in cards:
        price_text, price_value = normalize_price(_text_by_testid(card, 'e2e-tripcard-price-price-value'))
        link_node = card.find('a', href=True)
        amenities = []
        for testid in ('e2e-tripcard-amenities', 'e2e-trip-card-carrier-icon'):
            value = _text_by_testid(card, testid)
            if value:
                amenities.append(value)
        trip = BlaTrip(
            departure_time=_text_by_testid(card, 'e2e-itinerary-departure-time'),
            duration=_text_by_testid(card, 'e2e-itinerary-duration-time'),
            departure_station=_text_by_testid(card, 'e2e-itinerary-departure-station'),
            arrival_time=_text_by_testid(card, 'e2e-itinerary-arrival-time'),
            arrival_station=_text_by_testid(card, 'e2e-itinerary-arrival-station'),
            price_text=price_text,
            price_value=price_value,
            scarcity=_text_by_testid(card, 'ab-trip-card-scarcity'),
            not_available=_text_by_testid(card, 'e2e-trip-card-not-available'),
            driver_name=_text_by_testid(card, 'e2e-tripcard-driver-name'),
            rating=_text_by_testid(card, 'e2e-tripcard-rating'),
            amenities=' | '.join(amenities),
            link=_absolute_blablacar_url(link_node['href']) if link_node else '',
            raw_text=clean_text(card.get_text(' ', strip=True)),
        )
        trips.append(trip)
    return tuple(trips)


def parse_public_search_mhtml(raw: bytes, *, source: str = 'mhtml_upload') -> BlaValidationResult:
    search_url = extract_snapshot_search_url(raw)
    html = read_mhtml_html(raw)
    context = parse_search_context(search_url)
    trips = parse_trip_cards_from_html(html)
    raw_candidates = extract_api_candidates(raw)
    html_candidates = tuple(url for url in extract_api_candidates(html) if url not in raw_candidates)
    candidates = raw_candidates + html_candidates
    if context.is_complete() and trips:
        return BlaValidationResult(
            context=context,
            trips=trips,
            api_candidates=candidates,
            status=VALIDATION_OK,
            source=source,
            message=f'{len(trips)} viagem(ns) pública(s) extraída(s) da busca por data.',
        )
    return BlaValidationResult(
        context=context,
        trips=trips,
        api_candidates=candidates,
        status=STRICT_NOT_CONFIRMED,
        source=source,
        message='Não foi possível confirmar rota + data + cards públicos no arquivo.',
    )


def fetch_public_search(search_url: str, *, timeout: float = 20.0) -> BlaValidationResult:
    """Busca pública sem login. Se o HTML vier sem cards, mantém o bloqueio de recomendação."""
    headers = {
        'User-Agent': 'Mozilla/5.0 RotaCheiaPublicScan/1.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.6',
        'Referer': CARPOOL_START_URL,
    }
    try:
        response = httpx.get(search_url, headers=headers, follow_redirects=True, timeout=timeout)
        response.raise_for_status()
    except Exception as exc:
        return BlaValidationResult(
            context=parse_search_context(search_url),
            trips=(),
            api_candidates=(),
            status=STRICT_NOT_CONFIRMED,
            source='public_http_fetch',
            message=f'Falha ao acessar busca pública: {exc}',
        )
    html = response.text
    context = parse_search_context(str(response.url) or search_url)
    trips = parse_trip_cards_from_html(html)
    candidates = extract_api_candidates(html)
    if context.is_complete() and trips:
        return BlaValidationResult(
            context=context,
            trips=trips,
            api_candidates=candidates,
            status=VALIDATION_OK,
            source='public_http_fetch',
            message=f'{len(trips)} viagem(ns) pública(s) extraída(s) por HTTP.',
        )
    return BlaValidationResult(
        context=context,
        trips=trips,
        api_candidates=candidates,
        status=STRICT_NOT_CONFIRMED,
        source='public_http_fetch',
        message='Busca acessada, mas os cards públicos por data não foram confirmados no HTML.',
    )


def trip_to_dict(trip: BlaTrip) -> dict[str, object]:
    data = asdict(trip)
    data['cheio'] = trip.is_full
    data['esgotara_em_breve'] = trip.is_scarce
    data['minha_conta'] = trip.is_own_driver
    return data


def trips_to_table(trips: Iterable[BlaTrip]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for trip in trips:
        rows.append(
            {
                'horário': trip.departure_time,
                'origem': trip.departure_station,
                'chegada': trip.arrival_time,
                'destino': trip.arrival_station,
                'preço': trip.price_text,
                'motorista': trip.driver_name,
                'cheio': 'sim' if trip.is_full else 'não',
                'esgotará em breve': 'sim' if trip.is_scarce else 'não',
                'minha conta': 'sim' if trip.is_own_driver else 'não',
                'link': trip.link,
            }
        )
    return rows


def _prices_for_recommendation(trips: Iterable[BlaTrip]) -> list[float]:
    prices: list[float] = []
    for trip in trips:
        if trip.price_value is None:
            continue
        if any(ignored in normalize_key(trip.arrival_station) for ignored in IGNORED_DESTINATIONS):
            continue
        prices.append(float(trip.price_value))
    return prices


def suggested_price_text(trips: Iterable[BlaTrip], fallback: str = 'R$ 90,00') -> str:
    prices = _prices_for_recommendation(trips)
    if not prices:
        return fallback
    value = int(round(median(prices)))
    return f'R$ {value},00'


def _weekday_from_context(context: BlaSearchContext) -> int | None:
    try:
        return datetime.strptime(context.date, '%Y-%m-%d').date().weekday()
    except Exception:
        return None


def preferred_time_for_context(context: BlaSearchContext, trips: Iterable[BlaTrip]) -> str:
    origin_key = normalize_key(context.origin)
    destination_key = normalize_key(context.destination)
    weekday = _weekday_from_context(context)
    going_from_sp_to_mg = any(city in origin_key for city in ('santo andre', 'sao paulo')) and any(
        city in destination_key
        for city in (
            'minas gerais',
            'extrema',
            'pouso alegre',
            'tres coracoes',
            'varginha',
            'sao thome',
            'sao tome',
            'sobradinho',
            'cambuquira',
            'campanha',
        )
    )
    returning_to_sp = any(city in destination_key for city in ('santo andre', 'sao paulo'))
    if returning_to_sp:
        if weekday == 4:
            return 'manhã'
        if weekday == 6:
            return '11:00'
        return 'manhã'
    if going_from_sp_to_mg:
        if weekday == 3:
            return '17:30'
        if weekday == 4:
            return '20:30'
        if weekday == 5:
            has_pressure = any(trip.is_full or trip.is_scarce for trip in trips)
            return 'noite' if has_pressure else 'somente com evento/demanda'
    return 'validar melhor horário pela lista pública'


def _conflict_risk(account: str, final_destination: str, context: BlaSearchContext, result: BlaValidationResult) -> str:
    destination_key = normalize_key(final_destination or context.destination)
    if CONFLICT_DESTINATION not in destination_key:
        return 'baixo'
    other = SECONDARY_ACCOUNT if detect_account(account) == PRIMARY_ACCOUNT else PRIMARY_ACCOUNT
    other_on_same_day = any(
        detect_account(trip.driver_name) == other and CONFLICT_DESTINATION in normalize_key(trip.arrival_station)
        for trip in result.trips
    )
    if other_on_same_day:
        return f'ALTO: {other} já aparece em Três Corações nesta data.'
    return f'atenção: não publicar {other} para Três Corações no mesmo dia.'


def _intermediate_summary(context: BlaSearchContext, trip: BlaTrip | None = None) -> str:
    target = context.destination
    arrival = trip.arrival_station if trip else ''
    if trip and arrival and normalize_key(arrival) not in normalize_key(target):
        return f'alvo da busca: {target}; card público termina em {arrival}'
    if any(city in normalize_key(target) for city in ('sao tome', 'sao thome', 'sobradinho')):
        return 'Extrema / Pouso Alegre / Três Corações conforme demanda pública'
    if any(city in normalize_key(target) for city in ('varginha', 'cambuquira', 'campanha')):
        return 'Extrema / Pouso Alegre / Três Corações'
    return 'sem intermediárias obrigatórias'


def build_recommendations(result: BlaValidationResult, *, preferred_account: str = PRIMARY_ACCOUNT) -> list[BlaRecommendation]:
    context = result.context
    if not result.validated:
        return [
            BlaRecommendation(
                acao=STRICT_NOT_CONFIRMED,
                conta='',
                origem=context.origin,
                destino_final=context.destination,
                intermediarias='',
                data=context.date,
                horario='',
                preco_sugerido='',
                risco_de_conflito='indefinido',
                status_de_validacao=result.status,
            )
        ]

    own_trips = result.own_trips
    if own_trips:
        rows: list[BlaRecommendation] = []
        for trip in own_trips:
            account = detect_account(trip.driver_name, preferred_account)
            action = 'MANTER'
            if trip.is_full:
                action = 'MANTER / não duplicar'
            rows.append(
                BlaRecommendation(
                    acao=action,
                    conta=account,
                    origem=trip.departure_station or context.origin,
                    destino_final=trip.arrival_station or context.destination,
                    intermediarias=_intermediate_summary(context, trip),
                    data=context.date,
                    horario=trip.departure_time,
                    preco_sugerido=trip.price_text or suggested_price_text(result.trips),
                    risco_de_conflito=_conflict_risk(account, trip.arrival_station, context, result),
                    status_de_validacao=result.status,
                )
            )
        return rows

    preferred_time = preferred_time_for_context(context, result.trips)
    return [
        BlaRecommendation(
            acao='CRIAR / PUBLICAR',
            conta=preferred_account,
            origem=context.origin,
            destino_final=context.destination,
            intermediarias=_intermediate_summary(context, None),
            data=context.date,
            horario=preferred_time,
            preco_sugerido=suggested_price_text(result.trips),
            risco_de_conflito=_conflict_risk(preferred_account, context.destination, context, result),
            status_de_validacao=result.status,
        )
    ]


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
    'extract_api_candidates',
    'fetch_public_search',
    'parse_public_search_mhtml',
    'parse_search_context',
    'parse_trip_cards_from_html',
    'read_mhtml_html',
    'suggested_price_text',
    'trips_to_table',
]
