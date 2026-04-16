
import pandas as pd

def safe_df(df):
    return isinstance(df, pd.DataFrame) and not df.empty
