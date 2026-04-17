/* ============================================================
   UNBIASED AI DECISION — Application JavaScript
   ============================================================ */

document.addEventListener('DOMContentLoaded', function () {
    initThemeToggle();
    initScrollReveal();
    initNavbar();
    initFileUpload();
    initMobileMenu();
});

/* --- Theme Toggle --- */
function initThemeToggle() {
    const toggle = document.getElementById('theme-toggle');
    if (!toggle) return;

    const saved = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', saved);

    toggle.addEventListener('click', () => {
        const current = document.documentElement.getAttribute('data-theme');
        const next = current === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        localStorage.setItem('theme', next);
    });
}

/* --- Scroll Reveal Animations --- */
function initScrollReveal() {
    const reveals = document.querySelectorAll('.reveal');
    if (!reveals.length) return;

    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry, index) => {
            if (entry.isIntersecting) {
                setTimeout(() => {
                    entry.target.classList.add('visible');
                }, index * 100);
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.1, rootMargin: '0px 0px -50px 0px' });

    reveals.forEach(el => observer.observe(el));
}

/* --- Navbar Scroll Effect --- */
function initNavbar() {
    const navbar = document.getElementById('navbar');
    if (!navbar) return;

    let lastScroll = 0;
    window.addEventListener('scroll', () => {
        const curr = window.scrollY;
        if (curr > 100) {
            navbar.style.padding = '8px 0';
            navbar.style.boxShadow = '0 4px 20px rgba(0,0,0,0.2)';
        } else {
            navbar.style.padding = '16px 0';
            navbar.style.boxShadow = 'none';
        }
        lastScroll = curr;
    });
}

/* --- Mobile Menu --- */
function initMobileMenu() {
    const hamburger = document.getElementById('nav-hamburger');
    const menu = document.getElementById('mobile-menu');
    if (!hamburger || !menu) return;

    hamburger.addEventListener('click', () => {
        menu.classList.toggle('open');
        hamburger.classList.toggle('active');
    });

    // Close on link click
    menu.querySelectorAll('.mobile-link').forEach(link => {
        link.addEventListener('click', () => {
            menu.classList.remove('open');
            hamburger.classList.remove('active');
        });
    });
}

