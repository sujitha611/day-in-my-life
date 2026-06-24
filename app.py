from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import date

app = Flask(__name__)
app.secret_key = 'diml_secret_key_2026'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

def get_db():
    conn = sqlite3.connect('tasks.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        start_time TEXT,
        end_time TEXT,
        is_routine INTEGER DEFAULT 0,
        done INTEGER DEFAULT 0,
        task_date TEXT NOT NULL
    )''')
    conn.commit()
    conn.close()

class User(UserMixin):
    def __init__(self, id, name, email):
        self.id = id
        self.name = name
        self.email = email

@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
    conn.close()
    if user:
        return User(user['id'], user['name'], user['email'])
    return None

@app.route('/')
@login_required
def index():
    conn = get_db()
    today = str(date.today())
    today_date = date.today()
    is_weekend = today_date.weekday() in [5, 6]  # 5=Saturday, 6=Sunday
    tasks = []
    if not is_weekend:
        tasks = conn.execute('SELECT * FROM tasks WHERE user_id=? AND task_date=?',
                            (current_user.id, today)).fetchall()
    conn.close()
    return render_template('index.html', tasks=tasks, today=today, user=current_user, is_weekend=is_weekend)

@app.route('/add', methods=['POST'])
@login_required
def add_task():
    name = request.form['name']
    start_time = request.form['start_time']
    end_time = request.form['end_time']
    is_routine = 1 if request.form.get('is_routine') else 0
    today = str(date.today())
    conn = get_db()
    conn.execute('INSERT INTO tasks (user_id, name, start_time, end_time, is_routine, task_date) VALUES (?,?,?,?,?,?)',
                (current_user.id, name, start_time, end_time, is_routine, today))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/toggle/<int:task_id>')
@login_required
def toggle(task_id):
    conn = get_db()
    task = conn.execute('SELECT * FROM tasks WHERE id=? AND user_id=?',
                       (task_id, current_user.id)).fetchone()
    if task:
        conn.execute('UPDATE tasks SET done=? WHERE id=?', (1 - task['done'], task_id))
        conn.commit()
    conn.close()
    return redirect('/')

@app.route('/delete/<int:task_id>')
@login_required
def delete(task_id):
    conn = get_db()
    conn.execute('DELETE FROM tasks WHERE id=? AND user_id=?', (task_id, current_user.id))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        conn = get_db()
        try:
            conn.execute('INSERT INTO users (name, email, password) VALUES (?,?,?)',
                        (name, email, password))
            conn.commit()
            flash('Account created! Please login.', 'success')
            return redirect(url_for('login'))
        except:
            flash('Email already exists!', 'error')
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password'], password):
            login_user(User(user['id'], user['name'], user['email']))
            return redirect(url_for('index'))
        flash('Wrong email or password!', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)