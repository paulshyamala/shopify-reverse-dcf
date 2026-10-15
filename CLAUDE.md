# Shopify reverse DCF: working rules

## Git
- NEVER run git commit, git add, git push, or any other git write command. Paul commits manually at the end of each day. Finish tasks by showing `git status`.

## Workbook (`model/shopify_reverse_dcf.xlsx`)
- Never rebuild the workbook: open the existing file and edit in place, preserving values, styles, comments, formulas and data validation.
- Stop and tell Paul if the workbook is open in Excel (lock file `model/~$*`).
- Colour styles: blue `Input` = hardcoded inputs; black `Formula` = calculations; green `Link` = references to another tab; yellow `ToFill` = still to fill.
- Find rows by their label in column A and columns by the header row. Never hardcode cell addresses in scripts.
- No hardcoded numbers inside formulas; every assumption lives on the Inputs tab.
- openpyxl `insert_rows` does NOT update formulas. After shifting rows, rewrite every affected formula and data-validation range, then re-evaluate to confirm results are unchanged.
- Excel can't recalculate here: validate by evaluating formulas in Python and printing results.
- After every change, diff the workbook before vs after and confirm only the intended cells changed.
- Every hardcoded number needs a source (note or cell comment).

## Data
- SEC User-Agent comes from `SEC_USER_AGENT` in `.env` (gitignored). Never hardcode it.
- Never estimate or fill in a missing data value; leave it blank and report it.

## Decisions
- Every judgment call is logged in `memo/decisions.md`.
