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
  var preview = $("preview");
  var canvas = $("preview-canvas");
  var previewCaption = $("preview-caption");
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
    box.insertBefore(chip, later || null);
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
    Array.prototype.forEach.call(chipsBox.children, function (chip) {
      var focal = parseFloat(chip.getAttribute("data-focal"));
      chip.setAttribute("aria-pressed", state.focals.indexOf(focal) >= 0 ? "true" : "false");
    });
    var names = state.zooms.map(zoomName);
    Array.prototype.forEach.call(zoomsBox.children, function (chip) {
      chip.setAttribute("aria-pressed", names.indexOf(chip.getAttribute("data-zoom")) >= 0 ? "true" : "false");
    });
  }

  function svgEl(name, attrs) {
    var el = document.createElementNS("http://www.w3.org/2000/svg", name);
    Object.keys(attrs).forEach(function (k) { el.setAttribute(k, attrs[k]); });
    return el;
  }

  function key(focal, slot) { return focal + "|" + slot; }

  function drawFrames() {
    var old = stage.querySelector("svg.frames");
    if (old) old.remove();
    var aspect = photoAspect();
    var w = 1000, h = 1000 / aspect;
    var svg = svgEl("svg", { class: "frames", viewBox: "0 0 " + w + " " + h, "aria-hidden": "true" });
    var tooWide = [];
    var cams = cameras();
    cams.forEach(function (cam) {
      var drawn = 0;
      state.focals.forEach(function (focal) {
        var f = frameInPhoto(focal, cam.crop, state.photoFocal, aspect);
        if (f[0] > 1.0001 || f[1] > 1.0001) {
          tooWide.push(mm(focal) + (cams.length > 1 ? " (" + cam.name + ")" : ""));
          return;
        }
        var x = ((1 - f[0]) * w) / 2, y = ((1 - f[1]) * h) / 2;
        var classes = ["b" + (cam.slot + 1)];
        if (key(focal, cam.slot) === state.selected) classes.push("active");
        svg.appendChild(svgEl("rect", { x: x, y: y, width: f[0] * w, height: f[1] * h, class: classes.join(" ") }));
        // Alternate corners so labels of neighbouring frames don't overlap:
        // the first camera uses top left and bottom right, the second the other two.
        var even = drawn++ % 2 === 0;
        var left = cam.slot === 0 ? even : !even;
        var top = even;
        var attrs = {
          x: left ? x + 8 : x + f[0] * w - 8,
          y: top ? y + 26 : y + f[1] * h - 10,
          class: classes[0],
        };
        if (!left) attrs["text-anchor"] = "end";
        var label = svgEl("text", attrs);
        label.textContent = focalLabel(focal);
        svg.appendChild(label);
      });
    });
    stage.appendChild(svg);
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
      fill(strings[state.vertical ? "tool.table_fit_v" : "tool.table_fit_h"], { height: typed(state.subject) }),
      strings["tool.table_equiv"], strings["tool.table_h"], strings["tool.table_v"], strings["tool.table_d"],
    ];
    var head = heads.map(function (text) { return '<th scope="col">' + escapeHtml(text) + "</th>"; }).join("");
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
          "</td><td>" + mm(focal * cam.crop) + "</td><td>" + deg(a[0]) + "</td><td>" + deg(a[1]) + "</td><td>" + deg(a[2]) +
          "</td></tr>";
      }).join("") + "</tbody>";
    }).join("");
    results.innerHTML = '<div class="scroll"><table class="angles"><thead><tr>' + head + "</tr></thead>" + body + "</table></div>";
  }

  function drawPreview() {
    if (state.selected === null || !photo.complete || !photo.naturalWidth) { preview.hidden = true; return; }
    var parts = state.selected.split("|");
    var focal = parseFloat(parts[0]);
    var cam = cameras().filter(function (c) { return String(c.slot) === parts[1]; })[0];
    if (!cam) { preview.hidden = true; return; }
    var f = frameInPhoto(focal, cam.crop, state.photoFocal, photoAspect());
    if (f[0] > 1.0001 || f[1] > 1.0001) { preview.hidden = true; return; }
    var sw = f[0] * photo.naturalWidth, sh = f[1] * photo.naturalHeight;
    var sx = (photo.naturalWidth - sw) / 2, sy = (photo.naturalHeight - sh) / 2;
    var width = Math.min(1200, Math.max(600, Math.round(sw)));
    canvas.width = width;
    canvas.height = Math.round((width * sh) / sw);
    var ctx = canvas.getContext("2d");
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(photo, sx, sy, sw, sh, 0, 0, canvas.width, canvas.height);
    var what = mm(focal) + (cameras().length > 1 ? " (" + cam.name + ")" : "");
    previewCaption.textContent = fill(strings["tool.preview_title"], { focal: what });
    preview.hidden = false;
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
    drawPreview();
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
    if (params.get("u") === "ft") state.unit = "ft";
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
    var chip = event.target.closest(".chip");
    if (chip) toggleFocal(parseFloat(chip.getAttribute("data-focal")));
  });
  zoomsBox.addEventListener("click", function (event) {
    var chip = event.target.closest(".chip");
    if (chip) toggleZoom(chip.getAttribute("data-zoom"));
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
    select.addEventListener("change", function () { state.bodies[slot] = select.value; render(); });
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
    if (state.selected !== null && !preview.hidden) preview.scrollIntoView({ block: "nearest", behavior: "smooth" });
  });
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

  $("share").addEventListener("click", function () {
    var done = function () { shareStatus.textContent = strings["tool.copied"]; };
    if (navigator.clipboard) navigator.clipboard.writeText(location.href).then(done, function () {});
  });

  readUrl();
  bodySelects[0].value = state.bodies[0];
  bodySelects[1].value = state.bodies[1];
  syncDistanceInputs();
  if (state.sample) {
    form.querySelector('input[name="photo"][value="sample-' + state.sample + '"]').checked = true;
    showSample(state.sample);
  }
  form.hidden = false;
  var staticFigure = $("static-figure");
  if (staticFigure) staticFigure.hidden = true;
  render();
})();
