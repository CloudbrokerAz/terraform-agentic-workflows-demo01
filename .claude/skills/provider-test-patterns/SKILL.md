---
name: provider-test-patterns
description: Terraform provider acceptance test patterns using terraform-plugin-testing. Test structure, TestCase/TestStep fields, state checks, config helpers, import, sweepers.
metadata:
  version: "0.0.1"
---

# Provider Acceptance Test Patterns

Reference for `terraform-plugin-testing` acceptance tests.

- [Testing Patterns](https://developer.hashicorp.com/terraform/plugin/testing/testing-patterns)
- [terraform-plugin-testing repo](https://github.com/hashicorp/terraform-plugin-testing)

---

## Test Function Structure

```go
func TestAccExample_basic(t *testing.T) {
    ctx := acctest.Context(t)
    rName := sdkacctest.RandomWithPrefix(acctest.ResourcePrefix)
    resourceName := "provider_example.test"

    resource.ParallelTest(t, resource.TestCase{
        PreCheck:                 func() { acctest.PreCheck(ctx, t) },
        ProtoV5ProviderFactories: acctest.ProtoV5ProviderFactories,
        CheckDestroy:             testAccCheckExampleDestroy(ctx),
        Steps: []resource.TestStep{
            {
                Config: testAccExampleConfig_basic(rName),
                Check: resource.ComposeTestCheckFunc(
                    testAccCheckExampleExists(ctx, resourceName),
                    resource.TestCheckResourceAttr(resourceName, "name", rName),
                    resource.TestCheckResourceAttrSet(resourceName, "arn"),
                ),
            },
        },
    })
}
```

Use `resource.ParallelTest` by default. Use `resource.Test` only when tests cannot run concurrently.

---

## TestCase Fields

| Field | Type | Purpose |
|-------|------|---------|
| `PreCheck` | `func()` | Verify prerequisites (env vars, API access) |
| `ProtoV5ProviderFactories` | `map[string]func() (tfprotov5.ProviderServer, error)` | Plugin Framework provider factories |
| `CheckDestroy` | `TestCheckFunc` | Verify resources destroyed after test |
| `Steps` | `[]TestStep` | Sequential test operations |
| `TerraformVersionChecks` | `[]tfversion.TerraformVersionCheck` | Gate by Terraform CLI version |
| `IsUnitTest` | `bool` | Run without `TF_ACC=1` |

---

## TestStep Fields

### Lifecycle Mode

| Field | Purpose |
|-------|---------|
| `Config` | Inline HCL string to apply |
| `Check` | `ComposeTestCheckFunc(...)` assertions after apply |
| `ConfigStateChecks` | Modern `[]statecheck.StateCheck` assertions |
| `ConfigPlanChecks` | `[]plancheck.PlanCheck` assertions against plan |
| `ExpectError` | `*regexp.Regexp` — expect failure matching pattern |
| `ExpectNonEmptyPlan` | `bool` — expect non-empty plan (disappears tests) |
| `PlanOnly` | `bool` — plan without applying |
| `Destroy` | `bool` — run destroy |
| `PreConfig` | `func()` — setup before step |

### Import Mode

| Field | Purpose |
|-------|---------|
| `ImportState` | `true` to enable import |
| `ImportStateVerify` | Verify imported state matches prior state |
| `ImportStateKind` | `resource.ImportBlockWithID` for import block generation |
| `ResourceName` | Resource address to import |

---

## Check Functions

### Built-in TestCheckFunc

```go
resource.TestCheckResourceAttr(resourceName, "name", "expected")
resource.TestCheckResourceAttrSet(resourceName, "arn")
resource.TestCheckResourceAttrPair(res1, "vpc_id", res2, "id")
resource.TestCheckNoResourceAttr(resourceName, "deleted_attr")
resource.TestMatchResourceAttr(resourceName, "arn", regexp.MustCompile(`^arn:`))
resource.ComposeTestCheckFunc(check1, check2)          // fail-fast
resource.ComposeAggregateTestCheckFunc(check1, check2) // report all
```

### State Checks (modern)

```go
statecheck.ExpectKnownValue(resourceName,
    tfjsonpath.New("name"), knownvalue.StringExact("expected"))
statecheck.ExpectKnownValue(resourceName,
    tfjsonpath.New("active"), knownvalue.Bool(true))
statecheck.ExpectKnownValue(resourceName,
    tfjsonpath.New("count"), knownvalue.Int64Exact(5))
statecheck.ExpectKnownValue(resourceName,
    tfjsonpath.New("id"), knownvalue.NotNull())
statecheck.ExpectSensitiveValue(resourceName,
    tfjsonpath.New("password"))
```

### tfjsonpath

```go
tfjsonpath.New("attribute")                 // top-level
tfjsonpath.New("block").AtMapKey("key")     // nested map
tfjsonpath.New("list_attr").AtSliceIndex(0) // list index
```

---

## Config Functions

```go
func testAccExampleConfig_basic(rName string) string {
    return fmt.Sprintf(`
resource "provider_example" "test" {
  name = %[1]q
}
`, rName)
}

func testAccExampleConfig_fullFeatures(rName string) string {
    return fmt.Sprintf(`
resource "provider_example" "test" {
  name        = %[1]q
  description = "Full features test"
  enabled     = true

  nested_block {
    key   = "example"
    value = "test"
  }
}
`, rName)
}
```

Use `%[1]q` for quoted strings, `%[1]s` for raw. Numbered verbs (`%[1]`, `%[2]`) for multiple parameters.

---

## Scenario Patterns

### Basic + Import

```go
Steps: []resource.TestStep{
    {
        Config: testAccExampleConfig_basic(rName),
        Check: resource.ComposeTestCheckFunc(
            testAccCheckExampleExists(ctx, resourceName),
        ),
    },
    {
        ResourceName:      resourceName,
        ImportState:       true,
        ImportStateVerify: true,
    },
},
```

### Disappears

```go
Steps: []resource.TestStep{
    {
        Config: testAccExampleConfig_basic(rName),
        Check: resource.ComposeTestCheckFunc(
            testAccCheckExampleExists(ctx, resourceName),
            acctest.CheckResourceDisappears(ctx, acctest.Provider,
                ResourceExample(), resourceName),
        ),
        ExpectNonEmptyPlan: true,
    },
},
```

### Update

```go
Steps: []resource.TestStep{
    {
        Config: testAccExampleConfig_basic(rName),
        Check: resource.ComposeTestCheckFunc(
            resource.TestCheckResourceAttr(resourceName, "description", ""),
        ),
    },
    {
        Config: testAccExampleConfig_updated(rName),
        Check: resource.ComposeTestCheckFunc(
            resource.TestCheckResourceAttr(resourceName, "description", "updated"),
        ),
    },
},
```

### Validation (ExpectError)

```go
Steps: []resource.TestStep{
    {
        Config:      testAccExampleConfig_invalidName(rName),
        ExpectError: regexp.MustCompile(`expected length`),
    },
},
```

---

## Regression Testing

When fixing bugs, use two commits: first introduce a test that reproduces the issue (expect failure), then fix the underlying code. This allows independent verification of both the bug and its resolution. Link to the original bug report in the test comment.

---

## Helper Functions

### Exists

```go
func testAccCheckExampleExists(ctx context.Context, name string) resource.TestCheckFunc {
    return func(s *terraform.State) error {
        rs, ok := s.RootModule().Resources[name]
        if !ok {
            return fmt.Errorf("Not found: %s", name)
        }
        conn := acctest.Provider.Meta().(*conns.Client).ExampleClient(ctx)
        _, err := findExampleByID(ctx, conn, rs.Primary.ID)
        return err
    }
}
```

### Destroy

```go
func testAccCheckExampleDestroy(ctx context.Context) resource.TestCheckFunc {
    return func(s *terraform.State) error {
        conn := acctest.Provider.Meta().(*conns.Client).ExampleClient(ctx)
        for _, rs := range s.RootModule().Resources {
            if rs.Type != "provider_example" {
                continue
            }
            _, err := findExampleByID(ctx, conn, rs.Primary.ID)
            if tfresource.NotFound(err) {
                continue
            }
            if err != nil {
                return err
            }
            return fmt.Errorf("Example %s still exists", rs.Primary.ID)
        }
        return nil
    }
}
```

---

## Sweepers

```go
// sweep_test.go
func init() {
    resource.AddTestSweepers("provider_example", &resource.Sweeper{
        Name: "provider_example",
        F:    sweepExamples,
    })
}

func sweepExamples(region string) error {
    client, err := sharedClientForRegion(region)
    if err != nil {
        return fmt.Errorf("getting client: %w", err)
    }
    // List and delete resources with test prefix
    return nil
}
```

Dependencies for ordered cleanup:

```go
resource.AddTestSweepers("provider_example_child", &resource.Sweeper{
    Name:         "provider_example_child",
    Dependencies: []string{"provider_example"},
    F:            sweepExampleChildren,
})
```

Requires `TestMain`:

```go
func TestMain(m *testing.M) {
    resource.TestMain(m)
}
```

---

## Exports

Re-export resource constructors for test helpers (e.g., `CheckResourceDisappears`):

```go
// exports_test.go
package example_test

import example "github.com/org/provider/internal/service/example"

var ResourceExample = example.NewResourceExample
```

---

## Running Tests

```bash
# Compile only
go test -c -o /dev/null ./internal/service/<service>

# Run one test
TF_ACC=1 go test ./internal/service/<service> -run TestAccExample_basic -v -timeout 60m

# Debug logging
TF_ACC=1 TF_LOG=debug go test ./internal/service/<service> -run TestAccExample_basic -v

# No cache
go test -count=1 ./internal/service/<service> -run TestAccExample_basic

# Sweepers
TF_ACC=1 go test ./internal/service/<service> -sweep=us-east-1 -v
```
