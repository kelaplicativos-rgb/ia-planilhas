from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from bs4 import BeautifulSoup


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())


def detect_tables_from_html(html: str) -> list[dict[str, Any]]:
    """Detecta tabelas HTML no estilo Instant Data Scraper."""
    soup = BeautifulSoup(html or "", "html.parser")
    results: list[dict[str, Any]] = []

    for table_index, table in enumerate(soup.find_all("table")):
        header_cells = table.find_all("th")
        headers = [_clean(cell.get_text(" ")) for cell in header_cells if _clean(cell.get_text(" "))]

        rows: list[dict[str, str]] = []
        for tr in table.find_all("tr"):
            cells = tr.find_all(["td", "th"])
            values = [_clean(cell.get_text(" ")) for cell in cells]
            if not values or all(not value for value in values):
                continue

            if not headers or len(headers) != len(values):
                headers = [f"Coluna {i + 1}" for i in range(len(values))]

            row = {headers[i]: values[i] if i < len(values) else "" for i in range(len(headers))}
            if any(row.values()):
                rows.append(row)

        if len(rows) >= 2:
            results.append(
                {
                    "source": "table",
                    "index": table_index,
                    "score": min(1.0, 0.55 + (len(rows) / 50)),
                    "rows": rows,
                }
            )

    return results


def flatten_detected_tables(blocks: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for block in blocks:
        for row in block.get("rows") or []:
            if isinstance(row, dict) and any(str(v).strip() for v in row.values()):
                rows.append(row)
    return rows
