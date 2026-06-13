from __future__ import annotations

import unittest
from decimal import Decimal

from bling_app_zero.ui.easy_price_ui import _to_decimal


class TestEasyPriceUiDecimal(unittest.TestCase):
    def test_native_float_does_not_gain_extra_zero(self) -> None:
        self.assertEqual(_to_decimal(160.0), Decimal('160.0'))

    def test_brazilian_decimal_string(self) -> None:
        self.assertEqual(_to_decimal('160,00'), Decimal('160.00'))

    def test_brazilian_thousands_and_decimal_string(self) -> None:
        self.assertEqual(_to_decimal('R$ 1.234,56'), Decimal('1234.56'))


if __name__ == '__main__':
    unittest.main()
