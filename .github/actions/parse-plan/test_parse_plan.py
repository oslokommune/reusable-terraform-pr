import json
import pathlib
import unittest

import parse_plan as pp


def _plan(resources=(), outputs=None):
    """A minimal `terraform show -json` document with the given action verbs."""
    return {
        "resource_changes": [{"change": {"actions": list(a)}} for a in resources],
        "output_changes": {
            name: {"actions": list(a)} for name, a in (outputs or {}).items()
        },
    }


class TestResourceChanges(unittest.TestCase):
    def test_empty_plan_is_no_changes(self):
        self.assertEqual("no-changes", pp.classify(_plan()))

    def test_noop_and_read_are_no_changes(self):
        self.assertEqual("no-changes", pp.classify(_plan([["no-op"], ["read"]])))

    def test_create_is_additive(self):
        self.assertEqual("additive", pp.classify(_plan([["create"], ["create"]])))

    def test_update_is_non_destructive(self):
        self.assertEqual("non-destructive", pp.classify(_plan([["update"]])))

    def test_create_and_update_is_non_destructive(self):
        self.assertEqual("non-destructive", pp.classify(_plan([["create"], ["update"]])))

    def test_delete_is_any_changes(self):
        self.assertEqual("any-changes", pp.classify(_plan([["delete"]])))

    def test_replace_is_any_changes(self):
        self.assertEqual("any-changes", pp.classify(_plan([["delete", "create"]])))

    def test_replace_create_before_destroy_is_any_changes(self):
        self.assertEqual("any-changes", pp.classify(_plan([["create", "delete"]])))

    def test_create_with_replace_is_any_changes(self):
        self.assertEqual(
            "any-changes", pp.classify(_plan([["create"], ["delete", "create"]]))
        )

    def test_forget_is_any_changes(self):
        """A removed block orphans the object instead of destroying it."""
        self.assertEqual("any-changes", pp.classify(_plan([["forget"]])))

    def test_replace_by_forget_is_any_changes(self):
        self.assertEqual("any-changes", pp.classify(_plan([["create", "forget"]])))

    def test_unrankable_verb_is_any_changes(self):
        self.assertEqual("any-changes", pp.classify(_plan([["mystery"]])))

    def test_import_only_is_no_changes(self):
        """importing is a field, not a verb: an import-only plan adds only state."""
        plan = {"resource_changes": [{"change": {"actions": ["no-op"], "importing": {"id": "abc"}}}]}
        self.assertEqual("no-changes", pp.classify(plan))

    def test_import_with_update_is_non_destructive(self):
        plan = {"resource_changes": [{"change": {"actions": ["update"], "importing": {"id": "abc"}}}]}
        self.assertEqual("non-destructive", pp.classify(plan))


class TestOutputChanges(unittest.TestCase):
    def test_output_noop_is_no_changes(self):
        self.assertEqual("no-changes", pp.classify(_plan(outputs={"url": ["no-op"]})))

    def test_output_create_is_additive(self):
        self.assertEqual("additive", pp.classify(_plan(outputs={"url": ["create"]})))

    def test_output_update_is_non_destructive(self):
        self.assertEqual("non-destructive", pp.classify(_plan(outputs={"url": ["update"]})))

    def test_output_delete_is_any_changes(self):
        """Deleting an output breaks remote-state consumers, so it ranks with destruction."""
        self.assertEqual("any-changes", pp.classify(_plan(outputs={"url": ["delete"]})))

    def test_output_create_and_update_is_non_destructive(self):
        self.assertEqual(
            "non-destructive",
            pp.classify(_plan(outputs={"url": ["update"], "name": ["create"]})),
        )

    def test_output_unrankable_verb_is_any_changes(self):
        self.assertEqual("any-changes", pp.classify(_plan(outputs={"url": ["mystery"]})))

    def test_create_with_output_create_is_additive(self):
        self.assertEqual(
            "additive", pp.classify(_plan([["create"]], {"url": ["create"]}))
        )

    def test_create_with_output_update_is_non_destructive(self):
        """An existing output changing outranks a purely additive plan."""
        self.assertEqual(
            "non-destructive", pp.classify(_plan([["create"]], {"url": ["update"]}))
        )

    def test_create_with_output_delete_is_any_changes(self):
        self.assertEqual(
            "any-changes", pp.classify(_plan([["create"]], {"url": ["delete"]}))
        )

    def test_update_with_output_delete_is_any_changes(self):
        self.assertEqual(
            "any-changes", pp.classify(_plan([["update"]], {"url": ["delete"]}))
        )

    def test_delete_with_output_delete_is_any_changes(self):
        """Resource and output deletes both rank with destruction."""
        self.assertEqual(
            "any-changes", pp.classify(_plan([["delete"]], {"url": ["delete"]}))
        )

    def test_update_with_output_noop_is_non_destructive(self):
        self.assertEqual(
            "non-destructive", pp.classify(_plan([["update"]], {"url": ["no-op"]}))
        )


class TestVersionCheck(unittest.TestCase):
    def test_supported_major_passes(self):
        self.assertTrue(pp.verify_version({"format_version": "1.2"}))

    def test_future_major_fails(self):
        self.assertFalse(pp.verify_version({"format_version": "2.0"}))

    def test_missing_version_fails(self):
        self.assertFalse(pp.verify_version({}))


class TestFailSafes(unittest.TestCase):
    def test_missing_keys_are_no_changes(self):
        """resource_changes and output_changes may be absent or null."""
        self.assertEqual("no-changes", pp.classify({}))
        self.assertEqual(
            "no-changes", pp.classify({"resource_changes": None, "output_changes": None})
        )


class TestRealPlans(unittest.TestCase):
    """Scrubbed plans from real runs and their expected changes values."""

    PLANS = {
        "dev-remote-state.json": "no-changes",
        "dev-site-cdn-resource-moved.json": "no-changes",
        "dev-site-cdn-data-new-output.json": "additive",
        "dev-site-cdn-output-updated.json": "non-destructive",
        "dev-cicd-common-import-with-update.json": "non-destructive",
        "dev-cicd-common-role-replaced.json": "any-changes",
        "dev-site-cdn-resource-removed.json": "any-changes",
    }

    def test_real_plans(self):
        testdata = pathlib.Path(__file__).parent / "testdata"
        # every fixture on disk is asserted, and every assertion has a fixture
        self.assertEqual(set(self.PLANS), {path.name for path in testdata.glob("*.json")})
        for name, expected in self.PLANS.items():
            with self.subTest(plan=name):
                with open(testdata / name) as f:
                    plan = json.load(f)
                self.assertTrue(pp.verify_version(plan))
                self.assertEqual(expected, pp.classify(plan))


if __name__ == "__main__":
    unittest.main()
