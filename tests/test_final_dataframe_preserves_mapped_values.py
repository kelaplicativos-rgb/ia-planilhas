from __future__ import annotations

import unittest

import pandas as pd

from bling_app_zero.core.final_csv_exporter import sanitize_final_dataframe


class TestFinalDataframePreservesMappedValues(unittest.TestCase):
    def test_legacy_protections_do_not_override_mapping(self) -> None:
        source = pd.DataFrame(
            {
                'GTIN/EAN': ['123'],
                'Imagens': ['img1,img2'],
                'Código': ['', ''][:1],
                'Código alternativo': ['ABC'],
            }
        )

        result = sanitize_final_dataframe(
            source,
            contract_columns=list(source.columns),
            run_download_features=True,
        )

        self.assertEqual(result.to_dict(orient='records'), source.to_dict(orient='records'))


if __name__ == '__main__':
    unittest.main()
