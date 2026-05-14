from __future__ import annotations

import html

import streamlit as st
import streamlit.components.v1 as components

RESPONSIBLE_FILE = 'bling_app_zero/ui/html_capture_helper.py'
DEFAULT_SUPPLIER_PRODUCTS_URL = 'https://app.obaobamix.com.br/admin/products'

COPY_HTML_BOOKMARKLET = """javascript:(async()=>{try{const html='<!doctype html>\\n'+document.documentElement.outerHTML;await navigator.clipboard.writeText(html);alert('HTML da página copiado. Volte ao sistema e cole na Compatibilidade universal.');}catch(e){const html='<!doctype html>\\n'+document.documentElement.outerHTML;prompt('Copie o HTML abaixo e cole no sistema:',html);}})();"""

DOWNLOAD_HTML_BOOKMARKLET = """javascript:(()=>{const html='<!doctype html>\\n'+document.documentElement.outerHTML;const blob=new Blob([html],{type:'text/html;charset=utf-8'});const a=document.createElement('a');const host=(location.hostname||'fornecedor').replace(/[^a-z0-9.-]/gi,'_');a.href=URL.createObjectURL(blob);a.download='bling_fornecedor_'+host+'.html';document.body.appendChild(a);a.click();setTimeout(()=>{URL.revokeObjectURL(a.href);a.remove();},1000);})();"""

MULTIPAGE_HTML_BOOKMARKLET = """javascript:(async()=>{const sleep=ms=>new Promise(r=>setTimeout(r,ms));const clean=s=>(s||'').replace(/\s+/g,' ').trim();const host=(location.hostname||'fornecedor').replace(/[^a-z0-9.-]/gi,'_');const maxPages=Math.max(1,parseInt(prompt('Quantas páginas no máximo devo tentar capturar?', '80')||'80',10));const waitMs=Math.max(500,parseInt(prompt('Tempo de espera entre páginas em milissegundos?', '1800')||'1800',10));const pages=[];const seen=new Set();function pageKey(){return location.href+'|'+clean(document.body.innerText).slice(0,900);}function capture(reason){window.scrollTo(0,document.body.scrollHeight);const key=pageKey();if(seen.has(key))return false;seen.add(key);pages.push({url:location.href,title:document.title,reason,html:document.documentElement.outerHTML,text:document.body.innerText||''});return true;}function visible(el){if(!el)return false;const st=getComputedStyle(el);const r=el.getBoundingClientRect();return st.display!=='none'&&st.visibility!=='hidden'&&r.width>2&&r.height>2&&!el.disabled&&el.getAttribute('aria-disabled')!=='true';}function findNext(){const candidates=[...document.querySelectorAll('button,a,[role="button"],input[type="button"],input[type="submit"]')].filter(visible);const bad=/voltar|anterior|previous|prev|cancelar|excluir|remover|delete|logout|sair/i;const good=/carregar\s*mais|ver\s*mais|mostrar\s*mais|mais\s*produtos|pr[oó]xima|proxima|next|avan[cç]ar|\bmais\b|load\s*more|show\s*more/i;let picked=candidates.find(el=>good.test(clean(el.innerText||el.value||el.getAttribute('aria-label')||el.title||''))&&!bad.test(clean(el.innerText||el.value||el.getAttribute('aria-label')||el.title||'')));if(picked)return picked;const relNext=document.querySelector('a[rel="next"]');if(visible(relNext))return relNext;const pagers=candidates.filter(el=>/^\d+$/.test(clean(el.innerText||el.value||'')));if(pagers.length){const current=[...pagers].findIndex(el=>/active|selected|current/i.test(el.className+' '+el.getAttribute('aria-current')));if(current>=0&&pagers[current+1])return pagers[current+1];}return null;}function overlay(msg){let box=document.getElementById('bling-captura-html-status');if(!box){box=document.createElement('div');box.id='bling-captura-html-status';box.style.cssText='position:fixed;z-index:2147483647;left:12px;right:12px;bottom:12px;background:#fff3e0;border:2px solid #fb8c00;color:#4b2800;border-radius:12px;padding:12px;font:14px Arial,sans-serif;box-shadow:0 8px 30px rgba(0,0,0,.25);';document.body.appendChild(box);}box.textContent=msg;}capture('inicial');for(let i=1;i<maxPages;i++){overlay('BLING: capturando página '+(i)+' de até '+maxPages+'...');window.scrollTo(0,document.body.scrollHeight);await sleep(waitMs);capture('scroll');const next=findNext();if(!next){overlay('BLING: não encontrei botão próxima/carregar mais. Gerando arquivo...');break;}const before=pageKey();next.click();await sleep(waitMs);window.scrollTo(0,document.body.scrollHeight);await sleep(Math.min(waitMs,1600));capture('apos_clique');if(pageKey()===before){const next2=findNext();if(next2&&next2!==next){next2.click();await sleep(waitMs);capture('apos_segundo_clique');}else{break;}}}const combined='<!doctype html><html><head><meta charset="utf-8"><title>BLING captura multipágina '+host+'</title></head><body><h1>BLING captura multipágina</h1><p>Origem: '+location.origin+'</p><p>Total de páginas/blocos capturados: '+pages.length+'</p>'+pages.map((p,i)=>'<section class="bling-captured-page" data-url="'+p.url.replace(/"/g,'&quot;')+'"><h2>Página '+(i+1)+' - '+p.title.replace(/[<>]/g,'')+'</h2><p>URL: '+p.url+'</p>'+p.html+'</section>').join('\n')+'</body></html>';const blob=new Blob([combined],{type:'text/html;charset=utf-8'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='bling_site_inteiro_'+host+'_'+pages.length+'_paginas.html';document.body.appendChild(a);a.click();setTimeout(()=>{URL.revokeObjectURL(a.href);a.remove();},1000);overlay('BLING: arquivo gerado com '+pages.length+' página(s)/bloco(s). Envie este HTML no sistema.');alert('Captura finalizada com '+pages.length+' página(s)/bloco(s). Envie o HTML baixado no sistema.');})();"""


