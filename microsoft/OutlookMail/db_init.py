import sqlite3
import os

def init_db():
    # Get the directory of the current script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Define the database file path
    db_path = os.path.join(current_dir, 'emails.db')
    
    # Read the schema file
    schema_path = os.path.join(current_dir, 'schema.sql')
    with open(schema_path, 'r') as f:
        schema = f.read()
    
    # Connect to SQLite database (creates it if it doesn't exist)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Execute the schema
        cursor.executescript(schema)
        conn.commit()
        print("Database initialized successfully!")
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    init_db() 