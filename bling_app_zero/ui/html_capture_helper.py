from __future__ import annotations

import streamlit as st

RESPONSIBLE_FILE = 'bling_app_zero/ui/html_capture_helper.py'

COPY_HTML_BOOKMARKLET = """javascript:(async()=>{try{const html='<!doctype html>\\n'+document.documentElement.outerHTML;await navigator.clipboard.writeText(html);alert('HTML da página copiado. Volte ao sistema e cole na Compatibilidade universal.');}catch(e){const html='<!doctype html>\\n'+document.documentElement.outerHTML;prompt('Copie o HTML abaixo e cole no sistema:',html);}})();"""

DOWNLOAD_HTML_BOOKMARKLET = """javascript:(()=>{const html='<!doctype html>\\n'+document.documentElement.outerHTML;const blob=new Blob([html],{type:'text/html;charset=utf-8'});const a=document.createElement('a');const host=(location.hostname||'fornecedor').replace(/[^a-z0-9.-]/gi,'_');a.href=URL.createObjectURL(blob);a.download='bling_fornecedor_'+host+'.html';document.body.appendChild(a);a.click();setTimeout(()=>{URL.revokeObjectURL(a.href);a.remove();},1000);})();"""

MULTIPAGE_HTML_BOOKMARKLET = """javascript:(async()=>{const sleep=ms=>new Promise(r=>setTimeout(r,ms));const clean=s=>(s||'').replace(/\s+/g,' ').trim();const host=(location.hostname||'fornecedor').replace(/[^a-z0-9.-]/gi,'_');const maxPages=Math.max(1,parseInt(prompt('Quantas páginas no máximo devo tentar capturar?', '80')||'80',10));const waitMs=Math.max(500,parseInt(prompt('Tempo de espera entre páginas em milissegundos?', '1800')||'1800',10));const pages=[];const seen=new Set();function pageKey(){return location.href+'|'+clean(document.body.innerText).slice(0,900);}function capture(reason){window.scrollTo(0,document.body.scrollHeight);const key=pageKey();if(seen.has(key))return false;seen.add(key);pages.push({url:location.href,title:document.title,reason,html:document.documentElement.outerHTML,text:document.body.innerText||''});return true;}function visible(el){if(!el)return false;const st=getComputedStyle(el);const r=el.getBoundingClientRect();return st.display!=='none'&&st.visibility!=='hidden'&&r.width>2&&r.height>2&&!el.disabled&&el.getAttribute('aria-disabled')!=='true';}function findNext(){const candidates=[...document.querySelectorAll('button,a,[role="button"],input[type="button"],input[type="submit"]')].filter(visible);const bad=/voltar|anterior|previous|prev|cancelar|excluir|remover|delete|logout|sair/i;const good=/carregar\s*mais|ver\s*mais|mostrar\s*mais|mais\s*produtos|pr[oó]xima|proxima|next|avan[cç]ar|\bmais\b|load\s*more|show\s*more/i;let picked=candidates.find(el=>good.test(clean(el.innerText||el.value||el.getAttribute('aria-label')||el.title||''))&&!bad.test(clean(el.innerText||el.value||el.getAttribute('aria-label')||el.title||'')));if(picked)return picked;const relNext=document.querySelector('a[rel="next"]');if(visible(relNext))return relNext;const pagers=candidates.filter(el=>/^\d+$/.test(clean(el.innerText||el.value||'')));if(pagers.length){const current=[...pagers].findIndex(el=>/active|selected|current/i.test(el.className+' '+el.getAttribute('aria-current')));if(current>=0&&pagers[current+1])return pagers[current+1];}return null;}function overlay(msg){let box=document.getElementById('bling-captura-html-status');if(!box){box=document.createElement('div');box.id='bling-captura-html-status';box.style.cssText='position:fixed;z-index:2147483647;left:12px;right:12px;bottom:12px;background:#fff3e0;border:2px solid #fb8c00;color:#4b2800;border-radius:12px;padding:12px;font:14px Arial,sans-serif;box-shadow:0 8px 30px rgba(0,0,0,.25);';document.body.appendChild(box);}box.textContent=msg;}capture('inicial');for(let i=1;i<maxPages;i++){overlay('BLING: capturando página '+(i)+' de até '+maxPages+'...');window.scrollTo(0,document.body.scrollHeight);await sleep(waitMs);capture('scroll');const next=findNext();if(!next){overlay('BLING: não encontrei botão próxima/carregar mais. Gerando arquivo...');break;}const before=pageKey();next.click();await sleep(waitMs);window.scrollTo(0,document.body.scrollHeight);await sleep(Math.min(waitMs,1600));capture('apos_clique');if(pageKey()===before){const next2=findNext();if(next2&&next2!==next){next2.click();await sleep(waitMs);capture('apos_segundo_clique');}else{break;}}}const combined='<!doctype html><html><head><meta charset="utf-8"><title>BLING captura multipágina '+host+'</title></head><body><h1>BLING captura multipágina</h1><p>Origem: '+location.origin+'</p><p>Total de páginas/blocos capturados: '+pages.length+'</p>'+pages.map((p,i)=>'<section class="bling-captured-page" data-url="'+p.url.replace(/"/g,'&quot;')+'"><h2>Página '+(i+1)+' - '+p.title.replace(/[<>]/g,'')+'</h2><p>URL: '+p.url+'</p>'+p.html+'</section>').join('\n')+'</body></html>';const blob=new Blob([combined],{type:'text/html;charset=utf-8'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='bling_site_inteiro_'+host+'_'+pages.length+'_paginas.html';document.body.appendChild(a);a.click();setTimeout(()=>{URL.revokeObjectURL(a.href);a.remove();},1000);overlay('BLING: arquivo gerado com '+pages.length+' página(s)/bloco(s). Envie este HTML no sistema.');alert('Captura finalizada com '+pages.length+' página(s)/bloco(s). Envie o HTML baixado no sistema.');})();"""


