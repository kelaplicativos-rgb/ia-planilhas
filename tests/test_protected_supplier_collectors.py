from __future__ import annotations

import json
import unittest
import zipfile
from io import BytesIO

from bling_app_zero.core.protected_supplier_collectors import build_collector_zip, build_provider_config


class TestProtectedSupplierCollectors(unittest.TestCase):
    def test_builds_oba_collector_package(self) -> None:
        data = build_collector_zip('obaobamix', pages=25, capture_format='mhtml')
        self.assertGreater(len(data), 1000)
        with zipfile.ZipFile(BytesIO(data)) as zf:
            names = set(zf.namelist())
            self.assertIn('coletor_fornecedor_protegido.py', names)
            self.assertIn('RUN_COLETOR.bat', names)
            self.assertIn('provider_config.json', names)
            config = json.loads(zf.read('provider_config.json').decode('utf-8'))
        self.assertEqual(config['provider_key'], 'obaobamix')
        self.assertEqual(config['pages'], 25)
        self.assertEqual(config['format'], 'mhtml')
        self.assertIn('/admin/products', config['start_url'])

    def test_generated_script_uses_playwright_keyword_arg(self) -> None:
        data = build_collector_zip('obaobamix', pages=25, capture_format='mhtml')
        with zipfile.ZipFile(BytesIO(data)) as zf:
            script = zf.read('coletor_fornecedor_protegido.py').decode('utf-8')
        self.assertIn('arg=page_index', script)
        self.assertNotIn('''page.wait_for_function(
        """(pageIndex) => {
            if (!(window.jQuery && window.jQuery.fn && window.jQuery.fn.dataTable)) return false;
            const tables = window.jQuery.fn.dataTable.tables();
            if (!tables.length) return false;
            const dt = window.jQuery(tables[0]).DataTable();
            const info = dt.page.info();
            const processing = document.querySelector('.dataTables_processing');
            const isProcessing = processing && getComputedStyle(processing).display !== 'none';
            return info.page === pageIndex && !isProcessing;
        }""",
        page_index,
        timeout=90000,
    )''', script)

    def test_generic_provider_accepts_custom_url(self) -> None:
        config = build_provider_config(
            'datatables_generic',
            start_url='https://fornecedor.exemplo/admin/products',
            pages=9,
            capture_format='both',
        )
        self.assertEqual(config['provider_key'], 'datatables_generic')
        self.assertEqual(config['pages'], 9)
        self.assertEqual(config['format'], 'both')
        self.assertEqual(config['start_url'], 'https://fornecedor.exemplo/admin/products')


if __name__ == '__main__':
    unittest.main()
