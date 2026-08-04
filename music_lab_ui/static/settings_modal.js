/*
 * Overlay behaviour: the settings dialog, and the popovers behind the little
 * badges beside a chart or a detector score.
 *
 * The two live together because Escape has to pick between them — with a dialog
 * open it belongs to the dialog, and only otherwise to the popovers. Splitting
 * the file would mean one half reaching into the other's markup to find that
 * out.
 *
 * Visibility of the dialog itself is Gradio's: the panel is a Column whose
 * `visible` flag a Python callback toggles. This script never hides it
 * directly — it clicks the same close button a user would, so there is exactly
 * one path that changes the state and Python's idea of it cannot drift from
 * the DOM's.
 */
(function () {
  "use strict";

  // Every detector has a dialog of its own, so this has to find the open one
  // rather than the first one: querySelector would keep returning the hidden
  // muscriptor panel and Escape would do nothing for the others.
  function openModal() {
    var modals = document.querySelectorAll(".settings-modal");
    for (var i = 0; i < modals.length; i += 1) {
      // Not offsetParent: that is always null on a fixed-position element,
      // which these are, so the usual visibility check never sees them open.
      if (modals[i].getClientRects().length) return modals[i];
    }
    return null;
  }

  function close(modal) {
    var button = modal.querySelector(".settings-close button, button.settings-close");
    if (button) button.click();
  }

  /*
   * Badge disclosures open as popovers. Native <details> has no light dismiss,
   * so one is supplied — otherwise every explanation you glance at stays open
   * over the chart it explains.
   */
  function openPopovers() {
    return document.querySelectorAll(".lab-disclosure.layout-badge[open]");
  }

  function closePopovers(except) {
    var open = openPopovers();
    for (var i = 0; i < open.length; i += 1) {
      if (open[i] !== except) open[i].removeAttribute("open");
    }
  }

  /*
   * Placement.
   *
   * CSS anchors the popover under its badge, which is right whenever there is
   * room and wrong the moment there is not: the caveat badge on a detector card
   * sits at the right edge of a 305px card while the popover is 560px wide, so
   * a left-anchored box starts 443px past the window edge — and is clipped away
   * entirely first, by the card's own `overflow: hidden`.
   *
   * Neither part is expressible in CSS. It cannot ask how much room is left
   * beside the badge, and anchor positioning — which could — is Chromium-only
   * today. So the box is measured and pinned to viewport coordinates here.
   * Nothing above the badge needs to change: `position: fixed` leaves every
   * clipping ancestor behind, and the placement only ever moves the popover
   * further inside the window, never away from what it explains.
   */
  var VIEWPORT_MARGIN = 12;
  var ANCHOR_GAP = 6;
  // Below this, "under the badge" and "above the badge" are both unusable and
  // the popover takes the window instead of opening as a two-line sliver.
  var MIN_ROOM = 160;
  // Which popover currently holds pinned coordinates. Kept so that scroll —
  // which fires far more often than anything else here — costs a null check
  // rather than a document-wide query.
  var pinned = null;

  function place(details) {
    var summary = details.querySelector(":scope > summary");
    var body = details.querySelector(":scope > .lab-disclosure-body");
    if (!summary || !body) return;

    // Cleared before measuring: a clamp left over from the last placement would
    // otherwise be read back as the box's natural height and never grow again.
    body.style.maxHeight = "";

    var anchor = summary.getBoundingClientRect();
    var box = body.getBoundingClientRect();
    var viewWidth = document.documentElement.clientWidth;
    var viewHeight = document.documentElement.clientHeight;

    if (anchor.bottom < 0 || anchor.top > viewHeight) {
      // Scrolled past its badge. A pinned box does not follow, so it would hang
      // over unrelated content pointing at nothing.
      details.removeAttribute("open");
      return;
    }

    var below = viewHeight - anchor.bottom - ANCHOR_GAP - VIEWPORT_MARGIN;
    var above = anchor.top - ANCHOR_GAP - VIEWPORT_MARGIN;
    var room = below;
    var top = anchor.bottom + ANCHOR_GAP;
    if (Math.max(above, below) < MIN_ROOM) {
      room = viewHeight - VIEWPORT_MARGIN * 2;
      top = VIEWPORT_MARGIN;
    } else if (box.height > below && above > below) {
      room = above;
      top = anchor.top - ANCHOR_GAP - Math.min(box.height, room);
    }
    if (box.height > room) body.style.maxHeight = room + "px";

    // Aligned with the badge when it fits, pulled in from the window edge when
    // it does not.
    var left = Math.min(anchor.left, viewWidth - VIEWPORT_MARGIN - box.width);

    body.style.left = Math.max(VIEWPORT_MARGIN, left) + "px";
    body.style.top = top + "px";
    details.classList.add("is-placed");
  }

  function placeOpen() {
    if (!pinned) return;
    // Gradio replaces this markup wholesale on every analysis, and a detached
    // node measures as a zero-sized box at the window origin.
    if (!pinned.isConnected) {
      pinned = null;
      return;
    }
    place(pinned);
  }

  // `toggle` does not bubble, and the markup is re-rendered by Gradio on every
  // analysis, so there is nothing stable to bind to — but a capture-phase
  // listener still sees non-bubbling events on the way down.
  document.addEventListener(
    "toggle",
    function (event) {
      var details = event.target;
      if (!details.classList || !details.classList.contains("layout-badge")) return;
      if (details.hasAttribute("open")) {
        pinned = details;
        place(details);
      } else if (pinned === details) {
        pinned = null;
      }
    },
    true
  );

  // Capture again for scroll: the interface has inner scrollers, and a scroll
  // event from one of those never reaches the document by bubbling.
  document.addEventListener("scroll", placeOpen, true);
  window.addEventListener("resize", placeOpen);

  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") return;
    var modal = openModal();
    if (modal) {
      close(modal);
      return;
    }
    closePopovers(null);
  });

  // The backdrop is the modal's own ::before, so a click that lands on the
  // element itself rather than on anything inside it came from the backdrop.
  document.addEventListener("click", function (event) {
    var modal = openModal();
    if (modal && event.target === modal) {
      close(modal);
      return;
    }
    // `closest` keeps the popover open when the click was inside it — links in
    // a body have to stay clickable.
    var inside = event.target.closest
      ? event.target.closest(".lab-disclosure.layout-badge")
      : null;
    closePopovers(inside);
  });
})();
