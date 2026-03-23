import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.semantic_reasoner import generate_semantic_interpretations, semantic_abstraction_profile, semantic_action_roles, semantic_goal, semantic_intent_votes
from zero_os.task_planner_parsing import _split_subgoals, extract_request_targets


class SemanticReasonerTests(unittest.TestCase):
    def test_semantic_roles_map_same_meaning_across_phrasing(self) -> None:
        requests = [
            "get data from https://example.com",
            "retrieve info from https://example.com",
            "load results from https://example.com",
        ]
        role_sets = []
        for request in requests:
            decomposition = _split_subgoals(request)
            role_sets.append(tuple(semantic_action_roles(request, decomposition)))

        self.assertTrue(all(role_set == role_sets[0] for role_set in role_sets[1:]))
        self.assertIn("retrieve", role_sets[0])

    def test_semantic_interpretations_generate_diverse_structures(self) -> None:
        request = "open https://example.com and click and show file src/main.py"
        decomposition = _split_subgoals(request)
        targets = extract_request_targets(request)

        interpretations = generate_semantic_interpretations(request, decomposition, targets)

        self.assertGreaterEqual(len(interpretations), 10)
        self.assertIn("inspect_then_mutate_resource", {item["goal"] for item in interpretations})
        self.assertGreaterEqual(len({"->".join(item["structure"]) for item in interpretations}), 4)

    def test_semantic_votes_follow_target_and_role_shape(self) -> None:
        request = "retrieve info from https://example.com and click"
        decomposition = _split_subgoals(request)
        targets = extract_request_targets(request)

        votes = semantic_intent_votes(request, targets, decomposition)

        self.assertIn("retrieve", votes["roles"])
        self.assertGreater(float(votes["votes"]["web"]), 0.0)
        self.assertGreater(float(votes["votes"]["browser"]), 0.0)
        self.assertEqual("inspect_then_mutate_resource", semantic_goal(request, targets, decomposition))

    def test_semantic_abstraction_maps_cross_domain_observation_to_same_family(self) -> None:
        remote_request = "retrieve info from https://example.com"
        workspace_request = "read file src/main.py and show file src/main.py"

        remote_profile = semantic_abstraction_profile(
            remote_request,
            extract_request_targets(remote_request),
            _split_subgoals(remote_request),
        )
        workspace_profile = semantic_abstraction_profile(
            workspace_request,
            extract_request_targets(workspace_request),
            _split_subgoals(workspace_request),
        )

        self.assertEqual("source_observation_pattern", remote_profile["structure_family"])
        self.assertEqual(remote_profile["structure_family"], workspace_profile["structure_family"])
        self.assertIn("source_retrieval_equivalence", remote_profile["analogies"])
        self.assertIn("source_retrieval_equivalence", workspace_profile["analogies"])
        self.assertIn("fetch_surface_equivalence", remote_profile["analogies"])
        self.assertIn("file_fetch_equivalence", workspace_profile["analogies"])

    def test_semantic_abstraction_adds_browser_and_deploy_analogies(self) -> None:
        browser_request = "open https://example.com and click"
        deploy_request = "deploy artifact build/app.zip to prod"

        browser_profile = semantic_abstraction_profile(
            browser_request,
            extract_request_targets(browser_request),
            _split_subgoals(browser_request),
        )
        deploy_profile = semantic_abstraction_profile(
            deploy_request,
            extract_request_targets(deploy_request),
            _split_subgoals(deploy_request),
        )

        self.assertIn("state_change_equivalence", browser_profile["analogies"])
        self.assertIn("browser_fetch_equivalence", browser_profile["analogies"])
        self.assertIn("delivery_pipeline_equivalence", deploy_profile["analogies"])
        self.assertIn("deploy_control_equivalence", deploy_profile["analogies"])


if __name__ == "__main__":
    unittest.main()
