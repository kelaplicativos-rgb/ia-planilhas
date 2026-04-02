from core.logger import log
from core.reader.csv_reader import ler_csv
from core.reader.excel_reader import ler_excel


def ler_planilha(file):
    try:
        nome = (file.name or "").lower()

        if nome.endswith(".csv"):
            return ler_csv(file)

        if nome.endswith(".xlsx") or nome.endswith(".xls"):
            return ler_excel(file)

        log(f"Formato não suportado: {getattr(file, 'name', 'desconhecido')}")
        return None

    except Exception as e:
        log(f"ERRO leitura planilha arquivo={getattr(file, 'name', 'desconhecido')} detalhe={e}")
        return None
