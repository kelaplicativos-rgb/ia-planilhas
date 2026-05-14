from __future__ import annotations

import streamlit as st

RESPONSIBLE_FILE = 'bling_app_zero/ui/html_capture_helper.py'

COPY_HTML_BOOKMARKLET = """javascript:(async()=>{try{const html='<!doctype html>\\n'+document.documentElement.outerHTML;await navigator.clipboard.writeText(html);alert('HTML da página copiado. Volte ao sistema e cole na Compatibilidade universal.');}catch(e){const html='<!doctype html>\\n'+document.documentElement.outerHTML;prompt('Copie o HTML abaixo e cole no sistema:',html);}})();"""

DOWNLOAD_HTML_BOOKMARKLET = """javascript:(()=>{const html='<!doctype html>\\n'+document.documentElement.outerHTML;const blob=new Blob([html],{type:'text/html;charset=utf-8'});const a=document.createElement('a');const host=(location.hostname||'fornecedor').replace(/[^a-z0-9.-]/gi,'_');a.href=URL.createObjectURL(blob);a.download='bling_fornecedor_'+host+'.html';document.body.appendChild(a);a.click();setTimeout(()=>{URL.revokeObjectURL(a.href);a.remove();},1000);})();"""


def _orange_info(message: str) -> None:
    st.markdown(
        f'<div style="background:#fff3e0;border:1px solid #ffcc80;border-left:6px solid #fb8c00;color:#5d3200;border-radius:12px;padding:12px 14px;margin:8px 0;font-size:0.95rem;">⚠️ {message}</div>',
        unsafe_allow_html=True,
    )


def render_html_capture_helper() -> None:
    st.markdown('###### Capturar HTML da página aberta')
    st.caption('Use quando o fornecedor não tem botão de exportar CSV/XLSX. Você abre a página de produtos logado, executa um dos códigos abaixo e traz o HTML para cá.')

    _orange_info(
        'O sistema não consegue buscar HTML autenticado sozinho porque a sessão está no seu navegador. Este capturador roda no navegador onde você já está logado e copia ou baixa o HTML da tela atual.'
    )

    tab_copy, tab_download = st.tabs(['Copiar HTML', 'Baixar arquivo HTML'])

    with tab_copy:
        st.markdown('**Opção 1 — copiar HTML da página**')
        st.caption('No navegador do fornecedor, cole este código na barra de endereço e execute. Depois volte aqui e cole no campo de tabela/HTML copiado.')
        st.code(COPY_HTML_BOOKMARKLET, language='javascript')
        st.caption('No celular, talvez o navegador remova a palavra javascript: ao colar. Confira se o código começa exatamente com javascript: antes de executar.')

    with tab_download:
        st.markdown('**Opção 2 — baixar arquivo .html**')
        st.caption('No navegador do fornecedor, cole este código na barra de endereço e execute. Ele tenta baixar um arquivo HTML para você enviar no campo de upload.')
        st.code(DOWNLOAD_HTML_BOOKMARKLET, language='javascript')
        st.caption('Alguns navegadores móveis bloqueiam download por código. Se bloquear, use a opção de copiar HTML.')

    st.markdown('**Passo a passo simples**')
    st.markdown(
        '1. Abra o fornecedor no navegador normal e faça login.\n'
        '2. Vá até a tela de produtos.\n'
        '3. Use um dos códigos acima na barra de endereço.\n'
        '4. Volte ao sistema.\n'
        '5. Cole o HTML ou envie o arquivo baixado.\n'
        '6. Clique em **Importar tabela para o fluxo**.'
    )


__all__ = ['render_html_capture_helper']
