from flask import Flask, render_template, request, redirect, jsonify
import sqlite3
from datetime import date

app = Flask(__name__)

def get_db():
    conn = sqlite3.connect('tasks.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        start_time TEXT,
        end_time TEXT,
        is_routine INTEGER DEFAULT 0,
        done INTEGER DEFAULT 0,
        task_date TEXT NOT NULL
    )''')
    conn.commit()
    conn.close()

@app.route('/')
def index():
    conn = get_db()
    today = str(date.today())
    tasks = conn.execute('SELECT * FROM tasks WHERE task_date = ?', (today,)).fetchall()
    conn.close()
    return render_template('index.html', tasks=tasks, today=today)

@app.route('/add', methods=['POST'])
def add_task():
    name = request.form['name']
    start_time = request.form['start_time']
    end_time = request.form['end_time']
    is_routine = 1 if request.form.get('is_routine') else 0
    today = str(date.today())
    conn = get_db()
    conn.execute('INSERT INTO tasks (name, start_time, end_time, is_routine, task_date) VALUES (?,?,?,?,?)',
                 (name, start_time, end_time, is_routine, today))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/toggle/<int:task_id>')
def toggle(task_id):
    conn = get_db()
    task = conn.execute('SELECT done FROM tasks WHERE id=?', (task_id,)).fetchone()
    conn.execute('UPDATE tasks SET done=? WHERE id=?', (1 - task['done'], task_id))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/delete/<int:task_id>')
def delete(task_id):
    conn = get_db()
    conn.execute('DELETE FROM tasks WHERE id=?', (task_id,))
    conn.commit()
    conn.close()
    return redirect('/')

if __name__ == '__main__':
    init_db()
    app.run(debug=True)