"""Script one-shot pour créer la DB MySQL."""
import MySQLdb
try:
    conn = MySQLdb.connect(host='127.0.0.1', port=3306, user='root', password='')
    cursor = conn.cursor()
    cursor.execute("CREATE DATABASE IF NOT EXISTS erp_btp CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    conn.commit()
    print("Base erp_btp créée / vérifiée OK")
    cursor.execute("SHOW DATABASES LIKE 'erp_btp'")
    result = cursor.fetchone()
    if result:
        print("Confirmé : erp_btp existe dans MySQL")
    conn.close()
except Exception as e:
    print(f"Erreur : {e}")
