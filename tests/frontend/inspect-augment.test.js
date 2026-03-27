import { describe, it, expect, afterEach } from "bun:test";

// WagtailInspectAugment from setup.js (inspect-augment.js)

function makeAnnotatedBlock(id, type = "hero", label = "Hero") {
  const el = document.createElement("div");
  el.setAttribute("data-block-id", id);
  el.setAttribute("data-block-type", type);
  el.setAttribute("data-block-label", label);
  return el;
}

afterEach(() => {
  document.body.innerHTML = "";
});

describe("augmentPreviewBlocks", () => {
  it("annotates unannotated list children under a parent block", () => {
    const parentId = "parent-uuid";
    const childId1 = "child-uuid-1";
    const childId2 = "child-uuid-2";

    const parent = makeAnnotatedBlock(parentId, "logo_cloud", "Logo Cloud");
    const c1 = document.createElement("li");
    const c2 = document.createElement("li");
    parent.appendChild(c1);
    parent.appendChild(c2);
    document.body.appendChild(parent);

    const blocks = {
      [parentId]: {
        type: "logo_cloud",
        label: "Logo Cloud",
        children: [childId1, childId2],
      },
      [childId1]: { type: "logo", label: "Logo", children: [] },
      [childId2]: { type: "logo", label: "Logo", children: [] },
    };

    WagtailInspectAugment.augmentPreviewBlocks(blocks);

    expect(c1.dataset.blockId).toBe(childId1);
    expect(c1.dataset.blockType).toBe("logo");
    expect(c2.dataset.blockId).toBe(childId2);
    expect(c2.dataset.blockType).toBe("logo");
  });

  it("skips parent when all children already have data-block-id in the DOM", () => {
    const parentId = "parent-uuid";
    const childId = "child-uuid";

    const parent = makeAnnotatedBlock(parentId, "grid", "Grid");
    const child = makeAnnotatedBlock(childId, "card", "Card");
    parent.appendChild(child);
    document.body.appendChild(parent);

    const blocks = {
      [parentId]: { type: "grid", label: "Grid", children: [childId] },
      [childId]: { type: "card", label: "Card", children: [] },
    };

    WagtailInspectAugment.augmentPreviewBlocks(blocks);

    expect(child.dataset.blockId).toBe(childId);
  });

  it("does not throw when parent element is missing from the DOM", () => {
    const blocks = {
      "missing-parent": { type: "x", label: "X", children: ["child-uuid"] },
      "child-uuid": { type: "y", label: "Y", children: [] },
    };
    expect(() => WagtailInspectAugment.augmentPreviewBlocks(blocks)).not.toThrow();
  });

  it("annotates exactly two sibling children (two-children regression)", () => {
    const parentId = "parent-uuid";
    const c1id = "child-1";
    const c2id = "child-2";

    const parent = makeAnnotatedBlock(parentId, "stats", "Stats");
    const c1 = document.createElement("div");
    c1.className = "stat-item";
    const c2 = document.createElement("div");
    c2.className = "stat-item";
    parent.appendChild(c1);
    parent.appendChild(c2);
    document.body.appendChild(parent);

    const blocks = {
      [parentId]: { type: "stats", label: "Stats", children: [c1id, c2id] },
      [c1id]: { type: "stat", label: "Stat", children: [] },
      [c2id]: { type: "stat", label: "Stat", children: [] },
    };

    WagtailInspectAugment.augmentPreviewBlocks(blocks);

    expect(c1.dataset.blockId).toBe(c1id);
    expect(c2.dataset.blockId).toBe(c2id);
  });

  it("does not annotate when DOM sibling count does not match unannotated count", () => {
    const parentId = "p";
    const parent = makeAnnotatedBlock(parentId);
    for (let i = 0; i < 3; i++) {
      const el = document.createElement("li");
      parent.appendChild(el);
    }
    document.body.appendChild(parent);

    const blocks = {
      [parentId]: { type: "x", label: "X", children: ["c1", "c2"] },
      c1: { type: "y", label: "Y", children: [] },
      c2: { type: "y", label: "Y", children: [] },
    };

    WagtailInspectAugment.augmentPreviewBlocks(blocks);

    parent.querySelectorAll("li").forEach((el) => {
      expect(el.dataset.blockId).toBeUndefined();
    });
  });
});

describe("_repairEmptyLabels (via augmentPreviewBlocks)", () => {
  it("fills empty data-block-type and data-block-label from the map", () => {
    const id = "uuid-1";
    const el = document.createElement("div");
    el.setAttribute("data-block-id", id);
    el.setAttribute("data-block-type", "");
    el.setAttribute("data-block-label", "");
    document.body.appendChild(el);

    WagtailInspectAugment.augmentPreviewBlocks({
      [id]: { type: "hero", label: "Hero", children: [] },
    });

    expect(el.dataset.blockType).toBe("hero");
    expect(el.dataset.blockLabel).toBe("Hero");
  });

  it("does not overwrite existing type/label attributes", () => {
    const id = "uuid-2";
    const el = makeAnnotatedBlock(id, "existing-type", "Existing Label");
    document.body.appendChild(el);

    WagtailInspectAugment.augmentPreviewBlocks({
      [id]: { type: "override", label: "Override", children: [] },
    });

    expect(el.dataset.blockType).toBe("existing-type");
    expect(el.dataset.blockLabel).toBe("Existing Label");
  });
});
