# Running on macOS — Gatekeeper

Because the Traveller World Generator is not signed with an Apple Developer
certificate, macOS Gatekeeper may block both extraction of the archive and
the first launch of the app. The instructions below cover both situations.

---

## Part 1 — Extracting the archive

macOS may refuse to extract `TravellerWorldGen-macos.zip` with the error
*"unable to expand"* or silently produce an empty folder. This happens because
Gatekeeper quarantines the downloaded zip before it is opened.

### Option A — Remove quarantine from the zip first (recommended)

Run this in Terminal before double-clicking the zip:

```bash
xattr -dr com.apple.quarantine ~/Downloads/TravellerWorldGen-macos.zip
```

Then double-click the zip to extract it normally.

### Option B — Extract using Terminal

```bash
cd ~/Downloads
unzip TravellerWorldGen-macos.zip
```

The `unzip` command is not subject to Gatekeeper and will extract the app
without error.

---

## Part 2 — Opening the app

---

## Method 1 — Right-click to open (easiest)

1. Unzip `TravellerWorldGen-macos.zip`.
2. **Right-click** (or Control-click) `TravellerWorldGen.app`.
3. Select **Open** from the context menu.
4. A dialog will appear warning that the app is from an unidentified developer.
   Click **Open**.

macOS remembers your choice — subsequent launches work normally by
double-clicking.

---

## Method 2 — System Settings

If the right-click method does not show an **Open** option:

1. Attempt to open the app by double-clicking. macOS will block it and show a
   warning dialog — click **Done**.
2. Open **System Settings → Privacy & Security**.
3. Scroll down to the **Security** section. You will see a message:
   *"TravellerWorldGen.app was blocked because it is not from an identified
   developer."*
4. Click **Open Anyway**.
5. Authenticate with your password or Touch ID when prompted.

---

## Method 3 — Terminal (advanced)

If neither method above works, remove the quarantine attribute manually:

```bash
xattr -dr com.apple.quarantine /path/to/TravellerWorldGen.app
```

Replace `/path/to/` with the actual location of the app (e.g.
`~/Downloads/TravellerWorldGen.app`). After running this command the app will
open normally.

---

## Why does this happen?

Apple Gatekeeper blocks apps that are not signed with an Apple Developer ID
certificate and notarized by Apple. Obtaining and maintaining a Developer ID
requires an annual Apple Developer Program membership. This is a known
limitation of the current release; code signing and notarization are planned
for a future version.