def _orange_info(message: str) -> None:
    st.markdown(
        f'<div style="background:#fff3e0;border:1px solid #ffcc80;border-left:6px solid #fb8c00;color:#5d3200;border-radius:12px;padding:12px 14px;margin:8px 0;font-size:0.95rem;">⚠️ {message}</div>',
        unsafe_allow_html=True,
    )


def _copy_button(label: str, code: str, key: str) -> None:
    safe_code = html.escape(code, quote=True)
    safe_label = html.escape(label, quote=True)
    components.html(
        f'''
        <div style="margin:8px 0 12px 0;font-family:Arial,sans-serif;">
          <button id="btn-{key}" style="width:100%;border:0;border-radius:10px;background:#111827;color:white;padding:12px 14px;font-weight:700;font-size:14px;cursor:pointer;">📋 {safe_label}</button>
          <div id="msg-{key}" style="font-size:12px;color:#475569;margin-top:6px;"></div>
        </div>
        <script>
          const btn = document.getElementById('btn-{key}');
          const msg = document.getElementById('msg-{key}');
          const encoded = `{safe_code}`;
          btn.addEventListener('click', async () => {{
            const decoded = new DOMParser().parseFromString(encoded, 'text/html').documentElement.textContent;
            try {{
              await navigator.clipboard.writeText(decoded);
              msg.textContent = 'Código copiado. Agora volte na aba do fornecedor, cole na barra de endereço e execute.';
            }} catch (e) {{
              msg.textContent = 'Não consegui copiar automaticamente. Selecione o código abaixo e copie manualmente.';
            }}
          }});
        </script>
        ''',
        height=78,
    )


def _render_open_supplier(supplier_url: str) -> None:
    st.markdown('**1. Abrir fornecedor**')
    st.caption('Clique para abrir a tela de produtos. Faça login e resolva CAPTCHA se aparecer.')
    st.link_button('🔗 Abrir fornecedor / produtos', supplier_url, use_container_width=True)


def render_html_capture_helper() -> None:
    st.markdown('###### Capturar HTML da página aberta')
    st.caption('Abra o fornecedor, faça login, copie o código capturador e execute na barra de endereço da aba do fornecedor.')

    supplier_url = st.text_input(
        'Link do fornecedor/produtos',
        value=str(st.session_state.get('html_capture_supplier_url') or DEFAULT_SUPPLIER_PRODUCTS_URL),
        key='html_capture_supplier_url',
        help='Este botão só abre o fornecedor. O código capturador precisa ser executado na aba do fornecedor já logada.',
    )
    _render_open_supplier(supplier_url)

    _orange_info(
        'Fluxo: clique em Abrir fornecedor, faça login, volte aqui, copie o código capturador, retorne na aba do fornecedor, cole na barra de endereço e aperte Enter. O código roda na sua sessão logada.'
    )

    tab_multi, tab_copy, tab_download = st.tabs(['Varrer páginas', 'Copiar HTML', 'Baixar página atual'])

    with tab_multi:
        st.markdown('**2. Copiar código para varrer páginas/lista inteira**')
        st.caption('Tenta rolar, capturar, clicar em Próxima/Carregar mais e baixar um HTML único com todos os blocos encontrados.')
        _copy_button('Copiar código de varredura multipágina', MULTIPAGE_HTML_BOOKMARKLET, 'copy_multipage')
        st.code(MULTIPAGE_HTML_BOOKMARKLET, language='javascript')
        st.markdown(
            '**Depois de copiar:**\n'
            '1. Volte para a aba do fornecedor já logada.\n'
            '2. Toque na barra de endereço onde aparece o link.\n'
            '3. Apague o link.\n'
            '4. Cole o código.\n'
            '5. Confira se começa com `javascript:`.\n'
            '6. Aperte Enter/Ir.\n'
            '7. Envie o arquivo HTML baixado no sistema.'
        )

    with tab_copy:
        st.markdown('**2. Copiar código para copiar HTML da página atual**')
        _copy_button('Copiar código para copiar HTML', COPY_HTML_BOOKMARKLET, 'copy_current')
        st.code(COPY_HTML_BOOKMARKLET, language='javascript')

    with tab_download:
        st.markdown('**2. Copiar código para baixar somente a página atual**')
        _copy_button('Copiar código para baixar HTML', DOWNLOAD_HTML_BOOKMARKLET, 'download_current')
        st.code(DOWNLOAD_HTML_BOOKMARKLET, language='javascript')

    _orange_info('No celular, alguns navegadores removem `javascript:` ao colar. Se acontecer, digite manualmente `javascript:` no começo antes de apertar Enter.')


__all__ = ['render_html_capture_helper']
