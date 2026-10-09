// Chat section. Step 5 builds only the layout: a large message area and a composer.
// Nothing here talks to an AI yet, so the composer is switched off and says why.
const ChatScreen = {
  render(box) {
    const noteId = "chat-note";

    const note = Dom.el("p", {
      id: noteId,
      class: "status-note",
      "data-coming-soon": "true",
      text: "AI chat is not available yet. It is planned for Step 11 of the build plan, " +
            "with project memory, suggestions and web search following in later steps. " +
            "Until then nothing can be sent.",
    });

    const log = Dom.el("div", {
      id: "chat-log",
      class: "chat-log",
      role: "log",
      "aria-label": "Conversation",
    }, [Dom.el("p", { class: "muted", text: "No messages yet." })]);

    const composer = Dom.el("div", { class: "composer" }, [
      Dom.el("label", { for: "chat-input", text: "Message" }),
      Dom.el("textarea", {
        id: "chat-input",
        rows: "4",
        disabled: "",
        placeholder: "Chat isn't available yet.",
        "aria-describedby": noteId,
      }),
      Dom.el("div", { class: "row" }, [
        Dom.disabledButton("Send", "Chat is not available until Step 11."),
      ]),
    ]);

    box.append(Dom.el("h2", { class: "section-title", text: "Chat" }), note, log, composer);
  },
};
