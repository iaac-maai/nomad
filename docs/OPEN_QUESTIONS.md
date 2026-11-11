# Open questions

Legal and data questions NOMAD cannot settle by itself. Each says what we know, what is open, and who could answer.

## Decret 141/2012, Annex 4 (conversions)

1. **Grup C's "≤" — answered (10 Nov 2026).** The consolidated PDF (Portal Jurídic, version of 12 Dec 2020, the one
   `get_rulebook.py` downloads) prints Grup C as "canvi d'ús d'un edifici ( 50% de la superfície construïda …)": the
   sign is blank, also on the page image. The original **DOGC 6245, 2 Nov 2012, page 53451**
   (https://portaldogc.gencat.cat/utilsEADOP/PDF/6245/1267583.pdf, sha256 7065839b…d736a50) prints
   "(≤ 50% de la superfície construïda sobre o sota rasant)", and the rest of Grups B, C and D word for word as the
   consolidated text. Crop: `docs/law_check_scans/annex4_grupC_dogc6245.png`. Grup E has the same blank, also "≤" in
   the original. *To do:* nothing for NOMAD; the blank could be reported to the Portal Jurídic.

2. **"sobre o sota rasant": one total, or above and below ground separately?** Read as "of the built area, above or
   below ground" (one total for the whole building: NOMAD's choice), or as two tests (more than half of the
   above-ground area, or more than half of the below-ground area). `annex4_grup.py` computes both and counts the shops
   that would change group: **181 of 6,072** on the CAT file of 14 Aug 2026. *Who:* Agència de l'Habitatge de
   Catalunya, or the Ajuntament's licensing office.

3. **Grups B and D and the lift (Annex 1 2.4.1 a).** Grups B and D apply Annex 1 apartat 2, but 2.4.1 a) speaks of
   buildings "de nova construcció". Does a Grup B or D conversion have to add a lift? *Who:* Agència de l'Habitatge.

4. **Grups B and D patios: areas only?** "s'accepta una reducció del 10% en les superfícies" (Grups B and D). NOMAD
   reads it as the patio areas (9 → 8,1 m², 6 → 5,4 m²) with the circles (3 m, 2,5 m) unchanged. *Who:* Agència de
   l'Habitatge.

5. **Building or parcel.** Annex 4 says "edifici". The Catastro's parcel can hold several buildings (unidades
   constructivas); NOMAD then uses the shop's own building when it has upper floors. Where one building spans several
   parcels, NOMAD only sees the shop's parcel.

6. **Which part of the shop changes use.** NOMAD counts the unit's ground-floor non-housing space, and its own
   basement only when the unit holds no homes. If only the ground floor became homes and the basement stayed storage,
   the share would be smaller.

7. **Which unit is the shop.** The census and the Catastro number doors differently; when several ground-floor units
   could be the shop and they give different groups, NOMAD says "not known" rather than guess
   (`docs/ANNEX4.md`). A visit or the owner's deed settles it.

8. **When is a shop the whole building (Grup B)?** NOMAD says Grup B when the shop's area is at least 90 % of the
   building's and the Catastro records no housing in the building; the 10 % margin allows for common elements
   (entrance, stairs) counted apart. This threshold is NOMAD's choice (60 shops). *Who:* Agència de l'Habitatge.

## Barcelona plan (MPGM 2004)

9. **Are area-01 and facade-01 still in force?** MPGM 2004, Disposició addicional primera 2, says its conditions
   (40 m² useful area, 3 m of façade) apply only "until the Ordenances Metropolitanes d'Edificació are modified"
   ("En tant no s'aprovi la modificació de les esmentades Ordenances"). The OME is in the rulebook: check whether a
   later OME text replaced these two conditions, and whether cards `BCN-MPGM2004-area-01` and
   `BCN-MPGM2004-facade-01` are still in force. *Who:* the team reads the OME; then the Ajuntament (Urbanisme).

## Data licence

10. **Publishing per-shop results derived from the CAT file.** The Catastro licence allows publishing transformed
    data with attribution and the access date, and forbids putting the original data on the internet. NOMAD publishes
    only the group and the percentage (`annex4_grup.json`) and rounded shop shapes (`cut_shells.json`); the m² stay in
    local files. Whether these count as "transformed" is our reading of clause 6. *Who:* the Catastro (Gerencia
    Regional de Catalunya) if in doubt.