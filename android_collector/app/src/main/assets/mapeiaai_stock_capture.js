window.MapeiaAIStockCapture = window.MapeiaAIStockCapture || {};
window.MapeiaAIStockCapture.clean = function (value) {
    return String(value == null ? '' : value).replace(/\s+/g, ' ').trim();
};
window.MapeiaAIStockCapture.normalize = function (value) {
    return this.clean(value).toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
};
window.MapeiaAIStockCapture.escapeHtml = function (value) {
    return this.clean(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
};
window.MapeiaAIStockCapture.basicColumnPattern = /sku|codigo|referencia|produto|nome|descricao|ean|gtin|barras|estoque|saldo|quantidade|qtd|preco|valor|custo|situacao|status|ativo|variacao|grade|cor|tamanho|local|deposito|armazem|loja|fornecedor|marca/i;
window.MapeiaAIStockCapture.tableHtml = function () {
    try {
        var table = document.querySelector('table');
        if (!table) return JSON.stringify({ ok: false, reason: 'table_not_found' });

        var headerNodes = Array.prototype.slice.call(table.querySelectorAll('thead th, thead td'));
        var headers = headerNodes.map(function (cell) { return window.MapeiaAIStockCapture.clean(cell.textContent); });
        var rows = Array.prototype.slice.call(table.querySelectorAll('tbody tr')).filter(function (row) {
            return !!window.MapeiaAIStockCapture.clean(row.textContent);
        });

        if (!headers.length && rows.length) {
            headers = Array.prototype.slice.call(rows[0].children || []).map(function (_, idx) { return 'Coluna ' + (idx + 1); });
        }

        var keep = [];
        for (var i = 0; i < headers.length; i++) {
            var normalized = this.normalize(headers[i]);
            if (this.basicColumnPattern.test(normalized)) keep.push(i);
        }
        if (!keep.length) {
            for (var all = 0; all < Math.min(headers.length, 30); all++) keep.push(all);
        }

        var outHeaders = keep.map(function (idx) { return headers[idx] || ('Coluna ' + (idx + 1)); });
        var bodyRows = [];
        rows.forEach(function (row) {
            var cells = Array.prototype.slice.call(row.children || []);
            var values = keep.map(function (idx) {
                return window.MapeiaAIStockCapture.clean(cells[idx] ? cells[idx].textContent : '');
            });
            var hasValue = values.some(function (value) { return value.length > 0; });
            if (hasValue) bodyRows.push(values);
        });

        var html = '<!doctype html><html><head><meta charset="utf-8"><title>MapeiaAI estoque rapido</title>';
        html += '<meta name="mapeiaai_capture_type" content="stock_basic_html_only">';
        html += '<meta name="source_url" content="' + this.escapeHtml(window.location.href) + '">';
        html += '</head><body>';
        html += '<h1>MapeiaAI - Controle de estoque rapido</h1>';
        html += '<p>Origem: ' + this.escapeHtml(window.location.href) + '</p>';
        html += '<table><thead><tr>';
        html += outHeaders.map(function (header) { return '<th>' + window.MapeiaAIStockCapture.escapeHtml(header) + '</th>'; }).join('');
        html += '</tr></thead><tbody>';
        bodyRows.forEach(function (values) {
            html += '<tr>' + values.map(function (value) { return '<td>' + window.MapeiaAIStockCapture.escapeHtml(value) + '</td>'; }).join('') + '</tr>';
        });
        html += '</tbody></table></body></html>';

        return JSON.stringify({ ok: true, count: bodyRows.length, columns: outHeaders.length, html: html });
    } catch (e) {
        return JSON.stringify({ ok: false, reason: String(e) });
    }
};
