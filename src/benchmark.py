
import os
import csv
import time
import glob
import statistics
import json

from database import Database


filename = "data/benchmark.jsonl"
results_file = "results/benchmark.csv"

sizes = [100, 1000, 10000, 100000]
repetitions = 20

os.makedirs("data", exist_ok=True)
os.makedirs("results", exist_ok=True)

results = []

for size in sizes:

    # Nettoyer les anciens fichiers
    if os.path.exists(filename):
        os.remove(filename)

    for path in glob.glob(filename + ".*.index.json"):
        os.remove(path)

    db = Database(filename)

    # Générer les documents directement dans le fichier
    # pour ne pas mesurer le coût de vérification des IDs.
    with open(filename, "w", encoding="utf-8") as file:
        for i in range(size):
            document = {
                "id": i,
                "name": f"User {i}",
                "age": 20 + i % 50
            }
            file.write(json.dumps(document) + "\n")

    # RECHERCHE SANS INDEX
    search_times_without_index = []

    for _ in range(repetitions):
        start = time.perf_counter()
        result = db.read(size - 1)
        elapsed = time.perf_counter() - start

        search_times_without_index.append(elapsed * 1000)

    # CRÉATION DE L'INDEX
    start = time.perf_counter()
    db.create_index("id")
    index_time = time.perf_counter() - start

    # RECHERCHE AVEC INDEX
    search_times_with_index = []

    for _ in range(repetitions):
        start = time.perf_counter()
        result = db.read(size - 1)
        elapsed = time.perf_counter() - start

        search_times_with_index.append(elapsed * 1000)

    without_index = statistics.mean(search_times_without_index)
    with_index = statistics.mean(search_times_with_index)

    speedup = without_index / with_index if with_index > 0 else 0

    print(f"\nDocuments : {size}")
    print(f"Sans index : {without_index:.6f} ms")
    print(f"Création index : {index_time:.4f} secondes")
    print(f"Avec index : {with_index:.6f} ms")
    print(f"Accélération : x{speedup:.2f}")

    results.append([
        size,
        round(without_index, 6),
        round(index_time, 6),
        round(with_index, 6),
        round(speedup, 2)
    ])

# Export CSV
with open(results_file, "w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file, delimiter=";")

    writer.writerow([
        "documents",
        "search_without_index_ms",
        "index_creation_seconds",
        "search_with_index_ms",
        "speedup"
    ])

    writer.writerows(results)

print(f"\nRésultats enregistrés dans {results_file}")
