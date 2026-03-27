import { describe, it, expect, afterEach, mock, jest, spyOn } from "bun:test";

// WagtailInspectMode is set on globalThis by setup.js
// which loads inspect-core.js as a classic browser script.

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function createMode(overrides = {}) {
  return new WagtailInspectMode(document, {
    onBlockClick: mock(),
    onEscape: mock(),
    ...overrides,
  });
}

function blockEl(id = "uuid-1", label = "My Block") {
  const el = document.createElement("div");
  el.setAttribute("data-block-id", id);
  el.setAttribute("data-block-label", label);
  return el;
}

// ---------------------------------------------------------------------------
// InspectMode
// ---------------------------------------------------------------------------

describe("InspectMode", () => {
  let mode;

  afterEach(() => {
    if (mode) {
      mode.deactivate();
      mode = null;
    }
    // Remove any stray block elements added to the body during tests.
    document.body.querySelectorAll("[data-block-id]").forEach((el) => el.remove());
  });

  // --- activate() ---

  describe("activate()", () => {
    it("injects the overlay element", () => {
      mode = createMode();
      mode.activate();
      expect(document.getElementById("wagtail-inspect-overlay")).not.toBeNull();
    });

    it("injects a <style> element", () => {
      mode = createMode();
      mode.activate();
      expect(document.getElementById("wagtail-inspect-styles")).not.toBeNull();
    });

    it("injects an ARIA live region", () => {
      mode = createMode();
      mode.activate();
      const region = document.getElementById("wagtail-inspect-live");
      expect(region).not.toBeNull();
      expect(region.getAttribute("aria-live")).toBe("polite");
      expect(region.getAttribute("aria-atomic")).toBe("true");
    });

    it("sets active to true", () => {
      mode = createMode();
      mode.activate();
      expect(mode.active).toBe(true);
    });

    it("adds role and tabindex to existing block elements", () => {
      const el = blockEl();
      document.body.appendChild(el);
      mode = createMode();
      mode.activate();
      expect(el.getAttribute("role")).toBe("button");
      expect(el.getAttribute("tabindex")).toBe("0");
    });
  });

  // --- deactivate() ---

  describe("deactivate()", () => {
    it("removes the overlay", () => {
      mode = createMode();
      mode.activate();
      mode.deactivate();
      expect(document.getElementById("wagtail-inspect-overlay")).toBeNull();
    });

    it("removes the style element", () => {
      mode = createMode();
      mode.activate();
      mode.deactivate();
      expect(document.getElementById("wagtail-inspect-styles")).toBeNull();
    });

    it("removes the live region", () => {
      mode = createMode();
      mode.activate();
      mode.deactivate();
      expect(document.getElementById("wagtail-inspect-live")).toBeNull();
    });

    it("sets active to false", () => {
      mode = createMode();
      mode.activate();
      mode.deactivate();
      expect(mode.active).toBe(false);
    });

    it("removes role and tabindex from block elements", () => {
      const el = blockEl();
      document.body.appendChild(el);
      mode = createMode();
      mode.activate();
      mode.deactivate();
      expect(el.getAttribute("role")).toBeNull();
      expect(el.getAttribute("tabindex")).toBeNull();
    });

    it("is safe to call multiple times without throwing", () => {
      mode = createMode();
      mode.activate();
      mode.deactivate();
      expect(() => mode.deactivate()).not.toThrow();
    });
  });

  // --- _findBlockElement() ---

  describe("_findBlockElement()", () => {
    it("returns the element itself when it has data-block-id", () => {
      mode = createMode();
      const el = blockEl();
      document.body.appendChild(el);
      expect(mode._findBlockElement(el)).toBe(el);
    });

    it("returns the closest ancestor with data-block-id", () => {
      mode = createMode();
      const outer = blockEl("outer-uuid", "Outer");
      const inner = document.createElement("p");
      outer.appendChild(inner);
      document.body.appendChild(outer);
      expect(mode._findBlockElement(inner)).toBe(outer);
    });

    it("returns null when no ancestor has data-block-id", () => {
      mode = createMode();
      const el = document.createElement("span");
      document.body.appendChild(el);
      expect(mode._findBlockElement(el)).toBeNull();
      el.remove();
    });
  });

  // --- _resolveColors() ---

  describe("_resolveColors()", () => {
    it("returns the default color when --w-color-secondary is not set", () => {
      mode = createMode();
      const { color } = mode._resolveColors();
      expect(color).toBe(WagtailInspectMode.DEFAULTS.color);
    });

    it("returns the default labelColor when --w-color-text-button is not set", () => {
      mode = createMode();
      const { labelColor } = mode._resolveColors();
      expect(labelColor).toBe(WagtailInspectMode.DEFAULTS.labelColor);
    });
  });

  // --- _getBlockRect() ---

  describe("_getBlockRect()", () => {
    it("falls back to Range.getBoundingClientRect when there are no element children", () => {
      // jsdom does not implement Range.getBoundingClientRect, so we mock it.
      const mockRect = {
        x: 10,
        y: 20,
        width: 200,
        height: 80,
        top: 20,
        right: 210,
        bottom: 100,
        left: 10,
      };
      spyOn(document, "createRange").mockReturnValueOnce({
        selectNodeContents: mock(),
        getBoundingClientRect: mock(() => mockRect),
      });
      mode = createMode();
      const el = document.createElement("div");
      el.textContent = "Hello";
      document.body.appendChild(el);
      el.getBoundingClientRect = () => ({
        x: 0,
        y: 0,
        width: 0,
        height: 0,
        top: 0,
        right: 0,
        bottom: 0,
        left: 0,
      });
      const rect = mode._getBlockRect(el);
      expect(rect).toEqual(mockRect);
      el.remove();
      jest.restoreAllMocks();
    });

    it("unions direct child element rects when the root has zero size (display:contents)", () => {
      mode = createMode();
      const wrap = document.createElement("div");
      wrap.style.display = "contents";
      const p1 = document.createElement("p");
      const p2 = document.createElement("p");
      wrap.appendChild(p1);
      wrap.appendChild(p2);
      document.body.appendChild(wrap);
      wrap.getBoundingClientRect = () => ({
        x: 0,
        y: 0,
        width: 0,
        height: 0,
        top: 0,
        right: 0,
        bottom: 0,
        left: 0,
      });
      p1.getBoundingClientRect = () => ({
        x: 20,
        y: 10,
        width: 100,
        height: 30,
        top: 10,
        left: 20,
        right: 120,
        bottom: 40,
      });
      p2.getBoundingClientRect = () => ({
        x: 25,
        y: 50,
        width: 100,
        height: 40,
        top: 50,
        left: 25,
        right: 125,
        bottom: 90,
      });
      const rect = mode._getBlockRect(wrap);
      expect(rect.left).toBe(20);
      expect(rect.top).toBe(10);
      expect(rect.width).toBe(105);
      expect(rect.height).toBe(80);
      wrap.remove();
    });
  });

  // --- _positionOverlay() ---

  describe("_positionOverlay()", () => {
    it("uses viewport coordinates and does not add scroll offset", () => {
      mode = createMode();
      mode.activate();
      const prevScrollX = window.scrollX;
      const prevScrollY = window.scrollY;
      Object.defineProperty(window, "scrollX", { value: 400, configurable: true });
      Object.defineProperty(window, "scrollY", { value: 300, configurable: true });
      try {
        const el = blockEl();
        el.getBoundingClientRect = () => ({
          x: 10,
          y: 20,
          width: 40,
          height: 30,
          top: 20,
          right: 50,
          bottom: 50,
          left: 10,
        });
        document.body.appendChild(el);
        mode._positionOverlay(el);
        const overlay = document.getElementById("wagtail-inspect-overlay");
        expect(overlay.style.left).toBe("7px");
        expect(overlay.style.top).toBe("17px");
        el.remove();
      } finally {
        Object.defineProperty(window, "scrollX", { value: prevScrollX, configurable: true });
        Object.defineProperty(window, "scrollY", { value: prevScrollY, configurable: true });
      }
    });

    it("clamps to viewport when the rect starts in-viewport but extends far to the right", () => {
      mode = createMode();
      mode.activate();
      const vw = window.innerWidth;
      const el = blockEl();
      // Rect starts at the left of the viewport but extends 8000px to the right
      el.getBoundingClientRect = () => ({
        x: 0,
        y: 0,
        width: 8000,
        height: 100,
        top: 0,
        right: 8000,
        bottom: 100,
        left: 0,
      });
      document.body.appendChild(el);
      mode._positionOverlay(el);
      const overlay = document.getElementById("wagtail-inspect-overlay");
      const left = parseFloat(overlay.style.left);
      const width = parseFloat(overlay.style.width);
      expect(left).toBeGreaterThanOrEqual(0);
      expect(left + width).toBeLessThanOrEqual(vw);
      el.remove();
    });

    it("intersects a bogus wide rect with the viewport (Range/display:contents bug)", () => {
      mode = createMode();
      mode.activate();
      const el = blockEl();
      el.getBoundingClientRect = () => ({
        x: -6928,
        y: 214,
        width: 8039.52,
        height: 640.672,
        top: 214,
        left: -6928,
        right: -6928 + 8039.52,
        bottom: 214 + 640.672,
      });
      document.body.appendChild(el);
      mode._positionOverlay(el);
      const overlay = document.getElementById("wagtail-inspect-overlay");
      const left = parseFloat(overlay.style.left);
      const width = parseFloat(overlay.style.width);
      const vw = window.innerWidth;
      expect(left).toBeGreaterThanOrEqual(0);
      expect(left + width).toBeLessThanOrEqual(vw + 1);
      expect(width).toBeLessThanOrEqual(vw);
      el.remove();
    });

    it("pins the label to the overlay top when padded block top clips above the viewport", () => {
      mode = createMode();
      mode.activate();
      const el = blockEl();
      // Padded top = 0 - 3 = -3 → topClip > 0; overlay top clamped to 0. Label uses a fixed
      // inline offset (-1.5px) + bottom radii instead of computing from label height.
      el.getBoundingClientRect = () => ({
        x: 10,
        y: 0,
        width: 40,
        height: 50,
        top: 0,
        right: 50,
        bottom: 50,
        left: 10,
      });
      document.body.appendChild(el);
      mode._positionOverlay(el);
      const label = document.getElementById("wagtail-inspect-label");
      expect(label).not.toBeNull();
      expect(label.style.top).toBe("-1.5px");
      expect(label.style.borderRadius).toBe("0px 0px 3px 3px");
      el.remove();
    });

    it("clears inline label top when the padded block top is not above the viewport", () => {
      mode = createMode();
      mode.activate();
      const el = blockEl();
      el.getBoundingClientRect = () => ({
        x: 10,
        y: 20,
        width: 40,
        height: 30,
        top: 20,
        right: 50,
        bottom: 50,
        left: 10,
      });
      document.body.appendChild(el);
      mode._positionOverlay(el);
      const label = document.getElementById("wagtail-inspect-label");
      expect(label.style.top).toBe("");
      el.remove();
    });
  });

  describe("scroll reposition", () => {
    it("runs _positionOverlay on the next frame after document scroll when highlighted", async () => {
      mode = createMode();
      mode.activate();
      const el = blockEl();
      el.getBoundingClientRect = () => ({
        x: 0,
        y: 0,
        width: 40,
        height: 30,
        top: 0,
        right: 40,
        bottom: 30,
        left: 0,
      });
      document.body.appendChild(el);
      mode._highlightedElement = el;
      mode._overlay.style.display = "block";

      const spy = spyOn(mode, "_positionOverlay");
      document.dispatchEvent(new Event("scroll", { bubbles: true }));

      await new Promise((resolve) => {
        requestAnimationFrame(resolve);
      });

      expect(spy).toHaveBeenCalledWith(el);
      jest.restoreAllMocks();
      el.remove();
    });
  });

  // --- _buildBreadcrumbLabel() ---

  describe("_buildBreadcrumbLabel()", () => {
    it("returns the block label for a top-level block", () => {
      mode = createMode();
      const el = blockEl("uuid-1", "Hero");
      document.body.appendChild(el);
      expect(mode._buildBreadcrumbLabel(el)).toBe("Hero");
    });

    it('produces "Parent › Child" for a nested block', () => {
      mode = createMode();
      const outer = blockEl("uuid-outer", "Two Column");
      const inner = blockEl("uuid-inner", "Hero");
      outer.appendChild(inner);
      document.body.appendChild(outer);
      expect(mode._buildBreadcrumbLabel(inner)).toBe("Two Column \u203a Hero");
    });

    it("shows only the immediate parent for deeply nested blocks", () => {
      mode = createMode();
      const grandparent = blockEl("uuid-gp", "Section");
      const parent = blockEl("uuid-p", "Two Column");
      const child = blockEl("uuid-c", "Hero");
      grandparent.appendChild(parent);
      parent.appendChild(child);
      document.body.appendChild(grandparent);
      expect(mode._buildBreadcrumbLabel(child)).toBe("Two Column \u203a Hero");
    });

    it('falls back to "Block" when data-block-label is absent', () => {
      mode = createMode();
      const el = document.createElement("div");
      el.setAttribute("data-block-id", "uuid-1");
      document.body.appendChild(el);
      expect(mode._buildBreadcrumbLabel(el)).toBe("Block");
    });
  });

  // --- _enableBlockAccessibility() / _disableBlockAccessibility() ---

  describe("block accessibility", () => {
    it("_enableBlockAccessibility adds role, tabindex, and aria-label", () => {
      mode = createMode();
      const el = blockEl("uuid-1", "Text Block");
      document.body.appendChild(el);
      mode._enableBlockAccessibility();
      expect(el.getAttribute("role")).toBe("button");
      expect(el.getAttribute("tabindex")).toBe("0");
      expect(el.getAttribute("aria-label")).toBe("Inspect Text Block block");
    });

    it("_disableBlockAccessibility removes role, tabindex, and aria-label", () => {
      mode = createMode();
      const el = blockEl("uuid-1", "Text Block");
      document.body.appendChild(el);
      mode._enableBlockAccessibility();
      mode._disableBlockAccessibility();
      expect(el.getAttribute("role")).toBeNull();
      expect(el.getAttribute("tabindex")).toBeNull();
      expect(el.getAttribute("aria-label")).toBeNull();
    });
  });

  // --- Event handling ---

  describe("event handling", () => {
    it("calls onEscape when the Escape key is pressed", () => {
      const onEscape = mock();
      mode = createMode({ onEscape });
      mode.activate();
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
      expect(onEscape).toHaveBeenCalledTimes(1);
    });

    it("calls onBlockClick with the block ID when a block element is clicked", () => {
      const onBlockClick = mock();
      mode = createMode({ onBlockClick });
      mode.activate();
      const el = blockEl("click-uuid", "Text");
      document.body.appendChild(el);
      el.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      expect(onBlockClick).toHaveBeenCalledWith("click-uuid");
    });

    it("calls onBlockClick with Enter when a block element is focused", () => {
      const onBlockClick = mock();
      mode = createMode({ onBlockClick });
      mode.activate();
      const el = blockEl("enter-uuid", "Text");
      document.body.appendChild(el);
      el.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
      expect(onBlockClick).toHaveBeenCalledWith("enter-uuid");
    });

    it("clears highlight on focusout when focus leaves the block", () => {
      mode = createMode();
      mode.activate();
      const el = blockEl("focus-uuid", "Card");
      document.body.appendChild(el);

      mode._highlightedElement = el;

      const outside = document.createElement("span");
      document.body.appendChild(outside);
      el.dispatchEvent(new FocusEvent("focusout", { bubbles: true, relatedTarget: outside }));
      expect(mode._highlightedElement).toBeNull();
      outside.remove();
    });

    it("does not call onBlockClick on keydown when no block element is targeted", () => {
      const onBlockClick = mock();
      mode = createMode({ onBlockClick });
      mode.activate();
      const el = document.createElement("p");
      document.body.appendChild(el);
      el.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
      expect(onBlockClick).not.toHaveBeenCalled();
      el.remove();
    });
  });

  // --- CSS-in-JS removal ---

  describe("CSS-in-JS removal", () => {
    it("_createOverlay does not set inline cssText", () => {
      mode = createMode();
      mode.activate();
      const overlay = document.getElementById("wagtail-inspect-overlay");
      expect(overlay).not.toBeNull();
      expect(overlay.style.cssText).toBe("");
    });

    it("_injectStyles only writes :root custom properties", () => {
      mode = createMode();
      mode.activate();
      const style = document.getElementById("wagtail-inspect-styles");
      expect(style).not.toBeNull();
      expect(style.textContent).toContain("--wagtail-inspect-color");
      expect(style.textContent).not.toContain("cursor: crosshair");
      expect(style.textContent).not.toContain("focus-visible");
    });

    it("activate adds wagtail-inspect-active class to documentElement", () => {
      mode = createMode();
      mode.activate();
      expect(document.documentElement.classList.contains("wagtail-inspect-active")).toBe(true);
    });

    it("deactivate removes wagtail-inspect-active class from documentElement", () => {
      mode = createMode();
      mode.activate();
      mode.deactivate();
      expect(document.documentElement.classList.contains("wagtail-inspect-active")).toBe(false);
    });
  });

  // --- _announce() ---

  describe("_announce()", () => {
    it("schedules callback via doc.defaultView.requestAnimationFrame", () => {
      mode = createMode();
      mode.activate();
      const rafSpy = spyOn(document.defaultView, "requestAnimationFrame");
      mode._announce("test message");
      expect(rafSpy).toHaveBeenCalledTimes(1);
      jest.restoreAllMocks();
    });
  });

  // --- activateHighlightedBlock() ---

  describe("activateHighlightedBlock()", () => {
    it("calls onBlockClick for the currently highlighted element", () => {
      const onBlockClick = mock();
      mode = createMode({ onBlockClick });
      mode.activate();

      const el = blockEl("highlight-uuid", "Card");
      document.body.appendChild(el);
      // Set _highlightedElement directly — _highlight() calls _positionOverlay()
      // which uses Range.getBoundingClientRect that happy-dom does not implement.
      mode._highlightedElement = el;

      const fakeEvent = { preventDefault: mock(), stopPropagation: mock() };
      mode.activateHighlightedBlock(fakeEvent);
      expect(onBlockClick).toHaveBeenCalledWith("highlight-uuid");
    });

    it("does nothing when there is no highlighted element", () => {
      const onBlockClick = mock();
      mode = createMode({ onBlockClick });
      mode.activate();
      const fakeEvent = { preventDefault: mock(), stopPropagation: mock() };
      mode.activateHighlightedBlock(fakeEvent);
      expect(onBlockClick).not.toHaveBeenCalled();
    });
  });
});
