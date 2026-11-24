import json
import os
import glob
import hashlib
import tempfile

try:
    from .btree import BTree
except ImportError:
    from btree import BTree


class Database:

    def __init__(self, filename):
        self.filename = filename
        self.indexes = {}

        self.partition_field = None
        self.partitions = {}

        os.makedirs(os.path.dirname(filename) or ".", exist_ok=True)

        if not os.path.exists(filename):
            open(filename, "w").close()

        self._load_partitioning_metadata()
        self._load_indexes()


    # CREATE
    def create(self, document):
        if "id" not in document:
            raise ValueError("Document must have an id")

        if self.read(document["id"]) is not None:
            raise ValueError("Document already exists")

        data = json.dumps(document, ensure_ascii=False) + "\n"

        partition_file = self._get_partition_file(document)
        if self.partition_field is not None:
            partition_id = self._get_partition_id(
                document[self.partition_field]
            )
        else:
            partition_id = None

        with open(partition_file, "ab") as file:
            offset = file.tell()
            file.write(data.encode("utf-8"))

        for field in self.indexes:
            if field not in document:
                continue

            index = self._get_index(field, partition_id)

            if index is not None:
                key = self._index_key(document[field])
                index.insert(key, offset)

                if self.partition_field is None:
                    self._save_index(field)
                else:
                    self._save_partition_index(field, partition_id)

    # READ
    def read(self, value, field="id"):

        if self.partition_field == field:

            partition_id = self._get_partition_id(value)

            files = [
                (partition_id, self.partitions[partition_id])
            ]

        elif self.partition_field is not None:

            files = list(self.partitions.items())

        else:

            files = [(None, self.filename)]

        key = self._index_key(value)

        if field in self.indexes:

            for partition_id, path in files:

                if self.partition_field is not None:
                    index = self.indexes[field].get(partition_id)
                else:
                    index = self.indexes[field]

                if index is None:
                    continue

                offsets = index.search(key)

                if not offsets:
                    continue

                with open(path, "rb") as file:

                    for offset in offsets:

                        file.seek(offset)

                        document = json.loads(
                            file.readline().decode("utf-8")
                        )

                        if document.get(field) == value:
                            return document

            return None

        # Recherche sans index
        for _, path in files:

            with open(path, "r", encoding="utf-8") as file:

                for line in file:

                    document = json.loads(line)

                    if document.get(field) == value:
                        return document

        return None

    # UPDATE
    def update(self, document_id, updates):
        if "id" in updates and updates["id"] != document_id:
            raise ValueError("Document ID cannot be modified")

        existing = self.read(document_id)
        if existing is None:
            return False

        updated = dict(existing)
        updated.update(updates)
        old_partition_file = self._get_partition_file(existing)
        new_partition_file = self._get_partition_file(updated)

        documents = []
        with open(old_partition_file, "r", encoding="utf-8") as file:
            for line in file:
                document = json.loads(line)

                if document["id"] == document_id:
                    if old_partition_file == new_partition_file:
                        documents.append(updated)
                else:
                    documents.append(document)

        with open(old_partition_file, "w", encoding="utf-8") as file:
            for document in documents:
                file.write(
                    json.dumps(document, ensure_ascii=False) + "\n"
                )

        if old_partition_file != new_partition_file:
            with open(new_partition_file, "a", encoding="utf-8") as file:
                file.write(json.dumps(updated, ensure_ascii=False) + "\n")

        for field in list(self.indexes):
            self._rebuild_index(field)

        return True

    # DELETE
    def delete(self, document_id):
        existing = self.read(document_id)
        if existing is None:
            return False

        documents = []
        partition_file = self._get_partition_file(existing)

        with open(partition_file, "r", encoding="utf-8") as file:
            for line in file:
                document = json.loads(line)

                if document["id"] != document_id:
                    documents.append(document)

        with open(partition_file, "w", encoding="utf-8") as file:
            for document in documents:
                file.write(
                    json.dumps(document, ensure_ascii=False) + "\n"
                )

        for field in list(self.indexes):
            self._rebuild_index(field)

        return True


