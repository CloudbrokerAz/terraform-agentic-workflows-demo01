#!/usr/bin/env python3
"""Fetch a compliance baseline from Prowler and emit a near-complete YAML rule set.

Prowler (Apache-2.0, prowler-cloud/prowler) maintains an AWS-focused compliance
catalogue covering ~45 frameworks. Each framework has a structured JSON file
listing requirements, with each requirement pointing at one or more `check_id`s.
Each check has its own metadata file with severity, ResourceType, terraform
snippet, CLI snippet, console steps, recommendation text, and cross-framework
mappings.

This script joins the two sources and produces YAML rules conforming to the
tf-research-policy-aws schema. After running this script you typically only
need the model to add `condition.logic`, refine `tags`, and pick a stable `id`
where the auto-derived one isn't ideal.

Usage:
  scripts/fetch_prowler_baseline.py --list-frameworks
  scripts/fetch_prowler_baseline.py --framework cis_3.0_aws --output policy-research/cis-3.0.yaml
  scripts/fetch_prowler_baseline.py --framework hipaa  --output policy-research/hipaa.yaml
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import pathlib
import re
import sys
import urllib.parse
import urllib.request
from typing import Any

import yaml

REPO = "prowler-cloud/prowler"
BRANCH = "master"
COMPLIANCE_DIR = "prowler/compliance/aws"
SERVICES_DIR = "prowler/providers/aws/services"
RAW_BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"
API_BASE = f"https://api.github.com/repos/{REPO}"


# ASFF resource type prefix -> CFN type prefix. Best-effort.
ASFF_CFN_MAP = {
    "AwsAccount": "AWS::Organizations::Account",
    "AwsApiGatewayRestApi": "AWS::ApiGateway::RestApi",
    "AwsApiGatewayStage": "AWS::ApiGateway::Stage",
    "AwsApiGatewayV2Api": "AWS::ApiGatewayV2::Api",
    "AwsApiGatewayV2Stage": "AWS::ApiGatewayV2::Stage",
    "AwsAutoScalingAutoScalingGroup": "AWS::AutoScaling::AutoScalingGroup",
    "AwsAutoScalingLaunchConfiguration": "AWS::AutoScaling::LaunchConfiguration",
    "AwsBackupBackupPlan": "AWS::Backup::BackupPlan",
    "AwsBackupBackupVault": "AWS::Backup::BackupVault",
    "AwsCertificateManagerCertificate": "AWS::CertificateManager::Certificate",
    "AwsCloudFormationStack": "AWS::CloudFormation::Stack",
    "AwsCloudFrontDistribution": "AWS::CloudFront::Distribution",
    "AwsCloudTrailTrail": "AWS::CloudTrail::Trail",
    "AwsCloudWatchAlarm": "AWS::CloudWatch::Alarm",
    "AwsCodeBuildProject": "AWS::CodeBuild::Project",
    "AwsDmsReplicationInstance": "AWS::DMS::ReplicationInstance",
    "AwsDynamoDbTable": "AWS::DynamoDB::Table",
    "AwsEc2Eip": "AWS::EC2::EIP",
    "AwsEc2Instance": "AWS::EC2::Instance",
    "AwsEc2NetworkAcl": "AWS::EC2::NetworkAcl",
    "AwsEc2NetworkInterface": "AWS::EC2::NetworkInterface",
    "AwsEc2RouteTable": "AWS::EC2::RouteTable",
    "AwsEc2SecurityGroup": "AWS::EC2::SecurityGroup",
    "AwsEc2Snapshot": "AWS::EC2::Snapshot",
    "AwsEc2Subnet": "AWS::EC2::Subnet",
    "AwsEc2TransitGateway": "AWS::EC2::TransitGateway",
    "AwsEc2Volume": "AWS::EC2::Volume",
    "AwsEc2Vpc": "AWS::EC2::VPC",
    "AwsEc2VpcEndpoint": "AWS::EC2::VPCEndpoint",
    "AwsEc2VpcPeeringConnection": "AWS::EC2::VPCPeeringConnection",
    "AwsEc2VpnConnection": "AWS::EC2::VPNConnection",
    "AwsEcrRepository": "AWS::ECR::Repository",
    "AwsEcsCluster": "AWS::ECS::Cluster",
    "AwsEcsService": "AWS::ECS::Service",
    "AwsEcsTaskDefinition": "AWS::ECS::TaskDefinition",
    "AwsEfsAccessPoint": "AWS::EFS::AccessPoint",
    "AwsEfsFileSystem": "AWS::EFS::FileSystem",
    "AwsEksCluster": "AWS::EKS::Cluster",
    "AwsElasticBeanstalkEnvironment": "AWS::ElasticBeanstalk::Environment",
    "AwsElasticsearchDomain": "AWS::Elasticsearch::Domain",
    "AwsElbLoadBalancer": "AWS::ElasticLoadBalancing::LoadBalancer",
    "AwsElbv2LoadBalancer": "AWS::ElasticLoadBalancingV2::LoadBalancer",
    "AwsEmrCluster": "AWS::EMR::Cluster",
    "AwsGuardDutyDetector": "AWS::GuardDuty::Detector",
    "AwsIamAccessKey": "AWS::IAM::AccessKey",
    "AwsIamGroup": "AWS::IAM::Group",
    "AwsIamPolicy": "AWS::IAM::ManagedPolicy",
    "AwsIamRole": "AWS::IAM::Role",
    "AwsIamUser": "AWS::IAM::User",
    "AwsKinesisStream": "AWS::Kinesis::Stream",
    "AwsKmsKey": "AWS::KMS::Key",
    "AwsLambdaFunction": "AWS::Lambda::Function",
    "AwsLambdaLayerVersion": "AWS::Lambda::LayerVersion",
    "AwsNetworkFirewallFirewall": "AWS::NetworkFirewall::Firewall",
    "AwsOpenSearchServiceDomain": "AWS::OpenSearchService::Domain",
    "AwsRdsDbCluster": "AWS::RDS::DBCluster",
    "AwsRdsDbClusterSnapshot": "AWS::RDS::DBClusterSnapshot",
    "AwsRdsDbInstance": "AWS::RDS::DBInstance",
    "AwsRdsDbSnapshot": "AWS::RDS::DBSnapshot",
    "AwsRedshiftCluster": "AWS::Redshift::Cluster",
    "AwsRoute53HostedZone": "AWS::Route53::HostedZone",
    "AwsS3AccountPublicAccessBlock": "AWS::S3::AccountPublicAccessBlock",
    "AwsS3Bucket": "AWS::S3::Bucket",
    "AwsSageMakerNotebookInstance": "AWS::SageMaker::NotebookInstance",
    "AwsSecretsManagerSecret": "AWS::SecretsManager::Secret",
    "AwsSnsTopic": "AWS::SNS::Topic",
    "AwsSqsQueue": "AWS::SQS::Queue",
    "AwsSsmAssociationCompliance": "AWS::SSM::Association",
    "AwsSsmPatchCompliance": "AWS::SSM::PatchBaseline",
    "AwsStepFunctionStateMachine": "AWS::StepFunctions::StateMachine",
    "AwsTransferServer": "AWS::Transfer::Server",
    "AwsWafRegionalRule": "AWS::WAFRegional::Rule",
    "AwsWafRegionalWebAcl": "AWS::WAFRegional::WebACL",
    "AwsWafv2WebAcl": "AWS::WAFv2::WebACL",
    "AwsWorkspacesWorkspace": "AWS::WorkSpaces::Workspace",
}


def http_get(url: str, *, accept: str = "application/json") -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "tf-research-policy-aws/1",
            "Accept": accept,
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def list_frameworks() -> list[str]:
    contents = json.loads(http_get(f"{API_BASE}/contents/{COMPLIANCE_DIR}?ref={BRANCH}"))
    names = []
    for item in contents:
        name = item.get("name") or ""
        if name.endswith(".json"):
            names.append(name[:-5])
    return sorted(names)


def fetch_compliance(framework: str) -> dict[str, Any]:
    url = f"{RAW_BASE}/{COMPLIANCE_DIR}/{framework}.json"
    return json.loads(http_get(url))


def build_check_index() -> dict[str, str]:
    """Walk the git tree once to map check_id -> service path.

    Returns dict mapping check_id to the directory holding its metadata file.
    """
    tree = json.loads(http_get(f"{API_BASE}/git/trees/{BRANCH}?recursive=1"))
    if tree.get("truncated"):
        print("warn: git tree was truncated; some checks may not be found", file=sys.stderr)
    index: dict[str, str] = {}
    pattern = re.compile(rf"^{re.escape(SERVICES_DIR)}/([^/]+)/([^/]+)/\2\.metadata\.json$")
    for entry in tree.get("tree", []):
        m = pattern.match(entry.get("path") or "")
        if m:
            service, check_id = m.group(1), m.group(2)
            index[check_id] = f"{SERVICES_DIR}/{service}/{check_id}/{check_id}.metadata.json"
    return index


def fetch_check_metadata(check_id: str, index: dict[str, str]) -> dict[str, Any] | None:
    rel = index.get(check_id)
    if not rel:
        return None
    try:
        return json.loads(http_get(f"{RAW_BASE}/{rel}"))
    except urllib.error.HTTPError:
        return None


def asff_to_cfn_resource_types(asff: str) -> list[str]:
    if not asff:
        return []
    if asff in ASFF_CFN_MAP:
        return [ASFF_CFN_MAP[asff]]
    return [f"TODO: map ASFF '{asff}' to AWS::Service::Resource"]


def normalise_terraform(snippet: str | None) -> str:
    if not snippet:
        return ""
    s = snippet.strip()
    # Strip leading ```hcl / ```terraform / ```yaml fences
    s = re.sub(r"^```[a-z]*\n", "", s)
    s = re.sub(r"\n```$", "", s)
    return s


def parse_references(req_attr: dict[str, Any], check_meta: dict[str, Any] | None) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(title: str, url: str) -> None:
        if url and url not in seen:
            seen.add(url)
            refs.append({"title": title, "url": url})

    # framework requirement references (colon-separated)
    raw = (req_attr or {}).get("References") or ""
    for url in re.split(r"\s+|;|,(?=https?://)", raw):
        url = url.strip().rstrip(";.,")
        if url.startswith("http"):
            add("Framework reference", url)

    if check_meta:
        for url in check_meta.get("AdditionalURLs") or []:
            if isinstance(url, str) and url.startswith("http"):
                add("Background", url)
        rec_url = (check_meta.get("Remediation") or {}).get("Recommendation", {}).get("Url")
        if rec_url:
            add("Prowler check page", rec_url)
    return refs


def derive_related_controls(check_types: list[str]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if not check_types:
        return out
    seen: set[str] = set()
    for ct in check_types:
        # CheckType strings look like:
        #   "Software and Configuration Checks/Industry and Regulatory Standards/PCI-DSS"
        parts = ct.split("/")
        if len(parts) < 3:
            continue
        last = parts[-1]
        # heuristic clean-up
        framework = re.sub(r"\s*\([^)]+\)\s*$", "", last).strip()
        if framework in seen or not framework:
            continue
        seen.add(framework)
        out.append({"framework": framework, "id": "see CheckType mapping"})
    return out


def kebab(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def to_rule(
    requirement: dict[str, Any],
    check_id: str,
    check_meta: dict[str, Any] | None,
) -> dict[str, Any]:
    attr = (requirement.get("Attributes") or [{}])[0]
    cm = check_meta or {}

    severity = (cm.get("Severity") or "").upper() or None
    if severity not in {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL", None}:
        severity = None  # validator will complain on null but we won't fabricate

    resource_types = asff_to_cfn_resource_types(cm.get("ResourceType") or "")
    service = cm.get("ServiceName") or "TODO: aws service slug"

    title = cm.get("CheckTitle") or requirement.get("Description") or check_id

    framework_requirement = (
        attr.get("Description")
        or requirement.get("Description")
        or "TODO: verbatim requirement text"
    )

    remediation_text = ((cm.get("Remediation") or {}).get("Recommendation") or {}).get("Text") or ""
    remediation_code = (cm.get("Remediation") or {}).get("Code") or {}
    terraform = normalise_terraform(remediation_code.get("Terraform") or "")
    cli = (remediation_code.get("CLI") or "").strip()
    console = (remediation_code.get("Other") or "").strip()

    # AWS Config managed-rule identifier mapping is *not* deterministic from
    # Prowler — most checks are bespoke boto3 calls. Mark TODO for human/codegen.
    return {
        "id": kebab(check_id),
        "title": title,
        "framework_control": {
            "id": requirement.get("Id"),
            "title": requirement.get("Description"),
            "requirement": framework_requirement,
        },
        "related_controls": derive_related_controls(cm.get("CheckType") or []),
        "severity": severity if severity else "TODO: severity not provided by Prowler",
        "service": service,
        "resource_types": resource_types or ["TODO: AWS::Service::Resource"],
        "source": {
            "type": "aws-config-custom-rule",
            "identifier": f"prowler:{check_id}",
            "documentation_url": (
                ((cm.get("Remediation") or {}).get("Recommendation") or {}).get("Url")
                or f"https://hub.prowler.com/check/{check_id}"
            ),
            "parameters": {},
        },
        "condition": {
            "description": cm.get("Description") or "TODO: plain-English description",
            "parameters": {},
            "logic": "TODO: pseudocode (Prowler check is procedural; see Prowler check page)",
        },
        "remediation": {
            "summary": remediation_text or "TODO: remediation summary",
            "terraform_snippet": terraform or "TODO: minimal compliant HCL",
            **({"aws_cli_snippet": cli} if cli else {}),
            **({"console_steps": [s.strip() for s in console.splitlines() if s.strip()]} if console else {}),
            **({"notes": cm.get("Risk")} if cm.get("Risk") else {}),
        },
        "references": parse_references(attr, cm),
        "test_cases": [
            {
                "name": "TODO: compliant case",
                "input": {"resource_type": (resource_types or [""])[0], "properties": {}},
                "expected": "COMPLIANT",
            },
            {
                "name": "TODO: non-compliant case",
                "input": {"resource_type": (resource_types or [""])[0], "properties": {}},
                "expected": "NON_COMPLIANT",
            },
        ],
        "tags": cm.get("Categories") or [],
        "provenance": {
            "framework_control": "third-party-prowler",
            "severity": "third-party-prowler",
            "source_identifier": "third-party-prowler",
            "resource_types": "third-party-prowler",
            "condition_description": "third-party-prowler",
            "remediation_summary": "third-party-prowler",
            "remediation_terraform": "third-party-prowler" if terraform else "unknown",
            "remediation_cli": "third-party-prowler" if cli else "unknown",
            "remediation_console": "third-party-prowler" if console else "unknown",
            "references": ["third-party-prowler"],
            "tags": "third-party-prowler",
            "_note": (
                "Prowler is community open-source (Apache-2.0) and not AWS-official. "
                "Re-run with AWS-official sources (parse_conformance_pack.py + "
                "fetch_security_hub_controls.py) where available, then use merge_yaml.py "
                "to combine."
            ),
        },
    }


def build_document(framework_id: str, framework_json: dict[str, Any], index: dict[str, str]) -> dict[str, Any]:
    rules: list[dict[str, Any]] = []
    skipped: list[str] = []
    for req in framework_json.get("Requirements") or []:
        for check_id in req.get("Checks") or []:
            cm = fetch_check_metadata(check_id, index)
            if cm is None:
                skipped.append(check_id)
            rules.append(to_rule(req, check_id, cm))
    if skipped:
        print(
            f"warn: no metadata found for {len(skipped)} check(s); "
            f"first 5: {', '.join(skipped[:5])}",
            file=sys.stderr,
        )
    return {
        "metadata": {
            "framework": {
                "name": framework_json.get("Name") or framework_id,
                "version": str(framework_json.get("Version") or ""),
            },
            "source": f"https://github.com/{REPO}/blob/{BRANCH}/{COMPLIANCE_DIR}/{framework_id}.json",
            "generated_by": "tf-research-policy-aws",
            "generated_at": _dt.date.today().isoformat(),
            "notes": (
                "Skeleton produced from Prowler compliance + per-check metadata "
                "(prowler-cloud/prowler, Apache-2.0). source.identifier values "
                "use the prowler:<check_id> form because Prowler checks are not "
                "1:1 with AWS Config managed rules. If the rule maps to a Config "
                "managed rule, replace source with the managed-rule identifier."
            ),
        },
        "rules": rules,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list-frameworks", action="store_true")
    parser.add_argument("--framework", help="framework id, e.g. 'cis_3.0_aws' (substring match)")
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()

    if args.list_frameworks:
        for fw in list_frameworks():
            print(fw)
        return 0

    if not args.framework:
        print("must supply --framework or --list-frameworks", file=sys.stderr)
        return 2

    frameworks = list_frameworks()
    needle = args.framework.lower()
    matches = [f for f in frameworks if needle in f.lower()]
    if not matches:
        print(f"no framework matched '{args.framework}'. Use --list-frameworks.", file=sys.stderr)
        return 2
    if len(matches) > 1:
        print(f"'{args.framework}' matched: {', '.join(matches)}. Be more specific.", file=sys.stderr)
        return 2
    framework_id = matches[0]

    print(f"fetching framework {framework_id} ...", file=sys.stderr)
    framework_json = fetch_compliance(framework_id)
    print(f"building check index from git tree ...", file=sys.stderr)
    index = build_check_index()
    print(f"resolving {sum(len(r.get('Checks') or []) for r in framework_json.get('Requirements') or [])} checks ...", file=sys.stderr)
    doc = build_document(framework_id, framework_json, index)

    out = yaml.safe_dump(doc, sort_keys=False, width=100, default_flow_style=False, allow_unicode=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(out, encoding="utf-8")
        print(f"wrote {len(doc['rules'])} rules to {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
