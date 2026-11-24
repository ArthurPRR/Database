
import os
import csv
import time
from database import Database

filename = "data/benchmark.jsonl"
results_file = "results/benchmark.csv"

sizes = [100, 1000, 10000]

# Créer le dossier des résultats
os.makedirs("results", exist_ok=True)

# Initialiser le CSV
with open(results_file, "w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file, delimiter=";")
    writer.writerow([
        "documents",
        "insertion_seconds",
        "search_ms",
        "document_found"
    ])

for size in sizes:

    # Repartir de zéro pour chaque benchmark
    if os.path.exists(filename):
        os.remove(filename)

    db = Database(filename)

    # INSERTION
    start = time.perf_counter()

    for i in range(size):
        db.create({
            "id": i,
            "name": f"User {i}",
            "age": 20 + i % 50
        })

    insert_time = time.perf_counter() - start

    # RECHERCHE
    start = time.perf_counter()
    result = db.read(size - 1)
    search_time = time.perf_counter() - start

    # Résultats
    found = result is not None

    print(f"\nDocuments : {size}")
    print(f"Insertion : {insert_time:.4f} secondes")
    print(f"Recherche : {search_time * 1000:.4f} ms")
    print(f"Document trouvé : {found}")

    # Écriture dans le CSV
    with open(results_file, "a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file, delimiter=";")
        writer.writerow([
            size,
            round(insert_time, 6),
            round(search_time * 1000, 6),
            found
        ])

print(f"\nRésultats enregistrés dans : {results_file}")
