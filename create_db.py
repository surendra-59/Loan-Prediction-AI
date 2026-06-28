import mysql.connector
from mysql.connector import errorcode

# MySQL connection details
host = "localhost"
user = "root"            # MySQL root or admin user
password = "suresh"     # MySQL password
database_name = "loan_prediction_db"

try:
    # Connect to MySQL server
    conn = mysql.connector.connect(
        host=host,
        user=user,
        password=password
    )
    cursor = conn.cursor()

    # Create database
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {database_name}")
    print(f"Database '{database_name}' created successfully!")

except mysql.connector.Error as err:
    if err.errno == errorcode.ER_DB_CREATE_EXISTS:
        print(f"Database '{database_name}' already exists!")
    else:
        print("Error:", err)

finally:
    cursor.close()
    conn.close()
