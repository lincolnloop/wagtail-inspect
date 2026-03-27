/**
 * Editor block lookup, panel expand, hash scroll on edit pages.
 * window.WagtailInspectPreviewHelpers — load before preview-inspect-controller.js.
 */
(function (global) {
  "use strict";

  var BLOCK_HASH_RE = /^#block-([a-f0-9-]+)-section$/;
  var PAGE_ID_IN_PATH_RE = /\/pages\/(\d+)\//;

  function findEditorBlock(blockId) {
    return (
      document.querySelector(`[data-contentpath="${blockId}"]`) ||
      document.getElementById(`block-${blockId}-section`) ||
      document.querySelector(`[data-block-id="${blockId}"]`)
    );
  }

  function expandPanelIfCollapsed(panelSection) {
    const content = panelSection.querySelector(".w-panel__content");
    const toggleButton = panelSection.querySelector("[data-panel-toggle]");

    if (content?.hasAttribute("hidden")) {
      content.removeAttribute("hidden");
      toggleButton?.setAttribute("aria-expanded", "true");
    }
  }

  function expandCollapsedAncestors(element) {
    const ownPanel = element.closest("section.w-panel");
    if (ownPanel) {
      expandPanelIfCollapsed(ownPanel);
    }

    let current = element.parentElement;
    while (current) {
      if (current.matches("section.w-panel")) {
        expandPanelIfCollapsed(current);
      }
      current = current.parentElement;
    }
  }

  function flashHighlight(element) {
    element.classList.remove("wagtail-inspect-flash");
    void element.offsetWidth;
    element.classList.add("wagtail-inspect-flash");
    element.addEventListener(
      "animationend",
      () => {
        element.classList.remove("wagtail-inspect-flash");
      },
      { once: true },
    );
  }

  function scrollToHashBlock() {
    const hash = window.location.hash;
    if (!hash) return;

    if (!document.body.classList.contains("editor-view")) return;

    const match = hash.match(BLOCK_HASH_RE);
    if (!match) return;

    const blockId = match[1];
    const blockElement = findEditorBlock(blockId);
    if (!blockElement) return;

    expandCollapsedAncestors(blockElement);
    blockElement.scrollIntoView({ behavior: "instant" });
    requestAnimationFrame(() => flashHighlight(blockElement));
  }

  global.WagtailInspectPreviewHelpers = {
    BLOCK_HASH_RE: BLOCK_HASH_RE,
    PAGE_ID_IN_PATH_RE: PAGE_ID_IN_PATH_RE,
    findEditorBlock: findEditorBlock,
    expandPanelIfCollapsed: expandPanelIfCollapsed,
    expandCollapsedAncestors: expandCollapsedAncestors,
    flashHighlight: flashHighlight,
    scrollToHashBlock: scrollToHashBlock,
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
