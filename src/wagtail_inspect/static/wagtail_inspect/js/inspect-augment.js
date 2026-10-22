/**
 * Client-side DOM augmentation for blocks Python did not annotate (custom
 * templates, includecontents, etc.) and repair of empty type/label from the
 * flat API map. Exposed as window.WagtailInspectAugment.augmentPreviewBlocks.
 * Map shape: { [uuid]: { type, label, children?: string[] } }.
 */

/**
 * Sibling group of length `count` under `ancestor` (same tag or same class).
 * Requires exact count before deeper search to avoid wrong matches when count is 2.
 * @returns {Element[] | null}
 */
function _findSiblingGroup(ancestor, count) {
  function search(el) {
    const kids = Array.from(el.children).filter((c) => !c.hasAttribute("data-block-id"));

    if (kids.length === count) {
      const tags = new Set(kids.map((c) => c.tagName));
      if (tags.size === 1) return kids;

      const classes = new Set(kids.map((c) => c.className));
      if (classes.size === 1) return kids;
    }

    for (const kid of kids) {
      const result = search(kid);
      if (result) return result;
    }

    return null;
  }

  return search(ancestor);
}

/**
 * Annotate missing child nodes from the flat map; then fill empty type/label.
 * @param {Object<string, { type?: string, label?: string, children?: string[] }>} blocks
 */
function augmentPreviewBlocks(blocks) {
  // One pass over the DOM, not a query per id: this runs on every preview refresh.
  // Kept current as children are annotated, so later parents see them.
  const marked = Array.from(document.querySelectorAll("[data-block-id]:not(template)"));
  const elements = new Map();
  for (const el of marked) {
    if (!elements.has(el.dataset.blockId)) elements.set(el.dataset.blockId, el);
  }

  for (const [parentId, parentInfo] of Object.entries(blocks)) {
    const children = parentInfo.children;
    if (!children || children.length === 0) continue;

    const unannotated = children.filter((id) => !elements.has(id));

    if (unannotated.length === 0) continue;

    const parentEl = elements.get(parentId);
    if (!parentEl) continue;

    const candidates = _findSiblingGroup(parentEl, unannotated.length);

    if (!candidates || candidates.length !== unannotated.length) continue;

    for (let i = 0; i < unannotated.length; i++) {
      const childId = unannotated[i];
      const childInfo = blocks[childId];
      if (!childInfo) continue;

      candidates[i].dataset.blockId = childId;
      candidates[i].dataset.blockType = childInfo.type || "";
      candidates[i].dataset.blockLabel = childInfo.label || "";
      elements.set(childId, candidates[i]);
    }
  }

  // Annotated children already carry type and label; only the marked ones need repair.
  _repairEmptyLabels(blocks, marked);
}

function _repairEmptyLabels(blocks, marked) {
  for (const el of marked) {
    const info = blocks[el.dataset.blockId];
    if (!info) continue;

    if (!el.dataset.blockType && info.type) {
      el.dataset.blockType = info.type;
    }
    if (!el.dataset.blockLabel && info.label) {
      el.dataset.blockLabel = info.label;
    }
  }
}

window.WagtailInspectAugment = {
  augmentPreviewBlocks,
};
