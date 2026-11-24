
import json
import os
import glob


class Database:

    def __init__(self, filename):
        self.filename = filename
        self.indexes = {}

        os.makedirs(os.path.dirname(filename) or ".", exist_ok=True)

        if not os.path.exists(filename):
            open(filename, "w").close()

        # Charger les index existants
        self._load_indexes()

    # Convertir une valeur en clé JSON non ambiguë
    def _index_key(self, value):
        return json.dumps(value, sort_keys=True, ensure_ascii=False)

    # Chemin du fichier d'index
    def _index_filename(self, field):
        return f"{self.filename}.{field}.index.json"

    # Charger les index depuis le disque
    def _load_indexes(self):
        pattern = f"{self.filename}.*.index.json"

        for path in glob.glob(pattern):
            prefix = f"{self.filename}."
            field = path[len(prefix):-len(".index.json")]

            with open(path, "r", encoding="utf-8") as file:
                self.indexes[field] = json.load(file)

    # Sauvegarder un index
    def _save_index(self, field):
        path = self._index_filename(field)

        with open(path, "w", encoding="utf-8") as file:
            json.dump(self.indexes[field], file, indent=4)

    # Reconstruire un index
    def _rebuild_index(self, field):
        index = {}

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

                index.setdefault(key, []).append(offset)

        self.indexes[field] = index
        self._save_index(field)

    # Créer un index sur un champ
    def create_index(self, field):
        self._rebuild_index(field)
        print(f"Index created on field: {field}")

    # CREATE
    def create(self, document):
        if "id" not in document:
            raise ValueError("Document must have an id")

        if self.read(document["id"]) is not None:
            raise ValueError("Document already exists")

        data = (
            json.dumps(document, ensure_ascii=False) + "\n"
        ).encode("utf-8")

        with open(self.filename, "ab") as file:
            offset = file.tell()
            file.write(data)

        for field, index in self.indexes.items():
            if field in document:
                key = self._index_key(document[field])
                index.setdefault(key, []).append(offset)
                self._save_index(field)

    # READ
    def read(self, value, field="id"):

        if field in self.indexes:
            key = self._index_key(value)
            offsets = self.indexes[field].get(key, [])

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

    # UPDATE
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

    # DELETE
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
