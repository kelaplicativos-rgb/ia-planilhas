window.MapeiaAIDetailCapture = window.MapeiaAIDetailCapture || {};
window.MapeiaAIDetailCapture.clean = function (value) {
    return String(value == null ? '' : value).replace(/\s+/g, ' ').trim();
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
    for (var i = 0; i < body.length; i++) {
        total += parseInt(body[i], 10) * (i % 2 === 0 ? 3 : 1);
    }
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
        if (/(logo|favicon|sprite|placeholder|avatar|icon|whatsapp|facebook|instagram|youtube)/.test(normalized)) return;
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
    return urls.slice(0, 12);
};
window.MapeiaAIDetailCapture.escapeHtml = function (value) {
    return this.clean(value)
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
    var strongHints = ['getproduct', 'produto', 'product', 'detalhe', 'detail', 'editar', 'edit', 'visualizar', 'view', 'integr', 'mercado', 'ean', 'gtin', 'codigo', 'barcode'];
    for (var i = 0; i < nodes.length; i++) {
        var node = nodes[i];
        var raw = this.normalize([
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
        for (var j = 0; j < strongHints.length; j++) {
            if (raw.indexOf(strongHints[j]) >= 0) return node;
        }
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
window.MapeiaAIDetailCapture.field = function (selectors) {
    for (var i = 0; i < selectors.length; i++) {
        var node = document.querySelector(selectors[i]);
        if (!node) continue;
        var value = node.value != null ? node.value : node.textContent;
        value = this.clean(value);
        if (value) return value;
    }
    return '';
};
window.MapeiaAIDetailCapture.fieldByLabel = function (labels) {
    var nodes = Array.prototype.slice.call(document.querySelectorAll('label, th, td, dt, span, div'));
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
    var rawEan = this.field(['#EAN', '#ean', '#gtin', '#barcode', '#codigo_barras', '#codBarras', 'input[name="ean"]', 'input[name="EAN"]', 'input[name="gtin"]', 'input[name="GTIN"]', 'input[name="barcode"]', 'input[name="codigo_barras"]', 'input[name="codBarras"]']) || this.fieldByLabel(['ean', 'gtin', 'codigo de barras', 'código de barras', 'barcode']);
    var gtin = this.validGtin(rawEan) || this.firstValidGtin([rawEan, document.body ? document.body.textContent : '', item.gtin, item.row_text]);
    var skuText = this.field(['#sku', '#sku-link', '#codigo', '#referencia', '[data-field="sku"]', 'input[name="sku"]', 'input[name="codigo"]', 'input[name="referencia"]']) || this.fieldByLabel(['sku', 'codigo', 'código', 'referencia', 'referência']);
    var detailRoot = document.querySelector('.modal.show, .modal.in, .offcanvas.show, [role="dialog"]') || document;
    var detailImages = this.imageCandidates(detailRoot);
    var rowImages = this.clean(item.image_urls).split('|').filter(function (url) { return !!url; });
    var imageSeen = {};
    var imageUrls = [];
    detailImages.concat(rowImages).forEach(function (url) {
        if (url && !imageSeen[url]) {
            imageSeen[url] = true;
            imageUrls.push(url);
        }
    });
    var record = {
        sku: this.clean(skuText || item.sku),
        id: this.field(['#id', 'input[name="id"]']) || this.fieldByLabel(['id', 'id produto']),
        name: this.field(['#name', '#nome', '#produto', 'input[name="name"]', 'input[name="nome"]', 'textarea[name="name"]', 'textarea[name="nome"]']) || this.fieldByLabel(['nome', 'produto', 'descricao', 'descrição']) || this.clean(item.name),
        description: this.field(['#description', '#descricao', 'textarea[name="description"]', 'textarea[name="descricao"]']) || this.fieldByLabel(['descricao complementar', 'descrição complementar', 'descricao produto', 'descrição produto']),
        price: this.field(['#price_cost', '#price', '#preco', '#valor', 'input[name="price"]', 'input[name="preco"]', 'input[name="valor"]']) || this.fieldByLabel(['preco', 'preço', 'valor', 'preco custo', 'preço custo']),
        brand: this.field(['#brand', '#marca', 'input[name="brand"]', 'input[name="marca"]']) || this.fieldByLabel(['marca', 'brand']),
        category: this.field(['#nameCategoria', '#cadCategoria', '#categoria', 'input[name="categoria"]']) || this.fieldByLabel(['categoria', 'departamento']),
        images: imageUrls.slice(0, 12).join('|'),
        ean: gtin,
        raw_ean: rawEan || item.gtin || ''
    };
    return JSON.stringify({ ok: true, record: record });
};
window.MapeiaAIDetailCapture.tableHtml = function (recordsJson) {
    var records = [];
    try { records = JSON.parse(recordsJson || '[]'); } catch (e) { records = []; }
    var headers = ['SKU', 'Codigo produto *', 'Código produto', 'ID Produto', 'Nome', 'Produto', 'Descrição Produto', 'Descrição complementar', 'GTIN', 'GTIN **', 'GTIN/EAN**', 'EAN', 'Preço', 'Marca', 'Categoria', 'Imagens', 'Imagem', 'URL Imagem'];
    var html = '<!doctype html><html><head><meta charset="utf-8"><title>MapeiaAI detalhes EAN</title></head><body>';
    html += '<table><thead><tr>' + headers.map(function (h) { return '<th>' + window.MapeiaAIDetailCapture.escapeHtml(h) + '</th>'; }).join('') + '</tr></thead><tbody>';
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
            'Categoria': r.category || '',
            'Imagens': r.images || '',
            'Imagem': firstImage,
            'URL Imagem': firstImage
        };
        html += '<tr>' + headers.map(function (h) { return '<td>' + window.MapeiaAIDetailCapture.escapeHtml(row[h]) + '</td>'; }).join('') + '</tr>';
    });
    html += '</tbody></table></body></html>';
    return JSON.stringify({ ok: true, html: html });
};