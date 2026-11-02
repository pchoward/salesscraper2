# Dirt Jump complete-bike source research — US first

Research date: **2026-11-02**. Scope: new, orderable complete dirt jump bikes,
full-price and discounted, for the Explore pilot. International leads are
separate. No retailer adapter, classification, workflow or production setting
was changed. This is a research handoff for the ongoing Claude integration.

**Recommendation:** validate Albe's, Dan's Comp, Mike's Bikes and The Path first,
then diversify with US-market Commencal, BikesOnline/Polygon, Canyon and Verde.
Add more general bike shops only when they contribute a new model, genuinely
available size, or useful independent offer. Do not build a large store list that
mostly repeats the same few bikes or counts frames as completes.

## What was actually verified

There are **58 discovery leads** in the [source worksheet](dirt-jump/source-leads.csv),
not 58 verified sellers or live catalogs:

| Group | Leads | Meaning |
| --- | ---: | --- |
| First validation wave | 8 | Strongest evidence or proposed model-diversity value; current stock unverified |
| Second wave | 8 | More US channels/model families to validate |
| Dealer depth | 5 | Potential independent stock, sizes or builds; lower priority until confirmed |
| Manufacturer/regional references | 17 | Model/specification/dealer discovery, not automatically purchase offers |
| International/region-unverified | 20 | Separate regional inventory leads; no US shipping claim |

