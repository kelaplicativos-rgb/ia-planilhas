from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Any
import zipfile


def gerar_nome_arquivo(prefixo: str, extensao: str) -> str:
    """
    Gera nome de arquivo com data e hora.

    Exemplo:
    estoque_20260403_213500.xlsx
    """
    try:
        prefixo_limpo = str(prefixo or "arquivo").strip() or "arquivo"
        extensao_limpa = str(extensao or "").strip().lstrip(".") or "txt"
        agora = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{prefixo_limpo}_{agora}.{extensao_limpa}"
    except Exception:
        agora = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"arquivo_{agora}.txt"


def _to_bytes(conteudo: Any) -> bytes:
    """
    Converte BytesIO / bytes / str em bytes.
    """
    try:
        if conteudo is None:
            return b""

        if isinstance(conteudo, bytes):
            return conteudo

        if isinstance(conteudo, str):
            return conteudo.encode("utf-8")

        if isinstance(conteudo, BytesIO):
            try:
                conteudo.seek(0)
            except Exception:
                pass
            return conteudo.getvalue()

        if hasattr(conteudo, "getvalue"):
            valor = conteudo.getvalue()
            if isinstance(valor, bytes):
                return valor
            if isinstance(valor, str):
                return valor.encode("utf-8")

        if hasattr(conteudo, "read"):
            try:
                if hasattr(conteudo, "seek"):
                    conteudo.seek(0)
            except Exception:
                pass

            valor = conteudo.read()
            if isinstance(valor, bytes):
                return valor
            if isinstance(valor, str):
                return valor.encode("utf-8")

        return str(conteudo).encode("utf-8")
    except Exception:
        return b""


def preparar_download_excel(bytes_io: BytesIO | bytes, nome_arquivo: str) -> dict[str, Any]:
    """
    Prepara estrutura para download no Streamlit.
    """
    try:
        return {
            "data": _to_bytes(bytes_io),
            "file_name": str(nome_arquivo or "arquivo.xlsx"),
            "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }
    except Exception:
        return {
            "data": b"",
            "file_name": "arquivo.xlsx",
            "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }


def criar_zip(arquivos: dict[str, BytesIO | bytes | str]) -> BytesIO:
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

    try:
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for nome, conteudo in (arquivos or {}).items():
                nome_final = str(nome or "").strip()
                if not nome_final:
                    continue

                zip_file.writestr(nome_final, _to_bytes(conteudo))

        zip_buffer.seek(0)
        return zip_buffer
    except Exception:
        zip_buffer = BytesIO()
        zip_buffer.seek(0)
        return zip_buffer


def preparar_download_zip(bytes_io: BytesIO | bytes, nome_arquivo: str) -> dict[str, Any]:
    """
    Prepara download de arquivo ZIP no Streamlit.
    """
    try:
        return {
            "data": _to_bytes(bytes_io),
            "file_name": str(nome_arquivo or "arquivo.zip"),
            "mime": "application/zip",
        }
    except Exception:
        return {
            "data": b"",
            "file_name": "arquivo.zip",
            "mime": "application/zip",
        }


def criar_log_txt(linhas: list[str]) -> BytesIO:
    """
    Cria arquivo de log (.txt) em memória.
    """
    try:
        conteudo = "\n".join(str(linha) for linha in (linhas or []))
        buffer = BytesIO()
        buffer.write(conteudo.encode("utf-8"))
        buffer.seek(0)
        return buffer
    except Exception:
        buffer = BytesIO()
        buffer.write(b"")
        buffer.seek(0)
        return buffer


__all__ = [
    "gerar_nome_arquivo",
    "preparar_download_excel",
    "criar_zip",
    "preparar_download_zip",
    "criar_log_txt",
]
