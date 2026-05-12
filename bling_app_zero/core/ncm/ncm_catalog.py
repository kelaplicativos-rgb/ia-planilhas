from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NcmCatalogRule:
    ncm: str
    label: str
    keywords: tuple[str, ...]
    negative_keywords: tuple[str, ...] = ()
    base_score: int = 70


NCM_CATALOG_RULES: tuple[NcmCatalogRule, ...] = (
    NcmCatalogRule(
        ncm='85183000',
        label='Fones de ouvido, headphones e headsets',
        keywords=('fone', 'headphone', 'headset', 'earphone', 'auricular', 'bluetooth'),
        base_score=86,
    ),
    NcmCatalogRule(
        ncm='85176259',
        label='Aparelhos de comunicação/rede sem fio',
        keywords=('roteador', 'router', 'wifi', 'wi fi', 'repetidor', 'adaptador wireless'),
        base_score=82,
    ),
    NcmCatalogRule(
        ncm='85044010',
        label='Carregadores, fontes e adaptadores de energia',
        keywords=('carregador', 'charger', 'fonte', 'adaptador tomada', 'power adapter', 'usb c pd'),
        base_score=84,
    ),
    NcmCatalogRule(
        ncm='85076000',
        label='Baterias e acumuladores de íon de lítio',
        keywords=('power bank', 'powerbank', 'bateria externa', 'bateria portatil', 'bateria portátil', 'litio', 'lítio'),
        base_score=86,
    ),
    NcmCatalogRule(
        ncm='85444200',
        label='Cabos elétricos com conectores',
        keywords=('cabo usb', 'cabo hdmi', 'cabo tipo c', 'cabo type c', 'cabo lightning', 'cabo carregador'),
        base_score=84,
    ),
    NcmCatalogRule(
        ncm='85235190',
        label='Cartões de memória e mídias semicondutoras',
        keywords=('cartao memoria', 'cartão memória', 'micro sd', 'microsd', 'pen drive', 'pendrive'),
        base_score=82,
    ),
    NcmCatalogRule(
        ncm='85258929',
        label='Câmeras digitais/webcams semelhantes',
        keywords=('camera', 'câmera', 'webcam', 'camera ip', 'câmera ip'),
        base_score=78,
    ),
    NcmCatalogRule(
        ncm='95045000',
        label='Controles e acessórios para videogame',
        keywords=('controle gamer', 'joystick', 'gamepad', 'controle ps', 'controle xbox', 'videogame'),
        base_score=86,
    ),
    NcmCatalogRule(
        ncm='84716052',
        label='Teclados para computador',
        keywords=('teclado', 'keyboard', 'teclado gamer'),
        base_score=84,
    ),
    NcmCatalogRule(
        ncm='84716053',
        label='Mouses para computador',
        keywords=('mouse', 'mouse gamer', 'mouse sem fio'),
        base_score=84,
    ),
    NcmCatalogRule(
        ncm='85182100',
        label='Caixas de som/alto-falantes unitários',
        keywords=('caixa de som', 'speaker', 'alto falante', 'alto-falante', 'caixa bluetooth'),
        base_score=78,
    ),
    NcmCatalogRule(
        ncm='85181090',
        label='Microfones',
        keywords=('microfone', 'microphone', 'lapela'),
        base_score=84,
    ),
    NcmCatalogRule(
        ncm='39269090',
        label='Artigos diversos de plástico',
        keywords=('suporte plastico', 'suporte plástico', 'case', 'capa', 'capinha', 'pelicula', 'película'),
        base_score=68,
    ),
)


__all__ = ['NCM_CATALOG_RULES', 'NcmCatalogRule']
