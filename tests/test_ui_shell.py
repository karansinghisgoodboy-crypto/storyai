"""Static checks for the workspace shell and navigation (no browser needed)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "static" / "js"

EXPECTED_SECTIONS = [
    ("chat", "Chat"), ("characters", "Characters"), ("locations", "Locations"),
    ("story", "Story"), ("scenes", "Scenes"), ("storyboard", "Storyboard"),
    ("continuity", "Continuity"), ("export", "Export"),
]


def read(path):
    return path.read_text(encoding="utf-8")


def test_navigation_lists_exactly_the_approved_sections_in_order():
    text = read(JS / "screens" / "workspace.js")
    found = re.findall(r'\{\s*key:\s*"([a-z-]+)",\s*label:\s*"([A-Za-z ]+)"', text)
    assert found == EXPECTED_SECTIONS


def test_workspace_navigation_labels_remain_visible_and_accessible_on_mobile():
    workspace = read(JS / "screens" / "workspace.js")
    styles = read(ROOT / "static" / "css" / "studio.css")
    assert "'aria-label':s.label" in workspace
    assert ".side-nav a span:last-child { display: inline; }" in styles


def test_there_is_no_settings_screen_anywhere():
    for path in list((ROOT / "static").rglob("*")) + list((ROOT / "templates").rglob("*")):
        if path.is_file():
            assert "settings" not in read(path).lower(), path.name


def test_every_script_on_the_page_exists_and_is_served(client):
    html = client.get("/").get_data(as_text=True)
    sources = re.findall(r'<script src="([^"]+)"', html)
    assert sources, "no scripts found"
    for src in sources:
        assert client.get(src).status_code == 200, src


def test_scripts_load_in_a_safe_order(client):
    html = client.get("/").get_data(as_text=True)
    names = [Path(s).name for s in re.findall(r'<script src="([^"]+)"', html)]
    order = lambda name: names.index(name)
    assert order("dom.js") < order("api.js") < order("state.js")
    # screens must be defined before the workspace that lists them, and app.js starts last
    assert order("characters.js") < order("workspace.js")
    assert order("locations.js") < order("workspace.js")
    assert names[-1] == "app.js"
    assert "chat.js" not in names and "coming-soon.js" not in names


def test_page_uses_no_inline_scripts_or_styles(client):
    # The Content-Security-Policy blocks inline code, so the page must not rely on any.
    html = client.get("/").get_data(as_text=True)
    assert not re.search(r"<script(?![^>]*\bsrc=)", html)
    assert " style=" not in html and "onclick=" not in html.lower()


def test_locations_screen_is_loaded_as_a_built_workspace_section(client):
    html = client.get("/").get_data(as_text=True)
    assert "/static/js/screens/locations.js" in html
    text = read(JS / "screens" / "workspace.js")
    assert "LocationsScreen.render" in text


def test_active_chat_and_secondary_memory_screens_are_wired():
    text = read(JS / "screens" / "workspace.js")
    for required in ["Api.sendChat", "Api.history", "Api.suggest", "Screens.memory", "Screens.proposals"]:
        assert required in text


def test_storyboard_generator_is_connected_to_api_and_existing_storyboard_screen():
    workspace = read(JS / "screens" / "workspace.js")
    api = read(JS / "api.js")
    assert "Generate and save storyboard" in workspace
    assert "Api.generateStoryboard(p.id,direction.value.trim())" in workspace
    assert "Storyboard generated and saved." in workspace
    assert "generateStoryboard:(p,direction)=>Api.request('POST',`/api/projects/${p}/storyboard/generate`" in api
    assert "Api.listShots(p.id,scene.id)" in workspace


def test_disabled_buttons_must_come_with_a_reason():
    dom = read(JS / "dom.js")
    assert "A disabled button needs a reason." in dom
    assert "node.disabled = true" in dom
    for path in (JS).rglob("*.js"):
        for call in re.findall(r"Dom\.disabledButton\(([^)]*)\)", read(path)):
            assert re.match(r'\s*"[^"]+"\s*,\s*"[^"]+"', call), f"{path.name}: {call}"
