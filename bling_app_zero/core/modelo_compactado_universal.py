from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePosixPath
import zipfile

PLANILHAS_ACEITAS = {'.csv', '.xlsx', '.xlsm'}


@dataclass(frozen=True)
class ModeloResolvido:
    nome_original: str
    nome_planilha: str
    conteudo: bytes
    extensao: str
    origem_compactada: bool = False
    caminho_interno: str = ''


def extensao(nome: str | None) -> str:
    return Path(str(nome or '')).suffix.lower()


def nome_interno(caminho: str) -> str:
    return PurePosixPath(str(caminho or '')).name or 'modelo.csv'


def escolher_planilha(caminhos: list[str]) -> str:
    def ordem(caminho: str) -> tuple[int, int, str]:
        texto = str(caminho or '').lower()
        arquivo_sistema = texto.startswith('__macosx/') or '/__macosx/' in texto or PurePosixPath(texto).name.startswith('.')
        tipo = {'.csv': 0, '.xlsx': 1, '.xlsm': 2}.get(extensao(texto), 9)
        return (50 if arquivo_sistema else 0) + tipo, len(texto), texto

    return sorted(caminhos, key=ordem)[0]


def resolver_modelo(nome: str | None, conteudo: bytes | bytearray | None) -> ModeloResolvido:
    nome_original = str(nome or '').strip()
    dados = bytes(conteudo or b'')
    if not nome_original or not dados:
        raise ValueError('Modelo ausente na sessão.')

    ext = extensao(nome_original)
    if ext in PLANILHAS_ACEITAS:
        return ModeloResolvido(nome_original, nome_original, dados, ext)

    if ext != '.zip':
        raise ValueError('Formato do modelo não aceito para download fiel.')

    with zipfile.ZipFile(BytesIO(dados)) as pacote:
        candidatos = [info.filename for info in pacote.infolist() if not info.is_dir() and extensao(info.filename) in PLANILHAS_ACEITAS]
        if not candidatos:
            raise ValueError('O arquivo compactado não contém CSV, XLSX ou XLSM.')
        caminho = escolher_planilha(candidatos)
        nome_real = nome_interno(caminho)
        dados_reais = pacote.read(caminho)
        if not dados_reais:
            raise ValueError('A planilha interna está vazia.')
        return ModeloResolvido(nome_original, nome_real, bytes(dados_reais), extensao(nome_real), True, caminho)


__all__ = ['PLANILHAS_ACEITAS', 'ModeloResolvido', 'resolver_modelo']