# -----------------------------------------------
#  INDEXING
# -----------------------------------------------

    def _index_key(self, value):
        return json.dumps(value, sort_keys=True, ensure_ascii=False)

    def _index_filename(self, field):
        return f"{self.filename}.{field}.index.json"

    def _metadata_filename(self):
        return f"{self.filename}.metadata.json"

    def _load_partitioning_metadata(self):
        path = self._metadata_filename()
        if not os.path.exists(path):
            return

        with open(path, "r", encoding="utf-8") as file:
            metadata = json.load(file)

        if not isinstance(metadata, dict) or metadata.get("version") != 1:
            raise ValueError(f"Unsupported database metadata in {path}")

        partitioning = metadata.get("partitioning")
        if not isinstance(partitioning, dict):
            raise ValueError(f"Invalid partitioning metadata in {path}")

        field = partitioning.get("field")
        partition_count = partitioning.get("partition_count")
        strategy = partitioning.get("strategy")
        if (
            not isinstance(field, str)
            or not field
            or not isinstance(partition_count, int)
            or isinstance(partition_count, bool)
            or partition_count < 1
            or strategy != "hash"
        ):
            raise ValueError(f"Invalid partitioning metadata in {path}")

        self.partition_field = field
        self.partition_count = partition_count
        self.partition_strategy = strategy
        self.partitions = {
            partition_id: (
                f"{self.filename}.partition_{partition_id}.jsonl"
            )
            for partition_id in range(partition_count)
        }

        for partition_path in self.partitions.values():
            if not os.path.isfile(partition_path):
                raise FileNotFoundError(
                    f"Partition data file is missing: {partition_path}"
                )

    def _save_partitioning_metadata(self):
        path = self._metadata_filename()
        metadata = {
            "version": 1,
            "partitioning": {
                "field": self.partition_field,
                "partition_count": self.partition_count,
                "strategy": self.partition_strategy,
            },
        }

        temporary = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=os.path.basename(path) + ".",
            suffix=".tmp",
            dir=os.path.dirname(path) or ".",
            delete=False,
        )
        try:
            with temporary:
                json.dump(metadata, temporary)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary.name, path)
        finally:
            if os.path.exists(temporary.name):
                os.remove(temporary.name)

    def _partition_index_filename(self, field, partition_id):
        return (
            f"{self.filename}.{field}.partition_{partition_id}.index.json"
        )

    def _load_indexes(self):
        pattern = f"{self.filename}.*.index.json"
        indexes = {}
        partition_indexes = {}

        for path in glob.glob(pattern):
            prefix = f"{self.filename}."
            name = path[len(prefix):-len(".index.json")]
            field = name
            partition_id = None

            if ".partition_" in name:
                field, partition = name.rsplit(".partition_", 1)
                try:
                    partition_id = int(partition)
                except ValueError:
                    field = name

            with open(path, "r", encoding="utf-8") as file:
                data = json.load(file)

            is_legacy_index = not (
                isinstance(data, dict) and data.get("type") == "btree"
            )
            if not is_legacy_index:
                index = BTree.from_dict(data)
            else:
                index = BTree()
                if isinstance(data, dict):
                    for key, offsets in data.items():
                        for offset in offsets:
                            index.insert(key, offset)

            if partition_id is None:
                indexes[field] = index
            else:
                partition_indexes.setdefault(field, {})[partition_id] = index

            if is_legacy_index:
                with open(path, "w", encoding="utf-8") as file:
                    json.dump(index.to_dict(), file)

        self.indexes.update(indexes)
        self.indexes.update(partition_indexes)

    def _save_index(self, field):
        path = self._index_filename(field)

        with open(path, "w", encoding="utf-8") as file:
            json.dump(self.indexes[field].to_dict(), file)

    def _save_partition_index(self, field, partition_id):
        path = self._partition_index_filename(field, partition_id)

        with open(path, "w", encoding="utf-8") as file:
            json.dump(
                self.indexes[field][partition_id].to_dict(),
                file,
            )

    def _rebuild_index(self, field):
        if self.partition_field is not None:
            indexes = {}

            for partition_id, path in self.partitions.items():
                index = BTree()

                with open(path, "rb") as file:
                    while True:
                        offset = file.tell()
                        line = file.readline()

                        if not line:
                            break

                        document = json.loads(line.decode("utf-8"))

                        if field in document:
                            key = self._index_key(document[field])
                            index.insert(key, offset)

                indexes[partition_id] = index

            self.indexes[field] = indexes

            for partition_id in self.partitions:
                self._save_partition_index(field, partition_id)
            return

        index = BTree()

        with open(self.filename, "rb") as file:
            while True:
                offset = file.tell()
                line = file.readline()

                if not line:
                    break

                document = json.loads(line.decode("utf-8"))

                if field not in document:
                    continue

                key = self._index_key(document[field])
                index.insert(key, offset)

        self.indexes[field] = index
        self._save_index(field)

    def _get_index(self, field, partition_id=None):
        if self.partition_field is None:
            return self.indexes.get(field)

        return self.indexes.get(field, {}).get(partition_id)

    def create_index(self, field):
        self._rebuild_index(field)
        print(f"Index created on field: {field}")


