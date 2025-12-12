from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_super_segura' # Necessário para login (sessão)
DB_NAME = "interfone.db"

# --- Configuração do Banco de Dados ---
def init_db():
    """Cria as tabelas se não existirem e cria o admin padrão."""
    if not os.path.exists(DB_NAME):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Tabela de Usuários (Login)
        cursor.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        
        # Tabela de Ramais
        cursor.execute('''
            CREATE TABLE ramais (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                apartamento TEXT NOT NULL,  -- Ex: "101"
                nome_fala TEXT NOT NULL,    -- Ex: "cento e um" (o que o Vosk ouve)
                acao TEXT                   -- Ex: "GPIO_23" ou "DTMF_101"
            )
        ''')
        
        # Criar usuário admin padrão (admin / 1234)
        senha_hash = generate_password_hash("1234")
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", ("admin", senha_hash))
        
        conn.commit()
        conn.close()
        print("✅ Banco de dados criado com sucesso!")

# --- Rotas do Site ---

@app.route('/')
def index():
    """Se não estiver logado, manda pro login. Se estiver, manda pro admin."""
    if 'user_id' in session:
        return redirect(url_for('admin'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()
        
        # Verifica se usuário existe e se a senha bate com o hash
        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            return redirect(url_for('admin'))
        else:
            flash('Login inválido! Tente admin / 1234')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Adicionar novo ramal
    if request.method == 'POST':
        apto = request.form['apartamento']
        fala = request.form['nome_fala']
        # Simples validação
        if apto and fala:
            cursor.execute("INSERT INTO ramais (apartamento, nome_fala) VALUES (?, ?)", (apto, fala))
            conn.commit()
    
    # Listar ramais existentes
    cursor.execute("SELECT * FROM ramais")
    ramais = cursor.fetchall()
    conn.close()
    
    return render_template('admin.html', ramais=ramais)

@app.route('/delete/<int:id>')
def delete(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM ramais WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

if __name__ == '__main__':
    init_db() # Cria o banco na primeira vez
    # host='0.0.0.0' permite acessar de outro PC na rede
    app.run(debug=True, host='0.0.0.0', port=5003)