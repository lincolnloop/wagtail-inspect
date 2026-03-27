/**
 * Inspect mode: overlay highlight, hover/focus, click and Escape. Used from the
 * preview Stimulus controller and the userbar. Overlay tracks
 * getBoundingClientRect (with display:contents fallbacks); colors come from
 * parent/admin --w-color-* when available. Exposed as window.WagtailInspectMode.
 *
 * @param {Document} doc
 * @param {{ onBlockClick: function(string): void, onEscape: function(): void }} options
 */
class InspectMode {
  static DEFAULTS = {
    color: "#007D7E",
    labelColor: "#fff",
  };

  constructor(doc, { onBlockClick, onEscape }) {
    this.doc = doc;
    this.onBlockClick = onBlockClick;
    this.onEscape = onEscape;

    this._active = false;
    this._overlay = null;
    this._liveRegion = null;
    this._highlightedElement = null;
    this._overlayRafId = null;

    this._handleMouseOver = this._handleMouseOver.bind(this);
    this._handleLeave = this._handleLeave.bind(this);
    this._handleClick = this._handleClick.bind(this);
    this._handleKeyDown = this._handleKeyDown.bind(this);
    this._handleFocusIn = this._handleFocusIn.bind(this);
    this._handleResize = this._handleResize.bind(this);
    this._handleScroll = this._handleScroll.bind(this);
  }

  get active() {
    return this._active;
  }

  /** Enter/Space on admin document while a block is highlighted in the iframe. */
  activateHighlightedBlock(event) {
    if (!this._active || !this._highlightedElement) return;
    event.preventDefault();
    event.stopPropagation();
    this.onBlockClick(this._highlightedElement.dataset.blockId);
  }

  activate() {
    this._active = true;
    this._createOverlay();
    this._createLiveRegion();
    this._enableBlockAccessibility();

    this.doc.addEventListener("mouseover", this._handleMouseOver, true);
    this.doc.addEventListener("mouseout", this._handleLeave, true);
    this.doc.addEventListener("click", this._handleClick, true);
    this.doc.addEventListener("keydown", this._handleKeyDown, true);
    this.doc.addEventListener("focusin", this._handleFocusIn, true);
    this.doc.addEventListener("focusout", this._handleLeave, true);

    const win = this.doc.defaultView;
    if (win) {
      win.addEventListener("resize", this._handleResize);
    }
    this.doc.addEventListener("scroll", this._handleScroll, {
      capture: true,
      passive: true,
    });

    this._injectStyles();
    this._announce("Inspect mode on. Tab through blocks, press Enter to inspect.");
  }

  deactivate() {
    this._active = false;
    this._highlightedElement = null;

    this.doc.removeEventListener("mouseover", this._handleMouseOver, true);
    this.doc.removeEventListener("mouseout", this._handleLeave, true);
    this.doc.removeEventListener("click", this._handleClick, true);
    this.doc.removeEventListener("keydown", this._handleKeyDown, true);
    this.doc.removeEventListener("focusin", this._handleFocusIn, true);
    this.doc.removeEventListener("focusout", this._handleLeave, true);

    this.doc.removeEventListener("scroll", this._handleScroll, {
      capture: true,
      passive: true,
    });

    const win = this.doc.defaultView;
    if (win) {
      if (this._overlayRafId != null) {
        win.cancelAnimationFrame(this._overlayRafId);
        this._overlayRafId = null;
      }
      win.removeEventListener("resize", this._handleResize);
    }

    this._disableBlockAccessibility();
    this._removeStyles();
    this._removeOverlay();
    this._removeLiveRegion();
  }

  _findBlockElement(element) {
    return element.closest("[data-block-id]");
  }

  _handleMouseOver(event) {
    const blockElement = this._findBlockElement(event.target);
    if (blockElement) {
      this._highlight(blockElement);
    }
  }

  _handleLeave(event) {
    const blockElement = this._findBlockElement(event.target);
    const relatedBlock = event.relatedTarget ? this._findBlockElement(event.relatedTarget) : null;

    if (blockElement && blockElement !== relatedBlock) {
      this._unhighlight();
    }
  }

  _handleClick(event) {
    const blockElement = this._findBlockElement(event.target);
    if (blockElement) {
      event.preventDefault();
      event.stopPropagation();
      this.onBlockClick(blockElement.dataset.blockId);
    }
  }

