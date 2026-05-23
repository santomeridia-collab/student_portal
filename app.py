#!/usr/bin/env python3
"""
Student Result Portal - Oxford Fashion Designing
- Public: students search by register number (case‑insensitive)
- Private Admin: login, search students, edit records (no delete)
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash
import psycopg2
import os
import traceback
from functools import wraps

# ==================== CONFIGURATION ====================
DB_CONFIG = {
    'host': '140.245.239.67',  
    'database': 'smrl_dev',     
    'user': 'teamsdb',                      
    'password': 'smrl_dev251125',                   
    'port': 5432,
    'sslmode': 'require'
}

ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'supersecretkeychangeinproduction')

# ==================== HELPER ====================
def get_db_connection():
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        print(f"DB error: {e}")
        return None

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

# ==================== PUBLIC SEARCH ====================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    reg_number = request.form.get('register_number', '').strip()
    if not reg_number:
        return render_template('result.html', error="Please enter a register number.")

    conn = get_db_connection()
    if not conn:
        return render_template('result.html', error="Database error. Try later.")

    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT register_number, full_name, course, duration, center, date_of_issue, grade
            FROM business_db.oxford_students
            WHERE TRIM(register_number) ILIKE %s
        """, (reg_number,))
        student = cur.fetchone()
        cur.close()
        conn.close()

        if student:
            data = {
                'register_number': student[0],
                'full_name': student[1],
                'course': student[2],
                'duration': student[3],
                'center': student[4],
                'date_of_issue': student[5].strftime('%Y-%m-%d') if student[5] else 'N/A',
                'grade': student[6]
            }
            return render_template('result.html', student=data)
        else:
            return render_template('result.html', error=f"No record found for '{reg_number}'.")
    except Exception as e:
        print(traceback.format_exc())
        return render_template('result.html', error="Internal error.")

# ==================== ADMIN AUTH ====================
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Incorrect password', 'error')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

# ==================== ADMIN DASHBOARD (with search) ====================
@app.route('/admin')
@login_required
def admin_dashboard():
    search_query = request.args.get('search', '').strip()
    conn = get_db_connection()
    if not conn:
        flash('Database connection failed', 'error')
        return render_template('admin_dashboard.html', students=[], search_query=search_query)

    try:
        cur = conn.cursor()
        if search_query:
            cur.execute("""
                SELECT register_number, full_name, course, duration, center, date_of_issue, grade
                FROM business_db.oxford_students
                WHERE register_number ILIKE %s OR full_name ILIKE %s
                ORDER BY register_number
            """, (f'%{search_query}%', f'%{search_query}%'))
        else:
            cur.execute("""
                SELECT register_number, full_name, course, duration, center, date_of_issue, grade
                FROM business_db.oxford_students
                ORDER BY register_number
            """)
        students = cur.fetchall()
        cur.close()
        conn.close()
        return render_template('admin_dashboard.html', students=students, search_query=search_query)
    except Exception as e:
        flash(f'Error: {e}', 'error')
        return render_template('admin_dashboard.html', students=[], search_query=search_query)

# ==================== ADD / EDIT (no delete) ====================
@app.route('/admin/add', methods=['GET', 'POST'])
@login_required
def admin_add():
    if request.method == 'POST':
        register_number = request.form.get('register_number', '').strip()
        full_name = request.form.get('full_name', '').strip()
        course = request.form.get('course', '').strip()
        duration = request.form.get('duration', '').strip()
        center = request.form.get('center', '').strip()
        date_of_issue = request.form.get('date_of_issue', '') or None
        grade = request.form.get('grade', '').strip()

        if not register_number or not full_name:
            flash('Register number and Full name are required', 'error')
        else:
            conn = get_db_connection()
            if conn:
                try:
                    cur = conn.cursor()
                    cur.execute("""
                        INSERT INTO business_db.oxford_students 
                        (register_number, full_name, course, duration, center, date_of_issue, grade)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (register_number, full_name, course, duration, center, date_of_issue, grade))
                    conn.commit()
                    flash('Student added successfully!', 'success')
                    return redirect(url_for('admin_dashboard'))
                except Exception as e:
                    conn.rollback()
                    flash(f'Duplicate register number or error: {e}', 'error')
                finally:
                    cur.close()
                    conn.close()
            else:
                flash('Database error', 'error')
    return render_template('admin_add.html')

@app.route('/admin/edit/<path:register_number>', methods=['GET', 'POST'])
@login_required
def admin_edit(register_number):
    conn = get_db_connection()
    if not conn:
        flash('Database error', 'error')
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        course = request.form.get('course', '').strip()
        duration = request.form.get('duration', '').strip()
        center = request.form.get('center', '').strip()
        date_of_issue = request.form.get('date_of_issue', '') or None
        grade = request.form.get('grade', '').strip()

        try:
            cur = conn.cursor()
            cur.execute("""
                UPDATE business_db.oxford_students
                SET full_name=%s, course=%s, duration=%s, center=%s, date_of_issue=%s, grade=%s
                WHERE register_number=%s
            """, (full_name, course, duration, center, date_of_issue, grade, register_number))
            conn.commit()
            flash('Student updated successfully!', 'success')
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            conn.rollback()
            flash(f'Error: {e}', 'error')
        finally:
            cur.close()
            conn.close()
    else:
        # GET: load existing data
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM business_db.oxford_students WHERE register_number=%s", (register_number,))
            student = cur.fetchone()
            cur.close()
            conn.close()
            if student:
                return render_template('admin_edit.html', student={
                    'register_number': student[0],
                    'full_name': student[1],
                    'course': student[2],
                    'duration': student[3],
                    'center': student[4],
                    'date_of_issue': student[5].strftime('%Y-%m-%d') if student[5] else '',
                    'grade': student[6]
                })
            else:
                flash('Student not found', 'error')
                return redirect(url_for('admin_dashboard'))
        except Exception as e:
            flash(f'Error: {e}', 'error')
            return redirect(url_for('admin_dashboard'))

# (Optional: delete route is removed entirely – no delete functionality)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)