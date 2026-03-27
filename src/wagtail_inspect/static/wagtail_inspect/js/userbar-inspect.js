/**
 * Standalone preview userbar: InspectMode + API augment, then navigate to edit
 * with #block-{id}-section. Editor preview iframe uses preview-inspect-controller.js.
 */
(function () {
  "use strict";

  class InspectController {
    constructor(element, shadowRoot) {
      this.element = element;
      this.shadowRoot = shadowRoot;
      this.triggerTarget = element.querySelector('[data-wagtail-inspect-userbar-target="trigger"]');

      this.editUrlValue = "";
      this.apiUrl = "";
      this.pageIdValue = 0;
      this.inspectMode = null;

      this.toggle = this.toggle.bind(this);
    }

    connect() {
      this.loadConfiguration();
      this.fetchAndAugment();

      if (this.triggerTarget) {
        this.triggerTarget.addEventListener("click", this.toggle);
      }
    }

    disconnect() {
      if (this.inspectMode) {
        this.inspectMode.deactivate();
        this.inspectMode = null;
      }

      if (this.triggerTarget) {
        this.triggerTarget.removeEventListener("click", this.toggle);
      }
    }

    loadConfiguration() {
      const configElement = this.shadowRoot.getElementById("inspect-preview-configuration");
      if (!configElement) return;
      try {
        const config = JSON.parse(configElement.textContent);
        this.editUrlValue = config.editUrl || "";
        this.apiUrl = config.apiUrl || "";
        this.pageIdValue = config.pageId || 0;
      } catch (e) {
        console.warn("Inspect blocks: failed to parse configuration", e);
      }
    }

    toggle(event) {
      if (event) {
        event.preventDefault();
        event.stopPropagation();
      }

      if (this.inspectMode?.active) {
        this.deactivate();
      } else {
        this.activate();
      }
    }

    activate() {
      this.inspectMode = new window.WagtailInspectMode(document, {
        onBlockClick: (blockId) => {
          this.navigateToBlock(blockId);
          this.deactivate();
        },
        onEscape: () => {
          this.deactivate();
        },
      });
      this.inspectMode.activate();
      this.updateButtonState(true);
    }

    deactivate() {
      if (this.inspectMode) {
        this.inspectMode.deactivate();
        this.inspectMode = null;
      }
      this.updateButtonState(false);
    }

    updateButtonState(active) {
      if (!this.triggerTarget) return;

      this.triggerTarget.setAttribute("aria-pressed", active.toString());
      this.triggerTarget.classList.toggle("w-userbar__item--active", active);

      const icon = this.triggerTarget.querySelector(".icon-crosshairs");
      if (icon) {
        icon.style.color = active
          ? "var(--w-color-text-label-menus-active)"
          : "var(--w-color-icon-secondary)";
      }
    }

    async fetchAndAugment() {
      if (!this.apiUrl) return;
      try {
        const res = await fetch(this.apiUrl, {
          headers: { "X-Requested-With": "XMLHttpRequest" },
        });
        if (!res.ok) return;
        const { blocks } = await res.json();
        if (blocks) {
          window.WagtailInspectAugment?.augmentPreviewBlocks(blocks);
        }
      } catch {
        /* network / parse */
      }
    }

    navigateToBlock(blockId) {
      if (this.editUrlValue) {
        window.location.href = `${this.editUrlValue}#block-${blockId}-section`;
      }
    }
  }

  globalThis.WagtailInspectUserbar = {
    InspectController,
  };

  function tryAttach() {
    const userbarElement = document.querySelector("wagtail-userbar");
    if (!userbarElement?.shadowRoot) return false;

    const shadowRoot = userbarElement.shadowRoot;
    const controllerElement = shadowRoot.querySelector(
      '[data-controller="wagtail-inspect-userbar"]',
    );
    if (!controllerElement) return false;

    const controller = new InspectController(controllerElement, shadowRoot);
    controller.connect();
    return true;
  }

  function initialize() {
    if (tryAttach()) return;

    const observer = new MutationObserver(() => {
      if (tryAttach()) {
        observer.disconnect();
      }
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialize);
  } else {
    initialize();
  }
})();
