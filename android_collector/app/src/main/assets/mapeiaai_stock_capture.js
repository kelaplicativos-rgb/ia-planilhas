window.MapeiaAIStockCapture = window.MapeiaAIStockCapture || {};
window.MapeiaAIStockCapture.clean = function (value) {
    return String(value == null ? '' : value)
        .replace(/<[^>]*>/g, ' ')
        .replace(/&nbsp;/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
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
window.MapeiaAIStockCapture.getByPath = function (obj, path) {
    if (!obj || !path || typeof path !== 'string') return '';
    if (path === '_' || path === 'function') return '';
    var current = obj;
    var parts = path.replace(/\[(\w+)\]/g, '.$1').split('.');
    for (var i = 0; i < parts.length; i++) {
        var key = parts[i];
        if (!key) continue;
        if (current == null || typeof current !== 'object' || !(key in current)) return '';
        current = current[key];
    }
    return current == null || typeof current === 'object' ? '' : current;
};
window.MapeiaAIStockCapture.flatten = function (value, prefix, out) {
    out = out || {};
    if (value == null) return out;
    if (typeof value !== 'object') {
        if (prefix) out[prefix] = this.clean(value);
        return out;
    }
    if (Array.isArray(value)) {
        out[prefix || 'valor'] = value.map(function (item) { return window.MapeiaAIStockCapture.clean(typeof item === 'object' ? JSON.stringify(item) : item); }).filter(Boolean).join(' | ');
        return out;
    }
    Object.keys(value).forEach(function (key) {
        var next = prefix ? prefix + '.' + key : key;
        var item = value[key];
        if (item != null && typeof item === 'object' && !Array.isArray(item)) {
            window.MapeiaAIStockCapture.flatten(item, next, out);
        } else {
            out[next] = window.MapeiaAIStockCapture.clean(Array.isArray(item) ? item.join(' | ') : item);
        }
    });
    return out;
};
window.MapeiaAIStockCapture.bestObjectValue = function (flat, header, columnKey) {
    var normalizedHeader = this.normalize(header);
    var normalizedColumn = this.normalize(columnKey);
    var keys = Object.keys(flat || {});
    if (columnKey && flat[columnKey]) return flat[columnKey];
    for (var i = 0; i < keys.length; i++) {
        if (this.normalize(keys[i]) === normalizedColumn && flat[keys[i]]) return flat[keys[i]];
    }
    for (var j = 0; j < keys.length; j++) {
        var normalizedKey = this.normalize(keys[j].split('.').pop());
        if (normalizedHeader && (normalizedKey === normalizedHeader || normalizedKey.indexOf(normalizedHeader) >= 0 || normalizedHeader.indexOf(normalizedKey) >= 0)) {
            if (flat[keys[j]]) return flat[keys[j]];
        }
    }
    return '';
};
window.MapeiaAIStockCapture.headersFromDom = function (table) {
    return Array.prototype.slice.call((table || document).querySelectorAll('thead th, thead td')).map(function (cell) {
        return window.MapeiaAIStockCapture.clean(cell.textContent);
    });
};
window.MapeiaAIStockCapture.domRows = function (table, headers) {
    var rows = Array.prototype.slice.call((table || document).querySelectorAll('tbody tr')).filter(function (row) {
        return !!window.MapeiaAIStockCapture.clean(row.textContent);
    });
    return rows.map(function (row) {
        var cells = Array.prototype.slice.call(row.children || []);
        return headers.map(function (_, idx) {
            return window.MapeiaAIStockCapture.clean(cells[idx] ? cells[idx].textContent : '');
        });
    }).filter(function (values) {
        return values.some(function (value) { return value.length > 0; });
    });
};
window.MapeiaAIStockCapture.dataTablesPayload = function () {
    try {
        if (!(window.jQuery && window.jQuery.fn && window.jQuery.fn.dataTable)) return null;
        var tables = window.jQuery.fn.dataTable.tables();
        if (!tables || !tables.length) return null;
        var table = tables[0];
        var dt = window.jQuery(table).DataTable();
        var info = dt.page.info ? dt.page.info() : {};
        var headers = this.headersFromDom(table);
        var settings = dt.settings && dt.settings().length ? dt.settings()[0] : null;
        var columns = settings && settings.aoColumns ? settings.aoColumns.map(function (column) {
            return column.mData || column.data || column.sName || column.name || column.sTitle || column.title || '';
        }) : [];
        if (!headers.length && columns.length) {
            headers = columns.map(function (column, idx) { return window.MapeiaAIStockCapture.clean(column) || ('Coluna ' + (idx + 1)); });
        }
        var rawRows = dt.rows({ page: 'current' }).data().toArray();
        var rows = rawRows.map(function (row) {
            if (Array.isArray(row)) {
                if (!headers.length) headers = row.map(function (_, idx) { return 'Coluna ' + (idx + 1); });
                return headers.map(function (_, idx) { return window.MapeiaAIStockCapture.clean(row[idx]); });
            }
            if (row && typeof row === 'object') {
                var flat = window.MapeiaAIStockCapture.flatten(row, '', {});
                if (!headers.length) headers = Object.keys(flat);
                var values = headers.map(function (header, idx) {
                    var columnKey = columns[idx] && typeof columns[idx] === 'string' ? columns[idx] : '';
                    return window.MapeiaAIStockCapture.clean(window.MapeiaAIStockCapture.getByPath(row, columnKey) || window.MapeiaAIStockCapture.bestObjectValue(flat, header, columnKey));
                });
                if (!values.some(Boolean)) {
                    headers = Object.keys(flat);
                    values = headers.map(function (key) { return flat[key]; });
                }
                return values;
            }
            return [window.MapeiaAIStockCapture.clean(row)];
        }).filter(function (values) {
            return values.some(function (value) { return value.length > 0; });
        });
        return { headers: headers, rows: rows, total: info.recordsTotal || info.recordsDisplay || rows.length, pageLength: info.length || rows.length };
    } catch (e) {
        return null;
    }
};
window.MapeiaAIStockCapture.tableHtml = function () {
    try {
        var table = document.querySelector('table');
        var payload = this.dataTablesPayload();
        var headers = payload && payload.headers ? payload.headers : this.headersFromDom(table || document);
        if (!headers.length && table) {
            var firstRow = table.querySelector('tbody tr');
            if (firstRow) headers = Array.prototype.slice.call(firstRow.children || []).map(function (_, idx) { return 'Coluna ' + (idx + 1); });
        }
        var rows = payload && payload.rows && payload.rows.length ? payload.rows : this.domRows(table || document, headers);

        if (!headers.length || !rows.length) {
            return JSON.stringify({ ok: false, reason: 'no_rows_found', total: payload ? payload.total : 0, headers: headers });
        }

        var keep = [];
        for (var i = 0; i < headers.length; i++) {
            var normalized = this.normalize(headers[i]);
            if (this.basicColumnPattern.test(normalized)) keep.push(i);
        }
        if (!keep.length) {
            for (var all = 0; all < Math.min(headers.length, 40); all++) keep.push(all);
        }

        var outHeaders = keep.map(function (idx) { return headers[idx] || ('Coluna ' + (idx + 1)); });
        var bodyRows = rows.map(function (values) {
            return keep.map(function (idx) { return window.MapeiaAIStockCapture.clean(values[idx]); });
        }).filter(function (values) {
            return values.some(function (value) { return value.length > 0; });
        });

        if (!bodyRows.length) {
            return JSON.stringify({ ok: false, reason: 'no_basic_rows_found', total: payload ? payload.total : rows.length, headers: headers });
        }

        var html = '<!doctype html><html><head><meta charset="utf-8"><title>MapeiaAI estoque rapido</title>';
        html += '<meta name="mapeiaai_capture_type" content="stock_basic_html_only">';
        html += '<meta name="source_url" content="' + this.escapeHtml(window.location.href) + '">';
        html += '<meta name="source_total" content="' + this.escapeHtml(payload ? payload.total : bodyRows.length) + '">';
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

        return JSON.stringify({ ok: true, count: bodyRows.length, columns: outHeaders.length, total: payload ? payload.total : bodyRows.length, html: html });
    } catch (e) {
        return JSON.stringify({ ok: false, reason: String(e) });
    }
};