/* --- File Upload Handler --- */
function initFileUpload() {
    const zone = document.getElementById('upload-zone');
    const input = document.getElementById('dataset-file');
    const fileInfo = document.getElementById('file-info');
    const fileName = document.getElementById('file-name');
    const fileSize = document.getElementById('file-size');
    const fileRemove = document.getElementById('file-remove');
    const nameField = document.getElementById('upload-name-field');
    const nameInput = document.getElementById('dataset-name');
    const actions = document.getElementById('upload-actions');
    const form = document.getElementById('upload-form');

    if (!zone || !input) return;

    // Drag & Drop
    ['dragenter', 'dragover'].forEach(evt => {
        zone.addEventListener(evt, (e) => {
            e.preventDefault();
            zone.classList.add('dragover');
        });
    });
    ['dragleave', 'drop'].forEach(evt => {
        zone.addEventListener(evt, (e) => {
            e.preventDefault();
            zone.classList.remove('dragover');
        });
    });
    zone.addEventListener('drop', (e) => {
        const files = e.dataTransfer.files;
        if (files.length) {
            input.files = files;
            showFileInfo(files[0]);
        }
    });

    input.addEventListener('change', () => {
        if (input.files.length) {
            showFileInfo(input.files[0]);
        }
    });

    function showFileInfo(file) {
        if (!file.name.endsWith('.csv')) {
            alert('Please upload a CSV file.');
            return;
        }
        zone.style.display = 'none';
        fileInfo.style.display = 'flex';
        nameField.style.display = 'block';
        actions.style.display = 'block';
        fileName.textContent = file.name;
        fileSize.textContent = formatFileSize(file.size);

        // Auto-fill name from filename
        if (nameInput && !nameInput.value) {
            nameInput.value = file.name.replace('.csv', '').replace(/[_-]/g, ' ');
        }
    }

    if (fileRemove) {
        fileRemove.addEventListener('click', () => {
            input.value = '';
            zone.style.display = 'block';
            fileInfo.style.display = 'none';
            nameField.style.display = 'none';
            actions.style.display = 'none';
        });
    }

    // Form submit loading
    if (form) {
        form.addEventListener('submit', () => {
            // Show loading overlay
            const overlay = document.createElement('div');
            overlay.className = 'loading-overlay active';
            overlay.innerHTML = `
                <div class="loading-spinner"></div>
                <div class="loading-text">Analyzing your dataset for bias...</div>
            `;
            document.body.appendChild(overlay);
        });
    }
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/* ============================================================
   DASHBOARD CHARTS
   ============================================================ */
function renderDashboardCharts(data) {
    if (!data || !data.detailed) return;

    const detailed = data.detailed;
    const attrs = Object.keys(detailed);
    if (!attrs.length) return;

    // Color palette
    const colors = [
        '#7c3aed', '#06b6d4', '#f59e0b', '#10b981', '#ef4444',
        '#ec4899', '#8b5cf6', '#14b8a6', '#f97316', '#6366f1',
        '#84cc16', '#e879f9',
    ];
    const alphaColors = colors.map(c => c + '33');

    renderOutcomeChart(detailed, attrs, colors, alphaColors);
    renderDistributionChart(detailed, attrs, colors, alphaColors);
    renderRadarChart(data.metrics, attrs, colors, alphaColors);
    if (data.intersectional) {
        renderHeatmap(data.intersectional);
    }
}

function renderOutcomeChart(detailed, attrs, colors, alphaColors) {
    const canvas = document.getElementById('outcomeChart');
    if (!canvas) return;

    // Use first attribute with outcome rates
    let targetAttr = null;
    for (const attr of attrs) {
        if (detailed[attr] && detailed[attr].outcome_rates) {
            targetAttr = attr;
            break;
        }
    }
    if (!targetAttr) return;

    const outcomeRates = detailed[targetAttr].outcome_rates;
    const labels = Object.keys(outcomeRates);
    const positiveRates = labels.map(l => outcomeRates[l].rate);
    const negativeRates = labels.map(l => 100 - outcomeRates[l].rate);

    new Chart(canvas, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Positive Outcome (%)',
                    data: positiveRates,
                    backgroundColor: colors.slice(0, labels.length).map(c => c + '99'),
                    borderColor: colors.slice(0, labels.length),
                    borderWidth: 2,
                    borderRadius: 6,
                },
                {
                    label: 'Negative Outcome (%)',
                    data: negativeRates,
                    backgroundColor: 'rgba(148, 163, 184, 0.2)',
                    borderColor: 'rgba(148, 163, 184, 0.4)',
                    borderWidth: 1,
                    borderRadius: 6,
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'top', labels: { color: '#94a3b8', font: { family: 'Inter' } } },
                title: { display: true, text: `Outcome Rates by ${targetAttr}`, color: '#e2e8f0', font: { family: 'Inter', size: 14, weight: 600 } },
            },
            scales: {
                x: { ticks: { color: '#94a3b8', font: { family: 'Inter' } }, grid: { color: 'rgba(255,255,255,0.05)' } },
                y: { ticks: { color: '#94a3b8', font: { family: 'Inter' }, callback: v => v + '%' }, grid: { color: 'rgba(255,255,255,0.05)' }, max: 100 },
            }
        }
    });
}

