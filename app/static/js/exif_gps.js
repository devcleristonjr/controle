/**
 * Leitura mínima de GPS a partir dos metadados EXIF de uma foto JPEG, sem
 * dependências externas. Usado para preencher automaticamente a localização
 * quando a foto do material já contém coordenadas registradas pelo celular.
 */
(function (global) {
  function readAsArrayBuffer(file) {
    return new Promise(function (resolve, reject) {
      const reader = new FileReader();
      reader.onload = function () { resolve(reader.result); };
      reader.onerror = function () { reject(reader.error); };
      reader.readAsArrayBuffer(file);
    });
  }

  const TYPE_SIZES = { 1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 9: 4, 10: 8 };

  function readTagValue(view, tiffStart, entryValueOffset, type, count, littleEndian) {
    const size = (TYPE_SIZES[type] || 1) * count;
    const valueOffset = size > 4 ? tiffStart + view.getUint32(entryValueOffset, littleEndian) : entryValueOffset;

    if (type === 5 || type === 10) { // RATIONAL / SRATIONAL arrays (GPS coordinates use these)
      const values = [];
      for (let i = 0; i < count; i += 1) {
        const numerator = view.getUint32(valueOffset + i * 8, littleEndian);
        const denominator = view.getUint32(valueOffset + i * 8 + 4, littleEndian);
        values.push(denominator === 0 ? 0 : numerator / denominator);
      }
      return values;
    }

    if (type === 2) { // ASCII
      let text = '';
      for (let i = 0; i < count; i += 1) {
        const code = view.getUint8(valueOffset + i);
        if (code === 0) break;
        text += String.fromCharCode(code);
      }
      return text;
    }

    if (type === 3) return view.getUint16(valueOffset, littleEndian);
    if (type === 4) return view.getUint32(valueOffset, littleEndian);
    return null;
  }

  function parseIfd(view, tiffStart, ifdOffset, littleEndian) {
    const entries = {};
    const entryCount = view.getUint16(ifdOffset, littleEndian);
    for (let i = 0; i < entryCount; i += 1) {
      const entryOffset = ifdOffset + 2 + i * 12;
      const tag = view.getUint16(entryOffset, littleEndian);
      const type = view.getUint16(entryOffset + 2, littleEndian);
      const numValues = view.getUint32(entryOffset + 4, littleEndian);
      entries[tag] = readTagValue(view, tiffStart, entryOffset + 8, type, numValues, littleEndian);
    }
    return entries;
  }

  function dmsArrayToDecimal(dms, ref) {
    if (!Array.isArray(dms) || dms.length < 3) return null;
    const [degrees, minutes, seconds] = dms;
    let decimal = degrees + minutes / 60 + seconds / 3600;
    if (ref === 'S' || ref === 'W') decimal *= -1;
    return decimal;
  }

  /**
   * @param {File} file
   * @returns {Promise<{latitude: number, longitude: number} | null>}
   */
  async function extractGpsFromImageFile(file) {
    if (!file || !/image\/(jpe?g)/i.test(file.type || '')) {
      return null;
    }

    let buffer;
    try {
      buffer = await readAsArrayBuffer(file);
    } catch (error) {
      console.warn('Não foi possível ler o arquivo da foto.', error);
      return null;
    }

    try {
      const view = new DataView(buffer);
      if (view.getUint16(0) !== 0xffd8) return null; // não é JPEG

      let offset = 2;
      while (offset < view.byteLength - 4) {
        if (view.getUint8(offset) !== 0xff) break;
        const marker = view.getUint8(offset + 1);

        if (marker === 0xd8 || marker === 0xd9 || (marker >= 0xd0 && marker <= 0xd7)) {
          offset += 2;
          continue;
        }

        const segmentLength = view.getUint16(offset + 2);

        if (marker === 0xe1) {
          const exifHeaderOffset = offset + 4;
          const isExifHeader =
            view.getUint32(exifHeaderOffset) === 0x45786966 && view.getUint16(exifHeaderOffset + 4) === 0x0000;

          if (isExifHeader) {
            const tiffStart = exifHeaderOffset + 6;
            const littleEndian = view.getUint16(tiffStart) === 0x4949;
            const firstIfdOffset = view.getUint32(tiffStart + 4, littleEndian);
            const ifd0 = parseIfd(view, tiffStart, tiffStart + firstIfdOffset, littleEndian);
            const gpsIfdPointer = ifd0[0x8825];

            if (gpsIfdPointer) {
              const gpsIfd = parseIfd(view, tiffStart, tiffStart + gpsIfdPointer, littleEndian);
              const latitude = dmsArrayToDecimal(gpsIfd[0x0002], gpsIfd[0x0001]);
              const longitude = dmsArrayToDecimal(gpsIfd[0x0004], gpsIfd[0x0003]);

              if (latitude !== null && longitude !== null && !Number.isNaN(latitude) && !Number.isNaN(longitude)) {
                return {
                  latitude: Number(latitude.toFixed(6)),
                  longitude: Number(longitude.toFixed(6)),
                };
              }
            }
          }
        }

        offset += 2 + segmentLength;
      }
    } catch (error) {
      console.warn('Falha ao interpretar os metadados EXIF da foto.', error);
    }

    return null;
  }

  global.ExifGps = { extractGpsFromImageFile: extractGpsFromImageFile };
})(window);
