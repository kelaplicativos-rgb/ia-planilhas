from io import BytesIO

import pandas as pd


def df_to_excel_bytes(df: pd.DataFrame, sheet_name: str = "dados") -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=(sheet_name[:31] or "dados"))
    output.seek(0)
    return output.getvalue()
