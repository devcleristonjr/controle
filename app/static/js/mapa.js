(() => {
  const mapElement = document.getElementById('leaflet-map');
  if (!mapElement || typeof L === 'undefined') {
    return;
  }

  const map = L.map('leaflet-map', {
    maxBounds: [[-18.75, -46.5], [-8.0, -37.0]],
    maxBoundsViscosity: 1.0,
    minZoom: 6,
  }).setView([-12.8, -41.7], 7);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18,
    attribution: '&copy; OpenStreetMap contributors',
  }).addTo(map);

  const markerLayer = L.layerGroup().addTo(map);
  const totalPontosEl = document.getElementById('map-total-pontos');
  const totalMetricEl = document.getElementById('map-total-banners');
  const totalMetricLabelEl = document.getElementById('map-total-metric-label');

  const filters = {
    territorio_id: document.getElementById('filter-territorio'),
    municipio_id: document.getElementById('filter-municipio'),
    material_id: document.getElementById('filter-material'),
    status: document.getElementById('filter-status'),
  };

  function getQueryString() {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, element]) => {
      if (element?.value) {
        params.set(key, element.value);
      }
    });
    return params.toString();
  }

  function escapeHtml(value) {
    return String(value || '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  async function refreshMap() {
    const response = await fetch(`/api/mapa?${getQueryString()}`, {
      headers: { Accept: 'application/json' },
    });
    const points = await response.json();

    markerLayer.clearLayers();
    let totalMetric = 0;
    let metricLabel = 'Estoque total';
    const bounds = [];
    const duplicateCounts = new Map();

    const hasMaterialFilter = Boolean(filters.material_id?.value);

    points.forEach((point) => {
      const pointTotalStock = Number(point.total_estoque ?? 0);
      const pointMetric = hasMaterialFilter
        ? Number(point.metric_value ?? point.total_banners ?? 0)
        : pointTotalStock;
      const materialSummary = Array.isArray(point.materiais_resumo) ? point.materiais_resumo : [];
      const visibleMaterials = materialSummary.filter((item) => Number(item.quantidade || 0) > 0).slice(0, 4);
      const materialSummaryHtml = visibleMaterials.length > 0
        ? `
          <div class="mb-2">
            <strong>Materiais:</strong>
            <div class="small mt-1">
              ${visibleMaterials.map((item) => `${escapeHtml(item.nome)}: ${Number(item.quantidade || 0)}`).join('<br>')}
            </div>
          </div>
        `
        : '<div class="mb-2"><strong>Materiais:</strong> <span class="text-muted">Sem estoque informado</span></div>';
      totalMetric += pointMetric;
      metricLabel = hasMaterialFilter ? (point.metric_label || metricLabel) : 'Estoque total';
      bounds.push([point.latitude, point.longitude]);

      const coordinateKey = `${point.latitude}:${point.longitude}`;
      const duplicateIndex = duplicateCounts.get(coordinateKey) || 0;
      duplicateCounts.set(coordinateKey, duplicateIndex + 1);

      const markerOffset = duplicateIndex * 0.00022;
      const lat = point.latitude + ((duplicateIndex % 2 === 0 ? 1 : -1) * markerOffset);
      const lng = point.longitude + ((duplicateIndex % 3 === 0 ? 1 : -1) * markerOffset * 1.2);

      const popupHtml = `
        <div class="p-1" style="min-width: 240px; max-width: 300px;">
          <div class="fw-bold mb-1">${escapeHtml(point.nome)}</div>
          <div class="small text-muted mb-2">${escapeHtml(point.municipio)} • ${escapeHtml(point.territorio)}</div>
          <div class="mb-2"><strong>Estoque total:</strong> ${pointTotalStock}</div>
          ${hasMaterialFilter ? `<div class="mb-2"><strong>${escapeHtml(point.metric_label || 'Material selecionado')}:</strong> ${pointMetric}</div>` : ''}
          ${materialSummaryHtml}
          <div class="mb-2"><strong>Responsável:</strong> ${escapeHtml(point.responsavel_nome || '-')}</div>
          ${point.foto ? `<div class="mb-2"><img src="/${escapeHtml(point.foto)}" alt="Foto" style="width:100%;height:140px;object-fit:cover;border-radius:12px;"></div>` : ''}
          <div class="d-grid gap-2">
            ${point.whatsapp_url ? `<a class="btn btn-success btn-sm" target="_blank" rel="noopener noreferrer" href="${escapeHtml(point.whatsapp_url)}">💬 Falar no WhatsApp</a>` : ''}
            <a class="btn btn-outline-primary btn-sm" href="${escapeHtml(point.detail_url)}">Ver detalhes</a>
          </div>
        </div>
      `;
      L.marker([lat, lng]).addTo(markerLayer).bindPopup(popupHtml);
    });

    if (totalPontosEl) totalPontosEl.textContent = String(points.length);
    if (totalMetricEl) totalMetricEl.textContent = String(Math.round(totalMetric));
    if (totalMetricLabelEl) totalMetricLabelEl.textContent = metricLabel;

    if (bounds.length > 0) {
      map.fitBounds(bounds, { padding: [30, 30] });
    } else {
      map.setView([-12.8, -41.7], 7);
    }
  }

  Object.values(filters).forEach((element) => {
    if (element) {
      element.addEventListener('change', refreshMap);
    }
  });

  const button = document.getElementById('map-filter-button');
  if (button) {
    button.addEventListener('click', refreshMap);
  }

  refreshMap().catch((error) => {
    console.error(error);
  });
})();
