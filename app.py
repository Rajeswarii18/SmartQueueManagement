import os
import sqlite3
import time
import random
import json
import csv
import io
from datetime import datetime, timedelta
from flask import Flask, render_template_string, jsonify, request, Response

app = Flask(__name__)
DB_FILE = os.path.join(os.path.dirname(__file__), 'queue_system.db')

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        # Services Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                prefix TEXT NOT NULL,
                avg_time_mins INTEGER DEFAULT 5,
                color TEXT DEFAULT '#3b82f6'
            )
        ''')
        # Counters Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS counters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                staff_name TEXT DEFAULT 'Agent',
                current_ticket_id INTEGER,
                status TEXT DEFAULT 'available',
                active_service_id INTEGER
            )
        ''')
        # Tickets Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_number TEXT NOT NULL,
                service_id INTEGER NOT NULL,
                customer_name TEXT DEFAULT 'Guest',
                customer_phone TEXT,
                customer_email TEXT,
                is_vip INTEGER DEFAULT 0,
                status TEXT DEFAULT 'waiting',
                counter_id INTEGER,
                wait_time_mins INTEGER DEFAULT 0,
                service_time_mins INTEGER DEFAULT 0,
                rating INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                called_at TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (service_id) REFERENCES services (id),
                FOREIGN KEY (counter_id) REFERENCES counters (id)
            )
        ''')

        # Schema migrations for existing SQLite DBs
        cursor.execute("PRAGMA table_info(tickets)")
        cols = [row['name'] for row in cursor.fetchall()]
        if 'customer_email' not in cols:
            cursor.execute("ALTER TABLE tickets ADD COLUMN customer_email TEXT")
        if 'wait_time_mins' not in cols:
            cursor.execute("ALTER TABLE tickets ADD COLUMN wait_time_mins INTEGER DEFAULT 0")
        if 'service_time_mins' not in cols:
            cursor.execute("ALTER TABLE tickets ADD COLUMN service_time_mins INTEGER DEFAULT 0")
        if 'rating' not in cols:
            cursor.execute("ALTER TABLE tickets ADD COLUMN rating INTEGER")

        # Insert Default Services if empty
        cursor.execute('SELECT COUNT(*) FROM services')
        if cursor.fetchone()[0] == 0:
            cursor.executemany('''
                INSERT INTO services (code, name, description, prefix, avg_time_mins, color)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', [
                ('GEN', 'General Enquiry', 'General customer inquiries and assistance', 'A', 4, '#3b82f6'),
                ('ACC', 'Accounts & Billing', 'Payments, billing, and account management', 'B', 6, '#8b5cf6'),
                ('VIP', 'VIP / Priority Service', 'Fast-track premium queue for priority guests', 'V', 3, '#f59e0b'),
                ('TECH', 'Technical Support', 'Technical troubleshooting and hardware support', 'C', 8, '#10b981')
            ])

        # Insert Default Counters if empty
        cursor.execute('SELECT COUNT(*) FROM counters')
        if cursor.fetchone()[0] == 0:
            cursor.executemany('''
                INSERT INTO counters (name, staff_name, status, active_service_id)
                VALUES (?, ?, ?, ?)
            ''', [
                ('Counter 1', 'Sarah Jenkins', 'available', 1),
                ('Counter 2', 'David Miller', 'available', 2),
                ('Counter 3 (VIP)', 'Elena Rostova', 'available', 3),
                ('Counter 4', 'Alex Rivera', 'available', 4)
            ])
        conn.commit()

init_db()

# --- DATASET SEEDER ---
FIRST_NAMES = ["James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda", "William", "Elizabeth", "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica", "Thomas", "Sarah", "Charles", "Karen", "Christopher", "Nancy", "Daniel", "Lisa", "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra", "Oliver", "Emma", "Liam", "Ava", "Noah", "Sophia", "Lucas", "Isabella"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "White", "Harris", "Clark"]

def seed_dataset(count=500):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, prefix, avg_time_mins FROM services")
        services = [dict(row) for row in cursor.fetchall()]
        if not services:
            return 0
        
        cursor.execute("SELECT id FROM counters")
        counters = [row[0] for row in cursor.fetchall()]

        statuses = ['completed', 'completed', 'completed', 'completed', 'completed', 'no_show', 'cancelled']
        start_date = datetime.now() - timedelta(days=30)
        
        inserted = 0
        for i in range(count):
            srv = random.choice(services)
            c_first = random.choice(FIRST_NAMES)
            c_last = random.choice(LAST_NAMES)
            customer_name = f"{c_first} {c_last}"
            customer_phone = f"+1 ({random.randint(200,999)}) {random.randint(100,999)}-{random.randint(1000,9999)}"
            customer_email = f"{c_first.lower()}.{c_last.lower()}@example.com"
            is_vip = 1 if (srv['prefix'] == 'V' or random.random() < 0.15) else 0
            
            days_ago = random.randint(0, 30)
            hour = random.choices(
                population=[8, 9, 10, 11, 12, 13, 14, 15, 16, 17],
                weights=[5, 15, 22, 18, 10, 14, 18, 15, 8, 4]
            )[0]
            minute = random.randint(0, 59)
            second = random.randint(0, 59)
            
            created_dt = start_date + timedelta(days=days_ago)
            created_dt = created_dt.replace(hour=hour, minute=minute, second=second)
            
            status = random.choice(statuses)
            counter_id = random.choice(counters) if (counters and status == 'completed') else None
            
            wait_mins = random.randint(1, 22) if status == 'completed' else random.randint(5, 35)
            service_mins = max(1, int(random.normalvariate(srv['avg_time_mins'], 1.5)))
            
            called_dt = created_dt + timedelta(minutes=wait_mins)
            completed_dt = called_dt + timedelta(minutes=service_mins) if status == 'completed' else None
            
            rating = random.choices([1, 2, 3, 4, 5], weights=[2, 4, 12, 36, 46])[0] if status == 'completed' else None
            ticket_number = f"{srv['prefix']}-{random.randint(1, 999):03d}"
            
            cursor.execute('''
                INSERT INTO tickets 
                (ticket_number, service_id, customer_name, customer_phone, customer_email, is_vip, status, counter_id, wait_time_mins, service_time_mins, rating, created_at, called_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                ticket_number, srv['id'], customer_name, customer_phone, customer_email,
                is_vip, status, counter_id, wait_mins, service_mins, rating,
                created_dt.strftime('%Y-%m-%d %H:%M:%S'),
                called_dt.strftime('%Y-%m-%d %H:%M:%S'),
                completed_dt.strftime('%Y-%m-%d %H:%M:%S') if completed_dt else None
            ))
            inserted += 1
            
        conn.commit()
        return inserted

# --- API ENDPOINTS ---

@app.route('/api/status', methods=['GET'])
def get_status():
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT t.*, s.name as service_name, s.color as service_color, s.prefix
            FROM tickets t
            JOIN services s ON t.service_id = s.id
            WHERE t.status = 'waiting'
            ORDER BY t.is_vip DESC, t.id ASC
        ''')
        waiting_tickets = [dict(row) for row in cursor.fetchall()]

        cursor.execute('''
            SELECT t.*, s.name as service_name, s.color as service_color, c.name as counter_name
            FROM tickets t
            JOIN services s ON t.service_id = s.id
            LEFT JOIN counters c ON t.counter_id = c.id
            WHERE t.status IN ('called', 'in_service')
            ORDER BY t.called_at DESC
        ''')
        active_tickets = [dict(row) for row in cursor.fetchall()]

        cursor.execute('''
            SELECT c.*, s.name as service_name, t.ticket_number as current_ticket_number
            FROM counters c
            LEFT JOIN services s ON c.active_service_id = s.id
            LEFT JOIN tickets t ON c.current_ticket_id = t.id
        ''')
        counters = [dict(row) for row in cursor.fetchall()]

        cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'completed'")
        completed_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'waiting'")
        waiting_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tickets WHERE status IN ('called', 'in_service')")
        serving_count = cursor.fetchone()[0]

        avg_est_wait = waiting_count * 4

        return jsonify({
            'success': True,
            'waiting_tickets': waiting_tickets,
            'active_tickets': active_tickets,
            'counters': counters,
            'stats': {
                'waiting_count': waiting_count,
                'serving_count': serving_count,
                'completed_count': completed_count,
                'est_wait_mins': avg_est_wait
            }
        })

