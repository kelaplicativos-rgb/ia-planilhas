# bling_app_zero/core/instant_scraper/autonomous_agent.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

import pandas as pd

from .self_healing import auto_heal_dataframe, diagnosticar_dataframe


StrategyFn = Callable[[str], pd.DataFrame]


@dataclass
class AgentResult:
    dataframe: pd.DataFrame
    strategy: str
    score: int
    status: str


def _safe_df(df: object) -> pd.DataFrame:
    if isinstance(df, pd.DataFrame) and not df.empty:
        return df.copy().fillna("").reset_index(drop=True)
    return pd.DataFrame()


def _score_df(df: pd.DataFrame) -> int:
    diag = diagnosticar_dataframe(df)
    try:
        return int(diag.get("score", 0))
    except Exception:
        return 0


def _marcar_agente(df: pd.DataFrame, strategy: str, score: int) -> pd.DataFrame:
    base = _safe_df(df)
    if base.empty:
        return base
    base["agente_estrategia"] = strategy
    base["agente_score"] = str(int(score))
    base["agente_data"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return base


def run_autonomous_agent(url: str, strategies: dict[str, StrategyFn], min_score: int = 70) -> AgentResult:
    url = str(url or "").strip()
    if not url:
        return AgentResult(pd.DataFrame(), "none", 0, "url_vazia")

    best_df = pd.DataFrame()
    best_name = "none"
    best_score = 0

    for name, fn in strategies.items():
        try:
            df_raw = _safe_df(fn(url))
            if df_raw.empty:
                continue

            df_healed = auto_heal_dataframe(df_raw, url)
            score = _score_df(df_healed)

            if score > best_score or (score == best_score and len(df_healed) > len(best_df)):
                best_df = df_healed
                best_name = name
                best_score = score

            if best_score >= min_score:
                break
        except Exception:
            continue

    if best_df.empty:
        return AgentResult(pd.DataFrame(), best_name, best_score, "sem_resultado")

    status = "ok" if best_score >= min_score else "resultado_fraco"
    return AgentResult(_marcar_agente(best_df, best_name, best_score), best_name, best_score, status)
