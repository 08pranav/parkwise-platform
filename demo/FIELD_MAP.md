# Field map (Discovery phase)

Found by running `node discover.mjs <role>` against the live site. Flutter web draws to a canvas, so there are no
`<input>`/`<button>` elements: switch on Flutter's accessibility tree (click `flt-semantics-placeholder`) and drive the
semantic nodes by role and name. Nodes only exist while visible, so scroll before tapping anything below the fold.

The "Try as ..." button in the demo banner is **not** in the semantic tree; click it by position
(top right of the banner: `x = viewportWidth - 62`).

| App | Viewport | After "Try as ..." (route) | Interactive nodes |
|---|---|---|---|
| Super admin `/super-admin/` | 1280x720 | `#/dashboard` | button "ONBOARD NEW SOCIETY"; tabs Dashboard, Societies, Refunds |
| Society admin `/admin/` | 1280x720 | `#/dashboard` | buttons "Dark mode", "Copy code", "Join Requests", "Manage Guards", "Owners"; tabs Dashboard, Slots, Guards, Owners, Bookings |
| Slot owner `/owner/` | 390x844 | `#/slots` | buttons "Notifications", "Sign out", "Add slot" |
| Guard `/guard/` | 390x844 | `#/home` | buttons "Dark mode", "Notifications", "Logout", "SCAN ENTRY", "SCAN EXIT" |
| Resident `/user/` | 390x844 | `#/home` | textbox "Where do you need parking?"; buttons "Use Current Location", "Pick on Map", "BOOKING DATE ...", "START TIME ...", "Duration ...", "Find Available Parking"; checkboxes "Use Duration", "Use End Time", "Car", "Bike"; tabs Home, Bookings, Profile |

## Resident flow (verified step by step)

1. Type `Bandra` in the destination box: five suggestions appear; the first (`Bandra | Gurunanak Marg ...`) is the Mumbai one.
2. Tap it: a "Selected Destination" card appears with coordinates.
3. Tap "Find Available Parking" (below the fold): societies are listed by distance (`Sea Breeze Residency`, `Lakeview Heights`).
4. Tap a society: its detail shows the booking window and the matching slots (button label starts with `AVAILABLE | P-04 | ...`).

## Guard

"SCAN ENTRY" / "SCAN EXIT" open the camera screen. There is no camera in headless mode, so use the keyboard icon
("Enter code manually") and paste the code the resident copied with "Copy code for manual entry".

## Known quirks

- Playwright's `fill()` does not drive Flutter text fields reliably; click the node, then use `keyboard.type`.
- The first request after the API has been idle can take about a minute (free tier); `openApp` waits for it.
