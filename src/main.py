
import glob
import os

from database import Database


filename = "data/users.jsonl"

# Nettoyage pour rendre l'exemple reproductible.
for path in [filename] + glob.glob(filename + ".*.index.json"):
    if os.path.exists(path):
        os.remove(path)

db = Database(filename)

# Ajout de documents dans la table.
db.create({"id": 1, "name": "Alice", "age": 25})
db.create({"id": 2, "name": "Bob", "age": 30})
db.create({"id": 3, "name": "Charlie", "age": 22})
db.create({"id": 4, "name": "Alice", "age": 28})
db.create({"id": 5, "name": "Diana", "age": 35})

# Création des index B-Tree.
db.create_index("id")
db.create_index("name")

# Informations sur les index B-Tree.
for field, index in db.indexes.items():
    print(
        f"Index '{field}' : degré={index.degree}, "
        f"racine avec {len(index.root.keys)} clé(s)"
    )

# Recherche grâce aux index.
print("Recherche par ID :", db.read(2))
print("Recherche par nom :", db.read("Alice", field="name"))
print("Recherche inexistante :", db.read(99))

# Mise à jour : les index sont reconstruits.
db.update(2, {"name": "Robert", "age": 31})
print("Après modification - ancien nom :", db.read("Bob", field="name"))
print("Après modification - nouveau nom :", db.read("Robert", field="name"))
print("Après modification - nouveau contenu :", db.read(2))

# Suppression : les index sont reconstruits.
db.delete(1)
print("Après suppression :", db.read(1))

# Simulation d'un nouveau lancement : les index sont chargés depuis le disque.
reloaded_db = Database(filename)
print("Après rechargement :", reloaded_db.read("Charlie", field="name"))
print("Tous les index chargés :", list(reloaded_db.indexes))