  _handleKeyDown(event) {
    if (event.key === "Escape" && this._active) {
      this.onEscape();
      return;
    }

    if ((event.key === "Enter" || event.key === " ") && this._active) {
      const blockElement = this._findBlockElement(event.target) || this._highlightedElement;
      if (blockElement) {
        event.preventDefault();
        event.stopPropagation();
        this.onBlockClick(blockElement.dataset.blockId);
      }
    }
  }

  _handleFocusIn(event) {
    const blockElement = this._findBlockElement(event.target);
    if (blockElement) {
      this._highlight(blockElement);
    }
  }

  _scheduleOverlayReposition() {
    if (!this._highlightedElement) return;
    const win = this.doc.defaultView;
    if (!win) return;
    if (this._overlayRafId != null) return;
    this._overlayRafId = win.requestAnimationFrame(() => {
      this._overlayRafId = null;
      if (this._highlightedElement && this._overlay) {
        this._positionOverlay(this._highlightedElement);
      }
    });
  }

  _handleResize() {
    this._scheduleOverlayReposition();
  }

  _handleScroll() {
    this._scheduleOverlayReposition();
  }

  _createOverlay() {
    const overlay = this.doc.createElement("div");
    overlay.id = "wagtail-inspect-overlay";
    overlay.setAttribute("aria-hidden", "true");

    const label = this.doc.createElement("div");
    label.id = "wagtail-inspect-label";
    overlay.appendChild(label);

    this.doc.body.appendChild(overlay);
    this._overlay = overlay;
  }

  _removeOverlay() {
    this._overlay?.remove();
    this._overlay = null;
  }

  _highlight(element) {
    if (this._highlightedElement === element) return;
    if (!this._overlay) return;

    this._highlightedElement = element;
    this._positionOverlay(element);
    this._overlay.style.display = "block";

    const blockLabel = this._buildBreadcrumbLabel(element);

    const label = this._overlay.querySelector("#wagtail-inspect-label");
    if (label) {
      label.textContent = blockLabel;
    }

    this._announce(blockLabel);
  }

  /** One ancestor segment when nested, e.g. "Two Column › Hero". */
  _buildBreadcrumbLabel(element) {
    const label = element.dataset.blockLabel || "Block";
    const ancestor = element.parentElement?.closest("[data-block-id]");
    if (!ancestor) return label;
    return `${ancestor.dataset.blockLabel || "Block"} \u203A ${label}`;
  }

  _unhighlight() {
    this._highlightedElement = null;
    if (this._overlay) {
      this._overlay.style.display = "none";
    }
  }

  _positionOverlay(element) {
    if (!this._overlay) return;

    const win = this.doc.defaultView;
    if (!win) return;

    const pad = 3;
    const minSize = 5;
    const rect = this._getBlockRect(element);

    const viewW = win.innerWidth;
    const viewH = win.innerHeight;

    let padLeft = rect.left - pad;
    let padRight = rect.right + pad;
    let padTop = rect.top - pad;
    let padBottom = rect.bottom + pad;

    if (rect.width < minSize) {
      const midX = rect.left + rect.width / 2;
      padLeft = midX - minSize / 2;
      padRight = midX + minSize / 2;
    }
    if (rect.height < minSize) {
      const midY = rect.top + rect.height / 2;
      padTop = midY - minSize / 2;
      padBottom = midY + minSize / 2;
    }

    const clampLeft = Math.max(padLeft, 0);
    const clampRight = Math.min(padRight, viewW);
    const clampTop = Math.max(padTop, 0);
    const clampBottom = Math.min(padBottom, viewH);

    if (clampRight <= clampLeft || clampBottom <= clampTop) return;

    const left = clampLeft;
    const top = clampTop;
    const width = Math.max(clampRight - clampLeft, minSize);
    const height = Math.max(clampBottom - clampTop, minSize);

    this._overlay.style.top = `${top}px`;
    this._overlay.style.left = `${left}px`;
    this._overlay.style.width = `${width}px`;
    this._overlay.style.height = `${height}px`;

    const label = this._overlay.querySelector("#wagtail-inspect-label");
    if (label) {
      const topClip = Math.max(0, -padTop);
      if (topClip > 0) {
        label.style.top = "-1.5px";
        label.style.borderRadius = "0 0 3px 3px";
      } else {
        label.style.top = "";
      }
    }
  }

