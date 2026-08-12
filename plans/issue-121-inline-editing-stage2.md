# Plan: True Inline Name Editing — Issue #121 Stage 2

## Problem with the Stage 1 approach

Session 180's "Edit Names…" opens a separate modal dialog. The mainworld name in
the result header is a genuine inline `QLineEdit`, but everything else — stars,
worlds, moons — requires opening the dialog window. That is form-based editing,
not inline editing.

True inline editing means clicking a name **where it already appears** in the
orbital survey table or stars table and editing it in place, like a spreadsheet
cell.

---

## Why inline editing is non-trivial here

The system card and world card are rendered as HTML strings via Jinja2 and
loaded into `QWebEngineView` via `setHtml()`. This creates two problems:

**Problem 1 — No JS↔Python bridge.**
The views have no mechanism to send data from JavaScript (running inside
Chromium) back to Python. Editing a cell in HTML and writing the result back
to the Python model requires setting one up from scratch.

**Problem 2 — The NoFocus fix (Session 172).**
All result `QWebEngineView` instances have `setFocusPolicy(Qt.FocusPolicy.NoFocus)`
to prevent Chromium's native `NSView` from stealing global keyboard focus away
from other Qt widgets (the mainworld `QLineEdit` name field, etc.). Making cells
inside those views `contenteditable` creates a direct conflict — editable HTML
cells need keyboard focus to work, which is exactly what NoFocus prevents.

These two problems push in opposite directions:
- Solving the bridge problem requires making cells interactive.
- Making cells interactive re-introduces the Session 172 focus-stealing bug.

---

## Three realistic approaches

### Option A — QWebChannel + contenteditable, retire NoFocus

The canonical Qt solution for bidirectional communication with a `QWebEngineView`.

**Bridge setup:**
```python
from PySide6.QtWebEngineCore import QWebEngineScript
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtCore import QObject, Slot

class _NameBridge(QObject):
    @Slot(str, str)
    def nameChanged(self, body_id: str, new_name: str) -> None:
        # route body_id → model object → update name
        # patch other DOM nodes via runJavaScript() rather than full setHtml()
        ...

channel = QWebChannel()
channel.registerObject("bridge", self._name_bridge)
view.page().setWebChannel(channel)
```

**qwebchannel.js delivery.**
Pages loaded via `setHtml()` have no URL, so the JS cannot `fetch('/qwebchannel.js')`.
The file must be injected as a `QWebEngineScript` that runs before page content:
```python
js_path = Path(PySide6.__file__).parent / "Qt" / "resources" / "qtwebchannel" / "qwebchannel.js"
script = QWebEngineScript()
script.setName("qwebchannel-bridge")
script.setSourceCode(js_path.read_text())
script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
view.page().scripts().insert(script)
```

**Template changes.**
Tag every editable name cell with `data-body-id` so Python knows which object
to update, and make the cell editable:
```html
<!-- system_card.html — orbital row -->
<td class="name-cell" contenteditable="true"
    data-body-id="orbit:{{ o.star_desig }}:{{ o.orbit_number }}"
    onblur="bridge && bridge.nameChanged(this.dataset.bodyId, this.textContent.trim())"
>{{ o.name or "—" }}</td>

<!-- moon row -->
<td class="name-cell" contenteditable="true"
    data-body-id="moon:{{ o.star_desig }}:{{ o.orbit_number }}:{{ moon.idx }}"
    onblur="bridge && bridge.nameChanged(this.dataset.bodyId, this.textContent.trim())"
>{{ moon.name or "—" }}</td>
```

Stars table needs a **Name column** added (currently absent from `star_rows` dict
and the table header) with `data-body-id="star:{{ s.designation }}"`.

**JS init block** (appended to every editable template):
```html
<script>
new QWebChannel(qt.webChannelTransport, ch => { window.bridge = ch.objects.bridge; });
</script>
```

**Avoiding full re-render.**
After the model update, DON'T call `setHtml()` (resets scroll, loses focus).
Instead patch only the relevant DOM nodes in the other view:
```python
safe = json.dumps(new_name)
other_view.page().runJavaScript(
    f"document.querySelectorAll('[data-body-id={json.dumps(body_id)}]')"
    f".forEach(el => el.textContent = {safe});"
)
```

**NoFocus conflict.**
Remove `setFocusPolicy(NoFocus)` from result views and fix the Session 172
focus-stealing bug properly instead:
- Set `QWebEngineView.setTabOrder()` so Tab never lands on the view.
- Or use `installEventFilter` on the `QWindow` to detect when Chromium's
  native subview steals focus and immediately return it to the last-focused
  Qt widget.

