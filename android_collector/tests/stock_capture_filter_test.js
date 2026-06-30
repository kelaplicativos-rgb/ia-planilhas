const assert = require('assert');

global.window = global;
require('../app/src/main/assets/mapeiaai_stock_capture.js');

const capture = global.MapeiaAIStockCapture;

function prepare(headers, rows) {
  return capture.prepareColumns(headers, rows).headers;
}

function quality(headers, rows) {
  const prepared = capture.prepareColumns(headers, rows);
  return capture.qualityReport(prepared.headers, prepared.rows);
}

const brokenHeaders = ['sku', 'ean', 'price', 'price_of'];
const brokenRows = [
  ['" data-placement="right">', 'Veda Forte', 'R$ 79,80', 'Disponível'],
  ['" data-placement="right">', 'Bomvink', 'R$ 31,85', 'Disponível'],
  ['" data-placement="right"> ESGOTADO', 'Exbom', 'R$ 16,40', 'Esgotado'],
  ['" data-placement="right">', 'Genérica', 'R$ 67,14', 'Baixo'],
];
assert.deepStrictEqual(prepare(brokenHeaders, brokenRows), ['Marca', 'Preco', 'Disponibilidade']);
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

console.log('stock_capture_filter_test: ok');
