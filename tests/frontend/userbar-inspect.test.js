import { describe, it, expect, beforeAll, mock } from "bun:test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import "./setup.js";
import { WAGTAIL_INSPECT_JS_DIR } from "./static-dir.js";

beforeAll(() => {
  const userbarJs = readFileSync(resolve(WAGTAIL_INSPECT_JS_DIR, "userbar-inspect.js"), "utf-8");
  // eslint-disable-next-line no-new-func
  new Function(userbarJs)();
});

function UserbarInspectController() {
  return globalThis.WagtailInspectUserbar.InspectController;
}

describe("UserbarInspectController", () => {
  it("loadConfiguration parses json_script in the shadow root", () => {
    const C = UserbarInspectController();
    const host = document.createElement("div");
    const shadow = host.attachShadow({ mode: "open" });
    const script = document.createElement("script");
    script.id = "inspect-preview-configuration";
    script.type = "application/json";
    script.textContent = JSON.stringify({
      editUrl: "/cms/pages/3/edit/",
      apiUrl: "/cms/wagtail-inspect/api/page/3/",
      pageId: 3,
    });
    shadow.appendChild(script);

    const ctrl = new C(host, shadow);
    ctrl.loadConfiguration();
    expect(ctrl.editUrlValue).toBe("/cms/pages/3/edit/");
    expect(ctrl.apiUrl).toBe("/cms/wagtail-inspect/api/page/3/");
    expect(ctrl.pageIdValue).toBe(3);
  });

  it("fetchAndAugment requests apiUrl and forwards blocks to augment", async () => {
    const C = UserbarInspectController();
    const prevFetch = globalThis.fetch;
    const prevAugment = globalThis.WagtailInspectAugment;
    globalThis.WagtailInspectAugment = { augmentPreviewBlocks: mock(() => {}) };

    const fetchMock = mock(() =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            blocks: { u1: { type: "t", label: "T", children: [] } },
          }),
      }),
    );
    globalThis.fetch = fetchMock;

    try {
      const host = document.createElement("div");
      const shadow = host.attachShadow({ mode: "open" });
      const ctrl = new C(host, shadow);
      ctrl.apiUrl = "https://example.test/api/1/";
      await ctrl.fetchAndAugment();

      expect(fetchMock).toHaveBeenCalledWith("https://example.test/api/1/", {
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      expect(globalThis.WagtailInspectAugment.augmentPreviewBlocks).toHaveBeenCalled();
      const arg = globalThis.WagtailInspectAugment.augmentPreviewBlocks.mock.calls[0][0];
      expect(arg.u1.type).toBe("t");
    } finally {
      globalThis.fetch = prevFetch;
      globalThis.WagtailInspectAugment = prevAugment;
    }
  });

  it("is exclusive with other block modes such as live comments", () => {
    const C = UserbarInspectController();
    const prevMode = globalThis.WagtailInspectMode;
    globalThis.WagtailInspectMode = class {
      constructor() {
        this.active = false;
      }
      activate() {
        this.active = true;
      }
      deactivate() {
        this.active = false;
      }
    };
    const announced = [];
    const listen = (event) => announced.push(event.detail.source);
    document.addEventListener("wagtail-block-ids:mode-on", listen);

    try {
      const host = document.createElement("div");
      const ctrl = new C(host, host.attachShadow({ mode: "open" }));
      ctrl.connect();

      ctrl.activate();
      expect(announced).toEqual(["wagtail-inspect"]);
      expect(ctrl.inspectMode.active).toBe(true);

      const other = (source) =>
        document.dispatchEvent(
          new CustomEvent("wagtail-block-ids:mode-on", { detail: { source } }),
        );
      other("wagtail-inspect");
      expect(ctrl.inspectMode.active).toBe(true);
      other("wagtail-live-comments");
      expect(ctrl.inspectMode).toBeNull();

      ctrl.disconnect();
    } finally {
      document.removeEventListener("wagtail-block-ids:mode-on", listen);
      globalThis.WagtailInspectMode = prevMode;
    }
  });
});
