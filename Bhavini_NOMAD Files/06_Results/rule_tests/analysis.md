# Nomad rulebook test on Swiss Dwellings v3.0.0

Source: Swiss Dwellings v3.0.0 (Zenodo 7788422, CC BY 4.0). Rules: Decret 141/2012 Annex 1 + Barcelona MPGM 2004.
This is a stress test (Swiss plans, Catalan rules), not an accuracy score: the dataset has no legal labels.

## 1. Residential: 46,937 apartments, 442,019 rooms

| Rule | Pass rate | Fails |
|---|---|---|
| Decret 141/2012 Annex 1 3.1: superfície útil >= 36 m² | 93.0% | 3,275 |
| MPGM 2004 Barcelona DA 1a 2.a: superfície útil >= 40 m² | 91.5% | 3,992 |
| Decret 141/2012 Annex 1 3.8: every bedroom >= 6 m² | 100.0% | 19 |
| Decret 141/2012 Annex 1 3.8: 2,00 m square in every bedroom (2,60 m in one if >= 3 bedrooms) | 99.7% | 155 |
| Decret 141/2012 Annex 1 3.7.2: living/dining fits a 2,80 m circle | 97.0% | 1,421 |
| Decret 141/2012 Annex 1 3.9.1: windows (0-2,5 m) >= 1/8 of each bedroom and living room | 72.7% | 12,803 |
| Decret 141/2012 Annex 1 3.5: clear height >= 2,50 m in main rooms | 98.3% | 797 |
| Decret 141/2012 Annex 1 3.11: >= 1 bathroom (>= 2 WC if >= 4 bedrooms) | 94.6% | 2,519 |
| Decret 141/2012 Annex 1 3.6.2 + MPGM 2004 DA1 2.b: façade >= max(S/9, 3 m) (proxy: total window width) | 38.6% | 28,807 |

**All 9 rules pass: 32.2%** of apartments.

Most common reason a flat fails: `r_facade_s9` (28,807), `r_windows_1_8` (12,803), `r_useful_40` (3,992)

### By number of bedrooms (4 = 4 or more)

| Bedrooms | Units | Median useful m² | All rules pass |
|---|---|---|---|
| 0 | 2,355 | 40 | 11.1% |
| 1 | 9,280 | 53 | 22.4% |
| 2 | 15,801 | 76 | 33.4% |
| 3 | 14,442 | 92 | 40.3% |
| 4 | 5,059 | 102 | 32.6% |

## 2. Commercial units: 341 (the Nomad case: could this local become housing?)

A shop has no bedrooms yet, so only the rules a bare shell can meet are tested:

| Rule | Pass rate |
|---|---|
| MPGM 2004 Barcelona DA 1a 2.a: superfície útil >= 40 m² | 64.5% |
| Decret 141/2012 Annex 1 3.5: clear height >= 2,50 m in main rooms | 91.8% |
| Decret 141/2012 Annex 1 3.9.1: windows (0-2,5 m) >= 1/8 of each bedroom and living room | 62.5% |
| Decret 141/2012 Annex 1 3.6.2 + MPGM 2004 DA1 2.b: façade >= max(S/9, 3 m) (proxy: total window width) | 41.3% |

**Shell passes all 4: 28.4%** (97 of 341) - candidates for conversion.

If converted, the Barcelona density rule (built / 80 m²) would allow about 458 dwellings in the 97 candidate shells (assuming useful = 80% of built).

## 3. Room-level facts

- Bedrooms: 105,615; median 14.3 m²; under 6 m²: 19; no 2,00 m square: 155
- Window ratio (glazing 0-2,5 m / floor area), bedrooms: median 0.28 (rule: ≥ 0,125); below 1/8: 9.3%

## 4. Method notes (limits)

- Useful area = all rooms except balconies, loggias, shafts, stairs, lifts, voids, basements (Decret 141 'superfície útil').
- 2,00 / 2,60 m square: room eroded with a square-corner buffer (exact for rooms with walls parallel to the square).
- Windows: each window polygon is linked to the rooms it touches (0,45 m search across the wall); only glazing between 0 and 2,5 m above that room's floor counts (Decret 141 3.9.1). A window shared by two rooms counts for both.
- Façade S/9 uses total window width as a strict proxy for façade length: real façade is longer, so this rule under-reports passes.
- ROOM (unlabelled room) is treated as a bedroom; when no room is labelled living, the largest one is tested for the 2,80 m circle.
