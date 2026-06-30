window.MapeiaAIStockCapture = window.MapeiaAIStockCapture || {};
window.MapeiaAIStockCapture.decodeEntities = function (value) {
    return String(value == null ? '' : value)
        .replace(/&nbsp;/g, ' ')
        .replace(/&quot;/g, '"')
        .replace(/&#34;/g, '"')
        .replace(/&#39;/g, "'")
        .replace(/&amp;/g, '&')
        .replace(/&lt;/g, '<')
        .replace(/&gt;/g, '>');
};
window.MapeiaAIStockCapture.clean = function (value) {
    return this.decodeEntities(value)
        .replace(/<[^>]*>/g, ' ')
        .replace(/\b(data-[a-z0-9_-]+|class|style|title|href|src|alt|aria-[a-z0-9_-]+)\s*=\s*"[^"]*"/gi, ' ')
        .replace(/\b(data-[a-z0-9_-]+|class|style|title|href|src|alt|aria-[a-z0-9_-]+)\s*=\s*'[^']*'/gi, ' ')
        .replace(/\b(data-[a-z0-9_-]+|class|style|title|href|src|alt|aria-[a-z0-9_-]+)\s*=\s*[^\s>]+/gi, ' ')
        .replace(/[<>]/g, ' ')
        .replace(/^[\s"'=\/]+|[\s"'=\/]+$/g, '')
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
window.MapeiaAIStockCapture.numericPattern = /^-?\d+([,.]\d+)?$/;
window.MapeiaAIStockCapture.moneyPattern = /R\$\s*\d|^\d{1,6}([,.]\d{2})$/;
window.MapeiaAIStockCapture.statusPattern = /^(disponivel|disponível|indisponivel|indisponível|baixo|esgotado|sem estoque|em estoque|ativo|inativo)$/i;
window.MapeiaAIStockCapture.stockKeyPattern = /estoque|stock|saldo|quantidade|quantity|qtd|qty|inventory|inventario|inventário|balance|balanco|balanço|available|availability/i;
window.MapeiaAIStockCapture.extractHiddenStock = function (value) {
    var raw = this.decodeEntities(value);
    var visible = this.normalize(raw.replace(/<[^>]*>/g, ' '));
    if (/\b(esgotado|sem estoque|indisponivel|indisponível)\b/.test(visible)) return '0';

    var numericOnly = this.clean(raw);
    if (this.numericPattern.test(numericOnly)) return numericOnly.replace(',', '.');

    var attrRe = /(?:title|data-original-title|data-bs-original-title|data-title|data-stock|data-estoque|data-quantity|data-quantidade|data-qtd|data-qty|data-saldo|data-inventory|data-balance|aria-label)\s*=\s*(["'])(.*?)\1/gi;
    var match;
    while ((match = attrRe.exec(raw)) !== null) {
        var attrValue = this.clean(match[2]);
        var attrNorm = this.normalize(attrValue);
        if (/\b(esgotado|sem estoque|indisponivel|indisponível)\b/.test(attrNorm)) return '0';
        var attrNumber = attrValue.match(/-?\d+([,.]\d+)?/);
        if (attrNumber) return attrNumber[0].replace(',', '.');
    }

    var patterns = [
        /(?:estoque|saldo|stock|quantity|quantidade|qtd|inventory|invent[aá]rio|balance|dispon[ií]vel|available)[^0-9-]{0,50}(-?\d+([,.]\d+)?)/i,
        /(-?\d+([,.]\d+)?)\s*(?:unid|unidade|unidades|pe[cç]as|pcs|em estoque|dispon[ií]veis)/i,
        /(?:stockQuantity|inventoryLevel|availableQuantity|quantityAvailable|saldoAtual|estoqueAtual)\s*[:=]\s*["']?(-?\d+([,.]\d+)?)/i
    ];
    for (var i = 0; i < patterns.length; i++) {
        var found = raw.match(patterns[i]);
        if (found && found[1] != null) return String(found[1]).replace(',', '.');
    }
    return '';
};
window.MapeiaAIStockCapture.cleanForKey = function (key, value) {
    if (this.stockKeyPattern.test(String(key || ''))) {
        var hidden = this.extractHiddenStock(value);
        if (hidden !== '') return hidden;
    }
    return this.clean(value);
};
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
        if (prefix) out[prefix] = this.cleanForKey(prefix, value);
        return out;
    }
    if (Array.isArray(value)) {
        out[prefix || 'valor'] = value.map(function (item) {
            return window.MapeiaAIStockCapture.cleanForKey(prefix || 'valor', typeof item === 'object' ? JSON.stringify(item) : item);
        }).filter(Boolean).join(' | ');
        return out;
    }
    Object.keys(value).forEach(function (key) {
        var next = prefix ? prefix + '.' + key : key;
        var item = value[key];
        if (item != null && typeof item === 'object' && !Array.isArray(item)) {
            window.MapeiaAIStockCapture.flatten(item, next, out);
        } else {
            out[next] = window.MapeiaAIStockCapture.cleanForKey(next, Array.isArray(item) ? item.join(' | ') : item);
        }
    });
    return out;
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
        return headers.map(function (header, idx) {
            return window.MapeiaAIStockCapture.cleanForKey(header, cells[idx] ? cells[idx].innerHTML || cells[idx].textContent : '');
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
window.MapeiaAIStockCapture.extractResponseRows = function (json) {
    if (!json) return [];
    return json.data || json.aaData || json.rows || json.products || json.items || [];
};
window.MapeiaAIStockCapture.extractResponseTotal = function (json, fallback) {
    if (!json) return fallback || 0;
    return Number(json.recordsFiltered || json.recordsTotal || json.total || json.count || fallback || 0) || 0;
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
window.MapeiaAIStockCapture.valueFromObject = function (row, flat, header, columnKey) {
    var direct = this.getByPath(row, columnKey);
    if (direct) return direct;
    if (flat[header]) return flat[header];
    var target = this.normalize(columnKey || header);
    var keys = Object.keys(flat || {});
    for (var i = 0; i < keys.length; i++) {
        if (this.normalize(keys[i]) === target && flat[keys[i]]) return flat[keys[i]];
    }
    return '';
};
window.MapeiaAIStockCapture.rowsToValues = function (rawRows, headers, columns) {
    rawRows = rawRows || [];
    headers = headers || [];
    columns = columns || [];
    var objectRows = rawRows.filter(function (row) { return row && typeof row === 'object' && !Array.isArray(row); });
    if (objectRows.length) {
        var seen = {};
        headers = [];
        objectRows.forEach(function (row) {
            var flat = window.MapeiaAIStockCapture.flatten(row, '', {});
            Object.keys(flat).forEach(function (key) {
                if (!seen[key]) {
                    seen[key] = true;
                    headers.push(key);
                }
            });
        });
    }
    var rows = rawRows.map(function (row) {
        if (Array.isArray(row)) {
            if (!headers.length) headers = row.map(function (_, idx) { return 'Coluna ' + (idx + 1); });
            return headers.map(function (header, idx) { return window.MapeiaAIStockCapture.cleanForKey(header, row[idx]); });
        }
        if (row && typeof row === 'object') {
            var flat = window.MapeiaAIStockCapture.flatten(row, '', {});
            if (!headers.length) headers = Object.keys(flat);
            return headers.map(function (header, idx) {
                var columnKey = columns[idx] && typeof columns[idx] === 'string' ? columns[idx] : '';
                return window.MapeiaAIStockCapture.cleanForKey(header, window.MapeiaAIStockCapture.valueFromObject(row, flat, header, columnKey));
            });
        }
        return [window.MapeiaAIStockCapture.clean(row)];
    }).filter(function (values) {
        return values.some(function (value) { return value.length > 0; });
    });
    return { headers: headers, rows: rows };
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
window.MapeiaAIStockCapture.columnStats = function (values) {
    var nonEmpty = values.filter(function (value) { return window.MapeiaAIStockCapture.clean(value).length > 0; });
    var unique = {};
    nonEmpty.forEach(function (value) { unique[window.MapeiaAIStockCapture.normalize(value)] = true; });
    var numeric = nonEmpty.filter(function (value) { return window.MapeiaAIStockCapture.numericPattern.test(window.MapeiaAIStockCapture.clean(value)); }).length;
    var money = nonEmpty.filter(function (value) { return window.MapeiaAIStockCapture.moneyPattern.test(window.MapeiaAIStockCapture.clean(value)); }).length;
    var status = nonEmpty.filter(function (value) { return window.MapeiaAIStockCapture.statusPattern.test(window.MapeiaAIStockCapture.clean(value)); }).length;
    var alpha = nonEmpty.filter(function (value) { return /[A-Za-zÀ-ÿ]{2,}/.test(window.MapeiaAIStockCapture.clean(value)); }).length;
    return { total: values.length, nonEmpty: nonEmpty.length, unique: Object.keys(unique).length, numeric: numeric, money: money, status: status, alpha: alpha };
};
window.MapeiaAIStockCapture.isInternalHeader = function (header) {
    var h = this.normalize(header).replace(/\s+/g, '_');
    return /^info[_\.]/.test(h) || /^color([_\.]|$)/.test(h) || /^api_mercado_livre/.test(h) || /mercado_livre_category/.test(h) || /rgb$/.test(h);
};
window.MapeiaAIStockCapture.isBrokenIdentifier = function (header, values) {
    var h = this.normalize(header);
    if (!/(sku|codigo|referencia|ean|gtin|barras|id)/.test(h)) return false;
    var stats = this.columnStats(values);
    if (!stats.nonEmpty) return true;
    if (stats.unique <= 2 && stats.total >= 20) return true;
    if (/(ean|gtin|barras)/.test(h) && stats.alpha > 0 && stats.numeric === 0) return true;
    return false;
};
window.MapeiaAIStockCapture.inferHeader = function (header, values) {
    var h = this.normalize(header).replace(/\s+/g, '_');
    var stats = this.columnStats(values);
    if (this.isBrokenIdentifier(header, values)) return '';
    if (this.isInternalHeader(header)) return '';
    if (stats.status >= Math.max(1, stats.nonEmpty * 0.7)) return 'Disponibilidade';
    if (stats.money >= Math.max(1, stats.nonEmpty * 0.7)) return 'Preco';
    if (/^(id|product_id|produto_id)$/.test(h)) return 'id';
    if (/^(sku|codigo|referencia|model|modelo|mpn)$/.test(h)) return h === 'model' ? 'model' : header;
    if (/^(name|nome|produto|descricao|description)$/.test(h)) return h === 'name' ? 'name' : header;
    if (/^(brand|marca)$/.test(h)) return 'Marca';
    if (/^(price|preco|valor|custo)$/.test(h)) return 'Preco';
    if (/^(price_of|availability|disponibilidade|situacao|status)$/.test(h)) return 'Disponibilidade';
    if (/^(ean|gtin|codigo_de_barras|codigo_barras|barras)$/.test(h)) return stats.numeric >= Math.max(1, stats.nonEmpty * 0.8) ? header : 'Marca';
    if (/(estoque|stock|saldo|quantidade|quantity|qtd|qty|inventory|inventario|balance|balanco|balanço)/.test(h)) return stats.numeric > 0 ? 'Estoque' : 'Disponibilidade';
    return '';
};
window.MapeiaAIStockCapture.sameColumnRatio = function (a, b) {
    var total = Math.max(a.length, b.length, 1);
    var same = 0;
    for (var i = 0; i < total; i++) {
        if (this.normalize(a[i] || '') === this.normalize(b[i] || '')) same++;
    }
    return same / total;
};
window.MapeiaAIStockCapture.prepareColumns = function (headers, rows) {
    var candidates = [];
    for (var i = 0; i < headers.length; i++) {
        var values = rows.map(function (row) { return window.MapeiaAIStockCapture.cleanForKey(headers[i], row[i]); });
        var inferred = this.inferHeader(headers[i], values);
        if (!inferred) continue;
        var stats = this.columnStats(values);
        if (!stats.nonEmpty) continue;
        if (/^Marca$/.test(inferred) && stats.numeric > 0 && stats.alpha === 0) continue;
        candidates.push({ idx: i, header: inferred, values: values, stats: stats });
    }
    var kept = [];
    var seenHeader = {};
    candidates.forEach(function (candidate) {
        var key = window.MapeiaAIStockCapture.normalize(candidate.header);
        if ((key === 'marca' || key === 'preco' || key === 'disponibilidade' || key === 'estoque') && seenHeader[key]) return;
        for (var k = 0; k < kept.length; k++) {
            if (window.MapeiaAIStockCapture.sameColumnRatio(candidate.values, kept[k].values) >= 0.98) return;
        }
        seenHeader[key] = true;
        kept.push(candidate);
    });
    if (!kept.length) {
        for (var all = 0; all < Math.min(headers.length, 12); all++) {
            kept.push({ idx: all, header: headers[all] || ('Coluna ' + (all + 1)), values: rows.map(function (row) { return window.MapeiaAIStockCapture.cleanForKey(headers[all], row[all]); }) });
        }
    }
    return {
        headers: kept.map(function (item) { return item.header; }),
        rows: rows.map(function (row) {
            return kept.map(function (item) { return window.MapeiaAIStockCapture.cleanForKey(headers[item.idx], row[item.idx]); });
        }).filter(function (values) {
            return values.some(function (value) { return value.length > 0; });
        })
    };
};
window.MapeiaAIStockCapture.qualityReport = function (headers, rows) {
    var hasIdentifier = false;
    var hasNumericStock = false;
    var hasAvailability = false;
    var hasPrice = false;
    for (var i = 0; i < headers.length; i++) {
        var h = this.normalize(headers[i]);
        var values = rows.map(function (row) { return row[i] || ''; });
        var stats = this.columnStats(values);
        if (/(id|sku|codigo|referencia|model|modelo|ean|gtin|barras|name|nome|produto|descricao)/.test(h) && stats.unique > 2) hasIdentifier = true;
        if (/(estoque|stock|saldo|quantidade|quantity|qtd|qty|inventory|inventario|balance|balanco|balanço)/.test(h) && stats.numeric > 0 && stats.status === 0) hasNumericStock = true;
        if (/(disponibilidade|status|situacao|availability)/.test(h) || stats.status > 0) hasAvailability = true;
        if (/(preco|price|valor|custo)/.test(h) || stats.money > 0) hasPrice = true;
    }
    var warnings = [];
    if (!hasIdentifier) warnings.push('missing_product_identifier');
    if (!hasNumericStock) warnings.push('missing_numeric_stock');
    return { status: warnings.length ? warnings.join('+') : 'ok', hasIdentifier: hasIdentifier, hasNumericStock: hasNumericStock, hasAvailability: hasAvailability, hasPrice: hasPrice };
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
        var prepared = this.prepareColumns(headers, rows);
        var outHeaders = prepared.headers;
        var bodyRows = prepared.rows;
        if (!bodyRows.length) {
            return JSON.stringify({ ok: false, reason: 'no_basic_rows_found', total: payload ? payload.total : rows.length, headers: headers, ajax_error: payload ? payload.error : '', method: payload ? payload.method : '' });
        }
        var quality = this.qualityReport(outHeaders, bodyRows);
        var html = '<!doctype html><html><head><meta charset="utf-8"><title>MapeiaAI estoque rapido</title>';
        html += '<meta name="mapeiaai_capture_type" content="stock_basic_html_only">';
        html += '<meta name="source_url" content="' + this.escapeHtml(window.location.href) + '">';
        html += '<meta name="source_total" content="' + this.escapeHtml(payload ? payload.total : bodyRows.length) + '">';
        html += '<meta name="capture_method" content="' + this.escapeHtml(payload ? payload.method : 'dom') + '">';
        html += '<meta name="stock_quality_status" content="' + this.escapeHtml(quality.status) + '">';
        html += '<meta name="stock_has_identifier" content="' + String(quality.hasIdentifier) + '">';
        html += '<meta name="stock_has_numeric_stock" content="' + String(quality.hasNumericStock) + '">';
        html += '<meta name="stock_has_availability" content="' + String(quality.hasAvailability) + '">';
        html += '<meta name="stock_has_price" content="' + String(quality.hasPrice) + '">';
        html += '</head><body>';
        html += '<h1>MapeiaAI - Controle de estoque rapido</h1>';
        html += '<p>Origem: ' + this.escapeHtml(window.location.href) + '</p>';
        html += '<p>Qualidade estoque: ' + this.escapeHtml(quality.status) + '</p>';
        html += '<table><thead><tr>';
        html += outHeaders.map(function (header) { return '<th>' + window.MapeiaAIStockCapture.escapeHtml(header) + '</th>'; }).join('');
        html += '</tr></thead><tbody>';
        bodyRows.forEach(function (values) {
            html += '<tr>' + values.map(function (value) { return '<td>' + window.MapeiaAIStockCapture.escapeHtml(value) + '</td>'; }).join('') + '</tr>';
        });
        html += '</tbody></table></body></html>';
        return JSON.stringify({ ok: true, count: bodyRows.length, columns: outHeaders.length, total: payload ? payload.total : bodyRows.length, method: payload ? payload.method : 'dom', quality_status: quality.status, has_identifier: quality.hasIdentifier, has_numeric_stock: quality.hasNumericStock, has_availability: quality.hasAvailability, has_price: quality.hasPrice, html: html });
    } catch (e) {
        return JSON.stringify({ ok: false, reason: String(e) });
    }
};
