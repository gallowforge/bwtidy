# bwtidy: the README's look

**Family.** The README is drawn in Glass, the language of the gallowforge profile: real output as frosted-glass windows floating in a dark, softly lit space, with the one line that matters lifted out of its window toward you. aih, agent-guardrails and bwtidy share the renderer, the type and the composition grammar; each has its own accent light.

**The idea.** Find everything, change nothing until you say so. The hero shows the end of a real audit with its last line lifted out: 13 items flagged, nothing changed. Each panel lifts the proof of one step: the risky group, the checklist summary, the merge integrity check, the four fields the model sees, the byte-for-byte verify.

**Accent.** Teal, the colour of "Nothing was changed": `#6fe6d8` on dark windows, `#0b7d72` on light pages, and a pool of `#12907f` light behind the glass. Amber appears once, where the audit itself warns about a critical account.

**Type.** Geist for headings and copy, Geist Mono for every line of output.

**Themes.** Each image has a dark version (on GitHub's `#0d1117`) and a light one (on `#ffffff`), with phone crops; the edges dissolve into the page. Terminals stay dark in both themes; `cleanup.md` and the model request are dark pages in the dark version and light pages in the light one.

**Truth.** `scripts/readme_visuals.py` runs the scripts on the synthetic vault in `examples/` through the fake `bw` and the stand-in model, and refuses to run if `bw` is anything but the fake. Their output is written word for word into `docs/readme/src/tex/`; long reports are shown the way a terminal window would, scrolled to the top or the bottom. Every number in the copy is counted from the scripts, the tests or that output.

**Rebuild.** `python3 scripts/readme_visuals.py`. The renderer is `docs/readme/src/glass/`: `scene.js` (three.js compositor), `grammar.js` (light, glass, type and compositions), `layouts.js` (this README's scenes) and `glass.cjs` (textures, scenes and WebP).
