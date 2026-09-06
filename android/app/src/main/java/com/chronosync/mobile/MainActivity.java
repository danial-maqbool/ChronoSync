package com.chronosync.mobile;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.DownloadManager;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Environment;
import android.view.View;
import android.view.WindowInsets;
import android.webkit.*;
import android.widget.*;
import java.util.ArrayList;

/** Installable Android client for the hosted ChronoSync workspace. No JS/native bridge. */
public class MainActivity extends Activity {
    private WebView web;
    private String origin;
    private ValueCallback<Uri[]> fileCallback;
    private final int FILE_REQUEST = 41;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        origin = getPreferences(MODE_PRIVATE).getString("origin", "https://chronosync-qk1q.onrender.com");
        if (origin.isEmpty()) setup(); else openWorkspace();
    }

    private LinearLayout layout() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.rgb(247,248,245));
        root.setOnApplyWindowInsetsListener((v, insets) -> {
            android.graphics.Insets bars = insets.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.ime());
            v.setPadding(bars.left, bars.top, bars.right, bars.bottom);
            return insets;
        });
        setContentView(root);
        return root;
    }

    private void setup() {
        LinearLayout root = layout();
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(32, 48, 32, 24);
        root.addView(card);
        TextView title = new TextView(this);
        title.setText("ChronoSync"); title.setTextSize(32); title.setTextColor(Color.rgb(23,77,67));
        card.addView(title);
        TextView help = new TextView(this);
        help.setText("Enter the HTTPS address of your hosted ChronoSync app once, then sign in to your private account. Your laptop can stay off.\n\nUse only the address supplied by your workspace owner.");
        help.setTextSize(16); help.setPadding(0,24,0,24); card.addView(help);
        EditText address = new EditText(this);
        address.setInputType(android.text.InputType.TYPE_CLASS_TEXT | android.text.InputType.TYPE_TEXT_VARIATION_URI);
        address.setSingleLine(true); address.setHint("https://your-app.onrender.com");
        address.setText(origin); card.addView(address);
        Button connect = new Button(this); connect.setText("Connect to workspace"); card.addView(connect);
        connect.setOnClickListener(v -> {
            String value = address.getText().toString().trim().replaceAll("/+$", "");
            Uri uri = Uri.parse(value);
            if (!"https".equals(uri.getScheme()) || uri.getHost() == null || uri.getUserInfo() != null || (uri.getPort() != -1 && uri.getPort() != 443) || !uri.getPath().isEmpty() || uri.getQuery() != null || uri.getFragment() != null) {
                address.setError("Enter an HTTPS website address without a path"); return;
            }
            if (!value.equals(origin)) {
                CookieManager.getInstance().removeAllCookies(null);
                WebStorage.getInstance().deleteAllData();
            }
            origin = value;
            getPreferences(MODE_PRIVATE).edit().putString("origin", origin).apply();
            openWorkspace();
        });
    }

    private boolean trusted(Uri uri) {
        Uri home = Uri.parse(origin);
        return "https".equals(uri.getScheme()) && home.getHost().equals(uri.getHost()) && uri.getUserInfo() == null && (uri.getPort() == -1 || uri.getPort() == 443);
    }

    private void openWorkspace() {
        LinearLayout root = layout();
        LinearLayout toolbar = new LinearLayout(this);
        TextView label = new TextView(this); label.setText("ChronoSync"); label.setTextSize(18); label.setPadding(16,12,8,12);
        toolbar.addView(label, new LinearLayout.LayoutParams(0, -2, 1));
        Button reload = new Button(this); reload.setText("Reload"); toolbar.addView(reload);
        Button settings = new Button(this); settings.setText("Server"); toolbar.addView(settings);
        root.addView(toolbar);
        web = new WebView(this);
        root.addView(web, new LinearLayout.LayoutParams(-1, 0, 1));
        reload.setOnClickListener(v -> web.loadUrl(origin));
        settings.setOnClickListener(v -> new AlertDialog.Builder(this).setTitle("Workspace server").setMessage(origin).setPositiveButton("Change", (d,w) -> { web.destroy(); setup(); }).setNegativeButton("Cancel", null).show());
        WebSettings config = web.getSettings();
        config.setJavaScriptEnabled(true);
        config.setDomStorageEnabled(true);
        config.setAllowFileAccess(false);
        config.setAllowContentAccess(false);
        config.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        config.setSafeBrowsingEnabled(true);
        config.setCacheMode(WebSettings.LOAD_NO_CACHE);
        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, false);
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                if (trusted(request.getUrl())) return false;
                if ("https".equals(request.getUrl().getScheme()) && request.hasGesture()) {
                    try { startActivity(new Intent(Intent.ACTION_VIEW, request.getUrl())); } catch (Exception ignored) { }
                }
                return true;
            }
            @Override public void onPageFinished(WebView view, String url) { CookieManager.getInstance().flush(); }
            @Override public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) Toast.makeText(MainActivity.this, "Cannot connect. Check your internet and tap Reload. Free hosting may need a minute to wake.", Toast.LENGTH_LONG).show();
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = callback;
                Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                intent.setType("*/*");
                intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, params.getMode() == FileChooserParams.MODE_OPEN_MULTIPLE);
                try { startActivityForResult(intent, FILE_REQUEST); }
                catch (Exception e) { fileCallback.onReceiveValue(null); fileCallback = null; }
                return true;
            }
        });
        web.setDownloadListener((url, userAgent, disposition, mime, size) -> {
            Uri uri = Uri.parse(url);
            if (!trusted(uri)) return;
            try {
                DownloadManager.Request download = new DownloadManager.Request(uri);
                String cookies = CookieManager.getInstance().getCookie(url);
                if (cookies != null) download.addRequestHeader("Cookie", cookies);
                download.addRequestHeader("User-Agent", userAgent);
                String filename = URLUtil.guessFileName(url, disposition, mime).replaceAll("[^a-zA-Z0-9._-]", "_");
                download.setTitle(filename);
                download.setMimeType(mime);
                download.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
                download.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, filename);
                ((DownloadManager)getSystemService(DOWNLOAD_SERVICE)).enqueue(download);
                Toast.makeText(this, "Saving to Downloads", Toast.LENGTH_SHORT).show();
            } catch (Exception e) { Toast.makeText(this, "Download failed. Please try again.", Toast.LENGTH_LONG).show(); }
        });
        web.loadUrl(origin);
    }

    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request == FILE_REQUEST && fileCallback != null) {
            ArrayList<Uri> files = new ArrayList<>();
            if (result == RESULT_OK && data != null) {
                if (data.getClipData() != null) for (int i=0; i<data.getClipData().getItemCount(); i++) files.add(data.getClipData().getItemAt(i).getUri());
                else if (data.getData() != null) files.add(data.getData());
            }
            files.removeIf(uri -> !"content".equals(uri.getScheme()));
            fileCallback.onReceiveValue(files.isEmpty() ? null : files.toArray(new Uri[0]));
            fileCallback = null;
        }
    }
    @Override public void onBackPressed() { if (web != null && web.canGoBack()) web.goBack(); else super.onBackPressed(); }
    @Override protected void onPause() { CookieManager.getInstance().flush(); super.onPause(); }
    @Override protected void onDestroy() {
        if (fileCallback != null) fileCallback.onReceiveValue(null);
        if (web != null) web.destroy();
        super.onDestroy();
    }
}