@app.route('/api/ticket/issue', methods=['POST'])
def issue_ticket():
    data = request.json or {}
    service_id = data.get('service_id')
    customer_name = data.get('customer_name', 'Guest').strip() or 'Guest'
    customer_phone = data.get('customer_phone', '').strip()
    customer_email = data.get('customer_email', '').strip()
    is_vip = 1 if data.get('is_vip') else 0

    if not service_id:
        return jsonify({'success': False, 'error': 'Service ID is required'}), 400

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT prefix, avg_time_mins FROM services WHERE id = ?', (service_id,))
        srv = cursor.fetchone()
        if not srv:
            return jsonify({'success': False, 'error': 'Invalid Service'}), 404
        
        prefix = srv['prefix']
        
        cursor.execute('''
            SELECT COUNT(*) FROM tickets 
            WHERE service_id = ? AND date(created_at) = date('now')
        ''', (service_id,))
        count = cursor.fetchone()[0] + 1
        ticket_number = f"{prefix}-{count:03d}"

        cursor.execute('''
            INSERT INTO tickets (ticket_number, service_id, customer_name, customer_phone, customer_email, is_vip, status)
            VALUES (?, ?, ?, ?, ?, ?, 'waiting')
        ''', (ticket_number, service_id, customer_name, customer_phone, customer_email, is_vip))
        ticket_id = cursor.lastrowid
        conn.commit()

        cursor.execute('''
            SELECT COUNT(*) FROM tickets 
            WHERE service_id = ? AND status = 'waiting' AND id < ?
        ''', (service_id, ticket_id))
        ahead = cursor.fetchone()[0]

        return jsonify({
            'success': True,
            'ticket': {
                'id': ticket_id,
                'ticket_number': ticket_number,
                'customer_name': customer_name,
                'is_vip': is_vip,
                'position_ahead': ahead,
                'est_wait_mins': (ahead + 1) * srv['avg_time_mins']
            }
        })

