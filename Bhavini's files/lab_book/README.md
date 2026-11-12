# book — the NOMAD lab book

One entry per experiment, with pictures. Live page: https://claude.ai/artifact/VKhGfPuyE3X5FdMKRUiQDa

- `experiments.json` — the entries. Write numbers as `{metric}` (e.g. `{reader_iou_given}`); they are filled from the result files.
- `figures/` — charts and plan pictures made by `lab_book/code/make_figures.py` from the step `output/` folders (never typed by hand).
- `app/` — the built page (`index.html` + `figures/`), made by `lab_book/code/build_book.py`, published as the Lab Book.

After an experiment:
```
.venv/Scripts/python lab_book/code/make_figures.py
.venv/Scripts/python lab_book/code/build_book.py
.venv/Scripts/python 8_report_and_city/code/refresh_outcomes.py
```
then republish the book and upload the changed results-page CSVs.
