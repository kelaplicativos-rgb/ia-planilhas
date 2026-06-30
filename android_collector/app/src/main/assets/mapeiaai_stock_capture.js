window.MapeiaAIStockCapture = window.MapeiaAIStockCapture || {};
(function () {
    var M = window.MapeiaAIStockCapture;

    M.numericPattern = /^-?\d+([,.]\d+)?$/;
    M.moneyPattern = /R\$\s*[\d\.]+,\d{2}|R\$\s*\d+/gi;

    M.decodeEntities = function (value) {
        return String(value == null ? '' : value)
            .replace(/&nbsp;/g, ' ')
            .replace(/&quot;/g, '"')
            .replace(/&#34;/g, '"')
            .replace(/&#39;/g, "'")
            .replace(/&amp;/g, '&')
            .replace(/&lt;/g, '<')
            .replace(/&gt;/g, '>');
    };

    M.clean = function (value) {
        return this.decodeEntities(value)
            .replace(/<script[\s\S]*?<\/script>/gi, ' ')
            .replace(/<style[\s\S]*?<\/style>/gi, ' ')
            .replace(/<[^>]*>/g, ' ')
            .replace(/\s+/g, ' ')
            .trim();
    };

    M.normalize = function (value) {
        return this.clean(value).toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
    };

    M.escapeHtml = function (value) {
        return this.clean(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    };

    M.normalizeNumber = function (value) {
        var v = String(value == null ? '' : value).replace(',', '.').replace(/[^0-9.\-]/g, '');
        if (!this.numericPattern.test(v)) return '';
        return v;
    };

    M.firstNonEmpty = function () {
        for (var i = 0; i < arguments.length; i++) {
            var v = this.clean(arguments[i]);
            if (v) return v;
        }
        return '';
    };

    M.absoluteUrl = function (url) {
        if (!url) return '';
        var cleaned = this.decodeEntities(String(url)).trim();
        if (!cleaned || /^#/i.test(cleaned)) return '';
        try { return new URL(cleaned, window.location.href).href; } catch (e) { return cleaned; }
    };

    M.getAttrValues = function (html, attrNames) {
        var raw = this.decodeEntities(html || '');
        var values = [];
        attrNames.forEach(function (attr) {
            var re = new RegExp(attr + '\\s*=\\s*(["\\'])(.*?)\\1', 'gi');
            var match;
            while ((match = re.exec(raw)) !== null) values.push(match[2]);
        });
        return values;
    };

    M.flatten = function (value, prefix, out) {
        out = out || {};
        if (value == null) return out;
        if (typeof value !== 'object') {
            if (prefix) out[prefix] = value;
            return out;
        }
        if (Array.isArray(value)) {
            out[prefix || 'valor'] = value.map(function (item) {
                return typeof item === 'object' ? JSON.stringify(item) : String(item == null ? '' : item);
            }).filter(Boolean).join(' | ');
            return out;
        }
        Object.keys(value).forEach(function (key) {
            var next = prefix ? prefix + '.' + key : key;
            var item = value[key];
            if (item != null && typeof item === 'object' && !Array.isArray(item)) M.flatten(item, next, out);
            else out[next] = Array.isArray(item) ? item.join(' | ') : item;
        });
        return out;
    };

    M.findValue = function (flat, patterns) {
        flat = flat || {};
        var keys = Object.keys(flat);
        for (var p = 0; p < patterns.length; p++) {
            for (var i = 0; i < keys.length; i++) {
                var nk = M.normalize(keys[i]).replace(/[^a-z0-9_\.]/g, '_');
                if (patterns[p].test(nk)) return flat[keys[i]];
            }
        }
        return '';
    };

    M.extractImageUrl = function (html) {
        var raw = this.decodeEntities(html || '');
        var attrs = this.getAttrValues(raw, ['data-original-title', 'title', 'data-bs-original-title']).join(' ');
        var source = attrs + ' ' + raw;
        var img = source.match(/<img[^>]+src=['"]([^'"]+)['"]/i);
        if (img && img[1]) return this.absoluteUrl(img[1]);
        var href = source.match(/href=['"]([^'"]+\.(?:jpg|jpeg|png|webp|gif)(?:\?[^'"]*)?)['"]/i);
        if (href && href[1]) return this.absoluteUrl(href[1]);
        var src = source.match(/src=['"]([^'"]+\.(?:jpg|jpeg|png|webp|gif)(?:\?[^'"]*)?)['"]/i);
        if (src && src[1]) return this.absoluteUrl(src[1]);
        var url = source.match(/https?:\/\/[^\s'"<>]+\.(?:jpg|jpeg|png|webp|gif)(?:\?[^\s'"<>]*)?/i);
        if (url && url[0]) return this.absoluteUrl(url[0]);
        return '';
    };

    M.extractProductId = function (html, flat) {
        var raw = this.decodeEntities(html || '');
        var idFromButton = raw.match(/data-id=['"]?(\d+)['"]?/i);
        if (idFromButton) return idFromButton[1];
        var direct = this.findValue(flat, [/^(id|product_id|produto_id)$/i, /(^|\.)id$/i]);
        return this.clean(direct).replace(/[^0-9A-Za-z_\-.]/g, '');
    };

    M.extractAvailability = function (html) {
        var text = this.normalize(html);
        if (/esgotado|sem previsao|sem estoque|indisponivel/.test(text)) return 'Esgotado';
        if (/baixo/.test(text)) return 'Baixo';
        if (/disponivel|em estoque/.test(text)) return 'Disponível';
        return '';
    };

    M.extractStock = function (html) {
        var raw = this.decodeEntities(html || '');
        var attrs = this.getAttrValues(raw, ['data-original-title', 'title', 'data-bs-original-title', 'data-title', 'data-stock', 'data-estoque', 'data-quantity', 'data-quantidade', 'data-qtd', 'data-qty', 'aria-label', 'value']).join(' | ');
        var combined = attrs + ' | ' + raw;
        var normalized = this.normalize(combined);
        var unitMatch = combined.match(/(-?\d+([,.]\d+)?)\s*(?:unid|unidade|unidades|pe[cç]as|pcs)\b/i);
        if (unitMatch) return this.normalizeNumber(unitMatch[1]);
        var stockMatch = combined.match(/(?:estoque|saldo|stock|quantity|quantidade|qtd|qty|inventory|available)[^0-9-]{0,80}(-?\d+([,.]\d+)?)/i);
        if (stockMatch) return this.normalizeNumber(stockMatch[1]);
        var rawNumber = this.clean(combined);
        if (this.numericPattern.test(rawNumber) && !/^\d{8,14}$/.test(rawNumber.replace(/\D/g, ''))) return this.normalizeNumber(rawNumber);
        if (/esgotado|sem previsao|sem estoque|indisponivel/.test(normalized)) return '0';
        return '';
    };

    M.extractPrices = function (html) {
        var raw = this.decodeEntities(html || '');
        var matches = raw.match(this.moneyPattern) || [];
        matches = matches.map(function (v) { return M.clean(v).replace(/\s+/g, ' '); }).filter(Boolean);
        if (!matches.length) return { de: '', final: '' };
        return { de: matches.length > 1 ? matches[0] : '', final: matches[matches.length - 1] };
    };

    M.extractBadges = function (html) {
        var raw = this.decodeEntities(html || '');
        var badges = [];
        var re = /<span[^>]*class=['"][^'"]*badge[^'"]*['"][^>]*>([\s\S]*?)<\/span>/gi;
        var match;
        while ((match = re.exec(raw)) !== null) {
            var text = this.clean(match[1]);
            var norm = this.normalize(text);
            if (!text || /disponivel|esgotado|baixo|sem previsao|mercado livre/.test(norm)) continue;
            badges.push(text);
        }
        var unique = {};
        return badges.filter(function (b) { var k = M.normalize(b); if (unique[k]) return false; unique[k] = true; return true; }).join(' | ');
    };

    M.extractDetailUrl = function (html) {
        var raw = this.decodeEntities(html || '');
        var hrefs = this.getAttrValues(raw, ['href', 'data-href', 'data-url']);
        for (var i = 0; i < hrefs.length; i++) {
            var url = this.absoluteUrl(hrefs[i]);
            if (/products?|produtos?|items?|detalhe|edit|show|admin/i.test(url) && !/\.(jpg|jpeg|png|webp|gif|svg|css|js)(\?|$)/i.test(url)) return url;
        }
        return '';
    };

    M.mapKnownHeader = function (header) {
        var h = this.normalize(header);
        if (/^sku$|codigo|referencia/.test(h)) return 'SKU';
        if (/foto|imagem|image|photo/.test(h)) return 'Imagem URL';
        if (/titulo|title|nome|produto|descricao|description|name/.test(h)) return 'Título';
        if (/modelo|model|mpn/.test(h)) return 'Modelo';
        if (/marca|brand/.test(h)) return 'Marca';
        if (/preco|price|valor|custo/.test(h)) return 'Preço';
        if (/estoque|stock|saldo|quantidade|quantity|qtd|qty|inventory|availability|disponibilidade|situacao|status/.test(h)) return 'Estoque';
        if (/acao|acoes|actions|integracao|integra/.test(h)) return 'Ações';
        if (/id|product_id|produto_id/.test(h)) return 'product_id';
        return header || '';
    };

    M.parseDomRow = function (row, headers) {
        var cells = Array.prototype.slice.call(row.children || []);
        var data = { product_id: '', sku: '', imagem_url: '', titulo: '', modelo: '', marca: '', preco_de: '', preco_final: '', disponibilidade: '', estoque: '', badges: '', integracao: '', detalhe_url: '' };
        cells.forEach(function (cell, idx) {
            var header = M.mapKnownHeader(headers[idx] || ('Coluna ' + (idx + 1)));
            var html = cell.innerHTML || cell.textContent || '';
            var text = M.clean(cell.textContent || html);
            if (header === 'SKU') data.sku = text;
            else if (header === 'Imagem URL') data.imagem_url = M.extractImageUrl(html);
            else if (header === 'Título') { data.titulo = text.replace(/\bKIT\b$/i, '').trim(); data.badges = M.firstNonEmpty(data.badges, M.extractBadges(html)); }
            else if (header === 'Modelo') data.modelo = text;
            else if (header === 'Marca') data.marca = text;
            else if (header === 'Preço') { var p = M.extractPrices(html); data.preco_de = p.de; data.preco_final = p.final || text; }
            else if (header === 'Estoque') { data.estoque = M.extractStock(html); data.disponibilidade = M.extractAvailability(html); }
            else if (header === 'Ações') { data.product_id = M.firstNonEmpty(data.product_id, M.extractProductId(html, {})); data.detalhe_url = M.firstNonEmpty(data.detalhe_url, M.extractDetailUrl(html)); }
            else if (/integra/i.test(header)) data.integracao = text;
            data.product_id = M.firstNonEmpty(data.product_id, M.extractProductId(html, {}));
            if (!data.imagem_url) data.imagem_url = M.extractImageUrl(html);
        });
        return data;
    };

    M.parseObjectRow = function (row) {
        var flat = this.flatten(row, '', {});
        var rawAll = JSON.stringify(row || {});
        var sku = this.findValue(flat, [/^sku$/i, /codigo/i, /referencia/i]);
        var imageHtml = this.findValue(flat, [/photo|foto|image|imagem|thumbnail|picture|avatar/i]);
        var title = this.findValue(flat, [/^name$/i, /titulo/i, /title/i, /descricao/i, /description/i, /produto/i]);
        var model = this.findValue(flat, [/^model$/i, /modelo/i, /mpn/i]);
        var brand = this.findValue(flat, [/brand_name/i, /^brand$/i, /marca/i]);
        var priceHtml = this.findValue(flat, [/price/i, /preco/i, /valor/i, /custo/i]);
        var stockHtml = this.findValue(flat, [/inventory/i, /estoque/i, /stock/i, /saldo/i, /availability/i, /disponibilidade/i, /quantidade/i, /quantity/i, /qtd/i]);
        var actionsHtml = this.findValue(flat, [/action/i, /acoes/i, /view/i, /edit/i]);
        var integration = this.findValue(flat, [/integration/i, /integracao/i, /integra/i]);
        var prices = this.extractPrices(priceHtml || rawAll);
        return {
            product_id: this.firstNonEmpty(this.extractProductId(actionsHtml || rawAll, flat), this.findValue(flat, [/^(id|product_id|produto_id)$/i])),
            sku: this.clean(sku),
            imagem_url: this.extractImageUrl(imageHtml || rawAll),
            titulo: this.clean(title),
            modelo: this.clean(model),
            marca: this.clean(brand),
            preco_de: prices.de,
            preco_final: prices.final || this.clean(priceHtml),
            disponibilidade: this.extractAvailability(stockHtml || rawAll),
            estoque: this.extractStock(stockHtml || rawAll),
            badges: this.extractBadges(title || rawAll),
            integracao: this.clean(integration),
            detalhe_url: this.extractDetailUrl(actionsHtml || rawAll)
        };
    };

    M.headersFromDom = function (table) {
        return Array.prototype.slice.call((table || document).querySelectorAll('thead th, thead td')).map(function (cell) { return M.clean(cell.textContent); });
    };

    M.domData = function () {
        var table = document.querySelector('table.datatable, table.dataTable, table');
        if (!table) return { rows: [], total: 0, method: 'dom_no_table' };
        var headers = this.headersFromDom(table);
        var bodyRows = Array.prototype.slice.call(table.querySelectorAll('tbody tr')).filter(function (tr) { return M.clean(tr.textContent); });
        return { rows: bodyRows.map(function (tr) { return M.parseDomRow(tr, headers); }), total: bodyRows.length, method: 'dom_visible_rows' };
    };

    M.dataTableContext = function () {
        if (!(window.jQuery && window.jQuery.fn && window.jQuery.fn.dataTable)) return null;
        var tables = window.jQuery.fn.dataTable.tables();
        if (!tables || !tables.length) return null;
        var table = tables[0];
        var dt = window.jQuery(table).DataTable();
        var info = dt.page.info ? dt.page.info() : {};
        var settings = dt.settings && dt.settings().length ? dt.settings()[0] : null;
        return { table: table, dt: dt, info: info, settings: settings };
    };

    M.appendParam = function (params, key, value) {
        if (value == null) return;
        if (Array.isArray(value)) { for (var i = 0; i < value.length; i++) this.appendParam(params, key + '[' + i + ']', value[i]); return; }
        if (typeof value === 'object') { Object.keys(value).forEach(function (child) { M.appendParam(params, key ? key + '[' + child + ']' : child, value[child]); }); return; }
        params.push(encodeURIComponent(key) + '=' + encodeURIComponent(String(value)));
    };

    M.encodeParams = function (data) {
        var params = [];
        Object.keys(data || {}).forEach(function (key) { M.appendParam(params, key, data[key]); });
        return params.join('&');
    };

    M.ajaxConfig = function (ctx) {
        var settings = ctx && ctx.settings ? ctx.settings : null;
        if (!settings) return null;
        var ajax = settings.ajax || settings.oInit && settings.oInit.ajax || settings.sAjaxSource || '';
        var url = '';
        var method = settings.sServerMethod || 'GET';
        if (typeof ajax === 'string') url = ajax;
        else if (ajax && typeof ajax === 'object') { url = ajax.url || ajax.sUrl || ''; method = ajax.type || ajax.method || method; }
        if (!url) return null;
        return { url: new URL(url, window.location.href).href, method: String(method || 'GET').toUpperCase() };
    };

    M.lastAjaxParams = function (ctx) {
        try { if (ctx && ctx.dt && ctx.dt.ajax && ctx.dt.ajax.params) { var params = ctx.dt.ajax.params(); if (params) return JSON.parse(JSON.stringify(params)); } } catch (e) {}
        return {};
    };

    M.syncAjax = function (config, data) {
        var body = this.encodeParams(data || {});
        var url = config.url;
        var method = config.method || 'GET';
        var xhr = new XMLHttpRequest();
        if (method === 'GET') { url += (url.indexOf('?') >= 0 ? '&' : '?') + body; xhr.open('GET', url, false); }
        else { xhr.open(method, url, false); xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded; charset=UTF-8'); }
        xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
        var csrf = document.querySelector('meta[name="csrf-token"], meta[name="csrf_token"]');
        if (csrf && csrf.content) xhr.setRequestHeader('X-CSRF-TOKEN', csrf.content);
        xhr.send(method === 'GET' ? null : body);
        if (xhr.status < 200 || xhr.status >= 300) throw new Error('ajax_status_' + xhr.status);
        return JSON.parse(xhr.responseText || '{}');
    };

    M.extractResponseRows = function (json) {
        if (!json) return [];
        return json.data || json.aaData || json.rows || json.products || json.items || [];
    };

    M.extractResponseTotal = function (json, fallback) {
        if (!json) return fallback || 0;
        return Number(json.recordsFiltered || json.recordsTotal || json.total || json.count || fallback || 0) || 0;
    };

    M.dataTablesData = function () {
        var ctx = this.dataTableContext();
        if (!ctx) return null;
        var config = this.ajaxConfig(ctx);
        var rows = [];
        var total = Number(ctx.info.recordsTotal || ctx.info.recordsDisplay || 0) || 0;
        var method = 'datatable_current_page';
        try {
            if (config) {
                var base = this.lastAjaxParams(ctx);
                var requestedLength = Math.max(50, Math.min(500, Number(ctx.info.length || 50) || 50));
                var start = 0;
                var guard = 0;
                method = 'ajax_all_pages';
                while (guard < 250) {
                    var params = JSON.parse(JSON.stringify(base || {}));
                    params.start = start;
                    params.length = requestedLength;
                    params.draw = (Number(params.draw || 0) || 0) + guard + 1;
                    var json = this.syncAjax(config, params);
                    var part = this.extractResponseRows(json);
                    total = Math.max(total, this.extractResponseTotal(json, total));
                    if (!part || !part.length) break;
                    rows = rows.concat(part);
                    if (total > 0 && rows.length >= total) break;
                    if (part.length < requestedLength) break;
                    start += part.length;
                    guard++;
                }
            }
        } catch (e) { rows = []; method = 'ajax_failed_' + String(e && e.message ? e.message : e); }
        if (!rows.length) { try { rows = ctx.dt.rows({ page: 'current' }).data().toArray(); } catch (ignore) { rows = []; } }
        return { rows: rows.map(function (row) { return M.parseObjectRow(row); }), total: total || rows.length, method: method };
    };

    M.mergeFallback = function (primary, fallback) {
        if (!primary || !primary.length) return fallback || [];
        if (!fallback || !fallback.length) return primary;
        var bySku = {};
        fallback.forEach(function (r) { if (r.sku) bySku[M.normalize(r.sku)] = r; });
        return primary.map(function (row, idx) {
            var fb = bySku[M.normalize(row.sku || '')] || fallback[idx] || {};
            Object.keys(row).forEach(function (key) { if (!row[key] && fb[key]) row[key] = fb[key]; });
            return row;
        });
    };

    M.qualityReport = function (rows) {
        var hasIdentifier = rows.some(function (r) { return !!(r.product_id || r.sku || r.modelo); });
        var hasNumericStock = rows.some(function (r) { return M.numericPattern.test(String(r.estoque || '')); });
        var hasAvailability = rows.some(function (r) { return !!r.disponibilidade; });
        var hasPrice = rows.some(function (r) { return !!r.preco_final; });
        var hasImages = rows.some(function (r) { return !!r.imagem_url; });
        var warnings = [];
        if (!hasIdentifier) warnings.push('missing_product_identifier');
        if (!hasNumericStock) warnings.push('missing_numeric_stock');
        if (!hasPrice) warnings.push('missing_price');
        if (!hasImages) warnings.push('missing_images');
        return { status: warnings.length ? warnings.join('+') : 'ok', hasIdentifier: hasIdentifier, hasNumericStock: hasNumericStock, hasAvailability: hasAvailability, hasPrice: hasPrice, hasImages: hasImages };
    };

    M.renderHtml = function (rows, sourceTotal, method, quality) {
        var headers = ['product_id', 'SKU', 'Imagem URL', 'Título', 'Modelo', 'Marca', 'Preço De', 'Preço Final', 'Disponibilidade', 'Estoque', 'Badges', 'Integração', 'Detalhe URL'];
        var html = '<!doctype html><html><head><meta charset="utf-8"><title>MapeiaAI produtos e estoque</title>';
        html += '<meta name="mapeiaai_capture_type" content="stock_products_full_html">';
        html += '<meta name="source_url" content="' + this.escapeHtml(window.location.href) + '">';
        html += '<meta name="source_total" content="' + this.escapeHtml(sourceTotal || rows.length) + '">';
        html += '<meta name="capture_method" content="' + this.escapeHtml(method) + '">';
        html += '<meta name="stock_quality_status" content="' + this.escapeHtml(quality.status) + '">';
        html += '<meta name="stock_has_identifier" content="' + String(quality.hasIdentifier) + '">';
        html += '<meta name="stock_has_numeric_stock" content="' + String(quality.hasNumericStock) + '">';
        html += '<meta name="stock_has_availability" content="' + String(quality.hasAvailability) + '">';
        html += '<meta name="stock_has_price" content="' + String(quality.hasPrice) + '">';
        html += '<meta name="stock_has_images" content="' + String(quality.hasImages) + '">';
        html += '</head><body><h1>MapeiaAI - Produtos e Estoque</h1>';
        html += '<p>Origem: ' + this.escapeHtml(window.location.href) + '</p>';
        html += '<p>Qualidade: ' + this.escapeHtml(quality.status) + '</p>';
        html += '<table><thead><tr>' + headers.map(function (h) { return '<th>' + M.escapeHtml(h) + '</th>'; }).join('') + '</tr></thead><tbody>';
        rows.forEach(function (r) {
            var values = [r.product_id, r.sku, r.imagem_url, r.titulo, r.modelo, r.marca, r.preco_de, r.preco_final, r.disponibilidade, r.estoque, r.badges, r.integracao, r.detalhe_url];
            html += '<tr>' + values.map(function (v) { return '<td>' + M.escapeHtml(v) + '</td>'; }).join('') + '</tr>';
        });
        html += '</tbody></table></body></html>';
        return html;
    };

    M.tableHtml = function () {
        try {
            var dom = this.domData();
            var dt = this.dataTablesData();
            var rows = dt && dt.rows && dt.rows.length ? this.mergeFallback(dt.rows, dom.rows) : dom.rows;
            rows = rows.filter(function (r) { return r && (r.sku || r.titulo || r.modelo || r.product_id); });
            var total = dt && dt.total ? dt.total : (dom.total || rows.length);
            var method = dt && dt.rows && dt.rows.length ? dt.method : dom.method;
            var quality = this.qualityReport(rows);
            if (!rows.length) return JSON.stringify({ ok: false, reason: 'no_rows_found', total: total, method: method, quality_status: quality.status });
            return JSON.stringify({ ok: true, count: rows.length, columns: 13, total: total, method: method, quality_status: quality.status, has_identifier: quality.hasIdentifier, has_numeric_stock: quality.hasNumericStock, has_availability: quality.hasAvailability, has_price: quality.hasPrice, has_images: quality.hasImages, html: this.renderHtml(rows, total, method, quality) });
        } catch (e) {
            return JSON.stringify({ ok: false, reason: String(e && e.message ? e.message : e) });
        }
    };
})();
