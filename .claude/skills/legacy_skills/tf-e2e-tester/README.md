# tf-e2e-tester

End-to-end test harness for the Terraform spec-driven development workflow.

## Purpose

This skill validates the complete `/tf-plan` → `/tf-implement` pipeline after changes to any part of the workflow system — skills, agents, orchestrators, templates, or scripts.

It is **not** a production workflow entry point. It is a testing tool that:

- Runs the full planning workflow (requirements → specify → clarify → plan → review → tasks → analyze) with auto-resolved decisions
- Runs the full implementation workflow (tasks → code → sandbox → deploy → report → compound learning) non-interactively
- Uses predefined test scenarios with consistent prompts (see `prompts/` directory)
- Documents execution time and validates artifact generation at each phase
- Verifies cross-phase consistency and quality gates

## When to Use

- After modifying agent definitions in `.claude/agents/`
- After changing skill content in `.claude/skills/`
- After updating orchestration logic in `/tf-plan` or `/tf-implement`
- After changing templates, schemas, or scripts in `.foundations/`
- Before merging changes to the workflow system

## Test Scenarios

Test prompts live in the `prompts/` directory. Each provides a realistic infrastructure request that exercises different parts of the pipeline:

| Scenario | File | Exercises |
|----------|------|-----------|
| ASG | `prompts/example_asg.md` | Auto Scaling, launch templates, scaling policies |
| CloudFront | `prompts/example_cloudfront.md` | CDN, S3 origins, ACM certificates |
| EC2 | `prompts/example_ec2.md` | Compute, VPC, security groups, ALB |
| Elasticsearch | `prompts/example_elastic.md` | Managed service, VPC endpoints, IAM |
| Serverless | `prompts/example_serverless.md` | Lambda, API Gateway, DynamoDB |
| SQS | `prompts/example_sqs.md` | Queues, dead-letter queues, IAM policies |

## Invocation

```
/tf-e2e-tester
```

The skill auto-selects test defaults for all interactive decisions and creates a disposable test branch.

## Relationship to Entry Points

The two production entry points are:

- **`/tf-plan`** — Planning workflow (interactive, user-driven)
- **`/tf-implement`** — Implementation workflow (requires completed plan)

`/tf-e2e-tester` embeds the same orchestration logic as both but with non-interactive execution and automatic decision-making throughout.
