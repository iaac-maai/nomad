# Experiment 2 - rule cards: results

| Measure | Result |
| --- | --- |
| Drafts scored | 50 (10 questions) |
| Grounding: quote in PDF and number in quote | 37 / 50 (74 %) |
| Mean agreement across runs | 0.92 |
| Accuracy against gold cards | 23 / 50 (46 %) |
| Cards sent to the expert (confidence < 0.8) | 3 of 10 |
| ML trust layer | Logistic regression on 4 signals, leave-one-question-out: accuracy 0.68 (always-guess baseline 0.54), Brier score 0.231, 50 drafts. |
| Manual baseline (time to read the 10 clauses by hand) | fill in: 20 minutes (non-expert, with Google Translate) + expert check minutes |

| Question | Majority card | Gold | Agreement | Grounding | Accuracy | Confidence | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Q01 | min_area 36.0 | 36.0 | 1.00 | 1.00 | 1.0 | 1.00 | auto-approve |
| Q02 | min_area 20.0 | 20.0 | 1.00 | 1.00 | 1.0 | 1.00 | auto-approve |
| Q03 | not_found None | 2.8 | 1.00 | 0.00 | 0.0 | 0.00 | expert check |
| Q04 | not_found None | 6.0 | 1.00 | 0.00 | 0.0 | 0.00 | expert check |
| Q05 | fits_square 2.6 | 2.0 | 1.00 | 1.00 | 0.0 | 1.00 | auto-approve |
| Q06 | not_found None | 2.2 | 0.60 | 0.40 | 0.4 | 0.24 | expert check |
| Q07 | min_height 2.5 | 2.5 | 1.00 | 1.00 | 1.0 | 1.00 | auto-approve |
| Q08 | min_height 2.2 | 2.2 | 1.00 | 1.00 | 1.0 | 1.00 | auto-approve |
| Q09 | min_area 0.125 | 0.125 | 0.80 | 1.00 | 0.2 | 0.80 | auto-approve |
| Q10 | min_area 1.0 | 1.0 | 0.80 | 1.00 | 0.0 | 0.80 | auto-approve |
