from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd

from bling_app_zero.ui import mapping_dropdown_preview_runtime as dropdown_runtime
from bling_app_zero.ui import model_preserve_merge_runtime as preserve_runtime


class TestMappingPreserveToggle(unittest.TestCase):
    def setUp(self) -> None:
        self.session: dict[str, object] = {}
        self.dropdown_session = patch.object(dropdown_runtime.st, 'session_state', self.session)
        self.preserve_session = patch.object(preserve_runtime.st, 'session_state', self.session)
        self.dropdown_session.start()
        self.preserve_session.start()
        dropdown_runtime._CONTEXT['source'] = pd.DataFrame({'SKU origem': ['ABC'], 'Nome': ['Produto origem']})
        dropdown_runtime._CONTEXT['target'] = pd.DataFrame({'ID Produto': ['123'], 'Nome': ['Produto modelo']})

    def tearDown(self) -> None:
        dropdown_runtime._CONTEXT['source'] = None
        dropdown_runtime._CONTEXT['target'] = None
        self.dropdown_session.stop()
        self.preserve_session.stop()

    def test_toggle_off_hides_model_columns_from_dropdown(self) -> None:
        options, labels = dropdown_runtime._ranked_options(
            ['SKU origem', dropdown_runtime.EMPTY_OPTION, dropdown_runtime.WRITE_OPTION],
            {
                'SKU origem': '🟡 SKU origem',
                dropdown_runtime.EMPTY_OPTION: dropdown_runtime.EMPTY_OPTION,
                dropdown_runtime.WRITE_OPTION: dropdown_runtime.WRITE_OPTION,
            },
            'ID Produto',
            '',
        )

        self.assertFalse(dropdown_runtime._dual_enabled())
        self.assertNotIn('modelo::ID Produto', options)
        self.assertTrue(all(not str(option).startswith('modelo::') for option in options))
        self.assertTrue(all('Modelo anexado' not in str(label) for label in labels.values()))

    def test_toggle_on_shows_model_columns_from_dropdown(self) -> None:
        self.session[dropdown_runtime.MODEL_PRESERVE_TOGGLE_KEY] = True

        options, labels = dropdown_runtime._ranked_options(
            ['SKU origem', dropdown_runtime.EMPTY_OPTION, dropdown_runtime.WRITE_OPTION],
            {
                'SKU origem': '🟡 SKU origem',
                dropdown_runtime.EMPTY_OPTION: dropdown_runtime.EMPTY_OPTION,
                dropdown_runtime.WRITE_OPTION: dropdown_runtime.WRITE_OPTION,
            },
            'ID Produto',
            '',
        )

        self.assertTrue(dropdown_runtime._dual_enabled())
        self.assertIn('modelo::ID Produto', options)
        self.assertIn('Modelo anexado', labels['modelo::ID Produto'])

    def test_toggle_off_clears_stale_model_refs_and_unwraps_origin_refs(self) -> None:
        self.session['mapping'] = {
            'ID Produto': 'modelo::ID Produto',
            'Nome': 'origem::Nome',
            'Observação': '__mapeiaai_fixed_value__:OK',
        }

        changed = dropdown_runtime._clear_model_refs_when_toggle_disabled('mapping')

        self.assertEqual(changed, 2)
        self.assertEqual(self.session['mapping']['ID Produto'], '')
        self.assertEqual(self.session['mapping']['Nome'], 'Nome')
        self.assertEqual(self.session['mapping']['Observação'], '__mapeiaai_fixed_value__:OK')

    def test_output_preserve_ignores_model_choices_when_toggle_off(self) -> None:
        mapping = {'Nome': 'modelo::Nome'}
        self.assertEqual(preserve_runtime._model_copy_targets(mapping, ['Nome']), {})
        self.session[preserve_runtime.MODEL_PRESERVE_TOGGLE_KEY] = True
        self.assertEqual(preserve_runtime._model_copy_targets(mapping, ['Nome']), {'Nome': 'Nome'})

    def test_preserve_output_never_adds_source_columns(self) -> None:
        self.session[preserve_runtime.MODEL_PRESERVE_TOGGLE_KEY] = True
        df_model = pd.DataFrame({'SKU': ['ABC'], 'Nome': ['Produto modelo']})
        df_source = pd.DataFrame({'SKU': ['ABC'], 'Nome': ['Produto origem'], 'Arquivo origem': ['pagina.html'], 'Página origem': ['1']})
        output = preserve_runtime._merge_preserving_model(df_source, df_model, {'SKU': 'SKU', 'Nome': 'Nome'})

        self.assertEqual(list(output.columns), ['SKU', 'Nome'])
        self.assertNotIn('Arquivo origem', output.columns)
        self.assertNotIn('Página origem', output.columns)


if __name__ == '__main__':
    unittest.main()