@app.route('/api/counter/call_next', methods=['POST'])
def call_next_ticket():
    data = request.json or {}
    counter_id = data.get('counter_id')
    
    if not counter_id:
        return jsonify({'success': False, 'error': 'Counter ID is required'}), 400

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM counters WHERE id = ?', (counter_id,))
        counter = cursor.fetchone()
        if not counter:
            return jsonify({'success': False, 'error': 'Counter not found'}), 404

        if counter['current_ticket_id']:
            cursor.execute('''
                UPDATE tickets SET status = 'completed', completed_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status IN ('called', 'in_service')
            ''', (counter['current_ticket_id'],))

        active_srv_id = counter['active_service_id']
        cursor.execute('''
            SELECT * FROM tickets 
            WHERE status = 'waiting' AND (service_id = ? OR 1=1)
            ORDER BY is_vip DESC, (CASE WHEN service_id = ? THEN 0 ELSE 1 END), id ASC
            LIMIT 1
        ''', (active_srv_id, active_srv_id))
        next_ticket = cursor.fetchone()

        if not next_ticket:
            cursor.execute('UPDATE counters SET current_ticket_id = NULL, status = "available" WHERE id = ?', (counter_id,))
            conn.commit()
            return jsonify({'success': True, 'ticket': None, 'message': 'No waiting tickets in queue'})

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            UPDATE tickets 
            SET status = 'called', counter_id = ?, called_at = ?
            WHERE id = ?
        ''', (counter_id, now_str, next_ticket['id']))

        cursor.execute('''
            UPDATE counters 
            SET current_ticket_id = ?, status = 'busy'
            WHERE id = ?
        ''', (next_ticket['id'], counter_id))

        conn.commit()

        return jsonify({
            'success': True,
            'ticket': {
                'id': next_ticket['id'],
                'ticket_number': next_ticket['ticket_number'],
                'customer_name': next_ticket['customer_name'],
                'counter_name': counter['name']
            }
        })

@app.route('/api/counter/update_status', methods=['POST'])
def update_counter_ticket_status():
    data = request.json or {}
    counter_id = data.get('counter_id')
    new_status = data.get('status')

    if not counter_id or not new_status:
        return jsonify({'success': False, 'error': 'Missing parameters'}), 400

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT current_ticket_id FROM counters WHERE id = ?', (counter_id,))
        row = cursor.fetchone()
        if row and row['current_ticket_id']:
            ticket_id = row['current_ticket_id']
            if new_status in ['completed', 'no_show']:
                cursor.execute('UPDATE tickets SET status = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?', (new_status, ticket_id))
                cursor.execute('UPDATE counters SET current_ticket_id = NULL, status = "available" WHERE id = ?', (counter_id,))
            else:
                cursor.execute('UPDATE tickets SET status = ? WHERE id = ?', (new_status, ticket_id))
            conn.commit()

    return jsonify({'success': True})

@app.route('/api/services', methods=['GET'])
def get_services():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM services ORDER BY id ASC')
        services = [dict(row) for row in cursor.fetchall()]
    return jsonify({'success': True, 'services': services})

# --- DATASET & ANALYTICS API ENDPOINTS ---

@app.route('/api/dataset/seed', methods=['POST'])
def seed_dataset_endpoint():
    data = request.json or {}
    count = data.get('count', 500)
    try:
        count = int(count)
    except ValueError:
        count = 500

    count = max(10, min(count, 5000))
    inserted = seed_dataset(count)
    return jsonify({'success': True, 'inserted': inserted, 'message': f'Successfully seeded {inserted} dataset records!'})

@app.route('/api/dataset/reset', methods=['POST'])
def reset_dataset_endpoint():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tickets")
        cursor.execute("UPDATE counters SET current_ticket_id = NULL, status = 'available'")
        conn.commit()
    return jsonify({'success': True, 'message': 'Dataset reset successfully!'})

@app.route('/api/dataset/stats', methods=['GET'])
def get_dataset_stats():
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM tickets")
        total_tickets = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'completed'")
        completed_tickets = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'no_show'")
        no_show_tickets = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'cancelled'")
        cancelled_tickets = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'waiting'")
        waiting_tickets = cursor.fetchone()[0]

        cursor.execute("SELECT AVG(wait_time_mins), AVG(service_time_mins), AVG(rating) FROM tickets WHERE status = 'completed'")
        avg_row = cursor.fetchone()
        avg_wait = round(avg_row[0] or 0, 1)
        avg_service = round(avg_row[1] or 0, 1)
        avg_rating = round(avg_row[2] or 0, 2)

        # Hourly Distribution (08:00 to 17:00)
        cursor.execute('''
            SELECT strftime('%H:00', created_at) as hour, COUNT(*) as cnt 
            FROM tickets 
            GROUP BY hour 
            ORDER BY hour ASC
        ''')
        hourly_raw = {row['hour']: row['cnt'] for row in cursor.fetchall()}
        hourly_data = []
        for h in range(8, 18):
            h_str = f"{h:02d}:00"
            hourly_data.append({'hour': h_str, 'count': hourly_raw.get(h_str, 0)})

        # Service Distribution Breakdown
        cursor.execute('''
            SELECT s.name, s.color, COUNT(t.id) as count
            FROM services s
            LEFT JOIN tickets t ON s.id = t.service_id
            GROUP BY s.id
        ''')
        service_breakdown = [dict(row) for row in cursor.fetchall()]

        # Counter Performance Breakdown
        cursor.execute('''
            SELECT c.name as counter_name, c.staff_name, COUNT(t.id) as tickets_handled, AVG(t.service_time_mins) as avg_handle_time
            FROM counters c
            LEFT JOIN tickets t ON c.id = t.counter_id AND t.status = 'completed'
            GROUP BY c.id
        ''')
        counter_perf = [
            {
                'counter_name': row['counter_name'],
                'staff_name': row['staff_name'],
                'tickets_handled': row['tickets_handled'],
                'avg_handle_time': round(row['avg_handle_time'] or 0, 1)
            } for row in cursor.fetchall()
        ]

        # Rating CSAT Distribution
        cursor.execute('''
            SELECT rating, COUNT(*) as count 
            FROM tickets 
            WHERE rating IS NOT NULL 
            GROUP BY rating
            ORDER BY rating ASC
        ''')
        rating_raw = {row['rating']: row['count'] for row in cursor.fetchall()}
        rating_breakdown = [{'stars': r, 'count': rating_raw.get(r, 0)} for r in range(1, 6)]

        return jsonify({
            'success': True,
            'summary': {
                'total_tickets': total_tickets,
                'completed_tickets': completed_tickets,
                'no_show_tickets': no_show_tickets,
                'cancelled_tickets': cancelled_tickets,
                'waiting_tickets': waiting_tickets,
                'avg_wait_mins': avg_wait,
                'avg_service_mins': avg_service,
                'csat_score': avg_rating
            },
            'hourly_traffic': hourly_data,
            'service_breakdown': service_breakdown,
            'counter_perf': counter_perf,
            'rating_breakdown': rating_breakdown
        })

@app.route('/api/dataset/records', methods=['GET'])
def get_dataset_records():
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 15))
    search = request.args.get('search', '').strip()
    status = request.args.get('status', '').strip()
    service_id = request.args.get('service_id', '').strip()

    offset = (page - 1) * limit
    where_clauses = ["1=1"]
    params = []

    if search:
        where_clauses.append("(t.ticket_number LIKE ? OR t.customer_name LIKE ? OR t.customer_email LIKE ?)")
        search_param = f"%{search}%"
        params.extend([search_param, search_param, search_param])
    
    if status:
        where_clauses.append("t.status = ?")
        params.append(status)

    if service_id:
        where_clauses.append("t.service_id = ?")
        params.append(service_id)

    where_str = " AND ".join(where_clauses)

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM tickets t WHERE {where_str}", params)
        total_count = cursor.fetchone()[0]

        cursor.execute(f'''
            SELECT t.*, s.name as service_name, s.color as service_color, c.name as counter_name
            FROM tickets t
            JOIN services s ON t.service_id = s.id
            LEFT JOIN counters c ON t.counter_id = c.id
            WHERE {where_str}
            ORDER BY t.id DESC
            LIMIT ? OFFSET ?
        ''', params + [limit, offset])

        records = [dict(row) for row in cursor.fetchall()]
        total_pages = max(1, (total_count + limit - 1) // limit)

        return jsonify({
            'success': True,
            'records': records,
            'total': total_count,
            'page': page,
            'total_pages': total_pages
        })

@app.route('/api/dataset/export', methods=['GET'])
def export_dataset():
    fmt = request.args.get('format', 'csv').lower()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT t.id, t.ticket_number, s.name as service_name, t.customer_name, t.customer_phone, t.customer_email,
                   t.is_vip, t.status, c.name as counter_name, t.wait_time_mins, t.service_time_mins, t.rating,
                   t.created_at, t.completed_at
            FROM tickets t
            JOIN services s ON t.service_id = s.id
            LEFT JOIN counters c ON t.counter_id = c.id
            ORDER BY t.id ASC
        ''')
        rows = [dict(r) for r in cursor.fetchall()]

    if fmt == 'json':
        return Response(
            json.dumps(rows, indent=2),
            mimetype='application/json',
            headers={'Content-Disposition': 'attachment;filename=smart_queue_dataset.json'}
        )
    else:
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=[
            'id', 'ticket_number', 'service_name', 'customer_name', 'customer_phone', 'customer_email',
            'is_vip', 'status', 'counter_name', 'wait_time_mins', 'service_time_mins', 'rating',
            'created_at', 'completed_at'
        ])
        writer.writeheader()
        writer.writerows(rows)

        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment;filename=smart_queue_dataset.csv'}
        )

