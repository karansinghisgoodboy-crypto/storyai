// Screens that are not built yet. Each one says so plainly and lists what it will do.
// There are no buttons or form fields here, because nothing works yet.
const ComingSoon = {
  info: {
    characters: {
      label: "Characters",
      step: "Step 6",
      what: "A character database with appearance sheets, reference images and locking.",
    },
    locations: {
      label: "Locations",
      step: "Step 7",
      what: "A location database with descriptions, mood and reference images.",
    },
    story: {
      label: "Story",
      step: "Step 8",
      what: "Your logline, genre, tone, synopsis and story text.",
    },
    scenes: {
      label: "Scenes",
      step: "Step 9",
      what: "Scenes with linked locations and characters, and per-scene outfit notes. " +
            "Shots follow in Step 10.",
    },
    storyboard: {
      label: "Storyboard",
      step: "Step 15",
      what: "Shot panels with image or sketch upload, built on the shots from Step 10.",
    },
    continuity: {
      label: "Continuity",
      step: "Steps 16 and 17",
      what: "Rule checks first (Step 16), then AI checks for continuity problems (Step 17).",
    },
    export: {
      label: "Export",
      step: "Step 19",
      what: "Markdown, a JSON backup and a printable storyboard.",
    },
  },

  render(box, key) {
    const item = ComingSoon.info[key];
    box.append(
      Dom.el("h2", { class: "section-title", text: item.label }),
      Dom.el("div", { class: "status-note", "data-coming-soon": "true" }, [
        Dom.el("p", { text: item.label + " is not available yet. It is planned for " + item.step + " of the build plan." }),
        Dom.el("p", { class: "muted", text: "What it will do: " + item.what }),
      ])
    );
  },
};
