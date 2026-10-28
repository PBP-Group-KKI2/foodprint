/* FoodPrint – Reporting & Mapping
 * Leaflet + OpenStreetMap. One script for three pages:
 *   #rp-app          main map: pins, filters, list, AJAX create/delete
 *   #rp-picker-map   edit page: move the pin
 *   #rp-detail-map   detail page: one pin
 */
(function () {
  "use strict";

  var DEFAULT_CENTER = [-6.3628, 106.8269]; // Universitas Indonesia, Depok
  var DEFAULT_ZOOM = 14;
  var SEVERITY_COLORS = { LOW: "#7E9A4B", MEDIUM: "#D9A441", HIGH: "#B5462F" };

  // ---------- helpers ----------

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function round6(n) {
    return Math.round(n * 1e6) / 1e6;
  }

  function csrfToken(scope) {
    var input = (scope || document).querySelector("input[name=csrfmiddlewaretoken]");
    return input ? input.value : "";
  }

  function baseMap(el, center, zoom) {
    var map = L.map(el, { scrollWheelZoom: true }).setView(center, zoom);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      referrerPolicy: "strict-origin-when-cross-origin",
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);
    return map;
  }

  function severityPin(lat, lng, severity) {
    return L.circleMarker([lat, lng], {
      radius: 9,
      color: "#ffffff",
      weight: 2,
      fillColor: SEVERITY_COLORS[severity] || SEVERITY_COLORS.MEDIUM,
      fillOpacity: 0.95,
    });
  }

  function draftPin(latlng) {
    return L.marker(latlng, {
      draggable: true,
      keyboard: true,
      title: "New report location (drag to adjust)",
      icon: L.divIcon({ className: "rp-pin", iconSize: [22, 22], iconAnchor: [11, 11] }),
    });
  }

  function popupHtml(r) {
    var place = r.location_name ? '<div class="rp-popup__place">' + escapeHtml(r.location_name) + "</div>" : "";
    return (
      '<div class="rp-popup">' +
      '<strong class="rp-popup__title">' + escapeHtml(r.title) + "</strong>" +
      place +
      '<div class="rp-popup__meta">' +
      escapeHtml(r.waste_type_label) + " · " + escapeHtml(r.severity_label) + " · " + escapeHtml(r.status_label) +
      "</div>" +
      '<div class="rp-popup__meta">by ' + escapeHtml(r.reporter) + "</div>" +
      '<a href="' + escapeHtml(r.detail_url) + '">View details</a>' +
      "</div>"
    );
  }

  function debounce(fn, ms) {
    var t;
    return function () {
      var args = arguments;
      clearTimeout(t);
      t = setTimeout(function () { fn.apply(null, args); }, ms);
    };
  }

  // ---------- OpenStreetMap Nominatim (place search + reverse lookup) ----------
  // Nominatim's free tier allows about one request per second, so every call
  // goes through geocoderFetch(), which records when the last one was sent.

  var GEOCODER_URL = "https://nominatim.openstreetmap.org/search";
  var REVERSE_URL = "https://nominatim.openstreetmap.org/reverse";
  var GEOCODER_GAP_MS = 1100;
  var lastGeocoderCall = 0;

  function geocoderFetch(url, params) {
    lastGeocoderCall = Date.now();
    return fetch(url + "?" + params.toString(), {
      headers: { Accept: "application/json" },
      referrerPolicy: "strict-origin-when-cross-origin",
    }).then(function (res) {
      if (!res.ok) throw new Error("Geocoder error (" + res.status + ")");
      return res.json();
    });
  }

  // Nominatim address -> { city, district }. In Indonesia "city" is the
  // kota/kabupaten and "city_district" is usually the kecamatan; the other
  // keys are fallbacks for places tagged differently.
  function pickArea(address) {
    var a = address || {};
    return {
      city: a.city || a.town || a.municipality || a.county || a.state_district || "",
      district: a.city_district || a.district || a.subdistrict || a.suburb || "",
    };
  }

  // Looks up the area for a pin once it stops moving. Only the latest pin
  // position is looked up, and calls stay at least GEOCODER_GAP_MS apart.
  function makeAreaLookup() {
    var timer = null;
    var latest = 0;
    return function (latlng, onArea) {
      clearTimeout(timer);
      var id = ++latest;
      var wait = Math.max(600, GEOCODER_GAP_MS - (Date.now() - lastGeocoderCall));
      timer = setTimeout(function () {
        var params = new URLSearchParams({
          lat: String(latlng.lat),
          lon: String(latlng.lng),
          format: "jsonv2",
          zoom: "14",
          addressdetails: "1",
          "accept-language": "id",
        });
        geocoderFetch(REVERSE_URL, params)
          .then(function (data) {
            if (id !== latest || !data || !data.address) return; // pin moved again
            onArea(pickArea(data.address));
          })
          .catch(function () { /* leave the fields for the user to fill */ });
      }, wait);
    };
  }

  // City/district inputs: filled from the pin, but never overwrite what the
  // user typed themselves.
  function areaFields(form) {
    var inputs = ["city", "district"]
      .map(function (name) { return form.querySelector("[name=" + name + "]"); })
      .filter(Boolean);
    inputs.forEach(function (input) {
      input.addEventListener("input", function () { input.dataset.manual = "1"; });
    });
    return {
      fill: function (area) {
        inputs.forEach(function (input) {
          if (!input.dataset.manual) input.value = area[input.name] || "";
        });
      },
      reset: function () {
        inputs.forEach(function (input) { delete input.dataset.manual; });
      },
    };
  }

  function shortPlaceName(result) {
    if (result.name) return result.name;
    return result.display_name.split(",").slice(0, 2).join(",").trim();
  }

  function initPlaceSearch(container, map, onPick) {
    if (!container) return;
    var input = container.querySelector(".rp-search__input");
    var button = container.querySelector(".rp-search__btn");
    var resultsList = container.querySelector(".rp-search__results");
    var status = container.querySelector(".rp-search__status");
    var busy = false;

    function setStatus(text) {
      status.textContent = text || "";
    }

    function closeResults() {
      resultsList.hidden = true;
      resultsList.innerHTML = "";
    }

    function pick(result) {
      var latlng = L.latLng(parseFloat(result.lat), parseFloat(result.lon));
      closeResults();
      input.value = shortPlaceName(result);
      setStatus("");
      map.setView(latlng, 17);
      onPick(latlng, shortPlaceName(result), pickArea(result.address));
    }

    function showResults(results) {
      resultsList.innerHTML = "";
      results.forEach(function (result) {
        var li = document.createElement("li");
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "rp-search__result";
        btn.setAttribute("role", "option");
        btn.innerHTML =
          '<span class="rp-search__result-name">' + escapeHtml(shortPlaceName(result)) + "</span>" +
          '<span class="rp-search__result-detail">' + escapeHtml(result.display_name) + "</span>";
        btn.addEventListener("click", function () { pick(result); });
        li.appendChild(btn);
        resultsList.appendChild(li);
      });
      resultsList.hidden = results.length === 0;
    }

    function search() {
      var query = input.value.trim();
      if (busy) return;
      if (query.length < 3) {
        setStatus("Type at least 3 characters.");
        return;
      }

      // Prefer results near what the map is showing, but don't exclude others.
      var b = map.getBounds();
      var params = new URLSearchParams({
        q: query,
        format: "jsonv2",
        limit: "5",
        addressdetails: "1",
        countrycodes: "id",
        "accept-language": "id,en",
        viewbox: [b.getWest(), b.getNorth(), b.getEast(), b.getSouth()].join(","),
        bounded: "0",
      });

      busy = true;
      button.disabled = true;
      setStatus("Searching…");
      closeResults();

      geocoderFetch(GEOCODER_URL, params)
        .then(function (results) {
          if (!results.length) {
            setStatus("No places found. Try a different name, or click the map.");
            return;
          }
          if (results.length === 1) {
            pick(results[0]);
            return;
          }
          setStatus(results.length + " places found. Choose one:");
          showResults(results);
        })
        .catch(function () {
          setStatus("Search isn't available right now. Click the map instead.");
        })
        .then(function () {
          // Short cooldown keeps us within the geocoder's rate limit.
          setTimeout(function () {
            busy = false;
            button.disabled = false;
          }, 1000);
        });
    }

    button.addEventListener("click", search);
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter") {
        e.preventDefault(); // don't submit the surrounding report form
        search();
      } else if (e.key === "Escape") {
        closeResults();
      }
    });
    document.addEventListener("click", function (e) {
      if (!container.contains(e.target)) closeResults();
    });
  }

  // ---------- main map page ----------

  function initApp(root) {
    var map = baseMap(root.querySelector("#rp-map"), DEFAULT_CENTER, DEFAULT_ZOOM);
    var pinLayer = L.layerGroup().addTo(map);
    var markers = {};
    var list = root.querySelector("#rp-list");
    var count = root.querySelector("#rp-count");
    var filterForm = root.querySelector("#rp-filter");
    var reportForm = root.querySelector("#rp-form");
    var token = csrfToken(root);
    var hasFitted = false;
    var requestId = 0;

    function setCount(n) {
      count.textContent = n + (n === 1 ? " report" : " reports");
    }

    function filterParams() {
      var params = new URLSearchParams(new FormData(filterForm));
      Array.from(params.keys()).forEach(function (key) {
        if (!params.get(key)) params.delete(key);
      });
      return params;
    }

    function drawPins(reports) {
      pinLayer.clearLayers();
      markers = {};
      reports.forEach(function (r) {
        var m = severityPin(r.latitude, r.longitude, r.severity).bindPopup(popupHtml(r));
        m.addTo(pinLayer);
        markers[r.id] = m;
      });
      if (!hasFitted && reports.length) {
        var bounds = L.latLngBounds(reports.map(function (r) { return [r.latitude, r.longitude]; }));
        map.fitBounds(bounds, { padding: [40, 40], maxZoom: 16 });
        hasFitted = true;
      }
    }

    function load() {
      var params = filterParams();
      var thisRequest = ++requestId;
      var query = params.toString();
      history.replaceState(null, "", window.location.pathname + (query ? "?" + query : ""));

      return fetch(root.dataset.apiUrl + (query ? "?" + query : ""), {
        headers: { "X-Requested-With": "XMLHttpRequest" },
      })
        .then(function (res) {
          if (!res.ok) throw new Error("Could not load reports (" + res.status + ")");
          return res.json();
        })
        .then(function (data) {
          if (thisRequest !== requestId) return; // a newer filter request won
          drawPins(data.reports);
          list.innerHTML = data.html;
          setCount(data.count);
        })
        .catch(function (err) {
          list.innerHTML = '<li class="rp-empty">' + escapeHtml(err.message) + "</li>";
        });
    }

    // Filters: selects/checkbox apply instantly, search waits for typing to pause.
    filterForm.addEventListener("change", load);
    filterForm.addEventListener("input", debounce(function (e) {
      if (e.target.type === "search") load();
    }, 350));
    filterForm.addEventListener("submit", function (e) {
      e.preventDefault();
      load();
    });

    // List: focus a pin, or delete via AJAX.
    list.addEventListener("click", function (e) {
      var focusBtn = e.target.closest("[data-focus]");
      if (focusBtn) {
        var marker = markers[focusBtn.dataset.focus];
        if (marker) {
          map.setView(marker.getLatLng(), Math.max(map.getZoom(), 16));
          marker.openPopup();
          root.querySelector("#rp-map").scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
        return;
      }

      var deleteBtn = e.target.closest("[data-delete-url]");
      if (deleteBtn) {
        if (!confirm("Delete this report? This cannot be undone.")) return;
        deleteBtn.disabled = true;
        fetch(deleteBtn.dataset.deleteUrl, {
          method: "POST",
          headers: { "X-CSRFToken": token, "X-Requested-With": "XMLHttpRequest" },
        })
          .then(function (res) {
            if (!res.ok) throw new Error("Delete failed (" + res.status + ")");
            return res.json();
          })
          .then(function () { load(); })
          .catch(function (err) {
            deleteBtn.disabled = false;
            alert(err.message);
          });
      }
    });

    // Report form (only rendered for logged-in users).
    if (reportForm) initReportForm(root, map, reportForm, token, function (newId) {
      return load().then(function () {
        var marker = markers[newId];
        if (marker) {
          map.setView(marker.getLatLng(), Math.max(map.getZoom(), 16));
          marker.openPopup();
        }
      });
    });

    // The list is server-rendered; this fetch draws the pins.
    load();
  }

  function initReportForm(root, map, form, token, onCreated) {
    var latInput = form.querySelector("[name=latitude]");
    var lngInput = form.querySelector("[name=longitude]");
    var hint = form.querySelector("#rp-location-hint");
    var hintDefault = hint.innerHTML;
    var status = form.querySelector("#rp-form-status");
    var submitBtn = form.querySelector("#rp-submit");
    var locateBtn = form.querySelector("#rp-locate");
    var draft = null;
    var area = areaFields(form);
    var lookupArea = makeAreaLookup();

    function clearErrors() {
      form.querySelectorAll("[data-error-for]").forEach(function (el) { el.textContent = ""; });
      status.textContent = "";
    }

    function showErrors(errors) {
      Object.keys(errors).forEach(function (field) {
        var key = field === "longitude" ? "latitude" : field; // one slot for the location
        var slot = form.querySelector('[data-error-for="' + key + '"]');
        if (slot && !slot.textContent) slot.textContent = errors[field].join(" ");
      });
    }

    // knownArea comes from a search result; otherwise it is looked up.
    function setLocation(latlng, knownArea) {
      var lat = round6(latlng.lat);
      var lng = round6(latlng.lng);
      latInput.value = lat;
      lngInput.value = lng;
      if (draft) {
        draft.setLatLng([lat, lng]);
      } else {
        draft = draftPin([lat, lng]).addTo(map);
        draft.on("dragend", function () { setLocation(draft.getLatLng()); });
      }
      if (knownArea) area.fill(knownArea);
      else lookupArea(L.latLng(lat, lng), area.fill);
      hint.textContent = "Pinned at " + lat.toFixed(5) + ", " + lng.toFixed(5) + ". Drag the pin or click elsewhere to adjust.";
      var locErr = form.querySelector('[data-error-for="latitude"]');
      if (locErr) locErr.textContent = "";
    }

    function resetForm() {
      form.reset();
      latInput.value = "";
      lngInput.value = "";
      if (draft) { map.removeLayer(draft); draft = null; }
      area.reset();
      hint.innerHTML = hintDefault;
      bindLocate();
    }

    function bindLocate() {
      var btn = form.querySelector("#rp-locate");
      if (!btn) return;
      if (!("geolocation" in navigator)) { btn.hidden = true; return; }
      btn.addEventListener("click", function () {
        btn.disabled = true;
        navigator.geolocation.getCurrentPosition(
          function (pos) {
            var here = L.latLng(pos.coords.latitude, pos.coords.longitude);
            map.setView(here, 17);
            setLocation(here);
          },
          function () {
            btn.disabled = false;
            form.querySelector('[data-error-for="latitude"]').textContent =
              "Couldn't get your location. Click the map instead.";
          },
          { enableHighAccuracy: true, timeout: 10000 }
        );
      });
    }

    map.on("click", function (e) { setLocation(e.latlng); });
    if (locateBtn) bindLocate();

    var placeInput = form.querySelector("[name=location_name]");
    initPlaceSearch(form.querySelector("[data-place-search]"), map, function (latlng, name, foundArea) {
      setLocation(latlng, foundArea);
      if (placeInput && !placeInput.value) placeInput.value = name;
    });

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      clearErrors();

      if (!latInput.value || !lngInput.value) {
        showErrors({ latitude: ["Search for a place or click the map to pin where the waste is."] });
        return;
      }

      submitBtn.disabled = true;
      submitBtn.textContent = "Submitting…";

      fetch(root.dataset.createUrl, {
        method: "POST",
        headers: { "X-CSRFToken": token, "X-Requested-With": "XMLHttpRequest" },
        body: new FormData(form),
      })
        .then(function (res) {
          return res.json().then(function (data) { return { status: res.status, data: data }; });
        })
        .then(function (result) {
          if (result.status === 201) {
            resetForm();
            status.textContent = "Report submitted. Thanks for helping!";
            return onCreated(result.data.report.id);
          }
          if (result.status === 400) {
            showErrors(result.data.errors || {});
            return;
          }
          showErrors({ __all__: [result.data.error || "Something went wrong. Please try again."] });
        })
        .catch(function () {
          showErrors({ __all__: ["Network error. Check your connection and try again."] });
        })
        .then(function () {
          submitBtn.disabled = false;
          submitBtn.textContent = "Submit report";
        });
    });
  }

  // ---------- edit page ----------

  function initPicker(el) {
    var form = el.closest("form");
    var latInput = form.querySelector("[name=latitude]");
    var lngInput = form.querySelector("[name=longitude]");
    var lat = parseFloat(latInput.value);
    var lng = parseFloat(lngInput.value);
    var start = isNaN(lat) || isNaN(lng) ? DEFAULT_CENTER : [lat, lng];
    var map = baseMap(el, start, 16);
    var pin = draftPin(start).addTo(map);
    var area = areaFields(form);
    var lookupArea = makeAreaLookup();

    function setLocation(latlng, knownArea) {
      latInput.value = round6(latlng.lat);
      lngInput.value = round6(latlng.lng);
      pin.setLatLng(latlng);
      if (knownArea) area.fill(knownArea);
      else lookupArea(latlng, area.fill);
    }

    pin.on("dragend", function () { setLocation(pin.getLatLng()); });
    map.on("click", function (e) { setLocation(e.latlng); });

    var placeInput = form.querySelector("[name=location_name]");
    initPlaceSearch(form.querySelector("[data-place-search]"), map, function (latlng, name, foundArea) {
      setLocation(latlng, foundArea);
      if (placeInput && !placeInput.value) placeInput.value = name;
    });
  }

  // ---------- detail page ----------

  function initDetail(el) {
    var lat = parseFloat(el.dataset.lat);
    var lng = parseFloat(el.dataset.lng);
    var map = baseMap(el, [lat, lng], 17);
    severityPin(lat, lng, el.dataset.severity).addTo(map);
  }

  // ---------- boot ----------

  document.addEventListener("DOMContentLoaded", function () {
    if (typeof L === "undefined") return; // Leaflet failed to load
    var app = document.getElementById("rp-app");
    var picker = document.getElementById("rp-picker-map");
    var detail = document.getElementById("rp-detail-map");
    if (app) initApp(app);
    if (picker) initPicker(picker);
    if (detail) initDetail(detail);
  });
})();