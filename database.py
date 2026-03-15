import sqlite3

def init_db():
    conn = sqlite3.connect('ledger.db')
    cursor = conn.cursor()

    cursor.execute('''
                 CREATE TABLE IF NOT EXISTS accounts (
            id TEXT PRIMARY KEY,
            name TEXT,
            type TEXT -- 'CLIENT', 'PROVIDER', 'INTERNAL'
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ledger_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id TEXT,
            amount REAL, -- Positivo para crédito, Negativo para débito
            description TEXT,
            tx_group_id TEXT, -- Para ligar o débito ao crédito
            FOREIGN KEY(account_id) REFERENCES accounts(id)
        )
    ''')
   
    cursor.execute("INSERT OR IGNORE INTO accounts VALUES ('cli_1', 'Cliente João', 'CLIENT')")
    cursor.execute("INSERT OR IGNORE INTO accounts VALUES ('prov_1', 'Prestador Melanye', 'PROVIDER')")
    cursor.execute("INSERT OR IGNORE INTO accounts VALUES ('escrow', 'Conta Retenção', 'INTERNAL')")
    
    conn.commit()
    conn.close()

init_db()