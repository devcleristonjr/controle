/**
 * Funções auxiliares para o campo único de localização ("Buscar endereço,
 * coordenadas ou colar link do Maps"). Reconhece, por regex:
 *   a) coordenadas decimais        -12.92775, -38.38744
 *   b) coordenadas DMS             12°55'39.9"S 38°23'14.8"W
 *   c) links do Google Maps        https://www.google.com/maps/@-12.9,-38.3,17z
 *   d) endereço em texto plano     (não casa com os padrões acima)
 *
 * Todas as funções retornam/armazenam o valor sempre em graus decimais (DD).
 */
(function (global) {
  const DECIMAL_PAIR_RE = /(-?\d{1,3}(?:\.\d+))\s*[,; ]\s*(-?\d{1,3}(?:\.\d+))/;

  const DMS_TOKEN_RE = /(\d{1,3})\s*[°º]\s*(\d{1,2})\s*['’]\s*(\d{1,2}(?:\.\d+)?)\s*["”]?\s*([NSEW])/gi;

  const GOOGLE_MAPS_HOST_RE = /(google\.[a-z.]+\/maps|maps\.google\.|goo\.gl\/maps|maps\.app\.goo\.gl)/i;

  const SHORT_LINK_RE = /^https?:\/\/(maps\.app\.goo\.gl|goo\.gl\/maps)\//i;

  function dmsToDecimal(degrees, minutes, seconds, direction) {
    let decimal = Number(degrees) + Number(minutes) / 60 + Number(seconds) / 3600;
    if (/[SW]/i.test(direction)) decimal *= -1;
    return decimal;
  }

  /** Tenta extrair um par de coordenadas DMS (graus/minutos/segundos) de um texto. */
  function parseDmsPair(text) {
    const matches = [...String(text || '').matchAll(DMS_TOKEN_RE)];
    if (matches.length < 2) return null;

    const latitude = dmsToDecimal(matches[0][1], matches[0][2], matches[0][3], matches[0][4]);
    const longitude = dmsToDecimal(matches[1][1], matches[1][2], matches[1][3], matches[1][4]);
    if (Number.isNaN(latitude) || Number.isNaN(longitude)) return null;

    return { latitude: round6(latitude), longitude: round6(longitude) };
  }

  /** Tenta extrair um par de coordenadas decimais simples (ex.: "-12.92, -38.38"). */
  function parseDecimalPair(text) {
    const match = DECIMAL_PAIR_RE.exec(String(text || '').trim());
    if (!match) return null;

    const latitude = Number(match[1]);
    const longitude = Number(match[2]);
    if (Number.isNaN(latitude) || Number.isNaN(longitude)) return null;
    if (Math.abs(latitude) > 90 || Math.abs(longitude) > 180) return null;

    return { latitude: round6(latitude), longitude: round6(longitude) };
  }

  /** Extrai coordenadas de uma URL do Google Maps (padrões @lat,lon ou ?q=lat,lon ou !3dlat!4dlon). */
  function parseGoogleMapsUrl(text) {
    const value = String(text || '').trim();
    if (!/^https?:\/\//i.test(value) || !GOOGLE_MAPS_HOST_RE.test(value)) return null;

    // Padrão de URLs com local nomeado: .../@-12.9,-38.3,17z ou !3d-12.9!4d-38.3
    const atMatch = value.match(/@(-?\d{1,3}\.\d+),(-?\d{1,3}\.\d+)/);
    if (atMatch) return { latitude: round6(Number(atMatch[1])), longitude: round6(Number(atMatch[2])) };

    const bangMatch = value.match(/!3d(-?\d{1,3}\.\d+)!4d(-?\d{1,3}\.\d+)/);
    if (bangMatch) return { latitude: round6(Number(bangMatch[1])), longitude: round6(Number(bangMatch[2])) };

    const queryMatch = value.match(/[?&](?:q|query|ll)=(-?\d{1,3}\.\d+),(-?\d{1,3}\.\d+)/);
    if (queryMatch) return { latitude: round6(Number(queryMatch[1])), longitude: round6(Number(queryMatch[2])) };

    return null;
  }

  function isShortGoogleMapsLink(text) {
    return SHORT_LINK_RE.test(String(text || '').trim());
  }

  function isLikelyUrl(text) {
    return /^https?:\/\//i.test(String(text || '').trim());
  }

  function round6(value) {
    return Math.round(value * 1e6) / 1e6;
  }

  /**
   * Classifica e interpreta o texto colado/digitado no campo único de localização.
   * @returns {{ kind: 'coordinates'|'maps_url'|'short_link'|'address', latitude?: number, longitude?: number, raw: string }}
   */
  function parseSmartLocationInput(rawText) {
    const text = String(rawText || '').trim();
    if (!text) return { kind: 'empty', raw: text };

    if (isLikelyUrl(text)) {
      if (isShortGoogleMapsLink(text)) {
        return { kind: 'short_link', raw: text };
      }
      const fromUrl = parseGoogleMapsUrl(text);
      if (fromUrl) return { kind: 'coordinates', raw: text, ...fromUrl };
      // URL de mapa sem coordenadas visíveis (ex.: encurtador desconhecido): trata como link curto.
      if (GOOGLE_MAPS_HOST_RE.test(text)) return { kind: 'short_link', raw: text };
    }

    const dms = parseDmsPair(text);
    if (dms) return { kind: 'coordinates', raw: text, ...dms };

    const decimal = parseDecimalPair(text);
    if (decimal) return { kind: 'coordinates', raw: text, ...decimal };

    return { kind: 'address', raw: text };
  }

  global.LocationInput = {
    parseSmartLocationInput: parseSmartLocationInput,
    parseDmsPair: parseDmsPair,
    parseDecimalPair: parseDecimalPair,
    parseGoogleMapsUrl: parseGoogleMapsUrl,
    isShortGoogleMapsLink: isShortGoogleMapsLink,
  };
})(window);
