from __future__ import annotations

# ==========================================================
# EXCEL (BLINDADO)
# ==========================================================
try:
    from .excel import (
        baixar_logs_txt,
        df_to_excel_bytes,
        exportar_dataframe_para_excel,
        exportar_df_exato_para_excel_bytes,
        exportar_excel_bytes,
        gerar_zip_com_arquivos,
        gerar_zip_processamento,
        ler_planilha_excel,
        ler_planilha_segura,
        limpar_gtin_invalido,
        log_debug,
        validar_campos_obrigatorios,
    )
except Exception as e:
    # 🔒 Blindagem total — evita crash do app
    def _erro(*args, **kwargs):
        raise ImportError(f"Erro ao importar utils.excel: {e}")

    baixar_logs_txt = _erro
    df_to_excel_bytes = _erro
    exportar_dataframe_para_excel = _erro
    exportar_df_exato_para_excel_bytes = _erro
    exportar_excel_bytes = _erro
    gerar_zip_com_arquivos = _erro
    gerar_zip_processamento = _erro
    ler_planilha_excel = _erro
    ler_planilha_segura = _erro
    limpar_gtin_invalido = _erro
    log_debug = _erro
    validar_campos_obrigatorios = _erro


# ==========================================================
# NUMEROS
# ==========================================================
from .numeros import format_money, normalize_value, safe_float


# ==========================================================
# EXPORTS
# ==========================================================
__all__ = [
    "log_debug",
    "baixar_logs_txt",
    "limpar_gtin_invalido",
    "validar_campos_obrigatorios",
    "ler_planilha_segura",
    "ler_planilha_excel",
    "df_to_excel_bytes",
    "exportar_df_exato_para_excel_bytes",
    "exportar_dataframe_para_excel",
    "exportar_excel_bytes",
    "gerar_zip_com_arquivos",
    "gerar_zip_processamento",
    "normalize_value",
    "safe_float",
    "format_money",
]
