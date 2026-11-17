package zm.agriguard.app;

import android.net.Uri;
import android.os.Bundle;
import android.util.Log;
import android.webkit.PermissionRequest;
import com.getcapacitor.Bridge;
import com.getcapacitor.BridgeActivity;
import com.getcapacitor.BridgeWebChromeClient;

public class MainActivity extends BridgeActivity {

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        // Replaces the client Capacitor's Bridge installed; everything else is inherited.
        bridge.getWebView().setWebChromeClient(new SafePermissionChromeClient(bridge));
    }

    /**
     * Works around a crash in Capacitor 8.6.2's BridgeWebChromeClient.onPermissionRequest.
     *
     * The camera request (getUserMedia) opens Android's permission dialog. If the WebView
     * cancels the request while the dialog is open, Capacitor still calls grant() or deny()
     * on it when the dialog closes, and the WebView throws IllegalStateException
     * ("Either grant() or deny() has been already called"), killing the app on launch.
     * Seen on a Galaxy A51 (WebView 157) on 2026-11-17.
     *
     * Each request is wrapped so a second or late answer is ignored instead of crashing.
     * The page's getUserMedia then fails normally; the next attempt finds the permission
     * already granted.
     */
    private static final class SafePermissionChromeClient extends BridgeWebChromeClient {

        SafePermissionChromeClient(Bridge bridge) {
            super(bridge);
        }

        @Override
        public void onPermissionRequest(final PermissionRequest request) {
            super.onPermissionRequest(new AnswerOnce(request));
        }
    }

    private static final class AnswerOnce extends PermissionRequest {

        private final PermissionRequest inner;
        private boolean answered;

        AnswerOnce(PermissionRequest inner) {
            this.inner = inner;
        }

        @Override
        public Uri getOrigin() {
            return inner.getOrigin();
        }

        @Override
        public String[] getResources() {
            return inner.getResources();
        }

        @Override
        public void grant(String[] resources) {
            if (answered) return;
            answered = true;
            try {
                inner.grant(resources);
            } catch (IllegalStateException e) {
                Log.w("AgriGuard", "Camera request was already cancelled; ignoring grant", e);
            }
        }

        @Override
        public void deny() {
            if (answered) return;
            answered = true;
            try {
                inner.deny();
            } catch (IllegalStateException e) {
                Log.w("AgriGuard", "Camera request was already cancelled; ignoring deny", e);
            }
        }
    }
}
