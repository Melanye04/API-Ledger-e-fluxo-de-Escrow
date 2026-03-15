import os
import uuid
import sqlite3
import secrets
from fastapi import FastAPI, Header, HTTPException # type: ignore
from fastapi.middleware.cors import CORSMiddleware  # type: ignore
from dotenv import load_dotenv # type: ignore

load_dotenv()

app = FastAPI()

@app.post("/Reter pagamento")
def hold_payment_legacy(client_id: str, amount: float, api_key: str = Header(None)):
    verify_key(api_key)
    tx_id = str(uuid.uuid4())
    
    conn = sqlite3.connect('ledger.db')
    try:
        with conn: # Inicia transação atômica
            # 1. Débito no Cliente
            conn.execute("INSERT INTO ledger_entries (account_id, amount, description, tx_group_id) VALUES (?, ?, ?, ?)",
                         (client_id, -amount, "HOLD: Pagamento Pendente", tx_id))
            
            # 2. Crédito no Escrow
            conn.execute("INSERT INTO ledger_entries (account_id, amount, description, tx_group_id) VALUES (?, ?, ?, ?)",
                         ('escrow', amount, "ESCROW: Valor Retido", tx_id))
        return {"status": "Sucesso", "tx_id": tx_id, "message": "Fluxo de aprovação iniciado"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/Liberar pagamento")
def release_payment_legacy(provider_id: str, amount: float, tx_id: str, api_key: str = Header(None)):
    verify_key(api_key)
    
    conn = sqlite3.connect('ledger.db')
    try:
        with conn: # Garante que a liberação seja atômica
            # 1. Retira da conta de retenção
            conn.execute("INSERT INTO ledger_entries (account_id, amount, description, tx_group_id) VALUES (?, ?, ?, ?)",
                         ('escrow', -amount, "RELEASE: Saída de Custódia", tx_id))
            
            # 2. Envia para o prestador
            conn.execute("INSERT INTO ledger_entries (account_id, amount, description, tx_group_id) VALUES (?, ?, ?, ?)",
                         (provider_id, amount, "RELEASE: Pagamento Liberado", tx_id))
        return {"status": "Sucesso", "message": "Valor liberado ao prestador"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# Devolve o dinheiro pro cliente
@app.post("/Estorno") # type: ignore
def refund_payment(client_id: str, amount: float, tx_id: str, api_key: str = Header(None)):
    verify_key(api_key)
    
    conn = sqlite3.connect('ledger.db')
    cursor = conn.cursor()
  
    cursor.execute("SELECT SUM(amount) FROM ledger_entries WHERE account_id = 'escrow' AND tx_group_id = ?", (tx_id,))
    escrow_balance = cursor.fetchone()[0] or 0
    
    if escrow_balance < amount:
        conn.close()
        raise HTTPException(status_code=400, detail="Não há saldo suficiente para este estorno ou já foi liberado.")

    
    cursor.execute("INSERT INTO ledger_entries (account_id, amount, description, tx_group_id) VALUES (?, ?, ?, ?)",
                   ('escrow', -amount, "Estorno realizado para o cliente", tx_id))
    
    cursor.execute("INSERT INTO ledger_entries (account_id, amount, description, tx_group_id) VALUES (?, ?, ?, ?)",
                   (client_id, amount, "Reembolso recebido", tx_id))
    
    conn.commit()
    conn.close()
    
    return {"status": "Estorno concluído com sucesso", "valor_devolvido": amount}


@app.get("/Obter saldo") 
def get_history(account_id: str, api_key: str = Header(None)):
    verify_key(api_key) 
    
    conn = sqlite3.connect('ledger.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT amount, description, tx_group_id 
        FROM ledger_entries 
        WHERE account_id = ? 
        ORDER BY id DESC
    """, (account_id,))
    
    rows = cursor.fetchall()
    conn.close()

    history = [
        {"valor": r[0], "descricao": r[1], "id_transacao": r[2]} 
        for r in rows
    ]
    
    return {
        "conta": account_id,
        "total_operacoes": len(history),
        "lancamentos": history
    }


load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite que o Swagger (ou seu front-end) acesse a API
    allow_credentials=True,
    allow_methods=["*"],  # Permite POST, GET, etc.
    allow_headers=["*"],  # Permite enviar a API-KEY no cabeçalho
)

MASTER_API_KEY = os.getenv("MASTER_API_KEY")

def get_db():
    conn = sqlite3.connect('ledger.db')
    return conn

def verify_key(api_key: str):
    if not api_key or not MASTER_API_KEY or not secrets.compare_digest(str(api_key), str(MASTER_API_KEY)):
        raise HTTPException(status_code=401, detail="Chave API Inválida")

@app.post("/pay/hold")
def hold_payment(client_id: str, amount: float, api_key: str = Header("sk_ledger_123_abc")):
    verify_key(api_key)
    tx_id = str(uuid.uuid4()) 
    
    conn = get_db()
    cursor = conn.cursor()
    
    
    cursor.execute("INSERT INTO ledger_entries (account_id, amount, description, tx_group_id) VALUES (?, ?, ?, ?)",
                   (client_id, -amount, "Pagamento Retido (Hold)", tx_id))
    
    
    cursor.execute("INSERT INTO ledger_entries (account_id, amount, description, tx_group_id) VALUES (?, ?, ?, ?)",
                   ('escrow', amount, "Saldo em Custódia", tx_id))
    
    conn.commit()
    return {"status": "Valor retido com sucesso", "tx_id": tx_id}


@app.post("/pay/release")
def release_payment(provider_id: str, amount: float, tx_id: str, api_key: str = Header("sk_ledger_123_abc")):
    verify_key(api_key)
    
    conn = get_db()
    cursor = conn.cursor()
    
    
    cursor.execute("INSERT INTO ledger_entries (account_id, amount, description, tx_group_id) VALUES (?, ?, ?, ?)",
                   ('escrow', -amount, "Liberação de Custódia", tx_id))
    
    
    cursor.execute("INSERT INTO ledger_entries (account_id, amount, description, tx_group_id) VALUES (?, ?, ?, ?)",
                   (provider_id, amount, "Pagamento Recebido", tx_id))
    
    conn.commit()
    return {"status": "Valor liberado ao prestador"}


@app.get("/balance/{account_id}")
def get_balance(account_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(amount) FROM ledger_entries WHERE account_id = ?", (account_id,))
    balance = cursor.fetchone()[0] or 0.0
    return {"account_id": account_id, "balance": balance}