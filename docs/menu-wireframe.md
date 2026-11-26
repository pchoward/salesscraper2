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
   this order: **Helmets · Goggles · Gloves · Protection · Backpacks**. Protection
   is pads, armor, impact shorts and wrist guards. Backpacks (owner, 2026-11-12;
   named 2026-11-26 the way the stores name it) is backpacks and hydration
   packs. MTB calls it **Packs & Hydration**, as bike shops do (Fanatik: "Packs &
   Hydration"; evo: "Hydration Packs & Bags"); Skate, Ski and BMX shops say
   "Backpacks". The store category stays Packs, and `?type=packs` links still
   open it. It has a **Size (liters)** filter: Under 15L, 15–24L, 25–34L, 35L+. Each pack shows where it's used (owner,
   2026-11-14): ski, snowboard and avalanche packs on Ski; hydration, hip,
   lumbar and protector packs on MTB; a sport's own brands (Shadow for BMX,
   Spitfire for Skate) on that sport. Everyday packs are shared within two
   pairs: the skate and BMX shops' (Jansport, Vans, Herschel) on Skate and
   BMX, the ski and bike shops' (Arc'teryx, Topo, Dakine Campus) on Ski and
   MTB. A heading
   with no deals isn't shown.
3. Inside Protection, the **Protects** filter (knees, elbows, wrists, hips,
   back & chest) narrows on every sport.
4. Stored data keeps the stores' categories. The page groups deals into
   headings when it is built, so renaming a heading never makes deals look
   "gone" and then "new".
5. When a heading is renamed or merged, its old link slug goes in `ALIASES`, so
   saved links keep opening the right heading.
6. Parts stay in their heading as a **Type** (owner, 2026-11-26), the way
   Powers, Source and Circuit file spares (Hub Parts next to Hubs, Brake Parts
   next to Pads). On MTB every parts heading has a Type filter: the thing itself
   first (Forks, Hubs, Cranks), then its parts (Fork parts, Hub parts,
   Drivetrain parts). Rules: `sports/mtb/kinds.py`. Pedals keeps its own Pedal
   type filter instead. On BMX, Product kind gains the spares the shops list
   separately (Fork parts, Crank parts, Headset parts, Stem parts, Pedal parts)
   and Brakes splits into Brakes, Brake kits, Levers, Cables, Pads and Brake
   parts (`sports/bmx/kinds.py`).
7. **Tools & Care** (owner, 2026-11-26) holds tools, pumps, bleed kits, lubes and
   cleaners from any heading, after the parts headings and before the gear, on
   MTB and BMX.
