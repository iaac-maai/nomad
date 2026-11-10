# Conversions: Decret 141/2012 Annex 4

A shop that becomes homes is a change of use of part of a building. Decret 141/2012 Annex 4 says which rules of
Annex 1 (new buildings) apply then. For a single shop it is **Grup C** (≤ 50 % of the building's built area changes
use) or **Grup D** (> 50 %). Official text: the consolidated Decret 141/2012 that `tools/get_rulebook.py` downloads
(pinned in `nomad/04_Website/rulebook/sources.lock.json`), Annex 4 apartat 2, **page 23**.

| | Grup C (≤ 50 %) | Grup D (> 50 %) |
| --- | --- | --- |
| Annex 1 apartat 2 (the building: access, stairs, lift, patios, shared spaces) | exempt, except **2.2.1** (each home is reached from a public, common or annex space) | **applies**: 2.1 accessible route (p. 14), 2.2.2 1,50 m landing (p. 14), 2.6 shared space from 8 homes (p. 15); whether the lift rule 2.4.1 a) applies to conversions is still open |
| Ventilation patios, Annex 1 2.5.1 (p. 15) | not required (apartat 2 exempt) | areas −10 %: 8,1 m² (rooms) / 5,4 m² (kitchens, baths, stairs) |
| Clear height, Annex 1 3.5 (p. 17) | 2,40 m instead of 2,50 m; the rest of 3.5 stays: 2,20 m in bathrooms, kitchens and circulation, 2,30 m over at most 20 % of a room | same as Grup C |
| Annex 1 apartat 3 (the home: area, façade, rooms, windows, bathroom) | applies unchanged | applies unchanged |

## On the rule cards (no value changed)

`tools/annex4_cards.py` adds to every Decret 141 card `scope` (who it applies to), `conversion` (what changes for a
conversion) and `source.page`; height-04C and patio-01 get `extra_quotes`; `rules/annex4.json` holds the Annex 4 note
shown above the cards. Every quote is found word for word on its page (`tools/check_quotes.py`: 16/16 cards, 20/20
Annex 4 quotes).

| Card | For | Conversion |
| --- | --- | --- |
| height-01 (2,50 m) | new buildings (Annex 1) | replaced by height-04C |
| height-04C (2,40 m) | conversions (Annex 4 Grups C and D) | 2,40 m; 2,20 m in bathrooms, kitchens, circulation; 2,30 m over ≤ 20 % of a room |
| patio-01 (9 m²) | new buildings; conversions see the change | not required in Grup C; −10 % in Grup D (8,1 / 5,4 m²) |
| area-01, facade-01, bedroom-01/02, living-01, window-01, bath-01 | new buildings and conversions | unchanged |

The MPGM 2004 and CTE cards are not Decret 141: Annex 4 does not change them.

## Grup C or D for each shop

`tools/annex4_grup.py` computes, for each empty premises of the 2024 census:
**the shop's built area ÷ the building's total built area (above and below ground)** → Grup C (≤ 50 %) or D (> 50 %).

**Data: the Catastro's alphanumeric data, CAT format** (one file per municipality, urban; record layout
"Fichero informático de remisión de catastro", revision 16-11-2022,
https://www.catastro.hacienda.gob.es/documentos/formatos_intercambio/catastro_fin_cat_2006.pdf):
- record 11 (parcel): total built area, above ground, below ground;
- record 14 (each construction): its unit (blank = common element), its building (unidad constructiva), floor, door,
  use, m²;
- record 15 (each unit): floor, door, use (V residential, C commercial, O offices, A storage-parking, …), m².
The Catastro Visor layer is **not** used.

**Which unit is the shop.** The census gives the parcel (14 characters), "LOC" and a door number. Candidates are the
parcel's non-residential units with a construction on the ground floor:
`door` (one candidate has the census door) · `only` (one candidate) · `same` (several, all the same group; the %
shown is the smallest–largest) · `unknown` (no parcel, no candidate, or candidates that give different groups).
**Building** = the parcel; when the parcel holds several buildings, the shop's own building. The shop's area is its
own constructions on every floor (its basement too); common elements count only in the building's total.

### How to run it (needs Bars: the download needs a login)

1. On the Sede Electrónica del Catastro (https://www.sedecatastro.gob.es/Accesos/SECAccDescargaDatos.aspx), log in as
   a registered user or with a digital certificate, accept the licence and download the **urban CAT file of
   Barcelona** (province 08). Note the date.
2. Put it in `nomad/02_Code/data/barcelona/catastro/cat/` (not in git: `nomad/02_Code/data/` is ignored).
3. The census: `nomad/02_Code/data/barcelona/census/2024_CensComercial_BCN.csv` from Open Data BCN
   (https://opendata-ajuntament.barcelona.cat/data/dataset/cens-locals-planta-baixa-act-economica, CC BY 4.0).
4. `python tools/annex4_grup.py --cat <file>.CAT.gz --accessed YYYY-MM-DD`
   → `nomad/04_Website/data/annex4_grup.json` (site: group, %, how found) and
   `nomad/02_Code/results/annex4/spotcheck.md` (local only: counts, how each unit was found, 5 shops of each group with
   their m², and how many shops would change group if above and below ground were counted separately).
5. Tests without real data: `python tools/test_annex4_grup.py` (CAT records written by hand to the format).

Until then the site says "Conversion rules: Annex 4 Grup C or D (not known yet: needs the Catastro CAT data)".

## Licence of the CAT data, and attribution

Catastro "Licencia de descarga de productos catastrales" (https://www.catastro.hacienda.gob.es/pdf/ovc/licdescargaES.pdf),
which the download asks to accept:
- **Access:** "se requerirá la autentificación previa del usuario, bien accediendo como usuario registrado … o bien
  … certificado digital" (Condiciones técnicas).
- **Original data:** "No se autoriza el uso público ni la comercialización de la información catastral original" (5);
  "En ningún caso se autoriza a que la información catastral original descargada y no trasformada pueda ser difundida
  a través de Internet" (8). → The CAT file and the m² copied from it stay out of git and off the site.
- **Transformed data:** "Se autoriza el uso público, incluido el comercial, de la información catastral que haya sido
  sometida a cualquier proceso previo de transformación" (6), if it does not alter or distort the original. → The site
  shows only NOMAD's derived result: the group and the percentage.
- **Attribution:** "deberá citarse como fuente … a la Dirección General del Catastro … Asimismo deberá indicarse la
  fecha en la que se produjo el acceso" (12). → Each answer says "NOMAD's estimate from Dirección General del Catastro
  data, accessed YYYY-MM-DD"; the Sources table has a row.
- **Name:** new products must not call themselves "información catastral" or "cartografía catastral" (7). → "NOMAD's
  estimate", never "Catastro information".
- **Term:** 10 years from the download (13).
The licence PDF is dated 24 Oct 2011 and names the "Ministerio de Economía y Hacienda"; the Catastro is now under the
Ministerio de Hacienda. Open questions are in `docs/OPEN_QUESTIONS.md`.
