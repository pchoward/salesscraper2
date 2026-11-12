# Menu wireframe

The map of every sport's menu: headings, the types inside each, and their
filters. **Change the wireframe first, then the code.**

- Live page (owner's view): https://claude.ai/artifact/8reCCQ41F9dnzBQAT8CX5A
- Copy in the repo: [`menu-wireframe.html`](menu-wireframe.html). Open it in a browser. Republish the artifact from it after editing.
- Code: `sports/headings.py` (`HEADINGS`, `GEAR`, `ALIASES`) and Skate's `PART_ORDER` in `page.py`.

## Rules (owner, 2026-11-07)

1. A heading is a thing to shop for. Types inside it (ski type, hub vs rim)
   are filters or chips, not more headings, so the menu stays short on a phone.
2. The gear at the bottom of every menu uses the same names on every sport, in
   this order: **Helmets · Goggles · Gloves · Protection · Packs**. Protection
   is pads, armor, impact shorts and wrist guards. Packs (owner, 2026-11-12) is
   backpacks and hydration packs: general brands show on every sport's tab,
   wherever they're sold; packs from a sport's own brands (Shadow for BMX,
   Spitfire for Skate) and avalanche packs (Ski) only on that sport. A heading
   with no deals isn't shown.
3. Inside Protection, the **Protects** filter (knees, elbows, wrists, hips,
   back & chest) narrows on every sport.
4. Stored data keeps the stores' categories. The page groups deals into
   headings when it is built, so renaming a heading never makes deals look
   "gone" and then "new".
5. When a heading is renamed or merged, its old link slug goes in `ALIASES`, so
   saved links keep opening the right heading.
