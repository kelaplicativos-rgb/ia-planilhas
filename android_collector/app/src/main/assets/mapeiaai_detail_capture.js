window.MapeiaAIDetailCapture = window.MapeiaAIDetailCapture || {};
window.MapeiaAIDetailCapture.clean = function (value) {
    return String(value == null ? '' : value).replace(/\s+/g, ' ').trim();
};
window.MapeiaAIDetailCapture.digits = function (value) {
    return this.clean(value).replace(/\D+/g, '');
};
window.MapeiaAIDetailCapture.validGtin = function (value) {
    var d = this.digits(value);
    if (!/^(\d{8}|\d{12}|\d{13}|\d{14})$/.test(d)) return '';
    if (/^(\d)\1+$/.test(d)) return '';
    return d;
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
        return window.MapeiaAIDetailCapture.clean(cell.textContent).toLowerCase();
    });
};
window.MapeiaAIDetailCapture.cellByHeader = function (row, names) {
    var headers = this.headersForRow(row);
    var cells = Array.prototype.slice.call(row.children || []);
    for (var i = 0; i < headers.length && i < cells.length; i++) {
        for (var j = 0; j < names.length; j++) {
            if (headers[i].indexOf(names[j]) >= 0) return this.clean(cells[i].textContent);
        }
    }
    return '';
};
window.MapeiaAIDetailCapture.clickableForRow = function (row) {
    var nodes = Array.prototype.slice.call(row.querySelectorAll('button, a, [onclick], [data-id], [data-product-id], [data-produto-id]'));
    for (var i = 0; i < nodes.length; i++) {
        var node = nodes[i];
        var raw = [node.getAttribute('onclick'), node.getAttribute('data-id'), node.getAttribute('data-product-id'), node.getAttribute('data-produto-id'), node.textContent, node.className].join(' ').toLowerCase();
        if (raw.indexOf('getproduct') >= 0 || raw.indexOf('integr') >= 0 || raw.indexOf('mercado') >= 0 || raw.indexOf('ean') >= 0 || raw.indexOf('codigo') >= 0) {
            return node;
        }
    }
    return null;
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
        var sku = this.cellByHeader(row, ['sku', 'código', 'codigo', 'referência', 'referencia']) || this.clean(row.getAttribute('data-sku'));
        var name = this.cellByHeader(row, ['produto', 'nome', 'título', 'titulo', 'descrição', 'descricao']);
        var key = sku || name || this.clean(row.textContent).slice(0, 120);
        if (key && seen[key]) continue;
        if (key) seen[key] = true;
        items.push({ index: items.length, sku: sku, name: name, row_text: this.clean(row.textContent).slice(0, 800) });
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
window.MapeiaAIDetailCapture.read = function (itemJson) {
    var item = {};
    try { item = JSON.parse(itemJson || '{}'); } catch (e) { item = {}; }
    var rawEan = this.field(['#EAN', '#ean', 'input[name="ean"]', 'input[name="EAN"]', 'input[name="gtin"]', 'input[name="barcode"]']);
    var gtin = this.validGtin(rawEan);
    var skuText = this.field(['#sku', '#sku-link', '[data-field="sku"]']);
    var record = {
        sku: this.clean(skuText || item.sku),
        id: this.field(['#id', 'input[name="id"]']),
        name: this.field(['#name', 'input[name="name"]', 'textarea[name="name"]']) || this.clean(item.name),
        description: this.field(['#description', 'textarea[name="description"]', 'textarea[name="descricao"]']),
        price: this.field(['#price_cost', '#price', 'input[name="price"]', 'input[name="preco"]']),
        brand: this.field(['#brand', '#marca', 'input[name="brand"]', 'input[name="marca"]']),
        category: this.field(['#nameCategoria', '#cadCategoria', 'input[name="categoria"]']),
        ean: gtin,
        raw_ean: rawEan
    };
    return JSON.stringify({ ok: true, record: record });
};
window.MapeiaAIDetailCapture.tableHtml = function (recordsJson) {
    var records = [];
    try { records = JSON.parse(recordsJson || '[]'); } catch (e) { records = []; }
    var headers = ['SKU', 'Codigo produto *', 'Código produto', 'ID Produto', 'Nome', 'Produto', 'Descrição Produto', 'Descrição complementar', 'GTIN', 'GTIN **', 'GTIN/EAN**', 'EAN', 'Preço', 'Marca', 'Categoria'];
    var html = '<!doctype html><html><head><meta charset="utf-8"><title>MapeiaAI detalhes EAN</title></head><body>';
    html += '<table><thead><tr>' + headers.map(function (h) { return '<th>' + window.MapeiaAIDetailCapture.escapeHtml(h) + '</th>'; }).join('') + '</tr></thead><tbody>';
    records.forEach(function (r) {
        var code = r.sku || r.id || '';
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
            'Categoria': r.category || ''
        };
        html += '<tr>' + headers.map(function (h) { return '<td>' + window.MapeiaAIDetailCapture.escapeHtml(row[h]) + '</td>'; }).join('') + '</tr>';
    });
    html += '</tbody></table></body></html>';
    return JSON.stringify({ ok: true, html: html });
};
