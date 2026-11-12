"""Gramps Web integration tests use synthetic in-memory API responses only."""
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[1]
SKILL = Path(os.environ.get("FAMILY_TREE_SKILL", REPO / "skills/family-tree-chatgpt"))
SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gramps = load("gramps")
research = load("research")
family_tree = load("family_tree")


def model_patch():
    citation = {"source_id": "source_one", "locator": "p. 1", "quotation": "", "note": ""}

    def claim(identifier, subject_type, subject_id, predicate, value, status="supported"):
        return {
            "id": identifier,
            "subject": {"type": subject_type, "id": subject_id},
            "predicate": predicate,
            "value": value,
            "status": status,
            "citations": [citation],
            "rationale": "Synthetic cited conclusion." if status != "unverified" else "",
            "notes": "",
            "extensions": {},
        }

    return {
        "persons": [
            {"id": "parent", "label": "Synthetic parent", "notes": "", "extensions": {}},
            {"id": "child", "label": "Synthetic child", "notes": "", "extensions": {}},
        ],
        "relationships": [{
            "id": "parent_child",
            "type": "parent_child",
            "participants": [
                {"person_id": "parent", "role": "parent"},
                {"person_id": "child", "role": "child"},
            ],
            "notes": "",
            "extensions": {},
        }],
        "sources": [{
            "id": "source_one",
            "kind": "synthetic_register",
            "title": "Synthetic register",
            "citation": "Synthetic archive, book 1, page 1.",
            "repository": "Synthetic archive",
            "url": "https://example.invalid/source",
            "accessed_on": "2026-11-12",
            "files": [],
            "record_ids": [],
            "notes": "",
            "extensions": {},
        }],
        "claims": [
            claim("parent_given", "person", "parent", "name.given", "Alex"),
            claim("parent_surname", "person", "parent", "name.surname", "Example"),
            claim("parent_sex", "person", "parent", "sex", "M"),
            claim("child_given", "person", "child", "name.given", "Sam"),
            claim("child_surname", "person", "child", "name.surname", "Example"),
            claim("child_birth", "person", "child", "birth.date", "1900-01-02"),
            claim(
                "child_birth_guess", "person", "child", "birth.date", "1901", status="unverified"
            ),
            claim(
                "relationship_truth",
                "relationship",
                "parent_child",
                "relationship.parent_child",
                True,
            ),
        ],
        "conflicts": [],
    }


class FakeClient:
    def __init__(self):
        self.base_url = "https://gramps.example/api"
        self.objects = {}
        self._metadata = {
            "database": {"id": "synthetic-tree", "name": "Synthetic Tree", "schema": "21.0.0"},
            "gramps": {"version": "6.0.0"},
            "gramps_webapi": {"version": "3.7.2"},
            "object_counts": {"people": 0},
            "server": {"multi_tree": False, "task_queue": True},
        }

    def metadata(self):
        return json.loads(json.dumps(self._metadata))

    def get_optional(self, object_class, handle):
        value = self.objects.get((object_class, handle))
        return None if value is None else json.loads(json.dumps(value))

    def create_objects(self, payloads):
        for payload in payloads:
            value = json.loads(json.dumps(payload))
            value.pop("_class", None)
            value["change"] = 1
            self.objects[(payload["_class"], payload["handle"])] = value


class GrampsIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "private"
        research.initialize(self.root)
        research.apply_model(self.root, 0, model_patch(), "Export synthetic evidence.")
        self.client = FakeClient()

    def parse(self, arguments, workspace=True):
        command = []
        if workspace:
            command += ["--workspace", str(self.root)]
        return family_tree.build_parser().parse_args(command + arguments)

    def execute(self, arguments, workspace=True):
        args = self.parse(arguments, workspace=workspace)
        with patch.object(family_tree, "gramps_client", return_value=self.client):
            return family_tree.execute(args)

    def test_mapping_exports_only_supported_claims_and_private_objects(self):
        state = research.read_state(self.root)
        built = gramps.build_objects(state)
        self.assertNotIn("child_birth_guess", built["eligible_claim_ids"])
        self.assertEqual(built["excluded_claims"]["child_birth_guess"], "status_unverified")
        classes = [item["object_class"] for item in built["objects"]]
        self.assertEqual(classes.count("Person"), 2)
        self.assertEqual(classes.count("Event"), 1)
        self.assertEqual(classes.count("Family"), 1)
        self.assertTrue(all(item["payload"]["private"] for item in built["objects"]))
        family = next(item["payload"] for item in built["objects"] if item["object_class"] == "Family")
        self.assertIn("father_handle", family)
        child = next(
            item["payload"] for item in built["objects"]
            if item["object_class"] == "Person"
            and item["local_key"] == "person:child"
        )
        self.assertEqual(child["primary_name"]["first_name"], "Sam")
        self.assertEqual(child["birth_ref_index"], 0)

    def test_probe_plan_push_and_status_command_roundtrip(self):
        probe = self.execute(
            ["gramps", "probe", "--url", "https://gramps.example"], workspace=False
        )
        self.assertTrue(probe["connected"])
        self.assertTrue(probe["compatible"])
        self.assertEqual(probe["database"]["id"], "synthetic-tree")

        plan_path = Path(self.temp.name) / "gramps-plan.json"
        planned = self.execute([
            "gramps", "plan", str(plan_path), "--url", "https://gramps.example"
        ])
        self.assertGreater(planned["actions"]["create"], 0)
        self.assertEqual(stat.S_IMODE(plan_path.stat().st_mode), 0o600)

        pushed = self.execute([
            "gramps", "push", str(plan_path), "--url", "https://gramps.example"
        ])
        self.assertEqual(pushed["created"], planned["actions"]["create"])
        self.assertEqual(pushed["created"], pushed["verified"])

        current = self.execute([
            "gramps", "status", "--url", "https://gramps.example"
        ])
        self.assertEqual(current["status"], "synchronized")
        self.assertEqual(current["actions"]["create"], 0)

    def test_conflict_and_changed_plan_are_rejected_without_writes(self):
        state = research.read_state(self.root)
        state_hash = research.sha256(self.root / "research.json")
        plan = gramps.make_plan(self.client, state, state_hash)
        first = next(item for item in plan["objects"] if item["action"] == "create")
        collision = json.loads(json.dumps(first["payload"]))
        collision["gramps_id"] = "UNRELATED"
        self.client.objects[(first["object_class"], collision["handle"])] = collision
        conflicted = gramps.make_plan(self.client, state, state_hash)
        self.assertEqual(
            next(item for item in conflicted["objects"] if item["local_key"] == first["local_key"])["action"],
            "conflict",
        )
        with self.assertRaisesRegex(ValueError, "kolize"):
            gramps.push(self.client, conflicted, state["revision"], state_hash)

        plan["database"]["name"] = "Tampered"
        with self.assertRaisesRegex(ValueError, "změněn"):
            gramps.validate_plan(plan)

    def test_conflicts_dates_and_transport_fail_closed(self):
        self.assertIsNone(gramps._date_value("1900-02-30"))
        self.assertEqual(gramps._date_value("1900-02")["dateval"], [0, 2, 1900, False])
        patch_data = model_patch()
        competing = next(item for item in patch_data["claims"] if item["id"] == "child_birth_guess")
        competing["status"] = "supported"
        competing["rationale"] = "Synthetic competing source."
        patch_data["conflicts"] = [{
            "id": "birth_conflict",
            "claim_ids": ["child_birth", "child_birth_guess"],
            "status": "open",
            "resolution": {"preferred_claim_ids": [], "rationale": ""},
            "notes": "",
            "extensions": {},
        }]
        other = Path(self.temp.name) / "conflict"
        research.initialize(other)
        state = research.apply_model(other, 0, patch_data, "Resolve conflict.")
        built = gramps.build_objects(state)
        self.assertNotIn("child_birth", built["eligible_claim_ids"])
        self.assertNotIn("child_birth_guess", built["eligible_claim_ids"])
        self.assertEqual(
            [item for item in built["objects"] if item["object_class"] == "Event"], []
        )
        with self.assertRaisesRegex(ValueError, "HTTP je zakázané"):
            gramps.Client("http://127.0.0.1:5000")
        self.assertEqual(
            gramps.Client("http://127.0.0.1:5000", allow_http=True).base_url,
            "http://127.0.0.1:5000/api",
        )

    def test_authentication_uses_environment_without_exposing_password(self):
        class LoginClient:
            token = None

            def __init__(self):
                self.login_values = None

            def login(self, username, password):
                self.login_values = (username, password)

        client = LoginClient()
        with patch.dict(os.environ, {"TEST_GRAMPS_PASSWORD": "secret"}, clear=False):
            method = gramps.authenticate(
                client,
                username="editor",
                password_env="TEST_GRAMPS_PASSWORD",
                token_env="TEST_GRAMPS_TOKEN",
            )
        self.assertEqual(method, "password")
        self.assertEqual(client.login_values, ("editor", "secret"))

    def test_http_client_serializes_login_and_bearer_request(self):
        class Response:
            status = 200

            def __init__(self, value):
                self.body = json.dumps(value).encode("utf-8")

            def read(self, limit):
                return self.body[:limit]

        class Opener:
            def __init__(self):
                self.requests = []
                self.responses = [
                    Response({"access_token": "access", "refresh_token": "refresh"}),
                    Response(self_metadata),
                    Response({"handle": "person-handle", "private": True}),
                ]

            def open(self, request, timeout):
                self.requests.append(request)
                return self.responses.pop(0)

        self_metadata = self.client.metadata()
        client = gramps.Client("https://gramps.example")
        opener = Opener()
        client.opener = opener
        client.login("editor", "secret")
        self.assertEqual(json.loads(opener.requests[0].data), {"username": "editor", "password": "secret"})
        self.assertTrue(gramps.probe(client)["compatible"])
        self.assertEqual(opener.requests[1].get_header("Authorization"), "Bearer access")
        self.assertEqual(client.get_optional("Person", "person-handle")["handle"], "person-handle")
        self.assertTrue(opener.requests[0].full_url.endswith("/token/"))
        self.assertTrue(opener.requests[1].full_url.endswith("/metadata/"))
        self.assertTrue(opener.requests[2].full_url.endswith("/people/person-handle"))


if __name__ == "__main__":
    unittest.main()