  /**
   * Block rect: element box, else union of direct element children (avoids Range
   * blowing up on display:contents markdown), else Range over contents.
   */
  _getBlockRect(element) {
    const rect = element.getBoundingClientRect();
    if (rect.width > 0 || rect.height > 0) return rect;

    const union = this._unionDirectChildElementRects(element);
    if (union) return union;

    const range = this.doc.createRange();
    range.selectNodeContents(element);
    return range.getBoundingClientRect();
  }

  /** @returns {DOMRect | null} */
  _unionDirectChildElementRects(container) {
    let minL = Infinity;
    let minT = Infinity;
    let maxR = -Infinity;
    let maxB = -Infinity;
    let any = false;

    for (const node of container.childNodes) {
      if (node.nodeType !== Node.ELEMENT_NODE) continue;
      const r = node.getBoundingClientRect();
      if (r.width <= 0 && r.height <= 0) continue;
      any = true;
      minL = Math.min(minL, r.left);
      minT = Math.min(minT, r.top);
      maxR = Math.max(maxR, r.right);
      maxB = Math.max(maxB, r.bottom);
    }

    if (!any) return null;

    const w = maxR - minL;
    const h = maxB - minT;
    const Ctor = this.doc.defaultView?.DOMRect ?? DOMRect;
    return new Ctor(minL, minT, w, h);
  }

  _getBlockElements() {
    return this.doc.querySelectorAll("[data-block-id]");
  }

  _enableBlockAccessibility() {
    for (const el of this._getBlockElements()) {
      el.setAttribute("role", "button");
      el.setAttribute("tabindex", "0");
      const blockLabel = el.dataset.blockLabel || "Block";
      el.setAttribute("aria-label", `Inspect ${blockLabel} block`);
    }
  }

  _disableBlockAccessibility() {
    for (const el of this._getBlockElements()) {
      el.removeAttribute("role");
      el.removeAttribute("tabindex");
      el.removeAttribute("aria-label");
    }
  }

  _createLiveRegion() {
    const region = this.doc.createElement("div");
    region.id = "wagtail-inspect-live";
    region.setAttribute("aria-live", "polite");
    region.setAttribute("aria-atomic", "true");
    this.doc.body.appendChild(region);
    this._liveRegion = region;
  }

  _removeLiveRegion() {
    this._liveRegion?.remove();
    this._liveRegion = null;
  }

  _announce(message) {
    if (!this._liveRegion) return;
    this._liveRegion.textContent = "";
    const raf = this.doc.defaultView?.requestAnimationFrame || requestAnimationFrame;
    raf(() => {
      if (this._liveRegion) {
        this._liveRegion.textContent = message;
      }
    });
  }

  /** Resolve --w-color-* from parent/admin document when available. */
  _resolveColors() {
    const { color, labelColor } = InspectMode.DEFAULTS;
    const result = { color, labelColor };

    try {
      const win = this.doc.defaultView;
      const parentDoc = win?.parent !== win ? win.parent.document : null;
      const sourceDoc = parentDoc || this.doc;
      const styles = sourceDoc.defaultView.getComputedStyle(sourceDoc.documentElement);

      const secondary = styles.getPropertyValue("--w-color-secondary").trim();
      const textButton = styles.getPropertyValue("--w-color-text-button").trim();

      if (secondary) result.color = secondary;
      if (textButton) result.labelColor = textButton;
    } catch {
      /* cross-origin parent or no computed styles */
    }

    return result;
  }

  _injectStyles() {
    this.doc.documentElement.classList.add("wagtail-inspect-active");

    if (this.doc.getElementById("wagtail-inspect-styles")) return;

    const colors = this._resolveColors();

    const style = this.doc.createElement("style");
    style.id = "wagtail-inspect-styles";
    style.textContent = `
      :root {
        --wagtail-inspect-color: ${colors.color};
        --wagtail-inspect-bg: color-mix(in srgb, ${colors.color} 15%, transparent);
        --wagtail-inspect-label-color: ${colors.labelColor};
      }
    `;
    this.doc.head.appendChild(style);
  }

  _removeStyles() {
    this.doc.documentElement.classList.remove("wagtail-inspect-active");
    this.doc.getElementById("wagtail-inspect-styles")?.remove();
  }
}

window.WagtailInspectMode = InspectMode;
