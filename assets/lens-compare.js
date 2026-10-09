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

  var LensMath = { exifEquivalentFocal: exifEquivalentFocal, sensorAspect: sensorAspect, sensorSize: sensorSize, angles: angles, frameInPhoto: frameInPhoto };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = LensMath;
    return;
  }

  var dataNode = document.getElementById("tool-data");
  var form = document.getElementById("tool");
  if (!dataNode || !form) return;
  var data = JSON.parse(dataNode.textContent);
  var strings = data.strings;

  var bodySelect = document.getElementById("body");
  var chipsBox = form.querySelector(".chips");
  var customInput = document.getElementById("custom");
  var stage = document.getElementById("stage");
  var photo = document.getElementById("photo");
  var notes = document.getElementById("notes");
  var results = document.getElementById("results");
  var preview = document.getElementById("preview");
  var canvas = document.getElementById("preview-canvas");
  var previewCaption = document.getElementById("preview-caption");
  var ownBox = document.getElementById("own");
  var fileInput = document.getElementById("file");
  var photoFocalInput = document.getElementById("photo-focal");
  var shareButton = document.getElementById("share");
  var shareStatus = document.getElementById("share-status");

  var state = {
    body: "generic-1",
    focals: [24, 35, 50, 85],
    photoFocal: data.sample.focal,
    selected: null,
    ownUrl: null,
  };

  function num(value, decimals) {
    var text = value.toFixed(decimals);
    return data.comma ? text.replace(".", ",") : text;
  }
  // Keeps "24 mm" from turning into "mm 24" on right-to-left pages.
  function isolate(text) { return data.rtl ? "\u2066" + text + "\u2069" : text; }
  function mm(value) { return isolate(Math.round(value) + " mm"); }
  function deg(value) { return isolate(num(value, 1) + "°"); }
  function fill(template, focal) { return template.replace("{focal}", focal); }

  function crop() {
    var option = bodySelect.options[bodySelect.selectedIndex];
    return parseFloat(option.getAttribute("data-crop"));
  }

  function photoAspect() {
    return photo.naturalWidth && photo.naturalHeight ? photo.naturalWidth / photo.naturalHeight : 1.5;
  }

  function ensureChip(focal) {
    var chip = chipsBox.querySelector('[data-focal="' + focal + '"]');
    if (chip) return chip;
    chip = document.createElement("button");
    chip.type = "button";
    chip.className = "chip";
    chip.setAttribute("data-focal", String(focal));
    chip.textContent = String(focal);
    var later = Array.prototype.find.call(chipsBox.children, function (c) {
      return parseFloat(c.getAttribute("data-focal")) > focal;
    });
    chipsBox.insertBefore(chip, later || null);
    return chip;
  }

  function syncChips() {
    state.focals.forEach(ensureChip);
    Array.prototype.forEach.call(chipsBox.children, function (chip) {
      var focal = parseFloat(chip.getAttribute("data-focal"));
      chip.setAttribute("aria-pressed", state.focals.indexOf(focal) >= 0 ? "true" : "false");
    });
  }

  function svgEl(name, attrs) {
    var el = document.createElementNS("http://www.w3.org/2000/svg", name);
    Object.keys(attrs).forEach(function (k) { el.setAttribute(k, attrs[k]); });
    return el;
  }

  function drawFrames() {
    var old = stage.querySelector("svg.frames");
    if (old) old.remove();
    var aspect = photoAspect();
    var w = 1000, h = 1000 / aspect;
    var svg = svgEl("svg", { class: "frames", viewBox: "0 0 " + w + " " + h, "aria-hidden": "true" });
    var tooWide = [];
    var drawn = 0;
    state.focals.forEach(function (focal) {
      var f = frameInPhoto(focal, crop(), state.photoFocal, aspect);
      if (f[0] > 1.0001 || f[1] > 1.0001) { tooWide.push(focal); return; }
      var x = ((1 - f[0]) * w) / 2, y = ((1 - f[1]) * h) / 2;
      svg.appendChild(svgEl("rect", {
        x: x, y: y, width: f[0] * w, height: f[1] * h,
        class: focal === state.selected ? "active" : "",
      }));
      // Alternate corners so labels of neighbouring frames don't overlap.
      var even = drawn++ % 2 === 0;
      var label = svgEl("text", even
        ? { x: x + 8, y: y + 26 }
        : { x: x + f[0] * w - 8, y: y + f[1] * h - 10, "text-anchor": "end" });
      label.textContent = focal + " mm";
      svg.appendChild(label);
    });
    stage.appendChild(svg);
    notes.textContent = tooWide.map(function (f) { return fill(strings["tool.too_wide"], mm(f)); }).join(". ");
  }

  function drawTable() {
    var c = crop();
    var head = ["tool.table_focal", "tool.table_equiv", "tool.table_h", "tool.table_v", "tool.table_d"]
      .map(function (k) { return '<th scope="col">' + escapeHtml(strings[k]) + "</th>"; }).join("");
    var rows = state.focals.map(function (focal) {
      var a = angles(focal, c);
      return '<tr class="clickable' + (focal === state.selected ? " selected" : "") + '" data-focal="' + focal +
        '" tabindex="0"><th scope="row">' + mm(focal) + "</th><td>" + mm(focal * c) + "</td><td>" + deg(a[0]) +
        "</td><td>" + deg(a[1]) + "</td><td>" + deg(a[2]) + "</td></tr>";
    }).join("");
    results.innerHTML = '<div class="scroll"><table class="angles"><thead><tr>' + head + "</tr></thead><tbody>" +
      rows + "</tbody></table></div>";
  }

  function drawPreview() {
    if (state.selected === null || !photo.complete || !photo.naturalWidth) { preview.hidden = true; return; }
    var f = frameInPhoto(state.selected, crop(), state.photoFocal, photoAspect());
    if (f[0] > 1.0001 || f[1] > 1.0001) { preview.hidden = true; return; }
    var sw = f[0] * photo.naturalWidth, sh = f[1] * photo.naturalHeight;
    var sx = (photo.naturalWidth - sw) / 2, sy = (photo.naturalHeight - sh) / 2;
    var width = Math.min(1200, Math.max(600, Math.round(sw)));
    canvas.width = width;
    canvas.height = Math.round((width * sh) / sw);
    var ctx = canvas.getContext("2d");
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(photo, sx, sy, sw, sh, 0, 0, canvas.width, canvas.height);
    previewCaption.textContent = fill(strings["tool.preview_title"], mm(state.selected));
    preview.hidden = false;
  }

  function escapeHtml(text) {
    return String(text).replace(/[&<>"]/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[ch];
    });
  }

  function writeUrl() {
    var query = "?body=" + encodeURIComponent(state.body) + "&f=" + state.focals.join(",");
    history.replaceState(null, "", location.pathname + query);
  }

  function render() {
    state.focals.sort(function (a, b) { return a - b; });
    if (state.focals.indexOf(state.selected) < 0) state.selected = null;
    syncChips();
    drawFrames();
    drawTable();
    drawPreview();
    writeUrl();
  }

  function readUrl() {
    var params = new URLSearchParams(location.search);
    var body = params.get("body");
    if (body && bodySelect.querySelector('option[value="' + CSS.escape(body) + '"]')) state.body = body;
    var f = (params.get("f") || "").split(",").map(parseFloat).filter(function (v) { return v >= 4 && v <= 1200; });
    if (f.length) state.focals = f.filter(function (v, i) { return f.indexOf(v) === i; }).slice(0, 12);
  }

  function toggleFocal(focal) {
    var i = state.focals.indexOf(focal);
    if (i >= 0) state.focals.splice(i, 1);
    else state.focals.push(focal);
    render();
  }

  chipsBox.addEventListener("click", function (event) {
    var chip = event.target.closest(".chip");
    if (chip) toggleFocal(parseFloat(chip.getAttribute("data-focal")));
  });

  document.getElementById("add").addEventListener("click", function () {
    var focal = Math.round(parseFloat(customInput.value));
    if (!(focal >= 4 && focal <= 1200)) return;
    if (state.focals.indexOf(focal) < 0) state.focals.push(focal);
    customInput.value = "";
    render();
  });
  customInput.addEventListener("keydown", function (event) {
    if (event.key === "Enter") { event.preventDefault(); document.getElementById("add").click(); }
  });

  bodySelect.addEventListener("change", function () { state.body = bodySelect.value; render(); });

  results.addEventListener("click", function (event) {
    var row = event.target.closest("tr[data-focal]");
    if (!row) return;
    var focal = parseFloat(row.getAttribute("data-focal"));
    state.selected = state.selected === focal ? null : focal;
    render();
    if (state.selected !== null && !preview.hidden) preview.scrollIntoView({ block: "nearest", behavior: "smooth" });
  });
  results.addEventListener("keydown", function (event) {
    if ((event.key === "Enter" || event.key === " ") && event.target.matches("tr[data-focal]")) {
      event.preventDefault();
      event.target.click();
    }
  });

  form.addEventListener("change", function (event) {
    if (event.target.name !== "photo") return;
    var own = event.target.value === "own";
    ownBox.hidden = !own;
    if (!own) {
      photo.src = photo.getAttribute("data-sample");
      state.photoFocal = data.sample.focal;
    } else if (state.ownUrl) {
      photo.src = state.ownUrl;
      state.photoFocal = parseFloat(photoFocalInput.value) || 26;
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
    if (value >= 4 && value <= 1200 && form.querySelector('input[name="photo"]:checked').value === "own") {
      state.photoFocal = value;
      render();
    }
  });

  photo.addEventListener("load", render);

  shareButton.addEventListener("click", function () {
    var done = function () { shareStatus.textContent = strings["tool.copied"]; };
    if (navigator.clipboard) navigator.clipboard.writeText(location.href).then(done, function () {});
  });

  photo.setAttribute("data-sample", photo.getAttribute("src"));
  readUrl();
  bodySelect.value = state.body;
  form.hidden = false;
  var staticFigure = document.getElementById("static-figure");
  if (staticFigure) staticFigure.hidden = true;
  render();
})();
