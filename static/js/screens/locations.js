const LOCATION_FIELDS = [
  ["name", "Name", "text", true],
  ["description", "Description", "textarea"],
  ["mood", "Atmosphere", "textarea"],
];

const LocationsScreen = {
  render(box, project) {
    this.box = box;
    this.project = project;
    this.editor = null;
    this.draw();
  },

  async draw() {
    const box = this.box;
    Dom.clear(box);
    box.append(Dom.el("div", { class: "page-head location-page-head" }, [
      Dom.el("div", {}, [
        Dom.el("p", { class: "eyebrow", text: "WORLD LIBRARY" }),
        Dom.el("h2", { class: "section-title", text: "Locations" }),
        Dom.el("p", { class: "muted", text: "Build the worlds where your story lives." }),
      ]),
      Dom.button("Add Location", () => this.openEditor(null), "primary"),
    ]));

    try {
      const response = await Api.listLocations(this.project.id);
      if (!this.box) return;
      this.locations = response.locations;
      this.drawList();
    } catch (error) {
      box.append(Dom.el("p", { class: "message", role: "alert", text: error.message }));
    }
  },

  drawList() {
    const list = Dom.el("div", { class: "location-grid" });
    if (!this.locations.length) {
      list.append(Dom.el("div", { class: "location-empty" }, [
        Dom.el("div", { class: "location-empty-mark", "aria-hidden": "true", text: "◌" }),
        Dom.el("h3", { text: "A world waiting to be found" }),
        Dom.el("p", { class: "muted", text: "Create a location to give your story a place to unfold." }),
        Dom.button("Add your first location", () => this.openEditor(null), "primary"),
      ]));
    }

    for (const place of this.locations) {
      const media = place.image_id
        ? Dom.el("img", {
          class: "location-card-image",
          src: `/api/projects/${this.project.id}/locations/${place.id}/image`,
          alt: `${place.name} reference`,
          loading: "lazy",
        })
        : Dom.el("div", {
          class: "location-card-placeholder",
          "aria-hidden": "true",
          text: "⌁",
        });
      if (media.tagName === "IMG") {
        media.addEventListener("error", () => {
          media.replaceWith(Dom.el("div", {
            class: "location-card-placeholder",
            "aria-hidden": "true",
            text: "⌁",
          }));
        }, { once: true });
      }

      const status = Dom.el("span", {
        class: `location-state${place.locked ? " is-locked" : ""}`,
        text: place.locked ? "Locked" : "Editable",
      });
      const description = place.description || "No world description yet.";
      const atmosphere = place.mood
        ? Dom.el("p", { class: "location-atmosphere", text: place.mood })
        : null;
      const edit = place.locked
        ? Dom.disabledButton("Edit", "Unlock this location before editing.")
        : Dom.button("Edit", () => this.openEditor(place));

      list.append(Dom.el("article", {
        class: `location-card${place.locked ? " is-locked" : ""}`,
        "data-location-id": place.id,
      }, [
        Dom.el("div", { class: "location-card-art" }, [
          media,
          Dom.el("span", { class: "location-card-index", text: `PLACE / ${String(place.id).padStart(2, "0")}` }),
        ]),
        Dom.el("div", { class: "location-card-body" }, [
          Dom.el("div", { class: "location-card-heading" }, [
            Dom.el("h3", { text: place.name }),
            status,
          ]),
          Dom.el("p", { class: "location-description", text: description }),
          atmosphere,
          Dom.el("div", { class: "row location-card-actions" }, [
            edit,
            Dom.button(place.locked ? "Unlock" : "Lock", () => this.toggleLock(place)),
            Dom.button("Delete", () => this.remove(place), "danger"),
          ]),
        ]),
      ]));
    }
    this.box.append(list);
  },

  openEditor(place) {
    this.closeEditor();
    const isNew = !place;
    const location = place ? { ...place } : {
      id: null,
      project_id: this.project.id,
      name: "",
      description: "",
      mood: "",
      image_id: null,
      locked: false,
      updated_at: null,
    };
    const overlay = Dom.el("div", {
      class: "location-modal-backdrop",
      role: "presentation",
      onclick: event => {
        if (event.target === overlay) this.closeEditor();
      },
    });
    const panel = Dom.el("section", {
      class: "location-editor",
      role: "dialog",
      "aria-modal": "true",
      "aria-labelledby": "location-editor-title",
      tabindex: "-1",
    });
    const form = Dom.el("form", { class: "location-editor-form" });
    const close = () => this.closeEditor();
    const closeButton = Dom.button("Close", close);
    const saveButton = Dom.button(isNew ? "Create location" : "Save", () => this.save(form, location, isNew, status, saveButton), "primary");
    const status = Dom.el("p", {
      class: "location-editor-status",
      role: "status",
      "aria-live": "polite",
      text: isNew ? "Give this place a name to begin." : "Changes save automatically after a short pause.",
    });
    const inputs = new Map();

    panel.append(Dom.el("div", { class: "location-editor-header" }, [
      Dom.el("div", {}, [
        Dom.el("p", { class: "eyebrow", text: isNew ? "NEW PLACE" : "LOCATION SHEET" }),
        Dom.el("h2", { id: "location-editor-title", text: isNew ? "Create location" : `Edit ${location.name}` }),
      ]),
      closeButton,
    ]));

    const addField = ([key, label, type, required]) => {
      const id = `location-${location.id || "new"}-${key}`;
      const control = type === "textarea"
        ? Dom.el("textarea", { id, name: key, rows: key === "description" ? "5" : "3", maxlength: key === "description" ? "3000" : "500" })
        : Dom.el("input", { id, name: key, type: "text", maxlength: "120" });
      control.value = location[key] || "";
      if (required) control.required = true;
      inputs.set(key, control);
      return Dom.el("label", { class: "location-field", for: id }, [
        Dom.el("span", { text: `${label}${required ? " *" : ""}` }),
        control,
      ]);
    };

    const identity = Dom.el("div", { class: "location-form-section" }, [
      Dom.el("p", { class: "location-section-label", text: "01 / IDENTITY" }),
      addField(LOCATION_FIELDS[0]),
    ]);
    const environment = Dom.el("div", { class: "location-form-section" }, [
      Dom.el("p", { class: "location-section-label", text: "02 / ENVIRONMENT" }),
      addField(LOCATION_FIELDS[1]),
      addField(LOCATION_FIELDS[2]),
    ]);
    form.append(identity, environment);

    const uploadStatus = Dom.el("p", {
      class: "location-upload-status",
      role: "status",
      "aria-live": "polite",
      text: location.image_id ? "Reference image saved with this location." : "PNG, JPG or WEBP · up to 5 MB",
    });
    const preview = location.image_id
      ? Dom.el("img", {
        class: "location-editor-preview",
        src: `/api/projects/${this.project.id}/locations/${location.id}/image`,
        alt: `${location.name} reference image`,
      })
      : Dom.el("div", {
        class: "location-editor-preview location-card-placeholder",
        "aria-hidden": "true",
        text: "⌁",
      });
    const file = Dom.el("input", {
      class: "location-file-input",
      type: "file",
      accept: ".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp",
      "aria-label": "Choose a PNG, JPG, or WEBP reference image",
    });
    const dropArea = Dom.el("label", { class: "location-drop-area" }, [
      Dom.el("span", { class: "location-drop-icon", "aria-hidden": "true", text: "↑" }),
      Dom.el("span", { class: "location-drop-title", text: "Choose or drop a reference image" }),
      Dom.el("span", { class: "small muted", text: "PNG, JPG or WEBP · maximum 5 MB" }),
      file,
    ]);
    const showLocalPreview = selected => {
      if (!selected) return;
      if (selected.size > 5 * 1024 * 1024) {
        uploadStatus.textContent = "Image must be 5 MB or smaller.";
        return;
      }
      const imageFormats = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
      };
      const extension = selected.name.slice(selected.name.lastIndexOf(".")).toLowerCase();
      if (!imageFormats[extension] || imageFormats[extension] !== selected.type) {
        uploadStatus.textContent = "Choose a PNG, JPG or WEBP image with a matching file type.";
        return;
      }
      const reader = new FileReader();
      reader.addEventListener("load", () => {
        if (this.editor !== editorState) return;
        const localPreview = Dom.el("img", {
          class: "location-editor-preview",
          src: reader.result,
          alt: `Preview of ${selected.name}`,
        });
        this.editor.preview.replaceWith(localPreview);
        this.editor.preview = localPreview;
        uploadStatus.textContent = `${selected.name} selected. Upload it to save as the location reference.`;
      });
      reader.addEventListener("error", () => {
        uploadStatus.textContent = "Could not preview this image. Please choose another file.";
      }, { once: true });
      const editorState = this.editor;
      reader.readAsDataURL(selected);
    };
    const uploadButton = isNew
      ? Dom.disabledButton("Upload reference", "Save the location before uploading an image.")
      : location.locked
        ? Dom.disabledButton("Upload reference", "Unlock this location before changing its image.")
        : Dom.button("Upload reference", async () => {
          const editor = this.editor;
          if (!editor) return;
          const selected = file.files[0];
          if (!selected) {
            uploadStatus.textContent = "Choose an image file first.";
            return;
          }
          if (selected.size > 5 * 1024 * 1024) {
            uploadStatus.textContent = "Image must be 5 MB or smaller.";
            return;
          }
          editor.uploading = true;
          uploadButton.disabled = true;
          closeButton.disabled = true;
          for (const input of editor.inputs.values()) input.disabled = true;
          file.disabled = true;
          try {
            uploadStatus.textContent = "Uploading reference…";
            await AutoSave.settle(`location-${location.id}`);
            const saved = await Api.updateLocation(this.project.id, location.id, {
              ...this.values(editor.inputs),
              updated_at: location.updated_at,
            });
            Object.assign(location, saved.location);
            const response = await Api.uploadLocationImage(this.project.id, location.id, selected);
            if (this.editor !== editor) return;
            Object.assign(location, response.location);
            uploadStatus.textContent = "Reference image saved.";
            const savedPreview = Dom.el("img", {
              class: "location-editor-preview",
              src: `/api/projects/${this.project.id}/locations/${location.id}/image?updated=${encodeURIComponent(location.updated_at)}`,
              alt: `${location.name} reference image`,
            });
            this.editor.preview.replaceWith(savedPreview);
            this.editor.preview = savedPreview;
            const card = this.box.querySelector(`[data-location-id="${location.id}"]`);
            const cardArt = card?.querySelector(".location-card-art");
            if (cardArt) {
              const cardImage = Dom.el("img", {
                class: "location-card-image",
                src: `/api/projects/${this.project.id}/locations/${location.id}/image?updated=${encodeURIComponent(location.updated_at)}`,
                alt: `${location.name} reference`,
                loading: "lazy",
              });
              cardImage.addEventListener("error", () => {
                cardImage.replaceWith(Dom.el("div", {
                  class: "location-card-placeholder",
                  "aria-hidden": "true",
                  text: "⌁",
                }));
              }, { once: true });
              cardArt.querySelector(".location-card-image, .location-card-placeholder")?.replaceWith(cardImage);
            }
          } catch (error) {
            if (this.editor === editor) uploadStatus.textContent = error.message;
          } finally {
            editor.uploading = false;
            closeButton.disabled = false;
            if (this.editor === editor) {
              uploadButton.disabled = false;
              file.disabled = false;
              for (const input of editor.inputs.values()) input.disabled = false;
            }
          }
        });
    form.append(Dom.el("div", { class: "location-form-section location-reference-section" }, [
      Dom.el("p", { class: "location-section-label", text: "03 / REFERENCE IMAGE" }),
      Dom.el("div", { class: "location-reference-layout" }, [preview, Dom.el("div", {}, [dropArea, uploadStatus, uploadButton])]),
    ]));

    form.append(status, Dom.el("div", { class: "location-editor-actions" }, [
      Dom.button("Close", close),
      saveButton,
    ]));
    panel.append(form);
    overlay.append(panel);
    this.box.append(overlay);
    this.editor = { overlay, panel, location, inputs, isNew, uploadStatus };
    this.editor.preview = preview;
    file.addEventListener("change", () => showLocalPreview(file.files[0]));
    dropArea.addEventListener("dragover", event => {
      event.preventDefault();
      dropArea.classList.add("is-dragging");
    });
    dropArea.addEventListener("dragleave", () => dropArea.classList.remove("is-dragging"));
    dropArea.addEventListener("drop", event => {
      event.preventDefault();
      dropArea.classList.remove("is-dragging");
      const selected = event.dataTransfer.files[0];
      if (!selected) return;
      const transfer = new DataTransfer();
      transfer.items.add(selected);
      file.files = transfer.files;
      showLocalPreview(selected);
    });

    if (!isNew && !location.locked) {
      for (const control of inputs.values()) {
        control.addEventListener("input", () => {
          AutoSave.schedule(`location-${location.id}`, async () => {
            const response = await Api.updateLocation(this.project.id, location.id, {
              ...this.values(inputs),
              updated_at: location.updated_at,
            });
            Object.assign(location, response.location);
            status.textContent = "Saved";
          }, (state, error) => {
            status.textContent = state === "conflict"
              ? error.message
              : state === "failed"
                ? "Could not save changes. Check your connection and try again."
                : state === "saving" ? "Saving…" : "Saved";
          });
        });
      }
    }

    panel.addEventListener("keydown", event => {
      if (event.key === "Escape") {
        event.preventDefault();
        close();
      }
      if (event.key === "Tab") this.trapFocus(event, panel);
    });
    inputs.get("name").focus();
  },

  values(inputs) {
    return Object.fromEntries([...inputs].map(([key, input]) => [key, input.value]));
  },

  trapFocus(event, panel) {
    const focusable = [...panel.querySelectorAll("button:not(:disabled),input:not(:disabled),textarea:not(:disabled)")];
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  },

  async save(form, location, isNew, status, saveButton) {
    if (!form.reportValidity()) return;
    const editor = this.editor;
    const key = `location-${location.id}`;
    saveButton.disabled = true;
    status.textContent = "Saving…";
    try {
      if (!isNew) await AutoSave.settle(key);
      const values = this.values(editor.inputs);
      for (const input of editor.inputs.values()) input.disabled = true;
      const response = isNew
        ? await Api.createLocation(this.project.id, values)
        : await Api.updateLocation(this.project.id, location.id, {
          ...values,
          updated_at: location.updated_at,
        });
      Object.assign(location, response.location);
      if (this.editor === editor) {
        if (isNew) AutoSave.cancel(`location-${location.id}`);
        this.closeEditor();
        await this.draw();
      }
    } catch (error) {
      if (this.editor === editor) {
        for (const input of editor.inputs.values()) input.disabled = false;
        saveButton.disabled = false;
      }
      status.textContent = error.message;
    }
  },

  closeEditor() {
    if (!this.editor) return;
    if (this.editor.uploading) {
      this.editor.uploadStatus.textContent = "Wait for the image upload to finish before closing.";
      return;
    }
    this.editor.overlay.remove();
    this.editor = null;
  },

  async toggleLock(place) {
    try {
      await Api.lockLocation(this.project.id, place.id, !place.locked, place.updated_at);
      await this.draw();
    } catch (error) {
      this.showError(error);
    }
  },

  async remove(place) {
    if (place.locked) {
      this.showError(new Error("Unlock this location before deleting it."));
      return;
    }
    if (!window.confirm(`Delete "${place.name}"? Scenes using it will no longer have a location selected.`)) return;
    try {
      await Api.deleteLocation(this.project.id, place.id);
      await this.draw();
    } catch (error) {
      this.showError(error);
    }
  },

  showError(error) {
    const message = Dom.el("p", { class: "message", role: "alert", text: error.message });
    this.box.prepend(message);
  },
};
