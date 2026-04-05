# bling_app_zero/core/ia_logs.py

import re


def analisar_log(log_texto: str) -> dict:
    """
    Analisa o log e identifica o tipo de erro
    """

    if "SyntaxError" in log_texto:

        if "was never closed" in log_texto:
            return {
                "tipo": "syntax_dict",
                "mensagem": "Dicionário não fechado",
                "solucao": "Fechar chaves }"
            }

        if "unterminated string literal" in log_texto:
            return {
                "tipo": "string",
                "mensagem": "String não fechada",
                "solucao": "Fechar aspas"
            }

    if "ImportError" in log_texto:
        return {
            "tipo": "import",
            "mensagem": "Import inválido",
            "solucao": "Função não existe ou nome errado"
        }

    if "ValueError" in log_texto and "Excel file format" in log_texto:
        return {
            "tipo": "excel",
            "mensagem": "Erro leitura Excel",
            "solucao": "Definir engine ou tipo de arquivo"
        }

    return {
        "tipo": "desconhecido",
        "mensagem": "Erro não identificado",
        "solucao": "Verificar manualmente"
    }


# =========================
# CORREÇÕES AUTOMÁTICAS
# =========================

def sugerir_correcao(tipo: str, codigo: str) -> str:

    if tipo == "syntax_dict":
        # tenta fechar dicionário automaticamente
        if "append({" in codigo and not codigo.strip().endswith("})"):
            return codigo + "\n})"

    if tipo == "string":
        # tenta fechar aspas
        if codigo.count('"') % 2 != 0:
            return codigo + '"'

    return codigo
