# Bhavini's part: speaker script (3 minutes, about 420 words)

Slides 3, 4, 7, 12 and 13 of the 14-slide deck. About 35 seconds per slide.
Numbers match the deck of 29 Oct 2026 (188 test shops, 1,694 real Barcelona shops). The deck and this script get updated together.

---

## Slide 3 · Exp 1 (step 2): NOMAD reads a shop from its plan (≈ 35 s)

"Step two is reading the building. Most owners only have a drawing, so NOMAD reads the plan itself. An AI model from GitHub labels the walls, doors and windows, and NOMAD finds the outline of the shop and its street façade.

We tested it on 180 shop plans with known answers, clean and messy. With one known size, the outline overlaps the truth 0.93 out of 1, and the area is within 10 percent on 77 percent of plans. We also raced four wall readers, including MitUNet from GitHub. It wasn't better, so we kept ours.

What we learned: guessing the scale alone is about 50 percent off, so NOMAD always asks for one dimension. On real scanned plans the reader struggles more, so that's our next step."

## Slide 4 · Exp 2 (step 3): can each empty shop become housing at all? (≈ 35 s)

"Step three is the first legal question: does the zoning allow housing here at all?

We took all 6,149 empty ground-floor premises from the city's 2024 census and matched each one to its zone in the Generalitat's urban map. The rule is PGM article 225.7: ground-floor housing is allowed in the zones built along street lines, like the old town and the Eixample.

The result: 82 percent of empty shops pass this first gate, and in the Eixample it's 95 percent. 306 can't take housing at all: they're facilities, parks or industry.

So in the dense city, zoning is rarely the problem. The rules inside the shop decide. You can now type an address straight into NOMAD."

## Slide 7 · Exp 3: one rulebook, tested on 46,937 real flats (≈ 35 s)

"Step four is the law itself. We collected the national, Catalan, metropolitan and Barcelona rules into one rulebook: 2,470 pieces from 22 norms, each with its article.

From it we coded nine rules for a new home and tested them on 46,937 real flats. Only 32 percent pass all nine. The façade rule fails most: only 39 percent pass it.

We also built a golden set of 16 questions from the official text. It found real bugs. The biggest: a shop conversion only needs 2.40 metres of clear height, not 2.50. After the fixes, NOMAD gets 16 out of 16 right, and every number cites its article."

## Slide 12 · Exp 5 (step 6): every shop checked, yes, partly or no (≈ 35 s)

"Steps six to eight all run in one Grasshopper file inside Rhino. You give it the shop, as a plan file, an outline or an address, and the flats you want. NOMAD checks the rules, draws the layouts and builds the 3D.

Step six checks the shop as it is, flat by flat, and every rule names its article. The answer is yes, partly or no, and it's always written under the plan, never on it.

Over 188 shops asking for two one-bedroom flats and one two-bedroom flat: 41 yes, 104 partly and 43 no. Most of the partly shops aren't short on rules, they're short on street façade. On 1,694 real empty shops in Barcelona it's the same story: 155 yes, 946 partly and 593 no."

## Slide 13 · Exp 5 (steps 7-8): three layouts, built in 3D (≈ 40 s)

"Then NOMAD fits the homes. Room sizes are learned from 13,444 real flats that pass every rule. Each shop gets three layouts, and each one is checked again. The first is the flats you asked for. The second uses compact rooms, still legal. The third fits as many homes as possible.

This 850-square-metre shop holds 7 homes as asked and 12 at most. Across all 188 shops that's 266, 304 and 466 homes, and 157 shops can hold at least one.

Each layout is then built in Rhino: first the zoning as coloured blocks, then real walls, doors and windows. It's exported to IFC for BIM. Every experiment is saved in one Rhino file, and next we'll use the team's daylight model in place of our simple 5.5-metre rule."

---

**If you're short on time, cut:** the MitUNet race (slide 3) and the 13,444 flats (slide 13). That saves about 15 seconds.
