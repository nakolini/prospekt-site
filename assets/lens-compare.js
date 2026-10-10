// Lens comparison tool. The math mirrors gen/lensmath.py; gen/tests/test_js_parity.py
// runs both on the same inputs. Photos chosen by the visitor stay in the browser.
(function () {
  "use strict";

  var FULL_FRAME_DIAGONAL = Math.hypot(36, 24);

  function close(a, b) { return Math.abs(a - b) < 1e-9; }

  function sensorAspect(crop) {
    return close(crop, 2.0) || close(crop, 0.79) ? [4, 3] : [3, 2];
  }

  function sensorSize(crop) {
    var a = sensorAspect(crop);
    var unit = FULL_FRAME_DIAGONAL / crop / Math.hypot(a[0], a[1]);
    return [a[0] * unit, a[1] * unit];
  }

  function angleOfView(dimension, focal) {
    return (2 * Math.atan(dimension / (2 * focal)) * 180) / Math.PI;
  }

  function angles(focal, crop) {
    var s = sensorSize(crop);
    return [angleOfView(s[0], focal), angleOfView(s[1], focal), angleOfView(Math.hypot(s[0], s[1]), focal)];
  }

  // A vertical frame puts the sensor's long side upright.
  function frameInPhoto(focal, crop, photoEquivalent, photoAspect, vertical) {
    var s = sensorSize(crop);
    if (vertical) s = [s[1], s[0]];
    var unit = FULL_FRAME_DIAGONAL / Math.hypot(photoAspect, 1);
    var photoHalfW = (photoAspect * unit) / 2 / photoEquivalent;
    var photoHalfH = unit / 2 / photoEquivalent;
    return [s[0] / 2 / focal / photoHalfW, s[1] / 2 / focal / photoHalfH];
  }

  // Reads FocalLengthIn35mmFilm (EXIF tag 0xA405) from a JPEG, or returns null.
  function exifEquivalentFocal(buffer) {
    var view = new DataView(buffer);
    if (view.byteLength < 4 || view.getUint16(0) !== 0xffd8) return null;
    var offset = 2;
    while (offset + 4 <= view.byteLength) {
      var marker = view.getUint16(offset);
      var size = view.getUint16(offset + 2);
      if (marker === 0xffe1 && view.getUint32(offset + 4) === 0x45786966) {
        return readTiff(view, offset + 10);
      }
      if ((marker & 0xff00) !== 0xff00 || marker === 0xffda) return null;
      offset += 2 + size;
    }
    return null;
  }

  function readTiff(view, start) {
    if (start + 8 > view.byteLength) return null;
    var little = view.getUint16(start) === 0x4949;
    function u16(o) { return view.getUint16(start + o, little); }
    function u32(o) { return view.getUint32(start + o, little); }
    function find(ifd, tag) {
      if (start + ifd + 2 > view.byteLength) return null;
      var count = u16(ifd);
      for (var i = 0; i < count; i++) {
        var entry = ifd + 2 + i * 12;
        if (start + entry + 12 > view.byteLength) return null;
        if (u16(entry) === tag) return entry;
      }
      return null;
    }
    var exifPointer = find(u32(4), 0x8769);
    if (exifPointer === null) return null;
    var focal = find(u32(exifPointer + 8), 0xa405);
    if (focal === null) return null;
    var value = u16(focal + 8);
    return value > 0 ? value : null;
  }

  // Width and height of the scene at a distance, camera held horizontally,
  // in the unit of distance: distance x sensor size / focal.
  function coverage(focal, crop, distance) {
    var s = sensorSize(crop);
    return [(distance * s[0]) / focal, (distance * s[1]) / focal];
  }

  // How far to stand so a subject of this height fills `fill` of the frame.
  // Vertical framing puts the sensor's long side upright.
  function distanceToFit(subject, focal, crop, vertical, fill) {
    var s = sensorSize(crop);
    return ((subject / fill) * focal) / (vertical ? s[0] : s[1]);
  }

  // The focal length that fits a subject of this height at a distance.
  function focalToFit(subject, distance, crop, vertical, fill) {
    var s = sensorSize(crop);
    return (distance * fill * (vertical ? s[0] : s[1])) / subject;
  }

  var LensMath = {
    exifEquivalentFocal: exifEquivalentFocal, sensorAspect: sensorAspect, sensorSize: sensorSize,
    angles: angles, frameInPhoto: frameInPhoto, coverage: coverage, distanceToFit: distanceToFit,
    focalToFit: focalToFit,
  };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = LensMath;
    return;
  }

  var dataNode = document.getElementById("tool-data");
  var form = document.getElementById("tool");
  if (!dataNode || !form) return;
  var data = JSON.parse(dataNode.textContent);
  var strings = data.strings;
  var FOOT = data.foot;

  function $(id) { return document.getElementById(id); }
  var bodySelects = [$("body"), $("body2")];
  bodySelects[0].innerHTML = data.options;
  bodySelects[1].insertAdjacentHTML("beforeend", data.options);
  var chipsBox = $("chips");
  var zoomsBox = $("zooms");
  var customInput = $("custom");
  var zoomFrom = $("zoom-from");
  var zoomTo = $("zoom-to");
  var distanceInput = $("distance");
  var subjectInput = $("subject");
  var stage = $("stage");
  var photo = $("photo");
  var notes = $("notes");
  var legend = $("legend");
  var results = $("results");
  var resultsBox = $("results-box");
  var viewerHint = $("viewer-hint");
  var lensCta = $("lens-cta");
  var lensBack = $("lens-back");
  var body2Box = $("body2-box");
  var addBody2 = $("add-body2");
  var distanceSummary = $("distance-summary");
  var showAngles = $("show-angles");
  var ownBox = $("own");
  var fileInput = $("file");
  var photoFocalInput = $("photo-focal");
  var shareStatus = $("share-status");
  var scene = $("scene");
  var sceneActions = $("scene-actions");
  var sceneNote = $("scene-note");
  var customError = $("custom-error");
  var zoomError = $("zoom-error");
  var photoError = $("photo-error");
  var focalNote = $("photo-focal-note");

  var state = {
    bodies: ["generic-1", ""],
    focals: [24, 35, 50, 85],
    // The focal lengths picked on their own, which removing a zoom keeps.
    picked: [24, 35, 50, 85],
    zooms: [],
    distance: 3,
    unit: "m",
    subject: 1.8,
    // Distance and height in metres as well, so switching units back and
    // forth returns the same numbers; distance and subject are in state.unit.
    metres: { distance: 3, subject: 1.8 },
    vertical: true,
    sample: 0,
    photoFocal: data.samples[0].focal,
    selected: null,
    ownUrl: null,
    // The person scene instead of a photo; fit is the last "Fit" action, so
    // its lens view can say what it picked, and fitAdded the chip each kind
    // of Fit added, so the next one replaces it.
    scene: false,
    fit: null,
    fitAdded: {},
  };

  // Numbers the page's way ("1,200.5", "1.200,5", "1 200,5"), always in Latin digits like the rest of the site.
  var formats = {};
  function num(value, decimals, upTo) {
    var id = decimals + "-" + upTo;
    formats[id] = formats[id] || new Intl.NumberFormat(data.lang + "-u-nu-latn", {
      minimumFractionDigits: decimals, maximumFractionDigits: upTo === undefined ? decimals : upTo,
    });
    return formats[id].format(value);
  }
  // Keeps "24 mm" from turning into "mm 24" on right-to-left pages.
  function isolate(text) { return data.rtl ? "⁦" + text + "⁩" : text; }
  function mm(value) { return isolate(num(Math.round(value), 0) + "\u00a0mm"); }
  function deg(value) { return isolate(num(value, 1) + "°"); }
  // Lengths: one decimal, two below 1, none from 100 up.
  function decimalsFor(value) { return value < 1 ? 2 : value < 100 ? 1 : 0; }
  function len(value) { return num(value, decimalsFor(value)); }
  // Lengths keep a no-break space before the unit so "3.1 m" never wraps.
  function length(value) { return isolate(len(value) + "\u00a0" + state.unit); }
  // A value the visitor typed, as typed: "3 m", "1.8 m".
  function typed(value) { return isolate(num(value, 0, 2) + "\u00a0" + state.unit); }
  // Width and height share the precision of the larger: "1.4 × 1.0 m", not "1.4 × 0.96 m".
  function size(pair) {
    var d = decimalsFor(Math.max(pair[0], pair[1]));
    return isolate(num(pair[0], d) + "\u00a0\u00d7 " + num(pair[1], d) + "\u00a0" + state.unit);
  }
  function fill(template, values) {
    return template.replace(/\{(\w+)\}/g, function (all, key) { return key in values ? values[key] : all; });
  }
  function escapeHtml(text) {
    return String(text).replace(/[&<>"]/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[ch];
    });
  }

  // The chosen cameras: the first always, the second when picked.
  function cameras() {
    return bodySelects.map(function (select, slot) {
      var option = select.options[select.selectedIndex];
      if (!option || !option.value) return null;
      // label goes inside parentheses after a focal length: "24 mm (Full frame, 1x)".
      return {
        slot: slot, crop: parseFloat(option.getAttribute("data-crop")), name: option.textContent,
        label: option.getAttribute("data-label") || option.textContent,
      };
    }).filter(Boolean);
  }

  // A sample's own size: with srcset the browser reports a rounded one (800 x 533).
  function photoAspect() {
    var sample = data.samples[state.sample];
    if (!showingOwn()) return sample.width / sample.height;
    return photo.naturalWidth && photo.naturalHeight ? photo.naturalWidth / photo.naturalHeight : 1.5;
  }

  function zoomName(zoom) { return zoom[0] + "-" + zoom[1]; }
  // "(24-70)" after a focal length that ends one of the chosen zooms.
  function zoomsEndingAt(focal) {
    return state.zooms.filter(function (z) { return z[0] === focal || z[1] === focal; }).map(zoomName);
  }
  function focalLabel(focal) {
    var zooms = zoomsEndingAt(focal);
    return num(focal, 0) + " mm" + (zooms.length ? " (" + zooms.join(", ") + ")" : "");
  }

  function insertSorted(box, chip, value, attr) {
    var later = Array.prototype.find.call(box.children, function (c) {
      return parseFloat(c.getAttribute(attr)) > value;
    });
    box.insertBefore(chip, later || box.querySelector(".more"));
  }

  function makeChip(attr, value) {
    var chip = document.createElement("button");
    chip.type = "button";
    chip.className = "chip";
    chip.setAttribute(attr, value);
    chip.setAttribute("aria-label", value + " mm");
    chip.textContent = value;
    return chip;
  }

  function ensureChip(focal) {
    if (chipsBox.querySelector('[data-focal="' + focal + '"]')) return;
    insertSorted(chipsBox, makeChip("data-focal", String(focal)), focal, "data-focal");
  }

  function ensureZoomChip(zoom) {
    if (zoomsBox.querySelector('[data-zoom="' + zoomName(zoom) + '"]')) return;
    insertSorted(zoomsBox, makeChip("data-zoom", zoomName(zoom)), zoom[0], "data-zoom");
  }

  function syncChips() {
    state.focals.forEach(ensureChip);
    state.zooms.forEach(ensureZoomChip);
    Array.prototype.forEach.call(chipsBox.querySelectorAll("[data-focal]"), function (chip) {
      var focal = parseFloat(chip.getAttribute("data-focal"));
      chip.setAttribute("aria-pressed", state.focals.indexOf(focal) >= 0 ? "true" : "false");
    });
    var names = state.zooms.map(zoomName);
    Array.prototype.forEach.call(zoomsBox.querySelectorAll("[data-zoom]"), function (chip) {
      chip.setAttribute("aria-pressed", names.indexOf(chip.getAttribute("data-zoom")) >= 0 ? "true" : "false");
    });
  }

  function svgEl(name, attrs) {
    var el = document.createElementNS("http://www.w3.org/2000/svg", name);
    Object.keys(attrs).forEach(function (k) { el.setAttribute(k, attrs[k]); });
    return el;
  }

  function key(focal, slot) { return focal + "|" + slot; }

  // The person scene. The right half of a standing figure, 1000 units from
  // the top of the head to the soles, as cubic segments from the crown down
  // the outside of the arm and leg and back up to the crotch; mirrored below.
  var FIGURE_HALF = [
    [29, 0, 48, 18, 48, 52], [51, 55, 53, 66, 52, 80], [51, 89, 48, 93, 45, 95], [43, 108, 37, 116, 30, 124],
    [26, 128, 25, 134, 25, 144], [26, 156, 30, 166, 46, 172], [72, 180, 104, 182, 120, 192],
    [136, 204, 142, 228, 141, 256], [141, 300, 139, 360, 138, 410], [140, 440, 142, 470, 140, 500],
    [138, 525, 134, 545, 132, 560], [136, 585, 138, 620, 128, 646], [122, 660, 108, 660, 106, 644],
    [102, 620, 106, 590, 110, 562], [112, 520, 112, 470, 115, 420], [116, 360, 112, 300, 104, 264],
    [100, 300, 87, 352, 85, 402], [84, 440, 97, 468, 99, 510], [101, 560, 95, 650, 84, 738],
    [80, 772, 87, 800, 83, 850], [79, 900, 62, 930, 58, 955], [62, 972, 76, 984, 76, 993],
    [76, 1002, 64, 1003, 48, 1003], [38, 1003, 24, 1003, 23, 994], [22, 982, 26, 968, 26, 950],
    [22, 900, 19, 860, 23, 815], [25, 780, 20, 752, 20, 732], [18, 650, 10, 582, 0, 542],
  ];
  var FIGURE = (function () {
    var ends = [[0, 0]].concat(FIGURE_HALF.map(function (c) { return [c[4], c[5]]; }));
    var d = "M0 0" + FIGURE_HALF.map(function (c) { return "C" + c.join(" "); }).join("");
    for (var i = FIGURE_HALF.length - 1; i >= 0; i--) {
      var c = FIGURE_HALF[i];
      d += "C" + [-c[2], c[3], -c[0], c[1], -ends[i][0], ends[i][1]].join(" ");
    }
    return d + "Z";
  })();

  function gradient(defs, id, attrs, stops) {
    var g = svgEl("linearGradient", Object.assign({ id: id, gradientUnits: "userSpaceOnUse" }, attrs));
    stops.forEach(function (stop) { g.appendChild(svgEl("stop", { offset: stop[0], "stop-color": stop[1] })); });
    defs.appendChild(g);
  }

  // Scene units (1000 across) per unit of height at 1 unit of distance.
  function sceneScale(focal, aspect) {
    var unit = FULL_FRAME_DIAGONAL / Math.hypot(aspect, 1);
    return (1000 / 2) / ((aspect * unit) / 2 / focal);
  }

  // A level camera at eye level, a floor of 1 m tiles running to the horizon
  // and a figure of the subject height at the subject distance. Everything is
  // projected like the photos (size / distance x focal), with the view shifted
  // so the aim point is in the middle: what's at the subject distance is
  // exactly to scale, and the frames are centred on the body or the head.
  // o: focal (35 mm equivalent of the whole scene), aspect, distance, height,
  // eye and tile (in the unit of distance), aim (height of the middle), id.
  function drawScene(svg, o) {
    var w = 1000, h = w / o.aspect;
    var k = sceneScale(o.focal, o.aspect);
    var shift = (o.aim - o.eye) / o.distance;
    function sy(height, distance) { return h / 2 - ((height - o.eye) / distance - shift) * k; }
    var horizon = h / 2 + shift * k;
    svg.textContent = "";
    svg.setAttribute("viewBox", "0 0 " + w + " " + h);
    var defs = svgEl("defs", {});
    svg.appendChild(defs);
    // Shading by angle from the horizon, so it zooms like the scene.
    gradient(defs, o.id + "-wall", { x1: 0, y1: horizon - 0.6 * k, x2: 0, y2: horizon },
      [[0, "#2a2f37"], [0.75, "#4d5662"], [1, "#6a7480"]]);
    gradient(defs, o.id + "-floor", { x1: 0, y1: horizon, x2: 0, y2: horizon + 0.9 * k },
      [[0, "#5a636e"], [0.35, "#454c56"], [1, "#24282e"]]);
    gradient(defs, o.id + "-grid", { x1: 0, y1: horizon, x2: 0, y2: horizon + 0.5 * k },
      [[0, "rgba(255,255,255,0)"], [1, "rgba(255,255,255,0.13)"]]);
    gradient(defs, o.id + "-body", { x1: -140, y1: 0, x2: 140, y2: 0 },
      [[0, "#262a31"], [0.6, "#16191d"], [1, "#101215"]]);
    var shade = svgEl("radialGradient", { id: o.id + "-shadow" });
    shade.appendChild(svgEl("stop", { offset: 0, "stop-color": "rgba(0,0,0,0.5)" }));
    shade.appendChild(svgEl("stop", { offset: 1, "stop-color": "rgba(0,0,0,0)" }));
    defs.appendChild(shade);
    var top = Math.max(0, Math.min(h, horizon));
    if (top > 0) svg.appendChild(svgEl("rect", { x: 0, y: 0, width: w, height: top, fill: "url(#" + o.id + "-wall)" }));
    if (top < h) svg.appendChild(svgEl("rect", { x: 0, y: top, width: w, height: h - top, fill: "url(#" + o.id + "-floor)" }));
    // The nearest floor in view, then tile lines across it and towards the horizon.
    var below = (h / 2) / k - shift;
    if (below > 0) {
      var near = o.eye / below;
      var lines = [];
      for (var n = Math.ceil(near / o.tile); n < 400; n++) {
        var y = sy(0, n * o.tile);
        if (lines.length && y - horizon < 1.5) break;
        lines.push("M0 " + y + "H" + w);
      }
      var reach = Math.min(200, Math.ceil((near * (w / 2)) / k / o.tile) + 1);
      for (var i = -reach; i < reach; i++) {
        var x = (i + 0.5) * o.tile;
        lines.push("M" + (w / 2 + (x / near) * k) + " " + sy(0, near) + "L" + w / 2 + " " + horizon);
      }
      svg.appendChild(svgEl("path", { d: lines.join(""), stroke: "url(#" + o.id + "-grid)", "stroke-width": 1.2, fill: "none" }));
    }
    var feet = sy(0, o.distance);
    var scale = (o.height / 1000) * (k / o.distance);
    svg.appendChild(svgEl("ellipse", {
      cx: w / 2, cy: feet, rx: 190 * scale, ry: Math.max(1, (o.eye * 0.3 * k) / o.distance / o.distance),
      fill: "url(#" + o.id + "-shadow)",
    }));
    svg.appendChild(svgEl("path", {
      d: FIGURE, fill: "url(#" + o.id + "-body)",
      transform: "translate(" + w / 2 + " " + feet + ") scale(" + scale + ") translate(0 -1000)",
    }));
  }

  // [right, row]: the four corners inside a frame clockwise from top left,
  // then just above and just below its left edge. Row 0 is the top, 1 the
  // bottom, -1 above the frame, 2 below it.
  var CORNERS = [[0, 0], [1, 0], [1, 1], [0, 1]];
  var OUTSIDE = [[0, -1], [0, 2]];

  function overlap(a, b) {
    var x = Math.max(0, Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x));
    var y = Math.max(0, Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y));
    return x * y;
  }

  // Put a frame's label in the first corner where it clears the labels already
  // drawn and stays inside the photo, trying the label without its zoom names
  // next; if nothing fits, nowhere.
  function placeLabel(svg, item, placed, w, h) {
    var label = svgEl("text", { class: item.cls });
    svg.appendChild(label);
    var corners = CORNERS.map(function (_, i) { return CORNERS[(item.start + i) % 4]; }).concat(OUTSIDE);
    var texts = item.short !== item.text ? [item.text, item.short] : [item.text];
    var order = [];
    texts.forEach(function (text) { corners.forEach(function (corner) { order.push([text, corner]); }); });
    var best = null;
    for (var i = 0; i < order.length; i++) {
      var text = order[i][0], corner = order[i][1];
      label.textContent = text;
      var right = corner[0] === 1;
      var row = corner[1];
      label.setAttribute("x", right ? item.x + item.w - 8 : item.x + 8);
      if (right) label.setAttribute("text-anchor", "end"); else label.removeAttribute("text-anchor");
      label.setAttribute("y", 0);
      var box = label.getBBox();
      var ascent = -box.y, descent = box.y + box.height;
      var baseline = row === 0 ? item.y + 6 + ascent
        : row === 1 ? item.y + item.h - 6 - descent
        : row === -1 ? item.y - 4 - descent
        : item.y + item.h + 4 + ascent;
      label.setAttribute("y", baseline);
      box = label.getBBox();
      var rect = { x: box.x - 3, y: box.y - 2, width: box.width + 6, height: box.height + 4 };
      var outside = rect.x < 0 || rect.y < 0 || rect.x + rect.width > w || rect.y + rect.height > h;
      var cost = outside ? Infinity : placed.reduce(function (sum, other) { return sum + overlap(rect, other); }, 0);
      if (!best || cost < best.cost) best = { cost: cost, text: text, x: label.getAttribute("x"), y: baseline, right: right, rect: rect };
      if (cost === 0) break;
    }
    // A label that would cover another one is left out; tapping the frame or
    // its table row still names it.
    if (best.cost > 0) { label.remove(); return; }
    label.textContent = best.text;
    label.setAttribute("x", best.x);
    label.setAttribute("y", best.y);
    if (best.right) label.setAttribute("text-anchor", "end"); else label.removeAttribute("text-anchor");
    placed.push(best.rect);
  }

  // Frames on the photo in viewBox units, smallest first, for tapping.
  var hits = [];
  var lastZoom = 1;
  var SCENE_ASPECT = 1.5;
  // A frame up to 3% bigger than the photo is drawn on its edge: the "10 mm"
  // sample is 10.2 mm, and 2% is less than the line width on a phone.
  var FIT = 1.03;

  function inUnit(metres) { return state.unit === "ft" ? metres / FOOT : metres; }
  function toMetres(value) { return state.unit === "ft" ? value * FOOT : value; }

  // Each lens in the person scene is aimed like a portrait through it: a
  // frame shorter than the person keeps the top of the head where a fitted
  // frame has it, so a tight lens shows the head and shoulders, not the
  // waist; a taller frame is centred on the body.
  function aimHeight(focal, crop) {
    var s = sensorSize(crop);
    var tall = ((state.vertical ? s[0] : s[1]) / focal) * state.distance;
    return Math.max(state.subject / 2, state.subject + ((1 - data.fill) / 2) * tall - tall / 2);
  }

  function widestOf(frames) {
    return frames.reduce(function (m, fr) { return Math.max(m, fr.f[0], fr.f[1]); }, 0);
  }

  // The sample that shows the chosen frames best when the photo is too narrow
  // for one of them: one that holds every frame with the least room to spare,
  // or else the widest. Null when no sample beats the current photo.
  function betterSample(cams, widest) {
    var own = showingOwn();
    var best = null;
    data.samples.forEach(function (sample, i) {
      if (!own && i === state.sample) return;
      var w = 0;
      cams.forEach(function (cam) {
        state.focals.forEach(function (focal) {
          var f = frameInPhoto(focal, cam.crop, sample.focal, sample.width / sample.height);
          w = Math.max(w, f[0], f[1]);
        });
      });
      if (w >= widest - 1e-9) return;
      var fits = w <= FIT;
      if (!best || (fits && (!best.fits || w > best.w)) || (!fits && !best.fits && w < best.w)) {
        best = { index: i, w: w, fits: fits };
      }
    });
    return best;
  }

  function drawFrames() {
    var old = stage.querySelector("svg.frames");
    if (old) old.remove();
    var aspect = state.scene ? SCENE_ASPECT : photoAspect();
    var w = 1000, h = 1000 / aspect;
    var svg = svgEl("svg", { class: "frames", viewBox: "0 0 " + w + " " + h, "aria-hidden": "true" });
    var labels = [];
    var cams = cameras();
    var frames = [];
    // Frames scale with the photo's focal length, so the scene starts at 1 mm
    // and is then drawn at whatever focal length puts the widest frame at 85%
    // of the stage. The scene follows the Vertical frame option; a photo was
    // taken with the camera held the way it's shaped, so the frames are too.
    var photoFocal = state.scene ? 1 : state.photoFocal;
    var vertical = state.scene ? state.vertical : aspect < 1;
    cams.forEach(function (cam) {
      state.focals.forEach(function (focal) {
        var f = frameInPhoto(focal, cam.crop, photoFocal, aspect, vertical);
        if (!state.scene) f = f.map(function (v) { return v > 1 && v <= FIT ? 1 : v; });
        frames.push({ cam: cam, focal: focal, f: f });
      });
    });
    stage.style.setProperty("--aspect", aspect);
    var allWidest = widestOf(frames);
    if (state.scene) {
      var sceneFocal = allWidest ? 0.85 / allWidest : 24;
      frames.forEach(function (fr) { fr.f = [fr.f[0] * sceneFocal, fr.f[1] * sceneFocal]; });
      allWidest = widestOf(frames);
    }
    photo.hidden = state.scene;
    scene.toggleAttribute("hidden", !state.scene);
    sceneActions.hidden = !state.scene;
    var tooWide = frames.filter(function (fr) { return fr.f[0] > 1.0001 || fr.f[1] > 1.0001; });
    // Lens view: one frame, zoomed to fill the stage, the rest of the scene dimmed.
    var lens = frames.filter(function (fr) { return key(fr.focal, fr.cam.slot) === state.selected; })[0];
    if (lens) frames = [lens];
    // Zoom the photo in so the widest frame fills most of it: the scene
    // outside every chosen lens only makes the frames small. A frame wider
    // than the photo zooms it out instead, so that frame still fits.
    var widest = widestOf(frames);
    var target = lens ? 0.94 : 0.85;
    var zoom = 1;
    if (widest > 1.0001) zoom = Math.max(0.05, target / widest);
    else if (widest) zoom = Math.max(1, state.scene ? target / widest : Math.min(lens ? 12 : 4, target / widest));
    // The scene is redrawn at the zoomed focal length rather than scaled, so a
    // long lens stays sharp. It's aimed for the outermost frame; the others
    // sit at their own aim, higher or lower.
    var perHeight = 0, sceneAim = 0;
    if (state.scene) {
      var outer = frames.reduce(function (m, fr) {
        return !m || Math.max(fr.f[0], fr.f[1]) > Math.max(m.f[0], m.f[1]) ? fr : m;
      }, null);
      sceneAim = outer ? aimHeight(outer.focal, outer.cam.crop) : state.subject / 2;
      perHeight = sceneScale(sceneFocal * zoom, aspect) / state.distance;
      drawScene(scene, {
        focal: sceneFocal * zoom, aspect: aspect, distance: state.distance, height: state.subject,
        eye: inUnit(data.eye), tile: inUnit(1), aim: sceneAim, id: "scene",
      });
    }
    scene.style.transform = "";
    photo.style.transform = !state.scene && zoom !== 1 ? "scale(" + zoom + ")" : "";
    // The photo eases to its new zoom (site.css); the frames fade in once it's there.
    if (Math.abs(zoom - lastZoom) > 0.001) svg.classList.add("settle");
    lastZoom = zoom;
    stage.classList.toggle("lens", !!lens);
    lensBack.hidden = !lens;
    var placed = [];
    // Zoomed out, the photo sits in the middle: hatch what it doesn't show.
    if (zoom < 1) {
      var px = ((1 - zoom) * w) / 2, py = ((1 - zoom) * h) / 2;
      var defs = svgEl("defs", {});
      var pattern = svgEl("pattern", {
        id: "outside-hatch", width: 14, height: 14, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)",
      });
      pattern.appendChild(svgEl("rect", { width: 14, height: 14, class: "hatch-ground" }));
      pattern.appendChild(svgEl("path", { d: "M0 0V14", class: "hatch-line" }));
      defs.appendChild(pattern);
      svg.appendChild(defs);
      svg.appendChild(svgEl("path", {
        class: "outside", "fill-rule": "evenodd", fill: "url(#outside-hatch)",
        d: "M0 0H" + w + "V" + h + "H0Z M" + px + " " + py + "h" + zoom * w + "v" + zoom * h + "h" + -zoom * w + "Z",
      }));
      svg.appendChild(svgEl("rect", { x: px, y: py, width: zoom * w, height: zoom * h, class: "edge" }));
    }
    hits = [];
    var drawn = {};
    frames.forEach(function (fr) {
      var cam = fr.cam, focal = fr.focal;
      var f = [fr.f[0] * zoom, fr.f[1] * zoom];
      drawn[cam.slot] = drawn[cam.slot] || 0;
      var x = ((1 - f[0]) * w) / 2, y = ((1 - f[1]) * h) / 2;
      if (state.scene) y -= (aimHeight(focal, cam.crop) - sceneAim) * perHeight;
      var classes = ["b" + (cam.slot + 1)];
      if (lens) {
        svg.appendChild(svgEl("path", {
          class: "dim", "fill-rule": "evenodd",
          d: "M0 0H" + w + "V" + h + "H0Z M" + x + " " + y + "h" + f[0] * w + "v" + f[1] * h + "h" + -f[0] * w + "Z",
        }));
      }
      svg.appendChild(svgEl("rect", { x: x, y: y, width: f[0] * w, height: f[1] * h, class: classes.join(" ") }));
      hits.push({ key: key(focal, cam.slot), x: x, y: y, w: f[0] * w, h: f[1] * h });
      // In lens view the caption under the photo names the frame.
      if (lens) return;
      labels.push({ x: x, y: y, w: f[0] * w, h: f[1] * h, cls: classes[0], text: focalLabel(focal), short: focal + " mm",
        // Neighbouring frames start from opposite corners: the first camera
        // top left and bottom right, the second top right and bottom left.
        start: cam.slot + (drawn[cam.slot]++ % 2) * 2 });
    });
    hits.sort(function (a, b) { return a.w * a.h - b.w * b.h; });
    stage.appendChild(svg);
    if (zoom < 1) placeOutsideLabel(svg, placed, w, h, zoom, widest);
    labels.forEach(function (item) { placeLabel(svg, item, placed, w, h); });
    drawNotes(cams, tooWide, allWidest);
    legend.hidden = cams.length < 2;
    legend.textContent = "";
    if (cams.length > 1) {
      cams.forEach(function (cam) {
        var item = document.createElement("span");
        var swatch = document.createElement("span");
        swatch.className = "swatch b" + (cam.slot + 1);
        item.appendChild(swatch);
        item.appendChild(document.createTextNode(cam.name));
        legend.appendChild(item);
      });
    }
  }

  // "Not in this photo" in the hatched band above the photo, or below it,
  // inside the widest frame; left out when neither band is tall enough (the
  // note under the photo says it too).
  function placeOutsideLabel(svg, placed, w, h, zoom, widest) {
    var photoTop = ((1 - zoom) * h) / 2;
    var frameTop = Math.max(0, ((1 - widest * zoom) * h) / 2);
    var label = svgEl("text", { class: "outside-label", x: w / 2, "text-anchor": "middle" });
    label.textContent = strings["tool.outside_photo"];
    svg.appendChild(label);
    var box = label.getBBox();
    var band = photoTop - frameTop;
    if (box.height + 8 > band || box.width + 16 > zoom * w) { label.remove(); return; }
    label.setAttribute("y", frameTop + (band - box.height) / 2 - box.y);
    box = label.getBBox();
    placed.push({ x: box.x - 3, y: box.y - 2, width: box.width + 6, height: box.height + 4 });
  }

  function drawNotes(cams, tooWide, widest) {
    sceneNote.hidden = !state.scene;
    sceneNote.textContent = fill(strings["tool.scene_note"], { height: typed(state.subject), distance: typed(state.distance) });
    var text = "", better = null;
    if (tooWide.length) {
      var names = [];
      tooWide.forEach(function (fr) {
        var name = mm(fr.focal) + (cams.length > 1 ? " (" + fr.cam.label + ")" : "");
        if (names.indexOf(name) < 0) names.push(name);
      });
      text = fill(strings["tool.too_wide"], { focal: names.join(", ") });
      better = betterSample(cams, widest);
    }
    // The notes are a live region: rewrite them only when they say something new.
    var said = text + "|" + (better ? better.index : "");
    if (notes.getAttribute("data-said") === said) return;
    notes.setAttribute("data-said", said);
    notes.textContent = text ? text + " " : "";
    if (!better) return;
    var button = document.createElement("button");
    button.type = "button";
    button.className = "link-button";
    button.setAttribute("data-sample", better.index);
    button.textContent = fill(strings["tool.use_sample"], { focal: mm(data.samples[better.index].focal) });
    notes.appendChild(button);
  }

  function drawTable() {
    // Rebuilding the table drops the focus from a row's button; it goes back after.
    var focused = results.contains(document.activeElement) ? document.activeElement.getAttribute("data-key") : null;
    var cams = cameras();
    var heads = [
      strings["tool.table_focal"],
      fill(strings["tool.table_covers"], { distance: typed(state.distance) }),
      fill(strings["tool.table_fit"], { height: typed(state.subject) }),
      strings["tool.table_equiv"], strings["tool.table_h"], strings["tool.table_v"], strings["tool.table_d"],
    ];
    var head = heads.map(function (text, i) {
      return "<th scope=\"col\"" + (i > 3 ? ' class="angle"' : "") + ">" + escapeHtml(text) + "</th>";
    }).join("");
    var body = cams.map(function (cam) {
      var group = cams.length > 1
        ? '<tbody><tr class="group"><th colspan="7" scope="colgroup"><span class="swatch b' + (cam.slot + 1) + '"></span>' +
          escapeHtml(cam.name) + "</th></tr>"
        : "<tbody>";
      return group + state.focals.map(function (focal) {
        var a = angles(focal, cam.crop);
        var k = key(focal, cam.slot);
        var zooms = zoomsEndingAt(focal);
        var fit = distanceToFit(state.subject, focal, cam.crop, state.vertical, data.fill);
        return '<tr class="clickable' + (k === state.selected ? " selected" : "") + '" data-key="' + k +
          '"><th scope="row"><button type="button" class="row-pick" data-key="' + k + '" aria-pressed="' + (k === state.selected) +
          '">' + mm(focal) + (zooms.length ? ' <span class="zoom-tag">' + escapeHtml(zooms.join(", ")) + "</span>" : "") +
          "</button></th><td>" + size(coverage(focal, cam.crop, state.distance)) + "</td><td>" + length(fit) +
          "</td><td>" + mm(focal * cam.crop) + '</td><td class="angle">' + deg(a[0]) + '</td><td class="angle">' + deg(a[1]) +
          '</td><td class="angle">' + deg(a[2]) + "</td></tr>";
      }).join("") + "</tbody>";
    }).join("");
    results.innerHTML = '<div class="scroll"><table class="angles"><thead><tr>' + head + "</tr></thead>" + body + "</table></div>";
    var again = focused && results.querySelector('button[data-key="' + focused + '"]');
    if (again) again.focus({ preventScroll: true });
  }

  function drawText() {
    var parts = (state.selected || "").split("|");
    var cams = cameras();
    var cam = cams.filter(function (c) { return String(c.slot) === parts[1]; })[0];
    var lensView = cam && stage.classList.contains("lens");
    // At the 4 and 1200 mm limits the lens doesn't fit the person as asked, so it isn't called a fit.
    var fitted = lensView && state.scene && state.fit && cam.slot === 0 && parseFloat(parts[0]) === fitFocal(state.fit) &&
      fitFocal(state.fit) === fitFocal(state.fit, true);
    var hint = fitted
      ? fill(strings["tool.fit_" + state.fit + "_result"], {
        distance: typed(state.distance), focal: mm(parseFloat(parts[0])), equiv: mm(parseFloat(parts[0]) * cam.crop),
      })
      : lensView
        ? fill(strings["tool.preview_title"], { focal: mm(parseFloat(parts[0])) + (cams.length > 1 ? " (" + cam.label + ")" : "") })
        : strings["tool.preview_hint"];
    // A live region too: screen readers hear what a lens frames, once.
    if (viewerHint.textContent !== hint) viewerHint.textContent = hint;
    // In lens view the visitor has just done what the app does live, so offer it there.
    lensCta.hidden = !lensView;
    if (lensView) lensCta.firstChild.textContent = fill(strings["tool.lens_cta"], { focal: mm(parseFloat(parts[0])) }) + " \u2192";
    distanceSummary.textContent = fill(strings["tool.distance_summary"], {
      distance: typed(state.distance), height: typed(state.subject),
    });
    if (state.bodies[1]) body2Box.hidden = false;
    addBody2.hidden = !body2Box.hidden;
    // The second camera can't be the first one again.
    Array.prototype.forEach.call(bodySelects[1].options, function (o) { o.disabled = !!o.value && o.value === state.bodies[0]; });
  }

  function writeUrl() {
    var query = "?body=" + encodeURIComponent(state.bodies[0]);
    if (state.bodies[1]) query += "&body2=" + encodeURIComponent(state.bodies[1]);
    query += "&f=" + state.focals.join(",");
    if (state.zooms.length) query += "&z=" + state.zooms.map(zoomName).join(",");
    query += "&d=" + state.distance + "&u=" + state.unit + "&h=" + state.subject + "&o=" + (state.vertical ? "v" : "h");
    // The visitor's own photo stays in the browser, so the link opens on the first sample.
    if (state.scene) query += "&s=person";
    else if (state.sample && !showingOwn()) query += "&s=" + state.sample;
    history.replaceState(null, "", location.pathname + query);
  }

  function render() {
    state.focals.sort(function (a, b) { return a - b; });
    state.zooms.sort(function (a, b) { return a[0] - b[0] || a[1] - b[1]; });
    var keys = [];
    cameras().forEach(function (cam) { state.focals.forEach(function (f) { keys.push(key(f, cam.slot)); }); });
    if (keys.indexOf(state.selected) < 0) state.selected = null;
    syncChips();
    drawFrames();
    drawTable();
    drawText();
    writeUrl();
  }

  function validFocal(v) { return v >= 4 && v <= 1200; }
  function validLength(v) { return v >= 0.01 && v <= 100000; }
  // A length converted to another unit, at the precision the page shows.
  function shown(value) { return Math.max(0.01, round(value, value < 1 ? 2 : 1)); }
  function round(value, decimals) { var p = Math.pow(10, decimals); return Math.round(value * p) / p; }

  function addZoom(zoom) {
    if (!state.zooms.some(function (z) { return zoomName(z) === zoomName(zoom); })) state.zooms.push(zoom);
    zoom.forEach(function (f) { if (state.focals.indexOf(f) < 0) state.focals.push(f); });
  }

  function hasOption(select, value) {
    return Array.prototype.some.call(select.options, function (o) { return o.value === value; });
  }

  function readUrl() {
    var params = new URLSearchParams(location.search);
    var body = params.get("body");
    if (body && hasOption(bodySelects[0], body)) state.bodies[0] = body;
    var body2 = params.get("body2");
    if (body2 && body2 !== state.bodies[0] && hasOption(bodySelects[1], body2)) state.bodies[1] = body2;
    // Whole millimetres, like the focal lengths typed in; the limits only stop absurd links.
    function focal(text) { return Math.round(parseFloat(text)); }
    var f = (params.get("f") || "").split(",").map(focal).filter(validFocal);
    if (f.length) state.focals = f.filter(function (v, i) { return f.indexOf(v) === i; }).slice(0, 60);
    (params.get("z") || "").split(",").forEach(function (text) {
      var ends = text.split("-").map(focal);
      if (ends.length === 2 && validFocal(ends[0]) && validFocal(ends[1]) && ends[0] < ends[1] && state.zooms.length < 30) {
        addZoom(ends);
      }
    });
    // A link doesn't say which focal lengths were picked on their own: take
    // the ones that don't end a zoom.
    state.picked = state.focals.filter(function (v) { return !zoomsEndingAt(v).length; });
    var unit = params.get("u");
    // Feet for visitors whose browser says US English, unless the link says otherwise.
    if (unit === "ft" || (!unit && /^en-(US|LR|MM)$/i.test(navigator.language || ""))) state.unit = "ft";
    var d = parseFloat(params.get("d"));
    state.distance = validLength(d) ? d : state.unit === "ft" ? 10 : 3;
    var h = parseFloat(params.get("h"));
    state.subject = validLength(h) ? h : state.unit === "ft" ? 6 : 1.8;
    state.metres = { distance: toMetres(state.distance), subject: toMetres(state.subject) };
    if (params.get("o") === "h") state.vertical = false;
    var s = parseInt(params.get("s"), 10);
    if (s > 0 && s < data.samples.length) state.sample = s;
    if (params.get("s") === "person") state.scene = true;
  }

  function pick(focal) {
    if (state.focals.indexOf(focal) < 0) state.focals.push(focal);
    if (state.picked.indexOf(focal) < 0) state.picked.push(focal);
  }

  function toggleFocal(focal) {
    var i = state.focals.indexOf(focal);
    if (i >= 0) {
      state.focals.splice(i, 1);
      state.picked = state.picked.filter(function (v) { return v !== focal; });
      // A zoom missing one of its ends is no longer that zoom.
      state.zooms = state.zooms.filter(function (z) { return z[0] !== focal && z[1] !== focal; });
    } else {
      pick(focal);
    }
    render();
  }

  function toggleZoom(name) {
    var existing = state.zooms.filter(function (z) { return zoomName(z) === name; })[0];
    if (existing) {
      state.zooms = state.zooms.filter(function (z) { return z !== existing; });
      // Drop the ends unless another chosen zoom still uses them or they were picked on their own.
      existing.forEach(function (f) {
        if (!zoomsEndingAt(f).length && state.picked.indexOf(f) < 0) {
          state.focals = state.focals.filter(function (v) { return v !== f; });
        }
      });
    } else {
      addZoom(name.split("-").map(parseFloat));
    }
    render();
  }

  chipsBox.addEventListener("click", function (event) {
    var chip = event.target.closest("[data-focal]");
    if (chip) toggleFocal(parseFloat(chip.getAttribute("data-focal")));
  });
  zoomsBox.addEventListener("click", function (event) {
    var chip = event.target.closest("[data-zoom]");
    if (chip) toggleZoom(chip.getAttribute("data-zoom"));
  });
  // "+" opens the row for typing another focal length or zoom.
  function reveals(buttonId, rowId, inputId) {
    var button = $(buttonId), row = $(rowId);
    button.addEventListener("click", function () {
      row.hidden = !row.hidden;
      button.setAttribute("aria-expanded", row.hidden ? "false" : "true");
      if (!row.hidden) $(inputId).focus();
    });
  }
  reveals("more-focal", "custom-row", "custom");
  reveals("more-zoom", "zoom-row", "zoom-from");

  addBody2.addEventListener("click", function () {
    body2Box.hidden = false;
    addBody2.hidden = true;
    addBody2.setAttribute("aria-expanded", "true");
    bodySelects[1].focus();
  });

  // Marks the fields that are wrong and says why beside them; typing clears it.
  function complain(box, message, inputs) {
    box.textContent = message ? fill(message, { min: num(4, 0), max: mm(1200) }) : "";
    inputs.forEach(function (input) {
      if (message) input.setAttribute("aria-invalid", "true"); else input.removeAttribute("aria-invalid");
    });
  }
  customInput.addEventListener("input", function () { complain(customError, null, [customInput]); });
  [zoomFrom, zoomTo].forEach(function (input) {
    input.addEventListener("input", function () { complain(zoomError, null, [zoomFrom, zoomTo]); });
  });

  $("add").addEventListener("click", function () {
    var focal = Math.round(parseFloat(customInput.value));
    if (!validFocal(focal)) { complain(customError, strings["tool.focal_error"], [customInput]); return; }
    pick(focal);
    customInput.value = "";
    render();
  });
  $("add-zoom").addEventListener("click", function () {
    var a = Math.round(parseFloat(zoomFrom.value)), b = Math.round(parseFloat(zoomTo.value));
    var bad = [zoomFrom, zoomTo].filter(function (input, i) { return !validFocal([a, b][i]); });
    if (bad.length || a === b) { complain(zoomError, strings["tool.zoom_error"], bad.length ? bad : [zoomFrom, zoomTo]); return; }
    addZoom([Math.min(a, b), Math.max(a, b)]);
    zoomFrom.value = zoomTo.value = "";
    render();
  });
  function enterClicks(input, button) {
    input.addEventListener("keydown", function (event) {
      if (event.key === "Enter") { event.preventDefault(); $(button).click(); }
    });
  }
  enterClicks(customInput, "add");
  enterClicks(zoomFrom, "add-zoom");
  enterClicks(zoomTo, "add-zoom");

  bodySelects.forEach(function (select, slot) {
    select.addEventListener("change", function () {
      state.bodies[slot] = select.value;
      // The first camera taking the second one's place leaves just one.
      if (slot === 0 && state.bodies[1] === select.value) state.bodies[1] = bodySelects[1].value = "";
      // Choosing "None" puts the second camera away again, and the focus on
      // the button that brings it back.
      var away = slot === 1 && !select.value;
      if (away) { body2Box.hidden = true; addBody2.setAttribute("aria-expanded", "false"); }
      render();
      if (away) addBody2.focus();
    });
  });

  [[distanceInput, "distance"], [subjectInput, "subject"]].forEach(function (pair) {
    var input = pair[0], name = pair[1];
    input.addEventListener("input", function () {
      var value = parseFloat(input.value);
      if (validLength(value)) { state[name] = value; state.metres[name] = toMetres(value); render(); }
    });
    // Left empty or out of range, the field shows the value in use again.
    input.addEventListener("change", function () {
      if (!validLength(parseFloat(input.value))) input.value = state[name];
    });
  });

  function syncDistanceInputs() {
    distanceInput.value = state.distance;
    subjectInput.value = state.subject;
    form.querySelector('input[name="unit"][value="' + state.unit + '"]').checked = true;
    form.querySelector('input[name="orient"][value="' + (state.vertical ? "v" : "h") + '"]').checked = true;
    Array.prototype.forEach.call(form.querySelectorAll(".unit"), function (el) { el.textContent = state.unit; });
  }

  // A click anywhere on a row opens its lens view; the row's button does it from the keyboard.
  results.addEventListener("click", function (event) {
    var row = event.target.closest("tr[data-key]");
    if (!row) return;
    var k = row.getAttribute("data-key");
    state.selected = state.selected === k ? null : k;
    render();
    revealStage();
  });

  function revealStage() {
    var box = stage.getBoundingClientRect();
    if (box.top < 0 || box.bottom > window.innerHeight) {
      var smooth = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      stage.scrollIntoView({ block: "start", behavior: smooth ? "smooth" : "auto" });
    }
  }

  // The focal length on the first camera that fits the whole person, or the
  // head and shoulders, in 90% of the frame height at the subject distance.
  // unclamped: past the 4 to 1200 mm the tool takes.
  function fitFocal(kind, unclamped) {
    var crop = cameras()[0].crop;
    var subject = kind === "head" ? state.subject * data.head : state.subject;
    var focal = Math.round(focalToFit(subject, state.distance, crop, state.vertical, data.fill));
    return unclamped ? focal : Math.min(1200, Math.max(4, focal));
  }

  sceneActions.addEventListener("click", function (event) {
    var button = event.target.closest("[data-fit]");
    if (!button) return;
    var kind = button.getAttribute("data-fit");
    var focal = fitFocal(kind);
    // A new fit replaces the chip the last one of its kind added.
    var previous = state.fitAdded[kind];
    if (previous && previous !== focal && state.focals.indexOf(previous) >= 0 &&
        previous !== state.fitAdded[kind === "head" ? "body" : "head"]) toggleFocal(previous);
    state.fitAdded[kind] = state.focals.indexOf(focal) < 0 ? focal : null;
    pick(focal);
    state.fit = kind;
    state.selected = key(focal, 0);
    render();
    revealStage();
  });

  notes.addEventListener("click", function (event) {
    var button = event.target.closest("[data-sample]");
    if (!button) return;
    var value = "sample-" + button.getAttribute("data-sample");
    var tile = form.querySelector('input[name="photo"][value="' + value + '"]');
    tile.checked = true;
    choosePhoto(value);
    // The button is gone once the photo fits; the focus goes to that photo's tile.
    tile.focus({ preventScroll: true });
  });

  // Tapping the photo picks the smallest frame around that spot; in lens view
  // it goes back to all frames.
  stage.addEventListener("click", function (event) {
    if (event.target.closest("button")) return;
    if (stage.classList.contains("lens")) { state.selected = null; render(); return; }
    var svg = stage.querySelector("svg.frames");
    if (!svg) return;
    var box = svg.getBoundingClientRect();
    var view = svg.viewBox.baseVal;
    var px = ((event.clientX - box.left) / box.width) * view.width;
    var py = ((event.clientY - box.top) / box.height) * view.height;
    var hit = hits.filter(function (r) { return px >= r.x && px <= r.x + r.w && py >= r.y && py <= r.y + r.h; })[0];
    if (hit) { state.selected = hit.key; render(); }
  });
  lensBack.addEventListener("click", function () {
    var k = state.selected, focused = document.activeElement === lensBack;
    state.selected = null;
    render();
    // The button hides with the lens view; the focus goes back to the Fit
    // button that opened it, or else to that lens's row.
    var fit = state.fit && k === key(fitFocal(state.fit), 0) && sceneActions.querySelector('[data-fit="' + state.fit + '"]');
    var row = fit || results.querySelector('button[data-key="' + k + '"]');
    if (focused && row) row.focus({ preventScroll: true });
  });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && state.selected !== null) { state.selected = null; render(); }
  });

  function syncAngles() { resultsBox.classList.toggle("with-angles", showAngles.checked); }
  showAngles.addEventListener("change", syncAngles);

  function showSample(index) {
    var sample = data.samples[index], root = photo.getAttribute("data-root");
    state.sample = index;
    state.photoFocal = sample.focal;
    // Phones get the 1200 px copy where there is one.
    if (sample.small) {
      photo.srcset = root + sample.small + " " + sample.small_width + "w, " + root + sample.src + " " + sample.width + "w";
    } else {
      photo.removeAttribute("srcset");
    }
    photo.src = root + sample.src;
    photo.width = sample.width;
    photo.height = sample.height;
  }

  function showOwn(url) {
    var focal = parseFloat(photoFocalInput.value);
    state.photoFocal = validFocal(focal) ? focal : 26;
    photo.removeAttribute("srcset");
    photo.src = url;
  }

  // The visitor's own photo is on screen, not just its tile chosen.
  function showingOwn() { return !state.scene && !!state.ownUrl && photo.src === state.ownUrl; }

  // The tile chosen before "Use my own photo", to go back to when the file
  // picker closes without a photo or the browser can't open the one picked.
  var lastChoice = "sample-0";
  // A picked photo until it opens: its URL and the focal length in its EXIF.
  var pending = null;

  function choosePhoto(value) {
    photoError.textContent = "";
    ownBox.hidden = value !== "own";
    // Without a photo of their own yet, the current picture stays until one is picked.
    if (value === "own" && !state.ownUrl) { fileInput.click(); return; }
    if (value !== "own") lastChoice = value;
    state.scene = value === "person";
    if (value === "own") showOwn(state.ownUrl);
    else if (!state.scene) showSample(parseInt(value.split("-")[1], 10));
    render();
  }

  function chooseLast() {
    var tile = form.querySelector('input[name="photo"][value="' + lastChoice + '"]');
    var focused = document.activeElement === form.querySelector('input[name="photo"][value="own"]');
    tile.checked = true;
    choosePhoto(lastChoice);
    if (focused) tile.focus();
  }

  form.addEventListener("change", function (event) {
    var name = event.target.name;
    if (name === "unit") {
      if (event.target.value === state.unit) return;
      // From the metres, so m, ft, m gives back the same numbers.
      state.unit = event.target.value;
      state.distance = shown(inUnit(state.metres.distance));
      state.subject = shown(inUnit(state.metres.subject));
      syncDistanceInputs();
      render();
    } else if (name === "orient") {
      state.vertical = event.target.value === "v";
      render();
    } else if (name === "photo") {
      choosePhoto(event.target.value);
    }
  });

  fileInput.addEventListener("change", function () {
    var file = fileInput.files && fileInput.files[0];
    if (!file) { if (!state.ownUrl) chooseLast(); return; }
    var url = URL.createObjectURL(file);
    file.slice(0, 256 * 1024).arrayBuffer().then(function (buffer) {
      var focal = null;
      try { focal = exifEquivalentFocal(buffer); } catch (err) { focal = null; }
      pending = { url: url, focal: focal };
      photo.removeAttribute("srcset");
      photo.src = url;
    });
  });
  fileInput.addEventListener("cancel", function () { if (!state.ownUrl) chooseLast(); });

  photo.addEventListener("load", function () {
    if (pending && photo.src === pending.url) {
      // The picked photo opened and replaces any before it. Without a focal
      // length in its details, it starts again from the iPhone main camera.
      if (state.ownUrl) URL.revokeObjectURL(state.ownUrl);
      state.ownUrl = pending.url;
      state.scene = false;
      state.photoFocal = pending.focal || 26;
      photoFocalInput.value = state.photoFocal;
      focalNote.className = "field-note";
      complain(focalNote, pending.focal ? null : fill(strings["tool.photo_focal_missing"], { focal: mm(26) }), []);
      photoFocalInput.removeAttribute("aria-invalid");
      pending = null;
    }
    render();
  });
  // A photo this browser can't open (HEIC outside Safari): back to the one
  // before, with a note saying which formats work.
  photo.addEventListener("error", function () {
    if (!pending || photo.src !== pending.url) return;
    URL.revokeObjectURL(pending.url);
    pending = null;
    fileInput.value = "";
    if (state.ownUrl) showOwn(state.ownUrl); else chooseLast();
    photoError.textContent = strings["tool.photo_error"];
  });

  photoFocalInput.addEventListener("input", function () {
    var value = parseFloat(photoFocalInput.value);
    focalNote.className = "field-note";
    complain(focalNote, null, [photoFocalInput]);
    if (validFocal(value) && showingOwn()) {
      state.photoFocal = value;
      render();
    }
  });
  photoFocalInput.addEventListener("change", function () {
    if (validFocal(parseFloat(photoFocalInput.value))) return;
    focalNote.className = "field-error";
    complain(focalNote, strings["tool.focal_error"], [photoFocalInput]);
  });

  // Labels change size at these widths (site.css), so place them again when one is crossed.
  ["(max-width: 600px)", "(max-width: 1100px)"].forEach(function (query) {
    var list = window.matchMedia(query);
    if (list.addEventListener) list.addEventListener("change", drawFrames);
  });

  var shareTimer;
  function say(text, seconds) {
    shareStatus.textContent = text;
    clearTimeout(shareTimer);
    shareTimer = setTimeout(function () { shareStatus.textContent = ""; }, seconds * 1000);
  }
  $("share").addEventListener("click", function () {
    // The visitor's own photo never leaves the browser, so the link opens on a sample; say so.
    var own = showingOwn() ? strings["tool.share_own"] : "";
    // Phones get the system share sheet; elsewhere the link goes to the clipboard.
    if (navigator.share && window.matchMedia("(pointer: coarse)").matches) {
      navigator.share({ title: document.title, url: location.href }).then(function () { if (own) say(own, 10); }, function () {});
    } else if (navigator.clipboard) {
      navigator.clipboard.writeText(location.href).then(function () {
        say(own ? strings["tool.copied"] + " · " + own : strings["tool.copied"], own ? 10 : 4);
      }, function () {});
    }
  });

  readUrl();
  bodySelects[0].value = state.bodies[0];
  bodySelects[1].value = state.bodies[1];
  syncDistanceInputs();
  if (state.scene) {
    form.querySelector('input[name="photo"][value="person"]').checked = true;
  } else if (state.sample) {
    form.querySelector('input[name="photo"][value="sample-' + state.sample + '"]').checked = true;
    showSample(state.sample);
  }
  lastChoice = state.scene ? "person" : "sample-" + state.sample;
  // The person tile and the icons on the Fit buttons are drawn like the scene.
  drawScene($("person-thumb"), { focal: 36, aspect: SCENE_ASPECT, distance: 3, height: 1.8, eye: data.eye, tile: 1, aim: 0.9, id: "thumb" });
  Array.prototype.forEach.call(form.querySelectorAll("svg.figure"), function (icon) {
    icon.appendChild(svgEl("path", { d: FIGURE }));
  });
  showAngles.checked = window.matchMedia("(min-width: 760px)").matches;
  syncAngles();
  form.hidden = false;
  var staticFigure = $("static-figure");
  if (staticFigure) staticFigure.hidden = true;
  render();
  // On phones the chips scroll sideways: bring the first chosen one into view.
  [chipsBox, zoomsBox].forEach(function (box) {
    var chip = box.querySelector('[aria-pressed="true"]');
    if (!chip || box.scrollWidth <= box.clientWidth) return;
    var b = box.getBoundingClientRect(), c = chip.getBoundingClientRect();
    if (c.left < b.left + 16 || c.right > b.right - 28) box.scrollLeft += data.rtl ? c.right - b.right + 28 : c.left - b.left - 16;
  });
})();
