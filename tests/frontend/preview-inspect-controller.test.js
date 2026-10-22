import { describe, it, expect, beforeAll, afterEach, spyOn } from "bun:test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import "./setup.js";
import { WAGTAIL_INSPECT_JS_DIR } from "./static-dir.js";

beforeAll(() => {
  const previewJs = readFileSync(
    resolve(WAGTAIL_INSPECT_JS_DIR, "preview-inspect-controller.js"),
    "utf-8",
  );
  // eslint-disable-next-line no-new-func
  new Function("window", previewJs)(globalThis);
});

function PreviewInspectController() {
  return globalThis.WagtailInspectPreview.PreviewInspectController;
}

/**
 * Minimal document stub for injectAugmentScript duplicate-guard tests.
 * Happy-dom throws when appending external <script src>, so we avoid it here.
 */
function createAugmentScriptDoc() {
  const scripts = [];
  let scriptAppendCount = 0;
  return {
    scriptAppendCount: () => scriptAppendCount,
    querySelector(sel) {
      const m = /^script\[src="(.+)"\]$/.exec(sel);
      if (!m) return null;
      const want = m[1];
      return scripts.find((s) => s.src === want) ?? null;
    },
    createElement(tag) {
      const el = {
        tagName: String(tag).toUpperCase(),
        onload: null,
        onerror: null,
        _src: "",
      };
      Object.defineProperty(el, "src", {
        configurable: true,
        get() {
          return el._src;
        },
        set(v) {
          el._src = v;
        },
      });
      return el;
    },
    head: {
      appendChild(node) {
        if (node.tagName === "SCRIPT") {
          scriptAppendCount += 1;
          scripts.push(node);
          queueMicrotask(() => node.onload?.());
        }
        return node;
      },
    },
  };
}

describe("PreviewInspectController.getPageId", () => {
  it("reads numeric id from /pages/{id}/ paths", () => {
    const C = PreviewInspectController();
    const orig = window.location.pathname;
    try {
      Object.defineProperty(window.location, "pathname", {
        configurable: true,
        value: "/cms/pages/42/edit/preview/",
      });
      expect(C.prototype.getPageId.call({})).toBe("42");
    } finally {
      Object.defineProperty(window.location, "pathname", {
        configurable: true,
        value: orig,
      });
    }
  });
});

describe("PreviewInspectController.injectAugmentScript", () => {
  it("skips when augment URL is missing", async () => {
    const C = PreviewInspectController();
    const prev = globalThis.wagtailInspectConfig;
    globalThis.wagtailInspectConfig = {};
    const doc = document.implementation.createHTMLDocument("t");
    try {
      await C.prototype.injectAugmentScript.call({}, doc);
      expect(doc.querySelectorAll("script").length).toBe(0);
    } finally {
      globalThis.wagtailInspectConfig = prev;
    }
  });

  it("does not inject the same script src twice", async () => {
    const C = PreviewInspectController();
    const prev = globalThis.wagtailInspectConfig;
    const url = "https://example.test/wagtail-inspect/augment.js";
    globalThis.wagtailInspectConfig = { augmentScriptUrl: url };
    const doc = createAugmentScriptDoc();
    try {
      await C.prototype.injectAugmentScript.call({}, doc);
      await C.prototype.injectAugmentScript.call({}, doc);
      expect(doc.scriptAppendCount()).toBe(1);
      expect(doc.querySelector(`script[src="${url}"]`)).not.toBeNull();
    } finally {
      globalThis.wagtailInspectConfig = prev;
    }
  });
});

function previewPanel({ proxy = false } = {}) {
  const panel = document.createElement("div");
  panel.setAttribute("data-controller", "w-preview");
  panel.setAttribute("data-w-preview-proxy-class", "w-preview__proxy");
  const current = document.createElement("iframe");
  current.id = "w-preview-iframe";
  current.className = "w-preview__iframe";
  current.setAttribute("data-w-preview-target", "iframe");
  panel.appendChild(current);
  let proxyIframe = null;
  if (proxy) {
    // What Wagtail's reloadIframe() inserts: a clone without id, with the proxy class.
    proxyIframe = current.cloneNode();
    proxyIframe.removeAttribute("id");
    proxyIframe.classList.add("w-preview__proxy");
    current.insertAdjacentElement("afterend", proxyIframe);
  }
  document.body.appendChild(panel);
  return { panel, current, proxyIframe };
}

