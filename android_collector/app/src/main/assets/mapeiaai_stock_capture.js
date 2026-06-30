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
window.MapeiaAIStockCapture.basicColumnPattern = /sku|codigo|referencia|produto|nome|descricao|ean|gtin|barras|estoque|stock|saldo|quantidade|quantity|qtd|preco|price|valor|custo|situacao|status|ativo|disponivel|availability|variacao|grade|cor|tamanho|local|deposito|armazem|loja|fornecedor|marca/i;
window.MapeiaAIStockCapture.numericStockPattern = /^-?\d+([,.]\d+)?$/;
window.MapeiaAIStockCapture.statusPattern = /^(disponivel|disponível|indisponivel|indisponível|baixo|esgotado|sem estoque|em estoque|ativo|inativo)$/i;
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
        out[prefix || 'valor'] = value.map(function (item) {
            return window.MapeiaAIStockCapture.clean(typeof item === 'object' ? JSON.stringify(item) : item);
        }).filter(Boolean).join(' | ');
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
window.MapeiaAIStockCapture.appendParam = function (params, key, value) {
    if (value == null) return;
    if (Array.isArray(value)) {
        for (var i = 0; i < value.length; i++) this.appendParam(params, key + '[' + i + ']', value[i]);
        return;
    }
    if (typeof value === 'object') {
        Object.keys(value).forEach(function (child) {
            window.MapeiaAIStockCapture.appendParam(params, key ? key + '[' + child + ']' : child, value[child]);
        });
        return;
    }
    params.push(encodeURIComponent(key) + '=' + encodeURIComponent(String(value)));
};
window.MapeiaAIStockCapture.encodeParams = function (data) {
    var params = [];
    Object.keys(data || {}).forEach(function (key) {
        window.MapeiaAIStockCapture.appendParam(params, key, data[key]);
    });
    return params.join('&');
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
window.MapeiaAIStockCapture.dataTableContext = function () {
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
    return { table: table, dt: dt, settings: settings, headers: headers, columns: columns, info: info };
};
window.MapeiaAIStockCapture.rowsToValues = function (rawRows, headers, columns) {
    rawRows = rawRows || [];
    headers = headers || [];
    columns = columns || [];
    var objectRows = rawRows.filter(function (row) { return row && typeof row === 'object' && !Array.isArray(row); });
    if (objectRows.length) {
        var keySeen = {};
        var objectHeaders = [];
        objectRows.forEach(function (row) {
            var flat = window.MapeiaAIStockCapture.flatten(row, '', {});
            Object.keys(flat).forEach(function (key) {
                if (!keySeen[key]) {
                    keySeen[key] = true;
                    objectHeaders.push(key);
                }
            });
        });
        if (objectHeaders.length > headers.length) headers = objectHeaders;
    }
    var rows = rawRows.map(function (row) {
        if (Array.isArray(row)) {
            if (!headers.length) headers = row.map(function (_, idx) { return 'Coluna ' + (idx + 1); });
            return headers.map(function (_, idx) { return window.MapeiaAIStockCapture.clean(row[idx]); });
        }
        if (row && typeof row === 'object') {
            var flat = window.MapeiaAIStockCapture.flatten(row, '', {});
            if (!headers.length) headers = Object.keys(flat);
            return headers.map(function (header, idx) {
                var columnKey = columns[idx] && typeof columns[idx] === 'string' ? columns[idx] : '';
                return window.MapeiaAIStockCapture.clean(window.MapeiaAIStockCapture.getByPath(row, columnKey) || window.MapeiaAIStockCapture.bestObjectValue(flat, header, columnKey));
            });
        }
        return [window.MapeiaAIStockCapture.clean(row)];
    }).filter(function (values) {
        return values.some(function (value) { return value.length > 0; });
    });
    return { headers: headers, rows: rows };
};
window.MapeiaAIStockCapture.extractResponseRows = function (json) {
    if (!json) return [];
    return json.data || json.aaData || json.rows || json.products || json.items || [];
};
window.MapeiaAIStockCapture.extractResponseTotal = function (json, fallback) {
    if (!json) return fallback || 0;
    return Number(json.recordsFiltered || json.recordsTotal || json.total || json.count || fallback || 0) || 0;
};
window.MapeiaAIStockCapture.ajaxConfig = function (ctx) {
    var settings = ctx && ctx.settings ? ctx.settings : null;
    if (!settings) return null;
    var ajax = settings.ajax || settings.oInit && settings.oInit.ajax || settings.sAjaxSource || '';
    var url = '';
    var method = settings.sServerMethod || 'GET';
    if (typeof ajax === 'string') {
        url = ajax;
    } else if (ajax && typeof ajax === 'object') {
        url = ajax.url || ajax.sUrl || '';
        method = ajax.type || ajax.method || method;
    }
    if (!url) return null;
    return { url: new URL(url, window.location.href).href, method: String(method || 'GET').toUpperCase() };
};
window.MapeiaAIStockCapture.lastAjaxParams = function (ctx) {
    try {
        if (ctx && ctx.dt && ctx.dt.ajax && ctx.dt.ajax.params) {
            var params = ctx.dt.ajax.params();
            if (params) return JSON.parse(JSON.stringify(params));
        }
    } catch (e) {}
    return {};
};
window.MapeiaAIStockCapture.syncAjax = function (config, data) {
    var body = this.encodeParams(data || {});
    var url = config.url;
    var method = config.method || 'GET';
    var xhr = new XMLHttpRequest();
    if (method === 'GET') {
        url += (url.indexOf('?') >= 0 ? '&' : '?') + body;
        xhr.open('GET', url, false);
    } else {
        xhr.open(method, url, false);
        xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded; charset=UTF-8');
    }
    xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
    var csrf = document.querySelector('meta[name="csrf-token"], meta[name="csrf_token"]');
    if (csrf && csrf.content) xhr.setRequestHeader('X-CSRF-TOKEN', csrf.content);
    xhr.send(method === 'GET' ? null : body);
    if (xhr.status < 200 || xhr.status >= 300) throw new Error('ajax_status_' + xhr.status);
    return JSON.parse(xhr.responseText || '{}');
};
window.MapeiaAIStockCapture.serverSideAllRows = function (ctx) {
    try {
        var info = ctx.info || {};
        if (Number(info.page || 0) > 0 && Number(info.recordsTotal || info.recordsDisplay || 0) > Number(info.length || 0)) {
            return { rawRows: [], total: Number(info.recordsTotal || info.recordsDisplay || 0) || 0, method: 'skipped_after_ajax_all_pages' };
        }
        var config = this.ajaxConfig(ctx);
        if (!config) return null;
        var base = this.lastAjaxParams(ctx);
        var expected = Number(info.recordsTotal || info.recordsDisplay || 0) || 0;
        var currentLength = Number(info.length || 0) || 75;
        var requestedLength = Math.max(75, Math.min(500, currentLength > 0 ? currentLength : 500));
        var allRows = [];
        var total = expected;
        var seenStart = {};
        for (var start = 0, guard = 0; guard < 200; guard++) {
            if (seenStart[start]) break;
            seenStart[start] = true;
            var params = JSON.parse(JSON.stringify(base || {}));
            params.start = start;
            params.length = requestedLength;
            params.draw = (Number(params.draw || 0) || 0) + guard + 1;
            var json = this.syncAjax(config, params);
            var rows = this.extractResponseRows(json);
            total = Math.max(total, this.extractResponseTotal(json, total));
            if (!rows || !rows.length) break;
            allRows = allRows.concat(rows);
            if (total > 0 && allRows.length >= total) break;
            if (rows.length < requestedLength && (!total || allRows.length >= total)) break;
            start += rows.length;
        }
        if (!allRows.length) return null;
        return { rawRows: allRows, total: total || allRows.length, method: 'ajax_all_pages' };
    } catch (e) {
        return { rawRows: [], total: 0, method: 'ajax_failed', error: String(e && e.message ? e.message : e) };
    }
};
window.MapeiaAIStockCapture.dataTablesPayload = function () {
    try {
        var ctx = this.dataTableContext();
        if (!ctx) return null;
        var ajaxAll = this.serverSideAllRows(ctx);
        if (ajaxAll && ajaxAll.method === 'skipped_after_ajax_all_pages') {
            return { headers: ctx.headers, rows: [], total: ajaxAll.total, pageLength: ctx.info.length || 0, method: ajaxAll.method, error: '' };
        }
        var rawRows = ajaxAll && ajaxAll.rawRows && ajaxAll.rawRows.length ? ajaxAll.rawRows : ctx.dt.rows({ page: 'current' }).data().toArray();
        var converted = this.rowsToValues(rawRows, ctx.headers, ctx.columns);
        var total = ajaxAll && ajaxAll.total ? ajaxAll.total : (ctx.info.recordsTotal || ctx.info.recordsDisplay || converted.rows.length);
        var method = ajaxAll && ajaxAll.rawRows && ajaxAll.rawRows.length ? ajaxAll.method : 'current_page';
        var error = ajaxAll && ajaxAll.error ? ajaxAll.error : '';
        return { headers: converted.headers, rows: converted.rows, total: total, pageLength: ctx.info.length || converted.rows.length, method: method, error: error };
    } catch (e) {
        return null;
    }
};
window.MapeiaAIStockCapture.isStatusColumn = function (header, values) {
    var normalized = this.normalize(header);
    if (normalized.indexOf('estoque') < 0 && normalized.indexOf('stock') < 0) return false;
    var nonEmpty = values.filter(Boolean);
    if (!nonEmpty.length) return false;
    var numeric = nonEmpty.filter(function (value) { return window.MapeiaAIStockCapture.numericStockPattern.test(value); }).length;
    var status = nonEmpty.filter(function (value) { return window.MapeiaAIStockCapture.statusPattern.test(value); }).length;
    return status > 0 && numeric === 0;
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
            return JSON.stringify({ ok: false, reason: 'no_rows_found', total: payload ? payload.total : 0, headers: headers, ajax_error: payload ? payload.error : '', method: payload ? payload.method : '' });
        }

        var keep = [];
        for (var i = 0; i < headers.length; i++) {
            var normalized = this.normalize(headers[i]);
            if (this.basicColumnPattern.test(normalized)) keep.push(i);
        }
        if (!keep.length) {
            for (var all = 0; all < Math.min(headers.length, 80); all++) keep.push(all);
        }

        var outHeaders = keep.map(function (idx) { return headers[idx] || ('Coluna ' + (idx + 1)); });
        var bodyRows = rows.map(function (values) {
            return keep.map(function (idx) { return window.MapeiaAIStockCapture.clean(values[idx]); });
        }).filter(function (values) {
            return values.some(function (value) { return value.length > 0; });
        });

        for (var h = 0; h < outHeaders.length; h++) {
            var colValues = bodyRows.map(function (row) { return row[h] || ''; });
            if (this.isStatusColumn(outHeaders[h], colValues)) outHeaders[h] = 'Disponibilidade';
        }

        if (!bodyRows.length) {
            return JSON.stringify({ ok: false, reason: 'no_basic_rows_found', total: payload ? payload.total : rows.length, headers: headers, ajax_error: payload ? payload.error : '', method: payload ? payload.method : '' });
        }

        var html = '<!doctype html><html><head><meta charset="utf-8"><title>MapeiaAI estoque rapido</title>';
        html += '<meta name="mapeiaai_capture_type" content="stock_basic_html_only">';
        html += '<meta name="source_url" content="' + this.escapeHtml(window.location.href) + '">';
        html += '<meta name="source_total" content="' + this.escapeHtml(payload ? payload.total : bodyRows.length) + '">';
        html += '<meta name="capture_method" content="' + this.escapeHtml(payload ? payload.method : 'dom') + '">';
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

        return JSON.stringify({ ok: true, count: bodyRows.length, columns: outHeaders.length, total: payload ? payload.total : bodyRows.length, method: payload ? payload.method : 'dom', html: html });
    } catch (e) {
        return JSON.stringify({ ok: false, reason: String(e) });
    }
};
