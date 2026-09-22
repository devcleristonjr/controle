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
    replenishment: document.getElementById('filter-replenishment'),
    responsavel: document.getElementById('filter-responsavel'),
    localizador: document.getElementById('filter-localizador'),
    occurrence_type: document.getElementById('filter-occurrence-type'),
    with_occurrences: document.getElementById('filter-with-occurrences'),
    period_start: document.getElementById('filter-period-start'),
    period_end: document.getElementById('filter-period-end'),
  };

  let cachedPoints = [];

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

  function aggregateByZoom(points, zoom) {
    const clusters = new Map();
    const precision = zoom <= 7 ? 1 : 2;
    const factor = 10 ** precision;
    points.forEach((point) => {
      const latKey = Math.round(Number(point.latitude) * factor) / factor;
      const lngKey = Math.round(Number(point.longitude) * factor) / factor;
      const key = `${latKey}:${lngKey}`;
      if (!clusters.has(key)) {
        clusters.set(key, {
          lat: latKey,
          lng: lngKey,
          points: [],
          totalInUse: 0,
          totalReplenishment: 0,
        });
      }
      const cluster = clusters.get(key);
      cluster.points.push(point);
      cluster.totalInUse += Number(point.total_em_uso ?? point.total_estoque ?? 0);
      cluster.totalReplenishment += Number(point.total_reposicao_necessaria ?? 0);
    });
    return Array.from(clusters.values());
  }

  function renderMap(points, adjustBounds = true) { // NOSONAR
    markerLayer.clearLayers();
    let totalMetric = 0;
    let metricLabel = 'Em condições de uso';
    const bounds = [];
    const duplicateCounts = new Map();

    const hasMaterialFilter = Boolean(filters.material_id?.value);

    const useClusterMode = map.getZoom() <= 9;
    if (useClusterMode) {
      const clusters = aggregateByZoom(points, map.getZoom());
      clusters.forEach((cluster) => {
        const count = cluster.points.length;
        bounds.push([cluster.lat, cluster.lng]);
        totalMetric += cluster.totalInUse;

        const marker = L.circleMarker([cluster.lat, cluster.lng], {
          radius: Math.min(26, 10 + count),
          weight: 2,
          color: cluster.totalReplenishment > 0 ? '#b42318' : '#155eef',
          fillColor: cluster.totalReplenishment > 0 ? '#f04438' : '#2e90fa',
          fillOpacity: 0.75,
        }).addTo(markerLayer);

        const preview = cluster.points.slice(0, 5)
          .map((point) => `${escapeHtml(point.nome)} (${escapeHtml(point.municipio)})`)
          .join('<br>');
        const extra = cluster.points.length > 5 ? `<div class="small text-muted mt-1">+${cluster.points.length - 5} pontos</div>` : '';

        marker.bindPopup(`
          <div class="p-1" style="min-width: 240px; max-width: 320px;">
            <div class="fw-bold mb-1">Agrupamento de pontos (${count})</div>
            <div class="small text-muted mb-2">Aproxime o zoom para ver os pontos individualmente.</div>
            <div class="small mb-2"><strong>Em condições de uso:</strong> ${Math.round(cluster.totalInUse)}</div>
            <div class="small mb-2"><strong>Reposição necessária:</strong> ${Math.round(cluster.totalReplenishment)}</div>
            <div class="small">${preview}</div>
            ${extra}
          </div>
        `);
      });

      if (totalPontosEl) totalPontosEl.textContent = String(points.length);
      if (totalMetricEl) totalMetricEl.textContent = String(Math.round(totalMetric));
      if (totalMetricLabelEl) totalMetricLabelEl.textContent = metricLabel;

      if (adjustBounds && bounds.length > 0) {
        map.fitBounds(bounds, { padding: [30, 30] });
      } else if (adjustBounds) {
        map.setView([-12.8, -41.7], 7);
      }
      return;
    }

    points.forEach((point) => {
      const pointTotalStock = Number(point.total_estoque ?? 0);
      const pointAllocated = Number(point.total_alocado ?? pointTotalStock);
      const pointInUse = Number(point.total_em_uso ?? pointTotalStock);
      const pointReplenishmentNeeded = Number(point.total_reposicao_necessaria ?? 0);
      const pointDamaged = Number(point.total_danificado ?? 0);
      const occurrenceCount = Number(point.occurrence_count ?? 0);
      const localizadores = Array.isArray(point.localizadores) ? point.localizadores : [];
      const pointMetric = hasMaterialFilter
        ? Number(point.metric_value ?? point.total_banners ?? 0)
        : pointInUse;
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
      metricLabel = hasMaterialFilter ? (point.metric_label || metricLabel) : 'Em condições de uso';
      bounds.push([point.latitude, point.longitude]);

      const coordinateKey = `${point.latitude}:${point.longitude}`;
      const duplicateIndex = duplicateCounts.get(coordinateKey) || 0;
      duplicateCounts.set(coordinateKey, duplicateIndex + 1);

      const markerOffset = duplicateIndex * 0.00022;
      const lat = point.latitude + ((duplicateIndex % 2 === 0 ? 1 : -1) * markerOffset);
      const lng = point.longitude + ((duplicateIndex % 3 === 0 ? 1 : -1) * markerOffset * 1.2);

      const localizadorHtml = localizadores.length > 0
        ? `<div class="mb-2"><strong>Localizador:</strong> ${localizadores.map((value) => escapeHtml(value)).join(' • ')}</div>`
        : '<div class="mb-2"><strong>Localizador:</strong> <span class="text-muted">-</span></div>';

      const popupHtml = `
        <div class="p-1" style="min-width: 240px; max-width: 300px;">
          <div class="fw-bold mb-1">${escapeHtml(point.nome)}</div>
          <div class="small text-muted mb-2">${escapeHtml(point.municipio)} • ${escapeHtml(point.territorio)}</div>
          ${localizadorHtml}
          <div class="mb-2"><strong>Status dos dados:</strong> ${escapeHtml(point.status_migracao || "Operacional")}</div>
          <div class="mb-2"><strong>Alocado no ponto:</strong> ${pointAllocated}</div>
          <div class="mb-2"><strong>Em uso estimado:</strong> ${pointInUse}</div>
          <div class="mb-2"><strong>Danificado:</strong> ${pointDamaged}</div>
          <div class="mb-2"><strong>Ocorrências registradas:</strong> ${occurrenceCount}</div>
          <div class="mb-2"><strong>Reposição necessária:</strong> <span class="${pointReplenishmentNeeded > 0 ? 'text-danger fw-semibold' : ''}">${pointReplenishmentNeeded}</span></div>
          ${hasMaterialFilter ? `<div class="mb-2"><strong>${escapeHtml(point.metric_label || 'Material selecionado')}:</strong> ${pointMetric}</div>` : ''}
          ${materialSummaryHtml}
          <div class="mb-2"><strong>Responsável pelo ponto:</strong> ${escapeHtml(point.responsavel_nome || '-')}</div>
          ${point.foto ? `<div class="mb-2"><img src="/${escapeHtml(point.foto)}" alt="Foto" style="width:100%;height:140px;object-fit:cover;border-radius:12px;"></div>` : ''}
          <div class="d-grid gap-2">
            ${point.whatsapp_url ? `<a class="btn btn-success btn-sm" target="_blank" rel="noopener noreferrer" href="${escapeHtml(point.whatsapp_url)}">💬 Falar com o responsável</a>` : ''}
            <a class="btn btn-outline-primary btn-sm" href="${escapeHtml(point.detail_url)}">Ver detalhes</a>
          </div>
        </div>
      `;
      L.marker([lat, lng]).addTo(markerLayer).bindPopup(popupHtml);
    });

    if (totalPontosEl) totalPontosEl.textContent = String(points.length);
    if (totalMetricEl) totalMetricEl.textContent = String(Math.round(totalMetric));
    if (totalMetricLabelEl) totalMetricLabelEl.textContent = metricLabel;

    if (adjustBounds && bounds.length > 0) {
      map.fitBounds(bounds, { padding: [30, 30] });
    } else if (adjustBounds) {
      map.setView([-12.8, -41.7], 7);
    }
  }

  async function refreshMap() {
    const response = await fetch(`/api/mapa?${getQueryString()}`, {
      headers: { Accept: 'application/json' },
    });
    cachedPoints = await response.json();
    renderMap(cachedPoints, true);
  }

  Object.values(filters).forEach((element) => {
    if (element) {
      element.addEventListener('change', refreshMap);
    }
  });

  map.on('zoomend', () => {
    if (cachedPoints.length > 0) {
      renderMap(cachedPoints, false);
    }
  });

  const button = document.getElementById('map-filter-button');
  if (button) {
    button.addEventListener('click', refreshMap);
  }

  const clearButton = document.getElementById('map-clear-filters');
  if (clearButton) {
    clearButton.addEventListener('click', () => {
      Object.values(filters).forEach((element) => {
        if (element) {
          element.value = '';
        }
      });
      refreshMap().catch((error) => {
        console.error(error);
      });
    });
  }

  refreshMap().catch((error) => {
    console.error(error);
  });
})();
