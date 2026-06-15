from __future__ import annotations

import unittest

from bling_app_zero.ui.master_reset import (
    clear_operation_state,
    prepare_reuse_origin_state,
    reusable_origin_available,
    should_clear_for_new_operation,
)


class FakeDataFrame:
    def __init__(self, rows: int = 2) -> None:
        self.columns = ['codigo', 'descricao']
        self.rows = rows

    def __len__(self) -> int:
        return self.rows


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

    def test_reuse_origin_preserves_source_and_clears_previous_outputs(self) -> None:
        source = FakeDataFrame()
        state = {
            'cadastro_wizard_df_origem': source,
            'home_slim_flow_origin': 'arquivo',
            'home_modelo_cadastro_df': FakeDataFrame(),
            'mapping_universal': {'descricao': 'Nome'},
            'df_final_universal': FakeDataFrame(),
            'home_pricing_config': {'enabled': True},
            'bling_access_token': 'secret-token',
        }

        source_key, removed = prepare_reuse_origin_state(state)

        self.assertEqual(source_key, 'cadastro_wizard_df_origem')
        self.assertTrue(removed)
        self.assertIs(state['cadastro_wizard_df_origem'], source)
        self.assertEqual(state['home_slim_flow_origin'], 'arquivo')
        self.assertEqual(state['bling_wizard_step'], 'modelo')
        self.assertEqual(state['home_active_operation_v2'], 'wizard_cadastro_estoque')
        self.assertNotIn('home_modelo_cadastro_df', state)
        self.assertNotIn('mapping_universal', state)
        self.assertNotIn('df_final_universal', state)
        self.assertNotIn('home_pricing_config', state)
        self.assertEqual(state['bling_access_token'], 'secret-token')

    def test_reuse_origin_is_disabled_without_valid_source(self) -> None:
        state = {'df_final_universal': FakeDataFrame()}

        self.assertFalse(reusable_origin_available(state))
        source_key, removed = prepare_reuse_origin_state(state)

        self.assertEqual(source_key, '')
        self.assertEqual(removed, [])
        self.assertIn('df_final_universal', state)


if __name__ == '__main__':
    unittest.main()
