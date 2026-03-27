import { describe, it, expect } from "bun:test";

import "./setup.js";

const H = () => globalThis.WagtailInspectPreviewHelpers;

describe("WagtailInspectPreviewHelpers", () => {
  it("BLOCK_HASH_RE matches block section anchors", () => {
    const hash = "#block-a1b2c3d4-e5f6-7890-abcd-ef1234567890-section";
    const match = hash.match(H().BLOCK_HASH_RE);
    expect(match?.[1]).toBe("a1b2c3d4-e5f6-7890-abcd-ef1234567890");
  });

  it("PAGE_ID_IN_PATH_RE extracts id from admin paths", () => {
    const m = "/cms/pages/42/edit/preview/".match(H().PAGE_ID_IN_PATH_RE);
    expect(m?.[1]).toBe("42");
  });

  it("findEditorBlock resolves data-contentpath", () => {
    const el = document.createElement("div");
    el.setAttribute("data-contentpath", "uuid-1");
    document.body.appendChild(el);
    try {
      expect(H().findEditorBlock("uuid-1")).toBe(el);
    } finally {
      el.remove();
    }
  });

  it("expandPanelIfCollapsed reveals hidden w-panel__content", () => {
    const section = document.createElement("section");
    section.className = "w-panel";
    const content = document.createElement("div");
    content.className = "w-panel__content";
    content.setAttribute("hidden", "");
    const toggle = document.createElement("button");
    toggle.setAttribute("data-panel-toggle", "");
    toggle.setAttribute("aria-expanded", "false");
    section.appendChild(content);
    section.appendChild(toggle);

    H().expandPanelIfCollapsed(section);
    expect(content.hasAttribute("hidden")).toBe(false);
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
  });

  it("expandCollapsedAncestors expands own panel and ancestors", () => {
    const outer = document.createElement("section");
    outer.className = "w-panel";
    const outerContent = document.createElement("div");
    outerContent.className = "w-panel__content";
    outerContent.setAttribute("hidden", "");
    outer.appendChild(outerContent);

    const inner = document.createElement("section");
    inner.className = "w-panel";
    const innerContent = document.createElement("div");
    innerContent.className = "w-panel__content";
    innerContent.setAttribute("hidden", "");
    inner.appendChild(innerContent);

    const target = document.createElement("div");
    inner.appendChild(target);
    outer.appendChild(inner);
    document.body.appendChild(outer);

    try {
      H().expandCollapsedAncestors(target);
      expect(outerContent.hasAttribute("hidden")).toBe(false);
      expect(innerContent.hasAttribute("hidden")).toBe(false);
    } finally {
      outer.remove();
    }
  });
});