This is the most work but gives the most genuine inline experience.

---

### Option B — Overlay QLineEdit (no QWebChannel needed)

Keep the HTML read-only (NoFocus stays, no bridge needed). When the user
double-clicks a name cell, detect it via `QWebEngineView.page().runJavaScript()`
polling or a context-menu action, then position a native `QLineEdit` **over**
that cell as a floating overlay widget.

```
QWebEngineView                    QLineEdit (overlay)
┌─────────────────────┐          ┌──────────────────┐
│  Name    │ Star │ … │  →click→ │  Regina          │
│ [Regina] │  A   │ … │          └──────────────────┘
│  Efate   │  A   │   │
```

The overlay is positioned using `QWebEngineView.page().runJavaScript()` to
get the cell's bounding rect, then `QPoint` mapping to screen coordinates.

**Detection without QWebChannel:**
Inject a minimal JS snippet via `QWebEngineScript` that posts click coordinates
to Python via `Qt.InvokeMethod` — but this still needs SOME bridge. The simplest
version is a context-menu action ("Rename…") using `QWebEngineView`'s built-in
`contextMenuRequested` signal, which provides the element text at the cursor.

**Drawback:** Positioning an overlay over an HTML table cell is fragile — it
breaks on scroll, zoom, and theme changes. This approach is less "inline" than
it looks; it's closer to the dialog but without the separate window.

---

### Option C — Replace the HTML table with a native Qt widget

Implement the orbital survey table as a `QTreeWidget` with two columns — one
read-only (all the numeric/code columns, collapsible) and one editable (Name).
Double-clicking the Name cell gives a native Qt item editor — no bridge, no
focus issues, no JS.

**Drawback:** Completely replaces the Jinja2 HTML template for the orbital survey
table with Python widget construction code. The visual result will differ from
the web app and the poster. The rest of the card (stars table, profile rows)
would still be HTML or would also need to be ported.

This is practical only if the gen-ui card is being redesigned anyway.

---

## Recommendation

**Short term (issue #121 stage 2a):** Upgrade the "Edit Names…" dialog to be
**modeless** (`show()` instead of `exec()`), live-preview changes as you type
(call `_refresh_html_views()` on every `QLineEdit.textChanged`), and position it
adjacent to the result area rather than centred on the screen. This gives a
near-inline feel without any of the QWebChannel or focus-policy complexity, and
the Session 180 code is already most of the way there.

**Medium term (issue #121 stage 2b):** Implement Option A (QWebChannel). Fix the
NoFocus regression properly with an event filter rather than the blunt
`setFocusPolicy` call. This requires:
1. Finding `qwebchannel.js` in the PySide6 install (path varies by platform/version).
2. Adding `data-body-id` to all three template files.
3. Adding a Name column to the stars table in `_system_card_context()` and
   `system_card.html`.
4. A `_NameBridge` QObject wired to each result view's `QWebChannel`.
5. Careful testing of `contenteditable` + `blur` event handling in the themed
   templates (dark-mode CSS must not make the edit cursor invisible).

**Not recommended:** Option B (overlay widget) — fragile positioning with no
clear advantage over the modeless dialog.

---

## Body ID scheme

A flat colon-separated string is sufficient:

| Body | body_id format | Example |
|------|---------------|---------|
| Star | `star:<desig>` | `star:A` |
| Orbit (world/belt) | `orbit:<star_desig>:<orbit_number>` | `orbit:A:3` |
| Moon | `moon:<star_desig>:<orbit_number>:<moon_idx>` | `moon:A:3:0` |

The Python handler splits on `:` and resolves the target object by walking
`system.stellar_system.stars`, `system.system_orbits.orbits`, and
`orbit.detail.moons` — the same traversal `_EditNamesDialog.__init__` already does.

---

## Files to touch (stage 2b full implementation)

| File | Change |
|------|--------|
| `gen-ui/app.py` | `_NameBridge` class; `_inject_webchannel_script(view)`; register channel per result view; `_on_name_changed(body_id, name)` handler; DOM-patch helper; remove `NoFocus` + add focus event filter |
| `src/traveller_gen/templates/system_card.html` | `data-body-id` on name cells; Name column in stars table; JS init block |
| `src/traveller_gen/templates/world_card.html` | Same for standalone mainworld card |
| `src/traveller_gen/traveller_system_gen.py` | Add `"name"` key to `star_rows` dicts in `_system_card_context()` |
| `tests/test_genui_app.py` | Tests for `_NameBridge.nameChanged()`, `data-body-id` in rendered HTML, `star_rows` name key |
