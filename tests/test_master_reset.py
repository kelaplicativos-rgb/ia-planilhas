from __future__ import annotations

import unittest

from bling_app_zero.ui.master_reset import clear_operation_state, should_clear_for_new_operation


class TestMasterReset(unittest.TestCase):
    def test_clears_previous_operation_data(self) -> None:
        state = {
            'df_final_universal': object(),
            'mapping_universal': {'A': 'B'},
            'home_modelo_estoque_df': object(),
            'home_pricing_config': {'enabled': True},
            'bling_wizard_step': 'download',
            'unrelated_setting': 'keep',
        }

        clear_operation_state(state)

        self.assertEqual(state, {'unrelated_setting': 'keep'})

    def test_preserves_bling_connection(self) -> None:
        state = {
            'bling_access_token': 'secret-token',
            'bling_refresh_token': 'secret-refresh',
            'df_final_cadastro': object(),
        }

        clear_operation_state(state)

        self.assertIn('bling_access_token', state)
        self.assertIn('bling_refresh_token', state)
        self.assertNotIn('df_final_cadastro', state)

    def test_clears_navigation_deduplication_after_reset(self) -> None:
        state = {
            'home_wizard_last_rerun_reason': 'origin_selected',
            'home_wizard_last_rerun_target': 'entrada',
            'home_wizard_scroll_target_step': 'download',
            'unrelated_setting': 'keep',
        }

        clear_operation_state(state)

        self.assertEqual(state, {'unrelated_setting': 'keep'})

    def test_recognizes_dynamic_mapping_and_upload_keys(self) -> None:
        self.assertTrue(should_clear_for_new_operation('mapping_universal_page_2'))
        self.assertTrue(should_clear_for_new_operation('destination_model_upload_bytes'))
        self.assertFalse(should_clear_for_new_operation('bling_oauth_access_token'))


if __name__ == '__main__':
    unittest.main()
