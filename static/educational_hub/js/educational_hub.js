/* FoodPrint – Educational Hub
 * HTMX does the actual requests (search, like/save, comments). This file only
 * gives feedback when a request fails, so the page never silently does nothing.
 * The server still validates and authorizes everything.
 */
(function () {
  "use strict";

  var errorBox = document.getElementById("educational-hub-error");
  var hideTimer = null;

  function showError(message) {
    if (!errorBox) return;
    errorBox.textContent = message;
    errorBox.hidden = false;
    clearTimeout(hideTimer);
    hideTimer = setTimeout(function () { errorBox.hidden = true; }, 5000);
  }

  function messageFor(status) {
    if (status === 401) return "Please log in to do that.";
    if (status === 403) return "You don't have permission to do that.";
    if (status === 404) return "That article no longer exists.";
    return "Something went wrong. Please try again.";
  }

  // Server answered with an error status (4xx/5xx). HTMX leaves the page as it was.
  document.body.addEventListener("htmx:responseError", function (e) {
    showError(messageFor(e.detail.xhr.status));
  });

  // Request never reached the server (offline, server down).
  document.body.addEventListener("htmx:sendError", function () {
    showError("Couldn't reach FoodPrint. Check your connection and try again.");
  });

  // Confirmation modals: a link with data-eh-open-dialog="<id>" opens that <dialog>.
  // If the browser has no <dialog> support, the link just opens its fallback page.
  document.addEventListener("click", function (e) {
    var trigger = e.target.closest("[data-eh-open-dialog]");
    if (!trigger) return;
    var dialog = document.getElementById(trigger.dataset.ehOpenDialog);
    if (!dialog || typeof dialog.showModal !== "function") return;
    e.preventDefault();
    dialog.showModal();
  });

  // Clicking the dark backdrop (outside the modal box) closes it, like Escape does.
  document.querySelectorAll(".educational-hub__dialog").forEach(function (dialog) {
    dialog.addEventListener("click", function (e) {
      if (e.target === dialog) dialog.close();
    });
  });

  // Mark the updating region as busy for screen readers.
  document.body.addEventListener("htmx:beforeRequest", function (e) {
    var target = e.detail.target;
    if (target) target.setAttribute("aria-busy", "true");
  });
  document.body.addEventListener("htmx:afterRequest", function (e) {
    var target = e.detail.target;
    if (target && target.isConnected) target.removeAttribute("aria-busy");
  });
})();
