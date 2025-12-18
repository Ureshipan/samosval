// SSE logs for deployment detail.
// Exposes global function: window.initDeploymentLogsSSE(config)
// config: { deploymentId, sseUrl, logElementId, toggleId }

(function () {
    function initDeploymentLogsSSE(config) {
        var logEl = document.getElementById(config.logElementId);
        var toggle = document.getElementById(config.toggleId);
        if (!logEl || !toggle || typeof EventSource === 'undefined') {
            return;
        }

        var es = null;

        function start() {
            if (es || !toggle.checked) return;
            es = new EventSource(config.sseUrl);
            es.onmessage = function (evt) {
                var text = evt.data || '';
                if (!text) return;
                if (logEl.textContent && !logEl.textContent.endsWith('\n')) {
                    logEl.textContent += '\n';
                }
                logEl.textContent += text + '\n';
                logEl.scrollTop = logEl.scrollHeight;
            };
            es.onerror = function () {
                // restart later
                stop();
                setTimeout(start, 3000);
            };
        }

        function stop() {
            if (es) {
                es.close();
                es = null;
            }
        }

        toggle.addEventListener('change', function () {
            if (toggle.checked) {
                start();
            } else {
                stop();
            }
        });

        window.addEventListener('beforeunload', function () {
            stop();
        });

        if (toggle.checked) {
            start();
        }
    }

    window.initDeploymentLogsSSE = initDeploymentLogsSSE;
})();


