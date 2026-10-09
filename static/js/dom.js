// Tiny helpers for building the page safely.
// Text is always added with textContent / text nodes (never as raw HTML),
// so project titles or AI text can never run as code.
const Dom = {
  // Dom.el("p", { class: "note", text: "Hello" }, [child1, child2])
  el(tag, props = {}, children = []) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(props)) {
      if (key === "class") node.className = value;
      else if (key === "text") node.textContent = value;
      else if (key.startsWith("on") && typeof value === "function") {
        node.addEventListener(key.slice(2), value);
      } else node.setAttribute(key, value);
    }
    for (const child of [].concat(children)) {
      if (child !== null && child !== undefined) node.append(child);
    }
    return node;
  },

  // Every button on screen is created here, and it must have a click handler.
  // kind: "primary" | "danger" | "quiet"
  button(label, onClick, kind = "quiet") {
    if (typeof onClick !== "function") {
      throw new Error("Every button needs a click handler.");
    }
    return Dom.el("button", {
      type: "button",
      class: "btn btn-" + kind,
      text: label,
      onclick: onClick,
    });
  },

  // A button that is switched off on purpose. It must say why (shown as a tooltip),
  // and the screen around it should explain it in plain text too.
  disabledButton(label, reason, kind = "primary") {
    if (typeof reason !== "string" || reason.length === 0) {
      throw new Error("A disabled button needs a reason.");
    }
    const node = Dom.el("button", {
      type: "button",
      class: "btn btn-" + kind,
      text: label,
      title: reason,
      "aria-disabled": "true",
    });
    node.disabled = true;
    return node;
  },

  clear(node) {
    node.replaceChildren();
  },

  formatDate(iso) {
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return "";
    return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
  },
};
