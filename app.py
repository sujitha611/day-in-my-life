from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import date, timedelta

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
        task_date TEXT NOT NULL,
        notes TEXT DEFAULT ''
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        days_off TEXT DEFAULT '5,6'
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

def get_days_off(user_id):
    conn = get_db()
    setting = conn.execute('SELECT days_off FROM settings WHERE user_id=?', (user_id,)).fetchone()
    conn.close()
    if setting and setting['days_off']:
        return [int(d) for d in setting['days_off'].split(',') if d]
    return [5, 6]

def get_streak(user_id):
    conn = get_db()
    streak = 0
    today = date.today()
    days_off = get_days_off(user_id)
    for i in range(1, 30):
        day = today - timedelta(days=i)
        if day.weekday() in days_off:
            continue
        day_str = str(day)
        row = conn.execute(
            'SELECT COUNT(*) as total, SUM(done) as done FROM tasks WHERE user_id=? AND task_date=?',
            (user_id, day_str)
        ).fetchone()
        total = row['total'] or 0
        done = row['done'] or 0
        if total > 0 and done == total:
            streak += 1
        else:
            break
    conn.close()
    return streak

@app.route('/')
@login_required
def index():
    conn = get_db()
    today = str(date.today())
    today_date = date.today()
    days_off = get_days_off(current_user.id)
    is_off = today_date.weekday() in days_off
    streak = get_streak(current_user.id)
    tasks = []
    if not is_off:
        existing = conn.execute('SELECT COUNT(*) FROM tasks WHERE user_id=? AND task_date=?',
                               (current_user.id, today)).fetchone()[0]
        if existing == 0:
            routine_tasks = conn.execute(
                'SELECT * FROM tasks WHERE user_id=? AND is_routine=1 AND task_date != ?',
                (current_user.id, today)
            ).fetchall()
            for task in routine_tasks:
                already = conn.execute(
                    'SELECT COUNT(*) FROM tasks WHERE user_id=? AND name=? AND task_date=?',
                    (current_user.id, task['name'], today)
                ).fetchone()[0]
                if already == 0:
                    conn.execute(
                        'INSERT INTO tasks (user_id, name, start_time, end_time, is_routine, done, task_date) VALUES (?,?,?,?,?,0,?)',
                        (current_user.id, task['name'], task['start_time'], task['end_time'], 1, today)
                    )
            conn.commit()
        tasks = conn.execute('SELECT * FROM tasks WHERE user_id=? AND task_date=?',
                            (current_user.id, today)).fetchall()
    conn.close()
    return render_template('index.html', tasks=tasks, today=today, user=current_user, is_off=is_off, streak=streak)

@app.route('/add', methods=['POST'])
@login_required
def add_task():
    name = request.form['name']
    start_time = request.form['start_time']
    end_time = request.form['end_time']
    is_routine = 1 if request.form.get('is_routine') else 0
    notes = request.form.get('notes', '')
    today = str(date.today())
    conn = get_db()
    conn.execute('INSERT INTO tasks (user_id, name, start_time, end_time, is_routine, task_date, notes) VALUES (?,?,?,?,?,?,?)',
                (current_user.id, name, start_time, end_time, is_routine, today, notes))
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
@app.route('/history')
@login_required
def history():
    conn = get_db()
    today = str(date.today())
    search = request.args.get('search', '')
    if search:
        days = conn.execute(
            '''SELECT task_date, COUNT(*) as total, SUM(done) as done 
               FROM tasks WHERE user_id=? AND task_date != ? AND name LIKE ?
               GROUP BY task_date ORDER BY task_date DESC''',
            (current_user.id, today, f'%{search}%')
        ).fetchall()
        tasks = conn.execute(
            'SELECT * FROM tasks WHERE user_id=? AND name LIKE ? ORDER BY task_date DESC',
            (current_user.id, f'%{search}%')
        ).fetchall()
    else:
        days = conn.execute(
            'SELECT task_date, COUNT(*) as total, SUM(done) as done FROM tasks WHERE user_id=? AND task_date != ? GROUP BY task_date ORDER BY task_date DESC',
            (current_user.id, today)
        ).fetchall()
        tasks = []
    conn.close()
    return render_template('history.html', days=days, user=current_user, search=search, tasks=tasks)

@app.route('/weekly')
@login_required
def weekly():
    conn = get_db()
    today = date.today()
    week_data = []
    total_done = 0
    total_tasks = 0
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_str = str(day)
        row = conn.execute(
            'SELECT COUNT(*) as total, SUM(done) as done FROM tasks WHERE user_id=? AND task_date=?',
            (current_user.id, day_str)
        ).fetchone()
        done = row['done'] or 0
        total = row['total'] or 0
        percent = int((done / total) * 100) if total > 0 else 0
        week_data.append({
            'date': day_str,
            'day': day.strftime('%a'),
            'done': done,
            'total': total,
            'percent': percent
        })
        total_done += done
        total_tasks += total
    conn.close()
    week_percent = int((total_done / total_tasks) * 100) if total_tasks > 0 else 0
    return render_template('weekly.html', week_data=week_data, user=current_user,
                          total_done=total_done, total_tasks=total_tasks, week_percent=week_percent)

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html', user=current_user)

@app.route('/profile/name', methods=['POST'])
@login_required
def update_name():
    name = request.form['name']
    conn = get_db()
    conn.execute('UPDATE users SET name=? WHERE id=?', (name, current_user.id))
    conn.commit()
    conn.close()
    flash('Name updated successfully!', 'success')
    return redirect(url_for('profile'))

@app.route('/profile/password', methods=['POST'])
@login_required
def update_password():
    current_password = request.form['current_password']
    new_password = request.form['new_password']
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id=?', (current_user.id,)).fetchone()
    if check_password_hash(user['password'], current_password):
        conn.execute('UPDATE users SET password=? WHERE id=?',
                    (generate_password_hash(new_password), current_user.id))
        conn.commit()
        flash('Password updated successfully!', 'success')
    else:
        flash('Current password is wrong!', 'error')
    conn.close()
    return redirect(url_for('profile'))

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        selected = request.form.getlist('days_off')
        days_off_str = ','.join(selected)
        conn = get_db()
        existing = conn.execute('SELECT id FROM settings WHERE user_id=?', (current_user.id,)).fetchone()
        if existing:
            conn.execute('UPDATE settings SET days_off=? WHERE user_id=?', (days_off_str, current_user.id))
        else:
            conn.execute('INSERT INTO settings (user_id, days_off) VALUES (?,?)', (current_user.id, days_off_str))
        conn.commit()
        conn.close()
        flash('Settings saved!', 'success')
        return redirect(url_for('index'))
    days_off = get_days_off(current_user.id)
    return render_template('settings.html', user=current_user, days_off=days_off)

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
@app.route('/export')
@login_required
def export():
    import csv
    import io
    from flask import Response
    conn = get_db()
    tasks = conn.execute(
        'SELECT name, start_time, end_time, is_routine, done, task_date, notes FROM tasks WHERE user_id=? ORDER BY task_date DESC',
        (current_user.id,)
    ).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Task', 'Start Time', 'End Time', 'Routine', 'Done', 'Date', 'Notes'])
    for task in tasks:
        writer.writerow([
            task['name'],
            task['start_time'],
            task['end_time'],
            'Yes' if task['is_routine'] else 'No',
            'Done' if task['done'] else 'Pending',
            task['task_date'],
            task['notes']
        ])
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment;filename=diml_tasks_{current_user.name}.csv'}
    )
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)