from __future__ import annotations

from io import BytesIO
from datetime import datetime
import zipfile


def gerar_nome_arquivo(prefixo: str, extensao: str) -> str:
    """
    Gera nome de arquivo com data e hora.

    Exemplo:
    estoque_20260403_213500.xlsx
    """
    agora = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefixo}_{agora}.{extensao}"


def preparar_download_excel(bytes_io: BytesIO, nome_arquivo: str) -> dict:
    """
    Prepara estrutura para download no Streamlit.
    """
    return {
        "data": bytes_io.getvalue(),
        "file_name": nome_arquivo,
        "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    }


def criar_zip(arquivos: dict[str, BytesIO]) -> BytesIO:
    """
    Cria um ZIP em memória com múltiplos arquivos.

    Parâmetros:
        arquivos: dict no formato:
            {
                "nome.xlsx": BytesIO,
                "log.txt": BytesIO
            }

    Retorno:
        BytesIO (zip pronto para download)
    """
    zip_buffer = BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for nome, conteudo in arquivos.items():
            zip_file.writestr(nome, conteudo.getvalue())

    zip_buffer.seek(0)
    return zip_buffer


def preparar_download_zip(bytes_io: BytesIO, nome_arquivo: str) -> dict:
    """
    Prepara download de arquivo ZIP no Streamlit.
    """
    return {
        "data": bytes_io.getvalue(),
        "file_name": nome_arquivo,
        "mime": "application/zip"
    }


def criar_log_txt(linhas: list[str]) -> BytesIO:
    """
    Cria arquivo de log (.txt) em memória.
    """
    conteudo = "\n".join(linhas)
    buffer = BytesIO()
    buffer.write(conteudo.encode("utf-8"))
    buffer.seek(0)
    return buffer
