"""Regression tests for the canonical V8 web-data projection."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_v8_web_projection as projection_builder  # noqa: E402


OUTPUT = ROOT / "web/v8-canonical-projection"


def load(relative: str) -> dict:
    return json.loads((OUTPUT / relative).read_text(encoding="utf-8"))


class V8WebProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.projection = projection_builder.validate_projection_output(OUTPUT)

    def test_view_roles_scores_and_zero_delta_are_explicit(self) -> None:
        selection = self.projection["view_selection"]
        self.assertEqual("canonical_as_delivered", selection["authoritative_view_id"])
        self.assertEqual("canonical_as_delivered", selection["primary_view_id"])
        self.assertEqual("representation_adjusted", selection["default_display_view_id"])

        views = self.projection["score_views"]["views"]
        self.assertEqual(["canonical_as_delivered", "representation_adjusted"], [row["view_id"] for row in views])
        self.assertEqual([89.38, 89.38], [row["score"] for row in views])
        self.assertEqual(0, self.projection["score_views"]["total_delta"])
        self.assertEqual(0, views[1]["score_delta"])
        self.assertAlmostEqual(4.992778361344538, views[1]["scorecard"][-1]["rating"])
        self.assertTrue(all(row["formula_id"].startswith("subject-index-dimension-calculation-v5:") for row in views[0]["scorecard"]))
        source_paths = {row["artifact_path"] for row in self.projection["provenance"]["source_artifacts"]}
        self.assertIn("candidate/v8/evaluation-result.v12.json", source_paths)
        self.assertIn("candidate/v8/web-report.v10.json", source_paths)
        self.assertTrue(views[1]["readiness_equal_to_observed"])
        self.assertEqual("not_publication_ready", views[1]["readiness"]["status"])

    def test_overlay_has_the_complete_correction_and_causal_rows(self) -> None:
        overlay = load("data/correction-overlay.v1.json")
        expected_nodes = {
            "NODE-1233C7E79FAA", "NODE-1641E4FD4B44", "NODE-2424A4C28F25",
            "NODE-33047D522FEE", "NODE-367FC46D5C72", "NODE-680872D8E4EF",
            "NODE-7F548C32E062", "NODE-811B50B6DF90", "NODE-84D205EE3593",
            "NODE-894E2872B253", "NODE-A137505DA3E5", "NODE-A86D09652F29",
            "NODE-DD7675F9AF8F", "NODE-E9AB8D11D630",
        }
        self.assertEqual(expected_nodes, set(overlay["affected_node_ids"]))
        self.assertEqual(14, len(overlay["headings"]))
        self.assertEqual(18, len(overlay["character_replacements"]))
        self.assertTrue(all(row["causal_classification"] == "representation_only" for row in overlay["character_replacements"]))
        self.assertEqual({"2", "3"}, {row["delivered_character"] for row in overlay["character_replacements"]})
        self.assertTrue(all(row["delivered_heading_path"] != row["corrected_heading_path"] for row in overlay["adjusted_item_changes"]["heading_nodes"] if row["item_id"] in expected_nodes))

    def test_adjusted_item_and_cross_reference_outcomes_are_bounded(self) -> None:
        overlay = load("data/correction-overlay.v1.json")
        changes = overlay["adjusted_item_changes"]
        self.assertEqual(15, len(changes["heading_nodes"]))
        self.assertEqual(9, len(changes["locators"]))
        self.assertEqual(14, len(changes["paths"]))
        self.assertEqual(1, len(changes["cross_references"]))
        self.assertTrue(all(row["adjusted_popover"] for row in changes["heading_nodes"]))
        self.assertTrue(all(row["adjusted_popover"] for row in changes["locators"]))
        self.assertTrue(changes["cross_references"][0]["adjusted_popover"])

        resolution = overlay["cross_reference_resolution"]
        self.assertEqual("XREF-9A63B6DC42BB", resolution["item_id"])
        self.assertEqual("partially_supported", resolution["observed_judgment"])
        self.assertEqual("supported", resolution["adjusted_judgment"])
        self.assertEqual(["PATH-26704D6AB01B"], resolution["adjusted_target_resolution"]["target_path_ids"])
        self.assertEqual("XREF-6E6F54660707", resolution["remaining_unresolved_reference"]["reference_id"])
        self.assertTrue(resolution["cross_reference_gate_triggered_after_correction"])

    def test_complete_index_display_counts_and_resolution(self) -> None:
        records = load("data/index-records.v1.json")
        self.assertEqual(
            {
                "records": 1904,
                "heading_nodes": 1904,
                "paths": 1904,
                "displayed_locators": 4462,
                "atomic_locators": 5338,
                "cross_references": 16,
            },
            records["counts"],
        )
        self.assertEqual(list(range(1904)), [row["delivered_order"] for row in records["items"]])
        self.assertTrue(all(len(row["heading_hierarchy"]) == len(row["node_ids"]) == len(row["delivered_heading_path"]) for row in records["items"]))
        self.assertTrue(all(display["atomic_locator_ids"] == [row["locator_id"] for row in display["atomic_locators"]] for record in records["items"] for display in record["displayed_locators"]))
        references = {xref["reference_id"]: xref for record in records["items"] for xref in record["cross_references"]}
        self.assertEqual("unresolved", references["XREF-9A63B6DC42BB"]["observed_resolution"]["status"])
        self.assertEqual("resolved", references["XREF-9A63B6DC42BB"]["adjusted_resolution"]["status"])
        self.assertEqual("unresolved", references["XREF-6E6F54660707"]["adjusted_resolution"]["status"])

    def test_heading_access_causal_provenance_is_complete(self) -> None:
        records = load("data/index-records.v1.json")
        assessments = [row["heading_assessment"] for row in records["items"]]
        adverse = [row for row in assessments if row["heading_access_status"] in {"minor_issues", "major_issues", "fails"}]
        findings = [finding for row in assessments for finding in row["heading_access_causal_findings"]]
        self.assertEqual(224, len(adverse))
        self.assertTrue(all(row["heading_access_causal_findings"] for row in adverse))
        self.assertEqual(256, len(findings))
        self.assertEqual(
            {"benchmark_access": 203, "heading_fit": 48, "confirmed_subdivision_architecture": 3, "cross_reference": 2},
            {kind: sum(finding["kind"] == kind for finding in findings) for kind in {finding["kind"] for finding in findings}},
        )

    def test_source_tasks_treatments_and_named_density_rows_are_complete(self) -> None:
        subjects = load("data/source-subjects.v1.json")
        self.assertEqual(
            {"source_subjects": 638, "reader_tasks": 638, "expected_treatments": 1569},
            subjects["counts"],
        )
        self.assertTrue(all(row["reader_task"]["result"] for row in subjects["items"]))
        self.assertTrue(all(treatment["source_page_label"] for row in subjects["items"] for treatment in row["expected_treatments"]))

        density = load("data/density.v1.json")
        self.assertEqual(17, density["count"])
        self.assertTrue(all(row["title"] and row["canonical_fit_judgment"]["combined"] for row in density["items"]))

    def test_adjusted_item_summaries_reconcile(self) -> None:
        adjusted = self.projection["item_summaries"]["adjusted"]
        self.assertEqual({"excellent": 15, "strong": 0, "mixed": 0, "weak": 0, "poor": 1, "not_measured": 0}, adjusted["cross_references"]["bands"])
        self.assertEqual(5150, adjusted["locator_utility_tiers"]["fit"]["exact_fit"])
        self.assertEqual(93, adjusted["locator_utility_tiers"]["fit"]["material_partial_fit"])
        self.assertEqual({"0": 206, "1": 5132}, adjusted["locator_utility_tiers"]["rating_credit"])

    def test_public_safety_contract(self) -> None:
        projection_builder.privacy_scan(OUTPUT)
        self.assertEqual(
            {
                "source_excerpts_included": False,
                "restricted_files_included": False,
                "private_layout_evidence_included": False,
                "absolute_paths_included": False,
                "source_subject_summaries_are_synthesized_not_quoted": True,
            },
            self.projection["public_safety"],
        )


if __name__ == "__main__":
    unittest.main()
