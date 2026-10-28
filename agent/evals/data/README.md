# Step-check test cases

`step_cases.jsonl` is the real-world eval for the step checker. Each line is one photo:

```json
{"guide_id": 12345, "step": 3, "image": "images/t480-battery-unplugged.jpg", "label": "done"}
```

- `guide_id` and `step`: the guide and step number (from `data/guides.json`, or the URL on the step card in the app).
- `image`: a path under this folder.
- `label`: one of
  - `done`: the photo shows the step finished correctly
  - `not_done`: the step hasn't been done yet (for example, screws still in)
  - `wrong`: a mistake (wrong cable pulled, battery pried with metal, wrong part)
  - `unclear`: blurry, dark, or the part is out of frame

## How to collect them (about an hour)

1. Get an old laptop and open its guide in Handy.
2. For about 10 steps, take 4 photos each with your phone: one before the step (`not_done`), one after (`done`), one with a deliberate safe mistake (`wrong`, for example the cable next to the right one lifted), and one blurry or far away (`unclear`).
3. Save them in `images/` and add one line per photo here.
4. Run `python -m evals steps` from the `agent/` folder.

Forty photos is enough to see real accuracy and false alarm numbers, which are the most convincing thing to show in an interview.
