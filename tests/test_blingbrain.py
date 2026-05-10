from __future__ import annotations

import unittest

from bling_app_zero.ai_tools import build_blingbrain_response


class TestBlingBrain(unittest.TestCase):
    def test_descricao_vira_revisao_segura(self) -> None:
        response = build_blingbrain_response('revise as descrições antes do download final', etapa='preview', operacao='cadastro')

        self.assertEqual(response.action_type, 'descricao')
        self.assertIn('sem inventar', response.safety.lower())
        self.assertTrue(response.steps)

    def test_ncm_vira_sugestao_manual(self) -> None:
        response = build_blingbrain_response('quero que a IA procure NCMs', etapa='preview', operacao='cadastro')

        self.assertEqual(response.action_type, 'ncm')
        self.assertIn('revisão manual', response.title.lower())

    def test_gtin_fake_nao_e_aplicado_como_padrao(self) -> None:
        response = build_blingbrain_response('quero gerar gtin fake', etapa='download', operacao='cadastro')

        self.assertEqual(response.action_type, 'gtin')
        self.assertIn('não usar gtin fake', response.safety.lower())


if __name__ == '__main__':
    unittest.main()
