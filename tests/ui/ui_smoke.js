const assert = require("node:assert/strict");
const { JSDOM, VirtualConsole } = require("jsdom");

const BASE = process.argv[2] || process.env.STORYAI_BASE_URL || "http://127.0.0.1:5000";
const jsdomErrors = [];
const pause = (ms = 30) => new Promise((resolve) => setTimeout(resolve, ms));
const waitFor = async (predicate, description, timeout = 5000) => {
  const end = Date.now() + timeout;
  while (Date.now() < end) {
    if (predicate()) return;
    await pause();
  }
  throw new Error(`Timed out waiting for ${description}`);
};

const main = async () => {
  const virtualConsole = new VirtualConsole();
  virtualConsole.on("jsdomError", (error) => jsdomErrors.push(error.message));
  virtualConsole.on("error", (error) => jsdomErrors.push(String(error)));
  const dom = await JSDOM.fromURL(`${BASE}/`, {
    runScripts: "dangerously",
    resources: "usable",
    pretendToBeVisual: true,
    virtualConsole,
    beforeParse(window) {
      window.HTMLElement.prototype.scrollIntoView = () => {};
      window.fetch = async (...args) => {
        const response = await fetch(new URL(args[0], window.location.href), args[1]);
        if (response.status >= 500) {
          throw new Error(`Unexpected server error (${response.status})`);
        }
        return response;
      };
    },
  });
  const { window } = dom;
  const { document } = window;
  window.addEventListener("error", (event) => jsdomErrors.push(event.message));
  const button = (label, root = document) =>
    [...root.querySelectorAll("button")].find(
      (element) => element.textContent.trim() === label,
    );
  const click = (element, description) => {
    assert.ok(element, `Expected ${description} to exist`);
    element.click();
  };
  const projectCard = (title) =>
    [...document.querySelectorAll(".frame")].find(
      (card) => card.querySelector(".frame-title")?.textContent === title,
    );
  const locationCard = (name) =>
    [...document.querySelectorAll(".location-card")].find(
      (card) => card.querySelector(".location-card-heading h3")?.textContent === name,
    );
  const characterCard = (name) =>
    [...document.querySelectorAll(".character-card")].find(
      (card) => card.querySelector(".character-info h3")?.textContent === name,
    );
  const visible = (element) => element && !element.hidden;

  try {
    await waitFor(
      () => document.querySelector(".empty h2")?.textContent === "Your story starts here",
      "the empty project library",
    );
    assert.equal(document.title, "StoryAI — Projects");
    assert.ok(button("＋ New Project"));
    assert.ok(button("Create project"));
    assert.equal(document.querySelectorAll(".frame").length, 0);

    click(button("Create project"), "project creation button");
    await waitFor(
      () => [...document.querySelectorAll(".message")].some((el) => visible(el) && /title is required/i.test(el.textContent)),
      "required-title validation",
    );

    const title = document.querySelector("#new-title");
    const idea = document.querySelector("#new-idea");
    title.value = "<img src=x onerror=alert(1)> Smoke Story";
    title.dispatchEvent(new window.Event("input", { bubbles: true }));
    idea.value = "A browser-level smoke test.";
    idea.dispatchEvent(new window.Event("input", { bubbles: true }));
    click(button("Create project"), "project creation button");
    await waitFor(
      () => /^#\/project\/\d+(?:\/chat)?$/.test(window.location.hash)
        && document.querySelector(".workspace-head h1")?.textContent === "<img src=x onerror=alert(1)> Smoke Story",
      "the new project workspace",
    );
    const projectId = Number(window.location.hash.match(/^#\/project\/(\d+)/)[1]);
    assert.equal(document.querySelectorAll(".workspace-head h1 img").length, 0);
    assert.equal(document.querySelector(".workspace-head .logline").textContent, "A browser-level smoke test.");
    assert.equal(document.querySelectorAll(".side-nav a").length, 8);
    assert.deepEqual(
      [...document.querySelectorAll(".side-nav a span:last-child")].map((el) => el.textContent),
      ["Chat", "Characters", "Locations", "Story", "Scenes", "Storyboard", "Continuity", "Export"],
    );

    const sections = [
      ["chat", "AI Chat"],
      ["characters", "Characters"],
      ["locations", "Locations"],
      ["story", "Story"],
      ["scenes", "Scenes"],
      ["storyboard", "Storyboard"],
      ["continuity", "Continuity"],
      ["export", "Export"],
    ];
    for (const [key, heading] of sections) {
      const link = document.querySelector(`.side-nav a[data-section="${key}"]`);
      click(link, `${key} navigation link`);
      await waitFor(
        () => window.location.hash.endsWith(`/${key}`)
          && document.querySelector(".section-content h2")?.textContent === heading,
        `${key} section`,
      );
      assert.ok(link.hasAttribute("aria-current"), `${key} navigation link should be active`);
      assert.equal(document.querySelectorAll('.side-nav a[aria-current]').length, 1);
      assert.equal(
        document.querySelector(".section-content .message")?.textContent,
        undefined,
        `${key} section should not fall back to a render error`,
      );
    }

    click(document.querySelector('.side-nav a[data-section="story"]'), "Story navigation link");
    await waitFor(
      () => document.querySelector('.section-content input[name="logline"]'),
      "Story form fields",
    );
    assert.ok(document.querySelector('.section-content input[name="genre"]'));
    assert.ok(document.querySelector('.section-content input[name="tone"]'));
    assert.ok(document.querySelector('.section-content textarea[name="synopsis"]'));
    assert.ok(document.querySelector('.section-content textarea[name="story_text"]'));
    const storyLogline = document.querySelector('.section-content input[name="logline"]');
    storyLogline.value = "A smoke-tested story logline.";
    click(button("Save story"), "Save story button");
    await waitFor(
      () => document.querySelector(".section-content .small.muted")?.textContent === "Saved",
      "Story save confirmation",
    );
    const savedStory = await fetch(`${BASE}/api/projects/${projectId}/story`).then((response) => response.json());
    assert.equal(savedStory.story.logline, "A smoke-tested story logline.");
    const storyText = document.querySelector('.section-content textarea[name="story_text"]');
    storyText.value = "Autosaved story text survives refresh.";
    storyText.dispatchEvent(new window.Event("input", { bubbles: true }));
    await waitFor(
      () => document.querySelector(".section-content .small.muted")?.textContent === "Saving…",
      "Story autosave start",
    );
    await waitFor(
      () => document.querySelector(".section-content .small.muted")?.textContent === "Saved",
      "Story autosave completion",
    );
    const autoSaved = await fetch(`${BASE}/api/projects/${projectId}/story`).then((response) => response.json());
    assert.equal(autoSaved.story.story_text, "Autosaved story text survives refresh.");

    click(document.querySelector('.side-nav a[data-section="characters"]'), "Characters navigation link");
    await waitFor(() => button("Add character"), "Characters section");
    click(button("Add character"), "Add character button");
    await waitFor(() => document.querySelector(".character-editor"), "character editor");
    document.querySelector("#char-name").value = "UI Smoke Character";
    document.querySelector("#char-role").value = "Protagonist";
    document.querySelector("#char-age").value = "26";
    document.querySelector("#char-build").value = "Lean";
    document.querySelector("#char-hair").value = "Black";
    document.querySelector("#char-face").value = "Oval";
    document.querySelector("#char-appearance").value = "A scar across one eyebrow.";
    document.querySelector("#char-default_outfit").value = "Dark blue coat.";
    document.querySelector("#char-distinguishing_marks").value = "Silver ring.";
    document.querySelector("#char-personality").value = "Patient and observant.";
    document.querySelector("#char-backstory").value = "Raised near the old harbor.";
    document.querySelector("#char-voice").value = "Soft, measured.";
    document.querySelector("#char-abilities").value = "Reads nautical charts.";
    click(button("Create"), "Create character button");
    await waitFor(() => characterCard("UI Smoke Character"), "created Character card");
    click(button("Edit", characterCard("UI Smoke Character")), "Edit character button");
    await waitFor(() => document.querySelector("#char-age"), "character edit form");
    assert.equal(document.querySelector("#char-role").value, "Protagonist");
    document.querySelector("#char-age").value = "27";
    document.querySelector("#char-appearance").value = "A small scar across one eyebrow.";
    click(button("Save"), "Save character button");
    await waitFor(() => !document.querySelector(".character-editor"), "character save");
    await waitFor(() => characterCard("UI Smoke Character"), "updated Character card");
    click(button("Lock", characterCard("UI Smoke Character")), "Lock character button");
    await waitFor(() => characterCard("UI Smoke Character")?.textContent.includes("Locked"), "Character lock state");
    assert.ok(button("Edit", characterCard("UI Smoke Character"))?.disabled);
    click(button("Unlock", characterCard("UI Smoke Character")), "Unlock character button");
    await waitFor(
      () => characterCard("UI Smoke Character")?.textContent.includes("Editable"),
      "Character unlock state",
    );
    click(document.querySelector(".workspace-head .back"), "All projects link");
    await waitFor(() => projectCard("<img src=x onerror=alert(1)> Smoke Story"), "project library");
    click(button("Open workspace", projectCard("<img src=x onerror=alert(1)> Smoke Story")), "reopen project");
    await waitFor(
      () => document.querySelector(".workspace-head h1")?.textContent === "<img src=x onerror=alert(1)> Smoke Story",
      "reopened project workspace",
    );
    click(document.querySelector('.side-nav a[data-section="characters"]'), "Characters navigation link");
    await waitFor(() => characterCard("UI Smoke Character"), "persisted Character");
    click(button("Edit", characterCard("UI Smoke Character")), "Edit unlocked character button");
    await waitFor(
      () => document.querySelector("#char-age")?.value === "27",
      "saved Character fields",
    );
    assert.equal(document.querySelector("#char-build").value, "Lean");
    assert.equal(document.querySelector("#char-hair").value, "Black");
    assert.equal(document.querySelector("#char-face").value, "Oval");
    assert.equal(document.querySelector("#char-appearance").value, "A small scar across one eyebrow.");
    assert.equal(document.querySelector("#char-default_outfit").value, "Dark blue coat.");
    assert.equal(document.querySelector("#char-distinguishing_marks").value, "Silver ring.");
    assert.equal(document.querySelector("#char-personality").value, "Patient and observant.");
    assert.equal(document.querySelector("#char-backstory").value, "Raised near the old harbor.");
    assert.equal(document.querySelector("#char-voice").value, "Soft, measured.");
    assert.equal(document.querySelector("#char-abilities").value, "Reads nautical charts.");
    click(button("Close"), "Close character editor button");

    click(document.querySelector('.side-nav a[data-section="locations"]'), "Locations navigation link");
    await waitFor(
      () => button("Add Location"),
      "Locations section",
    );
    click(button("Add Location"), "Add location button");
    await waitFor(
      () => document.querySelector(".location-editor"),
      "location editor",
    );
    const locationName = document.querySelector('.location-editor [name="name"]');
    assert.ok(locationName, "the existing Location name field should be editable");
    locationName.value = "UI Smoke Location";
    locationName.dispatchEvent(new window.Event("input", { bubbles: true }));
    const locationDescription = document.querySelector('.location-editor [name="description"]');
    locationDescription.value = "Created by the simulated-browser regression test.";
    locationDescription.dispatchEvent(new window.Event("input", { bubbles: true }));
    click(button("Create location"), "Create location button");
    await waitFor(
      () => locationCard("UI Smoke Location"),
      "created Location card",
    );
    click(button("Lock", locationCard("UI Smoke Location")), "Location lock button");
    await waitFor(
      () => locationCard("UI Smoke Location")?.querySelector(".location-state")?.textContent === "Locked",
      "Location lock state",
    );
    assert.ok(button("Edit", locationCard("UI Smoke Location"))?.disabled);
    click(button("Unlock", locationCard("UI Smoke Location")), "Location unlock button");
    await waitFor(
      () => locationCard("UI Smoke Location")?.querySelector(".location-state")?.textContent === "Editable",
      "Location unlock state",
    );

    click(document.querySelector('.side-nav a[data-section="scenes"]'), "Scenes navigation link");
    await waitFor(() => button("Add scene"), "Scenes section");
    click(button("Add scene"), "Add scene button");
    await waitFor(() => document.querySelector(".scene-card"), "new scene form");
    const sceneCard = document.querySelector(".scene-card");
    sceneCard.querySelector('[name="title"]').value = "Harbor Arrival";
    sceneCard.querySelector('[name="summary"]').value = "The hero reaches the harbor.";
    sceneCard.querySelector('[name="order_no"]').value = "3";
    sceneCard.querySelector('[name="location_id"]').value = String(
      (await fetch(`${BASE}/api/projects/${projectId}/locations`).then((response) => response.json()))
        .locations.find((item) => item.name === "UI Smoke Location").id,
    );
    const includeCharacter = sceneCard.querySelector('[aria-label="Include UI Smoke Character"]');
    includeCharacter.checked = true;
    sceneCard.querySelector('[aria-label="UI Smoke Character outfit or state"]').value = "Wearing the dark blue coat.";
    click(button("Save", sceneCard), "Save scene and cast button");
    await waitFor(() => sceneCard.querySelector(".small.muted")?.textContent === "Saved", "scene and cast save");
    const sceneData = await fetch(`${BASE}/api/projects/${projectId}/scenes`).then((response) => response.json());
    const savedScene = sceneData.scenes.find((item) => item.title === "Harbor Arrival");
    assert.ok(savedScene);
    assert.equal(savedScene.order_no, 3);
    assert.equal(savedScene.location_id, Number(sceneCard.querySelector('[name="location_id"]').value));
    assert.deepEqual(
      savedScene.characters.map((item) => [item.name, item.outfit_state]),
      [["UI Smoke Character", "Wearing the dark blue coat."]],
    );

    click(document.querySelector('.side-nav a[data-section="storyboard"]'), "Storyboard navigation link");
    await waitFor(() => button("Add shot"), "Storyboard section");
    click(button("Add shot"), "Add storyboard shot button");
    await waitFor(() => document.querySelector(".shot-card"), "new storyboard shot");
    const shotCard = document.querySelector(".shot-card");
    shotCard.querySelector('[name="order_no"]').value = "4";
    shotCard.querySelector('[name="action"]').value = "A lantern swings above the wet pier.";
    click(button("Save", shotCard), "Save storyboard shot button");
    await waitFor(() => shotCard.querySelector(".small.muted")?.textContent === "Saved", "storyboard shot save");
    const savedShots = await fetch(
      `${BASE}/api/projects/${projectId}/scenes/${savedScene.id}/shots`,
    ).then((response) => response.json());
    assert.equal(savedShots.shots[0].order_no, 4);
    assert.equal(savedShots.shots[0].action, "A lantern swings above the wet pier.");

    click(document.querySelector('.side-nav a[data-section="continuity"]'), "Continuity navigation link");
    await waitFor(() => button("Run continuity check"), "Continuity section");
    click(document.querySelector('.side-nav a[data-section="export"]'), "Export navigation link");
    await waitFor(() => document.querySelector('a[href*="/export/json"]'), "Export section");

    click(document.querySelector('.side-nav a[data-section="chat"]'), "Chat navigation link");
    await waitFor(() => button("Structured memory"), "Chat workflow controls");
    click(button("Structured memory"), "Structured memory navigation button");
    await waitFor(() => button("Add memory"), "Structured memory section");
    click(button("Add memory"), "Add memory button");
    await waitFor(() => document.querySelector(".memory-card"), "created memory item");
    const memoryCard = document.querySelector(".memory-card");
    const memoryContent = memoryCard.querySelector('[name="content"]');
    memoryContent.value = "The harbor bell rings at dusk.";
    click(button("Save", memoryCard), "Save memory button");
    await waitFor(() => memoryCard.querySelector(".small.muted")?.textContent === "Saved", "memory save");
    click(button("Lock", memoryCard), "Lock memory button");
    await waitFor(() => document.querySelector(".memory-card .small.muted")?.textContent === "Locked", "memory lock");
    click(button("Unlock", document.querySelector(".memory-card")), "Unlock memory button");
    await waitFor(() => document.querySelector(".memory-card .small.muted")?.textContent === "Editable", "memory unlock");
    assert.equal(document.querySelector('.memory-card [name="content"]').value, "The harbor bell rings at dusk.");
    window.confirm = () => true;
    click(button("Delete", document.querySelector(".memory-card")), "Delete memory button");
    await waitFor(() => !document.querySelector(".memory-card"), "memory deletion");

    const proposal = await fetch(`${BASE}/api/projects/${projectId}/proposals`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        type: "memory",
        action: "add",
        payload: { kind: "fact", content: "The keeper carries a brass key." },
        reason: "Preserve a confirmed detail.",
      }),
    }).then((response) => response.json());
    click(button("Back to chat"), "Back to chat button");
    await waitFor(() => button("Review suggestions"), "Suggestion review button");
    click(button("Review suggestions"), "Review suggestions button");
    await waitFor(() => button("Accept"), "pending suggestion");
    click(button("Accept"), "Accept suggestion button");
    await waitFor(() => !button("Accept"), "suggestion approval");
    assert.ok(proposal.proposal.id);

    click(document.querySelector('.side-nav a[data-section="characters"]'), "Characters navigation link");
    await waitFor(() => characterCard("UI Smoke Character"), "Character remains after scene integration");
    click(button("Edit", characterCard("UI Smoke Character")), "Edit character button");
    await waitFor(() => document.querySelector("#char-age"), "Character editor before deletion");
    click(button("Close"), "Close character editor button");
    window.confirm = () => true;
    click(button("Delete", characterCard("UI Smoke Character")), "Delete character button");
    await waitFor(() => !characterCard("UI Smoke Character"), "Character deletion");

    click(document.querySelector(".workspace-head .back"), "All projects link");
    await waitFor(
      () => window.location.hash === "#/" && projectCard("<img src=x onerror=alert(1)> Smoke Story"),
      "return to project library",
    );
    click(button("Open workspace", projectCard("<img src=x onerror=alert(1)> Smoke Story")), "reopen project");
    await waitFor(
      () => document.querySelector(".workspace-head h1")?.textContent === "<img src=x onerror=alert(1)> Smoke Story",
      "reopened project workspace",
    );
    click(document.querySelector('.side-nav a[data-section="locations"]'), "Locations navigation link");
    await waitFor(
      () => locationCard("UI Smoke Location")?.querySelector(".location-state")?.textContent === "Editable",
      "persisted Location",
    );
    assert.equal(locationCard("UI Smoke Location").querySelector(".location-description").textContent, "Created by the simulated-browser regression test.");
    click(document.querySelector(".workspace-head .back"), "All projects link");
    await waitFor(
      () => window.location.hash === "#/" && projectCard("<img src=x onerror=alert(1)> Smoke Story"),
      "return to project library",
    );

    click(button("＋ New Project"), "New Project button");
    await waitFor(() => !document.querySelector("#new-title").disabled, "new project form");
    const secondTitle = document.querySelector("#new-title");
    secondTitle.value = "Second Smoke Story";
    secondTitle.dispatchEvent(new window.Event("input", { bubbles: true }));
    click(button("Create project"), "second project creation button");
    await waitFor(
      () => /^#\/project\/\d+(?:\/chat)?$/.test(window.location.hash)
        && document.querySelector(".workspace-head h1")?.textContent === "Second Smoke Story",
      "second project workspace",
    );
    const secondProjectId = Number(window.location.hash.match(/^#\/project\/(\d+)/)[1]);

    click(document.querySelector(".workspace-head .back"), "All projects link");
    await waitFor(
      () => window.location.hash === "#/" && projectCard("Second Smoke Story"),
      "project library with two projects",
    );
    assert.equal(document.querySelectorAll(".frame").length, 2);
    const secondCard = projectCard("Second Smoke Story");
    click(button("Rename", secondCard), "project rename button");
    const renameInput = secondCard.querySelector('input[aria-label="New project title"]');
    assert.ok(renameInput);
    renameInput.value = "Renamed Smoke Story";
    renameInput.dispatchEvent(new window.Event("input", { bubbles: true }));
    click(button("Save", secondCard), "project rename save button");
    await waitFor(() => projectCard("Renamed Smoke Story"), "renamed project");

    const staleCard = projectCard("Renamed Smoke Story");
    click(button("Rename", staleCard), "project rename button");
    const staleInput = staleCard.querySelector('input[aria-label="New project title"]');
    staleInput.value = "Stale Rename";
    staleInput.dispatchEvent(new window.Event("input", { bubbles: true }));
    const update = await fetch(`${BASE}/api/projects/${secondProjectId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: "Concurrent Rename" }),
    });
    assert.equal(update.status, 200);
    click(button("Save", staleCard), "stale project rename save button");
    await waitFor(
      () => [...staleCard.querySelectorAll(".message")].some((el) => visible(el) && /changed since you loaded/i.test(el.textContent)),
      "stale project edit conflict",
    );
    click(button("Reload latest", staleCard), "reload-latest button");
    await waitFor(() => projectCard("Concurrent Rename"), "latest project version");

    const latestCard = projectCard("Concurrent Rename");
    click(button("Delete", latestCard), "project delete button");
    await waitFor(() => button("Delete project", latestCard), "project deletion confirmation");
    click(button("Cancel", latestCard), "cancel project deletion button");
    assert.ok(projectCard("Concurrent Rename"));
    click(button("Delete", latestCard), "project delete button");
    await waitFor(() => button("Delete project", latestCard), "project deletion confirmation");
    click(button("Delete project", latestCard), "confirm project deletion button");
    await waitFor(
      () => !projectCard("Concurrent Rename") && document.querySelectorAll(".frame").length === 1,
      "project deletion",
    );

    window.location.hash = `#/project/${secondProjectId}/chat`;
    await waitFor(
      () => [...document.querySelectorAll(".message")].some((el) => el.textContent.includes("Project not found")),
      "deleted project not found response",
    );
    window.location.hash = `#/project/${projectId}/settings`;
    await waitFor(
      () => document.querySelector(".section-content h2")?.textContent === "Page not found",
      "unknown section handling",
    );
    window.location.hash = "#/";
    await waitFor(() => projectCard("<img src=x onerror=alert(1)> Smoke Story"), "project library");
    const firstCard = projectCard("<img src=x onerror=alert(1)> Smoke Story");
    click(button("Delete", firstCard), "last project delete button");
    await waitFor(() => button("Delete project", firstCard), "last project deletion confirmation");
    click(button("Delete project", firstCard), "confirm last project deletion");
    await waitFor(
      () => window.location.hash === "#/" && document.querySelector(".empty h2")?.textContent === "Your story starts here",
      "empty library after deleting the final project",
    );
    assert.equal(document.querySelectorAll(".frame").length, 0);
    assert.deepEqual(jsdomErrors, [], "the simulated browser should not report runtime errors");
    console.log("ALL UI CHECKS PASSED");
  } finally {
    window.close();
  }
};

main().catch((error) => {
  console.error(error.stack || error);
  if (jsdomErrors.length) console.error("Browser errors:", jsdomErrors);
  process.exitCode = 1;
});
