let trendChartInstance = null;
let doughnutChartInstance = null;

export function renderTrendChart(ctx, data) {
    if (trendChartInstance) trendChartInstance.destroy();
    
    trendChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.map(d => d.label),
            datasets: [
                { label: 'Przychody', data: data.map(d => d.income), borderColor: '#4ade80', backgroundColor: 'rgba(74, 222, 128, 0.1)', tension: 0.4, fill: true },
                { label: 'Wydatki', data: data.map(d => d.expense), borderColor: '#f87171', backgroundColor: 'rgba(248, 113, 113, 0.1)', tension: 0.4, fill: true }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { labels: { color: '#94a3b8', font: { size: 10 } } } },
            scales: {
                y: { grid: { color: '#334155' }, ticks: { color: '#94a3b8', font: { size: 10 } } },
                x: { grid: { display: false }, ticks: { color: '#94a3b8', font: { size: 10 } } }
            }
        }
    });
}

export function renderDoughnutChart(ctx, categories, chartColors, onClickCallback) {
    if (doughnutChartInstance) {
        doughnutChartInstance.destroy();
        doughnutChartInstance = null;
    }

    const labels = categories.map(c => c.name);
    const data = categories.map(c => Math.abs(c.total));
    const bgColors = categories.map((_, i) => chartColors[i % chartColors.length]);

    doughnutChartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: bgColors,
                borderWidth: 0,
                hoverOffset: 10
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '75%',
            plugins: {
                legend: { display: false },
                tooltip: { enabled: false }
            },
            onClick: (evt, elements) => {
                if (elements.length > 0) {
                    const index = elements[0].index;
                    onClickCallback({
                        name: labels[index],
                        amount: data[index],
                        color: bgColors[index]
                    });
                } else {
                    onClickCallback(null);
                }
            }
        }
    });
}
