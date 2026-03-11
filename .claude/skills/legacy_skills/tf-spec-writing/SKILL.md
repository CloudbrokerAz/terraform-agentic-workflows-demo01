---
name: tf-spec-writing
description: Terraform feature specification writing patterns. User story formats, success criteria templates, requirement quality rules, and Terraform-specific spec conventions.
---

# Terraform Feature Specification Patterns

## Specification Purpose

Specifications describe **WHAT** users need and **WHY** — never HOW to implement. Written for business stakeholders, not developers. No tech stack, APIs, or code structure.

## Section Requirements

### Mandatory Sections
- **User Scenarios & Testing**: Prioritized user stories with acceptance scenarios and edge cases
- **Requirements**: Functional requirements (FR-numbered) with Key Entities subsection when data is involved
- **Success Criteria**: Measurable, technology-agnostic outcomes

## Requirement Writing Rules

1. Every requirement MUST be testable and unambiguous
2. Maximum 3 `[NEEDS CLARIFICATION]` markers total
3. Prioritize clarifications: scope > security/privacy > UX > technical
4. Make informed guesses using context and industry standards
5. Document assumptions in Assumptions section

## Success Criteria Guidelines

Criteria must be:
- **Measurable**: Specific metrics (time, percentage, count, rate)
- **Technology-agnostic**: No frameworks, languages, databases, or tools
- **User-focused**: Outcomes from user/business perspective
- **Verifiable**: Testable without knowing implementation details

**Good**: "All application data is encrypted at rest and in transit"
**Bad**: "Enable KMS encryption on S3 buckets and RDS instances" (implementation leakage)

## Reasonable Defaults (don't ask about these)

- Encryption: At-rest and in-transit enabled by default
- Networking: Private subnets for workloads, public only for load balancers
- Logging: CloudWatch logging enabled for all services
- Tagging: Standard tagging strategy applied (environment, project, owner)
- Data retention: Industry-standard practices

## Terraform-Specific Patterns

For infrastructure specs:
- Describe desired infrastructure state, not Terraform resources
- Use cloud-agnostic language where possible (e.g., "network isolation" not "VPC")
- Security requirements should reference compliance frameworks (CIS, NIST) not tools
- Scalability should describe capacity needs, not auto-scaling implementation
- Reference module capabilities, not module names

## Quality Validation Checklist

After writing spec, validate:
- [ ] No implementation details (languages, frameworks, APIs)
- [ ] Focused on user value and business needs
- [ ] Written for non-technical stakeholders
- [ ] All mandatory sections completed
- [ ] Requirements are testable and unambiguous
- [ ] Success criteria are measurable and technology-agnostic
- [ ] Edge cases identified
- [ ] Scope clearly bounded
- [ ] Dependencies and assumptions identified
