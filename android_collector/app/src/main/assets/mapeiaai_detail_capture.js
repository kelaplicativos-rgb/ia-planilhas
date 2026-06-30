window.MapeiaAIDetailCapture = window.MapeiaAIDetailCapture || {};
window.MapeiaAIDetailCapture.clean = function (value) {
    return String(value == null ? '' : value).replace(/\s+/g, ' ').trim();
};
window.MapeiaAIDetailCapture.htmlToText = function (value) {
    return String(value == null ? '' : value)
        .replace(/&nbsp;/g, ' ')
        .replace(/&quot;/g, '"')
        .replace(/&#34;/g, '"')
        .replace(/&#39;/g, "'")
        .replace(/&amp;/g, '&')
        .replace(/&lt;/g, '<')
        .replace(/&gt;/g, '>')
        .replace(/<\s*br\s*\/?\s*>/gi, '\n')
        .replace(/<\s*\/p\s*>/gi, '\n')
        .replace(/<\s*\/li\s*>/gi, '\n')
        .replace(/<\s*li[^>]*>/gi, '- ')
        .replace(/<\s*\/h[1-6]\s*>/gi, '\n')
        .replace(/<[^>]*>/g, ' ')
        .replace(/[ \t]+/g, ' ')
        .replace(/\n\s+/g, '\n')
        .replace(/\n{3,}/g, '\n\n')
        .trim();
};
window.MapeiaAIDetailCapture.normalize = function (value) {
    return this.clean(value).toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
};
window.MapeiaAIDetailCapture.digits = function (value) {
    return this.clean(value).replace(/\D+/g, '');
};
window.MapeiaAIDetailCapture.validGtin = function (value) {
    var d = this.digits(value);
    if (!/^(\d{8}|\d{12}|\d{13}|\d{14})$/.test(d)) return '';
    if (/^(\d)\1+$/.test(d)) return '';
    var total = 0;
    var body = d.slice(0, -1).split('').reverse();
    for (var i = 0; i < body.length; i++) total += parseInt(body[i], 10) * (i % 2 === 0 ? 3 : 1);
    var expected = (10 - (total % 10)) % 10;
    return expected === parseInt(d.slice(-1), 10) ? d : '';
};
window.MapeiaAIDetailCapture.firstValidGtin = function (values) {
    for (var i = 0; i < values.length; i++) {
        var raw = this.clean(values[i]);
        var matches = raw.match(/\b\d{8}\b|\b\d{12}\b|\b\d{13}\b|\b\d{14}\b/g) || [];
        for (var j = 0; j < matches.length; j++) {
            var valid = this.validGtin(matches[j]);
            if (valid) return valid;
        }
    }
    return '';
};
window.MapeiaAIDetailCapture.absoluteUrl = function (value) {
    value = this.clean(value).replace(/^url\(["']?/, '').replace(/["']?\)$/, '');
    if (!value || value === '#' || /^javascript:/i.test(value) || /^data:/i.test(value) || /^blob:/i.test(value)) return '';
    try { return new URL(value, window.location.href).href; } catch (e) { return ''; }
};
window.MapeiaAIDetailCapture.imageCandidates = function (root) {
    root = root || document;
    var urls = [];
    var seen = {};
    var push = function (raw) {
        raw = window.MapeiaAIDetailCapture.clean(raw);
        if (!raw) return;
        if (raw.indexOf(',') >= 0 && raw.indexOf(' ') >= 0) {
            raw.split(',').forEach(function (part) { push(part.split(/\s+/)[0]); });
            return;
        }
        var url = window.MapeiaAIDetailCapture.absoluteUrl(raw.split(/\s+/)[0]);
        if (!url || seen[url]) return;
        var normalized = window.MapeiaAIDetailCapture.normalize(url);
        if (/(logo|favicon|sprite|placeholder|icon|whatsapp|facebook|instagram|youtube)/.test(normalized)) return;
        seen[url] = true;
        urls.push(url);
    };
    var nodes = Array.prototype.slice.call(root.querySelectorAll('img, source, a[href], [data-src], [data-original], [data-lazy], [data-image], [data-img], [data-url], [style*="background"]'));
    for (var i = 0; i < nodes.length; i++) {
        var node = nodes[i];
        ['src', 'data-src', 'data-original', 'data-lazy', 'data-image', 'data-img', 'data-url', 'href'].forEach(function (attr) {
            if (node.getAttribute) push(node.getAttribute(attr));
        });
        if (node.getAttribute) push(node.getAttribute('srcset'));
        var style = node.getAttribute ? node.getAttribute('style') || '' : '';
        var matches = style.match(/url\([^)]+\)/g) || [];
        matches.forEach(push);
    }
    return urls.slice(0, 20);
};
window.MapeiaAIDetailCapture.escapeHtml = function (value) {
    return String(value == null ? '' : value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
};
window.MapeiaAIDetailCapture.headersForRow = function (row) {
    var table = row && row.closest ? row.closest('table') : null;
    if (!table) return [];
    return Array.prototype.map.call(table.querySelectorAll('thead th, thead td'), function (cell) {
        return window.MapeiaAIDetailCapture.normalize(cell.textContent);
    });
};
window.MapeiaAIDetailCapture.cellByHeader = function (row, names) {
    var headers = this.headersForRow(row);
    var cells = Array.prototype.slice.call(row.children || []);
    for (var i = 0; i < headers.length && i < cells.length; i++) {
        for (var j = 0; j < names.length; j++) {
            if (headers[i].indexOf(this.normalize(names[j])) >= 0) return this.clean(cells[i].textContent);
        }
    }
    return '';
};
window.MapeiaAIDetailCapture.clickableForRow = function (row) {
    var nodes = Array.prototype.slice.call(row.querySelectorAll('button, a, [role="button"], [onclick], [data-id], [data-product-id], [data-produto-id], [data-bs-target], [data-target]'));
    var strongHints = ['btnviewproduct', 'visualizar', 'view', 'detalhe', 'detail', 'produto', 'product', 'editar', 'edit', 'ean', 'gtin'];
    for (var i = 0; i < nodes.length; i++) {
        var node = nodes[i];
        var raw = this.normalize([
            node.id,
            node.getAttribute('onclick'),
            node.getAttribute('href'),
            node.getAttribute('title'),
            node.getAttribute('aria-label'),
            node.getAttribute('data-id'),
            node.getAttribute('data-product-id'),
            node.getAttribute('data-produto-id'),
            node.getAttribute('data-bs-target'),
            node.getAttribute('data-target'),
            node.textContent,
            node.className
        ].join(' '));
        for (var j = 0; j < strongHints.length; j++) if (raw.indexOf(strongHints[j]) >= 0) return node;
    }
    return nodes.length === 1 ? nodes[0] : null;
};
window.MapeiaAIDetailCapture.init = function () {
    var rows = Array.prototype.slice.call(document.querySelectorAll('table tbody tr'));
    var items = [];
    var seen = {};
    for (var i = 0; i < rows.length; i++) {
        var row = rows[i];
        var action = this.clickableForRow(row);
        if (!action) continue;
        var idx = String(items.length);
        action.setAttribute('data-mapeiaai-detail-index', idx);
        var sku = this.cellByHeader(row, ['sku', 'codigo', 'código', 'referencia', 'referência', 'modelo']) || this.clean(row.getAttribute('data-sku'));
        var name = this.cellByHeader(row, ['produto', 'nome', 'titulo', 'título', 'descricao', 'descrição']);
        var gtin = this.firstValidGtin([row.textContent]);
        var imageUrls = this.imageCandidates(row).join('|');
        var key = sku || gtin || name || this.clean(row.textContent).slice(0, 120);
        if (key && seen[key]) continue;
        if (key) seen[key] = true;
        items.push({ index: items.length, sku: sku, name: name, gtin: gtin, image_urls: imageUrls, row_text: this.clean(row.textContent).slice(0, 1200) });
    }
    return JSON.stringify({ ok: true, count: items.length, items: items });
};
window.MapeiaAIDetailCapture.click = function (index) {
    var node = document.querySelector('[data-mapeiaai-detail-index="' + String(index) + '"]');
    if (!node) return JSON.stringify({ ok: false, reason: 'detail_button_not_found', index: index });
    try { node.click(); } catch (e) { return JSON.stringify({ ok: false, reason: String(e), index: index }); }
    return JSON.stringify({ ok: true, index: index });
};
window.MapeiaAIDetailCapture.field = function (selectors, root) {
    root = root || document;
    for (var i = 0; i < selectors.length; i++) {
        var node = root.querySelector ? root.querySelector(selectors[i]) : document.querySelector(selectors[i]);
        if (!node) continue;
        var value = node.value != null ? node.value : node.textContent;
        value = this.clean(value);
        if (value) return value;
    }
    return '';
};
window.MapeiaAIDetailCapture.htmlField = function (selectors, root) {
    root = root || document;
    for (var i = 0; i < selectors.length; i++) {
        var node = root.querySelector ? root.querySelector(selectors[i]) : document.querySelector(selectors[i]);
        if (!node) continue;
        var value = node.innerHTML || node.textContent || '';
        value = this.htmlToText(value);
        if (value) return value;
    }
    return '';
};
window.MapeiaAIDetailCapture.listField = function (selectors, root) {
    var text = this.htmlField(selectors, root);
    if (!text) return '';
    return text.split('\n').map(function (line) {
        return window.MapeiaAIDetailCapture.clean(line.replace(/^[-•]\s*/, ''));
    }).filter(function (line) {
        var n = window.MapeiaAIDetailCapture.normalize(line);
        return line && !/^palavras-chave|^titulos? com palavra-chave|^nenhuma informacao|^clique para copiar/.test(n);
    }).join(' | ');
};
window.MapeiaAIDetailCapture.fieldByLabel = function (labels, root) {
    root = root || document;
    var nodes = Array.prototype.slice.call(root.querySelectorAll ? root.querySelectorAll('label, th, td, dt, span, div') : document.querySelectorAll('label, th, td, dt, span, div'));
    for (var i = 0; i < nodes.length; i++) {
        var label = this.normalize(nodes[i].textContent);
        for (var j = 0; j < labels.length; j++) {
            if (label === this.normalize(labels[j]) || label.indexOf(this.normalize(labels[j]) + ':') === 0) {
                var control = null;
                var forId = nodes[i].getAttribute && nodes[i].getAttribute('for');
                if (forId) control = document.getElementById(forId);
                if (!control && nodes[i].nextElementSibling) control = nodes[i].nextElementSibling;
                if (!control && nodes[i].parentElement) control = nodes[i].parentElement.querySelector('input, textarea, select, td:nth-child(2), dd');
                var value = control ? (control.value != null ? control.value : control.textContent) : nodes[i].textContent.replace(/^[^:]+:/, '');
                value = this.clean(value);
                if (value && this.normalize(value) !== label) return value;
            }
        }
    }
    return '';
};
window.MapeiaAIDetailCapture.read = function (itemJson) {
    var item = {};
    try { item = JSON.parse(itemJson || '{}'); } catch (e) { item = {}; }
    var detailRoot = document.querySelector('.modal.show, .modal.in, #viewProduct, .offcanvas.show, [role="dialog"]') || document;
    var rawEan = this.field(['#modal-ean', '#EAN', '#ean', '#gtin', '#barcode', '#codigo_barras', '#codBarras', 'input[name="ean"]', 'input[name="EAN"]', 'input[name="gtin"]'], detailRoot) || this.fieldByLabel(['ean', 'gtin', 'codigo de barras', 'código de barras', 'barcode'], detailRoot);
    var gtin = this.validGtin(rawEan) || this.firstValidGtin([rawEan, detailRoot ? detailRoot.textContent : '', item.gtin, item.row_text]);
    var skuText = this.field(['#modal-sku', '#sku', '#sku-link', '#codigo', '#referencia', '[data-field="sku"]', 'input[name="sku"]', 'input[name="codigo"]', 'input[name="referencia"]'], detailRoot) || this.fieldByLabel(['sku', 'codigo', 'código', 'referencia', 'referência'], detailRoot);
    var detailImages = this.imageCandidates(detailRoot);
    var rowImages = this.clean(item.image_urls).split('|').filter(function (url) { return !!url; });
    var imageSeen = {};
    var imageUrls = [];
    detailImages.concat(rowImages).forEach(function (url) {
        if (url && !imageSeen[url]) { imageSeen[url] = true; imageUrls.push(url); }
    });
    var categories = this.listField(['#modal-categories'], detailRoot) || this.field(['#nameCategoria', '#cadCategoria', '#categoria', 'input[name="categoria"]'], detailRoot) || this.fieldByLabel(['categoria', 'departamento'], detailRoot);
    var price = this.field(['#modal-price', '#price_cost', '#price', '#preco', '#valor', 'input[name="price"]', 'input[name="preco"]', 'input[name="valor"]'], detailRoot) || this.fieldByLabel(['preco', 'preço', 'valor', 'preco custo', 'preço custo'], detailRoot);
    if (price && price.indexOf('R$') < 0 && /^\d/.test(price)) price = 'R$ ' + price;
    var record = {
        sku: this.clean(skuText || item.sku),
        id: this.field(['#id', 'input[name="id"]'], detailRoot) || this.fieldByLabel(['id', 'id produto'], detailRoot),
        name: this.field(['#modal-name', '#name', '#nome', '#produto', 'input[name="name"]', 'input[name="nome"]', 'textarea[name="name"]', 'textarea[name="nome"]'], detailRoot) || this.fieldByLabel(['nome', 'produto'], detailRoot) || this.clean(item.name),
        description: this.htmlField(['#modal-description', '#description', '#descricao', 'textarea[name="description"]', 'textarea[name="descricao"]'], detailRoot) || this.fieldByLabel(['descricao complementar', 'descrição complementar', 'descricao produto', 'descrição produto'], detailRoot),
        price: price,
        brand: this.field(['#modal-brand', '#brand', '#marca', 'input[name="brand"]', 'input[name="marca"]'], detailRoot) || this.fieldByLabel(['marca', 'brand'], detailRoot),
        model: this.field(['#modal-model', '#model', '#modelo', 'input[name="model"]', 'input[name="modelo"]'], detailRoot) || this.fieldByLabel(['modelo', 'model'], detailRoot),
        category: categories,
        images: imageUrls.slice(0, 20).join('|'),
        ean: gtin,
        raw_ean: rawEan || item.gtin || '',
        ncm: this.field(['#modal-ncm', '#ncm', 'input[name="fiscal_ncm"]', 'input[name="ncm"]'], detailRoot) || this.fieldByLabel(['ncm'], detailRoot),
        weight: this.field(['#modal-weight', '#weight', 'input[name="weight"]', 'input[name="peso"]'], detailRoot) || this.fieldByLabel(['peso'], detailRoot),
        size: this.field(['#modal-size', '#size', 'input[name="size"]', 'input[name="medidas"]'], detailRoot) || this.fieldByLabel(['medidas', 'dimensoes', 'dimensões'], detailRoot),
        stock: this.field(['#modal-inv', '#quantity', '#estoque', 'input[name="quantity"]', 'input[name="estoque"]'], detailRoot) || this.fieldByLabel(['estoque', 'quantidade'], detailRoot),
        keywords: this.listField(['#modal-top-keys'], detailRoot),
        suggested_titles: this.listField(['#modal-top-titles'], detailRoot),
        anatel: this.field(['#modal-anatel', '#anatel', 'input[name="anatel"]'], detailRoot) || this.fieldByLabel(['anatel'], detailRoot),
        inmetro: this.field(['#modal-inmetro', '#inmetro', 'input[name="inmetro"]'], detailRoot) || this.fieldByLabel(['inmetro'], detailRoot),
        video: this.absoluteUrl(this.field(['#nav-video iframe', 'iframe.embed-responsive-item', '#video', 'input[name="video"]'], detailRoot))
    };
    return JSON.stringify({ ok: true, record: record });
};
window.MapeiaAIDetailCapture.tableHtml = function (recordsJson) {
    var records = [];
    try { records = JSON.parse(recordsJson || '[]'); } catch (e) { records = []; }
    var headers = ['SKU', 'Codigo produto *', 'Código produto', 'ID Produto', 'Nome', 'Produto', 'Descrição Produto', 'Descrição complementar', 'GTIN', 'GTIN **', 'GTIN/EAN**', 'EAN', 'Preço', 'Marca', 'Modelo', 'Categoria', 'Peso kg', 'Medidas cm', 'NCM', 'Estoque', 'Palavras-Chave', 'Títulos Sugeridos', 'Anatel', 'Inmetro', 'Imagens', 'Imagem', 'URL Imagem', 'Vídeo URL'];
    var html = '<!doctype html><html><head><meta charset="utf-8"><title>MapeiaAI detalhes completos</title>';
    html += '<meta name="mapeiaai_capture_type" content="product_detail_full">';
    html += '<meta name="detail_has_description" content="' + String(records.some(function (r) { return !!r.description; })) + '">';
    html += '<meta name="detail_has_keywords" content="' + String(records.some(function (r) { return !!r.keywords; })) + '">';
    html += '<meta name="detail_has_ean" content="' + String(records.some(function (r) { return !!(r.ean || r.raw_ean); })) + '">';
    html += '<meta name="detail_has_ncm" content="' + String(records.some(function (r) { return !!r.ncm; })) + '">';
    html += '</head><body><table><thead><tr>' + headers.map(function (h) { return '<th>' + window.MapeiaAIDetailCapture.escapeHtml(h) + '</th>'; }).join('') + '</tr></thead><tbody>';
    records.forEach(function (r) {
        var code = r.sku || r.id || '';
        var firstImage = window.MapeiaAIDetailCapture.clean(r.images).split('|')[0] || '';
        var row = {
            'SKU': code,
            'Codigo produto *': code,
            'Código produto': code,
            'ID Produto': r.id || '',
            'Nome': r.name || '',
            'Produto': r.name || '',
            'Descrição Produto': r.name || '',
            'Descrição complementar': r.description || '',
            'GTIN': r.ean || r.raw_ean || '',
            'GTIN **': r.ean || r.raw_ean || '',
            'GTIN/EAN**': r.ean || r.raw_ean || '',
            'EAN': r.ean || r.raw_ean || '',
            'Preço': r.price || '',
            'Marca': r.brand || '',
            'Modelo': r.model || '',
            'Categoria': r.category || '',
            'Peso kg': r.weight || '',
            'Medidas cm': r.size || '',
            'NCM': r.ncm || '',
            'Estoque': r.stock || '',
            'Palavras-Chave': r.keywords || '',
            'Títulos Sugeridos': r.suggested_titles || '',
            'Anatel': r.anatel || '',
            'Inmetro': r.inmetro || '',
            'Imagens': r.images || '',
            'Imagem': firstImage,
            'URL Imagem': firstImage,
            'Vídeo URL': r.video || ''
        };
        html += '<tr>' + headers.map(function (h) { return '<td>' + window.MapeiaAIDetailCapture.escapeHtml(row[h]) + '</td>'; }).join('') + '</tr>';
    });
    html += '</tbody></table></body></html>';
    return JSON.stringify({ ok: true, html: html });
};