def _orange_info(message: str) -> None:
    st.markdown(
        f'<div style="background:#fff3e0;border:1px solid #ffcc80;border-left:6px solid #fb8c00;color:#5d3200;border-radius:12px;padding:12px 14px;margin:8px 0;font-size:0.95rem;">⚠️ {message}</div>',
        unsafe_allow_html=True,
    )


def render_html_capture_helper() -> None:
    st.markdown('###### Capturar HTML da página aberta')
    st.caption('Use quando o fornecedor não tem botão de exportar CSV/XLSX. Você abre a página de produtos logado, executa um dos códigos abaixo e traz o HTML para cá.')

    _orange_info(
        'O sistema não consegue buscar HTML autenticado sozinho porque a sessão está no seu navegador. Este capturador roda no navegador onde você já está logado e copia ou baixa o HTML da tela atual. A opção multipágina tenta clicar em Próxima/Carregar mais, mas não burla login, CAPTCHA ou bloqueios do fornecedor.'
    )

    tab_multi, tab_copy, tab_download = st.tabs(['Varrer páginas', 'Copiar HTML', 'Baixar página atual'])

    with tab_multi:
        st.markdown('**Opção principal — varrer páginas/lista inteira**')
        st.caption('Use na tela de produtos já logada. O código tenta rolar a página, capturar o HTML, clicar em “Próxima”, “Carregar mais” ou equivalente, juntar tudo e baixar um único arquivo HTML.')
        st.code(MULTIPAGE_HTML_BOOKMARKLET, language='javascript')
        st.markdown(
            '**Como usar:**\n'
            '1. Abra a página de produtos do fornecedor e faça login.\n'
            '2. Cole o código acima na barra de endereço.\n'
            '3. Confirme quantas páginas quer tentar capturar.\n'
            '4. Aguarde baixar o arquivo `bling_site_inteiro_...html`.\n'
            '5. Envie esse arquivo no campo **Enviar HTML/CSV/XLSX exportado do fornecedor**.'
        )
        _orange_info('Em celular, alguns navegadores removem `javascript:` ao colar. Confira se o código começa exatamente com `javascript:` antes de executar.')

    with tab_copy:
        st.markdown('**Opção 2 — copiar HTML da página atual**')
        st.caption('No navegador do fornecedor, cole este código na barra de endereço e execute. Depois volte aqui e cole no campo de tabela/HTML copiado.')
        st.code(COPY_HTML_BOOKMARKLET, language='javascript')

    with tab_download:
        st.markdown('**Opção 3 — baixar somente a página atual**')
        st.caption('No navegador do fornecedor, cole este código na barra de endereço e execute. Ele tenta baixar um arquivo HTML da tela atual.')
        st.code(DOWNLOAD_HTML_BOOKMARKLET, language='javascript')
        st.caption('Alguns navegadores móveis bloqueiam download por código. Se bloquear, use a opção de copiar HTML.')

    st.markdown('**Passo a passo simples**')
    st.markdown(
        '1. Abra o fornecedor no navegador normal e faça login.\n'
        '2. Vá até a tela de produtos.\n'
        '3. Use primeiro a aba **Varrer páginas**.\n'
        '4. Volte ao sistema.\n'
        '5. Envie o HTML baixado ou cole o HTML capturado.\n'
        '6. Clique em **Importar tabela para o fluxo**.'
    )


__all__ = ['render_html_capture_helper']
