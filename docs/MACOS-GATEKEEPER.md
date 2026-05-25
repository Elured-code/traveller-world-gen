# Running on macOS — Gatekeeper

Because the Traveller World Generator is not signed with an Apple Developer
certificate, macOS Gatekeeper will block it from opening on the first launch.
There are two ways to allow it.

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
