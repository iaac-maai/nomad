# Experiment 2 - rule cards: results

| Measure | Result |
| --- | --- |
| Drafts scored | 50 (10 questions) |
| Grounding: quote in PDF and number in quote | 50 / 50 (100 %) |
| Mean agreement across runs | 0.96 |
| Accuracy against gold cards | 38 / 50 (76 %) |
| Cards sent to the expert (confidence < 0.8) | 1 of 10 |
| ML trust layer | Logistic regression on 4 signals, leave-one-question-out: accuracy 0.76 (always-guess baseline 0.76), Brier score 0.220, 50 drafts. |
| Manual baseline (time to read the 10 clauses by hand) | fill in: 20 minutes (non-expert, with Google Translate) + expert check |

| Question | Majority card | Gold | Agreement | Grounding | Accuracy | Confidence | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Q01 | min_area 36.0 | 36.0 | 1.00 | 1.00 | 1.0 | 1.00 | auto-approve |
| Q02 | min_area 20.0 | 20.0 | 1.00 | 1.00 | 1.0 | 1.00 | auto-approve |
| Q03 | fits_circle 2.8 | 2.8 | 1.00 | 1.00 | 1.0 | 1.00 | auto-approve |
| Q04 | min_area 5.0 | 6.0 | 1.00 | 1.00 | 0.0 | 1.00 | auto-approve |
| Q05 | fits_square 2.6 | 2.0 | 1.00 | 1.00 | 0.0 | 1.00 | auto-approve |
| Q06 | min_length 2.2 | 2.2 | 1.00 | 1.00 | 1.0 | 1.00 | auto-approve |
| Q07 | min_height 2.5 | 2.5 | 1.00 | 1.00 | 1.0 | 1.00 | auto-approve |
| Q08 | min_height 2.2 | 2.2 | 1.00 | 1.00 | 1.0 | 1.00 | auto-approve |
| Q09 | min_ratio 0.125 | 0.125 | 0.60 | 1.00 | 0.6 | 0.60 | expert check |
| Q10 | min_length 1.0 | 1.0 | 1.00 | 1.00 | 1.0 | 1.00 | auto-approve |
