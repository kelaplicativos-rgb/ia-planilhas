import pandas as pd

from bling_app_zero.core.final_output_engine import build_final_output
from bling_app_zero.core.critical_empty_fields_guard import strip_critical_empty_mappings


def test_strip_critical_empty_mappings_remove_tags_e_codigo_pai():
    mapping, report = strip_critical_empty_mappings({
        'Código': 'SKU',
        'Tags': 'Tags',
        'Código Pai': 'Código Pai',
    })

    assert mapping['Código'] == 'SKU'
    assert mapping['Tags'] == ''
    assert mapping['Código Pai'] == ''
    assert len(report) == 2


def test_download_final_limpa_tags_e_codigo_pai_mesmo_se_mapeados():
    source = pd.DataFrame([
        {'SKU': 'ABC-1', 'Tags': 'tag-invalida', 'Código Pai': 'ABC-1'},
        {'SKU': 'ABC-2', 'Tags': 'outra-tag', 'Código Pai': 'ABC-2'},
    ])
    model = pd.DataFrame(columns=['Código', 'Tags', 'Código Pai'])
    mapping = {
        'Código': 'SKU',
        'Tags': 'Tags',
        'Código Pai': 'Código Pai',
    }

    result = build_final_output(source, model, mapping, run_smart_features=False)

    assert result.state.result.ok
    assert result.output is not None
    assert result.output['Código'].tolist() == ['ABC-1', 'ABC-2']
    assert result.output['Tags'].tolist() == ['', '']
    assert result.output['Código Pai'].tolist() == ['', '']
    assert result.smart_rules_report is not None
    assert 'critical_empty_fields' in result.smart_rules_report
