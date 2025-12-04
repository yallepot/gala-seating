"""
Gala Seating System - Main Application
Real-time seating assignment with WebSocket support
FULLY DEBUGGED VERSION 1.2 - All bugs fixed
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit
from datetime import datetime
from functools import wraps
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///gala_seating.db')
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['ADMIN_PASSWORD'] = os.environ.get('ADMIN_PASSWORD', 'admin123')

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Configuration
TOTAL_TABLES = 25
SEATS_PER_TABLE = 10
TOTAL_TICKETS = 250  # Total number of tickets (but not sequential!)

# ==================== MODELS ====================

class Ticket(db.Model):
    """Represents a valid ticket - NON-SEQUENTIAL numeric ticket numbers"""
    id = db.index = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(200), nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    used_at = db.Column(db.DateTime, nullable=True)
    
    def __repr__(self):
        return f'<Ticket {self.ticket_number}>'

class TableAssignment(db.Model):
    """Tracks which ticket is assigned to which table"""
    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(200), nullable=False)
    table_number = db.Column(db.Integer, nullable=False, index=True)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Assignment Ticket:{self.ticket_number} Table:{self.table_number}>'

class BlockedTable(db.Model):
    """Tracks which tables are blocked by admin"""
    id = db.Column(db.Integer, primary_key=True)
    table_number = db.Column(db.Integer, unique=True, nullable=False)
    reason = db.Column(db.String(200), nullable=True)
    blocked_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<BlockedTable {self.table_number}>'

# ==================== ADMIN DECORATOR ====================

def require_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            return jsonify({'success': False, 'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function

# ==================== HELPER FUNCTIONS ====================

def get_table_status():
    """Get current status of all tables"""
    blocked_tables = {bt.table_number: bt.reason for bt in BlockedTable.query.all()}
    
    tables = []
    for table_num in range(1, TOTAL_TABLES + 1):
        assignments = TableAssignment.query.filter_by(table_number=table_num).all()
        occupied = len(assignments)
        
        is_blocked = table_num in blocked_tables
        
        occupants = [{
            'ticket': a.ticket_number,
            'name': a.full_name
        } for a in assignments]
        
        tables.append({
            'number': table_num,
            'capacity': SEATS_PER_TABLE,
            'occupied': occupied,
            'available': SEATS_PER_TABLE - occupied,
            'is_full': occupied >= SEATS_PER_TABLE,
            'is_blocked': is_blocked,
            'block_reason': blocked_tables.get(table_num, ''),
            'occupants': occupants
        })
    
    return tables

def validate_tickets(ticket_data):
    """Validate ticket numbers and check availability - INCLUDES DUPLICATE CHECK"""
    validated_guests = []
    ticket_numbers_in_request = []
    
    for data in ticket_data:
        ticket_number = data.get('ticket_number', '').strip()
        full_name = data.get('full_name', '').strip()
        
        if not ticket_number or not full_name:
            return False, [], "All fields must be filled out"
        
        # Validate ticket number is numeric only
        if not ticket_number.isdigit():
            return False, [], f"Ticket {ticket_number} is invalid. Ticket numbers must be numbers only (no letters or special characters)."
        
        # Check for duplicates in current request
        if ticket_number in ticket_numbers_in_request:
            return False, [], f"Ticket {ticket_number} appears multiple times in your entry. Please remove duplicates."
        
        ticket_numbers_in_request.append(ticket_number)
        
        # Check if ticket exists in database
        ticket = Ticket.query.filter_by(ticket_number=ticket_number).first()
        
        if not ticket:
            return False, [], f"Ticket {ticket_number} is invalid or does not exist in our system"
        
        # Check if ticket is already used/assigned
        if ticket.is_used:
            assignment = TableAssignment.query.filter_by(ticket_number=ticket_number).first()
            if assignment:
                return False, [], f"Ticket {ticket_number} has already been assigned to Table {assignment.table_number}"
            else:
                return False, [], f"Ticket {ticket_number} has already been used"
        
        validated_guests.append({
            'ticket_number': ticket_number,
            'full_name': full_name,
            'original_name': ticket.full_name
        })
    
    return True, validated_guests, None

# ==================== ROUTES ====================

@app.route('/')
def index():
    """Landing page for ticket entry"""
    return render_template('index.html')

@app.route('/api/validate-tickets', methods=['POST'])
def validate_tickets_api():
    """Validate ticket numbers before showing seating page"""
    try:
        tickets = request.json.get('tickets', [])
        
        if not tickets:
            return jsonify({'success': False, 'error': 'No tickets provided'}), 400
        
        is_valid, validated_guests, error_msg = validate_tickets(tickets)
        
        if not is_valid:
            return jsonify({'success': False, 'error': error_msg}), 400
        
        # Store validated guests in session
        session['validated_guests'] = validated_guests
        session['session_id'] = datetime.utcnow().isoformat()
        
        return jsonify({
            'success': True,
            'redirect': url_for('seating')
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/seating')
def seating():
    """Seating selection page"""
    guests = session.get('validated_guests', [])
    
    if not guests:
        return redirect(url_for('index'))
    
    return render_template('seating.html', guests=guests)

@app.route('/api/get-tables')
def get_tables_api():
    """Get current table status"""
    try:
        tables = get_table_status()
        return jsonify({'success': True, 'tables': tables})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/assign-seats', methods=['POST'])
def assign_seats():
    """Assign validated guests to tables"""
    try:
        assignments = request.json.get('assignments', [])
        validated_guests = session.get('validated_guests', [])
        
        if not validated_guests:
            return jsonify({'success': False, 'error': 'Session expired. Please start over.'}), 400
        
        # Validate all assignments
        for assignment in assignments:
            ticket_number = assignment['ticket_number']
            table_number = assignment['table_number']
            
            # Check if ticket is in validated session
            if not any(g['ticket_number'] == ticket_number for g in validated_guests):
                return jsonify({'success': False, 'error': f'Ticket {ticket_number} not in your session'}), 400
            
            # Check table capacity
            current_count = TableAssignment.query.filter_by(table_number=table_number).count()
            if current_count >= SEATS_PER_TABLE:
                return jsonify({'success': False, 'error': f'Table {table_number} is full'}), 400
            
            # Check if table is blocked
            blocked = BlockedTable.query.filter_by(table_number=table_number).first()
            if blocked:
                return jsonify({'success': False, 'error': f'Table {table_number} is blocked'}), 400
        
        # All validated, create assignments
        for assignment in assignments:
            new_assignment = TableAssignment(
                ticket_number=assignment['ticket_number'],
                full_name=assignment['full_name'],
                table_number=assignment['table_number']
            )
            db.session.add(new_assignment)
            
            # Mark ticket as used
            ticket = Ticket.query.filter_by(ticket_number=assignment['ticket_number']).first()
            if ticket:
                ticket.is_used = True
                ticket.used_at = datetime.utcnow()
        
        db.session.commit()
        
        # Clear session
        session.pop('validated_guests', None)
        
        # Broadcast update via WebSocket
        socketio.emit('table_update', {'tables': get_table_status()}, namespace='/')
        
        # Store assignments for confirmation page
        session['final_assignments'] = assignments
        
        return jsonify({'success': True, 'message': 'Seats assigned successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/confirmation')
def confirmation():
    """Confirmation page after seat assignment"""
    assignments = session.get('final_assignments', [])
    
    if not assignments:
        return redirect(url_for('index'))
    
    return render_template('confirmation.html', assignments=assignments)

# ==================== ADMIN ROUTES ====================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
    if request.method == 'POST':
        password = request.form.get('password')
        
        if password == app.config['ADMIN_PASSWORD']:
            session['is_admin'] = True
            return redirect(url_for('admin_panel'))
        else:
            return render_template('admin_login.html', error='Invalid password')
    
    return render_template('admin_login.html')

@app.route('/admin')
@require_admin
def admin_panel():
    """Admin control panel"""
    return render_template('admin.html', total_tables=TOTAL_TABLES)

@app.route('/admin/logout')
def admin_logout():
    """Admin logout"""
    session.pop('is_admin', None)
    return redirect(url_for('index'))

@app.route('/api/admin/get-all-assignments')
@require_admin
def get_all_assignments():
    """Get all seat assignments"""
    try:
        assignments = TableAssignment.query.order_by(TableAssignment.table_number, TableAssignment.assigned_at).all()
        
        assignments_data = [{
            'id': a.id,
            'ticket_number': a.ticket_number,
            'full_name': a.full_name,
            'table_number': a.table_number,
            'assigned_at': a.assigned_at.isoformat()
        } for a in assignments]
        
        return jsonify({'success': True, 'assignments': assignments_data})
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
        
        ticket_number = assignment.ticket_number
        
        # Free up the ticket
        ticket = Ticket.query.filter_by(ticket_number=ticket_number).first()
        if ticket:
            ticket.is_used = False
            ticket.used_at = None
        
        db.session.delete(assignment)
        db.session.commit()
        
        # Broadcast update
        socketio.emit('table_update', {'tables': get_table_status()}, namespace='/')
        
        return jsonify({'success': True, 'message': 'Assignment deleted'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/block-table', methods=['POST'])
@require_admin
def block_table():
    """Block a table from being selected"""
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
        
        return jsonify({'success': True, 'message': f'Table {table_number} blocked'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/unblock-table', methods=['POST'])
@require_admin
def unblock_table():
    """Unblock a table"""
    try:
        table_number = request.json.get('table_number')
        
        blocked = BlockedTable.query.filter_by(table_number=table_number).first()
        if not blocked:
            return jsonify({'success': False, 'error': 'Table not blocked'}), 404
        
        db.session.delete(blocked)
        db.session.commit()
        
        socketio.emit('table_update', {'tables': get_table_status()}, namespace='/')
        
        return jsonify({'success': True, 'message': f'Table {table_number} unblocked'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/manual-assign', methods=['POST'])
@require_admin
def manual_assign_api():
    """Manually assign a guest to a table (even if blocked) - ADMIN ONLY"""
    try:
        table_number = request.json.get('table_number')
        ticket_number = request.json.get('ticket_number', '').strip()
        full_name = request.json.get('full_name', '').strip()
        
        if not table_number or not ticket_number or not full_name:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        # Validate ticket number is numeric
        if not ticket_number.isdigit():
            return jsonify({'success': False, 'error': 'Ticket number must be numbers only'}), 400
        
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
        
        # Create assignment
        new_assignment = TableAssignment(
            ticket_number=ticket_number,
            full_name=full_name,
            table_number=table_number
        )
        db.session.add(new_assignment)
        
        # Mark ticket as used if it exists
        ticket = Ticket.query.filter_by(ticket_number=ticket_number).first()
        if ticket:
            ticket.is_used = True
            ticket.used_at = datetime.utcnow()
        
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
            # Validate ticket number is numeric
            if not new_ticket_number.isdigit():
                return jsonify({'success': False, 'error': 'Ticket number must be numbers only'}), 400
            
            existing = TableAssignment.query.filter_by(ticket_number=new_ticket_number).first()
            if existing:
                return jsonify({
                    'success': False,
                    'error': f'Ticket {new_ticket_number} is already assigned to Table {existing.table_number}'
                }), 400
            
            # Free up old ticket
            old_ticket = Ticket.query.filter_by(ticket_number=old_ticket_number).first()
            if old_ticket:
                old_ticket.is_used = False
                old_ticket.used_at = None
            
            # Mark new ticket as used
            new_ticket = Ticket.query.filter_by(ticket_number=new_ticket_number).first()
            if new_ticket:
                new_ticket.is_used = True
                new_ticket.used_at = datetime.utcnow()
            
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

@app.route('/api/admin/lookup-ticket')
@require_admin
def lookup_ticket():
    """Look up a ticket by number"""
    try:
        ticket_number = request.args.get('ticket', '').strip()
        
        if not ticket_number:
            return jsonify({'success': False, 'error': 'No ticket number provided'}), 400
        
        # Check if ticket exists
        ticket = Ticket.query.filter_by(ticket_number=ticket_number).first()
        
        # Check if assigned
        assignment = TableAssignment.query.filter_by(ticket_number=ticket_number).first()
        
        if assignment:
            return jsonify({
                'success': True,
                'assignment': {
                    'ticket_number': assignment.ticket_number,
                    'full_name': assignment.full_name,
                    'table_number': assignment.table_number,
                    'assigned_at': assignment.assigned_at.isoformat()
                }
            })
        elif ticket:
            return jsonify({
                'success': True,
                'ticket_exists': True,
                'guest_name': ticket.full_name,
                'assignment': None
            })
        else:
            return jsonify({
                'success': True,
                'ticket_exists': False,
                'assignment': None
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/reset-demo', methods=['GET', 'POST'])
@require_admin
def reset_demo():
    """Reset all assignments (keep tickets)"""
    try:
        # Delete all assignments
        TableAssignment.query.delete()
        
        # Mark all tickets as unused
        tickets = Ticket.query.all()
        for ticket in tickets:
            ticket.is_used = False
            ticket.used_at = None
        
        db.session.commit()
        
        socketio.emit('table_update', {'tables': get_table_status()}, namespace='/')
        
        return jsonify({'success': True, 'message': 'All assignments reset'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/reset-tickets', methods=['GET', 'POST'])
@require_admin
def reset_tickets():
    """DANGER: Delete all tickets and assignments"""
    try:
        TableAssignment.query.delete()
        Ticket.query.delete()
        db.session.commit()
        
        socketio.emit('table_update', {'tables': get_table_status()}, namespace='/')
        
        return jsonify({
            'success': True,
            'message': 'All tickets and assignments deleted. You can now upload new tickets.'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== TICKET MANAGEMENT (NEW) ====================

@app.route('/admin/upload-tickets', methods=['GET', 'POST'])
@require_admin
def upload_tickets():
    """Upload tickets from CSV or manual entry"""
    if request.method == 'GET':
        return render_template('upload_tickets.html')
    
    try:
        # Get ticket data from form
        ticket_data = request.json.get('tickets', [])
        
        if not ticket_data:
            return jsonify({'success': False, 'error': 'No ticket data provided'}), 400
        
        added_count = 0
        skipped_count = 0
        errors = []
        
        for data in ticket_data:
            ticket_number = data.get('ticket_number', '').strip()
            full_name = data.get('full_name', '').strip()
            
            if not ticket_number or not full_name:
                errors.append(f'Missing data for ticket {ticket_number}')
                continue
            
            # Validate ticket number is numeric
            if not ticket_number.isdigit():
                errors.append(f'Ticket {ticket_number} is invalid (must be numbers only)')
                continue
            
            # Check if ticket already exists
            existing = Ticket.query.filter_by(ticket_number=ticket_number).first()
            if existing:
                skipped_count += 1
                continue
            
            # Create ticket
            new_ticket = Ticket(
                ticket_number=ticket_number,
                full_name=full_name
            )
            db.session.add(new_ticket)
            added_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'added': added_count,
            'skipped': skipped_count,
            'errors': errors
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== INITIALIZE DATABASE ====================

def init_db():
    """Initialize database tables"""
    with app.app_context():
        db.create_all()
        print("Database tables created successfully!")

# Call init_db when app starts
init_db()

# ==================== WEBSOCKET EVENTS ====================

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print('Client connected')
    emit('table_update', {'tables': get_table_status()})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print('Client disconnected')

# ==================== RUN ====================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("Database initialized!")
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
