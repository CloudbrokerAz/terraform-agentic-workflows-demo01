---
name: tf-research-heuristics
description: Search query construction for private Terraform registries, AWS documentation, and provider docs. Effective research strategies for infrastructure unknowns.
---

# Terraform Research Heuristics

## Private Module Registry Search

### Strategy
1. Start with broad category terms: "vpc", "iam", "s3", "rds", "ec2"
2. Narrow with purpose: "vpc networking", "iam role", "s3 bucket"
3. Check module details for inputs/outputs compatibility
4. Verify version constraints and provider compatibility

### MCP Tools (registry-private toolset)
- `search_private_modules(query)` — Search private registry for modules (ALWAYS use this FIRST)
- `get_private_module_details(moduleID)` — Get full module documentation, inputs, outputs
- `search_private_providers(query)` — Search private registry for providers
- `get_private_provider_details(providerID)` — Get private provider documentation

### Search Protocol

Before declaring MODULE GAP for any infrastructure component, you MUST execute the full protocol below. Do not stop after the first failure.

> **CRITICAL**: Private registry search uses simple keyword/substring matching, NOT semantic search. Single short words return the best results. Multi-word queries often return ZERO results even when modules exist. ALWAYS start with the shortest, simplest terms.

### Search Query Tips

- **One search per query**: Do NOT combine terms. Search `alb` and `lb` as separate queries, not `alb lb`.
- **Log every query and result**: The module gap documentation (below) requires this for debugging.
- **Beware false negatives**: If search returns nothing, the module may still exist — proceed to Direct Module ID Verification.

### Direct Module ID Verification

After search queries return no results, attempt direct lookup using `get_private_module_details`. **This step catches modules that exist but aren't returned by search** (common with private registries).

1. Determine the organization name from the constitution or project configuration (e.g., the org in `app.terraform.io/<org-name>/`)
2. Construct candidate module IDs using the pattern `<org>/<component>/<provider>`:
   For each infrastructure component, try ALL of these naming patterns:
   - Abbreviation: `<org>/alb/aws`, `<org>/nlb/aws`, `<org>/acm/aws`
   - Short name: `<org>/lb/aws`, `<org>/cert/aws`, `<org>/sg/aws`
   - Full name hyphenated: `<org>/load-balancer/aws`, `<org>/security-group/aws`
   - Full name underscored: `<org>/load_balancer/aws`, `<org>/security_group/aws`
   - AWS service name: `<org>/elbv2/aws`, `<org>/elasticache/aws`
   - Descriptive: `<org>/application-load-balancer/aws`
   - Prefixed: `<org>/aws-alb/aws`, `<org>/terraform-aws-alb/aws`
3. Call `get_private_module_details` for EACH candidate ID
4. If any returns a valid module, use it — the module exists but was not indexed by search
5. **Also try the public registry module name pattern**: Many orgs fork public modules with the same name. If the public registry has `terraform-aws-modules/alb/aws`, try `<org>/alb/aws`.

### Broad Registry Discovery

Before researching specific components, run a broad discovery search to understand what modules are available in the private registry. This prevents false MODULE GAP declarations.

1. Search `search_private_modules` with broad single-word terms: `aws`, `terraform`, `module`
2. Note all returned module names — these are the modules you can use
3. Cross-reference this list when searching for specific components
4. If the broad search returns a module like `<org>/alb/aws` but your targeted search for "application load balancer" missed it, the targeted search had a false negative

**Run broad discovery ONCE at the start of the research phase**, not per-question. Share the results across all research questions.

### Search Result Validation

When search returns results, verify each result actually provides the required capability:
- Read the module description and confirm it matches the infrastructure need
- Check inputs/outputs compatibility with the planned architecture
- Verify the module version is actively maintained (check last updated date)
- Do not accept a module solely because its name matches the search term

### Output Type Verification (MANDATORY)

**CRITICAL**: For every module selected, you MUST call `get_private_module_details` and document the **actual HCL type** of each output that will be referenced by other modules. This prevents type mismatch errors at `terraform plan` time.

Common type mismatches that cause failures:
- **map vs tuple**: Module outputs named with plural keys (e.g., `_arns`, `_ids`) may return `tuple` (list indexed by position `[0]`) instead of `map` (keyed by name `["key"]`). Always verify.
- **string vs list**: Some outputs return a single string, others return a list of one element.
- **object vs map**: Outputs may be typed objects with fixed keys, not open maps.

**Verification steps**:
1. Call `get_private_module_details` for the selected module
2. Locate each output that downstream modules will reference
3. Record the output's HCL type from the module documentation (e.g., `list(string)`, `map(string)`, `string`)
4. If the type is ambiguous in docs, check the module source code for `output` block definitions
5. Include the type in your research findings under **Key Outputs** using the format: `output_name` (`type`) — description

**Example of what goes wrong without this**:
```hcl
# Plan assumed map access:
AWS = module.cloudfront.cloudfront_origin_access_identity_iam_arns["s3_origin"]
# Actual type was tuple — correct access is:
AWS = module.cloudfront.cloudfront_origin_access_identity_iam_arns[0]
```

### Module Gap Documentation

Before declaring MODULE GAP, you MUST document in the research output:
1. All search queries attempted
2. All direct module ID lookups attempted
3. Results returned for each query (including "no results")
4. Reason each result was rejected (if any were returned but unsuitable)

This documentation enables future debugging of search failures and feeds into compound learning.

## AWS Documentation Search

### MCP Tools
- `search_documentation(phrase, topics)` — Search AWS docs
- `read_documentation(url)` — Fetch specific page
- `recommend(url)` — Find related content

### Topic Selection Guide
| Query Type | Topic | Example |
|------------|-------|---------|
| API/SDK code | `reference_documentation` | "S3 PutObject API" |
| New features | `current_awareness` | "Lambda new features" |
| Errors | `troubleshooting` | "AccessDenied S3" |
| Architecture | `general` | "VPC best practices" |
| CloudFormation | `cloudformation` | "DynamoDB template" |
| CDK | `cdk_docs` | "CDK stack TypeScript" |

### Query Best Practices
- Be specific with service names: "S3 bucket versioning" not "versioning"
- Include context: "Lambda environment variables Python SDK"
- Use exact error messages for troubleshooting
- Add temporal context for recent features: "Lambda features [current year]"

## Provider Documentation Search

### MCP Tools
- `search_providers(provider_name, provider_namespace, service_slug, provider_document_type)` — Find provider doc ID
- `get_provider_details(provider_doc_id)` — Fetch provider documentation

### Strategy
1. Identify provider: `aws`, `azurerm`, `google`
2. Use single-word service slug: "vpc", "instance", "bucket"
3. Select data type: `resources` for deploying, `data-sources` for reading
4. Review documentation for required vs optional arguments
