(() => {
  const mapElement = document.getElementById('leaflet-map');
  if (!mapElement || typeof L === 'undefined') return;

  const map = L.map('leaflet-map', {
    maxBounds: [[-18.75, -46.5], [-8.0, -37.0]],
    maxBoundsViscosity: 1.0,
    minZoom: 6,
    zoomControl: false,
    preferCanvas: true,
  }).setView([-12.8, -41.7], 7);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18,
    attribution: '&copy; OpenStreetMap contributors',
  }).addTo(map);
  L.control.zoom({ position: 'bottomright' }).addTo(map);

  const markerLayer = L.layerGroup().addTo(map);
  const totalPontosEl = document.getElementById('map-total-pontos');
  const totalMetricEl = document.getElementById('map-total-banners');
  const totalMetricLabelEl = document.getElementById('map-total-metric-label');
  const totalReplenishmentEl = document.getElementById('map-total-replenishment');
  const replenishmentKpiEl = document.getElementById('map-replenishment-kpi');

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

  function formatNumber(value) {
    return new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 2 }).format(Number(value || 0));
  }

  function getQueryString() {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, element]) => {
      if (element && element.value) params.set(key, element.value);
    });
    return params.toString();
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;').replaceAll("'", '&#039;');
  }

  function getPointValues(point) {
    return {
      totalInUse: Number(point.total_em_uso ?? point.total_estoque ?? 0),
      replenishment: Number(point.total_reposicao_necessaria ?? 0),
      occurrences: Number(point.occurrence_count ?? 0),
    };
  }

  function getStatus(point) {
    const values = getPointValues(point);
    if (values.replenishment > 0) return { className: 'status-replenishment', label: 'Reposição necessária' };
    if (values.totalInUse <= 0) return { className: 'status-empty', label: 'Sem material' };
    if (values.occurrences > 0) return { className: 'status-occurrence', label: 'Com ocorrência' };
    return { className: 'status-ok', label: 'Com material' };
  }

  function createPointIcon(point) {
    const values = getPointValues(point);
    const status = getStatus(point);
    return L.divIcon({
      className: 'map-point-icon-wrapper',
      html: '<div class="map-point-marker ' + status.className + '" title="' + escapeHtml(status.label) + '">' +
        '<span class="map-point-pulse"></span>' +
        '<span class="map-point-pin"><span class="map-point-quantity">' + formatNumber(values.totalInUse) + '</span></span>' +
        '</div>',
      iconSize: [58, 70], iconAnchor: [29, 58], popupAnchor: [0, -58], tooltipAnchor: [0, -52],
    });
  }

  function createClusterIcon(cluster) {
    const count = cluster.points.length;
    const statusClass = cluster.totalReplenishment > 0 ? 'status-replenishment' : 'status-ok';
    const size = Math.min(68, 42 + Math.min(count, 10) * 2);
    return L.divIcon({
      className: 'map-cluster-icon-wrapper',
      html: '<div class="map-cluster-marker ' + statusClass + '" style="width:' + size + 'px;height:' + size + 'px;">' +
        '<strong>' + formatNumber(count) + '</strong><span>pontos</span></div>',
      iconSize: [size, size], iconAnchor: [size / 2, size / 2],
    });
  }

  function buildPopup(point) {
    const values = getPointValues(point);
    const hasMaterialFilter = Boolean(filters.material_id && filters.material_id.value);
    const materialSummary = Array.isArray(point.materiais_resumo) ? point.materiais_resumo : [];
    const visibleMaterials = materialSummary.filter((item) => Number(item.quantidade || 0) > 0).slice(0, 5);
    const status = getStatus(point);
    const localizadores = Array.isArray(point.localizadores) ? point.localizadores : [];

    const materialHtml = visibleMaterials.length
      ? visibleMaterials.map((item) =>
          '<div class="map-popup-material"><span>' + escapeHtml(item.nome) + '</span><strong>' +
          formatNumber(item.quantidade) + '</strong></div>'
        ).join('')
      : '<div class="map-popup-empty">Nenhum material registrado</div>';

    const photoHtml = point.foto
      ? '<div class="map-popup-photo-wrap"><img class="map-popup-photo" src="/' + escapeHtml(point.foto) +
        '" alt="Foto do ponto"></div>'
      : '';

    const contactHtml = point.whatsapp_url
      ? '<a class="map-popup-action map-popup-action-whatsapp" target="_blank" rel="noopener noreferrer" href="' +
        escapeHtml(point.whatsapp_url) + '">' +
        '<i class="bi bi-whatsapp"></i><span>Falar com o responsável</span></a>'
      : '';

    return '<div class="map-popup-card">' +
      '<div class="map-popup-top">' +
        '<div class="map-popup-heading">' +
          '<span class="map-popup-kicker"><i class="bi bi-geo-alt-fill"></i>' +
            escapeHtml(point.municipio || 'Ponto') + '</span>' +
          '<h3>' + escapeHtml(point.nome) + '</h3>' +
        '</div>' +
        '<span class="map-popup-status ' + status.className + '">' +
          '<i class="bi bi-circle-fill"></i>' + escapeHtml(status.label) +
        '</span>' +
      '</div>' +

      '<div class="map-popup-summary">' +
        '<div class="map-popup-summary-item map-popup-summary-use">' +
          '<span>Em condições de uso</span><strong>' + formatNumber(values.totalInUse) + '</strong>' +
        '</div>' +
        '<div class="map-popup-summary-item ' + (values.replenishment > 0 ? 'is-alert' : '') + '">' +
          '<span>Reposição</span><strong>' + formatNumber(values.replenishment) + '</strong>' +
        '</div>' +
        '<div class="map-popup-summary-item ' + (values.occurrences > 0 ? 'has-occurrence' : '') + '">' +
          '<span>Ocorrências</span><strong>' + formatNumber(values.occurrences) + '</strong>' +
        '</div>' +
      '</div>' +

      '<div class="map-popup-section">' +
        '<div class="map-popup-section-heading">' +
          '<span class="map-popup-section-title">Materiais no ponto</span>' +
          (hasMaterialFilter ? '<span class="map-popup-filter-badge">Filtro aplicado</span>' : '') +
        '</div>' +
        '<div class="map-popup-material-list">' +
          (hasMaterialFilter && point.metric_label
            ? '<div class="map-popup-material"><span>' + escapeHtml(point.metric_label) + '</span><strong>' +
              formatNumber(point.metric_value) + '</strong></div>'
            : materialHtml) +
        '</div>' +
      '</div>' +

      '<div class="map-popup-meta">' +
        '<div class="map-popup-meta-row">' +
          '<i class="bi bi-person"></i><div><span>Responsável</span><strong>' +
          escapeHtml(point.responsavel_nome || 'Não informado') + '</strong></div>' +
        '</div>' +
        (localizadores.length
          ? '<div class="map-popup-meta-row">' +
            '<i class="bi bi-pin-map"></i><div><span>Localizador</span><strong>' +
            escapeHtml(localizadores.join(' • ')) + '</strong></div>' +
            '</div>'
          : '') +
      '</div>' +

      photoHtml +

      '<div class="map-popup-actions">' +
        contactHtml +
        '<a class="map-popup-action map-popup-action-details" href="' + escapeHtml(point.detail_url) + '">' +
          '<i class="bi bi-box-arrow-up-right"></i><span>Ver detalhes</span><i class="bi bi-arrow-right"></i>' +
        '</a>' +
      '</div>' +
    '</div>';
  }

  function aggregateByZoom(points, zoom) {
    const clusters = new Map();
    const precision = zoom <= 7 ? 1 : zoom <= 9 ? 2 : 3;
    const factor = 10 ** precision;
    points.forEach((point) => {
      const latKey = Math.round(Number(point.latitude) * factor) / factor;
      const lngKey = Math.round(Number(point.longitude) * factor) / factor;
      const key = latKey + ':' + lngKey;
      if (!clusters.has(key)) clusters.set(key, { lat: latKey, lng: lngKey, points: [], totalInUse: 0, totalReplenishment: 0 });
      const cluster = clusters.get(key);
      const values = getPointValues(point);
      cluster.points.push(point);
      cluster.totalInUse += values.totalInUse;
      cluster.totalReplenishment += values.replenishment;
    });
    return Array.from(clusters.values());
  }

  function updateMetrics(points) {
    const hasMaterialFilter = Boolean(filters.material_id && filters.material_id.value);
    const totalInUse = points.reduce((sum, point) => sum + getPointValues(point).totalInUse, 0);
    const totalReplenishment = points.reduce((sum, point) => sum + getPointValues(point).replenishment, 0);
    const metricTotal = hasMaterialFilter ? points.reduce((sum, point) => sum + Number(point.metric_value || 0), 0) : totalInUse;
    const metricLabel = hasMaterialFilter ? (points[0]?.metric_label || 'Material selecionado') : 'Em condições de uso';
    if (totalPontosEl) totalPontosEl.textContent = formatNumber(points.length);
    if (totalMetricEl) totalMetricEl.textContent = formatNumber(metricTotal);
    if (totalMetricLabelEl) totalMetricLabelEl.textContent = metricLabel;
    if (totalReplenishmentEl) totalReplenishmentEl.textContent = formatNumber(totalReplenishment);
    if (replenishmentKpiEl) replenishmentKpiEl.classList.toggle('has-alert', totalReplenishment > 0);
  }

  function renderMap(points, adjustBounds = true) { // NOSONAR
    markerLayer.clearLayers();
    updateMetrics(points);
    const bounds = [];
    const duplicateCounts = new Map();
    const useClusterMode = map.getZoom() <= 9;

    if (useClusterMode) {
      aggregateByZoom(points, map.getZoom()).forEach((cluster) => {
        const count = cluster.points.length;
        bounds.push([cluster.lat, cluster.lng]);
        const marker = L.marker([cluster.lat, cluster.lng], { icon: createClusterIcon(cluster), keyboard: true }).addTo(markerLayer);
        const preview = cluster.points.slice(0, 6).map((point) => {
          const values = getPointValues(point);
          return '<div class="map-cluster-preview-row"><span>' + escapeHtml(point.nome) + '</span><strong>' + formatNumber(values.totalInUse) + '</strong></div>';
        }).join('');
        marker.bindTooltip('<div class="map-hover-tooltip"><strong>' + formatNumber(count) + ' pontos nesta área</strong><span>' + formatNumber(cluster.totalInUse) + ' em condições de uso</span></div>', {
          direction: 'top', offset: [0, -10], opacity: 1, className: 'map-hover-tooltip-container',
        });
        marker.bindPopup('<div class="map-cluster-popup"><div class="map-cluster-popup-title"><span>Agrupamento de pontos</span><strong>' + formatNumber(count) + '</strong></div>' +
          '<div class="map-cluster-popup-subtitle">Em condições de uso: <strong>' + formatNumber(cluster.totalInUse) + '</strong></div>' +
          '<div class="map-cluster-preview">' + preview + '</div>' +
          (cluster.totalReplenishment > 0 ? '<div class="map-cluster-alert"><i class="bi bi-exclamation-triangle-fill"></i>' + formatNumber(cluster.totalReplenishment) + ' unidades precisam de reposição</div>' : '') +
          '</div>');
        marker.on('click', () => map.setView([cluster.lat, cluster.lng], Math.min(map.getZoom() + 2, 14), { animate: true }));
      });
      if (adjustBounds && bounds.length) map.fitBounds(bounds, { padding: [90, 90], maxZoom: 10 });
      else if (adjustBounds) map.setView([-12.8, -41.7], 7);
      return;
    }

    points.forEach((point) => {
      const values = getPointValues(point);
      const coordinateKey = point.latitude + ':' + point.longitude;
      const duplicateIndex = duplicateCounts.get(coordinateKey) || 0;
      duplicateCounts.set(coordinateKey, duplicateIndex + 1);
      const offset = duplicateIndex * 0.00022;
      const lat = Number(point.latitude) + (duplicateIndex % 2 === 0 ? offset : -offset);
      const lng = Number(point.longitude) + (duplicateIndex % 3 === 0 ? offset * 1.2 : -offset * 1.2);
      bounds.push([lat, lng]);
      const marker = L.marker([lat, lng], {
        icon: createPointIcon(point), keyboard: true, riseOnHover: true, zIndexOffset: values.replenishment > 0 ? 300 : 0,
      }).addTo(markerLayer);
      marker.bindTooltip('<div class="map-hover-tooltip"><strong>' + escapeHtml(point.nome) + '</strong><span>' + formatNumber(values.totalInUse) + ' em condições de uso</span>' +
        (values.replenishment > 0 ? '<em>' + formatNumber(values.replenishment) + ' para reposição</em>' : '<em>Sem necessidade de reposição</em>') + '</div>', {
        direction: 'top', offset: [0, -12], opacity: 1, className: 'map-hover-tooltip-container',
      });
      marker.bindPopup(buildPopup(point), { maxWidth: 390, minWidth: 320, className: 'map-professional-popup', closeButton: true });
    });
    if (adjustBounds && bounds.length) map.fitBounds(bounds, { padding: [100, 100], maxZoom: 14 });
    else if (adjustBounds) map.setView([-12.8, -41.7], 7);
  }

  async function refreshMap(adjustBounds = true) {
    try {
      mapElement.classList.add('is-loading');
      const response = await fetch('/api/mapa?' + getQueryString(), { headers: { Accept: 'application/json' } });
      if (!response.ok) throw new Error('Falha ao carregar o mapa (' + response.status + ').');
      cachedPoints = await response.json();
      renderMap(cachedPoints, adjustBounds);
    } catch (error) {
      console.error(error);
      mapElement.classList.add('has-error');
    } finally {
      mapElement.classList.remove('is-loading');
    }
  }

  function clearFilters() {
    Object.values(filters).forEach((element) => { if (element) element.value = ''; });
    refreshMap(true);
  }

  Object.values(filters).forEach((element) => {
    if (element) element.addEventListener('change', () => refreshMap(true));
  });
  map.on('zoomend', () => { if (cachedPoints.length) renderMap(cachedPoints, false); });
  const button = document.getElementById('map-filter-button');
  if (button) button.addEventListener('click', () => refreshMap(true));
  const clearButton = document.getElementById('map-clear-filters');
  const clearTopButton = document.getElementById('map-clear-filters-top');
  if (clearButton) clearButton.addEventListener('click', clearFilters);
  if (clearTopButton) clearTopButton.addEventListener('click', clearFilters);
  refreshMap(true);
})();