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

    def test_partitioned_reads_use_partition_specific_indexes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "users.jsonl")
            db = Database(path)
            db.enable_partitioning("group", partition_count=2)

            values_by_partition = {}
            for value in range(100):
                partition_id = db._get_partition_id(value)
                values_by_partition.setdefault(partition_id, value)
                if len(values_by_partition) == 2:
                    break

            documents = {}
            for partition_id, group in values_by_partition.items():
                document = {
                    "id": partition_id + 1,
                    "group": group,
                    "name": f"user-{partition_id}",
                }
                documents[partition_id] = document
                db.create(document)

            db.create_index("id")
            db.create_index("name")

            self.assertEqual(len(db.indexes["id"]), 2)
            for partition_indexes in db.indexes.values():
                self.assertEqual(set(partition_indexes), {0, 1})

            for document in documents.values():
                self.assertEqual(db.read(document["id"]), document)
                self.assertEqual(
                    db.read(document["name"], field="name"),
                    document,
                )

            target = documents[1]
            self.assertTrue(db.update(target["id"], {"name": "updated"}))
            self.assertIsNone(db.read(target["name"], field="name"))
            self.assertEqual(
                db.read("updated", field="name")["id"],
                target["id"],
            )
            self.assertTrue(db.delete(target["id"]))
            self.assertIsNone(db.read(target["id"]))

            reloaded = Database(path)
            self.assertEqual(reloaded.partition_field, "group")
            self.assertEqual(reloaded.partition_count, 2)
            self.assertEqual(
                reloaded.read(documents[0]["name"], field="name"),
                documents[0],
            )
            after_reload = {
                "id": 3,
                "group": documents[0]["group"],
                "name": "after-reload",
            }
            reloaded.create(after_reload)
            self.assertEqual(reloaded.read(3), after_reload)

            reloaded_again = Database(path)
            self.assertEqual(reloaded_again.read(3), after_reload)

    def test_enable_partitioning_migrates_existing_data_and_indexes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "users.jsonl")
            db = Database(path)
            documents = [
                {"id": 1, "group": "north", "name": "Alice"},
                {"id": 2, "group": "south", "name": "Bob"},
                {"id": 3, "group": "east", "name": "Charlie"},
            ]
            for document in documents:
                db.create(document)
            db.create_index("id")
            db.create_index("name")

            db.enable_partitioning("group", partition_count=2)

            with open(path, "r", encoding="utf-8") as file:
                self.assertEqual(file.read(), "")

            for document in documents:
                self.assertEqual(db.read(document["id"]), document)
                self.assertEqual(
                    db.read(document["name"], field="name"),
                    document,
                )

            db.enable_partitioning("group", partition_count=1)
            migrated_documents = []
            for partition_path in db.partitions.values():
                with open(partition_path, "r", encoding="utf-8") as file:
                    migrated_documents.extend(
                        json.loads(line) for line in file
                    )

            self.assertCountEqual(migrated_documents, documents)
            self.assertFalse(os.path.exists(f"{path}.partition_1.jsonl"))
            for document in documents:
                self.assertEqual(db.read(document["id"]), document)

    def test_partition_migration_keeps_source_when_validation_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "users.jsonl")
            with open(path, "w", encoding="utf-8") as file:
                file.write(json.dumps({"id": 1, "name": "Alice"}) + "\n")

            db = Database(path)
            with self.assertRaisesRegex(ValueError, "partition field"):
                db.enable_partitioning("group", partition_count=2)

            with open(path, "r", encoding="utf-8") as file:
                self.assertEqual(
                    file.read(),
                    json.dumps({"id": 1, "name": "Alice"}) + "\n",
                )
            self.assertIsNone(db.partition_field)


if __name__ == "__main__":
    unittest.main()
