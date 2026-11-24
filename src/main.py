
from database import Database

db = Database("data/users.jsonl")

# Création des documents
db.create({
    "id": 1,
    "name": "Alice",
    "age": 25
})

db.create({
    "id": 2,
    "name": "Bob",
    "age": 30
})

db.create({
    "id": 3,
    "name": "Charlie",
    "age": 22
})

# Création d'un index sur l'ID
db.create_index("id")

# Création d'un deuxième index sur le nom
db.create_index("name")

# Lecture avec l'index ID
print(db.read(2))

# Lecture avec l'index name
print(db.read("Alice", field="name"))

# Modification
db.update(2, {"age": 31})

# Suppression
db.delete(1)
