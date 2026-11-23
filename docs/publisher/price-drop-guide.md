# What a price drop and a lowest observed price actually tell you

**Editorial draft for review.** Suggested path `/guides/price-drop-vs-lowest-observed/`. Description: Read the dates behind a price drop, check the tracked low, and decide whether to buy now or set an alert.

A **price drop** answers a question about movement. Was an offer cheaper than it was at an earlier observation? A **lowest observed price** answers a question about the range. Has ShredDeals recorded a lower price for this retailer listing before? The answers can differ even when the current sale is worth considering.

## Read the changes in date order

For the Baker Elissa Steamer Ephemera 8.25 × 31.875-inch deck at Skate Warehouse, ShredDeals recorded these USD prices in November 2026.

| Observation date | Listed price |
| --- | ---: |
| November 9 | $74.98 |
| November 10 | $64.98 |
| November 20 | $60.88 |

On November 10, the product cost $10.00 less than the November 9 observation, a reduction of about 13%. By November 20, an observation was another $4.10 below that November 10 price. Someone looking later at the tracked record would see that the earlier $10 drop was real, but $64.98 was $4.10 above the newer tracked low. The three points illustrate how a drop badge and a history chart can serve different decisions. They do not show what every buyer could purchase on every day between them.

## Decide what signal you need

- **Buying soon?** Check the current listing and the dated chart first. If you are comfortable paying a little more than the tracked low, the price difference can give you a dollar amount to weigh against waiting or losing your size.
- **Waiting for another reduction?** Choose a target that matters to you. Where an email alert is available, confirm it and check which event or price it watches. ShredDeals can notify you about events detected by its scans. Stock and short-lived sales can change before you act.
- **Comparing stores?** Check the same size and variant. A tracked low is tied to the observed listing and available history. It can miss prices before tracking began, untracked retailers, coupon savings, and sales that happened between scans.

Try this in [current Skate deals](https://shreddeals.com/?sport=skate) or [BMX deals](https://shreddeals.com/?sport=bmx). Open Quick View on a listing with history and compare its current price with both the previous observation and the tracked low. See [how ShredDeals works](https://shreddeals.com/how-it-works/) for the rules behind the Drop interval filter.

**Source for review** — `history.json` at commit `65bc07f`, daily observations keyed by the [Skate Warehouse listing](https://www.skatewarehouse.com/Baker_Elissa_Steamer_Ephemera_Deck/descpage-BKESEDK.html). Examples describe observed listed prices, excluding shipping and tax.