function renderDistributionChart(detailed, attrs, colors, alphaColors) {
    const canvas = document.getElementById('distributionChart');
    if (!canvas) return;

    // Build datasets for each attribute
    const datasets = [];
    attrs.forEach((attr, i) => {
        const dist = detailed[attr]?.distribution;
        if (!dist) return;

        const labels = Object.keys(dist);
        const values = labels.map(l => dist[l].count);

        if (i === 0) {
            // Use doughnut for first attribute
            new Chart(canvas, {
                type: 'doughnut',
                data: {
                    labels: labels,
                    datasets: [{
                        data: values,
                        backgroundColor: colors.slice(0, labels.length).map(c => c + 'cc'),
                        borderColor: colors.slice(0, labels.length),
                        borderWidth: 2,
                        hoverOffset: 8,
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '55%',
                    plugins: {
                        legend: { position: 'bottom', labels: { color: '#94a3b8', font: { family: 'Inter' }, padding: 16, usePointStyle: true } },
                        title: { display: true, text: `Distribution by ${attr}`, color: '#e2e8f0', font: { family: 'Inter', size: 14, weight: 600 } },
                    }
                }
            });
        }
    });
}

function renderRadarChart(metricsData, attrs, colors, alphaColors) {
    const canvas = document.getElementById('radarChart');
    if (!canvas) return;

    const metricLabels = ['Demographic Parity', 'Disparate Impact', 'Statistical Parity', 'Group Size Ratio'];
    const metricKeys = ['demographic_parity', 'disparate_impact', 'statistical_parity_difference', 'group_size_ratio'];

    const datasets = [];
    Object.keys(metricsData).forEach((attr, i) => {
        const attrMetrics = metricsData[attr];
        const values = metricKeys.map(key => {
            const found = attrMetrics.find(m => m.type === key);
            if (!found) return 0;
            // Normalize: for spd, invert (lower is better)
            if (key === 'statistical_parity_difference') {
                return Math.max(0, 1 - (found.value / 100));
            }
            return Math.min(found.value, 1);
        });

        datasets.push({
            label: attr,
            data: values,
            backgroundColor: (colors[i % colors.length]) + '22',
            borderColor: colors[i % colors.length],
            borderWidth: 2,
            pointBackgroundColor: colors[i % colors.length],
            pointBorderColor: '#fff',
            pointRadius: 4,
        });
    });

    new Chart(canvas, {
        type: 'radar',
        data: {
            labels: metricLabels,
            datasets: datasets,
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'top', labels: { color: '#94a3b8', font: { family: 'Inter' }, usePointStyle: true } },
            },
            scales: {
                r: {
                    angleLines: { color: 'rgba(255,255,255,0.08)' },
                    grid: { color: 'rgba(255,255,255,0.08)' },
                    pointLabels: { color: '#94a3b8', font: { family: 'Inter', size: 12 } },
                    ticks: { display: false },
                    min: 0, max: 1,
                }
            }
        }
    });
}

/* --- Intersectional Heatmap --- */
function renderHeatmap(intersectionalData) {
    const container = document.getElementById('heatmapContainer');
    if (!container || !intersectionalData) return;

    const attrs = Object.keys(intersectionalData);
    if (!attrs.length) return;

    // Collect all unique groups and their rates
    let allRates = [];
    const attrData = {};
    attrs.forEach(attr => {
        const groups = intersectionalData[attr];
        attrData[attr] = groups;
        Object.values(groups).forEach(rate => allRates.push(rate));
    });

    const minRate = Math.min(...allRates);
    const maxRate = Math.max(...allRates);
    const range = maxRate - minRate || 1;

    // Color interpolation: red (low) -> yellow (mid) -> green (high)
    function getColor(rate) {
        const normalized = (rate - minRate) / range;
        if (normalized < 0.5) {
            const t = normalized * 2;
            const r = 239;
            const g = Math.round(68 + t * (158 - 68));
            const b = Math.round(68 + t * (11 - 68));
            return `rgba(${r}, ${g}, ${b}, 0.85)`;
        } else {
            const t = (normalized - 0.5) * 2;
            const r = Math.round(245 - t * (245 - 16));
            const g = Math.round(158 + t * (185 - 158));
            const b = Math.round(11 + t * (129 - 11));
            return `rgba(${r}, ${g}, ${b}, 0.85)`;
        }
    }

    function getTextColor(rate) {
        const normalized = (rate - minRate) / range;
        return normalized > 0.4 ? '#000' : '#fff';
    }

    // Build HTML table
    let html = '<table class="heatmap-table"><thead><tr><th>Attribute</th><th>Group</th><th>Positive Rate</th><th style="width:50%">Heatmap</th></tr></thead><tbody>';

    attrs.forEach(attr => {
        const groups = attrData[attr];
        const sortedGroups = Object.entries(groups).sort((a, b) => b[1] - a[1]);

        sortedGroups.forEach(([group, rate], idx) => {
            html += '<tr>';
            if (idx === 0) {
                html += `<td class="heatmap-row-label" rowspan="${sortedGroups.length}">${attr}</td>`;
            }
            html += `<td class="heatmap-row-label">${group}</td>`;
            html += `<td style="text-align:center; font-weight:700;">${rate.toFixed(1)}%</td>`;
            html += `<td style="background:${getColor(rate)}; color:${getTextColor(rate)}; text-align:center; font-weight:700;">`;
            html += `<div style="width:${Math.max(rate, 5)}%; min-width:30px; height:28px; line-height:28px; border-radius:4px; display:inline-block;">${rate.toFixed(1)}%</div>`;
            html += '</td></tr>';
        });
    });

    html += '</tbody></table>';
    container.innerHTML = html;
}
