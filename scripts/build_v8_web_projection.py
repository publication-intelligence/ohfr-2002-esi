#!/usr/bin/env python3
"""Build and validate the canonical V8 web-data projection."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from copy import deepcopy
from decimal import Decimal, getcontext
from pathlib import Path
from typing import Any, Iterable, Mapping

from jsonschema import Draft202012Validator


getcontext().prec = 50

SCHEMA_VERSION = "ohfr-v8-canonical-web-projection-v1"
COLLECTION_SCHEMA_VERSION = "ohfr-v8-web-collection-v1"
DEFAULT_EVALUATION_ROOT = Path("staging/v8/evaluation")
DEFAULT_OUTPUT = Path("web/v8-canonical-projection")
CORRECTION_CATEGORY = "digit_for_accent_substitution"
CORRUPTION_PATTERN = re.compile(r"corrupt|malformed", re.IGNORECASE)

DETAIL_PATHS = {
    "candidate": "candidates/oxford-history-french-revolution-2002-original-published-index/candidate-index.draft.v2.json",
    "inventory": "candidates/oxford-history-french-revolution-2002-original-published-index/item-inventory.draft.v2.json",
    "items": "scoring/causal-percentage-native/item-assessments.v7.json",
    "calculation": "scoring/causal-percentage-native/dimension-calculations.v6.json",
    "projection_metadata": "scoring/causal-percentage-native/projection-metadata.v2.json",
    "structure": "structure/structure-audit.v6.json",
    "benchmark": "source/source-benchmark.v2.json",
    "chunk_manifest": "source/chunk-manifest.json",
}

PUBLIC_PATHS = {
    "result": "candidate/v8/evaluation-result.v12.json",
    "web_report": "candidate/v8/web-report.v10.json",
    "correction_ledger": "candidate/representation-adjustment/correction-causal-ledger.v1.json",
    "character_audit": "candidate/representation-adjustment/character-fidelity-audit.v1.json",
}

LOGICAL_DETAIL_PATHS = {
    "candidate": "candidates/<candidate-id>/candidate-index.v2.json",
    "inventory": "candidates/<candidate-id>/item-inventory.v2.json",
    "items": "scoring/item-assessments.v7.json",
    "calculation": "scoring/dimension-calculations.v6.json",
    "projection_metadata": "scoring/projection-metadata.v2.json",
    "structure": "structure/structure-audit.v6.json",
    "benchmark": "source/source-benchmark.v2.json",
    "chunk_manifest": "source/chunk-manifest.json",
}


class ProjectionError(RuntimeError):
    pass


def require(condition: Any, message: str) -> None:
    if not condition:
        raise ProjectionError(message)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectionError(f"Cannot read JSON {path}: {exc}") from exc
    require(isinstance(value, dict), f"Expected a JSON object: {path}")
    return value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def self_hash(value: Mapping[str, Any], field: str) -> str:
    payload = deepcopy(dict(value))
    payload.pop(field, None)
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def grade(score: float | int | None) -> dict[str, Any]:
    if score is None:
        return {
            "score": None,
            "rating": None,
            "band": "not_measured",
            "color_token": "grade_neutral",
            "status": "not_measured",
        }
    bounded = round(max(0.0, min(100.0, float(score))), 2)
    if bounded >= 90:
        band, token, status = "excellent", "grade_excellent", "passes"
    elif bounded >= 80:
        band, token, status = "strong", "grade_strong", "passes_with_issues"
    elif bounded >= 70:
        band, token, status = "mixed", "grade_mixed", "needs_review"
    elif bounded >= 60:
        band, token, status = "weak", "grade_weak", "needs_revision"
    else:
        band, token, status = "poor", "grade_poor", "fails"
    return {
        "score": bounded,
        "rating": round(bounded / 20, 3),
        "band": band,
        "color_token": token,
        "status": status,
    }


def collection(kind: str, items: list[dict[str, Any]], source_order: str) -> dict[str, Any]:
    result = {
        "schema_version": COLLECTION_SCHEMA_VERSION,
        "collection_kind": kind,
        "source_order": source_order,
        "count": len(items),
        "items": items,
    }
    result["collection_sha256"] = self_hash(result, "collection_sha256")
    return result


def canonical_target(value: str) -> str:
    normalized = value.casefold().replace("–", "—")
    normalized = re.sub(r"\s*(?:—|--)\s*", "—", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def corrected_text(issue: Mapping[str, Any], value: str) -> str:
    delivered = str(issue["delivered_text"])
    corrected = str(issue["proposed_corrected_text"])
    require(delivered in value, f"Delivered correction text not found for {issue['issue_id']}")
    return value.replace(delivered, corrected, 1)


def corrected_heading_path(
    heading_path: list[str], issue_by_path: Mapping[str, Mapping[str, Any]], path_id: str
) -> list[str]:
    issue = issue_by_path.get(path_id)
    if issue is None:
        return list(heading_path)
    result = list(heading_path)
    result[-1] = corrected_text(issue, result[-1])
    return result


def character_replacements(issue: Mapping[str, Any]) -> list[dict[str, Any]]:
    delivered = str(issue["delivered_text"])
    corrected = str(issue["proposed_corrected_text"])
    require(len(delivered) == len(corrected), f"Non-substitution correction in {issue['issue_id']}")
    return [
        {
            "issue_id": issue["issue_id"],
            "record_id": issue["record_ids"][0],
            "path_id": issue["path_ids"][0],
            "node_id": issue["node_ids"][-1],
            "character_index": index + 1,
            "delivered_character": before,
            "corrected_character": after,
            "delivered_code_point": f"U+{ord(before):04X}",
            "corrected_code_point": f"U+{ord(after):04X}",
            "causal_classification": issue["causal_classification"],
            "correction_category": issue["correction_category"],
        }
        for index, (before, after) in enumerate(zip(delivered, corrected))
        if before != after
    ]


def adjusted_locator_changes(
    item_assessments: Mapping[str, Any], affected_paths: set[str]
) -> list[dict[str, Any]]:
    changes = []
    for item in item_assessments["locator_assessments"]:
        utility = item["locator_utility"]
        rationale = item["locator_explanation"]["complete_path_fit"]["rationale"]
        if (
            item["path_id"] not in affected_paths
            or utility["fit_category"] != "material_partial_fit"
            or not CORRUPTION_PATTERN.search(rationale)
        ):
            continue
        treatment_score = Decimal(utility["treatment_score"])
        adjusted_score = int(treatment_score * 100)
        adjusted_grade = grade(adjusted_score)
        explanation = "The page treatment is unchanged; correcting the corrupted heading makes complete-path fit exact and the locator keepable."
        changes.append(
            {
                "item_type": "locator",
                "item_id": item["locator_id"],
                "path_id": item["path_id"],
                "causal_classification": "representation_only",
                "observed_judgment": item["judgment"],
                "adjusted_judgment": "supported",
                "observed_complete_path_fit": utility["fit_category"],
                "adjusted_complete_path_fit": "exact_fit",
                "observed_grade": deepcopy(item["grade"]),
                "adjusted_grade": adjusted_grade,
                "grade_delta": round(adjusted_score - float(item["grade"]["score"]), 2),
                "observed_dimension_reliability_credit": item["dimension_reliability_credit"],
                "adjusted_dimension_reliability_credit": "1",
                "retained_page_treatment": utility["treatment_category"],
                "explanation": explanation,
                "adjusted_popover": {
                    "title": f"Adjusted locator {item['source_page_label']}",
                    "summary": explanation,
                    "grade": adjusted_grade,
                    "grade_scope": item["grade_scope"],
                    "confidence": item["confidence"],
                    "factors": [
                        {
                            "factor_id": "complete_path_fit",
                            "observed_status": utility["fit_category"],
                            "adjusted_status": "exact_fit",
                            "explanation": explanation,
                        }
                    ],
                    "navigation": {
                        "locator_id": item["locator_id"],
                        "path_id": item["path_id"],
                    },
                },
            }
        )
    changes.sort(key=lambda row: row["item_id"])
    return changes


def adjusted_heading_changes(
    item_assessments: Mapping[str, Any],
    issues: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    by_node = {row["node_id"]: row for row in item_assessments["heading_node_assessments"]}
    changes = []
    for issue in issues:
        node_id = issue["node_ids"][-1]
        observed = by_node[node_id]
        components = deepcopy(observed["component_results"])
        component_changes = []
        for component in components:
            before_status = component["status"]
            before_score = component["score"]
            if component["dimension_id"] == "mechanics_consistency":
                component["status"], component["score"] = "passes", 100.0
            elif component["dimension_id"] == "heading_access_architecture" and before_status != "passes":
                if node_id == "NODE-1233C7E79FAA":
                    component["status"], component["score"] = "minor_issues", 85.0
                else:
                    component["status"], component["score"] = "passes", 100.0
            if (before_status, before_score) != (component["status"], component["score"]):
                component_changes.append(
                    {
                        "component_id": component["dimension_id"],
                        "observed_status": before_status,
                        "adjusted_status": component["status"],
                        "observed_score": before_score,
                        "adjusted_score": component["score"],
                    }
                )
        adjusted_score = sum(float(row["score"]) for row in components) / len(components)
        adjusted_grade = grade(adjusted_score)
        adjusted_path = corrected_heading_path(
            observed["heading_path"], {issue["path_ids"][0]: issue}, issue["path_ids"][0]
        )
        changes.append(
            {
                "item_type": "heading_node",
                "item_id": node_id,
                "record_id": issue["record_ids"][0],
                "path_id": issue["path_ids"][0],
                "causal_classification": (
                    "mixed" if node_id == "NODE-1233C7E79FAA" else "representation_only"
                ),
                "delivered_heading_path": deepcopy(observed["heading_path"]),
                "corrected_heading_path": adjusted_path,
                "observed_grade": deepcopy(observed["grade"]),
                "adjusted_grade": adjusted_grade,
                "grade_delta": round(adjusted_score - float(observed["grade"]["score"]), 2),
                "component_changes": component_changes,
                "retained_independent_consequence": node_id == "NODE-1233C7E79FAA",
                "adjusted_popover": {
                    "title": " — ".join(adjusted_path),
                    "summary": "Confirmed representation effects are removed from the V8 component grades; any independent V8 consequence is retained.",
                    "grade": adjusted_grade,
                    "grade_scope": observed["grade_scope"],
                    "confidence": "high",
                    "factors": deepcopy(component_changes),
                    "navigation": {"node_id": node_id, "path_id": issue["path_ids"][0]},
                },
            }
        )

    source_node = by_node["NODE-5C19CC7E2872"]
    source_adjusted_grade = grade(100)
    changes.append(
        {
            "item_type": "heading_node",
            "item_id": source_node["node_id"],
            "record_id": source_node["record_ids"][0],
            "path_id": source_node["direct_path_ids"][0],
            "causal_classification": "downstream_cross_reference_resolution",
            "delivered_heading_path": deepcopy(source_node["heading_path"]),
            "corrected_heading_path": deepcopy(source_node["heading_path"]),
            "observed_grade": deepcopy(source_node["grade"]),
            "adjusted_grade": source_adjusted_grade,
            "grade_delta": round(100 - float(source_node["grade"]["score"]), 2),
            "component_changes": [
                {
                    "component_id": "heading_access_architecture",
                    "observed_status": "minor_issues",
                    "adjusted_status": "passes",
                    "observed_score": 85.0,
                    "adjusted_score": 100.0,
                }
            ],
            "retained_independent_consequence": False,
            "adjusted_popover": {
                "title": "conscription — Swiss",
                "summary": "The corrected levée-en-masse target resolves, removing the V8 cross-reference access penalty from this source heading.",
                "grade": source_adjusted_grade,
                "grade_scope": source_node["grade_scope"],
                "confidence": "high",
                "factors": [
                    {
                        "component_id": "heading_access_architecture",
                        "observed_status": "minor_issues",
                        "adjusted_status": "passes",
                        "observed_score": 85.0,
                        "adjusted_score": 100.0,
                    }
                ],
                "navigation": {
                    "node_id": source_node["node_id"],
                    "path_id": source_node["direct_path_ids"][0],
                    "reference_id": "XREF-9A63B6DC42BB",
                },
            },
        }
    )
    changes.sort(key=lambda row: row["item_id"])
    return changes


def adjusted_cross_reference_change(item_assessments: Mapping[str, Any]) -> dict[str, Any]:
    observed = next(
        row
        for row in item_assessments["cross_reference_assessments"]
        if row["reference_id"] == "XREF-9A63B6DC42BB"
    )
    adjusted_grade = grade(100)
    explanation = "Correcting ‘lev2e en masse’ to ‘levée en masse’ creates an exact displayed target for the delivered see-also reference."
    return {
        "item_type": "cross_reference",
        "item_id": observed["reference_id"],
        "record_id": observed["record_id"],
        "source_path_id": observed["source_path_id"],
        "source_node_id": observed["source_node_id"],
        "target_display": observed["target_display"],
        "causal_classification": "representation_only",
        "observed_target_resolution": {"status": "unresolved", "target_path_ids": []},
        "adjusted_target_resolution": {
            "status": "resolved",
            "target_path_ids": ["PATH-26704D6AB01B"],
            "target_node_ids": ["NODE-1233C7E79FAA"],
        },
        "observed_judgment": observed["judgment"],
        "adjusted_judgment": "supported",
        "observed_grade": deepcopy(observed["grade"]),
        "adjusted_grade": adjusted_grade,
        "grade_delta": 50.0,
        "explanation": explanation,
        "adjusted_popover": {
            "title": "Adjusted see also levée en masse",
            "summary": explanation,
            "grade": adjusted_grade,
            "grade_scope": observed["grade_scope"],
            "confidence": "high",
            "factors": [
                {
                    "factor_id": "target_resolution",
                    "observed_status": "unresolved",
                    "adjusted_status": "resolved",
                    "explanation": explanation,
                }
            ],
            "navigation": {
                "source_path_id": observed["source_path_id"],
                "target_path_id": "PATH-26704D6AB01B",
            },
        },
    }


def build_correction_overlay(
    ledger: Mapping[str, Any],
    character_audit: Mapping[str, Any],
    structure: Mapping[str, Any],
    item_assessments: Mapping[str, Any],
    source_bindings: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    require(
        character_audit["scan_summary"]["digit_for_accent_record_count"] == 14
        and character_audit["scan_summary"]["digit_for_accent_character_occurrences"] == 18,
        "Character-fidelity audit does not attest the expected 14/18 correction scope",
    )
    require(
        character_audit["correction_ledger"]["canonical_ledger_sha256"]
        == ledger["ledger_sha256"],
        "Character-fidelity audit and correction ledger identity mismatch",
    )
    issues = [
        row
        for row in ledger["text_order_and_mechanical_issues"]
        if row["correction_category"] == CORRECTION_CATEGORY
        and row["overall_status"] == "confirmed"
    ]
    require(len(issues) == 14, "Expected exactly 14 confirmed digit-substitution headings")
    affected_node_ids = [row["node_ids"][-1] for row in issues]
    defect = next(
        row for row in structure["defects"] if row["defect_id"] == "DEFECT-STRUCT-MECHANICS-001"
    )
    require(
        sorted(affected_node_ids) == sorted(defect["affected_item_ids"]),
        "V8 mechanics defect and correction ledger node sets differ",
    )
    replacements = [item for issue in issues for item in character_replacements(issue)]
    require(len(replacements) == 18, "Expected exactly 18 character substitutions")
    locator_changes = adjusted_locator_changes(
        item_assessments, {row["path_ids"][0] for row in issues}
    )
    require(len(locator_changes) == 9, "Expected exactly 9 V8 locator keep-credit changes")
    overlay = {
        "schema_version": "ohfr-v8-representation-correction-overlay-v1",
        "evaluation_id": item_assessments["evaluation_id"],
        "overlay_role": "display_only_counterfactual_bound_to_canonical_v8",
        "causal_classification": "confirmed_representation_only_digit_for_accent_substitution",
        "affected_heading_count": len(issues),
        "affected_node_ids": sorted(affected_node_ids),
        "character_replacement_count": len(replacements),
        "headings": [
            {
                "issue_id": row["issue_id"],
                "record_id": row["record_ids"][0],
                "path_id": row["path_ids"][0],
                "node_id": row["node_ids"][-1],
                "path_node_ids": deepcopy(row["node_ids"]),
                "as_delivered_heading_path": [row["delivered_text"]]
                if len(row["node_ids"]) == 1
                else None,
                "as_delivered_terminal_heading": row["delivered_text"],
                "corrected_terminal_heading": row["proposed_corrected_text"],
                "causal_classification": row["causal_classification"],
                "confidence": row["confidence"],
                "correction_category": row["correction_category"],
                "replacement_count": len(character_replacements(row)),
            }
            for row in issues
        ],
        "character_replacements": replacements,
        "adjustment_rules": [
            {
                "rule_id": "V8-REP-HEADING-MECHANICS",
                "applies_to": "the 14 terminal heading nodes in DEFECT-STRUCT-MECHANICS-001",
                "effect": "Replace the confirmed digit-for-accent characters and change only the V8 mechanics component from minor_issues/85 to passes/100.",
            },
            {
                "rule_id": "V8-REP-LOCATOR-FIT",
                "applies_to": "locators on corrected paths whose V8 complete-path-fit rationale explicitly attributes material_partial_fit to corruption or malformed display text",
                "effect": "Change complete-path fit to exact_fit and the keep rating credit to 1; retain the V8 page-treatment category and score.",
            },
            {
                "rule_id": "V8-REP-XREF-RESOLUTION",
                "applies_to": "XREF-9A63B6DC42BB",
                "effect": "Resolve the target to PATH-26704D6AB01B / NODE-1233C7E79FAA and change the relationship judgment to supported; leave XREF-6E6F54660707 unresolved.",
            },
            {
                "rule_id": "V8-REP-ACCESS-CONSEQUENCE",
                "applies_to": "heading-access components with representation-caused locator-fit or cross-reference friction",
                "effect": "Remove only the demonstrated representation-caused penalty; retain independent V8 access consequences, including minor_issues/85 for levée en masse.",
            },
            {
                "rule_id": "V8-REP-PATH-DISPLAY-ONLY",
                "applies_to": "all 14 corrected V8 paths",
                "effect": "Correct the displayed path string; V8 path grades remain not_measured.",
            },
        ],
        "adjusted_item_changes": {
            "heading_nodes": adjusted_heading_changes(item_assessments, issues),
            "locators": locator_changes,
            "paths": [
                {
                    "item_type": "path",
                    "item_id": row["path_ids"][0],
                    "record_id": row["record_ids"][0],
                    "node_id": row["node_ids"][-1],
                    "grade_status": "unchanged_not_measured",
                    "delivered_terminal_heading": row["delivered_text"],
                    "corrected_terminal_heading": row["proposed_corrected_text"],
                }
                for row in issues
            ],
            "cross_references": [adjusted_cross_reference_change(item_assessments)],
            "source_subjects": [],
        },
        "cross_reference_resolution": {
            **adjusted_cross_reference_change(item_assessments),
            "remaining_unresolved_reference": {
                "reference_id": "XREF-6E6F54660707",
                "target_display": "individual regiments",
                "judgment": "unsupported",
            },
            "cross_reference_gate_triggered_after_correction": True,
        },
        "defect_outcomes": [
            {
                "defect_id": "DEFECT-STRUCT-MECHANICS-001",
                "observed_affected_count": 14,
                "adjusted_affected_count": 0,
                "adjusted_status": "removed_by_confirmed_representation_correction",
            },
            {
                "defect_id": "DEFECT-STRUCT-XREF-001",
                "observed_affected_count": 2,
                "adjusted_affected_count": 1,
                "adjusted_status": "retained_for_other_unresolved_reference",
                "removed_item_ids": ["XREF-9A63B6DC42BB"],
                "retained_item_ids": ["XREF-6E6F54660707"],
            },
        ],
        "provenance": {
            "v8_structure_artifact": deepcopy(source_bindings["structure"]),
            "v8_item_assessment_artifact": deepcopy(source_bindings["items"]),
            "correction_ledger_artifact": deepcopy(source_bindings["correction_ledger"]),
            "correction_ledger_sha256": ledger["ledger_sha256"],
            "character_audit_artifact": deepcopy(source_bindings["character_audit"]),
            "character_audit_sha256": character_audit["audit_sha256"],
            "applicability_check": "The V8 DEFECT-STRUCT-MECHANICS-001 affected-item set exactly equals the 14 corrected terminal-node IDs, and every delivered terminal heading matches the V8 candidate record.",
            "version_bridge": "The public correction audit predates the V8 evaluation ID. This overlay re-applies only its confirmed digit-for-accent facts to the matching V8 candidate/node identities, then derives item outcomes from V8 assessments and V8 item-grading rules.",
        },
    }
    issue_by_path = {row["path_ids"][0]: row for row in issues}
    by_path = {row["path_id"]: row for row in item_assessments["path_assessments"]}
    for row in overlay["headings"]:
        delivered_path = by_path[row["path_id"]]["heading_path"]
        row["as_delivered_heading_path"] = deepcopy(delivered_path)
        row["corrected_heading_path"] = corrected_heading_path(
            delivered_path, issue_by_path, row["path_id"]
        )
    overlay["overlay_sha256"] = self_hash(overlay, "overlay_sha256")
    return overlay


def resolved_targets(
    target_display: str, target_index: Mapping[str, list[dict[str, str]]]
) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for part in re.split(r"\s*;\s*", target_display):
        matches = target_index.get(canonical_target(part), [])
        if len(matches) != 1:
            return []
        results.extend(matches)
    return results


def build_index_records(
    candidate: Mapping[str, Any],
    inventory: Mapping[str, Any],
    item_assessments: Mapping[str, Any],
    correction_overlay: Mapping[str, Any],
) -> dict[str, Any]:
    paths = {row["path_id"]: row for row in inventory["paths"]}
    nodes = {row["node_id"]: row for row in inventory["heading_nodes"]}
    locator_items = {row["locator_id"]: row for row in item_assessments["locator_assessments"]}
    path_items = {row["path_id"]: row for row in item_assessments["path_assessments"]}
    node_items = {row["node_id"]: row for row in item_assessments["heading_node_assessments"]}
    reference_items = {
        row["reference_id"]: row for row in item_assessments["cross_reference_assessments"]
    }
    issue_by_path = {
        row["path_id"]: row for row in correction_overlay["headings"]
    }
    heading_changes = {
        row["item_id"]: row
        for row in correction_overlay["adjusted_item_changes"]["heading_nodes"]
    }
    locator_changes = {
        row["item_id"]: row
        for row in correction_overlay["adjusted_item_changes"]["locators"]
    }
    xref_changes = {
        row["item_id"]: row
        for row in correction_overlay["adjusted_item_changes"]["cross_references"]
    }

    observed_target_index: dict[str, list[dict[str, str]]] = {}
    adjusted_target_index: dict[str, list[dict[str, str]]] = {}
    for record in candidate["records"]:
        path = paths[record["path_id"]]
        node_id = path["node_ids"][-1]
        adjusted_path = (
            issue_by_path[record["path_id"]]["corrected_heading_path"]
            if record["path_id"] in issue_by_path
            else record["heading_path"]
        )
        entry = {"path_id": record["path_id"], "node_id": node_id}
        observed_target_index.setdefault(
            canonical_target("—".join(record["heading_path"])), []
        ).append(entry)
        adjusted_target_index.setdefault(
            canonical_target("—".join(adjusted_path)), []
        ).append(entry)

    output = []
    for source_order, record in enumerate(candidate["records"]):
        path = paths[record["path_id"]]
        terminal_node_id = path["node_ids"][-1]
        terminal_node = nodes[terminal_node_id]
        adjusted_path = (
            issue_by_path[record["path_id"]]["corrected_heading_path"]
            if record["path_id"] in issue_by_path
            else deepcopy(record["heading_path"])
        )
        heading_hierarchy = []
        for level, (node_id, delivered_heading, corrected_heading) in enumerate(
            zip(path["node_ids"], record["heading_path"], adjusted_path)
        ):
            hierarchy_node = nodes[node_id]
            heading_hierarchy.append(
                {
                    "level": level,
                    "node_id": node_id,
                    "parent_node_id": hierarchy_node["parent_node_id"],
                    "delivered_heading": delivered_heading,
                    "corrected_heading": corrected_heading,
                    "assessment": deepcopy(node_items[node_id]),
                    "adjusted_assessment": deepcopy(heading_changes.get(node_id)),
                }
            )
        displays = []
        for display_order, display in enumerate(record["locator_displays"]):
            atomic = []
            for atomic_order, locator_id in enumerate(display["locator_ids"]):
                assignment = next(
                    row for row in record["locator_assignments"] if row["locator_id"] == locator_id
                )
                assessment = locator_items[locator_id]
                atomic.append(
                    {
                        "atomic_order": atomic_order,
                        "locator_id": locator_id,
                        "source_page_label": assignment["source_page_label"],
                        "document_page": assignment["document_page"],
                        "mapping_status": assignment["mapping_status"],
                        "assessment": deepcopy(assessment),
                        "adjusted_assessment": deepcopy(locator_changes.get(locator_id)),
                    }
                )
            displays.append(
                {
                    "display_order": display_order,
                    "display_id": display["display_id"],
                    "displayed_locator": display["displayed_locator"],
                    "kind": display["kind"],
                    "range_id": display.get("range_id"),
                    "range_start_display": display.get("start_display"),
                    "range_end_display": display.get("end_display"),
                    "mapping_status": display["mapping_status"],
                    "atomic_locator_ids": deepcopy(display["locator_ids"]),
                    "atomic_locators": atomic,
                }
            )

        references = []
        for reference_order, raw in enumerate(record["cross_references"]):
            assessment = reference_items[raw["reference_id"]]
            observed_targets = resolved_targets(raw["target"], observed_target_index)
            adjusted_targets = resolved_targets(raw["target"], adjusted_target_index)
            references.append(
                {
                    "reference_order": reference_order,
                    "reference_id": raw["reference_id"],
                    "reference_type": raw["type"],
                    "source": {
                        "record_id": record["record_id"],
                        "path_id": record["path_id"],
                        "node_id": terminal_node_id,
                        "heading_path": deepcopy(record["heading_path"]),
                    },
                    "target_display": raw["target"],
                    "observed_resolution": {
                        "status": "resolved" if observed_targets else "unresolved",
                        "targets": observed_targets,
                    },
                    "adjusted_resolution": {
                        "status": "resolved" if adjusted_targets else "unresolved",
                        "targets": adjusted_targets,
                    },
                    "observed_judgment": assessment["judgment"],
                    "adjusted_judgment": xref_changes.get(raw["reference_id"], {}).get(
                        "adjusted_judgment", assessment["judgment"]
                    ),
                    "assessment": deepcopy(assessment),
                    "adjusted_assessment": deepcopy(xref_changes.get(raw["reference_id"])),
                }
            )
        output.append(
            {
                "delivered_order": source_order,
                "record_id": record["record_id"],
                "record_type": record["record_type"],
                "path_id": record["path_id"],
                "node_ids": deepcopy(path["node_ids"]),
                "terminal_node_id": terminal_node_id,
                "parent_node_id": terminal_node["parent_node_id"],
                "heading_hierarchy": heading_hierarchy,
                "delivered_indentation_level": record["delivered_indentation_level"],
                "delivered_heading_path": deepcopy(record["heading_path"]),
                "corrected_heading_path": deepcopy(adjusted_path),
                "display_heading_path": deepcopy(adjusted_path),
                "original_displayed_form": record["original_displayed_form"],
                "displayed_locators": displays,
                "cross_references": references,
                "heading_assessment": deepcopy(node_items[terminal_node_id]),
                "adjusted_heading_assessment": deepcopy(heading_changes.get(terminal_node_id)),
                "path_assessment": deepcopy(path_items[record["path_id"]]),
            }
        )
    result = collection("index_records", output, "candidate.records delivered order")
    result["counts"] = {
        "records": len(output),
        "heading_nodes": len(nodes),
        "paths": len(paths),
        "displayed_locators": sum(len(row["displayed_locators"]) for row in output),
        "atomic_locators": sum(
            len(display["atomic_locators"])
            for row in output
            for display in row["displayed_locators"]
        ),
        "cross_references": sum(len(row["cross_references"]) for row in output),
    }
    result["collection_sha256"] = self_hash(result, "collection_sha256")
    return result


def load_missing_access(
    evaluation_root: Path,
) -> tuple[list[dict[str, Any]], list[Path]]:
    directory = evaluation_root / "candidates/oxford-history-french-revolution-2002-original-published-index/missing-access-audits"
    paths = sorted(directory.glob("missing-access-audit.CHUNK-*.v1.json"))
    require(len(paths) == 17, "Expected 17 V8 missing-access audit chunks")
    return [load_json(path) for path in paths], paths


def build_source_subjects(
    benchmark: Mapping[str, Any],
    item_assessments: Mapping[str, Any],
    missing_documents: list[Mapping[str, Any]],
) -> dict[str, Any]:
    assessments = {
        row["subject_id"]: row for row in item_assessments["source_subject_assessments"]
    }
    subject_judgments = {
        row["subject_id"]: row
        for document in missing_documents
        for row in document["subject_judgments"]
    }
    task_results = {
        row["task_id"]: row
        for document in missing_documents
        for row in document["reader_task_results"]
    }
    treatments = [
        row for document in missing_documents for row in document["treatment_judgments"]
    ]
    treatment_by_subject: dict[str, list[dict[str, Any]]] = {}
    for row in treatments:
        treatment_by_subject.setdefault(row["subject_id"], []).append(row)
    tasks = {row["subject_ids"][0]: row for row in benchmark["reader_tasks"]}
    require(len(assessments) == len(subject_judgments) == len(tasks) == 638, "V8 source-subject denominator mismatch")
    require(len(treatments) == 1569, "V8 expected-treatment denominator mismatch")

    output = []
    for source_order, subject in enumerate(benchmark["subjects"]):
        subject_id = subject["subject_id"]
        task = tasks[subject_id]
        evidence_by_key: dict[tuple[int, str], list[Mapping[str, Any]]] = {}
        for evidence in subject["evidence"]:
            evidence_by_key.setdefault(
                (evidence["document_page"], evidence["locator_class"]), []
            ).append(evidence)
        expected_treatments = []
        for treatment in treatment_by_subject.get(subject_id, []):
            matches = evidence_by_key.get(
                (treatment["document_page"], treatment["locator_class"]), []
            )
            require(matches, f"Missing benchmark evidence for {treatment['treatment_id']}")
            expected_treatments.append(
                {
                    "treatment_id": treatment["treatment_id"],
                    "subject_id": subject_id,
                    "document_page": treatment["document_page"],
                    "source_page_label": matches[0]["source_page_label"],
                    "locator_class": treatment["locator_class"],
                    "status": treatment["status"],
                    "evidence_ids": deepcopy(treatment["evidence_ids"]),
                }
            )
        expected_treatments.sort(key=lambda row: row["treatment_id"])
        output.append(
            {
                "source_order": source_order,
                "subject_id": subject_id,
                "label": subject["label"],
                "priority": subject["priority"],
                "meaning": subject["meaning"],
                "stance": subject["stance"],
                "acceptable_access": deepcopy(subject["acceptable_access"]),
                "chapter_provenance": deepcopy(subject["chapter_provenance"]),
                "source_chunk_ids": deepcopy(subject["source_chunk_ids"]),
                "assessment": deepcopy(assessments[subject_id]),
                "audit_judgment": deepcopy(subject_judgments[subject_id]),
                "reader_task": {
                    "task_id": task["task_id"],
                    "question": task["question"],
                    "subject_ids": deepcopy(task["subject_ids"]),
                    "task_basis": task["task_basis"],
                    "result": deepcopy(task_results[task["task_id"]]),
                },
                "expected_treatments": expected_treatments,
            }
        )
    result = collection("source_subjects", output, "frozen benchmark subject order")
    result["counts"] = {
        "source_subjects": len(output),
        "reader_tasks": len({row["reader_task"]["task_id"] for row in output}),
        "expected_treatments": sum(len(row["expected_treatments"]) for row in output),
    }
    result["collection_sha256"] = self_hash(result, "collection_sha256")
    return result


def build_density(
    structure: Mapping[str, Any], chunk_manifest: Mapping[str, Any]
) -> dict[str, Any]:
    chunks = {row["chunk_id"]: row for row in chunk_manifest["chunks"]}
    findings = {
        row["chunk_id"]: row for row in structure["density"]["distribution_findings"]
    }
    rows = []
    for source_order, measurement in enumerate(structure["density"]["chapter_measurements"]):
        chunk = chunks[measurement["chunk_id"]]
        finding = findings[measurement["chunk_id"]]
        combined = (
            "within_acceptable_bands"
            if finding["finding"] == "within_path_band"
            and finding["locator_occurrence_finding"] == "within_occurrence_band"
            else "outside_one_or_more_acceptable_bands"
        )
        rows.append(
            {
                "source_order": source_order,
                "chunk_id": measurement["chunk_id"],
                "title": chunk["title"],
                "source_units": deepcopy(chunk["source_units"]),
                "owned_document_page_ranges": deepcopy(chunk["owned_document_page_ranges"]),
                **deepcopy(measurement),
                "canonical_fit_judgment": {
                    "combined": combined,
                    "path_rate": finding["finding"],
                    "locator_occurrence_rate": finding["locator_occurrence_finding"],
                    "interpretation": finding["interpretation"],
                    "automatic_defect": False,
                },
            }
        )
    result = collection("density", rows, "chunk manifest packet order")
    result["policy_status"] = structure["density"]["policy_status"]
    result["measurement_level"] = structure["density"]["measurement_level"]
    result["targets"] = deepcopy(structure["density"]["targets"])
    result["maximum_score_contribution"] = structure["density"]["maximum_score_contribution"]
    result["fit_rating"] = structure["density"]["fit_rating"]
    result["collection_sha256"] = self_hash(result, "collection_sha256")
    return result


def source_binding(path: str, file_path: Path, **extra: Any) -> dict[str, Any]:
    return {"artifact_path": path, "sha256": sha256_file(file_path), **extra}


def decimal_text(value: Decimal) -> str:
    return format(value, "f")


def build_projection(
    repository_root: Path, evaluation_root: Path, output_directory: Path
) -> dict[str, Any]:
    public_files = {key: repository_root / value for key, value in PUBLIC_PATHS.items()}
    detail_files = {key: evaluation_root / value for key, value in DETAIL_PATHS.items()}
    public = {key: load_json(path) for key, path in public_files.items()}
    detail = {key: load_json(path) for key, path in detail_files.items()}
    missing_documents, missing_paths = load_missing_access(evaluation_root)

    result = public["result"]
    web = public["web_report"]
    require(result["schema_version"] == "subject-index-evaluation-result-v12", "V8 result required")
    require(web["schema_version"] == "subject-index-web-report-v10", "V8 web report required")
    require(result["evaluation_id"] == detail["items"]["evaluation_id"], "Evaluation identity mismatch")
    require(result["overall_percentage"] == 89.38, "Unexpected canonical V8 score")
    require(web["score_views"]["views"][0]["score"] == result["overall_percentage"], "V8 score mismatch")
    require(web["score_views"]["adjustment_status"] == "none", "Canonical V8 source must expose no prior adjustment")
    require(result["item_assessments"]["summary"] == detail["items"]["summary"], "Current detail item summary mismatch")

    for key, result_field in (
        ("items", "item_assessments"),
        ("calculation", "dimension_calculations"),
        ("structure", "structure_audit"),
        ("projection_metadata", "projection_metadata"),
    ):
        require(
            sha256_file(detail_files[key]) == result[result_field]["sha256"],
            f"Current V8 detail binding mismatch for {key}",
        )
    require(
        detail["benchmark"]["benchmark_sha256"] == result["provenance"]["benchmark_sha256"],
        "V8 benchmark identity mismatch",
    )

    bindings: dict[str, dict[str, Any]] = {
        key: source_binding(PUBLIC_PATHS[key], path, availability="public_committed")
        for key, path in public_files.items()
    }
    for key, path in detail_files.items():
        bindings[key] = source_binding(
            LOGICAL_DETAIL_PATHS[key],
            path,
            availability="restricted_local_build_input_not_committed_under_candidate/v8",
        )
    for index, path in enumerate(missing_paths, start=1):
        bindings[f"missing_access_{index:03d}"] = source_binding(
            f"candidates/<candidate-id>/missing-access-audits/{path.name}",
            path,
            availability="restricted_local_build_input_not_committed_under_candidate/v8",
        )

    overlay = build_correction_overlay(
        public["correction_ledger"],
        public["character_audit"],
        detail["structure"],
        detail["items"],
        bindings,
    )
    index_records = build_index_records(
        detail["candidate"], detail["inventory"], detail["items"], overlay
    )
    source_subjects = build_source_subjects(
        detail["benchmark"], detail["items"], missing_documents
    )
    density = build_density(detail["structure"], detail["chunk_manifest"])

    output_directory.mkdir(parents=True, exist_ok=True)
    data_directory = output_directory / "data"
    for filename, value in (
        ("correction-overlay.v1.json", overlay),
        ("index-records.v1.json", index_records),
        ("source-subjects.v1.json", source_subjects),
        ("density.v1.json", density),
    ):
        write_json(data_directory / filename, value)

    observed_scorecard = [
        {
            "dimension_id": row["dimension_id"],
            "rating": float(Decimal(row["dimension_percentage"]) / Decimal(20)),
            "awarded_points": float(Decimal(row["weighted_contribution"])),
            "maximum_points": row["weight"],
            "formula_id": row["formula_id"],
        }
        for row in web["scorecard"]
    ]
    adjusted_scorecard = [
        {**deepcopy(row), "rating_delta": 0, "points_delta": 0}
        for row in observed_scorecard
    ]

    canonical_precision = Decimal(web["precision_diagnostics"]["keep_precision"])
    recall = Decimal(web["precision_diagnostics"]["treatment_recall"])
    adjusted_numerator = 5123 + len(overlay["adjusted_item_changes"]["locators"])
    adjusted_denominator = 5338
    adjusted_precision = Decimal(adjusted_numerator) / Decimal(adjusted_denominator)
    adjusted_f1 = Decimal(2) * adjusted_precision * recall / (adjusted_precision + recall)
    require(adjusted_precision > canonical_precision, "Adjusted keep precision must improve")

    gates = deepcopy(result["critical_gates"])
    readiness = {
        "status": "not_publication_ready",
        "triggered_gate_ids": [row["gate_id"] for row in gates if row["triggered"]],
        "cross_reference_gate_remains_triggered": True,
        "reason": "XREF-6E6F54660707 remains unresolved, and the other canonical triggered gates are unchanged.",
    }
    collection_values = {
        "correction_overlay": overlay,
        "index_records": index_records,
        "source_subjects": source_subjects,
        "density": density,
    }
    collection_paths = {
        "correction_overlay": "data/correction-overlay.v1.json",
        "index_records": "data/index-records.v1.json",
        "source_subjects": "data/source-subjects.v1.json",
        "density": "data/density.v1.json",
    }
    collections = [
        {
            "collection_id": key,
            "artifact_path": collection_paths[key],
            "count": value["count"] if "count" in value else value["affected_heading_count"],
            "content_sha256": value.get("collection_sha256", value.get("overlay_sha256")),
            "file_sha256": sha256_file(output_directory / collection_paths[key]),
        }
        for key, value in collection_values.items()
    ]

    projection_seed = {
        "evaluation_id": result["evaluation_id"],
        "canonical_result_sha256": bindings["result"]["sha256"],
        "overlay_sha256": overlay["overlay_sha256"],
    }
    projection = {
        "schema_version": SCHEMA_VERSION,
        "projection_id": "OHFR-V8-WEB-" + hashlib.sha256(canonical_bytes(projection_seed)).hexdigest()[:12].upper(),
        "projection_role": "deterministic_public_safe_display_projection",
        "evaluation_id": result["evaluation_id"],
        "view_selection": {
            "authoritative_view_id": "canonical_as_delivered",
            "primary_view_id": "canonical_as_delivered",
            "default_display_view_id": "representation_adjusted",
            "display_view_rationale": "The percentage-native observed V8 result remains authoritative; the default display repairs confirmed representation-only accent substitutions without creating a separate scoring view.",
        },
        "score_views": {
            "canonical_source_adjustment_status": web["score_views"]["adjustment_status"],
            "projection_adjustment_status": "confirmed_representation_adjustment_applied",
            "total_delta": 0,
            "views": [
                {
                    "view_id": "canonical_as_delivered",
                    "label": "Canonical as delivered",
                    "view_kind": "observed",
                    "role": "authoritative_primary_observation",
                    "score": result["overall_percentage"],
                    "maximum": 100,
                    "scorecard": observed_scorecard,
                    "critical_gates": gates,
                    "readiness": readiness,
                    "provenance_artifacts": [bindings["result"], bindings["web_report"], bindings["calculation"]],
                },
                {
                    "view_id": "representation_adjusted",
                    "label": "Representation adjusted",
                    "view_kind": "counterfactual_display",
                    "role": "default_display_secondary_counterfactual",
                    "score": result["overall_percentage"],
                    "maximum": 100,
                    "score_delta": 0,
                    "scorecard": adjusted_scorecard,
                    "critical_gates": gates,
                    "gate_outcomes_equal_to_observed": True,
                    "readiness": readiness,
                    "readiness_equal_to_observed": True,
                    "score_stability_reason": "Confirmed representation corrections affect the index presentation and diagnostics only; the percentage-native report scores the canonical as-delivered evidence, so both display views retain the same scorecard.",
                    "adjusted_diagnostics": {
                        "keep_precision_numerator": adjusted_numerator,
                        "keep_precision_denominator": adjusted_denominator,
                        "keep_precision": decimal_text(adjusted_precision),
                        "treatment_recall": decimal_text(recall),
                        "reliability_f1": decimal_text(adjusted_f1),
                        "locator_keep_credit_changes": len(overlay["adjusted_item_changes"]["locators"]),
                        "cross_reference_counts": {"supported": 15, "partially_supported": 0, "unsupported": 1},
                        "mechanics_defect_affected_headings": 0,
                    },
                    "provenance_artifacts": [bindings["result"], bindings["calculation"], bindings["structure"], bindings["items"], bindings["correction_ledger"], bindings["character_audit"]],
                },
            ],
        },
        "correction_outcomes": {
            "affected_headings": 14,
            "character_replacements": 18,
            "corrected_cross_reference_id": "XREF-9A63B6DC42BB",
            "remaining_unresolved_cross_reference_id": "XREF-6E6F54660707",
            "observed_minor_defect_count": 4,
            "adjusted_minor_defect_count": 3,
            "cross_reference_gate_unchanged": True,
            "readiness_unchanged": True,
        },
        "item_summaries": {
            "observed": deepcopy(result["item_assessments"]["summary"]),
            "adjusted": {
                **deepcopy(detail["items"]["summary"]),
                "locators": {
                    **deepcopy(detail["items"]["summary"]["locators"]),
                    "bands": {
                        **deepcopy(detail["items"]["summary"]["locators"]["bands"]),
                        "excellent": 3521,
                        "mixed": 1704,
                    },
                },
                "locator_utility_tiers": {
                    **deepcopy(detail["items"]["summary"]["locator_utility_tiers"]),
                    "fit": {
                        **deepcopy(detail["items"]["summary"]["locator_utility_tiers"]["fit"]),
                        "exact_fit": 5150,
                        "material_partial_fit": 93,
                    },
                    "diagnostic_credit": {
                        **deepcopy(detail["items"]["summary"]["locator_utility_tiers"]["diagnostic_credit"]),
                        "0.7": 1704,
                        "1": 3521,
                    },
                    "rating_credit": {
                        "0": 206,
                        "1": 5132,
                    },
                },
                "heading_nodes": {
                    **deepcopy(detail["items"]["summary"]["heading_nodes"]),
                    "bands": {
                        **deepcopy(detail["items"]["summary"]["heading_nodes"]["bands"]),
                        "excellent": 1796,
                        "strong": 95,
                    },
                },
                "cross_references": {
                    **deepcopy(detail["items"]["summary"]["cross_references"]),
                    "bands": {
                        **deepcopy(detail["items"]["summary"]["cross_references"]["bands"]),
                        "excellent": 15,
                        "poor": 1,
                    },
                },
            },
        },
        "collections": collections,
        "provenance": {
            "source_artifacts": [bindings[key] for key in sorted(bindings)],
            "source_sha256": result["provenance"]["source_sha256"],
            "benchmark_sha256": result["provenance"]["benchmark_sha256"],
            "judgment_policy_sha256": result["provenance"]["judgment_policy_sha256"],
            "rubric_version": result["provenance"]["rubric_version"],
            "dimension_calculation_profile": result["provenance"]["dimension_calculation_profile"],
            "projection_metadata_sha256": result["projection_metadata"]["projection_metadata_sha256"],
            "calculation_sha256": result["dimension_calculations"]["calculation_sha256"],
            "missing_access_audit_set_sha256": detail["items"]["evidence_identity"]["missing_access_audit_set_sha256"],
            "correction_overlay_sha256": overlay["overlay_sha256"],
        },
        "public_safety": {
            "source_excerpts_included": False,
            "restricted_files_included": False,
            "private_layout_evidence_included": False,
            "absolute_paths_included": False,
            "source_subject_summaries_are_synthesized_not_quoted": True,
        },
        "limitations": [
            "The representation-adjusted view is a deterministic counterfactual projection, not a replacement for the canonical as-delivered V8 result.",
            "Restricted detailed artifacts are used only as validated local build inputs; their public hashes are retained, but the files themselves remain uncommitted.",
            "Current V8 causal-provenance artifacts supply the detailed collection source and are hash-bound to the public result.",
            "The representation corrections are presentation-only under the percentage-native V8 report and do not create a separately recalculated score.",
            "Aggregate scores are taken from the authoritative V8 calculation and are not reconstructed by averaging item grades.",
        ],
    }
    projection["projection_sha256"] = self_hash(projection, "projection_sha256")
    write_json(output_directory / "projection.v1.json", projection)
    validate_projection_output(output_directory)
    return projection


def validate_schema(instance: Mapping[str, Any], schema_path: Path) -> None:
    schema = load_json(schema_path)
    errors = sorted(Draft202012Validator(schema).iter_errors(instance), key=lambda row: list(row.path))
    require(not errors, "; ".join(error.message for error in errors[:10]))


def privacy_scan(output_directory: Path) -> None:
    prohibited = (
        "/home/",
        "staging/",
        "private_evidence",
        "layout_line_ids",
        "region_ids",
        '"bboxes"',
        ".pdf",
    )
    for path in output_directory.rglob("*.json"):
        text = path.read_text(encoding="utf-8")
        for token in prohibited:
            require(token not in text, f"Public-safety token {token!r} found in {path}")


def validate_projection_output(output_directory: Path) -> dict[str, Any]:
    projection = load_json(output_directory / "projection.v1.json")
    validate_schema(projection, output_directory / "projection.schema.json")
    require(projection["projection_sha256"] == self_hash(projection, "projection_sha256"), "Projection self-hash mismatch")
    require(projection["score_views"]["total_delta"] == 0, "V8 total delta must be explicit zero")
    require(projection["view_selection"]["primary_view_id"] == "canonical_as_delivered", "Observed V8 view must remain primary")
    require(projection["view_selection"]["default_display_view_id"] == "representation_adjusted", "Adjusted V8 view must be the explicit display view")
    require(projection["correction_outcomes"]["affected_headings"] == 14, "Affected-heading count mismatch")
    require(projection["correction_outcomes"]["character_replacements"] == 18, "Replacement count mismatch")
    adjusted_tiers = projection["item_summaries"]["adjusted"]["locator_utility_tiers"]
    require(sum(adjusted_tiers["fit"].values()) == 5338, "Adjusted fit-tier total mismatch")
    require(sum(adjusted_tiers["diagnostic_credit"].values()) == 5338, "Adjusted diagnostic-credit total mismatch")
    require(sum(adjusted_tiers["rating_credit"].values()) == 5338, "Adjusted rating-credit total mismatch")
    require(adjusted_tiers["rating_credit"] == {"0": 206, "1": 5132}, "Adjusted locator keep-credit counts mismatch")

    by_id = {row["collection_id"]: row for row in projection["collections"]}
    expected = {"correction_overlay", "index_records", "source_subjects", "density"}
    require(set(by_id) == expected, "Projection collection set mismatch")
    values = {}
    for collection_id, binding in by_id.items():
        path = output_directory / binding["artifact_path"]
        require(path.is_file(), f"Missing projected collection {path}")
        require(sha256_file(path) == binding["file_sha256"], f"Collection file hash mismatch: {collection_id}")
        value = load_json(path)
        validate_schema(value, output_directory / "collection.schema.json")
        values[collection_id] = value
        content_field = "overlay_sha256" if collection_id == "correction_overlay" else "collection_sha256"
        require(value[content_field] == self_hash(value, content_field), f"Collection self-hash mismatch: {collection_id}")
        require(value[content_field] == binding["content_sha256"], f"Projection collection binding mismatch: {collection_id}")

    overlay = values["correction_overlay"]
    records = values["index_records"]
    subjects = values["source_subjects"]
    density = values["density"]
    require(overlay["affected_heading_count"] == 14, "Overlay heading count mismatch")
    expected_node_ids = {
        "NODE-1233C7E79FAA",
        "NODE-1641E4FD4B44",
        "NODE-2424A4C28F25",
        "NODE-33047D522FEE",
        "NODE-367FC46D5C72",
        "NODE-680872D8E4EF",
        "NODE-7F548C32E062",
        "NODE-811B50B6DF90",
        "NODE-84D205EE3593",
        "NODE-894E2872B253",
        "NODE-A137505DA3E5",
        "NODE-A86D09652F29",
        "NODE-DD7675F9AF8F",
        "NODE-E9AB8D11D630",
    }
    require(set(overlay["affected_node_ids"]) == expected_node_ids, "Overlay node IDs must be the complete V8 mechanics-defect set")
    require(overlay["character_replacement_count"] == len(overlay["character_replacements"]) == 18, "Overlay character rows mismatch")
    require(len(overlay["adjusted_item_changes"]["locators"]) == 9, "Adjusted locator count mismatch")
    require(records["count"] == 1904, "Index record count mismatch")
    require(records["counts"] == {"records": 1904, "heading_nodes": 1904, "paths": 1904, "displayed_locators": 4462, "atomic_locators": 5338, "cross_references": 16}, "Index display summary mismatch")
    require([row["delivered_order"] for row in records["items"]] == list(range(1904)), "Delivered record order is not contiguous")
    require(len({row["record_id"] for row in records["items"]}) == 1904, "Record IDs are not complete and unique")
    require(len({row["path_id"] for row in records["items"]}) == 1904, "Path IDs are not complete and unique")
    require(len({row["terminal_node_id"] for row in records["items"]}) == 1904, "Terminal node IDs are not complete and unique")
    require(all("popover" in row["heading_assessment"] and "popover" in row["path_assessment"] for row in records["items"]), "Heading/path popover coverage mismatch")
    require(sum(len(row["displayed_locators"]) for row in records["items"]) == 4462, "Displayed locator count mismatch")
    require(sum(len(display["atomic_locators"]) for row in records["items"] for display in row["displayed_locators"]) == 5338, "Atomic locator count mismatch")
    atomic_rows = [atomic for row in records["items"] for display in row["displayed_locators"] for atomic in display["atomic_locators"]]
    require(len({row["locator_id"] for row in atomic_rows}) == 5338, "Atomic locator IDs are not complete and unique")
    require(all("popover" in row["assessment"] and row["source_page_label"] for row in atomic_rows), "Locator popover or source-page-label coverage mismatch")
    require(all(display["atomic_locator_ids"] == [row["locator_id"] for row in display["atomic_locators"]] for record in records["items"] for display in record["displayed_locators"]), "Displayed-to-atomic locator order mismatch")
    require(sum(len(row["cross_references"]) for row in records["items"]) == 16, "Cross-reference count mismatch")
    references = {
        reference["reference_id"]: reference
        for record in records["items"]
        for reference in record["cross_references"]
    }
    require(len(references) == 16 and all("popover" in row["assessment"] for row in references.values()), "Cross-reference assessment/popover coverage mismatch")
    corrected_reference = references["XREF-9A63B6DC42BB"]
    require(corrected_reference["observed_resolution"]["status"] == "unresolved", "Corrected cross-reference must be unresolved as delivered")
    require(corrected_reference["adjusted_resolution"]["status"] == "resolved", "Corrected cross-reference must resolve in the adjusted display")
    require(corrected_reference["adjusted_resolution"]["targets"] == [{"path_id": "PATH-26704D6AB01B", "node_id": "NODE-1233C7E79FAA"}], "Corrected cross-reference target mismatch")
    require(references["XREF-6E6F54660707"]["adjusted_resolution"]["status"] == "unresolved", "The independent unresolved cross-reference must remain")
    require(subjects["count"] == 638, "Source-subject count mismatch")
    require(subjects["counts"] == {"source_subjects": 638, "reader_tasks": 638, "expected_treatments": 1569}, "Source collection summary mismatch")
    require(sum(len(row["expected_treatments"]) for row in subjects["items"]) == 1569, "Expected-treatment count mismatch")
    require(len({row["reader_task"]["task_id"] for row in subjects["items"]}) == 638, "Reader-task count mismatch")
    require(all("popover" in row["assessment"] for row in subjects["items"]), "Source-subject popover coverage mismatch")
    require(all(treatment["source_page_label"] for row in subjects["items"] for treatment in row["expected_treatments"]), "Expected-treatment source-page-label coverage mismatch")
    require(density["count"] == 17, "Density row count mismatch")
    privacy_scan(output_directory)
    return projection


def copy_contracts(contract_directory: Path, output_directory: Path) -> None:
    output_directory.mkdir(parents=True, exist_ok=True)
    for name in ("projection.schema.json", "collection.schema.json"):
        source = contract_directory / name
        target = output_directory / name
        if source.resolve() != target.resolve():
            shutil.copyfile(source, target)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "validate"))
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--evaluation-root", default=str(DEFAULT_EVALUATION_ROOT))
    parser.add_argument("--output-directory", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--contract-directory", default=str(DEFAULT_OUTPUT))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repository_root = Path(args.repository_root).resolve()
    evaluation_root = (repository_root / args.evaluation_root).resolve()
    output_directory = (repository_root / args.output_directory).resolve()
    contract_directory = (repository_root / args.contract_directory).resolve()
    try:
        copy_contracts(contract_directory, output_directory)
        if args.command == "build":
            projection = build_projection(repository_root, evaluation_root, output_directory)
        else:
            projection = validate_projection_output(output_directory)
        print(
            json.dumps(
                {
                    "command": f"{args.command}-v8-web-projection",
                    "ok": True,
                    "projection_id": projection["projection_id"],
                    "projection_sha256": projection["projection_sha256"],
                    "canonical_score": projection["score_views"]["views"][0]["score"],
                    "representation_adjusted_score": projection["score_views"]["views"][1]["score"],
                    "total_delta": projection["score_views"]["total_delta"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except (OSError, ProjectionError) as exc:
        print(json.dumps({"command": f"{args.command}-v8-web-projection", "ok": False, "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
