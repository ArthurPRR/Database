import json
import os
import glob

try:
    from .btree import BTree
except ImportError:
    from btree import BTree


class Database:

    def __init__(self, filename):
        self.filename = filename
        self.indexes = {}

        os.makedirs(os.path.dirname(filename) or ".", exist_ok=True)

        if not os.path.exists(filename):
            open(filename, "w").close()

        self._load_indexes()

    def _index_key(self, value):
        return json.dumps(value, sort_keys=True, ensure_ascii=False)

    def _index_filename(self, field):
        return f"{self.filename}.{field}.index.json"

    def _load_indexes(self):
        pattern = f"{self.filename}.*.index.json"

        for path in glob.glob(pattern):
            prefix = f"{self.filename}."
            field = path[len(prefix):-len(".index.json")]

            with open(path, "r", encoding="utf-8") as file:
                data = json.load(file)

            if isinstance(data, dict) and data.get("type") == "btree":
                self.indexes[field] = BTree.from_dict(data)
            else:
                index = BTree()
                if isinstance(data, dict):
                    for key, offsets in data.items():
                        for offset in offsets:
                            index.insert(key, offset)
                self.indexes[field] = index
                self._save_index(field)

    def _save_index(self, field):
        path = self._index_filename(field)

        with open(path, "w", encoding="utf-8") as file:
            json.dump(self.indexes[field].to_dict(), file)

    def _rebuild_index(self, field):
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

    def create_index(self, field):
        self._rebuild_index(field)
        print(f"Index created on field: {field}")

    def create(self, document):
        if "id" not in document:
            raise ValueError("Document must have an id")

        if self.read(document["id"]) is not None:
            raise ValueError("Document already exists")

        data = json.dumps(document, ensure_ascii=False) + "\n"

        with open(self.filename, "ab") as file:
            offset = file.tell()
            file.write(data.encode("utf-8"))

        for field, index in self.indexes.items():
            if field in document:
                key = self._index_key(document[field])
                index.insert(key, offset)
                self._save_index(field)

    def read(self, value, field="id"):
        if field in self.indexes:
            key = self._index_key(value)
            offsets = self.indexes[field].search(key)

            if not offsets:
                return None

            with open(self.filename, "rb") as file:
                for offset in offsets:
                    file.seek(offset)
                    document = json.loads(file.readline().decode("utf-8"))

                    if document.get(field) == value:
                        return document

            return None

        with open(self.filename, "r", encoding="utf-8") as file:
            for line in file:
                document = json.loads(line)

                if document.get(field) == value:
                    return document

        return None

    def update(self, document_id, updates):
        documents = []
        found = False

        with open(self.filename, "r", encoding="utf-8") as file:
            for line in file:
                document = json.loads(line)

                if document["id"] == document_id:
                    document.update(updates)
                    found = True

                documents.append(document)

        if not found:
            return False

        with open(self.filename, "w", encoding="utf-8") as file:
            for document in documents:
                file.write(
                    json.dumps(document, ensure_ascii=False) + "\n"
                )

        for field in list(self.indexes):
            self._rebuild_index(field)

        return True

    def delete(self, document_id):
        documents = []
        found = False

        with open(self.filename, "r", encoding="utf-8") as file:
            for line in file:
                document = json.loads(line)

                if document["id"] == document_id:
                    found = True
                else:
                    documents.append(document)

        if not found:
            return False

        with open(self.filename, "w", encoding="utf-8") as file:
            for document in documents:
                file.write(
                    json.dumps(document, ensure_ascii=False) + "\n"
                )

        for field in list(self.indexes):
            self._rebuild_index(field)

        return True
