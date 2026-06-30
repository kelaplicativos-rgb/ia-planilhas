package br.com.mapeiaai.coletor;

import android.Manifest;
import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.provider.MediaStore;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;
import org.json.JSONTokener;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

public class MainActivity extends Activity {
    private static final int WRITE_REQUEST_CODE = 9101;
    private static final int MAX_AUTO_PAGES = 500;
    private static final int PRODUCT_TARGET_PAGE_LENGTH = 200;
    private static final int STOCK_TARGET_PAGE_LENGTH = 500;
    private static final long PRODUCT_PAGE_SETTLE_MS = 800;
    private static final long STOCK_PAGE_SETTLE_MS = 900;
    private static final long AUTO_NEXT_PAGE_MS = 200;
    private static final long DETAIL_OPEN_WAIT_MS = 300;
    private static final long DETAIL_NEXT_ITEM_MS = 120;

    private EditText urlInput;
    private TextView statusText;
    private ProgressBar progressBar;
    private WebView webView;
    private File captureDir;

    private int captureCount = 0;
    private int autoIndex = 0;
    private int autoPages = 0;
    private boolean autoRunning = false;
    private String activeCaptureMode = "none";

    private int productExpectedTotal = 0;
    private int productListRecordCount = 0;
    private int productPageFileCount = 0;
    private int productDetailCandidateCount = 0;
    private int productDetailFileCount = 0;
    private int productDetailRecordCount = 0;
    private String productCompletenessStatus = "not_started";
    private String productLastError = "";

