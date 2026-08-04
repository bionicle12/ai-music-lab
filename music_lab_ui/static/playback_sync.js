/*
 * Two-way sync between Plotly time charts and the Gradio audio player.
 *
 *   chart click  -> player seeks to that second
 *   playback     -> playhead line follows on every opted-in chart
 *
 * Runs entirely in the browser: a server round-trip per frame would be far too
 * slow for a playhead. Charts opt in through `layout.meta.time_axis`, set in
 * plots.py, so frequency-domain charts never get a time playhead.
 *
 * Gradio 6 renders the player with wavesurfer, whose real <audio> element lives
 * inside a shadow root — a plain document.querySelector('audio') finds only the
 * unused fallback element with an empty src.
 */
(function () {
  "use strict";

  var PLAYHEAD_COLOR = "#f0a443";
  var FRAME_INTERVAL_MS = 40; // ~25 fps; timeupdate alone fires only ~4x/sec
  var audioElement = null;
  var rafHandle = null;
  var lastDrawn = -1;
  var lastFrameAt = 0;

  function allAudio() {
    var found = [];
    // The wavesurfer player keeps its real <audio> in a shadow root, so a plain
    // document query finds only the unused fallback element.
    var hosts = document.querySelectorAll("*");
    for (var i = 0; i < hosts.length; i += 1) {
      var root = hosts[i].shadowRoot;
      if (!root) continue;
      var candidate = root.querySelector("audio");
      if (candidate && candidate.src) found.push(candidate);
    }
    // …but a native player lives in the light DOM, and a shadow-only sweep
    // would silently drop chart-click seeking for it.
    var plain = document.querySelectorAll("audio");
    for (var j = 0; j < plain.length; j += 1) {
      if (plain[j].src && found.indexOf(plain[j]) === -1) found.push(plain[j]);
    }
    return found;
  }

  /*
   * There is more than one player on the page — the analysed track and the MIDI
   * preview — so "the first audio element with a src" is the wrong answer.
   * `audioElement` is whichever one last started playing; a still-playing
   * element always wins over that, in case a stale handle survived a re-render.
   */
  function findAudio() {
    var players = allAudio();
    for (var i = 0; i < players.length; i += 1) {
      if (!players[i].paused) {
        audioElement = players[i];
        return players[i];
      }
    }
    if (audioElement && audioElement.isConnected && audioElement.src) {
      return audioElement;
    }
    audioElement = players.length ? players[0] : null;
    return audioElement;
  }

  function timeCharts() {
    var charts = document.querySelectorAll(".js-plotly-plot");
    var out = [];
    for (var i = 0; i < charts.length; i += 1) {
      var chart = charts[i];
      var meta = chart.layout && chart.layout.meta;
      if (meta && meta.time_axis) out.push(chart);
    }
    return out;
  }

  function baseShapes(chart) {
    if (!chart._aiLabBaseShapes) {
      var existing = (chart.layout && chart.layout.shapes) || [];
      chart._aiLabBaseShapes = existing.filter(function (shape) {
        return !shape || shape.name !== "ai-lab-playhead";
      });
    }
    return chart._aiLabBaseShapes;
  }

  function drawPlayhead(seconds) {
    var playhead = {
      name: "ai-lab-playhead",
      type: "line",
      xref: "x",
      yref: "paper",
      x0: seconds,
      x1: seconds,
      y0: 0,
      y1: 1,
      line: { color: PLAYHEAD_COLOR, width: 2 },
      layer: "above"
    };
    var charts = timeCharts();
    for (var i = 0; i < charts.length; i += 1) {
      var chart = charts[i];
      // Skip charts on hidden tabs: relayout on them costs work nobody sees.
      if (!chart.offsetParent) continue;
      try {
        window.Plotly.relayout(chart, {
          shapes: baseShapes(chart).concat([playhead])
        });
      } catch (error) {
        /* a chart mid-rerender is not worth breaking the loop for */
      }
    }
  }

  function tick() {
    var audio = findAudio();
    if (!audio) {
      rafHandle = null;
      return;
    }
    var now = performance.now();
    if (now - lastFrameAt >= FRAME_INTERVAL_MS) {
      lastFrameAt = now;
      var position = audio.currentTime;
      if (Math.abs(position - lastDrawn) > 0.005) {
        lastDrawn = position;
        drawPlayhead(position);
      }
    }
    rafHandle = audio.paused ? null : window.requestAnimationFrame(tick);
  }

  function startLoop() {
    if (rafHandle === null) {
      lastFrameAt = 0;
      rafHandle = window.requestAnimationFrame(tick);
    }
  }

  function seek(seconds) {
    var audio = findAudio();
    if (!audio || !isFinite(seconds)) return;
    var target = Math.max(0, seconds);
    if (isFinite(audio.duration) && audio.duration > 0) {
      target = Math.min(target, audio.duration - 0.01);
    }
    audio.currentTime = target;
    lastDrawn = -1;
    drawPlayhead(target);
  }

  function bindChart(chart) {
    if (chart._aiLabBound) return;
    chart._aiLabBound = true;

    if (typeof chart.on === "function") {
      chart.on("plotly_click", function (event) {
        if (event && event.points && event.points.length) {
          seek(Number(event.points[0].x));
        }
      });
    }

    // plotly_click only fires on data points, so a click on empty canvas is
    // translated through the axis directly.
    chart.addEventListener("click", function (event) {
      if (event._aiLabHandled) return;
      try {
        var axis = chart._fullLayout && chart._fullLayout.xaxis;
        if (!axis || typeof axis.p2d !== "function") return;
        var box = chart.getBoundingClientRect();
        var left = chart._fullLayout.margin.l;
        var seconds = axis.p2d(event.clientX - box.left - left);
        if (isFinite(seconds)) {
          event._aiLabHandled = true;
          seek(seconds);
        }
      } catch (error) {
        /* internal layout not ready yet */
      }
    });
  }

  function bind(audio) {
    if (audio._aiLabBound) return;
    audio._aiLabBound = true;
    function claim() {
      // Whoever starts playing becomes the element the playhead follows.
      audioElement = audio;
      startLoop();
    }
    audio.addEventListener("play", claim);
    audio.addEventListener("playing", claim);
    audio.addEventListener("seeked", function () {
      audioElement = audio;
      lastDrawn = -1;
      drawPlayhead(audio.currentTime);
    });
    // Fallback path: fires ~4x/sec and keeps the playhead alive even if the
    // animation loop never started.
    audio.addEventListener("timeupdate", function () {
      if (audioElement && audioElement !== audio && !audioElement.paused) return;
      drawPlayhead(audio.currentTime);
      if (!audio.paused) claim();
    });
  }

  function bindAudio() {
    var players = allAudio();
    for (var i = 0; i < players.length; i += 1) bind(players[i]);
  }

  function refresh() {
    var charts = timeCharts();
    for (var i = 0; i < charts.length; i += 1) {
      bindChart(charts[i]);
    }
    bindAudio();
  }

  var refreshTimer = null;
  function scheduleRefresh() {
    if (refreshTimer) window.clearTimeout(refreshTimer);
    refreshTimer = window.setTimeout(refresh, 250);
  }

  function boot() {
    refresh();
    // Gradio replaces plot and player nodes on every update, which drops the
    // listeners attached to the old nodes.
    new MutationObserver(scheduleRefresh).observe(document.body, {
      childList: true,
      subtree: true
    });
    // A MutationObserver on document.body cannot see inside the player's shadow
    // root, and the media element gets its blob src only after the file loads —
    // so binding has to be retried on a timer as well.
    window.setInterval(bindAudio, 1000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }

  window.aiLabPlaybackSync = { seek: seek, refresh: refresh, findAudio: findAudio };
})();
