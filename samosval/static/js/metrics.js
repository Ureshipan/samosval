// Графики метрик для страницы развёртывания (CPU/RAM)
// Глобальная функция: window.initDeploymentMetrics(config)
// config: { deploymentId, metricsUrl, cpuCanvasId, ramCanvasId, refreshIntervalMs }

(function () {
    function createLineChart(ctx, label, color) {
        return new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: label,
                    data: [],
                    borderColor: color,
                    backgroundColor: 'rgba(255,255,255,0.02)',
                    borderWidth: 1.5,
                    pointRadius: 0,
                    tension: 0.25
                }]
            },
            options: {
                animation: false,
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100
                    }
                },
                plugins: {
                    legend: {
                        display: true,
                        labels: {
                            color: '#f5f5f5'
                        }
                    }
                }
            }
        });
    }

    function initDeploymentMetrics(config) {
        var cpuCtx = document.getElementById(config.cpuCanvasId);
        var ramCtx = document.getElementById(config.ramCanvasId);
        if (!cpuCtx || !ramCtx || typeof Chart === 'undefined') {
            return;
        }

        var cpuChart = createLineChart(cpuCtx, 'CPU, %', '#ff5252');
        var ramChart = createLineChart(ramCtx, 'RAM, %', '#64b5f6');

        function refresh() {
            fetch(config.metricsUrl)
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    cpuChart.data.labels = data.labels;
                    cpuChart.data.datasets[0].data = data.cpu;
                    ramChart.data.labels = data.labels;
                    ramChart.data.datasets[0].data = data.ram;
                    cpuChart.update('none');
                    ramChart.update('none');
                })
                .catch(function () { /* ignore errors */ })
                .finally(function () {
                    setTimeout(refresh, config.refreshIntervalMs || 2500);
                });
        }

        refresh();
    }

    window.initDeploymentMetrics = initDeploymentMetrics;
})();


