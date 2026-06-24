from __future__ import annotations

from typing import Any

import pandas as pd

RESPONSIBLE_FILE = 'bling_app_zero/ui/universal_price_calculator_patch.py'


def _audit(event: str, *, status: str = 'OK', details: dict[str, Any] | None = None) -> None:
    try:
        from bling_app_zero.core.audit import add_audit_event
        add_audit_event(event, area='UNIVERSAL', status=status, details={**(details or {}), 'responsible_file': RESPONSIBLE_FILE})
    except Exception:
        pass


def _install_mapping_locked_fields() -> None:
    try:
        from bling_app_zero.ui.mapping_locked_fields_runtime import install
        install()
        _audit('universal_price_runtime_mapping_locked_fields_loaded', details={'locked_fields_runtime': True})
    except Exception as exc:
        _audit('universal_price_runtime_mapping_locked_fields_failed', status='AVISO', details={'error': str(exc)[:220]})


def _store_priced_source(st, universal_source_key: str, df: pd.DataFrame) -> None:
    clean = df.copy().fillna('')
    for key in (universal_source_key, 'df_origem_unificada', 'cadastro_wizard_df_para_mapear', 'df_origem_cadastro_precificada'):
        st.session_state[key] = clean.copy().fillna('')
    try:
        from bling_app_zero.ui.universal_wizard_state import UNIVERSAL_ORIGEM_PRICED_KEY
        st.session_state[UNIVERSAL_ORIGEM_PRICED_KEY] = clean.copy().fillna('')
    except Exception:
        pass


def _promo_columns(source: pd.DataFrame, model: pd.DataFrame | None) -> list[str]:
    detected: list[str] = []
    try:
        from bling_app_zero.core.product_pricing_center import promotional_price_columns
        for frame in (source, model):
            if isinstance(frame, pd.DataFrame):
                for column in promotional_price_columns(frame.columns):
                    if column not in detected:
                        detected.append(column)
    except Exception:
        pass
    return detected


def _render_preview(st, df: pd.DataFrame, selected_cost_column: str, promo_columns: list[str]) -> None:
    columns: list[str] = []
    for column in (selected_cost_column, 'Preço de venda', 'Preco', 'Preço', 'Preço promocional', 'Preco Promocional', *promo_columns):
        if column and column in df.columns and column not in columns:
            columns.append(column)
    if not columns:
        return
    preview = df.loc[:, columns].head(20).copy().fillna('')
    price_columns = [column for column in columns if column != selected_cost_column]
    st.markdown('##### Resultado ao vivo')
    st.success('Calculadora oficial aplicada: preço normal e promocional seguirão para o mapeamento.')
    try:
        styled = preview.style.set_properties(
            subset=price_columns,
            **{'background-color': '#dcfce7', 'color': '#166534', 'font-weight': '700'},
        )
        st.dataframe(styled, use_container_width=True, hide_index=True, height=min(520, 72 + (len(preview) * 35)))
    except Exception:
        st.dataframe(preview, use_container_width=True, hide_index=True)


def install() -> None:
    _install_mapping_locked_fields()
    try:
        from bling_app_zero.ui import universal_flow
    except Exception as exc:
        _audit('universal_price_calculator_patch_import_failed', status='AVISO', details={'error': str(exc)[:220]})
        return

    if getattr(universal_flow, '_mapeiaai_universal_price_official_patched', False):
        return

    st = universal_flow.st
    universal_source_key = getattr(universal_flow, 'UNIVERSAL_SOURCE_KEY', 'mapeiaai_universal_source_df')

    def _render_price_group_official(source: pd.DataFrame, model: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
        st.markdown('### 3. Calculadora de preços')
        enabled = st.toggle('Preço / cálculo marketplace', value=False, key='mapeiaai_universal_toggle_price')
        if not enabled:
            st.caption('Desligado. O mapeamento usará os preços originais da origem, se existirem.')
            try:
                from bling_app_zero.ui.cadastro_pricing import clear_cadastro_pricing_state
                clear_cadastro_pricing_state()
            except Exception:
                pass
            universal_flow._audit('mapear_planilha_grupo_preco_toggle', enabled=False, grouped_toggle=True, official_calculator=True)
            return source, False

        universal_flow._audit('mapear_planilha_grupo_preco_toggle', enabled=True, grouped_toggle=True, official_calculator=True)
        st.caption('Calculadora oficial: calcula preço normal e preço promocional linha a linha antes do mapeamento.')
        try:
            from bling_app_zero.ui.home_pricing_config import render_home_pricing_config_form, set_home_pricing_config
            from bling_app_zero.ui.cadastro_pricing import apply_cadastro_pricing
            config = render_home_pricing_config_form(source_df=source)
            config = set_home_pricing_config(config)
            priced = apply_cadastro_pricing(source, channel='universal_price_step')
        except Exception as exc:
            st.warning(f'Calculadora oficial não aplicada: {exc}')
            universal_flow._audit('mapear_planilha_calculadora_oficial_erro', enabled=True, error=str(exc)[:220])
            return source, True

        if not isinstance(priced, pd.DataFrame) or priced.empty:
            return source, True

        if bool(st.session_state.get('cadastro_preco_calculado_ativo', False)) or bool(config.get('enabled', False)):
            _store_priced_source(st, universal_source_key, priced)
            selected_cost_column = str(st.session_state.get('global_price_source_cost_column') or st.session_state.get('price_calculator_source_cost_column') or '').strip()
            promo_columns = _promo_columns(priced, model)
            _render_preview(st, priced, selected_cost_column, promo_columns)
            st.session_state['flow_spine_pricing_applied'] = True
            universal_flow._audit('mapear_planilha_calculadora_oficial_aplicada', rows=int(len(priced)), columns=int(len(priced.columns)), selected_cost_column=selected_cost_column, promo_columns=promo_columns, official_calculator=True)
            return priced, True

        st.info('Preencha e aplique a calculadora para recalcular os preços. Enquanto isso, a origem original fica preservada.')
        st.session_state['flow_spine_pricing_applied'] = False
        return source, True

    universal_flow._render_price_group = _render_price_group_official
    universal_flow._mapeiaai_universal_price_official_patched = True
    _audit('universal_price_calculator_official_installed', details={'replaces': 'render_shared_calculator'})


__all__ = ['install']
