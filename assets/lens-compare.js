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

  function frameInPhoto(focal, crop, photoEquivalent, photoAspect) {
    var s = sensorSize(crop);
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

  var LensMath = {
    exifEquivalentFocal: exifEquivalentFocal, sensorAspect: sensorAspect, sensorSize: sensorSize,
    angles: angles, frameInPhoto: frameInPhoto, coverage: coverage, distanceToFit: distanceToFit,
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

  var state = {
    bodies: ["generic-1", ""],
    focals: [24, 35, 50, 85],
    zooms: [],
    distance: 3,
    unit: "m",
    subject: 1.8,
    vertical: true,
    sample: 0,
    photoFocal: data.samples[0].focal,
    selected: null,
    ownUrl: null,
  };

  function num(value, decimals) {
    var text = value.toFixed(decimals);
    return data.comma ? text.replace(".", ",") : text;
  }
  // Keeps "24 mm" from turning into "mm 24" on right-to-left pages.
  function isolate(text) { return data.rtl ? "⁦" + text + "⁩" : text; }
  function mm(value) { return isolate(Math.round(value) + " mm"); }
  function deg(value) { return isolate(num(value, 1) + "°"); }
  // Lengths: one decimal, two below 1, none from 100 up.
  function len(value) { return num(value, value < 1 ? 2 : value < 100 ? 1 : 0); }
  // Lengths keep a no-break space before the unit so "3.1 m" never wraps.
  function length(value) { return isolate(len(value) + "\u00a0" + state.unit); }
  // A value the visitor typed, as typed: "3 m", "1.8 m".
  function typed(value) {
    var text = String(round(value, 2));
    return isolate((data.comma ? text.replace(".", ",") : text) + "\u00a0" + state.unit);
  }
  function size(pair) { return isolate(len(pair[0]) + "\u00a0\u00d7 " + len(pair[1]) + "\u00a0" + state.unit); }
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
      return { slot: slot, crop: parseFloat(option.getAttribute("data-crop")), name: option.textContent };
    }).filter(Boolean);
  }

  function photoAspect() {
    return photo.naturalWidth && photo.naturalHeight ? photo.naturalWidth / photo.naturalHeight : 1.5;
  }

  function zoomName(zoom) { return zoom[0] + "-" + zoom[1]; }
  // "(24-70)" after a focal length that ends one of the chosen zooms.
  function zoomsEndingAt(focal) {
    return state.zooms.filter(function (z) { return z[0] === focal || z[1] === focal; }).map(zoomName);
  }
  function focalLabel(focal) {
    var zooms = zoomsEndingAt(focal);
    return focal + " mm" + (zooms.length ? " (" + zooms.join(", ") + ")" : "");
  }

  function insertSorted(box, chip, value, attr) {
    var later = Array.prototype.find.call(box.children, function (c) {
      return parseFloat(c.getAttribute(attr)) > value;
    });
    box.insertBefore(chip, later || box.querySelector(".more"));
  }

  function makeChip(attr, value, text) {
    var chip = document.createElement("button");
    chip.type = "button";
    chip.className = "chip";
    chip.setAttribute(attr, value);
    chip.textContent = text;
    return chip;
  }

  function ensureChip(focal) {
    if (chipsBox.querySelector('[data-focal="' + focal + '"]')) return;
    insertSorted(chipsBox, makeChip("data-focal", String(focal), String(focal)), focal, "data-focal");
  }

  function ensureZoomChip(zoom) {
    if (zoomsBox.querySelector('[data-zoom="' + zoomName(zoom) + '"]')) return;
    insertSorted(zoomsBox, makeChip("data-zoom", zoomName(zoom), zoomName(zoom)), zoom[0], "data-zoom");
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
  // next; if nothing fits, where it overlaps least.
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
    label.textContent = best.text;
    label.setAttribute("x", best.x);
    label.setAttribute("y", best.y);
    if (best.right) label.setAttribute("text-anchor", "end"); else label.removeAttribute("text-anchor");
    placed.push(best.rect);
  }

  // Frames on the photo in viewBox units, smallest first, for tapping.
  var hits = [];
  var lastZoom = 1;

  function drawFrames() {
    var old = stage.querySelector("svg.frames");
    if (old) old.remove();
    var aspect = photoAspect();
    var w = 1000, h = 1000 / aspect;
    var svg = svgEl("svg", { class: "frames", viewBox: "0 0 " + w + " " + h, "aria-hidden": "true" });
    var tooWide = [];
    var labels = [];
    var cams = cameras();
    var frames = [];
    cams.forEach(function (cam) {
      state.focals.forEach(function (focal) {
        var f = frameInPhoto(focal, cam.crop, state.photoFocal, aspect);
        if (f[0] > 1.0001 || f[1] > 1.0001) {
          tooWide.push(mm(focal) + (cams.length > 1 ? " (" + cam.name + ")" : ""));
          return;
        }
        frames.push({ cam: cam, focal: focal, f: f });
      });
    });
    // Lens view: one frame, zoomed to fill the photo, the rest of the scene dimmed.
    var lens = frames.filter(function (fr) { return key(fr.focal, fr.cam.slot) === state.selected; })[0];
    if (lens) frames = [lens];
    // Otherwise zoom the photo in so the widest frame fills most of it: the
    // scene outside every chosen lens only makes the frames small.
    var widest = frames.reduce(function (m, fr) { return Math.max(m, fr.f[0], fr.f[1]); }, 0);
    var zoom = widest ? Math.max(1, Math.min(lens ? 12 : 4, (lens ? 0.94 : 0.85) / widest)) : 1;
    photo.style.transform = zoom > 1 ? "scale(" + zoom + ")" : "";
    // The photo eases to its new zoom (site.css); the frames fade in once it's there.
    if (Math.abs(zoom - lastZoom) > 0.001) svg.classList.add("settle");
    lastZoom = zoom;
    stage.classList.toggle("lens", !!lens);
    lensBack.hidden = !lens;
    hits = [];
    var drawn = {};
    frames.forEach(function (fr) {
      var cam = fr.cam, focal = fr.focal;
      var f = [fr.f[0] * zoom, fr.f[1] * zoom];
      drawn[cam.slot] = drawn[cam.slot] || 0;
      var x = ((1 - f[0]) * w) / 2, y = ((1 - f[1]) * h) / 2;
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
    var placed = [];
    labels.forEach(function (item) { placeLabel(svg, item, placed, w, h); });
    notes.textContent = tooWide.map(function (f) { return fill(strings["tool.too_wide"], { focal: f }); }).join(". ");
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

  function drawTable() {
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
          '" tabindex="0"><th scope="row">' + mm(focal) +
          (zooms.length ? ' <span class="zoom-tag">' + escapeHtml(zooms.join(", ")) + "</span>" : "") +
          "</th><td>" + size(coverage(focal, cam.crop, state.distance)) + "</td><td>" + length(fit) +
          "</td><td>" + mm(focal * cam.crop) + '</td><td class="angle">' + deg(a[0]) + '</td><td class="angle">' + deg(a[1]) +
          '</td><td class="angle">' + deg(a[2]) + "</td></tr>";
      }).join("") + "</tbody>";
    }).join("");
    results.innerHTML = '<div class="scroll"><table class="angles"><thead><tr>' + head + "</tr></thead>" + body + "</table></div>";
  }

  function drawText() {
    var parts = (state.selected || "").split("|");
    var cams = cameras();
    var cam = cams.filter(function (c) { return String(c.slot) === parts[1]; })[0];
    var lens = cam && stage.classList.contains("lens");
    viewerHint.textContent = lens
      ? fill(strings["tool.preview_title"], { focal: mm(parseFloat(parts[0])) + (cams.length > 1 ? " (" + cam.name + ")" : "") })
      : strings["tool.preview_hint"];
    // In lens view the visitor has just done what the app does live, so offer it there.
    lensCta.hidden = !lens;
    if (lens) lensCta.firstChild.textContent = fill(strings["tool.lens_cta"], { focal: mm(parseFloat(parts[0])) }) + " \u2192";
    distanceSummary.textContent = fill(strings["tool.distance_summary"], {
      distance: typed(state.distance), height: typed(state.subject),
    });
    if (state.bodies[1]) body2Box.hidden = false;
    addBody2.hidden = !body2Box.hidden;
  }

  function writeUrl() {
    var query = "?body=" + encodeURIComponent(state.bodies[0]);
    if (state.bodies[1]) query += "&body2=" + encodeURIComponent(state.bodies[1]);
    query += "&f=" + state.focals.join(",");
    if (state.zooms.length) query += "&z=" + state.zooms.map(zoomName).join(",");
    query += "&d=" + state.distance + "&u=" + state.unit + "&h=" + state.subject + "&o=" + (state.vertical ? "v" : "h");
    if (state.sample) query += "&s=" + state.sample;
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
  function validLength(v) { return v > 0 && v <= 100000; }
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
    if (body2 && hasOption(bodySelects[1], body2)) state.bodies[1] = body2;
    var f = (params.get("f") || "").split(",").map(parseFloat).filter(validFocal);
    if (f.length) state.focals = f.filter(function (v, i) { return f.indexOf(v) === i; }).slice(0, 16);
    (params.get("z") || "").split(",").forEach(function (text) {
      var ends = text.split("-").map(parseFloat);
      if (ends.length === 2 && validFocal(ends[0]) && validFocal(ends[1]) && ends[0] < ends[1] && state.zooms.length < 6) {
        addZoom(ends);
      }
    });
    var unit = params.get("u");
    // Feet for visitors whose browser says US English, unless the link says otherwise.
    if (unit === "ft" || (!unit && /^en-(US|LR|MM)$/i.test(navigator.language || ""))) state.unit = "ft";
    var d = parseFloat(params.get("d"));
    state.distance = validLength(d) ? d : state.unit === "ft" ? 10 : 3;
    var h = parseFloat(params.get("h"));
    state.subject = validLength(h) ? h : state.unit === "ft" ? 6 : 1.8;
    if (params.get("o") === "h") state.vertical = false;
    var s = parseInt(params.get("s"), 10);
    if (s > 0 && s < data.samples.length) state.sample = s;
  }

  function toggleFocal(focal) {
    var i = state.focals.indexOf(focal);
    if (i >= 0) {
      state.focals.splice(i, 1);
      // A zoom missing one of its ends is no longer that zoom.
      state.zooms = state.zooms.filter(function (z) { return z[0] !== focal && z[1] !== focal; });
    } else {
      state.focals.push(focal);
    }
    render();
  }

  function toggleZoom(name) {
    var existing = state.zooms.filter(function (z) { return zoomName(z) === name; })[0];
    if (existing) {
      state.zooms = state.zooms.filter(function (z) { return z !== existing; });
      // Drop the ends unless another chosen zoom still uses them.
      existing.forEach(function (f) {
        if (!zoomsEndingAt(f).length) state.focals = state.focals.filter(function (v) { return v !== f; });
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

  $("add").addEventListener("click", function () {
    var focal = Math.round(parseFloat(customInput.value));
    if (!validFocal(focal)) return;
    if (state.focals.indexOf(focal) < 0) state.focals.push(focal);
    customInput.value = "";
    render();
  });
  $("add-zoom").addEventListener("click", function () {
    var a = Math.round(parseFloat(zoomFrom.value)), b = Math.round(parseFloat(zoomTo.value));
    if (!validFocal(a) || !validFocal(b) || a === b) return;
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
      // Choosing "None" puts the second camera away again.
      if (slot === 1 && !select.value) { body2Box.hidden = true; addBody2.setAttribute("aria-expanded", "false"); }
      render();
    });
  });

  distanceInput.addEventListener("input", function () {
    var value = parseFloat(distanceInput.value);
    if (validLength(value)) { state.distance = value; render(); }
  });
  subjectInput.addEventListener("input", function () {
    var value = parseFloat(subjectInput.value);
    if (validLength(value)) { state.subject = value; render(); }
  });

  function syncDistanceInputs() {
    distanceInput.value = state.distance;
    subjectInput.value = state.subject;
    form.querySelector('input[name="unit"][value="' + state.unit + '"]').checked = true;
    form.querySelector('input[name="orient"][value="' + (state.vertical ? "v" : "h") + '"]').checked = true;
    Array.prototype.forEach.call(form.querySelectorAll(".unit"), function (el) { el.textContent = state.unit; });
  }

  results.addEventListener("click", function (event) {
    var row = event.target.closest("tr[data-key]");
    if (!row) return;
    var k = row.getAttribute("data-key");
    state.selected = state.selected === k ? null : k;
    render();
    var box = stage.getBoundingClientRect();
    if (box.top < 0 || box.bottom > window.innerHeight) {
      var smooth = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      stage.scrollIntoView({ block: "start", behavior: smooth ? "smooth" : "auto" });
    }
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
  lensBack.addEventListener("click", function () { state.selected = null; render(); });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && state.selected !== null) { state.selected = null; render(); }
  });

  function syncAngles() { resultsBox.classList.toggle("with-angles", showAngles.checked); }
  showAngles.addEventListener("change", syncAngles);
  results.addEventListener("keydown", function (event) {
    if ((event.key === "Enter" || event.key === " ") && event.target.matches("tr[data-key]")) {
      event.preventDefault();
      event.target.click();
    }
  });

  function showSample(index) {
    state.sample = index;
    state.photoFocal = data.samples[index].focal;
    photo.src = photo.getAttribute("data-root") + data.samples[index].src;
    photo.width = data.samples[index].width;
    photo.height = data.samples[index].height;
  }

  form.addEventListener("change", function (event) {
    var name = event.target.name;
    if (name === "unit") {
      var unit = event.target.value;
      if (unit === state.unit) return;
      var factor = unit === "ft" ? 1 / FOOT : FOOT;
      state.distance = round(state.distance * factor, 1);
      state.subject = round(state.subject * factor, state.subject * factor < 1 ? 2 : 1);
      state.unit = unit;
      syncDistanceInputs();
      render();
    } else if (name === "orient") {
      state.vertical = event.target.value === "v";
      render();
    } else if (name === "photo") {
      var own = event.target.value === "own";
      ownBox.hidden = !own;
      if (!own) {
        showSample(parseInt(event.target.value.split("-")[1], 10));
        render();
      } else if (state.ownUrl) {
        photo.src = state.ownUrl;
        state.photoFocal = parseFloat(photoFocalInput.value) || 26;
      } else {
        fileInput.click();
      }
    }
  });

  fileInput.addEventListener("change", function () {
    var file = fileInput.files && fileInput.files[0];
    if (!file) return;
    if (state.ownUrl) URL.revokeObjectURL(state.ownUrl);
    state.ownUrl = URL.createObjectURL(file);
    file.slice(0, 256 * 1024).arrayBuffer().then(function (buffer) {
      var focal = null;
      try { focal = exifEquivalentFocal(buffer); } catch (err) { focal = null; }
      if (focal) photoFocalInput.value = focal;
      state.photoFocal = parseFloat(photoFocalInput.value) || 26;
      photo.src = state.ownUrl;
    });
  });

  photoFocalInput.addEventListener("input", function () {
    var value = parseFloat(photoFocalInput.value);
    if (validFocal(value) && form.querySelector('input[name="photo"]:checked').value === "own") {
      state.photoFocal = value;
      render();
    }
  });

  photo.addEventListener("load", render);
  // Labels grow on narrow screens (site.css), so place them again when that flips.
  var narrow = window.matchMedia("(max-width: 600px)");
  if (narrow.addEventListener) narrow.addEventListener("change", drawFrames);

  $("share").addEventListener("click", function () {
    var done = function () { shareStatus.textContent = strings["tool.copied"]; };
    // Phones get the system share sheet; elsewhere the link goes to the clipboard.
    if (navigator.share && window.matchMedia("(pointer: coarse)").matches) {
      navigator.share({ title: document.title, url: location.href }).catch(function () {});
    } else if (navigator.clipboard) {
      navigator.clipboard.writeText(location.href).then(done, function () {});
    }
  });

  readUrl();
  bodySelects[0].value = state.bodies[0];
  bodySelects[1].value = state.bodies[1];
  syncDistanceInputs();
  if (state.sample) {
    form.querySelector('input[name="photo"][value="sample-' + state.sample + '"]').checked = true;
    showSample(state.sample);
  }
  showAngles.checked = window.matchMedia("(min-width: 760px)").matches;
  syncAngles();
  form.hidden = false;
  var staticFigure = $("static-figure");
  if (staticFigure) staticFigure.hidden = true;
  render();
})();