# -----------------------------------------------
#  PARTITIONING
# -----------------------------------------------

    def enable_partitioning(self, field, partition_count=4):
        if (
            not isinstance(partition_count, int)
            or isinstance(partition_count, bool)
            or partition_count < 1
        ):
            raise ValueError("Partition count must be a positive integer")

        partition_files = {
            partition_id: f"{self.filename}.partition_{partition_id}.jsonl"
            for partition_id in range(partition_count)
        }
        source_files = [self.filename]
        source_files.extend(
            sorted(glob.glob(f"{self.filename}.partition_*.jsonl"))
        )

        staged_paths = {}
        staged_files = {}
        seen_ids = {}

        try:
            for partition_id, path in partition_files.items():
                staged = tempfile.NamedTemporaryFile(
                    mode="wb",
                    prefix=os.path.basename(path) + ".",
                    suffix=".tmp",
                    dir=os.path.dirname(path) or ".",
                    delete=False,
                )
                staged_paths[partition_id] = staged.name
                staged_files[partition_id] = staged

            for source_path in source_files:
                with open(source_path, "rb") as source:
                    for line in source:
                        document = json.loads(line.decode("utf-8"))
                        if not isinstance(document, dict):
                            raise ValueError(
                                "Each stored document must be a JSON object"
                            )
                        if "id" not in document:
                            raise ValueError(
                                "Every document must have an id"
                            )

                        id_key = self._index_key(document["id"])
                        if id_key in seen_ids:
                            if seen_ids[id_key] != document:
                                raise ValueError(
                                    f"Conflicting documents share id "
                                    f"{document['id']!r}"
                                )
                            continue
                        seen_ids[id_key] = document

                        value = document.get(field)
                        if value is None:
                            raise ValueError(
                                f"Document {document['id']!r} is missing "
                                f"partition field {field!r}"
                            )

                        partition_id = self._get_partition_id(
                            value,
                            partition_count=partition_count,
                        )
                        staged_files[partition_id].write(line)
                        if not line.endswith(b"\n"):
                            staged_files[partition_id].write(b"\n")

            for staged in staged_files.values():
                staged.close()

            for partition_id, path in partition_files.items():
                os.replace(staged_paths[partition_id], path)

            self.partition_field = field
            self.partition_count = partition_count
            self.partition_strategy = "hash"
            self.partitions = partition_files

            for indexed_field in list(self.indexes):
                self._rebuild_index(indexed_field)

            self._save_partitioning_metadata()

            with open(self.filename, "wb"):
                pass

            for path in source_files[1:]:
                if (
                    path not in partition_files.values()
                    and os.path.exists(path)
                ):
                    os.remove(path)
        finally:
            for staged in staged_files.values():
                if not staged.closed:
                    staged.close()
            for path in staged_paths.values():
                if os.path.exists(path):
                    os.remove(path)


    def _get_partition_id(self, value, partition_count=None):

        key = self._index_key(value)

        hash_value = int.from_bytes(
            hashlib.sha256(key.encode("utf-8")).digest()[:8],
            byteorder="big",
        )

        return hash_value % (partition_count or self.partition_count)


    def _get_partition_file(self, document):

        if self.partition_field is None:
            return self.filename

        value = document.get(self.partition_field)

        if value is None:
            raise ValueError("Missing partition key")

        partition_id = self._get_partition_id(value)

        return self.partitions[partition_id]