@app.route('/api/dataset/import', methods=['POST'])
def import_dataset():
    data = request.json
    if not data or not isinstance(data, list):
        return jsonify({'success': False, 'error': 'Invalid format. Expected a JSON array of records.'}), 400

    imported = 0
    with get_db() as conn:
        cursor = conn.cursor()
        for item in data:
            cursor.execute('''
                INSERT INTO tickets (ticket_number, service_id, customer_name, customer_phone, customer_email, is_vip, status, wait_time_mins, service_time_mins, rating)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                item.get('ticket_number', 'T-001'),
                item.get('service_id', 1),
                item.get('customer_name', 'Guest'),
                item.get('customer_phone', ''),
                item.get('customer_email', ''),
                1 if item.get('is_vip') else 0,
                item.get('status', 'completed'),
                item.get('wait_time_mins', 5),
                item.get('service_time_mins', 5),
                item.get('rating', 5)
            ))
            imported += 1
        conn.commit()

    return jsonify({'success': True, 'imported': imported, 'message': f'Successfully imported {imported} records.'})

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(os.path.join(app.root_path, 'static'), filename)

@app.route('/hospital_hero.jpg')
def serve_hospital_hero():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'hospital_hero.jpg')

# --- HTML TEMPLATE WITH PREMIUM REDESIGN ---

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Smart Queue Pro - Intelligent Queue & Dataset Engine</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --bg: #0b0f19;
            --surface: #131b2e;
            --surface-card: #1c2640;
            --surface-hover: #263352;
            --border: rgba(255, 255, 255, 0.08);
            --primary: #4f46e5;
            --primary-light: #6366f1;
            --primary-glow: rgba(99, 102, 241, 0.35);
            --accent: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Plus Jakarta Sans', sans-serif;
        }

        body {
            background-color: var(--bg);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }

        /* Modern Glass Header */
        header {
            background: rgba(19, 27, 46, 0.85);
            backdrop-filter: blur(16px);
            border-bottom: 1px solid var(--border);
            padding: 1rem 2rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            position: sticky;
            top: 0;
            z-index: 100;
        }

        .brand {
            display: flex;
            align-items: center;
            gap: 0.85rem;
        }

        .brand-icon {
            width: 42px;
            height: 42px;
            background: linear-gradient(135deg, #4f46e5, #ec4899);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 800;
            font-size: 1.3rem;
            box-shadow: 0 0 25px rgba(99, 102, 241, 0.4);
        }

        .brand h1 {
            font-size: 1.35rem;
            font-weight: 800;
            background: linear-gradient(90deg, #ffffff, #818cf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .nav-tabs {
            display: flex;
            gap: 0.4rem;
            background: rgba(255, 255, 255, 0.04);
            padding: 0.35rem;
            border-radius: 14px;
            border: 1px solid var(--border);
        }

        .tab-btn {
            padding: 0.6rem 1.1rem;
            border: none;
            background: transparent;
            color: var(--text-muted);
            font-weight: 600;
            font-size: 0.88rem;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
            display: flex;
            align-items: center;
            gap: 0.4rem;
        }

        .tab-btn:hover {
            color: var(--text-main);
            background: rgba(255, 255, 255, 0.05);
        }

        .tab-btn.active {
            background: var(--primary);
            color: white;
            box-shadow: 0 4px 20px var(--primary-glow);
        }

        .server-url-badge {
            background: rgba(16, 185, 129, 0.15);
            border: 1px solid rgba(16, 185, 129, 0.4);
            color: #34d399;
            padding: 0.4rem 0.8rem;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .container {
            max-width: 1440px;
            margin: 0 auto;
            width: 100%;
            padding: 2rem;
            flex: 1;
        }

        /* View Panels */
        .view-panel {
            display: none;
            animation: fadeIn 0.35s ease;
        }
        .view-panel.active {
            display: block;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* Cards & Layout */
        .grid-2 {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2rem;
        }

        .grid-4 {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 1.5rem;
        }

        @media (max-width: 1024px) {
            .grid-2, .grid-4 { grid-template-columns: 1fr; }
        }

        .card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 1.75rem;
            box-shadow: 0 15px 35px rgba(0,0,0,0.35);
        }

        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.5rem;
        }

        .card-title {
            font-size: 1.15rem;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 0.6rem;
        }

        /* Buttons & Forms */
        .btn {
            background: var(--primary);
            color: white;
            border: none;
            padding: 0.7rem 1.4rem;
            font-weight: 600;
            font-size: 0.9rem;
            border-radius: 12px;
            cursor: pointer;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
        }

        .btn:hover {
            opacity: 0.92;
            transform: translateY(-1px);
            box-shadow: 0 4px 18px var(--primary-glow);
        }

        .btn-success { background: var(--accent); }
        .btn-warning { background: var(--warning); color: #000; }
        .btn-danger { background: var(--danger); }
        .btn-secondary { background: rgba(255,255,255,0.08); color: var(--text-main); border: 1px solid var(--border); }
        .btn-secondary:hover { background: rgba(255,255,255,0.15); }

        .input-group {
            margin-bottom: 1.1rem;
        }

        .input-group label {
            display: block;
            font-size: 0.85rem;
            color: var(--text-muted);
            margin-bottom: 0.45rem;
            font-weight: 500;
        }

        .input-group input, .input-group select {
            width: 100%;
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid var(--border);
            padding: 0.8rem 1rem;
            border-radius: 12px;
            color: white;
            font-size: 0.95rem;
            outline: none;
            transition: border 0.2s;
        }

        .input-group input:focus, .input-group select:focus {
            border-color: var(--primary-light);
            background: rgba(255, 255, 255, 0.07);
        }

        /* Badges */
        .badge {
            padding: 0.35rem 0.8rem;
            border-radius: 20px;
            font-size: 0.78rem;
            font-weight: 700;
            display: inline-flex;
            align-items: center;
            gap: 0.3rem;
        }

        .badge-vip { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.4); }
        .badge-waiting { background: rgba(99, 102, 241, 0.2); color: #a5b4fc; border: 1px solid rgba(99, 102, 241, 0.3); }
        .badge-active { background: rgba(16, 185, 129, 0.2); color: #6ee7b7; border: 1px solid rgba(16, 185, 129, 0.4); }
        .badge-noshow { background: rgba(239, 68, 68, 0.2); color: #fca5a5; border: 1px solid rgba(239, 68, 68, 0.4); }

        /* Ticket Receipt Card */
        .ticket-receipt {
            background: linear-gradient(180deg, #1e293b, #0f172a);
            border: 2px dashed rgba(255,255,255,0.18);
            border-radius: 20px;
            padding: 2rem;
            text-align: center;
            margin-top: 1rem;
            animation: fadeIn 0.4s ease;
        }

        .ticket-number-display {
            font-size: 3.8rem;
            font-weight: 900;
            color: #818cf8;
            letter-spacing: 3px;
            margin: 0.5rem 0;
            text-shadow: 0 0 25px rgba(129, 140, 248, 0.5);
        }

        /* Big TV Display View */
        .display-grid {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 2rem;
        }

        .now-calling-card {
            background: linear-gradient(135deg, rgba(79, 70, 229, 0.25), rgba(15, 23, 42, 0.95));
            border: 2px solid var(--primary-light);
            border-radius: 24px;
            padding: 3.5rem;
            text-align: center;
            box-shadow: 0 0 60px rgba(99, 102, 241, 0.3);
        }

        .calling-number {
            font-size: 6.5rem;
            font-weight: 900;
            color: #818cf8;
            margin: 1rem 0;
            animation: pulse 2s infinite;
        }

        .calling-counter {
            font-size: 2.4rem;
            font-weight: 800;
            color: #34d399;
        }

        @keyframes pulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.03); }
        }

        /* Tables */
        .data-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 1rem;
        }

        .data-table th, .data-table td {
            padding: 1rem 1.25rem;
            text-align: left;
            border-bottom: 1px solid var(--border);
            font-size: 0.9rem;
        }

        .data-table th {
            color: var(--text-muted);
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            font-weight: 700;
            background: rgba(255,255,255,0.02);
        }

        .data-table tr:hover td {
            background: rgba(255,255,255,0.02);
        }

        /* Counter Workstation Grid */
        .counter-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(310px, 1fr));
            gap: 1.5rem;
        }

        .counter-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 1.75rem;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }

        /* Stats Banners */
        .stats-banner {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 1.5rem;
            margin-bottom: 2rem;
        }

        .stat-card {
            background: var(--surface);
            border: 1px solid var(--border);
            padding: 1.4rem;
            border-radius: 18px;
            text-align: center;
        }

        .stat-value {
            font-size: 2.2rem;
            font-weight: 800;
            color: var(--primary-light);
            margin-top: 0.4rem;
        }

        /* Pagination & Search Bar */
        .table-controls {
            display: flex;
            gap: 1rem;
            margin-bottom: 1.25rem;
            flex-wrap: wrap;
            align-items: center;
            justify-content: space-between;
        }

        .pagination {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-top: 1.25rem;
            justify-content: flex-end;
        }

        /* Chart Canvas Wrappers */
        .chart-container {
            position: relative;
            height: 280px;
            width: 100%;
        }
    </style>
</head>
<body>

    <header>
        <div class="brand">
            <div class="brand-icon">⚡</div>
            <div>
                <h1>SmartQueue Pro</h1>
                <p style="font-size: 0.78rem; color: var(--text-muted);">Intelligent Queue Management & Dataset Hub</p>
            </div>
        </div>

        <div class="nav-tabs">
            <button class="tab-btn active" onclick="switchTab('kiosk', event)">🎫 Kiosk & Ticket</button>
            <button class="tab-btn" onclick="switchTab('display', event)">📺 Big Screen TV</button>
            <button class="tab-btn" onclick="switchTab('counter', event)">🎧 Counter Agent</button>
            <button class="tab-btn" onclick="switchTab('dataset', event)">📈 Dataset & Analytics</button>
            <button class="tab-btn" onclick="switchTab('admin', event)">⚙️ Admin Panel</button>
        </div>

        <div class="server-url-badge">
            <span style="width:8px; height:8px; background:#10b981; border-radius:50%; display:inline-block;"></span>
            <span>http://127.0.0.1:5000</span>
        </div>
    </header>

    <div class="container">

        <!-- HOSPITAL HERO BANNER -->
        <div class="card" style="margin-bottom: 2rem; overflow: hidden; padding: 0; position: relative; border-color: rgba(99, 102, 241, 0.25);">
            <div style="position: relative; width: 100%; height: 260px; overflow: hidden;">
                <img src="/static/hospital_hero.jpg" alt="Nexus Medical Center Hospital Reception" style="width: 100%; height: 100%; object-fit: cover; filter: brightness(0.85);" />
                <div style="position: absolute; inset: 0; background: linear-gradient(90deg, rgba(11, 15, 25, 0.92) 0%, rgba(11, 15, 25, 0.6) 50%, rgba(11, 15, 25, 0.2) 100%); display: flex; align-items: center; padding: 2.5rem;">
                    <div style="max-width: 650px;">
                        <span class="badge badge-waiting" style="margin-bottom: 0.75rem; background: rgba(99, 102, 241, 0.25); color: #a5b4fc; border: 1px solid rgba(99, 102, 241, 0.5);">🏥 Healthcare Patient Flow & Queue Portal</span>
                        <h2 style="font-size: 2rem; font-weight: 800; color: #ffffff; line-height: 1.2; margin-bottom: 0.5rem;">The Nexus Medical Center</h2>
                        <p style="font-size: 0.95rem; color: #cbd5e1; line-height: 1.5;">Intelligent patient check-in, priority emergency triage, specialized consultation queue, and real-time medical staff workload management.</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- TOP STATS BANNER -->
        <div class="stats-banner">
            <div class="stat-card">
                <div style="font-size:0.85rem; color:var(--text-muted);">Waiting Guests</div>
                <div class="stat-value" id="stat-waiting">0</div>
            </div>
            <div class="stat-card">
                <div style="font-size:0.85rem; color:var(--text-muted);">Now Serving</div>
                <div class="stat-value" id="stat-serving" style="color:var(--accent);">0</div>
            </div>
            <div class="stat-card">
                <div style="font-size:0.85rem; color:var(--text-muted);">Served Today</div>
                <div class="stat-value" id="stat-completed" style="color:#a78bfa;">0</div>
            </div>
            <div class="stat-card">
                <div style="font-size:0.85rem; color:var(--text-muted);">Est. Avg Wait Time</div>
                <div class="stat-value" id="stat-wait-time" style="color:var(--warning);">0 mins</div>
            </div>
        </div>

        <!-- 1. KIOSK & TICKET VIEW -->
        <div id="view-kiosk" class="view-panel active">
            <div class="grid-2">
                <div class="card">
                    <div class="card-title">🎟️ Self-Service Ticket Kiosk</div>
                    <form id="kiosk-form" onsubmit="handleIssueTicket(event)" style="margin-top: 1.25rem;">
                        <div class="input-group">
                            <label>Select Required Service</label>
                            <select id="kiosk-service-select" required></select>
                        </div>
                        <div class="input-group">
                            <label>Customer Name</label>
                            <input type="text" id="kiosk-name" placeholder="e.g. Alex Morgan">
                        </div>
                        <div class="input-group">
                            <label>Phone Number (SMS Notifications)</label>
                            <input type="text" id="kiosk-phone" placeholder="e.g. +1 555 0199">
                        </div>
                        <div class="input-group">
                            <label>Email Address (Digital Ticket)</label>
                            <input type="email" id="kiosk-email" placeholder="e.g. alex@example.com">
                        </div>
                        <div class="input-group" style="display:flex; align-items:center; gap:0.6rem; margin-top:1rem;">
                            <input type="checkbox" id="kiosk-vip" style="width:auto; height:18px; width:18px;">
                            <label for="kiosk-vip" style="margin:0; color:#fbbf24; font-weight:700; cursor:pointer;">
                                ⭐ VIP Priority Access / Senior Guest
                            </label>
                        </div>
                        <button type="submit" class="btn btn-success" style="width: 100%; padding: 1.1rem; margin-top: 1.25rem; font-size:1rem;">
                            🖨️ Dispense Token Ticket
                        </button>
                    </form>
                </div>

                <div class="card">
                    <div class="card-title">🧾 Live Dispense Receipt</div>
                    <div id="kiosk-ticket-result">
                        <div style="color: var(--text-muted); text-align: center; padding: 4rem 2rem;">
                            <div style="font-size:3rem; margin-bottom:1rem;">🎫</div>
                            <p>Select a service on the left and click "Dispense Token Ticket" to view your queue token.</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 2. TV DISPLAY VIEW -->
        <div id="view-display" class="view-panel">
            <div class="card-header" style="margin-bottom:1.5rem;">
                <h2>📺 Main TV Display Board</h2>
                <div style="display:flex; align-items:center; gap:0.5rem; font-size:0.9rem; color:var(--text-muted);">
                    <input type="checkbox" id="voiceToggle" checked style="width:18px; height:18px; cursor:pointer;">
                    <label for="voiceToggle" style="cursor:pointer; color:var(--text-main); font-weight:600;">🔊 Voice Announcements (TTS)</label>
                </div>
            </div>
            <div class="display-grid">
                <div class="now-calling-card">
                    <div style="text-transform: uppercase; letter-spacing: 4px; font-weight: 800; color: var(--text-muted); font-size:1.1rem;">Now Serving</div>
                    <div class="calling-number" id="tv-calling-number">---</div>
                    <div class="calling-counter" id="tv-calling-counter">Please Wait...</div>
                </div>

                <div class="card">
                    <div class="card-title">⏳ Waiting List</div>
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>Token</th>
                                <th>Service</th>
                                <th>Priority</th>
                            </tr>
                        </thead>
                        <tbody id="tv-waiting-table"></tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- 3. COUNTER AGENT VIEW -->
        <div id="view-counter" class="view-panel">
            <div class="card-header">
                <div class="card-title">🎧 Service Counter Workstations</div>
                <button class="btn btn-secondary" onclick="fetchQueueStatus()">🔄 Refresh Status</button>
            </div>
            <div class="counter-grid" id="counter-cards-container"></div>
        </div>

        <!-- 4. DATASET & ANALYTICS HUB -->
        <div id="view-dataset" class="view-panel">
            <!-- DATASET ACTIONS BANNER -->
            <div class="card" style="margin-bottom: 2rem;">
                <div class="card-header">
                    <div>
                        <h2 style="font-size:1.3rem; font-weight:800;">📈 Dataset Engine & Historical Analytics</h2>
                        <p style="font-size:0.85rem; color:var(--text-muted); margin-top:0.3rem;">Manage historical ticket datasets, seed simulated past traffic data, and analyze queue efficiency metrics.</p>
                    </div>
                    <div style="display:flex; gap:0.75rem; flex-wrap:wrap;">
                        <button class="btn btn-primary" onclick="triggerSeedDataset()">⚡ Seed 500+ Sample Dataset</button>
                        <button class="btn btn-success" onclick="exportDataset('csv')">📥 Export CSV Dataset</button>
                        <button class="btn btn-secondary" onclick="exportDataset('json')">📥 Export JSON Dataset</button>
                        <button class="btn btn-danger" onclick="triggerResetDataset()">🗑️ Clear Dataset</button>
                    </div>
                </div>

                <!-- KPI SUMMARY CARDS -->
                <div class="grid-4" style="margin-top:1.5rem;">
                    <div class="stat-card" style="border-color: rgba(99,102,241,0.3);">
                        <div style="font-size:0.8rem; color:var(--text-muted);">Total Dataset Volume</div>
                        <div class="stat-value" id="ds-total-tickets">0</div>
                    </div>
                    <div class="stat-card" style="border-color: rgba(16,185,129,0.3);">
                        <div style="font-size:0.8rem; color:var(--text-muted);">Completion Rate</div>
                        <div class="stat-value" id="ds-completion-rate" style="color:var(--accent);">0%</div>
                    </div>
                    <div class="stat-card" style="border-color: rgba(245,158,11,0.3);">
                        <div style="font-size:0.8rem; color:var(--text-muted);">Avg Handling Duration</div>
                        <div class="stat-value" id="ds-avg-service" style="color:var(--warning);">0m</div>
                    </div>
                    <div class="stat-card" style="border-color: rgba(236,72,153,0.3);">
                        <div style="font-size:0.8rem; color:var(--text-muted);">Customer CSAT Score</div>
                        <div class="stat-value" id="ds-csat-score" style="color:#ec4899;">0 / 5.0</div>
                    </div>
                </div>
            </div>

            <!-- ANALYTICS CHARTS GRID -->
            <div class="grid-2" style="margin-bottom: 2rem;">
                <div class="card">
                    <div class="card-title">📊 Hourly Queue Traffic Distribution</div>
                    <div class="chart-container">
                        <canvas id="chartHourlyTraffic"></canvas>
                    </div>
                </div>

                <div class="card">
                    <div class="card-title">🍩 Service Demand Share</div>
                    <div class="chart-container">
                        <canvas id="chartServiceBreakdown"></canvas>
                    </div>
                </div>

                <div class="card">
                    <div class="card-title">🖥️ Counter Handle Time & Throughput</div>
                    <div class="chart-container">
                        <canvas id="chartCounterPerf"></canvas>
                    </div>
                </div>

                <div class="card">
                    <div class="card-title">⭐ Customer Rating (CSAT) Spread</div>
                    <div class="chart-container">
                        <canvas id="chartCsatSpread"></canvas>
                    </div>
                </div>
            </div>

            <!-- DATASET DATA TABLE -->
            <div class="card">
                <div class="card-header">
                    <div class="card-title">📋 Historical Dataset Records Table</div>
                    <span id="ds-record-count-badge" class="badge badge-waiting">0 Records</span>
                </div>

                <div class="table-controls">
                    <input type="text" id="ds-search-input" placeholder="Search by name, ticket or email..." style="width:280px; background:rgba(255,255,255,0.04); border:1px solid var(--border); padding:0.65rem 1rem; border-radius:10px; color:white;" oninput="loadDatasetRecords(1)">
                    
                    <select id="ds-status-filter" style="width:160px; background:rgba(255,255,255,0.04); border:1px solid var(--border); padding:0.65rem 1rem; border-radius:10px; color:white;" onchange="loadDatasetRecords(1)">
                        <option value="">All Statuses</option>
                        <option value="completed">Completed</option>
                        <option value="waiting">Waiting</option>
                        <option value="no_show">No Show</option>
                        <option value="cancelled">Cancelled</option>
                    </select>

                    <select id="ds-service-filter" style="width:180px; background:rgba(255,255,255,0.04); border:1px solid var(--border); padding:0.65rem 1rem; border-radius:10px; color:white;" onchange="loadDatasetRecords(1)">
                        <option value="">All Services</option>
                    </select>
                </div>

                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Ticket</th>
                            <th>Customer Name</th>
                            <th>Service</th>
                            <th>VIP</th>
                            <th>Status</th>
                            <th>Counter</th>
                            <th>Wait (Mins)</th>
                            <th>Duration</th>
                            <th>Rating</th>
                            <th>Date & Time</th>
                        </tr>
                    </thead>
                    <tbody id="ds-records-table-body"></tbody>
                </table>

                <div class="pagination">
                    <button class="btn btn-secondary" id="btn-prev-page" onclick="changeDatasetPage(-1)">Previous</button>
                    <span id="ds-pagination-info" style="font-size:0.85rem; color:var(--text-muted); padding:0 0.5rem;">Page 1 of 1</span>
                    <button class="btn btn-secondary" id="btn-next-page" onclick="changeDatasetPage(1)">Next</button>
                </div>
            </div>
        </div>

        <!-- 5. ADMIN PANEL -->
        <div id="view-admin" class="view-panel">
            <div class="grid-2">
                <div class="card">
                    <div class="card-title">🛠️ Service Categories Config</div>
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>Code</th>
                                <th>Service Name</th>
                                <th>Prefix</th>
                                <th>Avg Handling Time</th>
                            </tr>
                        </thead>
                        <tbody id="admin-services-table"></tbody>
                    </table>
                </div>

                <div class="card">
                    <div class="card-title">🖥️ Counter Workstations Config</div>
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>Counter</th>
                                <th>Staff Agent</th>
                                <th>Status</th>
                                <th>Active Ticket</th>
                            </tr>
                        </thead>
                        <tbody id="admin-counters-table"></tbody>
                    </table>
                </div>
            </div>
        </div>

    </div>

    <script>
        let lastCalledTicketId = null;
        let dsCurrentPage = 1;
        let chartHourly, chartService, chartCounter, chartCsat;

        function switchTab(tabId, event) {
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            document.querySelectorAll('.view-panel').forEach(panel => panel.classList.remove('active'));

            if(event && event.target) {
                event.target.classList.add('active');
            }
            document.getElementById('view-' + tabId).classList.add('active');

            if(tabId === 'dataset') {
                loadDatasetAnalytics();
                loadDatasetRecords(1);
            }
        }

        async function loadServices() {
            try {
                const res = await fetch('/api/services');
                const data = await res.json();
                if(data.success) {
                    const select = document.getElementById('kiosk-service-select');
                    select.innerHTML = data.services.map(s => 
                        `<option value="${s.id}">${s.name} (${s.prefix}) - Avg ${s.avg_time_mins} min</option>`
                    ).join('');

                    const dsFilter = document.getElementById('ds-service-filter');
                    dsFilter.innerHTML = '<option value="">All Services</option>' + data.services.map(s => 
                        `<option value="${s.id}">${s.name}</option>`
                    ).join('');

                    const adminTable = document.getElementById('admin-services-table');
                    adminTable.innerHTML = data.services.map(s => `
                        <tr>
                            <td><span class="badge" style="background:${s.color}22; color:${s.color}; border:1px solid ${s.color};">${s.code}</span></td>
                            <td>${s.name}</td>
                            <td><strong>${s.prefix}</strong></td>
                            <td>${s.avg_time_mins} mins</td>
                        </tr>
                    `).join('');
                }
            } catch(e) { console.error(e); }
        }

        async function handleIssueTicket(e) {
            e.preventDefault();
            const service_id = document.getElementById('kiosk-service-select').value;
            const customer_name = document.getElementById('kiosk-name').value;
            const customer_phone = document.getElementById('kiosk-phone').value;
            const customer_email = document.getElementById('kiosk-email').value;
            const is_vip = document.getElementById('kiosk-vip').checked;

            try {
                const res = await fetch('/api/ticket/issue', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ service_id, customer_name, customer_phone, customer_email, is_vip })
                });
                const data = await res.json();
                if(data.success) {
                    const t = data.ticket;
                    document.getElementById('kiosk-ticket-result').innerHTML = `
                        <div class="ticket-receipt">
                            <div style="font-size:0.85rem; color:var(--text-muted); text-transform:uppercase;">Your Queue Token</div>
                            <div class="ticket-number-display">${t.ticket_number}</div>
                            <div style="margin-bottom:1rem; font-weight:600;">Guest: ${t.customer_name} ${t.is_vip ? '<span class="badge badge-vip">VIP</span>' : ''}</div>
                            <div style="background:rgba(255,255,255,0.05); padding:1rem; border-radius:12px; display:flex; justify-content:space-around;">
                                <div><div style="font-size:0.75rem; color:var(--text-muted);">Ahead in Queue</div><strong>${t.position_ahead} guests</strong></div>
                                <div><div style="font-size:0.75rem; color:var(--text-muted);">Est. Wait Time</div><strong>~${t.est_wait_mins} mins</strong></div>
                            </div>
                        </div>
                    `;
                    fetchQueueStatus();
                }
            } catch(err) { alert('Error issuing ticket'); }
        }

        async function callNext(counterId) {
            try {
                const res = await fetch('/api/counter/call_next', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ counter_id: counterId })
                });
                const data = await res.json();
                if(data.success) {
                    fetchQueueStatus();
                }
            } catch(e) { console.error(e); }
        }

        async function updateStatus(counterId, status) {
            try {
                await fetch('/api/counter/update_status', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ counter_id: counterId, status: status })
                });
                fetchQueueStatus();
            } catch(e) { console.error(e); }
        }

        function speakTicketCall(ticketNum, counterName) {
            if (!document.getElementById('voiceToggle').checked) return;
            if ('speechSynthesis' in window) {
                const text = `Ticket number ${ticketNum.split('').join(' ')}, please proceed to ${counterName}`;
                const utterance = new SpeechSynthesisUtterance(text);
                utterance.rate = 0.9;
                window.speechSynthesis.speak(utterance);
            }
        }

        async function fetchQueueStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                if(!data.success) return;

                document.getElementById('stat-waiting').innerText = data.stats.waiting_count;
                document.getElementById('stat-serving').innerText = data.stats.serving_count;
                document.getElementById('stat-completed').innerText = data.stats.completed_count;
                document.getElementById('stat-wait-time').innerText = data.stats.est_wait_mins + ' mins';

                if (data.active_tickets.length > 0) {
                    const topTicket = data.active_tickets[0];
                    document.getElementById('tv-calling-number').innerText = topTicket.ticket_number;
                    document.getElementById('tv-calling-counter').innerText = topTicket.counter_name;

                    if (lastCalledTicketId !== topTicket.id) {
                        lastCalledTicketId = topTicket.id;
                        speakTicketCall(topTicket.ticket_number, topTicket.counter_name);
                    }
                } else {
                    document.getElementById('tv-calling-number').innerText = '---';
                    document.getElementById('tv-calling-counter').innerText = 'Counters Available';
                }

                const tvWaiting = document.getElementById('tv-waiting-table');
                tvWaiting.innerHTML = data.waiting_tickets.slice(0, 7).map(t => `
                    <tr>
                        <td><strong>${t.ticket_number}</strong></td>
                        <td>${t.service_name}</td>
                        <td>${t.is_vip ? '<span class="badge badge-vip">VIP</span>' : '<span class="badge badge-waiting">Standard</span>'}</td>
                    </tr>
                `).join('') || '<tr><td colspan="3" style="text-align:center; color:var(--text-muted);">Queue is empty</td></tr>';

                const counterCards = document.getElementById('counter-cards-container');
                counterCards.innerHTML = data.counters.map(c => `
                    <div class="counter-card">
                        <div>
                            <div class="card-header" style="margin-bottom:0.75rem;">
                                <h3>${c.name}</h3>
                                <span class="badge ${c.status === 'busy' ? 'badge-vip' : 'badge-active'}">${c.status.toUpperCase()}</span>
                            </div>
                            <div style="font-size:0.85rem; color:var(--text-muted); margin-bottom:1rem;">Agent: <strong>${c.staff_name}</strong></div>
                            
                            <div style="background:rgba(255,255,255,0.04); padding:1rem; border-radius:14px; text-align:center; margin-bottom:1rem;">
                                <div style="font-size:0.75rem; color:var(--text-muted);">CURRENT TICKET</div>
                                <div style="font-size:2.4rem; font-weight:800; color:#818cf8;">${c.current_ticket_number || 'NONE'}</div>
                            </div>
                        </div>

                        <div style="display:flex; flex-direction:column; gap:0.5rem;">
                            <button class="btn btn-warning" onclick="callNext(${c.id})">📢 Call Next Ticket</button>
                            <div style="display:flex; gap:0.5rem;">
                                <button class="btn btn-success" style="flex:1;" onclick="updateStatus(${c.id}, 'completed')">Done</button>
                                <button class="btn btn-danger" style="flex:1;" onclick="updateStatus(${c.id}, 'no_show')">No Show</button>
                            </div>
                        </div>
                    </div>
                `).join('');

                const adminCounters = document.getElementById('admin-counters-table');
                adminCounters.innerHTML = data.counters.map(c => `
                    <tr>
                        <td><strong>${c.name}</strong></td>
                        <td>${c.staff_name}</td>
                        <td><span class="badge ${c.status === 'busy' ? 'badge-vip' : 'badge-active'}">${c.status}</span></td>
                        <td><strong>${c.current_ticket_number || '-'}</strong></td>
                    </tr>
                `).join('');

            } catch(e) { console.error(e); }
        }

        // --- DATASET & CHARTS FUNCTIONS ---

        async function triggerSeedDataset() {
            try {
                const res = await fetch('/api/dataset/seed', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ count: 500 })
                });
                const data = await res.json();
                if(data.success) {
                    alert(data.message);
                    loadDatasetAnalytics();
                    loadDatasetRecords(1);
                    fetchQueueStatus();
                }
            } catch(e) { alert('Error seeding dataset'); }
        }

        async function triggerResetDataset() {
            if(!confirm('Are you sure you want to clear all historical dataset records?')) return;
            try {
                const res = await fetch('/api/dataset/reset', { method: 'POST' });
                const data = await res.json();
                if(data.success) {
                    alert(data.message);
                    loadDatasetAnalytics();
                    loadDatasetRecords(1);
                    fetchQueueStatus();
                }
            } catch(e) { alert('Error resetting dataset'); }
        }

        function exportDataset(format) {
            window.location.href = '/api/dataset/export?format=' + format;
        }

        async function loadDatasetAnalytics() {
            try {
                const res = await fetch('/api/dataset/stats');
                const data = await res.json();
                if(!data.success) return;

                const s = data.summary;
                document.getElementById('ds-total-tickets').innerText = s.total_tickets;
                const compRate = s.total_tickets > 0 ? ((s.completed_tickets / s.total_tickets) * 100).toFixed(1) : 0;
                document.getElementById('ds-completion-rate').innerText = compRate + '%';
                document.getElementById('ds-avg-service').innerText = s.avg_service_mins + ' mins';
                document.getElementById('ds-csat-score').innerText = s.csat_score + ' / 5.0';

                renderHourlyChart(data.hourly_traffic);
                renderServiceChart(data.service_breakdown);
                renderCounterChart(data.counter_perf);
                renderCsatChart(data.rating_breakdown);

            } catch(e) { console.error(e); }
        }

        function renderHourlyChart(hourlyData) {
            const ctx = document.getElementById('chartHourlyTraffic').getContext('2d');
            if(chartHourly) chartHourly.destroy();
            chartHourly = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: hourlyData.map(d => d.hour),
                    datasets: [{
                        label: 'Ticket Traffic',
                        data: hourlyData.map(d => d.count),
                        backgroundColor: 'rgba(99, 102, 241, 0.7)',
                        borderColor: '#6366f1',
                        borderWidth: 1,
                        borderRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' } },
                        y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' } }
                    }
                }
            });
        }

        function renderServiceChart(serviceData) {
            const ctx = document.getElementById('chartServiceBreakdown').getContext('2d');
            if(chartService) chartService.destroy();
            chartService = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: serviceData.map(s => s.name),
                    datasets: [{
                        data: serviceData.map(s => s.count),
                        backgroundColor: serviceData.map(s => s.color || '#3b82f6'),
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { position: 'bottom', labels: { color: '#f8fafc' } } }
                }
            });
        }

        function renderCounterChart(counterData) {
            const ctx = document.getElementById('chartCounterPerf').getContext('2d');
            if(chartCounter) chartCounter.destroy();
            chartCounter = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: counterData.map(c => c.counter_name),
                    datasets: [
                        {
                            label: 'Handled Tickets',
                            data: counterData.map(c => c.tickets_handled),
                            backgroundColor: 'rgba(16, 185, 129, 0.7)',
                            borderColor: '#10b981',
                            borderWidth: 1,
                            borderRadius: 6
                        },
                        {
                            label: 'Avg Handle Time (Mins)',
                            data: counterData.map(c => c.avg_handle_time),
                            backgroundColor: 'rgba(245, 158, 11, 0.7)',
                            borderColor: '#f59e0b',
                            borderWidth: 1,
                            borderRadius: 6
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { labels: { color: '#f8fafc' } } },
                    scales: {
                        x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' } },
                        y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' } }
                    }
                }
            });
        }

        function renderCsatChart(ratingData) {
            const ctx = document.getElementById('chartCsatSpread').getContext('2d');
            if(chartCsat) chartCsat.destroy();
            chartCsat = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: ratingData.map(r => r.stars + ' ⭐'),
                    datasets: [{
                        label: 'Rating Count',
                        data: ratingData.map(r => r.count),
                        backgroundColor: '#ec4899',
                        borderRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' } },
                        y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' } }
                    }
                }
            });
        }

        async function loadDatasetRecords(page = 1) {
            dsCurrentPage = page;
            const search = document.getElementById('ds-search-input').value;
            const status = document.getElementById('ds-status-filter').value;
            const service_id = document.getElementById('ds-service-filter').value;

            try {
                const res = await fetch(`/api/dataset/records?page=${page}&limit=12&search=${encodeURIComponent(search)}&status=${encodeURIComponent(status)}&service_id=${encodeURIComponent(service_id)}`);
                const data = await res.json();
                if(!data.success) return;

                document.getElementById('ds-record-count-badge').innerText = data.total + ' Records';
                document.getElementById('ds-pagination-info').innerText = `Page ${data.page} of ${data.total_pages}`;
                
                document.getElementById('btn-prev-page').disabled = data.page <= 1;
                document.getElementById('btn-next-page').disabled = data.page >= data.total_pages;

                const tbody = document.getElementById('ds-records-table-body');
                tbody.innerHTML = data.records.map(r => `
                    <tr>
                        <td><strong>${r.ticket_number}</strong></td>
                        <td>${r.customer_name}</td>
                        <td><span class="badge" style="background:${r.service_color}22; color:${r.service_color};">${r.service_name}</span></td>
                        <td>${r.is_vip ? '<span class="badge badge-vip">VIP</span>' : 'Standard'}</td>
                        <td><span class="badge ${r.status === 'completed' ? 'badge-active' : (r.status === 'no_show' ? 'badge-noshow' : 'badge-waiting')}">${r.status}</span></td>
                        <td>${r.counter_name || '-'}</td>
                        <td>${r.wait_time_mins || 0}m</td>
                        <td>${r.service_time_mins || 0}m</td>
                        <td>${r.rating ? r.rating + ' ⭐' : '-'}</td>
                        <td><span style="font-size:0.8rem; color:var(--text-muted);">${r.created_at}</span></td>
                    </tr>
                `).join('') || '<tr><td colspan="10" style="text-align:center; color:var(--text-muted);">No dataset records found</td></tr>';

            } catch(e) { console.error(e); }
        }

        function changeDatasetPage(delta) {
            loadDatasetRecords(dsCurrentPage + delta);
        }

        window.onload = function() {
            loadServices();
            fetchQueueStatus();
            setInterval(fetchQueueStatus, 3000);
        };
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Smart Queue Management Backend Server on http://127.0.0.1:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)