Evidence levels are recorded per row. Only **one specific complete-bike listing**
was found in the inspected saved report evidence: Mike's Bikes / Pivot Point.
Five category URLs were supplied by the owner in [issue #160](https://github.com/pchoward/salesscraper2/issues/160),
with Dan's complete-bike category added in the owner follow-up. Existing adapter
code also establishes some retailer integration paths. The rest are explicitly
**unverified research leads drawn from known model families and channels**;
they are not represented as newly inspected web pages.

### Important correction: Mike's Bikes is a real saved lead

The earlier #169 quick check of `catalogs/mtb/previous_data.json` found two DJ tire
matches and no complete-bike title matches. That was too narrow for source
research. `catalogs/mtb/report_inputs.json` also contains:

| Field | Saved observation |
| --- | --- |
| Product | Pivot Cycles Point |
| Retailer URL | https://mikesbikes.com/products/pivot-point-2027 |
| Explicit type | `BIKES AND FRAMES/BIKES - MOUNTAIN/DIRT JUMP/POINT` |
| Saved offer price | `1499.00` |
| Retailer reference/compare-at | `1899.00` — **not a historical observation** |
| Variant | `45495263166533`, `available: true` |
| Variant technical specs | Empty; do not invent reach, wheel size or travel |
| Report generated | `2026-11-02T17:21:20+00:00` |
| JSON locations | `changes["Mike's Bikes_Bikes"][50].item`, `digest.new_items[50]` |

This is saved report evidence at main commit
[`9c24ba4`](https://github.com/pchoward/salesscraper2/blob/9c24ba4057b78d33372505ea9ad531c4f65df4a6/catalogs/mtb/report_inputs.json),
not a fresh stock check or a complete assortment count. The saved offer has no
explicit currency field; confirm the US-market currency before promoting it to
Explore. The URL's `2027` is a merchant handle, not independently verified model-year
metadata. The two report occurrences describe one listing, not two products.
This lead should be coordinated with Claude's existing Mike's integration rather
than implemented as a competing scraper.

### Live-web limitation

The environment still has a restrictive retailer allowlist. Six fresh, bounded
`robots.txt` requests to Mike's, Commencal, Canyon, BikesOnline, City Grounds and
Jenson USA all failed at the **cloud proxy CONNECT layer with 403**, before any
retailer content or policy was reached. See [timestamped probe results](dirt-jump/access-probes-2026-11-02.json).
Prior #169 probes also failed for Albe's, Dan's, Verde, Woods Room and The Path.

This establishes an environment access blocker. It does **not** establish that a
retailer bans scraping, is down, is sold out, or lacks a DJ catalog. No search
engine/browser research tool is connected here. Current product ranges, prices,
stock counts, store platforms for new leads, shipping and retailer terms could
not be independently verified. The report is an evidence-backed starting point
plus a broad validation worksheet, **not a completed live-market census**.

## 1. Highest-value US validation queue

“Model targets” below are search/recall targets, not assertions that the retailer
currently carries them. Priority reflects evidence and potential assortment
breadth, not measured inventory size.

| Order | Source / starting point | Why investigate | Verification needed |
| --- | --- | --- | --- |
| 1 | [Albe's DJ category](https://www.albes.com/collections/dirt-jump-bikes) | Owner-supplied dedicated category plus an existing Shopify integration. Best early multi-brand category hypothesis. | Enumerate actual complete models/variants; distinguish frame SKUs; verify policy and terminal pagination. Existing BMX sale feeds are not full DJ inventory. |
| 2 | [Dan's Comp DJ bikes](https://www.danscomp.com/dirt-jump-mtb-bikes/c16114) | Owner-supplied complete-bike category and existing retailer-specific adapter. Complement to the Shopify approach. | Use bikes `c16114`, **not frames `c17909`**. Determine allowed category/product access and variant stock; do not force this through Shopify. |
| 3 | [Mike's Pivot Point](https://mikesbikes.com/products/pivot-point-2027) | Strongest concrete saved complete-bike evidence. Claude is already integrating the retailer. | Ask the existing integration to preserve the DJ type and full-price variants; confirm policy, actual stock and broader relevant inventory without duplicating a live crawl. |
| 4 | [The Path DJ bikes](https://www.thepathbikeshop.com/collections/dirt-jump-bikes) | Owner-supplied dedicated category; possible specialist dealer coverage. | Actual brands, complete/frame split, current available variants, shipping and platform still unknown. |
| 5 | [Commencal](https://www.commencal.com/) → US catalog → **Absolut** | Target a distinct brand family via its regional commerce channel. | US stock/fulfillment, full builds versus frames, model variants and region-specific currency. |
| 6 | [BikesOnline US](https://www.bikesonline.com/) → **Polygon Trid** | Distinct complete-bike family/channel rather than another copy of an existing dealer listing. | Current US Trid hardtail range; distinguish Trid ZZ slopestyle/full suspension; cart and size availability. |
| 7 | [Canyon US](https://www.canyon.com/en-us/) → **Stitched 360** | Another model family/channel to diversify the pilot. | Current US model availability; separate complete/frameset and any Stitched 720 slopestyle inventory. |
| 8 | [Verde DJ collection](https://verdebicycles.com/collections/dirt-jumpers) → **Radix** lead | Owner-supplied category; useful independent brand lead. | Exact current complete model, product type, regional fulfillment and available variants. |

An initial US pilot should be assembled from whichever of these actually passes
verification. This is **not** a recommendation to turn on all eight unverified
sources. Dedicated categories still need complete-bike eligibility checks.

## 2. US breadth and dealer depth

| Source | What to look for | Why it may help / caveat |
| --- | --- | --- |
| [Source BMX US](https://us.sourcebmx.com) | Explicit DJ complete inventory; NS/Radio search leads | Existing Shopify adapter reduces integration uncertainty. It currently reads BMX sale collections; those do not establish DJ coverage. US storefront must stay separate from UK/global stock. |
| [City Grounds](https://www.citygrounds.com/) | DJ complete search; Haro/GT/Mongoose recall targets | Potential alternate price/build segment. Large-wheel BMX, wheelie and city bikes must not be admitted based on 26-inch wheels alone. |
| [Jenson USA](https://www.jensonusa.com/) | Dirt Jump complete category; Marin Alcatraz lead | Existing research candidate, not a verified DJ inventory source. A result consisting only of a frame/fork adds no complete-bike coverage. |
| [Specialized US](https://www.specialized.com/us/en) plus dealers | P-series complete bikes and size/wheel variants | Manufacturer identification plus independently available dealer offers. Check shipping versus store pickup, and avoid assuming every model/year uses the same wheel diameter. |
| [YT US](https://us.yt-industries.com/) | Dirt Love | Potential distinct family. Verify active commerce, fulfillment and support before treating an old product page as a purchasable offer. |
| [Kona](https://www.konaworld.com/) | Shonky complete versus frame | Useful family lead, but current production, checkout route and dealer stock must be checked. |
| [Haro](https://harobikes.com/) | Steel Reserve / Thread family leads | Historical recall, not verified current model names or inventory. Distinguish rigid/suspension versions and unrelated BMX. |
| [Mongoose](https://www.mongoose.com/) | Fireball | Brand commerce lead; confirm exact build and actual merchant stock. |
| [Fanatik](https://www.fanatikbike.com/) | DJ complete/custom builds; Monk/PBJ search leads | Existing Shopify integration. Do not count a frame or an unfinished bike configurator as a stocked complete. Brand carriage is not verified here. |
| [The Lost Co](https://thelostco.com/) | Complete DJ builds versus components | Specialist discovery lead, lower priority until a real orderable complete is found. |
| [ERIK'S](https://www.eriksbikeshop.com/), [Incycle](https://www.incycle.com/), [Wheel World](https://www.wheelworld.com/) | Dealer availability for models such as P-series; search DJ explicitly | May add local stock, sizes or independent offers. Shipping, pickup and each dealer's actual current brands are unverified. |

**Woods Room** has an owner-supplied [DJ collection](https://woodsroombikeshop.com/collections/dj),
but its market and fulfillment were not verified. It remains in the
region-unverified queue, not counted as US inventory merely because it uses `.com`.

## 3. Model-family map: search broadly, admit narrowly

All families except the saved Pivot listing are discovery targets requiring
current official/retailer confirmation. This is a recall map, not a statement
that every family remains in production or that every listed version is a
complete DJ bike.

| Family / manufacturer reference | Discovery role and boundaries |
| --- | --- |
| [Pivot](https://www.pivotcycles.com/) **Point** | Saved Mike's complete-bike lead. Recheck merchant offer; obtain official specs separately. |
| [Commencal](https://www.commencal.com/) **Absolut** | Regional direct-commerce target; complete versus frame and exact selected build matter. |
| [Polygon via BikesOnline](https://www.bikesonline.com/) **Trid** | Hardtail DJ target. **Trid ZZ** belongs in a separate slopestyle decision if encountered. |
| [Canyon](https://www.canyon.com/en-us/) **Stitched 360** | Hardtail target; **720** slopestyle versions must not be silently mixed. |
| [Marin](https://www.marinbikes.com/) **Alcatraz** | Manufacturer/dealer discovery; manufacturer catalog does not by itself prove a purchasable offer. |
| [Specialized](https://www.specialized.com/us/en) **P-series** | Search P.1/P.2/P.3/P.4 where actually offered. Model/year and intended discipline determine youth/adult and wheel-size coverage. |
| [YT](https://us.yt-industries.com/) **Dirt Love** | Verify current regional availability and commerce/fulfillment rather than relying on historic launch pages. |
| [Kona](https://www.konaworld.com/) **Shonky** | Complete/frame split and current versus remaining-stock status need confirmation. |
| [Transition](https://www.transitionbikes.com/) **PBJ** | Owner-supplied recall target; verify current production versus legitimate remaining dealer stock. |
| [Fairdale](https://fairdalebikes.com/) **Hareraiser** | Verify current complete builds, rigid/suspension variants and actual retailer channel. |
| [Verde](https://verdebicycles.com/collections/dirt-jumpers) **Radix** | Owner category plus model-family search lead, not a verified available product. |
| [NS Bikes](https://nsbikes.com/) **Movement / Metropolis / Zircus** | Broad family recall; verify current model names, complete builds, distribution and US stock. |
| [Radio](https://radiobikes.com/) **Asura / Griffin** | Confirm current DJ complete range; exclude ordinary BMX/race products. |
| [DMR](https://www.dmrbikes.com/) **Sect / Rhythm** | Complete versions and frame-only products need explicit separation; US dealer availability is unverified. |
| [Chromag](https://chromagbikes.com/) **Monk** | Brand/dealer/custom-build routes may differ. Capture exact build definition and checkout readiness. |
| [Dartmoor](https://dartmoor-bikes.com/) **Two6Player / Gamer** | Model naming, frames versus factory completes and regional distribution must be confirmed. |
| [Rose](https://www.rosebikes.com/) **The Bruce** | Useful EU range lead; no assumption of US complete-bike delivery. |
| [Propain](https://www.propain-bikes.com/) **Trickshot** | Check current regional model and orderability before assigning US coverage. |
| [GT](https://gtbicycles.com/) **La Bomba**; [Haro](https://harobikes.com/) **Steel Reserve / Thread**; [Mongoose](https://www.mongoose.com/) **Fireball** | Historical/common recall targets. Storefront existence, current production, dealer remaining stock and fulfillment are separate facts. |
| [Giant](https://www.giant-bicycles.com/us) **STP**; [Norco](https://www.norco.com/) **Rampage / Ryde** | Verify exact model/year and intended discipline. Youth/geared/trail variants or similar names are not automatic DJ eligibility. |
| [Octane One](https://octane-one.com/) **Melt**; [Cube](https://www.cube.eu/) **Flying Circus**; [Scott](https://www.scott-sports.com/) **Voltage YZ** | Extra regional/historical recall. Generic **Voltage** alone is unsafe: the name can identify unrelated bikes. |

Do not prioritize frame-oriented names such as Trek Ticket, Evil Faction,
S&M DJ/Big Jumper or aftermarket DJ frames as complete-bike supply without an
actual merchant complete build. The owner mentioned S&M as a recall target in
#160; that is not evidence of a currently orderable factory complete. Dealer
custom builds can qualify later when their complete configuration, price and
stock are explicit.

## 4. International leads — separate from US coverage

These are unverified source leads, not inspected catalogs or shipping promises.
Use them first for model discovery; enable regional offers only after separate
market/currency and fulfillment checks.

| Region | Source leads | What to validate |
| --- | --- | --- |
| UK | [Source BMX](https://www.sourcebmx.com/), [Alans BMX](https://alansbmx.com/), [Crucial BMX](https://crucialbmxshop.com/), [Custom Riders](https://www.customriders.com/) | Specialist DJ assortment, complete/frame split, VAT treatment, actual dispatch and delivery destinations. |
| UK | [Winstanleys Bikes](https://winstanleysbikes.co.uk/), [Tredz](https://www.tredz.co.uk/), [Leisure Lakes](https://www.leisurelakesbikes.com/) | Additional complete-bike offers versus stock only available in selected stores. |
| EU | [26Bikes](https://26bikes.com/), [Bike Mailorder](https://www.bike-mailorder.de/) | Prioritize specialist model discovery, including NS/Dartmoor/Octane One search leads; actual carried brands remain unverified. |
| EU | [Bike-Discount](https://www.bike-discount.de/), [BIKE24](https://www.bike24.com/), [bike-components](https://www.bike-components.de/), [Alltricks](https://www.alltricks.com/) | Orderable completes, export restrictions, merchant of record, taxes and shipping; a components-heavy result is not a useful complete-bike source. |
| Canada | [Lama Cycles](https://www.lamacycles.com/), [Dunbar](https://www.dunbarcycles.com/), [The Inside Line](https://www.theinsideline.ca/) | Regional complete/custom-build supply, dealer versus wholesale roles, CAD currency and cross-border freight. |
| Australia | [LUXBMX](https://www.luxbmx.com/), [Pushys](https://www.pushys.com.au/), [BikesOnline AU](https://www.bikesonline.com.au/) | Actual DJ completes, regional domain/catalog, AUD prices and complete-bike shipping restrictions. US and AU BikesOnline must not share stock. |
| Unknown until checked | [Woods Room DJ](https://woodsroombikeshop.com/collections/dj) | Establish geography and shipping before assigning a regional catalog. |

Do not combine USD, CAD, GBP, EUR or AUD into one cheapest-price ordering without
an explicit conversion/landed-cost design. An EU model catalog can identify a
missing family while still contributing **zero US-buyable offers**. Legacy search
results, discontinued-store pages and sold-out product pages can aid discovery,
but cannot count as current inventory.

## 5. How to get a genuinely wide range efficiently

### Validate in two rounds

**Round A — breadth:** verify the first eight sources, adding one at a time.
For each source, record complete product/model families, selectable in-stock
variants, regular/sale mix, unknown stock, missing specs, terminal pagination,
US delivery/pickup restrictions and retrieval cost. Choose additional sources by
**incremental model/build/size coverage**, not just their raw product count.

**Round B — gaps:** compare the observed inventory with the model-family map.
For each absent family, follow the manufacturer's official dealer locator or
regional sales channel. Validate targeted merchant listings; do not crawl every
MTB product at every national retailer. A new dealer with only the same model and
size still adds an independent offer, but not a new model family.

A model-family map helps catch missing products; it must not force admission of
unrelated products or fabricate availability. Missing families might be genuinely
discontinued, unavailable in the US, frame-only, or entirely sold out.

### Keep four counts separate

1. **Unique model/build families** — coverage breadth, after reliable manual or
   explicit manufacturer identification; no fuzzy auto-merge required.
2. **Retailer product listings** — different sellers/builds remain distinct.
3. **Verified available variants** — the actual orderable size/color/build and
   its matching price; unknown stock is not availability.
4. **US-buyable offers** — stock plus verified fulfillment to the selected market;
   local pickup and overseas-only listings are labeled separately.

Model matching is a research aid, not permission to merge provider product or
variant identities. Keep merchant IDs/variants/region/currency stable; never merge
price histories merely because titles look similar. Report the number of
verified sources and their completion, not “all dirt jumpers everywhere.”

### Promotion checklist for Claude / the pilot

For each candidate, supply a small evidence packet:

* canonical retailer origin and selected regional storefront;
* retailer terms/robots review, allowed exact category/feed/product URLs and date;
* one verified complete product, provider product/variant IDs and retailer URL;
* explicit DJ and complete-bike evidence, plus frame/component exclusion examples;
* actual price/currency, optional genuine compare-at, stock confidence and shipping;
* selected variant specs, with unknown values left unknown;
* terminal-page/completeness evidence and counts, including full-price products;
* request/time/byte cost and a reproducible fixture captured under permitted access.

Existing adapters already establish Shopify handling for Albe's, Source US,
Mike's and Fanatik. Their existing **sale collections** must not be used as proof
of full-price completeness. Dan's has a separate adapter; new sources' platforms
are unverified. Reuse Claude's shared capture and caches where appropriate,
without altering Deals sale gates or running overlapping retailer jobs.

## 6. Access needed to finish the live investigation

The first-wave origins to permit through the **supported environment network
configuration** are:

```
www.albes.com
www.danscomp.com
mikesbikes.com
www.thepathbikeshop.com
www.commencal.com
www.bikesonline.com
www.canyon.com
verdebicycles.com
```

Add redirect/region hosts only when an actual response establishes they are
needed. Broader worksheet hosts can be allowed in later rounds. Network access
is distinct from retailer permission, and saving a draft alone does not apply
access to the running environment. No allowlist, repository selection, approval
flag or production configuration was changed during this research.

Until that access is available, the strongest concrete handoff is the saved
Mike's Pivot Point, the owner-supplied dedicated category URLs, the existing
adapter evidence, and the explicitly unverified source/model worksheet. Live
breadth, inventory counts, shipping and policy verification remain outstanding.
