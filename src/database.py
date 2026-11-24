
import json
import os
import time


class Database:

    def __init__(self, filename):
        self.filename = filename

        # Créer le fichier s'il n'existe pas
        os.makedirs(os.path.dirname(filename) or ".", exist_ok=True)

        if not os.path.exists(filename):
            open(filename, "w").close()

    # CREATE
    def create(self, document):
        if "id" not in document:
            raise ValueError("Document must have an id")

        # Vérifier que l'ID n'existe pas déjà
        if self.read(document["id"]) is not None:
            raise ValueError("Document already exists")

        with open(self.filename, "a", encoding="utf-8") as file:
            file.write(json.dumps(document) + "\n")

        print(f"Document {document['id']} created")

    # READ
    def read(self, document_id):
        start = time.perf_counter()

        with open(self.filename, "r", encoding="utf-8") as file:
            for line in file:
                document = json.loads(line)

                if document["id"] == document_id:
                    elapsed = time.perf_counter() - start

                    print(f"Read time: {elapsed * 1000:.4f} ms")
                    return document

        elapsed = time.perf_counter() - start
        print(f"Read time: {elapsed * 1000:.4f} ms")

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
                file.write(json.dumps(document) + "\n")

        print(f"Document {document_id} updated")
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
                file.write(json.dumps(document) + "\n")

        print(f"Document {document_id} deleted")
        return True