    private int stockFileCount = 0;
    private int stockRecordCount = 0;
    private int stockExpectedTotal = 0;
    private String stockCompletenessStatus = "not_started";
    private String stockLastError = "";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        requestLegacyWritePermissionIfNeeded();
        buildLayout();
        configureWebView();
        setStatus("Abra o site, faça login e escolha uma das duas coletas: estoque ou cadastro completo.");
    }

    @SuppressLint("SetJavaScriptEnabled")
    private void configureWebView() {
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setLoadsImagesAutomatically(true);
        settings.setBlockNetworkImage(false);
        settings.setUseWideViewPort(true);
        settings.setLoadWithOverviewMode(true);
        settings.setBuiltInZoomControls(true);
        settings.setDisplayZoomControls(false);
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                setStatus("Página carregada: " + url);
            }
        });
    }

    private void buildLayout() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(12, 12, 12, 12);

        TextView title = new TextView(this);
        title.setText("MapeiaAI Coletor Android");
        title.setTextSize(20);
        title.setPadding(0, 0, 0, 8);
        root.addView(title, new LinearLayout.LayoutParams(-1, -2));

        urlInput = new EditText(this);
        urlInput.setSingleLine(true);
        urlInput.setHint("https://fornecedor.com.br/admin/produtos");
        root.addView(urlInput, new LinearLayout.LayoutParams(-1, -2));

        Button openButton = new Button(this);
        openButton.setText("Abrir site / login");
        openButton.setOnClickListener(v -> openSite());
        root.addView(openButton, new LinearLayout.LayoutParams(-1, -2));

        LinearLayout actions = new LinearLayout(this);
        actions.setOrientation(LinearLayout.VERTICAL);

        Button stockButton = new Button(this);
        stockButton.setText("Atualização de estoque - coletar todos");
        stockButton.setOnClickListener(v -> startStockOnlyDatatablesCapture());
        actions.addView(stockButton, new LinearLayout.LayoutParams(-1, -2));

        Button productButton = new Button(this);
        productButton.setText("Cadastro de produtos - coleta completa");
        productButton.setOnClickListener(v -> startProductFullDatatablesCapture());
        actions.addView(productButton, new LinearLayout.LayoutParams(-1, -2));

        Button zipButton = new Button(this);
        zipButton.setText("Gerar ZIP validado");
        zipButton.setOnClickListener(v -> createZipForMapeiaAI());
        actions.addView(zipButton, new LinearLayout.LayoutParams(-1, -2));

        root.addView(actions, new LinearLayout.LayoutParams(-1, -2));

        progressBar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progressBar.setMax(100);
        progressBar.setProgress(0);
        root.addView(progressBar, new LinearLayout.LayoutParams(-1, -2));

        ScrollView statusScroll = new ScrollView(this);
        statusText = new TextView(this);
        statusText.setTextSize(13);
        statusText.setPadding(0, 8, 0, 8);
        statusScroll.addView(statusText);
        root.addView(statusScroll, new LinearLayout.LayoutParams(-1, 140));

        webView = new WebView(this);
        root.addView(webView, new LinearLayout.LayoutParams(-1, 0, 1));

        setContentView(root);
    }

    private void openSite() {
        String url = urlInput.getText().toString().trim();
        if (url.length() == 0) {
            toast("Informe o site primeiro.");
            return;
        }
        if (!url.startsWith("http://") && !url.startsWith("https://")) {
            url = "https://" + url;
            urlInput.setText(url);
        }
        resetCaptureSession();
        setStatus("Abrindo: " + url + "\nFaça login normalmente e vá até a tela/lista de produtos.");
        webView.loadUrl(url);
    }

    private void resetCaptureSession() {
        captureCount = 0;
        autoIndex = 0;
        autoPages = 0;
        autoRunning = false;
        activeCaptureMode = "none";
        captureDir = null;
        resetProductState();
        resetStockState();
        progressBar.setProgress(0);
        setAutoPerformanceMode(false);
    }

    private void resetProductState() {
        productExpectedTotal = 0;
        productListRecordCount = 0;
        productPageFileCount = 0;
        productDetailCandidateCount = 0;
        productDetailFileCount = 0;
        productDetailRecordCount = 0;
        productCompletenessStatus = "not_started";
        productLastError = "";
    }

    private void resetStockState() {
        stockFileCount = 0;
        stockRecordCount = 0;
        stockExpectedTotal = 0;
        stockCompletenessStatus = "not_started";
        stockLastError = "";
    }

    private void setAutoPerformanceMode(boolean enabled) {
        if (webView == null) return;
        WebSettings settings = webView.getSettings();
        settings.setLoadsImagesAutomatically(!enabled);
        settings.setBlockNetworkImage(enabled);
    }

    private File ensureCaptureDir() {
        if (captureDir != null && captureDir.exists()) return captureDir;
        String stamp = new SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(new Date());
        captureDir = new File(getCacheDir(), "mapeiaai_android_capture_" + stamp);
        if (!captureDir.exists()) captureDir.mkdirs();
        return captureDir;
    }

    private String nextBaseName(String label) {
        String safeLabel = String.valueOf(label == null ? "pagina" : label).replaceAll("[^a-zA-Z0-9_-]", "_");
        String number = String.format(Locale.US, "%03d", captureCount + 1);
        return "mapeiaai_android_" + number + "_" + safeLabel;
    }

    private String nextProductDetailBaseName(String label) {
        String safeLabel = String.valueOf(label == null ? "pagina" : label).replaceAll("[^a-zA-Z0-9_-]", "_");
        String number = String.format(Locale.US, "%03d", productDetailFileCount + 1);
        return "mapeiaai_android_product_detail_" + number + "_" + safeLabel + "_detalhes";
    }

    private String nextStockBaseName(String label) {
        String safeLabel = String.valueOf(label == null ? "estoque" : label).replaceAll("[^a-zA-Z0-9_-]", "_");
        String number = String.format(Locale.US, "%03d", stockFileCount + 1);
        return "mapeiaai_android_stock_" + number + "_" + safeLabel;
    }

    private void startProductFullDatatablesCapture() {
        if (autoRunning) {
            toast("Captura automática já está rodando.");
            return;
        }
        resetProductState();
        activeCaptureMode = "products";
        productCompletenessStatus = "running";
        setAutoPerformanceMode(true);
        setStatus("Cadastro completo: vou varrer todos os produtos, salvar HTML da lista e detalhes disponíveis, e validar o total.");
        String js = "(function(){try{if(!(window.jQuery&&window.jQuery.fn&&window.jQuery.fn.dataTable)){return JSON.stringify({ok:false,reason:'datatable_not_found'});}var tables=window.jQuery.fn.dataTable.tables();if(!tables.length){return JSON.stringify({ok:false,reason:'table_not_found'});}var dt=window.jQuery(tables[0]).DataTable();try{dt.page.len(" + PRODUCT_TARGET_PAGE_LENGTH + ").draw(false);}catch(e){}return JSON.stringify({ok:true});}catch(e){return JSON.stringify({ok:false,reason:String(e)});}})()";
        webView.evaluateJavascript(js, value -> webView.postDelayed(this::readProductDatatablesInfoAndStart, PRODUCT_PAGE_SETTLE_MS));
    }

    private void readProductDatatablesInfoAndStart() {
        String js = dataTablesInfoScript();
        webView.evaluateJavascript(js, value -> {
            try {
                JSONObject data = new JSONObject(decodeJsValue(value));
                if (!data.optBoolean("ok")) {
                    setAutoPerformanceMode(false);
                    productCompletenessStatus = "failed_no_datatable";
                    productLastError = data.optString("reason", "datatable_not_found");
                    setStatus("Não encontrei tabela paginada de produtos. Vá até a tela/lista correta e tente novamente.");
                    return;
                }
                autoPages = Math.min(MAX_AUTO_PAGES, Math.max(1, data.optInt("pages", 1)));
                autoIndex = 0;
                autoRunning = true;
                productExpectedTotal = Math.max(0, data.optInt("total", 0));
                int pageLength = data.optInt("pageLength", 0);
                setStatus("Cadastro completo detectado: " + autoPages + " página(s), esperado " + productExpectedTotal + " produto(s), até " + pageLength + " por página.");
                captureProductDataTablePage();
            } catch (Exception exc) {
                setAutoPerformanceMode(false);
                productCompletenessStatus = "failed_start";
                productLastError = exc.getMessage();
                setStatus("Não consegui iniciar cadastro completo: " + exc.getMessage());
            }
        });
    }

    private void captureProductDataTablePage() {
        if (!autoRunning || autoIndex >= autoPages) {
            autoRunning = false;
            setAutoPerformanceMode(false);
            progressBar.setProgress(100);
            updateProductCompletenessStatus();
            setStatus(productCompletionMessage() + " Toque em Gerar ZIP validado.");
            return;
        }
        String script = "(function(){try{var tables=window.jQuery.fn.dataTable.tables();var dt=window.jQuery(tables[0]).DataTable();dt.page(" + autoIndex + ").draw(false);return JSON.stringify({ok:true,page:" + autoIndex + "});}catch(e){return JSON.stringify({ok:false,error:String(e)});}})()";
        webView.evaluateJavascript(script, value -> webView.postDelayed(() -> {
            String label = "produtos_" + String.format(Locale.US, "%03d", autoIndex + 1);
            setStatus("Capturando cadastro " + label + " de " + autoPages + "...");
            readCurrentDataTableRowCount(count -> {
                productListRecordCount += count;
                saveCurrentHtmlSnapshot(label, () -> {
                    captureCount++;
                    productPageFileCount++;
                    runDetailCaptureForCurrentPage(label, () -> {
                        int progress = autoPages > 0 ? Math.min(99, (int) (((autoIndex + 1) * 100.0f) / autoPages)) : Math.min(99, captureCount * 4);
                        progressBar.setProgress(progress);
                        setStatus("Cadastro salvo: lista " + productListRecordCount + "/" + productExpectedTotal + ", detalhes " + productDetailRecordCount + "/" + productDetailCandidateCount + ".");
                        autoIndex++;
                        webView.postDelayed(this::captureProductDataTablePage, AUTO_NEXT_PAGE_MS);
                    });
                });
            });
        }, PRODUCT_PAGE_SETTLE_MS));
    }

    private void startStockOnlyDatatablesCapture() {
        if (autoRunning) {
            toast("Captura automática já está rodando.");
            return;
        }
        resetStockState();
        activeCaptureMode = "stock";
        stockCompletenessStatus = "running";
        setAutoPerformanceMode(true);
        setStatus("Atualização de estoque: vou varrer até o último produto e validar o total capturado.");
        String js = "(function(){try{if(!(window.jQuery&&window.jQuery.fn&&window.jQuery.fn.dataTable)){return JSON.stringify({ok:false,reason:'datatable_not_found'});}var tables=window.jQuery.fn.dataTable.tables();if(!tables.length){return JSON.stringify({ok:false,reason:'table_not_found'});}var dt=window.jQuery(tables[0]).DataTable();try{dt.page.len(" + STOCK_TARGET_PAGE_LENGTH + ").draw(false);}catch(e){}return JSON.stringify({ok:true});}catch(e){return JSON.stringify({ok:false,reason:String(e)});}})()";
        webView.evaluateJavascript(js, value -> webView.postDelayed(this::readStockDatatablesInfoAndStart, STOCK_PAGE_SETTLE_MS));
    }

    private void readStockDatatablesInfoAndStart() {
        String js = dataTablesInfoScript();
        webView.evaluateJavascript(js, value -> {
            try {
                JSONObject data = new JSONObject(decodeJsValue(value));
                if (!data.optBoolean("ok")) {
                    setAutoPerformanceMode(false);
                    stockCompletenessStatus = "failed_no_datatable";
                    stockLastError = data.optString("reason", "datatable_not_found");
                    setStatus("Não encontrei tabela paginada para estoque. Vá até a tela/lista correta e tente novamente.");
                    return;
                }
                autoPages = Math.min(MAX_AUTO_PAGES, Math.max(1, data.optInt("pages", 1)));
                autoIndex = 0;
                autoRunning = true;
                stockExpectedTotal = Math.max(0, data.optInt("total", 0));
                int pageLength = data.optInt("pageLength", 0);
                setStatus("Estoque detectado: " + autoPages + " página(s), esperado " + stockExpectedTotal + " produto(s), até " + pageLength + " por página.");
                captureStockDataTablePage();
            } catch (Exception exc) {
                setAutoPerformanceMode(false);
                stockCompletenessStatus = "failed_start";
                stockLastError = exc.getMessage();
                setStatus("Não consegui iniciar estoque: " + exc.getMessage());
            }
        });
    }

    private void captureStockDataTablePage() {
        if (!autoRunning || autoIndex >= autoPages) {
            autoRunning = false;
            setAutoPerformanceMode(false);
            progressBar.setProgress(100);
            updateStockCompletenessStatus();
            setStatus(stockCompletionMessage() + " Toque em Gerar ZIP validado.");
            return;
        }
        String script = "(function(){try{var tables=window.jQuery.fn.dataTable.tables();var dt=window.jQuery(tables[0]).DataTable();dt.page(" + autoIndex + ").draw(false);return JSON.stringify({ok:true,page:" + autoIndex + "});}catch(e){return JSON.stringify({ok:false,error:String(e)});}})()";
        webView.evaluateJavascript(script, value -> webView.postDelayed(() -> {
            String label = "estoque_" + String.format(Locale.US, "%03d", autoIndex + 1);
            setStatus("Capturando estoque " + label + " de " + autoPages + "...");
            saveCurrentStockTableHtml(label, () -> {
                autoIndex++;
                webView.postDelayed(this::captureStockDataTablePage, AUTO_NEXT_PAGE_MS);
            });
        }, STOCK_PAGE_SETTLE_MS));
    }

    private void saveCurrentStockTableHtml(String label, Runnable afterStock) {
        loadStockCaptureScript(() -> {
            String script = "(function(){try{if(!window.MapeiaAIStockCapture){return JSON.stringify({ok:false,reason:'stock_script_missing'});}return window.MapeiaAIStockCapture.tableHtml();}catch(e){return JSON.stringify({ok:false,reason:String(e)});}})()";
            webView.evaluateJavascript(script, value -> {
                try {
                    JSONObject data = new JSONObject(decodeJsValue(value));
                    int total = data.optInt("total", 0);
                    if (total > stockExpectedTotal) stockExpectedTotal = total;
                    if (data.optBoolean("ok")) {
                        String html = data.optString("html", "");
                        int count = data.optInt("count", 0);
                        if (html.trim().length() > 0 && count > 0) {
                            File dir = ensureCaptureDir();
                            File out = new File(dir, nextStockBaseName(label) + ".html");
                            try (FileOutputStream fos = new FileOutputStream(out)) {
                                fos.write(html.getBytes("UTF-8"));
                            }
                            stockFileCount++;
                            stockRecordCount += count;
                            captureCount++;
                            int progress = autoPages > 0 ? Math.min(99, (int) (((autoIndex + 1) * 100.0f) / autoPages)) : Math.min(99, captureCount * 4);
                            progressBar.setProgress(progress);
                            setStatus("Estoque salvo: " + count + " item(ns). Total capturado: " + stockRecordCount + "/" + stockExpectedTotal + ".");
                        } else {
                            stockLastError = "empty_html_or_zero_count";
                            setStatus("Aviso: página de estoque sem linhas. Capturado: " + stockRecordCount + "/" + stockExpectedTotal + ".");
                        }
                    } else {
                        stockLastError = data.optString("reason", "stock_capture_failed");
                        setStatus("Aviso: estoque não capturado nesta página: " + stockLastError + ". Capturado: " + stockRecordCount + "/" + stockExpectedTotal + ".");
                    }
                } catch (Exception exc) {
                    stockLastError = exc.getMessage();
                    setStatus("Aviso: erro ao salvar estoque: " + exc.getMessage());
                }
                if (afterStock != null) afterStock.run();
            });
        });
    }

    private void saveCurrentHtmlSnapshot(String label, Runnable afterHtml) {
        String script = "(function(){try{return '<!doctype html>\\n'+document.documentElement.outerHTML;}catch(e){return '';}})()";
        webView.evaluateJavascript(script, value -> {
            try {
                String html = decodeJsValue(value);
                if (html != null && html.trim().length() > 0) {
                    File dir = ensureCaptureDir();
                    File out = new File(dir, nextBaseName(label) + ".html");
                    try (FileOutputStream fos = new FileOutputStream(out)) {
                        fos.write(html.getBytes("UTF-8"));
                    }
                }
            } catch (Exception ignored) {
                setStatus("Aviso: HTML simples não foi salvo.");
            }
            if (afterHtml != null) afterHtml.run();
        });
    }

    private void runDetailCaptureForCurrentPage(String pageLabel, Runnable afterDetails) {
        if (webView.getUrl() == null || webView.getUrl().trim().length() == 0) {
            if (afterDetails != null) afterDetails.run();
            return;
        }
        loadDetailCaptureScript(() -> {
            String init = "(function(){try{if(!window.MapeiaAIDetailCapture){return JSON.stringify({ok:false,reason:'detail_script_missing'});}return window.MapeiaAIDetailCapture.init();}catch(e){return JSON.stringify({ok:false,reason:String(e)});}})()";
            webView.evaluateJavascript(init, value -> {
                try {
                    JSONObject data = new JSONObject(decodeJsValue(value));
                    if (!data.optBoolean("ok")) {
                        productLastError = data.optString("reason", "detail_capture_unavailable");
                        if (afterDetails != null) afterDetails.run();
                        return;
                    }
                    JSONArray items = data.optJSONArray("items");
                    int count = data.optInt("count", items == null ? 0 : items.length());
                    if (count > 0) productDetailCandidateCount += count;
                    if (items == null || count <= 0) {
                        if (afterDetails != null) afterDetails.run();
                        return;
                    }
                    setStatus("Capturando detalhes HTML de " + count + " produto(s) em " + pageLabel + "...");
                    collectDetailItem(pageLabel, items, 0, new JSONArray(), afterDetails);
                } catch (Exception exc) {
                    productLastError = exc.getMessage();
                    if (afterDetails != null) afterDetails.run();
                }
            });
        });
    }

    private void collectDetailItem(String pageLabel, JSONArray items, int index, JSONArray records, Runnable afterDetails) {
        if (index >= items.length()) {
            saveDetailRecordsHtml(pageLabel, records, afterDetails);
            return;
        }
        JSONObject item = items.optJSONObject(index);
        if (item == null) item = new JSONObject();
        int detailIndex = item.optInt("index", index);
        String itemJson = JSONObject.quote(item.toString());
        String clickScript = "(function(){try{return window.MapeiaAIDetailCapture.click(" + detailIndex + ");}catch(e){return JSON.stringify({ok:false,reason:String(e)});}})()";
        webView.evaluateJavascript(clickScript, clickValue -> webView.postDelayed(() -> {
            String readScript = "(function(){try{return window.MapeiaAIDetailCapture.read(" + itemJson + ");}catch(e){return JSON.stringify({ok:false,reason:String(e)});}})()";
            webView.evaluateJavascript(readScript, readValue -> {
                try {
                    JSONObject data = new JSONObject(decodeJsValue(readValue));
                    JSONObject record = data.optJSONObject("record");
                    if (data.optBoolean("ok") && record != null) {
                        record.put("detail_index", index + 1);
                        records.put(record);
                    }
                } catch (Exception ignored) {
                    // Continua mesmo quando um detalhe individual falha.
                }
                setStatus("Detalhes capturados: " + records.length() + "/" + items.length());
                closeDetailOverlay(() -> webView.postDelayed(() -> collectDetailItem(pageLabel, items, index + 1, records, afterDetails), DETAIL_NEXT_ITEM_MS));
            });
        }, DETAIL_OPEN_WAIT_MS));
    }

    private void saveDetailRecordsHtml(String pageLabel, JSONArray records, Runnable afterDetails) {
        if (records.length() == 0) {
            if (afterDetails != null) afterDetails.run();
            return;
        }
        String recordsJson = JSONObject.quote(records.toString());
        String tableScript = "(function(){try{return window.MapeiaAIDetailCapture.tableHtml(" + recordsJson + ");}catch(e){return JSON.stringify({ok:false,reason:String(e)});}})()";
        webView.evaluateJavascript(tableScript, value -> {
            try {
                JSONObject data = new JSONObject(decodeJsValue(value));
                String html = data.optString("html", "");
                if (data.optBoolean("ok") && html.trim().length() > 0) {
                    File dir = ensureCaptureDir();
                    File out = new File(dir, nextProductDetailBaseName(pageLabel) + ".html");
                    try (FileOutputStream fos = new FileOutputStream(out)) {
                        fos.write(html.getBytes("UTF-8"));
                    }
                    productDetailFileCount++;
                    productDetailRecordCount += records.length();
                    setStatus("Detalhes salvos: " + records.length() + " produto(s) em " + out.getName());
                }
            } catch (Exception exc) {
                productLastError = exc.getMessage();
                setStatus("Aviso: não consegui salvar HTML de detalhes: " + exc.getMessage());
            }
            if (afterDetails != null) afterDetails.run();
        });
    }

    private void readCurrentDataTableRowCount(RowCountCallback callback) {
        String js = "(function(){try{if(!(window.jQuery&&window.jQuery.fn&&window.jQuery.fn.dataTable)){return '0';}var tables=window.jQuery.fn.dataTable.tables();if(!tables.length){return '0';}var dt=window.jQuery(tables[0]).DataTable();return String(dt.rows({page:'current'}).data().toArray().length||0);}catch(e){return '0';}})()";
        webView.evaluateJavascript(js, value -> {
            int count = 0;
            try {
                count = Integer.parseInt(decodeJsValue(value));
            } catch (Exception ignored) {
                count = 0;
            }
            callback.onRowCount(count);
        });
    }

    private String dataTablesInfoScript() {
        return "(function(){try{if(!(window.jQuery&&window.jQuery.fn&&window.jQuery.fn.dataTable)){return JSON.stringify({ok:false,reason:'datatable_not_found'});}var tables=window.jQuery.fn.dataTable.tables();if(!tables.length){return JSON.stringify({ok:false,reason:'table_not_found'});}var dt=window.jQuery(tables[0]).DataTable();var info=dt.page.info();return JSON.stringify({ok:true,pages:info.pages,total:info.recordsTotal||info.recordsDisplay||0,pageLength:info.length||0});}catch(e){return JSON.stringify({ok:false,reason:String(e)});}})()";
    }

    private void updateProductCompletenessStatus() {
        boolean listComplete = productExpectedTotal > 0 && productListRecordCount >= productExpectedTotal;
        boolean detailsComplete = productDetailCandidateCount == 0 || productDetailRecordCount >= productDetailCandidateCount;
        if (listComplete && detailsComplete) {
            productCompletenessStatus = productDetailCandidateCount == 0 ? "complete_list_only_no_detail_buttons" : "complete";
            return;
        }
        if (productListRecordCount <= 0) {
            productCompletenessStatus = productExpectedTotal > 0 ? "failed_zero_records" : "failed_no_total";
            if (productLastError.length() == 0) productLastError = "no_products_captured";
            return;
        }
        if (!detailsComplete) {
            productCompletenessStatus = "incomplete_details";
            if (productLastError.length() == 0) productLastError = "some_product_details_not_captured";
            return;
        }
        productCompletenessStatus = "incomplete_list";
        if (productLastError.length() == 0) productLastError = "captured_less_than_expected";
    }

    private void updateStockCompletenessStatus() {
        if (stockExpectedTotal > 0 && stockRecordCount >= stockExpectedTotal) {
            stockCompletenessStatus = "complete";
            return;
        }
        if (stockRecordCount <= 0) {
            stockCompletenessStatus = stockExpectedTotal > 0 ? "failed_zero_records" : "failed_no_total";
            if (stockLastError.length() == 0) stockLastError = "no_products_captured";
            return;
        }
        stockCompletenessStatus = "incomplete";
        if (stockLastError.length() == 0) stockLastError = "captured_less_than_expected";
    }

    private String productCompletionMessage() {
        if ("complete".equals(productCompletenessStatus)) {
            return "VALIDADO: cadastro completo, " + productListRecordCount + "/" + productExpectedTotal + " produto(s) e " + productDetailRecordCount + " detalhe(s) capturados.";
        }
        if ("complete_list_only_no_detail_buttons".equals(productCompletenessStatus)) {
            return "VALIDADO: lista completa, " + productListRecordCount + "/" + productExpectedTotal + " produto(s). Nenhum detalhe separado foi encontrado nessa tela.";
        }
        if (productExpectedTotal > 0) {
            int missing = Math.max(0, productExpectedTotal - productListRecordCount);
            return "ATENÇÃO: cadastro incompleto, lista " + productListRecordCount + "/" + productExpectedTotal + ", faltando " + missing + ". Detalhes " + productDetailRecordCount + "/" + productDetailCandidateCount + ". Motivo: " + productLastError + ".";
        }
        return "ATENÇÃO: não consegui validar o total de produtos para cadastro. Capturados na lista: " + productListRecordCount + ". Motivo: " + productLastError + ".";
    }

    private String stockCompletionMessage() {
        if ("complete".equals(stockCompletenessStatus)) {
            return "VALIDADO: estoque completo, " + stockRecordCount + "/" + stockExpectedTotal + " produto(s) capturados.";
        }
        if (stockExpectedTotal > 0) {
            int missing = Math.max(0, stockExpectedTotal - stockRecordCount);
            return "ATENÇÃO: estoque incompleto, " + stockRecordCount + "/" + stockExpectedTotal + " produto(s). Faltando: " + missing + ". Motivo: " + stockLastError + ".";
        }
        return "ATENÇÃO: não consegui validar o total de produtos para estoque. Capturados: " + stockRecordCount + ". Motivo: " + stockLastError + ".";
    }

    private void createZipForMapeiaAI() {
        File dir = ensureCaptureDir();
        File[] files = dir.listFiles();
        if (files == null || files.length == 0) {
            toast("Nenhuma captura foi gerada ainda.");
            return;
        }
        try {
            writeManifest(dir);
            String stamp = new SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(new Date());
            File zipFile = new File(getCacheDir(), "mapeiaai_capturas_android_" + stamp + ".zip");
            zipDirectory(dir, zipFile);
            saveZipToDownloads(zipFile);
            progressBar.setProgress(100);
            if ("stock".equals(activeCaptureMode) && !"complete".equals(stockCompletenessStatus)) {
                setStatus("ZIP gerado, mas com alerta. " + stockCompletionMessage());
                toast("ZIP gerado com alerta: estoque incompleto.");
                return;
            }
            if ("products".equals(activeCaptureMode) && !("complete".equals(productCompletenessStatus) || "complete_list_only_no_detail_buttons".equals(productCompletenessStatus))) {
                setStatus("ZIP gerado, mas com alerta. " + productCompletionMessage());
                toast("ZIP gerado com alerta: cadastro incompleto.");
                return;
            }
            setStatus("ZIP validado e salvo em Downloads: " + zipFile.getName() + "\nAnexe esse ZIP no MapeiaAI.");
            toast("ZIP validado salvo em Downloads.");
        } catch (Exception exc) {
            setStatus("Erro ao gerar ZIP: " + exc.getMessage());
            toast("Erro ao gerar ZIP.");
        }
    }

    private void writeManifest(File dir) throws Exception {
        if ("stock".equals(activeCaptureMode) && stockFileCount > 0) updateStockCompletenessStatus();
        if ("products".equals(activeCaptureMode) && productPageFileCount > 0) updateProductCompletenessStatus();
        JSONObject manifest = new JSONObject();
        manifest.put("schema_version", "mapeiaai_android_collector_v6_two_validated_flows");
        manifest.put("generated_at", new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US).format(new Date()));
        manifest.put("start_url", urlInput.getText().toString().trim());
        manifest.put("current_url", webView.getUrl());
        manifest.put("capture_mode", activeCaptureMode);
        manifest.put("pages_captured", captureCount);

        manifest.put("product_expected_total", productExpectedTotal);
        manifest.put("product_list_records", productListRecordCount);
        manifest.put("product_page_files", productPageFileCount);
        manifest.put("product_detail_candidates", productDetailCandidateCount);
        manifest.put("product_detail_files", productDetailFileCount);
        manifest.put("product_detail_records", productDetailRecordCount);
        manifest.put("product_missing_records", Math.max(0, productExpectedTotal - productListRecordCount));
        manifest.put("product_capture_complete", "complete".equals(productCompletenessStatus) || "complete_list_only_no_detail_buttons".equals(productCompletenessStatus));
        manifest.put("product_completeness_status", productCompletenessStatus);
        manifest.put("product_last_error", productLastError);

        manifest.put("stock_files", stockFileCount);
        manifest.put("stock_records", stockRecordCount);
        manifest.put("stock_expected_total", stockExpectedTotal);
        manifest.put("stock_missing_records", Math.max(0, stockExpectedTotal - stockRecordCount));
        manifest.put("stock_capture_complete", "complete".equals(stockCompletenessStatus));
        manifest.put("stock_completeness_status", stockCompletenessStatus);
        manifest.put("stock_last_error", stockLastError);

        manifest.put("detail_capture_marker", GtinCaptureMarker.VERSION);
        manifest.put("product_target_page_length", PRODUCT_TARGET_PAGE_LENGTH);
        manifest.put("stock_target_page_length", STOCK_TARGET_PAGE_LENGTH);
        manifest.put("format", "html_only:stock_basic_html_or_product_full_html_validated");
        File out = new File(dir, "mapeiaai_android_manifest.json");
        try (FileOutputStream fos = new FileOutputStream(out)) {
            fos.write(manifest.toString(2).getBytes("UTF-8"));
        }
    }

    private void zipDirectory(File dir, File zipFile) throws Exception {
        try (ZipOutputStream zos = new ZipOutputStream(new FileOutputStream(zipFile))) {
            File[] files = dir.listFiles();
            if (files == null) return;
            for (File file : files) {
                if (!file.isFile()) continue;
                try (FileInputStream fis = new FileInputStream(file)) {
                    zos.putNextEntry(new ZipEntry(file.getName()));
                    byte[] buffer = new byte[8192];
                    int read;
                    while ((read = fis.read(buffer)) > 0) {
                        zos.write(buffer, 0, read);
                    }
                    zos.closeEntry();
                }
            }
        }
    }

    private void saveZipToDownloads(File zipFile) throws Exception {
        String fileName = zipFile.getName();
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ContentValues values = new ContentValues();
            values.put(MediaStore.Downloads.DISPLAY_NAME, fileName);
            values.put(MediaStore.Downloads.MIME_TYPE, "application/zip");
            values.put(MediaStore.Downloads.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS);
            ContentResolver resolver = getContentResolver();
            Uri uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values);
            if (uri == null) throw new IllegalStateException("Não consegui criar arquivo em Downloads.");
            try (OutputStream os = resolver.openOutputStream(uri); FileInputStream fis = new FileInputStream(zipFile)) {
                if (os == null) throw new IllegalStateException("Downloads indisponível.");
                byte[] buffer = new byte[8192];
                int read;
                while ((read = fis.read(buffer)) > 0) {
                    os.write(buffer, 0, read);
                }
            }
            return;
        }
        File downloads = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS);
        if (!downloads.exists()) downloads.mkdirs();
        File target = new File(downloads, fileName);
        try (FileOutputStream fos = new FileOutputStream(target); FileInputStream fis = new FileInputStream(zipFile)) {
            byte[] buffer = new byte[8192];
            int read;
            while ((read = fis.read(buffer)) > 0) {
                fos.write(buffer, 0, read);
            }
        }
    }

    private void loadDetailCaptureScript(Runnable afterLoad) {
        try {
            String script = readAssetText("mapeiaai_detail_capture.js");
            webView.evaluateJavascript(script + "\ntrue;", value -> {
                if (afterLoad != null) afterLoad.run();
            });
        } catch (Exception exc) {
            productLastError = exc.getMessage();
            if (afterLoad != null) afterLoad.run();
        }
    }

    private void loadStockCaptureScript(Runnable afterLoad) {
        try {
            String script = readAssetText("mapeiaai_stock_capture.js");
            webView.evaluateJavascript(script + "\ntrue;", value -> {
                if (afterLoad != null) afterLoad.run();
            });
        } catch (Exception exc) {
            stockLastError = exc.getMessage();
            if (afterLoad != null) afterLoad.run();
        }
    }

    private String readAssetText(String name) throws Exception {
        try (InputStream is = getAssets().open(name); ByteArrayOutputStream bos = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int read;
            while ((read = is.read(buffer)) > 0) {
                bos.write(buffer, 0, read);
            }
            return bos.toString("UTF-8");
        }
    }

    private String decodeJsValue(String value) throws Exception {
        if (value == null || "null".equals(value)) return "";
        Object parsed = new JSONTokener(value).nextValue();
        return parsed == null ? "" : String.valueOf(parsed);
    }

    private void closeDetailOverlay(Runnable afterClose) {
        String closeScript = "(function(){try{var selectors=['.modal.show .btn-close','.modal.show [data-bs-dismiss=modal]','.modal.in .close','.modal .close','button[aria-label=Close]','button[aria-label=Fechar]'];for(var i=0;i<selectors.length;i++){var n=document.querySelector(selectors[i]);if(n){try{n.click();break;}catch(e){}}}try{document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',keyCode:27,which:27,bubbles:true}));}catch(e){}return true;}catch(e){return false;}})()";
        webView.evaluateJavascript(closeScript, value -> {
            if (afterClose != null) afterClose.run();
        });
    }

    private void setStatus(String text) {
        statusText.setText(text);
    }

    private void toast(String text) {
        Toast.makeText(this, text, Toast.LENGTH_LONG).show();
    }

    private void requestLegacyWritePermissionIfNeeded() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q && checkSelfPermission(Manifest.permission.WRITE_EXTERNAL_STORAGE) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.WRITE_EXTERNAL_STORAGE}, WRITE_REQUEST_CODE);
        }
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
            return;
        }
        super.onBackPressed();
    }

    private interface RowCountCallback {
        void onRowCount(int count);
    }
}
