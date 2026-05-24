# HM3 Stat Mappings

Use these formulas for player aggregate stats.

- Hands: `SUM(totalhands)`
- bb/100: `SUM(totalbbswon) / SUM(totalhands) * 100`
- VPIP: `SUM(vpiphands) / SUM(couldvpip) * 100`
- PFR: `SUM(pfrhands) / SUM(couldpfr) * 100`
- VPIP/PFR gap: `VPIP - PFR`
- 3Bet: `SUM(didthreebet) / SUM(couldthreebet) * 100`
- Squeeze: `SUM(didsqueeze) / SUM(couldsqueeze) * 100`
- WTSD: `SUM(sawshowdown) / SUM(sawflop) * 100`
- W$SD: `SUM(wonshowdown) / SUM(sawshowdown) * 100`
- WWSF: `SUM(wonhandwhensawflop) / SUM(sawflop) * 100`
- Agg estimate: `SUM(totalbets) / SUM(totalcalls)`
- Postflop aggression: `SUM(totalaggressivepostflopstreetsseen) / SUM(totalpostflopstreetsseen) * 100`
- Fold to 3Bet: `SUM(foldedtothreebetpreflop) / SUM(facedthreebetpreflop) * 100`
- Flop CBet: `SUM(flopcontinuationbetmade) / SUM(flopcontinuationbetpossible) * 100`
- Fold to Flop CBet: `SUM(foldedtoflopcontinuationbet) / SUM(facingflopcontinuationbet) * 100`

Use exact numerator and denominator counts when possible.
Do not invent unsupported stats.
