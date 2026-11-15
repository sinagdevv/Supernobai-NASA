# TERRAWINDOW: NASA Space Apps Challenge 2026 submission draft

Ready to paste into the Project page. Every statement comes from this repository or from sources checked on 2026-11-15
(see [SCIENTIFIC_REFERENCES.md](SCIENTIFIC_REFERENCES.md)). Field names follow the official
[Project Submission Guide](https://www.spaceappschallenge.org/resources/project-submission-guide/), read on 2026-11-15.
The submission form itself needs a team login and was not opened, so compare each field with it. Items marked
**TEAM TO CONFIRM** cannot be established from the repository.

**Deadline, from the guide:** project submission closes **Sunday, November 15 at 11:59 p.m., in the time zone of your team's Local Event**
(Universal Event teams: the local time of the Team Owner's area of residence). Save progress often; changes are visible only to the team until the project is submitted.

**Demo rules, from the guide:** a video of **30 seconds or less**, or a deck of **at most seven slides** (title and intro slides included), hosted on an external site with a public link that needs no login, password or permission, **in English** (a video in another language needs English subtitles). Projects that exceed these limits are not eligible for Global Judging. Judging criteria: Impact, Creativity, Validity, Relevance, Presentation. A storyboard is in [DEMO_STORYBOARD.md](DEMO_STORYBOARD.md).

---

## Challenge

Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars ([challenge page](https://www.spaceappschallenge.org/2026/challenges/permanent-moon-base-locations-and-mars/)). The challenge asks teams to use open Earth, Moon and Mars data from NASA and other space agencies to identify and characterize terrestrial analogs, and to present findings as a map, visualization or other tool.

## Project Name

TERRAWINDOW

## High-Level Project Summary

TERRAWINDOW helps researchers identify, compare and assess Earth terrain as an analog for the Moon and Mars. It measures NASA LOLA (Moon) and MOLA (Mars) terrain beside ESA Copernicus Earth terrain criterion by criterion, computes SPICE sun geometry and terrain shadows, and assesses candidates against user-set mission criteria. It shows what each result does and does not establish: nothing is scored as a single "similarity", missing evidence is never a pass, and no result is claimed as observationally validated.

*Why it matters:* analog sites are "not entirely well characterized" (the challenge text). TERRAWINDOW makes the characterisation reproducible and its limits visible.

## Link to Project Demo

**TEAM TO ADD**: a public link to a video of 30 seconds or less (or up to seven slides). Storyboard: [DEMO_STORYBOARD.md](DEMO_STORYBOARD.md).

## Link to Final Project

- Code: https://github.com/sinagdevv/Supernobai-NASA
- Interface: https://terrawindow.vercel.app/ (the frontend is permanent; its scientific calculations run on a developer machine through a temporary tunnel and are available only while a demonstration is running. Otherwise the site shows a "service unavailable" state and no measurements. Judges who need the live calculations should be told when it is running. A new site may be blocked by a judge's web filter; the guide suggests an optional FortiGuard classification request.)

## Detailed Project Description

**What it does.** A rover that will drive near the lunar south pole needs somewhere on Earth to rehearse, and slope and roughness only compare where the data can resolve them. TERRAWINDOW works through that in the open:

1. Retrieves and checksums NASA and ESA terrain data (Layer 2).
2. Measures slope, roughness and relief at stated scales; compares a lunar or Martian reference with Earth candidates per criterion; screens a region for candidate patches (Layer 3).
3. Computes solar elevation, azimuth, terrain illumination and shadow, and candidate rehearsal windows with NASA NAIF SPICE (Layer 4).
4. Assesses a candidate against user-set criteria with explicit evidence status: pass, fail, unverified claim, indeterminate, not assessed (Layer 5).
5. A separate reporting service stores runs (Layer 6, not connected to the live interface).

Every result carries its dataset, scale, provenance and limitations, and is labelled computed, illustrative, insufficient evidence or service unavailable. Moon is the primary scope; Mars is a regional, data-backed experience (Jezero, MOLA).

**Example result** (reproduce with `backend/geoprocessing/scripts/research_demonstration.py`). Screening 342 patches of the San Francisco Volcanic Field, Arizona, against ranges derived from LOLA Site01 left five candidates. The best, patch r14c17 at 35.3614 N, 111.4239 W (5.5 km box), matches the lunar site on 25 of 35 criterion comparisons (mean slope 9.8 vs 12.3 degrees; roughness 0.88 vs 0.86 m). Its 90th-percentile slope is 21.02 degrees against an example limit of 20 degrees, so the assessment is "not suitable" under that assumed limit, although the screening tolerance (15 to 25 degrees) accepted it. Layer 4 finds about one hour of low sun per day there, against days at the lunar pole. It is a preliminary characterised candidate, not a discovery and not a confirmed analog.

**How it works / tools.** React 19, TypeScript, Vite, Tailwind, MapLibre for the interface; Python, FastAPI, rasterio, NumPy, SciPy and pyproj for retrieval and terrain processing; SpiceyPy and Numba for solar geometry; PostgreSQL/PostGIS for the reporting layer; Vercel for the frontend and a Cloudflare tunnel with a restricted gateway for the temporary live backend.

**What has and has not been validated.** Solar elevation was cross-checked against independent calculations (NOAA/Meeus for Earth; SPICE with a second orientation model for the Moon; Mars24 and plain SPICE for Mars). Terrain code was tested on synthetic slopes of known value, and the Jezero raster was verified byte for byte against the NASA PDS source. **No result is observationally validated**: no illumination, shadow or terrain output has been compared with observations. Mission thresholds are assumptions. The Mars coordinate origin and NAIF centre are not tied. Coarse data cannot show rover-scale hazards. Layer 6 is not connected to the interface.

**Benefit and aim.** A transparent, reproducible way to screen and characterise Earth analog candidates and to see what evidence is still missing before a site is trusted.

## Use of Super Intelligence (SI)

*(Not shown to judges; judges do see SI indicators inside the project.)*

**Answer: Yes.** TERRAWINDOW was developed with AI coding assistants, chiefly Claude Code (Anthropic). Other team members' AI tools: **TEAM TO CONFIRM**.

**How it was used:** writing and refactoring application code (the frontend and the integration of the backend layers), debugging, user-interface and accessibility implementation, writing and running automated and browser tests, running independent cross-checks of numerical results, writing documentation and the reference list, and checking citation metadata against live records.

**What SI was not:** a source of scientific data (the data come from NASA, ESA/Copernicus and NAIF, with recorded identifiers and checksums); a source of numerical results (they come from the repository's own code, tested as described above); or any observation or validation of illumination, shadows or terrain, of which there is none. No output was generated or verified by NASA. There is no NASA branding in the interface or documentation, and the screenshots are captures of the running interface, not generated images.

**The idea:** the concept (using measured Earth terrain to find analogs for lunar and Martian experiments) comes from the team's original project proposal; SI tools were used to implement and document it. **TEAM TO CONFIRM this statement**: the guide says SI should not be used to devise the idea.

**Acknowledgement in code and data (required by the guide):** this section, the README's "AI assistance disclosure" and [SCIENTIFIC_REFERENCES.md](SCIENTIFIC_REFERENCES.md#8-ai-assistance-disclosure) state the use in descriptive text. The repository's Git history carries no AI co-author trailers, by project policy. **TEAM TO CONFIRM** whether the form or the guide expects a marker inside the code files themselves.

## NASA Data

| Resource | What was used | Where | Link |
|---|---|---|---|
| LOLA high-resolution south-pole topography (NASA PGDA; Lunar Reconnaissance Orbiter) | Site01 (Connecting ridge), 5 m surface model, 16 x 16 km | Lunar reference terrain; lunar illumination terrain | https://pgda.gsfc.nasa.gov/products/78 |
| MGS MOLA MEGDR topography (NASA PDS Geosciences Node) | 128 ppd tile `megt44n000hb` (Jezero region, 463 m); 32 ppd global topography, observation counts and radii (1.85 km) | Martian terrain; Mars-Earth comparison; Mars solar geometry | https://pds-geosciences.wustl.edu/missions/mgs/megdr.html ; DOI 10.17189/1z1b-kv84 |
| NAIF SPICE kernels (NASA/JPL) | de440s, mar099s, naif0012, pck00011, mars_iau2000_v1, moon_pa_de440, moon_de440 frame kernel, Earth orientation kernel | Sun position and body orientation | https://naif.jpl.nasa.gov/naif/ |

Exact product identifiers, versions, checksums and frames: [SCIENTIFIC_REFERENCES.md](SCIENTIFIC_REFERENCES.md#1-data-actually-used). Not used: NASA Earthdata, NASA's lunar polar illumination maps (suggested for future validation), the enhanced south-pole topography. Problem-context material (not data): NASA Technical Reports Server 20240011393 and 20250003890 and the NESC article on the visual experience of astronauts at the lunar south pole.

## Space Agency Partner Data and Other References

ESA is a 2026 Space Agency Partner. The guide asks for **all** data, resources and tools used, including code, text and images, even if open source.

**Partner data**

| Resource | Provider | Use |
|---|---|---|
| Copernicus DEM GLO-30 (surface model, 30 m) | ESA / Copernicus programme (credit line names DLR and Airbus); AWS Open Data copy | Earth candidate terrain (three Arizona and California regions). Derived products carry: "produced using Copernicus WorldDEM-30 (c) DLR e.V. 2010-2014 and (c) Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved" |

**Other data and imagery**

| Resource | Use |
|---|---|
| Esri World Imagery and Dark Gray Canvas (Esri, Vantor, Earthstar Geographics, HERE, Garmin, OpenStreetMap contributors and the GIS user community), with "Powered by Esri" | Analog Explorer map display only; no scientific result depends on it |
| OpenTopoMap (CC-BY-SA) and OpenStreetMap contributors | Topographic map display |
| Terrain Tiles (Mapzen, AWS Open Data) | Optional relief shading on the map |
| ESA WorldCover | **Not used** in any result (optional code path only) |

**Software, fonts and tools** (all unmodified; licences in [SCIENTIFIC_REFERENCES.md](SCIENTIFIC_REFERENCES.md#7-licences-and-attribution)): React, Vite, TypeScript, Tailwind CSS, Motion, MapLibre GL JS, Recharts, lucide-react, Geist, Geist Mono and Newsreader fonts (Fontsource); Python, FastAPI, Uvicorn, Pydantic, rasterio, NumPy, SciPy, pyproj, Pillow, SpiceyPy, Numba, httpx, psycopg, fpdf2, PostgreSQL/PostGIS; Vercel and Cloudflare Tunnel for hosting; Claude Code (see above). Text and images in the interface were written for this project; the original TERRAWINDOW logo is the team's own. **TEAM TO CONFIRM** that no other text, image or code from outside the team was used.

**Citations:** Barker et al. (2021) for LOLA; the PDS record (Smith, Neumann, & Hughes, 2026) for MOLA; ESA (2024) for Copernicus DEM; Acton (1996) and Acton et al. (2018) for SPICE. Full APA list: [SCIENTIFIC_REFERENCES.md](SCIENTIFIC_REFERENCES.md#9-references-apa-7th-edition).

## Licensing, team and pre-existing work

- The repository has **no licence file**; nothing in it is licensed as open source. Third-party materials keep their own terms. TERRAWINDOW is an independent entry, not affiliated with or officially endorsed by NASA, ESA, the U.S. Geological Survey or any data provider.
- The repository's Git history begins on 2026-11-13 and holds the work of four authors: Gabriel John Solomon (Layers 2 and 3), Monodyp (Layers 4 and 5), Alvin187187 (Layer 6) and sinagdev (frontend and integration). **TEAM TO CONFIRM** that all four are confirmed participants of the same Local Event, which the guide requires for award eligibility.
- Third-party open-source libraries and public datasets are the only pre-existing components the repository records. Any earlier team work (proposal text, earlier prototypes kept outside this repository): **TEAM TO DECLARE.**

## Known limitations (for judges)

No observational validation; thresholds are assumptions; one lunar site, one Martian region and three Earth regions; Earth analogs reproduce terrain statistics and sun angle only, not gravity, vacuum, regolith or thermal conditions; MOLA, Copernicus and LOLA cells cannot resolve rover-scale hazards; the live scientific backend needs the demonstration machine and tunnel to be running.
