/**
 * Stimulus controller: inspect mode in the admin preview iframe (InspectMode +
 * API block map + inspect-augment.js). Requires window.WagtailInspectPreviewHelpers.
 * @see https://docs.wagtail.org/en/stable/extending/extending_client_side.html
 */
const { findEditorBlock, expandCollapsedAncestors, flashHighlight } =
  window.WagtailInspectPreviewHelpers;

class PreviewInspectController extends window.StimulusModule.Controller {
  connect() {
    this.inspectModeActive = false;
    this.inspectMode = null;
    this.boundHandleKeyDown = this.handleKeyDown.bind(this);
    this.injectInspectButton();
    this.setupIframeLoadAction();
  }

  disconnect() {
    if (this.blockObserver) {
      this.blockObserver.disconnect();
      this.blockObserver = null;
    }
    this.deactivateInspectMode();
  }

  toggleInspectMode() {
    if (this.inspectModeActive) {
      this.deactivateInspectMode();
    } else {
      this.activateInspectMode();
    }
  }

  activateInspectMode() {
    const previewDoc = this.getPreviewDocument();
    if (!previewDoc) {
      console.warn("Could not access preview document");
      return;
    }

    this.inspectMode = this._createInspectMode(previewDoc);
    this.inspectMode.activate();

    document.addEventListener("keydown", this.boundHandleKeyDown);

    this.inspectModeActive = true;
    this.updateButtonState();
  }

  deactivateInspectMode() {
    if (this.inspectMode) {
      this.inspectMode.deactivate();
      this.inspectMode = null;
    }

    document.removeEventListener("keydown", this.boundHandleKeyDown);

    this.inspectModeActive = false;
    this.updateButtonState();
  }

  _createInspectMode(previewDoc) {
    return new window.WagtailInspectMode(previewDoc, {
      onBlockClick: (blockId) => {
        this.navigateToBlock(blockId);
        this.deactivateInspectMode();
      },
      onEscape: () => {
        this.deactivateInspectMode();
      },
    });
  }

  handleKeyDown(event) {
    if (!this.inspectModeActive) return;

    if (event.key === "Escape") {
      this.deactivateInspectMode();
      return;
    }

    if (event.key === "Enter" || event.key === " ") {
      this.inspectMode?.activateHighlightedBlock(event);
    }
  }

  injectInspectButton() {
    const sizesContainer = this.element.querySelector(".w-preview__sizes");
    if (sizesContainer && !sizesContainer.querySelector("[data-preview-inspect-button]")) {
      const button = this.createInspectButton();
      sizesContainer.appendChild(button);
      this.inspectButton = button;
    }
  }

  createInspectButton() {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "w-preview__size-button";
    button.setAttribute("data-preview-inspect-button", "");
    button.setAttribute("title", "Inspect blocks (Esc to cancel)");
    button.setAttribute("aria-label", "Inspect preview blocks");
    button.setAttribute("aria-pressed", "false");

    button.innerHTML = `
      <svg class="icon icon-crosshairs" aria-hidden="true">
        <use href="#icon-crosshairs"></use>
      </svg>
    `;

    button.setAttribute("data-action", "click->preview-inspect#toggleInspectMode");

    return button;
  }

  updateButtonState() {
    if (!this.inspectButton) return;
    this.inspectButton.setAttribute("aria-pressed", this.inspectModeActive.toString());
    this.inspectButton.classList.toggle("w-preview__size-button--selected", this.inspectModeActive);
  }

  getPageId() {
    const match = window.location.pathname.match(
      window.WagtailInspectPreviewHelpers.PAGE_ID_IN_PATH_RE,
    );
    return match?.[1] ?? null;
  }

  injectAugmentScript(doc) {
    return new Promise((resolve) => {
      const url = window.wagtailInspectConfig?.augmentScriptUrl;
      if (!url) return resolve();
      if (doc.querySelector(`script[src="${url}"]`)) return resolve();
      const script = doc.createElement("script");
      script.src = url;
      script.onload = resolve;
      script.onerror = resolve;
      (doc.head || doc.documentElement).appendChild(script);
    });
  }

  async fetchAndAugment() {
    const config = window.wagtailInspectConfig;
    const pageId = this.getPageId();
    if (!config || !pageId) return;

    const res = await fetch(`${config.apiBase}${pageId}/`, {
      headers: { "X-Requested-With": "XMLHttpRequest" },
    });
    if (!res.ok) return;
    const { blocks } = await res.json();
    if (!blocks) return;

    const previewDoc = this.getPreviewDocument();
    if (!previewDoc) return;

    await this.injectAugmentScript(previewDoc);
    previewDoc.defaultView?.WagtailInspectAugment?.augmentPreviewBlocks(blocks);
  }

