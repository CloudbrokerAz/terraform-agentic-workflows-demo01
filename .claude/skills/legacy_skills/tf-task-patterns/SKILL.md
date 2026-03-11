---
name: tf-task-patterns
description: Task breakdown format and phase organization for Terraform implementation.
---

# Task Breakdown Patterns

Transform plan.md into dependency-ordered, checklist-format tasks organized by implementation phase. The tf-implement orchestrator passes phases to tf-task-executor subagents.

## Workflow

1. **Extract**: Pull user stories, modules, data model, infrastructure from plan.md and spec.md
2. **Map requirements**: Build coverage matrix linking requirements → tasks
3. **Assign phases**: Setup → Foundational → User Stories (priority order) → Polish
4. **Order tasks**: Sequential T001, T002... respecting dependencies
5. **Label stories**: Add `[US#]` labels only in story phases
6. **Generate sections**: Header, matrix, phases, dependencies, strategy, checklist, summary

## Output

- **Location**: `tasks.md` in feature directory
- **Format**: Markdown checklist with phase headers

### Required Sections

| Section | Purpose |
|---------|---------|
| Header | Feature name, input path, prerequisites, tests stance, organization note |
| Format explanation | `[ID] [Story] Description` with sequential execution note |
| Requirements Coverage Matrix | Requirement → Task(s) → Description traceability |
| Phase sections | Grouped tasks with purpose, checkpoints, and dependency notes |
| Dependencies & Execution Order | Phase deps, story deps, cross-module data flow table |
| Implementation Strategy | MVP first, incremental delivery approach |
| File Checklist | File → Task → Purpose mapping |
| Task Summary | Phase → Task range → User Story table with total count |

## Constraints

- Every task: `- [ ] T### [US#?] Description with file path`
- Include checkpoint markers after each phase
- Document circular dependencies explicitly

## Examples

**Good task format**:
```
- [ ] T001 Create project structure per implementation plan
- [ ] T005 [US1] Implement auth middleware in src/middleware/auth.py
- [ ] T010 [US1] Implement CloudFront module in main.tf with OAI creation, S3 origin at /main.tf
```

**Good phase header**:
```
## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core S3 bucket infrastructure that MUST be complete before CloudFront

**CRITICAL**: CloudFront origin configuration requires S3 bucket outputs

- [ ] T005 Implement S3 bucket module in main.tf with public access blocking at /main.tf

**Checkpoint**: S3 bucket module configured - CloudFront implementation can proceed
```

**Bad**:
```
- [ ] Create User model
```
Missing task ID, story label, and file path.

## Context

### Phase Structure

| Phase | Content | Story Labels |
|-------|---------|--------------|
| 1 - Setup | Project initialization, file structure, Terraform config | No |
| 2 - Foundational | Blocking prerequisites, core infrastructure | No |
| 3+ - User Stories | Priority order (P1, P2...) with independent tests | Required |
| Final - Polish | Cross-cutting concerns, formatting, validation | No |

### Source Material Placement

| Source | Placement |
|--------|-----------|
| User stories | Own phase; map models, services, endpoints, tests |
| Module contracts | Serving story; interface tests before impl if TDD |
| Data model | Earliest needing story; multi-story entities → Setup |
| Infrastructure | Shared → Phase 1; blocking → Phase 2; story-specific → that phase |

### Header Template

```markdown
# Tasks: [Feature Name]

**Input**: [spec path]
**Prerequisites**: plan.md, spec.md, data-model.md, contracts/module-interfaces.md
**Tests**: [from spec or "No tests requested"]
**Organization**: [brief description]
```

### Cross-Module Data Flow Table

```markdown
| Task | From | Output | To | Input |
|------|------|--------|-----|-------|
| T010 | `module.s3_bucket` | `bucket_regional_domain_name` | `module.cloudfront` | `origin.domain_name` |
```

### Task Summary Table

```markdown
| Phase | Tasks | User Story |
|-------|-------|------------|
| Phase 1: Setup | T001-T004 | - |
| Phase 2: Foundational | T005-T007 | - |
| Phase 3: User Story 1 | T008-T013 | US1 (P1) |

**Total Tasks**: N
```
