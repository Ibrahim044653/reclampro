// Mini-bibliothèque de graphiques SVG sans dépendance.

const PALETTE = ["#185FA5", "#1D9E75", "#BA7517", "#E24B4A", "#7A4FA0", "#888780"];

function couleurPour(i) { return PALETTE[i % PALETTE.length]; }

// Donut chart — n segments avec valeurs proportionnelles.
function donutSvg(segments, opts = {}) {
  const taille = opts.size || 130;
  const centre = taille / 2;
  const rayon = centre - 12;
  const epaisseur = opts.thickness || 14;
  const circ = 2 * Math.PI * rayon;
  const total = segments.reduce((s, x) => s + x.valeur, 0) || 1;

  let offset = 0;
  const arcs = segments.map((s, i) => {
    const longueur = (s.valeur / total) * circ;
    const cercle = `
      <circle cx="${centre}" cy="${centre}" r="${rayon}" fill="none"
        stroke="${s.couleur || couleurPour(i)}" stroke-width="${epaisseur}"
        stroke-dasharray="${longueur} ${circ - longueur}"
        stroke-dashoffset="${-offset}"
        transform="rotate(-90 ${centre} ${centre})"/>`;
    offset += longueur;
    return cercle;
  }).join("");

  return `
    <svg class="donut-svg" width="${taille}" height="${taille}" viewBox="0 0 ${taille} ${taille}">
      <circle cx="${centre}" cy="${centre}" r="${rayon}" fill="none" stroke="#F1EFE8" stroke-width="${epaisseur}"/>
      ${arcs}
    </svg>`;
}

// Line chart — series multiples sur une grille temporelle commune.
function lineChartSvg(labels, series, opts = {}) {
  const w = opts.width || 600, h = opts.height || 200;
  const padX = 36, padY = 24;
  const innerW = w - padX * 2, innerH = h - padY * 2;
  const n = labels.length;
  const xStep = n > 1 ? innerW / (n - 1) : innerW;

  const maxV = Math.max(1, ...series.flatMap(s => s.valeurs));

  const yTicks = 4;
  const grid = Array.from({ length: yTicks + 1 }, (_, i) => {
    const y = padY + (innerH / yTicks) * i;
    const v = Math.round(maxV - (maxV / yTicks) * i);
    return `
      <line x1="${padX}" y1="${y}" x2="${w - padX}" y2="${y}" stroke="#EFEDE5" stroke-width="1"/>
      <text x="${padX - 6}" y="${y + 3}" text-anchor="end" font-size="9" fill="#888780">${v}</text>`;
  }).join("");

  const xLabels = labels.map((l, i) => `
    <text x="${padX + xStep * i}" y="${h - 6}" text-anchor="middle" font-size="10" fill="#888780">${l}</text>
  `).join("");

  const seriesSvg = series.map((s, idx) => {
    const couleur = s.couleur || couleurPour(idx);
    const pts = s.valeurs.map((v, i) => {
      const x = padX + xStep * i;
      const y = padY + innerH - (v / maxV) * innerH;
      return [x, y];
    });
    const path = pts.map(([x, y], i) => (i === 0 ? `M${x},${y}` : `L${x},${y}`)).join(" ");
    const aire = `${path} L${pts[pts.length - 1][0]},${padY + innerH} L${pts[0][0]},${padY + innerH} Z`;
    const dots = pts.map(([x, y]) => `<circle cx="${x}" cy="${y}" r="3" fill="${couleur}"/>`).join("");
    return `
      <path d="${aire}" fill="${couleur}" fill-opacity="0.08"/>
      <path d="${path}" fill="none" stroke="${couleur}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
      ${dots}`;
  }).join("");

  return `
    <svg width="100%" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" style="max-height:240px">
      ${grid}
      ${seriesSvg}
      ${xLabels}
    </svg>`;
}

// Bar chart — barres verticales en groupes (multi-séries optionnel).
function barChartSvg(labels, series, opts = {}) {
  const w = opts.width || 500, h = opts.height || 180;
  const padX = 30, padY = 18;
  const innerW = w - padX * 2, innerH = h - padY * 2;
  const n = labels.length;
  const groupW = innerW / n;
  const barW = (groupW - 6) / series.length;

  const maxV = Math.max(1, ...series.flatMap(s => s.valeurs));

  const bars = series.flatMap((s, si) => s.valeurs.map((v, i) => {
    const x = padX + groupW * i + 3 + barW * si;
    const hh = (v / maxV) * innerH;
    const y = padY + innerH - hh;
    return `<rect x="${x}" y="${y}" width="${barW - 2}" height="${hh}" rx="3"
      fill="${s.couleur || couleurPour(si)}"/>`;
  })).join("");

  const xLabels = labels.map((l, i) => `
    <text x="${padX + groupW * i + groupW / 2}" y="${h - 4}"
      text-anchor="middle" font-size="10" fill="#888780">${l}</text>
  `).join("");

  return `
    <svg width="100%" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" style="max-height:200px">
      ${bars}
      ${xLabels}
    </svg>`;
}

// Légende universelle pour un graphique multi-séries ou un donut.
function legendHtml(items) {
  return `<div class="legend-list">${items.map((it, i) => `
    <div class="legend-item">
      <div class="legend-dot" style="background:${it.couleur || couleurPour(i)}"></div>
      <div class="legend-text">${it.label}</div>
      <div class="legend-val">${it.valeur}${it.suffixe || ""}</div>
    </div>`).join("")}</div>`;
}
