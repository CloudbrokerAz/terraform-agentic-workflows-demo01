# E2E Eval Judge — Case: {{CASE_ID}}

You are the independent judge for an end-to-end workflow eval run. Follow the
`tf-e2e-judge` agent instructions (.claude/agents/tf-e2e-judge.md) exactly:
read-only, evidence-cited, one fenced JSON verdict as your entire final message.

## Rubric

Load the `tf-judge-criteria` skill and apply the **{{RUBRIC}}** workflow rubric:
its 6-dimension table, weights, scoring formula, and the Security (D2) < 5.0
"Not Production Ready" override.

## What to grade

- Workdir (current directory): design/research docs under `specs/`, Terraform
  code at the root{{TESTS_HINT}}.
- Diff of everything the run produced: `{{DIFF_PATH}}`
- Deterministic gate outcomes (facts, not opinions): `{{CHECKS_PATH}}`
- Sandbox facts (run id, apply status, run tasks, cost estimate): `{{FACTS_PATH}}`

**Do NOT open** `specs/*/reports/validation_*.md`, or the Quality Score /
narrative sections of `specs/*/reports/deployment-report.md` — the workflow's
self-assessment must not anchor your score.

## Run metadata

- Run status: {{RUN_STATUS}}
- Run incomplete (timed out / killed): {{RUN_INCOMPLETE}} — if true, grade the
  partial artifacts and note it in `summary`.

## Per-case assertions (each needs a strict pass/fail with file:line evidence)

{{ASSERTIONS}}

## Output

Your final message must be exactly one fenced ```json block matching the schema
in the tf-e2e-judge agent definition, with `"rubric": "{{RUBRIC}}"`.
