# Medium Banner Prompts — Quilt Series

Text-to-image prompts for the 4 article thumbnails. Generate each at **16:9**
(Medium feature image ~1500×750 / 2:1 also fine — crop to taste), then overlay
the **Quilt logo** in the reserved clear corner and add the article title text
in your editor. Prompts deliberately bake in **no text** (image models render
text badly) and leave **negative space** for the logo.

All four share the **Aurora** palette so the series reads as one set:
slate near-black `#0B0F17`, gradient **teal `#2DD4BF` → indigo `#6366F1` → violet `#A855F7`**.

---

## Shared style spine (reused in every prompt)

> Dark editorial tech banner, near-black slate background #0B0F17, Aurora color
> gradient flowing from teal #2DD4BF through indigo #6366F1 into violet #A855F7,
> soft volumetric glow, faint dot-grid canvas texture, clean empty negative space
> in the upper-left third for a logo, modern minimal vector illustration, crisp
> geometric shapes, premium SaaS aesthetic, subtle depth, no text, no words, no
> letters, 16:9 wide banner.

---

## Banner 1 — Meet Quilt (intro: CSV → filter → Parquet)

```
Dark editorial tech banner, near-black slate background #0B0F17, Aurora gradient
flowing teal #2DD4BF into indigo #6366F1 into violet #A855F7, soft volumetric glow,
faint dot-grid canvas texture. Centerpiece: a sleek node-based data pipeline on a
dark canvas — three glowing rounded rectangular nodes connected left to right by
luminous flowing curved wires, a small data table icon entering on the left and a
neat stacked-file icon exiting on the right, gentle particles streaming along the
wires. A subtle 2x2 patchwork of softly glowing tiles woven into the background.
Clean empty negative space in the upper-left for a logo. Modern minimal vector
illustration, premium SaaS aesthetic, crisp geometry, no text, no words, no
letters, 16:9 wide banner.
```

## Banner 2 — Taming Dirty Data (validation + dead-letter)

```
Dark editorial tech banner, near-black slate background #0B0F17, Aurora gradient
teal #2DD4BF to indigo #6366F1 to violet #A855F7, soft glow, faint dot-grid texture.
Centerpiece: a stream of glowing data particles flowing into a translucent funnel /
sieve node that SPLITS into two diverging luminous paths — one clean bright teal
stream continuing forward into an orderly grid, and one dimmer red-violet stream
of broken, jagged, irregular fragments diverting downward into a small quarantine
bin. Visual contrast of order vs chaos, clean vs rejected. Clean empty negative
space upper-left for a logo. Modern minimal vector illustration, crisp geometry,
premium aesthetic, no text, no words, no letters, 16:9 wide banner.
```

## Banner 3 — From Files to a Warehouse (Postgres upsert)

```
Dark editorial tech banner, near-black slate background #0B0F17, Aurora gradient
teal #2DD4BF to indigo #6366F1 to violet #A855F7, soft volumetric glow, faint
dot-grid texture. Centerpiece: stacks of glowing document/file cards on the left
flowing through luminous curved pipes into a large glowing cylindrical database
stack on the right, the cylinder lit with concentric Aurora rings; near the
junction, two overlapping arrows forming a circular merge/sync symbol to suggest
upsert (update + insert) with no duplicates. Sense of data consolidating into a
single source of truth. Clean empty negative space upper-left for a logo. Modern
minimal vector illustration, crisp geometry, premium SaaS aesthetic, no text, no
words, no letters, 16:9 wide banner.
```

## Banner 4 — Customer Segmentation with RFM

```
Dark editorial tech banner, near-black slate background #0B0F17, Aurora gradient
teal #2DD4BF to indigo #6366F1 to violet #A855F7, soft glow, faint dot-grid texture.
Centerpiece: a scatter of many small glowing dots that organize into FOUR distinct
clusters, each cluster a different Aurora hue (teal, blue, indigo, violet), with
faint connecting halos grouping them; beside the clusters, a small set of ascending
glowing quartile bars (four steps) suggesting scoring and ranking. Sense of raw
points resolving into meaningful customer segments. Clean empty negative space
upper-left for a logo. Modern minimal vector illustration, crisp geometry, premium
analytics aesthetic, no text, no words, no letters, 16:9 wide banner.
```

---

## Tips when generating

- **Aspect:** ask for 16:9 / landscape. Medium crops feature images to ~2:1, so keep the subject centered-right and the logo zone upper-left.
- **If text leaks in:** add `no text, no words, no letters, no typography, no labels` (already included) or regenerate — models occasionally ignore it.
- **Logo overlay:** place the Quilt mark in the reserved upper-left clear area; add the article title in your own editor (Figma / Canva / Photopea) so the type stays sharp.
- **Series consistency:** keep the shared style spine identical across all four; only swap the centerpiece sentence. That's what makes them look like one set.
