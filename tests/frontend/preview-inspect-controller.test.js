import { describe, it, expect, beforeAll } from "bun:test";
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