  getPreviewIframe() {
    return (
      this.element.querySelector('[data-w-preview-target="iframe"]') ||
      this.element.querySelector(".w-preview__iframe") ||
      this.element.querySelector("#w-preview-iframe")
    );
  }

  getPreviewDocument() {
    const iframe = this.getPreviewIframe();
    if (!iframe) return null;

    try {
      return iframe.contentDocument || iframe.contentWindow?.document;
    } catch (e) {
      console.error("Cannot access iframe document:", e);
      return null;
    }
  }

  setupIframeLoadAction() {
    const iframe = this.getPreviewIframe();
    if (iframe) {
      this._attachIframeLoadListener(iframe);
      return;
    }

    const observer = new MutationObserver(() => {
      const iframe = this.getPreviewIframe();
      if (iframe) {
        observer.disconnect();
        this._attachIframeLoadListener(iframe);
      }
    });
    observer.observe(this.element, { childList: true, subtree: true });
  }

  _attachIframeLoadListener(iframe) {
    const existingActions = iframe.getAttribute("data-action") || "";
    if (!existingActions.includes("preview-inspect#handleIframeLoad")) {
      iframe.setAttribute(
        "data-action",
        `${existingActions} load->preview-inspect#handleIframeLoad`.trim(),
      );
    }

    try {
      const doc = iframe.contentDocument;
      if (doc && doc.readyState === "complete" && doc.body) {
        this.handleIframeLoad();
      }
    } catch {
      /* cross-origin or iframe not ready */
    }
  }

  async handleIframeLoad() {
    this.shouldReactivateInspect = this.inspectModeActive;

    if (this.inspectMode) {
      this.inspectMode.deactivate();
      this.inspectMode = null;
    }

    if (this.blockObserver) {
      this.blockObserver.disconnect();
      this.blockObserver = null;
    }

    await this.fetchAndAugment().catch(() => {});
    this.waitForBlocks();
  }

  waitForBlocks() {
    const previewDoc = this.getPreviewDocument();
    if (!previewDoc || !previewDoc.body) return;

    if (previewDoc.querySelector("[data-block-id]")) {
      this.onBlocksReady();
      return;
    }

    this.blockObserver = new MutationObserver(() => {
      if (previewDoc.querySelector("[data-block-id]")) {
        this.blockObserver.disconnect();
        this.blockObserver = null;
        this.onBlocksReady();
      }
    });

    this.blockObserver.observe(previewDoc.body, {
      childList: true,
      subtree: true,
    });
  }

  onBlocksReady() {
    if (this.shouldReactivateInspect) {
      this.shouldReactivateInspect = false;
      requestAnimationFrame(() => {
        const previewDoc = this.getPreviewDocument();
        if (!previewDoc) {
          this.inspectModeActive = false;
          this.updateButtonState();
          return;
        }
        this.inspectMode = this._createInspectMode(previewDoc);
        this.inspectMode.activate();
      });
    }
  }

  navigateToBlock(blockId) {
    const anchor = `#block-${blockId}-section`;
    window.history.pushState(null, "", anchor);

    const blockElement = findEditorBlock(blockId);
    if (blockElement) {
      expandCollapsedAncestors(blockElement);
      blockElement.scrollIntoView({ behavior: "smooth" });
      requestAnimationFrame(() => flashHighlight(blockElement));
    }
  }
}

globalThis.WagtailInspectPreview = {
  PreviewInspectController,
};

window.wagtail.app.register("preview-inspect", PreviewInspectController);

function attachToExistingPreviewController() {
  const previewPanels = document.querySelectorAll('[data-controller*="w-preview"]');

  previewPanels.forEach((panel) => {
    const controllers = panel.getAttribute("data-controller") || "";

    if (!controllers.includes("preview-inspect")) {
      panel.setAttribute("data-controller", `${controllers} preview-inspect`.trim());
    }
  });
}

const observer = new MutationObserver((mutations) => {
  for (const mutation of mutations) {
    if (mutation.addedNodes.length) {
      attachToExistingPreviewController();
    }
  }
});

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    attachToExistingPreviewController();
    observer.observe(document.body, { childList: true, subtree: true });
  });
} else {
  attachToExistingPreviewController();
  observer.observe(document.body, { childList: true, subtree: true });
}

if (document.readyState === "complete") {
  window.WagtailInspectPreviewHelpers.scrollToHashBlock();
} else {
  window.addEventListener("load", () => window.WagtailInspectPreviewHelpers.scrollToHashBlock(), {
    once: true,
  });
}
