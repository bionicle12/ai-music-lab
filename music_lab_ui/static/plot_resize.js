/*
 * Keep every Plotly chart as wide as the container it is drawn in.
 *
 * Gradio builds all tabs up front and hides the inactive ones with
 * `display: none`. A chart laid out while hidden measures its container as zero
 * — or keeps whatever width the previously visible layout had — and holds that
 * width once its tab is finally opened. That is the half-width chart that only
 * a page reload straightens out.
 *
 * Plotly's own responsive handler listens for window resizes, so it never sees
 * a container that changes width without one. The reveal has to be caught here.
 */
(function () {
  "use strict";

  // Sub-pixel layout rounding is normal; only a real mismatch is worth redrawing.
  var TOLERANCE_PX = 2;
  var queue = [];
  var flushTimer = null;

  function chartsIn(root) {
    return (root || document).querySelectorAll(".js-plotly-plot");
  }

  function drawnWidth(chart) {
    return (chart._fullLayout && chart._fullLayout.width) || 0;
  }

  function availableWidth(chart) {
    var box = chart.parentElement;
    return box ? box.clientWidth : 0;
  }

  function flush() {
    flushTimer = null;
    var pending = queue;
    queue = [];
    if (!window.Plotly) return;
    for (var i = 0; i < pending.length; i += 1) {
      var chart = pending[i];
      // offsetParent is null on a hidden tab: there is nothing to measure yet,
      // and the reveal will queue the chart again.
      if (!chart.isConnected || !chart.offsetParent) continue;
      var available = availableWidth(chart);
      if (!available) continue;
      // The width check is also the loop breaker: a resize that changed nothing
      // must not re-trigger the observer that asked for it.
      if (Math.abs(drawnWidth(chart) - available) <= TOLERANCE_PX) continue;
      try {
        window.Plotly.Plots.resize(chart);
      } catch (error) {
        /* a chart mid-rerender lays itself out anyway */
      }
    }
  }

  function schedule(chart) {
    if (queue.indexOf(chart) === -1) queue.push(chart);
    // A timer rather than requestAnimationFrame: rAF is paused whenever the page
    // is not compositing — a background browser tab, a hidden window — and a
    // chart that came out the wrong width would stay that way until it is looked
    // at, which is precisely when the fix is too late to be invisible.
    if (flushTimer === null) flushTimer = window.setTimeout(flush, 0);
  }

  function scheduleWithin(root) {
    var charts = chartsIn(root);
    for (var i = 0; i < charts.length; i += 1) schedule(charts[i]);
  }

  var sizeObserver =
    typeof window.ResizeObserver === "function"
      ? new window.ResizeObserver(function (entries) {
          for (var i = 0; i < entries.length; i += 1) {
            scheduleWithin(entries[i].target);
          }
        })
      : null;

  function watch() {
    if (!sizeObserver) return;
    var charts = chartsIn(document);
    for (var i = 0; i < charts.length; i += 1) {
      var box = charts[i].parentElement;
      if (!box || box._aiLabSizeWatched) continue;
      box._aiLabSizeWatched = true;
      // Hiding a tab collapses its boxes to zero and showing it restores them,
      // so the observer fires exactly at the moment a relayout is needed.
      sizeObserver.observe(box);
    }
  }

  var settleTimer = null;
  function settle() {
    // Tab switches and Gradio re-renders animate; one pass at the end catches
    // whatever was still mid-transition on the first.
    if (settleTimer) window.clearTimeout(settleTimer);
    settleTimer = window.setTimeout(function () {
      watch();
      scheduleWithin(document);
    }, 220);
  }

  function boot() {
    watch();
    scheduleWithin(document);
    // Plotly measures text to compute margins and tick spacing. A chart drawn
    // before the vendored woff2 lands keeps the fallback font's metrics — the
    // same class of bug as a dataframe sized against the wrong font.
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(settle);
    }
    // Covers browsers without ResizeObserver, and tab buttons that reveal a
    // panel whose box size happens not to change.
    document.addEventListener("click", settle, true);
    window.addEventListener("resize", settle);
    // Gradio replaces plot nodes on every update, so new charts have to be
    // picked up as they appear.
    new MutationObserver(settle).observe(document.body, {
      childList: true,
      subtree: true
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }

  window.aiLabPlotResize = { sweep: function () { scheduleWithin(document); } };
})();
