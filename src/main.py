
from database import Database


def main():
    db = Database("data/users.jsonl")

    # CREATE
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

    # READ
    user = db.read(2)
    print("Found:", user)

    # UPDATE
    db.update(2, {
        "age": 31
    })

    print("After update:", db.read(2))

    # DELETE
    db.delete(1)

    print("After delete:", db.read(1))


if __name__ == "__main__":
    main()
