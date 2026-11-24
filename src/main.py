
import glob
import os

from database import Database


filename = "data/users.jsonl"

# Nettoyage pour rendre l'exemple reproductible.
paths = (
    [filename, filename + ".metadata.json"]
    + glob.glob(filename + ".*.index.json")
    + glob.glob(filename + ".partition_*.jsonl")
)
for path in paths:
    if os.path.exists(path):
        os.remove(path)

db = Database(filename)
db.enable_partitioning(field="id", partition_count=2)

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
for field, partition_indexes in db.indexes.items():
    for partition_id, index in partition_indexes.items():
        print(
            f"Index '{field}' partition {partition_id} : "
            f"degré={index.degree}, "
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
print(
    "Partitionnement restauré :",
    reloaded_db.partition_field,
    reloaded_db.partition_count,
)
