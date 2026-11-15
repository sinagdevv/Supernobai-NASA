# TERRAWINDOW: 30-second demo storyboard

For the Space Apps "Link to Project Demo": a video of **30 seconds or less**, in English (or subtitled in English), hosted publicly with a link that needs no login
(see [SPACE_APPS_SUBMISSION.md](SPACE_APPS_SUBMISSION.md)). The structure follows the guide's own timing suggestions.

**Nothing here is invented footage.** Every shot is a screen recording of the running app, and every number on screen is a reproducible output
(source in the right-hand column). Record from the real app with the service running (start it as in the README); do not edit values, speed up a calculation
so it looks instant without saying so, or composite results.

**Recording setup:** 1440 x 900 window, browser tabs and bookmarks hidden (a full-screen or app-mode window), 100% zoom, Moon selected, first-visit guide dismissed, intro already seen. Pre-run the Layer 4 calculation once so the result is on screen (a fresh run takes about 25 to 30 seconds): record the click, cut to the finished result, and show a "calculation takes about 30 s" caption rather than hiding that it takes time.

| Time | Shot (real screen) | On-screen text | Voice-over | Number's source |
|---|---|---|---|---|
| 0:00-0:03 | Title card on the dark app background with the logo | **TERRAWINDOW** · team name · member names · challenge title (**TEAM TO FILL**) | "We're **[team]**. Our challenge: find Earth analogs for Moon and Mars bases." | n/a |
| 0:03-0:07 | Landing hero, planet switcher: click Moon, then Mars; the terrain ribbons morph | "Find the Earth. Test for the Moon." | "TERRAWINDOW: find the Earth, test for the Moon." | n/a (the hero profile is schematic; do not caption it as data) |
| 0:07-0:12 | Analog Explorer, Moon: world map with candidate markers; click a candidate; the card shows status and slope/roughness figures | "Earth candidates, measured against a lunar reference" | "It screens Earth terrain against real NASA lunar data." | Moon: NASA LOLA Site01 (5 m). Earth: ESA Copernicus DEM. The example sites are labelled illustrative in the app; keep that label visible |
| 0:12-0:17 | Comparison, "At a glance": slope, roughness, resolution groups for a candidate | "Criterion by criterion. No single score." | "Criterion by criterion: no single score." | Values as shown by the app for the chosen example site; the app labels them illustrative |
| 0:17-0:23 | Rehearsal Windows, Moon · Site01: show the finished result: elevation curve, class strip, one candidate window | "Computed with NASA SPICE · not independently validated" · "Site01, 7 days: 1 candidate window, 4.2 days" · "peak terrain shadow 26.4 %" | "NASA SPICE computes the sun and terrain shadows at the lunar south pole." | `POST /v1/rehearsal/evaluate`, Site01 at 40 m, 2026-12-14 to 12-21, 2 h step (84 samples): 1 window, 4.2 days, peak shadow 26.4 % |
| 0:23-0:27 | Mission assessment (Moon): the status "Indeterminate", 4 pass / 2 unverified claims | "Missing evidence is never a pass" | "Missing evidence is never counted as a pass." | Layer 5 on Site01: slope p90 19.91 deg (limit 20 deg) pass; illumination and shadow are unverified Layer 4 claims |
| 0:27-0:30 | Result card (white text on dark, from the research script output) | "r14c17, Arizona · 35.3614 N, 111.4239 W" · "matches Site01 on 25 of 35 criteria" · "slope 21.02 deg vs 20 deg limit: **not suitable**" · "A preliminary candidate, not a discovery" | "Our first candidate nearly matches, and we say exactly where it falls short." | `scripts/research_demonstration.py` (reproduced 2026-11-15): 342 patches, 5 candidates, 25 of 35 within tolerance, p90 21.02 deg vs 20 deg |

**Final frame (hold about one second, within the 30):** "Computed, not validated · NASA LOLA, MOLA, SPICE · ESA Copernicus · github.com/sinagdevv/Supernobai-NASA".

**Voice-over, about 70 words (reads in under 30 seconds):**
"We're [team]. Our challenge: find Earth analogs for Moon and Mars bases. TERRAWINDOW: find the Earth, test for the Moon. It screens Earth terrain against real NASA lunar data, criterion by criterion, with no single score. NASA SPICE computes the sun and terrain shadows at the lunar south pole. Missing evidence is never counted as a pass. Our first candidate nearly matches, and we say exactly where it falls short."

**Checks before uploading**
- Length is 30 seconds or less on the exported file, not just in the plan.
- Every on-screen number matches the source column. If the service was down while recording, the app shows an honest unavailable state: re-record rather than fill the gap.
- Keep the app's "computed", "illustrative" and "not validated" labels visible in the shots that carry them.
- No NASA logos, flags or mission identifiers anywhere (the guide forbids NASA branding in generated content; use none).
- Add English subtitles if anything is spoken in another language.
- If an AI voice or generated imagery is used, the guide requires it to be marked (a watermark on generated images and video, a note for audio); live screen recordings need no watermark.
- Test the public link in a private window.

**If you prefer slides (at most seven, title and intro included):** 1 title, team and challenge; 2 the problem (the lunar south-pole rehearsal need); 3 the six layers and the data (LOLA, MOLA, SPICE, Copernicus); 4 the interface (Explorer and Comparison screenshots); 5 Rehearsal Windows and Mission assessment (the real screenshots in `docs/media/`); 6 the r14c17 result and why it is not suitable; 7 limits, validation status and what comes next. Use the screenshots in `docs/media/` and the figures above.