describe("PreviewInspectController.getPreviewIframe", () => {
  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("returns the current iframe while a proxy iframe is loading", () => {
    const { panel, current } = previewPanel({ proxy: true });
    const C = PreviewInspectController();
    expect(C.prototype.getPreviewIframe.call({ element: panel })).toBe(current);
  });

  it("returns the swapped-in iframe once Wagtail promotes the proxy", () => {
    const { panel, current, proxyIframe } = previewPanel({ proxy: true });
    current.remove();
    proxyIframe.id = "w-preview-iframe";
    proxyIframe.classList.remove("w-preview__proxy");
    const C = PreviewInspectController();
    expect(C.prototype.getPreviewIframe.call({ element: panel })).toBe(proxyIframe);
  });
});

describe("PreviewInspectController.setupIframeLoadAction", () => {
  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("listens for w-preview:loaded instead of the iframe load event on swapping previews", () => {
    const { panel, current } = previewPanel();
    const C = PreviewInspectController();
    const ctx = Object.create(C.prototype);
    ctx.element = panel;
    ctx.handleIframeLoad = () => {};
    ctx.setupIframeLoadAction();
    expect(panel.getAttribute("data-action")).toContain(
      "w-preview:loaded->preview-inspect#handleIframeLoad",
    );
    expect(current.getAttribute("data-action") || "").not.toContain("preview-inspect");
  });

  it("keeps the iframe load action on previews without a proxy class", () => {
    const { panel, current } = previewPanel();
    panel.removeAttribute("data-w-preview-proxy-class");
    const C = PreviewInspectController();
    const ctx = Object.create(C.prototype);
    ctx.element = panel;
    ctx.handleIframeLoad = () => {};
    ctx.setupIframeLoadAction();
    expect(current.getAttribute("data-action")).toContain("load->preview-inspect#handleIframeLoad");
  });
});

describe("preview panel observer", () => {
  afterEach(() => {
    document.body.innerHTML = "";
  });

  const flushObserver = () => new Promise((resolve) => setTimeout(resolve, 0));

  it("adds preview-inspect to a preview panel added to the page", async () => {
    const panel = document.createElement("div");
    panel.setAttribute("data-controller", "w-preview");
    document.body.appendChild(panel);
    await flushObserver();
    expect(panel.getAttribute("data-controller")).toBe("w-preview preview-inspect");
  });

  it("adds preview-inspect to a preview panel nested in an added element", async () => {
    const wrapper = document.createElement("section");
    const panel = document.createElement("div");
    panel.setAttribute("data-controller", "w-preview");
    wrapper.appendChild(panel);
    document.body.appendChild(wrapper);
    await flushObserver();
    expect(panel.getAttribute("data-controller")).toBe("w-preview preview-inspect");
  });

  it("does not query the whole document when unrelated nodes are added", async () => {
    const queries = spyOn(document, "querySelectorAll");
    document.body.appendChild(document.createTextNode("typing"));
    document.body.appendChild(document.createElement("p"));
    await flushObserver();
    expect(queries).not.toHaveBeenCalled();
    queries.mockRestore();
  });
});

describe("PreviewInspectController.navigateToBlock", () => {
  const originalMatchMedia = globalThis.matchMedia;

  afterEach(() => {
    globalThis.matchMedia = originalMatchMedia;
    document.body.innerHTML = "";
  });

  function navigate({ reduceMotion }) {
    globalThis.matchMedia = () => ({ matches: reduceMotion });
    const section = document.createElement("section");
    section.id = "block-abc-section";
    const scrolls = [];
    section.scrollIntoView = (options) => scrolls.push(options.behavior);
    document.body.appendChild(section);
    PreviewInspectController().prototype.navigateToBlock.call({}, "abc");
    return { section, scrolls };
  }

  it("scrolls smoothly and flashes once the scroll ends", () => {
    const { section, scrolls } = navigate({ reduceMotion: false });
    expect(scrolls).toEqual(["smooth"]);
    expect(section.classList.contains("wagtail-inspect-flash")).toBe(false);
    section.dispatchEvent(new Event("scrollend"));
    expect(section.classList.contains("wagtail-inspect-flash")).toBe(true);
  });

  it("jumps without smooth scrolling under reduced motion", () => {
    const { scrolls } = navigate({ reduceMotion: true });
    expect(scrolls).toEqual(["instant"]);
  });
});
