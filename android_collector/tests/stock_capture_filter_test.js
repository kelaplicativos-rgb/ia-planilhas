const assert = require('assert');

global.window = global;
require('../app/src/main/assets/mapeiaai_stock_capture.js');

const capture = global.MapeiaAIStockCapture;

function prepare(headers, rows) {
  return capture.prepareColumns(headers, rows).headers;
}

function preparedRows(headers, rows) {
  return capture.prepareColumns(headers, rows).rows;
}

function quality(headers, rows) {
  const prepared = capture.prepareColumns(headers, rows);
  return capture.qualityReport(prepared.headers, prepared.rows);
}

const brokenHeaders = ['sku', 'ean', 'price', 'price_of'];
const brokenBaseRows = [
  ['" data-placement="right">', 'Veda Forte', 'R$ 79,80', 'Disponível'],
  ['" data-placement="right">', 'Bomvink', 'R$ 31,85', 'Disponível'],
  ['" data-placement="right"> ESGOTADO', 'Exbom', 'R$ 16,40', 'Esgotado'],
  ['" data-placement="right">', 'Genérica', 'R$ 67,14', 'Baixo'],
];
const brokenRows = Array.from({ length: 24 }, (_, index) => brokenBaseRows[index % brokenBaseRows.length]);
assert.deepStrictEqual(
  prepare(brokenHeaders, brokenRows),
  ['Preco', 'Disponibilidade'],
  'broken SKU/EAN data must be ignored instead of becoming product columns'
);
assert.strictEqual(quality(brokenHeaders, brokenRows).hasIdentifier, false);

const richHeaders = [
  'id', 'name', 'model', 'brand', 'price', 'brand.id', 'color_id', 'info_me',
  'info_qe', 'api_mercado_livre_category', 'brand.name', 'color', 'color.id',
  'color.name', 'color.rgb'
];
const richRows = [
  ['OOM-3124', 'Kit Borracha Liquida', 'KIT-VFBL500', 'Veda Forte', 'R$ 79,80', '3124', '3124', '0', '0', '', 'Kit Borracha Liquida', '#e7f5df', '3124', 'Kit Borracha Liquida', '000000'],
  ['OOM-3107', 'Alicate Amperimetro Digital', 'BOM-6004', 'Bomvink', 'R$ 31,85', '3107', '3107', '0', '0', 'MLB456027', 'Alicate Amperimetro Digital', '#fdf7de', '3107', 'Alicate Amperimetro Digital', '1717FF'],
  ['OOM-3000', 'Multimetro Digital', 'MD-100', 'Exbom', 'R$ 25,90', '3000', '3000', '1', '0', 'MLB5923', 'Multimetro Digital', '#f7e3e0', '3000', 'Multimetro Digital', 'FF0000'],
];
assert.deepStrictEqual(prepare(richHeaders, richRows), ['id', 'name', 'model', 'Marca', 'Preco']);
assert.strictEqual(quality(richHeaders, richRows).hasIdentifier, true);
assert.strictEqual(quality(richHeaders, richRows).hasNumericStock, false);

const stockHeaders = ['id', 'name', 'model', 'brand', 'price', 'stock'];
const stockRows = [
  ['A-1', 'Produto A', 'A100', 'Marca A', 'R$ 10,00', '5'],
  ['B-2', 'Produto B', 'B200', 'Marca B', 'R$ 20,00', '0'],
  ['C-3', 'Produto C', 'C300', 'Marca C', 'R$ 30,00', '12'],
];
assert.deepStrictEqual(prepare(stockHeaders, stockRows), ['id', 'name', 'model', 'Marca', 'Preco', 'Estoque']);
assert.strictEqual(quality(stockHeaders, stockRows).hasNumericStock, true);

const hiddenHeaders = ['id', 'name', 'model', 'brand', 'price', 'inventory'];
const hiddenRows = [
  ['OOM-1', 'Produto 1', 'P1', 'Marca A', 'R$ 10,00', '<span class="badge" title="8">Disponível</span>'],
  ['OOM-2', 'Produto 2', 'P2', 'Marca B', 'R$ 20,00', '<span data-original-title="2 unidades em estoque">Baixo</span>'],
  ['OOM-3', 'Produto 3', 'P3', 'Marca C', 'R$ 30,00', '<span class="badge">Esgotado</span>'],
];
assert.deepStrictEqual(prepare(hiddenHeaders, hiddenRows), ['id', 'name', 'model', 'Marca', 'Preco', 'Estoque']);
assert.deepStrictEqual(preparedRows(hiddenHeaders, hiddenRows).map((row) => row[5]), ['8', '2', '0']);
assert.strictEqual(quality(hiddenHeaders, hiddenRows).hasNumericStock, true);

console.log('stock_capture_filter_test: ok');
