---
name: tf-consumer-e2e
description: "End-to-end test harness for the Terraform consumer workflow. Runs the full `/tf-consumer-plan` -> `/tf-consumer-implement` cycle in a single session, then verifies every consumer-design.md Section 5 checklist item is complete. Optionally takes the name of a ready-made prompt from this skill's prompts/ directory. Non-interactive runs take their defaults from that prompt and from the eval runner, not from this skill."
user-invocable: true
argument-hint: "[prompt-name] - Optional; a prompt in prompts/, e.g. consumer_sqs. Omit to take requirements from the invoking prompt"
---

# E2E Test Orchestrator — Consumer

---

## INPUT

If given an argument, treat it as the name of a file in this skill's `prompts/`
directory, with or without the `.md` suffix — `/tf-consumer-e2e consumer_sqs`
reads `prompts/consumer_sqs.md`. Read that file and use it as the requirements
for this run. Those prompts also instruct you not to ask clarifying questions,
which is what makes the run non-interactive. If the named prompt does not exist,
list the available prompts and stop.

With no argument, take the requirements from the invoking prompt. This is the
path the eval harness uses: it renders the prompt file itself and passes it as
the session prompt.

---

## PART 1: PLANNING

Follow `/tf-consumer-plan` skill phases.

---

## PART 2: IMPLEMENTATION

Follow `/tf-consumer-implement` skill phases (reads consumer-design.md).

### Implementation Validation Expectations

After implementation completes, verify:

- All checklist items from consumer-design.md Section 5 are marked `[x]`

Report: whether every consumer-design.md Section 5 checklist item is `[x]` (and which are not), plus the issue and PR links. This summary is for the human reader — the eval harness derives its verdict from its own checks, not from this text.
