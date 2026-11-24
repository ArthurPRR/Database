import json
import os
import sys
import tempfile
import unittest

SRC_DIRECTORY = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "src")
)
sys.path.insert(0, SRC_DIRECTORY)

from btree import BTree
from database import Database


class BTreeTest(unittest.TestCase):

    def test_insert_search_and_duplicates(self):
        tree = BTree(degree=3)

        for key in [10, 20, 5, 6, 12, 30, 7, 17]:
            tree.insert(json.dumps(key), key * 100)

        tree.insert(json.dumps(10), 999)

        self.assertEqual(tree.search(json.dumps(10)), [1000, 999])
        self.assertEqual(tree.search(json.dumps(17)), [1700])
        self.assertEqual(tree.search(json.dumps(99)), [])

    def test_split_keeps_keys_searchable(self):
        tree = BTree(degree=2)

        for value in range(1000):
            tree.insert(json.dumps(value), value * 10)

        for value in range(1000):
            self.assertEqual(tree.search(json.dumps(value)), [value * 10])

    def test_tree_remains_balanced(self):
        tree = BTree(degree=3)

        for value in range(500):
            tree.insert(json.dumps(value), value)

        leaf_depths = set()

        def visit(node, depth):
            if node.leaf:
                leaf_depths.add(depth)
                return

            for child in node.children:
                visit(child, depth + 1)

        visit(tree.root, 0)
        self.assertLessEqual(max(leaf_depths) - min(leaf_depths), 1)

    def test_json_values_can_be_indexed(self):
        tree = BTree(degree=3)
        values = [
            None,
            True,
            12,
            "Alice",
            [1, 2],
            {"age": 25, "name": "Alice"},
        ]

        for offset, value in enumerate(values):
            tree.insert(json.dumps(value), offset)

        for offset, value in enumerate(values):
            self.assertEqual(
                tree.search(json.dumps(value)),
                [offset],
            )

    def test_serialization_round_trip(self):
        tree = BTree(degree=3)

        for value in range(100):
            tree.insert(json.dumps(value), value * 10)

        restored = BTree.from_dict(tree.to_dict())

        self.assertEqual(restored.search(json.dumps(42)), [420])
        self.assertEqual(restored.search(json.dumps(-1)), [])

    def test_database_index_integration(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "users.jsonl")
            db = Database(path)

            db.create({"id": 1, "name": "Alice"})
            db.create({"id": 2, "name": "Bob"})
            db.create({"id": 3, "name": "Alice"})
            db.create_index("id")
            db.create_index("name")

            self.assertEqual(db.read(2)["name"], "Bob")
            self.assertEqual(db.read("Alice", field="name")["id"], 1)

            db.update(2, {"name": "Robert"})
            self.assertIsNone(db.read("Bob", field="name"))
            self.assertEqual(db.read("Robert", field="name")["id"], 2)

            db.delete(1)
            self.assertIsNone(db.read(1))

            reloaded = Database(path)
            self.assertIn("id", reloaded.indexes)
            self.assertIn("name", reloaded.indexes)
            self.assertEqual(reloaded.read(3)["name"], "Alice")


if __name__ == "__main__":
    unittest.main()
