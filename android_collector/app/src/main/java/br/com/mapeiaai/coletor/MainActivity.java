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
import android.webkit.ValueCallback;
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
    private static final int AUTO_TARGET_PAGE_LENGTH = 200;
    private static final long AUTO_PAGE_SETTLE_MS = 650;
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
    private int detailFileCount = 0;
    private int detailRecordCount = 0;
    private boolean autoRunning = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        requestLegacyWritePermissionIfNeeded();
        buildLayout();
        configureWebView();
        setStatus("Cole o site do fornecedor, abra, faça login e capture.");
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

        Button captureButton = new Button(this);
        captureButton.setText("Capturar página atual");
        captureButton.setOnClickListener(v -> captureCurrentPage("manual", null));
        actions.addView(captureButton, new LinearLayout.LayoutParams(-1, -2));

        Button autoButton = new Button(this);
        autoButton.setText("Capturar tabela automática TURBO");
        autoButton.setOnClickListener(v -> startAutoDatatablesCapture());
        actions.addView(autoButton, new LinearLayout.LayoutParams(-1, -2));

        Button detailButton = new Button(this);
        detailButton.setText("Capturar detalhes da tabela atual");
        detailButton.setOnClickListener(v -> runDetailCaptureForCurrentPage("detalhes_manual", () -> setStatus("Captura de detalhes finalizada. Toque em Gerar ZIP para MapeiaAI.")));
        actions.addView(detailButton, new LinearLayout.LayoutParams(-1, -2));

        Button zipButton = new Button(this);
        zipButton.setText("Gerar ZIP para MapeiaAI");
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
        setStatus("Abrindo: " + url + "\nFaça login normalmente. Depois vá até a tela de produtos.");
        webView.loadUrl(url);
    }

    private void resetCaptureSession() {
        captureCount = 0;
        autoIndex = 0;
        autoPages = 0;
        detailFileCount = 0;
        detailRecordCount = 0;
        autoRunning = false;
        captureDir = null;
        progressBar.setProgress(0);
        setAutoPerformanceMode(false);
    }

    private void setAutoPerformanceMode(boolean enabled) {
        if (webView == null) return;
        WebSettings settings = webView.getSettings();
        settings.setLoadsImagesAutomatically(!enabled);
        settings.setBlockNetworkImage(enabled);
    }

    private File ensureCaptureDir() {
        if (captureDir != null && captureDir.exists()) {
            return captureDir;
        }
        String stamp = new SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(new Date());
        captureDir = new File(getCacheDir(), "mapeiaai_android_capture_" + stamp);
        if (!captureDir.exists()) {
            captureDir.mkdirs();
        }
        return captureDir;
    }

    private void captureCurrentPage(String label, Runnable afterCapture) {
        captureCurrentPage(label, afterCapture, true);
    }

    private void captureCurrentPage(String label, Runnable afterCapture, boolean includeArchive) {
        if (webView.getUrl() == null || webView.getUrl().trim().length() == 0) {
            toast("Abra um site antes de capturar.");
            if (afterCapture != null) afterCapture.run();
            return;
        }
        webView.evaluateJavascript("(function(){return !!document.querySelector('input[type=password]');})()", value -> {
            if ("true".equalsIgnoreCase(String.valueOf(value))) {
                setStatus("Não capturei porque a tela atual parece ser login/senha. Entre no painel e abra a lista de produtos.");
                if (afterCapture != null) afterCapture.run();
                return;
            }
            Runnable afterSave = () -> {
                captureCount++;
                int progress = autoRunning && autoPages > 0 ? Math.min(99, (int) (((autoIndex + 1) * 100.0f) / autoPages)) : Math.min(99, captureCount * 4);
                progressBar.setProgress(progress);
                setStatus("Captura salva. Total na sessão: " + captureCount + " página(s).");
                if (afterCapture != null) afterCapture.run();
            };
            if (includeArchive) {
                saveCurrentWebArchive(label, () -> saveCurrentHtmlSnapshot(label, afterSave));
            } else {
                saveCurrentHtmlSnapshot(label, afterSave);
            }
        });
    }

    private void saveCurrentWebArchive(String label, Runnable afterArchive) {
        File dir = ensureCaptureDir();
        String name = nextBaseName(label) + ".mhtml";
        File out = new File(dir, name);
        webView.saveWebArchive(out.getAbsolutePath(), false, new ValueCallback<String>() {
            @Override
            public void onReceiveValue(String savedPath) {
                if (savedPath == null || savedPath.length() == 0) {
                    setStatus("Aviso: não consegui salvar MHTML. Vou manter o HTML simples se disponível.");
                }
                if (afterArchive != null) afterArchive.run();
            }
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
                setStatus("Aviso: HTML simples não foi salvo, mas o MHTML pode estar disponível.");
            }
            if (afterHtml != null) afterHtml.run();
        });
    }

    private String nextBaseName(String label) {
        String safeLabel = String.valueOf(label == null ? "pagina" : label).replaceAll("[^a-zA-Z0-9_-]", "_");
        String number = String.format(Locale.US, "%03d", captureCount + 1);
        return "mapeiaai_android_" + number + "_" + safeLabel;
    }

    private String nextDetailBaseName(String label) {
        String safeLabel = String.valueOf(label == null ? "pagina" : label).replaceAll("[^a-zA-Z0-9_-]", "_");
        String number = String.format(Locale.US, "%03d", detailFileCount + 1);
        return "mapeiaai_android_detail_" + number + "_" + safeLabel + "_detalhes";
    }

    private void startAutoDatatablesCapture() {
        if (autoRunning) {
            toast("Captura automática já está rodando.");
            return;
        }
        setAutoPerformanceMode(true);
        setStatus("Modo TURBO ligado: imagens bloqueadas, HTML leve e tabela ampliada para acelerar a coleta.");
        String js = "(function(){try{if(!(window.jQuery&&window.jQuery.fn&&window.jQuery.fn.dataTable)){return JSON.stringify({ok:false,reason:'datatable_not_found'});}var tables=window.jQuery.fn.dataTable.tables();if(!tables.length){return JSON.stringify({ok:false,reason:'table_not_found'});}var dt=window.jQuery(tables[0]).DataTable();try{dt.page.len(" + AUTO_TARGET_PAGE_LENGTH + ").draw(false);}catch(e){}return JSON.stringify({ok:true});}catch(e){return JSON.stringify({ok:false,reason:String(e)});}})()";
        webView.evaluateJavascript(js, value -> webView.postDelayed(this::readAutoDatatablesInfoAndStart, AUTO_PAGE_SETTLE_MS));
    }

    private void readAutoDatatablesInfoAndStart() {
        String js = "(function(){try{if(!(window.jQuery&&window.jQuery.fn&&window.jQuery.fn.dataTable)){return JSON.stringify({ok:false,reason:'datatable_not_found'});}var tables=window.jQuery.fn.dataTable.tables();if(!tables.length){return JSON.stringify({ok:false,reason:'table_not_found'});}var dt=window.jQuery(tables[0]).DataTable();var info=dt.page.info();return JSON.stringify({ok:true,pages:info.pages,total:info.recordsTotal||info.recordsDisplay||0,pageLength:info.length||0});}catch(e){return JSON.stringify({ok:false,reason:String(e)});}})()";
        webView.evaluateJavascript(js, value -> {
            try {
                JSONObject data = new JSONObject(decodeJsValue(value));
                if (!data.optBoolean("ok")) {
                    setAutoPerformanceMode(false);
                    setStatus("Não encontrei DataTables. Use Capturar página atual ou navegue até a tela correta de produtos.");
                    return;
                }
                autoPages = Math.min(MAX_AUTO_PAGES, Math.max(1, data.optInt("pages", 1)));
                autoIndex = 0;
                autoRunning = true;
                int total = data.optInt("total", 0);
                int pageLength = data.optInt("pageLength", 0);
                setStatus("Tabela TURBO detectada: " + autoPages + " página(s), " + total + " registro(s), até " + pageLength + " por página. Captura iniciada.");
                captureDataTablePage();
            } catch (Exception exc) {
                setAutoPerformanceMode(false);
                setStatus("Não consegui iniciar captura automática: " + exc.getMessage());
            }
        });
    }

    private void captureDataTablePage() {
        if (!autoRunning || autoIndex >= autoPages) {
            autoRunning = false;
            setAutoPerformanceMode(false);
            progressBar.setProgress(100);
            setStatus("Captura automática TURBO finalizada. Toque em Gerar ZIP para MapeiaAI.");
            return;
        }
        String script = "(function(){try{var tables=window.jQuery.fn.dataTable.tables();var dt=window.jQuery(tables[0]).DataTable();dt.page(" + autoIndex + ").draw(false);return JSON.stringify({ok:true,page:" + autoIndex + "});}catch(e){return JSON.stringify({ok:false,error:String(e)});}})()";
        webView.evaluateJavascript(script, value -> webView.postDelayed(() -> {
            String label = "pagina_" + String.format(Locale.US, "%03d", autoIndex + 1);
            setStatus("Capturando " + label + " de " + autoPages + " em modo TURBO...");
            captureCurrentPage(label, () -> runDetailCaptureForCurrentPage(label, () -> {
                autoIndex++;
                webView.postDelayed(this::captureDataTablePage, AUTO_NEXT_PAGE_MS);
            }), false);
        }, AUTO_PAGE_SETTLE_MS));
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
                        setStatus("Captura de detalhes indisponível nesta tela: " + data.optString("reason"));
                        if (afterDetails != null) afterDetails.run();
                        return;
                    }
                    JSONArray items = data.optJSONArray("items");
                    int count = data.optInt("count", items == null ? 0 : items.length());
                    if (items == null || count <= 0) {
                        setStatus("Nenhum botão de detalhe encontrado nesta página. Mantive a captura da listagem.");
                        if (afterDetails != null) afterDetails.run();
                        return;
                    }
                    setStatus("Capturando detalhes TURBO de " + count + " produto(s) em " + pageLabel + "...");
                    collectDetailItem(pageLabel, items, 0, new JSONArray(), afterDetails);
                } catch (Exception exc) {
                    setStatus("Não consegui iniciar detalhes: " + exc.getMessage());
                    if (afterDetails != null) afterDetails.run();
                }
            });
        });
    }

    private void loadDetailCaptureScript(Runnable afterLoad) {
        try {
            String script = readAssetText("mapeiaai_detail_capture.js");
            webView.evaluateJavascript(script + "\ntrue;", value -> {
                if (afterLoad != null) afterLoad.run();
            });
        } catch (Exception exc) {
            setStatus("Script de detalhes não foi carregado: " + exc.getMessage());
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

    private void closeDetailOverlay(Runnable afterClose) {
        String closeScript = "(function(){try{var selectors=['.modal.show .btn-close','.modal.show [data-bs-dismiss=modal]','.modal.in .close','.modal .close','button[aria-label=Close]','button[aria-label=Fechar]'];for(var i=0;i<selectors.length;i++){var n=document.querySelector(selectors[i]);if(n){try{n.click();break;}catch(e){}}}try{document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',keyCode:27,which:27,bubbles:true}));}catch(e){}return true;}catch(e){return false;}})()";
        webView.evaluateJavascript(closeScript, value -> {
            if (afterClose != null) afterClose.run();
        });
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
                    File out = new File(dir, nextDetailBaseName(pageLabel) + ".html");
                    try (FileOutputStream fos = new FileOutputStream(out)) {
                        fos.write(html.getBytes("UTF-8"));
                    }
                    detailFileCount++;
                    detailRecordCount += records.length();
                    setStatus("Detalhes salvos: " + records.length() + " produto(s) em " + out.getName());
                }
            } catch (Exception exc) {
                setStatus("Aviso: não consegui salvar HTML de detalhes: " + exc.getMessage());
            }
            if (afterDetails != null) afterDetails.run();
        });
    }

    private void createZipForMapeiaAI() {
        File dir = ensureCaptureDir();
        File[] files = dir.listFiles();
        if (files == null || files.length == 0) {
            toast("Nenhuma página capturada ainda.");
            return;
        }
        try {
            writeManifest(dir);
            String stamp = new SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(new Date());
            File zipFile = new File(getCacheDir(), "mapeiaai_capturas_android_" + stamp + ".zip");
            zipDirectory(dir, zipFile);
            saveZipToDownloads(zipFile);
            progressBar.setProgress(100);
            setStatus("ZIP gerado e salvo em Downloads: " + zipFile.getName() + "\nAnexe esse ZIP no MapeiaAI.");
            toast("ZIP salvo em Downloads.");
        } catch (Exception exc) {
            setStatus("Erro ao gerar ZIP: " + exc.getMessage());
            toast("Erro ao gerar ZIP.");
        }
    }

    private void writeManifest(File dir) throws Exception {
        JSONObject manifest = new JSONObject();
        manifest.put("schema_version", "mapeiaai_android_collector_v3_turbo_capture");
        manifest.put("generated_at", new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US).format(new Date()));
        manifest.put("start_url", urlInput.getText().toString().trim());
        manifest.put("current_url", webView.getUrl());
        manifest.put("pages_captured", captureCount);
        manifest.put("detail_files", detailFileCount);
        manifest.put("details_captured", detailRecordCount);
        manifest.put("detail_capture_marker", GtinCaptureMarker.VERSION);
        manifest.put("auto_target_page_length", AUTO_TARGET_PAGE_LENGTH);
        manifest.put("format", "manual:mhtml+html; auto:html+detail_html");
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

    private String decodeJsValue(String value) throws Exception {
        if (value == null || "null".equals(value)) return "";
        Object parsed = new JSONTokener(value).nextValue();
        return parsed == null ? "" : String.valueOf(parsed);
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
}
