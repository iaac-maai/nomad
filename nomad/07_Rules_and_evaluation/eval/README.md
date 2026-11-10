# eval — Stage 9 golden set

`golden_set.csv`: 16 questions with the correct answer and its article; 10 from the team's gold cards (Exp 2), 6 from the official text.
Every answer is found word for word in its source (`answer_as_written`). Score NOMAD with `src/eval/run_golden.py` → `results/eval/`.
Re-run it after every rule change.
