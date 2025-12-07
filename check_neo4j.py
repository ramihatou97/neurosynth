import sys

from neo4j import GraphDatabase


def main():
    uri = "bolt://localhost:7687"
    # Default Neo4j credentials, might need user input if changed
    auth = ("neo4j", "password")

    print(f"🔌 Testing connection to Neo4j at {uri}...")
    try:
        with GraphDatabase.driver(uri, auth=auth) as driver:
            driver.verify_connectivity()
            print("✅ Connection Successful!")
    except Exception as e:
        print(f"❌ Connection Failed: {e}")
        # Not a fatal error for *planning*, but critical for *execution*.
        # We can write the code even if the DB isn't up, but can't run it.


if __name__ == "__main__":
    main()
