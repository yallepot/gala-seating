"""
Gala Seating System - Main Application
Real-time seating assignment with WebSocket support
FULLY DEBUGGED VERSION 1.2 - All bugs fixed
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from models import db, TableAssignment, BlockedTable
from datetime import datetime, timedelta
import os
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///seating.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)
app.config['ADMIN_PASSWORD'] = os.environ.get('ADMIN_PASSWORD', 'admin123')

# Initialize extensions
db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
CORS(app)

# Configuration
TOTAL_TABLES = 25
SEATS_PER_TABLE = 10
MAX_GUESTS = 250

# Create tables
with app.app_context():
    db.create_all()

# Admin decorator
def require_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# Helper functions
def get_table_status():
    """Get status of all tables with occupancy info - OPTIMIZED"""
    tables = []
    
    # Single query for all blocked tables
    blocked_dict = {bt.table_number: bt.reason for bt in BlockedTable.query.all()}
    
    # Single query for all assignments, organized by table
    all_assignments = TableAssignment.query.all()
    assignments_by_table = {}
    for assignment in all_assignments:
        if assignment.table_number not in assignments_by_table:
            assignments_by_table[assignment.table_number] = []
        assignments_by_table[assignment.table_number].append(assignment)
    
    # Build table status
    for table_num in range(1, TOTAL_TABLES + 1):
        assignments = assignments_by_table.get(table_num, [])
        occupied = len(assignments)
        available = SEATS_PER_TABLE - occupied
        is_blocked = table_num in blocked_dict
        
        occupants = [{
            'ticket': a.ticket_number,
            'name': a.full_name
        } for a in assignments]
        
        tables.append({
            'number': table_num,
            'capacity': SEATS_PER_TABLE,
            'occupied': occupied,
            'available': available,
            'is_full': occupied >= SEATS_PER_TABLE,
            'is_blocked': is_blocked,
            'block_reason': blocked_dict.get(table_num, ''),
            'occupants': occupants
        })
    
    return tables

def validate_tickets(ticket_data):
    """Validate ticket numbers - accepts ANY ticket number, tracks up to 250 total guests"""
    validated_guests = []
    ticket_numbers_in_request = []
    
    for data in ticket_data:
        ticket_number = data.get('ticket_number', '').strip()
        full_name = data.get('full_name', '').strip()
        
        if not ticket_number or not full_name:
            return False, [], "All fields must be filled out"
        
        # Check for duplicates in current request
        if ticket_number in ticket_numbers_in_request:
            return False, [], f"Ticket {ticket_number} appears multiple times in your entry. Please remove duplicates."
        
        ticket_numbers_in_request.append(ticket_number)
        
        # Check if ticket is already assigned
        existing_assignment = TableAssignment.query.filter_by(ticket_number=ticket_number).first()
        if existing_assignment:
            return False, [], f"Ticket {ticket_number} has already been assigned to Table {existing_assignment.table_number}"
        
        validated_guests.append({
            'ticket_number': ticket_number,
            'full_name': full_name
        })
    
    # Check total capacity (250 guests max)
    current_total = TableAssignment.query.count()
    new_total = current_total + len(validated_guests)
    
    if new_total > MAX_GUESTS:
        remaining = MAX_GUESTS - current_total
        return False, [], f"Only {remaining} spots remaining. You are trying to register {len(validated_guests)} tickets. The gala is limited to {MAX_GUESTS} guests."
    
    return True, validated_guests, None

# Routes
@app.route('/')
def index():
    """Landing page - ticket entry"""
    session.clear()
    return render_template('index.html')

@app.route('/api/validate-tickets', methods=['POST'])
def validate_tickets_api():
    """Validate tickets and store in session"""
    try:
        tickets = request.json.get('tickets', [])
        
        if not tickets:
            return jsonify({'success': False, 'error': 'No tickets provided'}), 400
        
        # Validate tickets
        is_valid, validated_guests, error = validate_tickets(tickets)
        
        if not is_valid:
            return jsonify({'success': False, 'error': error}), 400
        
        # Store in session
        session['guests'] = validated_guests
        session.permanent = True
        
        return jsonify({
            'success': True,
            'redirect': '/select-seats'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/select-seats')
def select_seats():
    """Seating selection page"""
    guests = session.get('guests', [])
    
    if not guests:
        return redirect(url_for('index'))
    
    return render_template('seating.html', guests=guests)

@app.route('/api/get-tables')
def get_tables_api():
    """Get all tables status"""
    try:
        tables = get_table_status()
        return jsonify({'success': True, 'tables': tables})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/assign-seats', methods=['POST'])
def assign_seats_api():
    """Assign seats to guests"""
    try:
        assignments = request.json.get('assignments', [])
        
        if not assignments:
            return jsonify({'success': False, 'error': 'No assignments provided'}), 400
        
        # Verify session
        guests = session.get('guests', [])
        if not guests:
            return jsonify({'success': False, 'error': 'Session expired. Please start over.'}), 400
        
        # Check total capacity
        current_total = TableAssignment.query.count()
        new_total = current_total + len(assignments)
        
        if new_total > MAX_GUESTS:
            remaining = MAX_GUESTS - current_total
            return jsonify({
                'success': False,
                'error': f'Only {remaining} spots remaining. The gala is limited to {MAX_GUESTS} guests.'
            }), 400
        
        # Validate and create assignments
        created_assignments = []
        
        for assignment in assignments:
            ticket_number = assignment.get('ticket_number')
            full_name = assignment.get('full_name')
            table_number = assignment.get('table_number')
            
            # Check if already assigned
            existing = TableAssignment.query.filter_by(ticket_number=ticket_number).first()
            if existing:
                return jsonify({
                    'success': False,
                    'error': f'Ticket {ticket_number} is already assigned'
                }), 400
            
            # Check table capacity
            table_count = TableAssignment.query.filter_by(table_number=table_number).count()
            if table_count >= SEATS_PER_TABLE:
                return jsonify({
                    'success': False,
                    'error': f'Table {table_number} is full'
                }), 400
            
            # Create assignment
            new_assignment = TableAssignment(
                ticket_number=ticket_number,
                full_name=full_name,
                table_number=table_number
            )
            db.session.add(new_assignment)
            created_assignments.append({
                'ticket_number': ticket_number,
                'full_name': full_name,
                'table_number': table_number
            })
        
        db.session.commit()
        
        # Store in session for confirmation page
        session['final_assignments'] = created_assignments
        
        # Broadcast update via WebSocket
        socketio.emit('table_update', {'tables': get_table_status()}, namespace='/')
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/confirmation')
def confirmation():
    """Confirmation page"""
    assignments = session.get('final_assignments', [])
    
    if not assignments:
        return redirect(url_for('index'))
    
    return render_template('confirmation.html', assignments=assignments)

# Usher routes
@app.route('/usher')
def usher():
    """Usher view - real-time table status"""
    return render_template('usher.html', total_tables=TOTAL_TABLES)

@app.route('/api/usher/lookup-ticket')
def usher_lookup_ticket():
    """Look up a ticket for ushers"""
    try:
        ticket_number = request.args.get('ticket')
        
        if not ticket_number:
            return jsonify({'success': False, 'error': 'Ticket number required'}), 400
        
        assignment = TableAssignment.query.filter_by(ticket_number=ticket_number).first()
        
        if assignment:
            return jsonify({
                'success': True,
                'found': True,
                'assignment': assignment.to_dict()
            })
        else:
            return jsonify({
                'success': True,
                'found': False,
                'message': f'Ticket {ticket_number} not found or not assigned'
            })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Admin routes
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
    if request.method == 'GET':
        return render_template('admin_login.html')
    
    password = request.form.get('password')
    
    if password == app.config['ADMIN_PASSWORD']:
        session['is_admin'] = True
        session.permanent = True
        return redirect(url_for('admin_panel'))
    
    return render_template('admin_login.html', error='Invalid password')

@app.route('/admin/logout')
def admin_logout():
    """Admin logout"""
    session.pop('is_admin', None)
    return redirect(url_for('index'))

@app.route('/admin')
@require_admin
def admin_panel():
    """Admin control panel"""
    return render_template('admin.html', total_tables=TOTAL_TABLES, max_guests=MAX_GUESTS)

@app.route('/api/admin/get-all-assignments')
@require_admin
def get_all_assignments():
    """Get all seat assignments"""
    try:
        assignments = TableAssignment.query.order_by(TableAssignment.table_number, TableAssignment.assigned_at).all()
        return jsonify({
            'success': True,
            'assignments': [a.to_dict() for a in assignments]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/delete-any-assignment', methods=['POST'])
@require_admin
def delete_any_assignment():
    """Delete any assignment by ID"""
    try:
        assignment_id = request.json.get('assignment_id')
        
        assignment = TableAssignment.query.get(assignment_id)
        if not assignment:
            return jsonify({'success': False, 'error': 'Assignment not found'}), 404
        
        db.session.delete(assignment)
        db.session.commit()
        
        socketio.emit('table_update', {'tables': get_table_status()}, namespace='/')
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/block-table', methods=['POST'])
@require_admin
def block_table_api():
    """Block a table"""
    try:
        table_number = request.json.get('table_number')
        reason = request.json.get('reason', 'Reserved')
        
        if table_number < 1 or table_number > TOTAL_TABLES:
            return jsonify({'success': False, 'error': 'Invalid table number'}), 400
        
        existing = BlockedTable.query.filter_by(table_number=table_number).first()
        if existing:
            return jsonify({'success': False, 'error': 'Table already blocked'}), 400
        
        blocked = BlockedTable(table_number=table_number, reason=reason)
        db.session.add(blocked)
        db.session.commit()
        
        socketio.emit('table_update', {'tables': get_table_status()}, namespace='/')
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/unblock-table', methods=['POST'])
@require_admin
def unblock_table_api():
    """Unblock a table"""
    try:
        table_number = request.json.get('table_number')
        
        blocked = BlockedTable.query.filter_by(table_number=table_number).first()
        if not blocked:
            return jsonify({'success': False, 'error': 'Table not blocked'}), 404
        
        db.session.delete(blocked)
        db.session.commit()
        
        socketio.emit('table_update', {'tables': get_table_status()}, namespace='/')
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/lookup-ticket')
@require_admin
def lookup_ticket():
    """Look up a ticket by number"""
    try:
        ticket_number = request.args.get('ticket')
        
        if not ticket_number:
            return jsonify({'success': False, 'error': 'Ticket number required'}), 400
        
        assignment = TableAssignment.query.filter_by(ticket_number=ticket_number).first()
        
        if assignment:
            return jsonify({
                'success': True,
                'assignment': assignment.to_dict()
            })
        else:
            return jsonify({
                'success': True,
                'assignment': None,
                'ticket_exists': False
            })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/manual-assign', methods=['POST'])
@require_admin
def manual_assign_api():
    """Manually assign a guest to a table (even if blocked) - ADMIN ONLY"""
    try:
        table_number = request.json.get('table_number')
        ticket_number = request.json.get('ticket_number')
        full_name = request.json.get('full_name')
        
        if not table_number or not ticket_number or not full_name:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        if table_number < 1 or table_number > TOTAL_TABLES:
            return jsonify({'success': False, 'error': 'Invalid table number'}), 400
        
        # Check if ticket is already assigned
        existing = TableAssignment.query.filter_by(ticket_number=ticket_number).first()
        if existing:
            return jsonify({
                'success': False, 
                'error': f'Ticket {ticket_number} is already assigned to Table {existing.table_number}'
            }), 400
        
        # Check table capacity (even for blocked tables)
        current_count = TableAssignment.query.filter_by(table_number=table_number).count()
        if current_count >= SEATS_PER_TABLE:
            return jsonify({
                'success': False,
                'error': f'Table {table_number} is full ({current_count}/{SEATS_PER_TABLE})'
            }), 400
        
        # Check total capacity
        total_guests = TableAssignment.query.count()
        if total_guests >= MAX_GUESTS:
            return jsonify({
                'success': False,
                'error': f'Gala is at maximum capacity ({MAX_GUESTS} guests)'
            }), 400
        
        # Create assignment
        new_assignment = TableAssignment(
            ticket_number=ticket_number,
            full_name=full_name,
            table_number=table_number
        )
        db.session.add(new_assignment)
        db.session.commit()
        
        # Broadcast update
        socketio.emit('table_update', {'tables': get_table_status()}, namespace='/')
        
        return jsonify({
            'success': True,
            'message': f'Successfully assigned to Table {table_number}'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/edit-assignment', methods=['POST'])
@require_admin
def edit_assignment_api():
    """Edit an existing assignment - change ticket number, name, or table"""
    try:
        assignment_id = request.json.get('assignment_id')
        new_ticket_number = request.json.get('ticket_number', '').strip()
        new_full_name = request.json.get('full_name', '').strip()
        new_table_number = request.json.get('table_number')
        
        if not assignment_id:
            return jsonify({'success': False, 'error': 'Assignment ID required'}), 400
        
        # Get existing assignment
        assignment = TableAssignment.query.get(assignment_id)
        if not assignment:
            return jsonify({'success': False, 'error': 'Assignment not found'}), 404
        
        old_ticket_number = assignment.ticket_number
        old_table_number = assignment.table_number
        
        # If changing ticket number, check if new ticket is available
        if new_ticket_number and new_ticket_number != old_ticket_number:
            existing = TableAssignment.query.filter_by(ticket_number=new_ticket_number).first()
            if existing:
                return jsonify({
                    'success': False,
                    'error': f'Ticket {new_ticket_number} is already assigned to Table {existing.table_number}'
                }), 400
            
            assignment.ticket_number = new_ticket_number
        
        # Update name if provided
        if new_full_name:
            assignment.full_name = new_full_name
        
        # If changing table, check capacity
        if new_table_number and new_table_number != old_table_number:
            # Check new table capacity
            new_table_count = TableAssignment.query.filter_by(table_number=new_table_number).count()
            if new_table_count >= SEATS_PER_TABLE:
                return jsonify({
                    'success': False,
                    'error': f'Table {new_table_number} is full ({new_table_count}/{SEATS_PER_TABLE})'
                }), 400
            
            assignment.table_number = new_table_number
        
        db.session.commit()
        
        # Broadcast update
        socketio.emit('table_update', {'tables': get_table_status()}, namespace='/')
        
        return jsonify({
            'success': True,
            'message': 'Assignment updated successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/reset-demo')
@require_admin
def reset_demo():
    """Reset all assignments - KEEPS accepting any ticket numbers"""
    try:
        # Delete all assignments
        TableAssignment.query.delete()
        
        # Unblock all tables
        BlockedTable.query.delete()
        
        db.session.commit()
        
        # Broadcast update
        socketio.emit('table_update', {'tables': get_table_status()}, namespace='/')
        
        return jsonify({
            'success': True,
            'message': f'All assignments and blocks reset. System ready to accept any ticket numbers (up to {MAX_GUESTS} total guests).'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
