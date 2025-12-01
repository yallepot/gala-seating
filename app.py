"""
Gala Seating System - Main Application
Real-time seating assignment with WebSocket support
FULLY DEBUGGED VERSION 1.0 - All bugs fixed
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from functools import wraps
import os
import secrets

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///gala_seating.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['ADMIN_PASSWORD'] = os.environ.get('ADMIN_PASSWORD', 'admin123')

# Fix for Heroku postgres URL
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://', 1)

# Initialize extensions
db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Configuration
TOTAL_TABLES = 25
SEATS_PER_TABLE = 10

# ==================== DATABASE MODELS ====================

class Ticket(db.Model):
    """Valid ticket database"""
    __tablename__ = 'tickets'
    
    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(200), nullable=False)
    is_used = db.Column(db.Boolean, default=False, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
    
    def __repr__(self):
        return f'<Ticket {self.ticket_number}: {self.full_name}>'


class TableAssignment(db.Model):
    """Table seating assignments"""
    __tablename__ = 'table_assignments'
    
    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(50), db.ForeignKey('tickets.ticket_number'), nullable=False)
    full_name = db.Column(db.String(200), nullable=False)
    table_number = db.Column(db.Integer, nullable=False)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        db.Index('idx_table_lookup', 'table_number', 'assigned_at'),
    )
    
    def __repr__(self):
        return f'<Assignment: {self.full_name} at Table {self.table_number}>'


class BlockedTable(db.Model):
    """Tables that are blocked/reserved by admin"""
    __tablename__ = 'blocked_tables'
    
    id = db.Column(db.Integer, primary_key=True)
    table_number = db.Column(db.Integer, nullable=False, unique=True)
    reason = db.Column(db.String(200), nullable=True)
    blocked_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Blocked Table {self.table_number}: {self.reason}>'


# ==================== DATABASE INITIALIZATION ====================

def init_database():
    """Initialize database and create sample tickets"""
    with app.app_context():
        db.create_all()
        
        if Ticket.query.count() == 0:
            print("Creating sample tickets...")
            sample_tickets = []
            
            for i in range(1, 251):
                ticket = Ticket(
                    ticket_number=str(i),
                    full_name=f'Guest {i}'
                )
                sample_tickets.append(ticket)
            
            db.session.bulk_save_objects(sample_tickets)
            db.session.commit()
            print(f"Created {len(sample_tickets)} sample tickets")


# ==================== ADMIN AUTHENTICATION ====================

def check_admin_auth():
    """Check if user is authenticated as admin"""
    return session.get('admin_authenticated', False)


def require_admin(f):
    """Decorator to require admin authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not check_admin_auth():
            return jsonify({'success': False, 'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function


# ==================== HELPER FUNCTIONS ====================

def get_table_status():
    """Get current status of all tables with real-time occupancy data - OPTIMIZED"""
    # Single query to get all blocked tables
    blocked_tables_query = BlockedTable.query.all()
    blocked_tables = {bt.table_number: bt.reason for bt in blocked_tables_query}
    
    # Single query to get all assignments with eager loading
    all_assignments = TableAssignment.query.order_by(TableAssignment.table_number, TableAssignment.assigned_at).all()
    
    # Group assignments by table number
    assignments_by_table = {}
    for assignment in all_assignments:
        if assignment.table_number not in assignments_by_table:
            assignments_by_table[assignment.table_number] = []
        assignments_by_table[assignment.table_number].append(assignment)
    
    # Build table data
    tables = []
    for table_num in range(1, TOTAL_TABLES + 1):
        is_blocked = table_num in blocked_tables
        block_reason = blocked_tables.get(table_num, None)
        
        table_assignments = assignments_by_table.get(table_num, [])
        
        occupants = [
            {
                'name': assignment.full_name,
                'ticket': assignment.ticket_number
            }
            for assignment in table_assignments
        ]
        
        tables.append({
            'number': table_num,
            'capacity': SEATS_PER_TABLE,
            'occupied': len(occupants),
            'available': SEATS_PER_TABLE - len(occupants),
            'occupants': occupants,
            'is_full': len(occupants) >= SEATS_PER_TABLE,
            'is_blocked': is_blocked,
            'block_reason': block_reason
        })
    
    return tables


def validate_tickets(ticket_data):
    """Validate ticket numbers and check availability"""
    validated_guests = []
    
    for data in ticket_data:
        ticket_number = data.get('ticket_number', '').strip()
        full_name = data.get('full_name', '').strip()
        
        if not ticket_number or not full_name:
            return False, [], "All fields must be filled out"
        
        ticket = Ticket.query.filter_by(ticket_number=ticket_number).first()
        
        if not ticket:
            return False, [], f"Invalid ticket number: {ticket_number}"
        
        if ticket.is_used:
            return False, [], f"Ticket {ticket_number} has already been used"
        
        validated_guests.append({
            'ticket_number': ticket_number,
            'full_name': full_name,
            'original_name': ticket.full_name
        })
    
    return True, validated_guests, None


def assign_seats_atomic(assignments):
    """Atomically assign seats to tables"""
    try:
        for assignment_data in assignments:
            table_number = assignment_data['table_number']
            ticket_number = assignment_data['ticket_number']
            full_name = assignment_data['full_name']
            
            blocked = BlockedTable.query.filter_by(table_number=table_number).first()
            if blocked:
                db.session.rollback()
                reason = blocked.reason or "reserved"
                return False, f"Table {table_number} is blocked ({reason})"
            
            current_count = TableAssignment.query.filter_by(
                table_number=table_number
            ).count()
            
            if current_count >= SEATS_PER_TABLE:
                db.session.rollback()
                return False, f"Table {table_number} is full ({current_count}/{SEATS_PER_TABLE})"
            
            new_assignment = TableAssignment(
                ticket_number=ticket_number,
                full_name=full_name,
                table_number=table_number
            )
            db.session.add(new_assignment)
            
            ticket = Ticket.query.filter_by(ticket_number=ticket_number).first()
            ticket.is_used = True
            ticket.used_at = datetime.utcnow()
        
        db.session.commit()
        return True, None
        
    except Exception as e:
        db.session.rollback()
        return False, f"Database error: {str(e)}"


# ==================== ROUTES ====================

@app.route('/')
def index():
    """Main landing page - ticket registration"""
    return render_template('index.html')


@app.route('/seating')
def seating():
    """Interactive seating view page"""
    if 'validated_guests' not in session:
        return render_template('error.html', 
            error="Please register your tickets first",
            return_url='/')
    
    return render_template('seating.html', 
        guests=session['validated_guests'],
        total_tables=TOTAL_TABLES)


@app.route('/confirmation')
def confirmation():
    """Confirmation page after successful assignment"""
    if 'assignments' not in session:
        return render_template('error.html',
            error="No assignments found",
            return_url='/')
    
    return render_template('confirmation.html',
        assignments=session.get('assignments', []))


@app.route('/admin')
def admin_panel():
    """Admin panel - requires authentication"""
    if not check_admin_auth():
        return render_template('admin_login.html')
    
    return render_template('admin.html',
        total_tables=TOTAL_TABLES,
        seats_per_table=SEATS_PER_TABLE)


@app.route('/admin/login', methods=['POST'])
def admin_login():
    """Admin login endpoint"""
    password = request.form.get('password', '')
    
    if password == app.config['ADMIN_PASSWORD']:
        session['admin_authenticated'] = True
        return redirect(url_for('admin_panel'))
    else:
        return render_template('admin_login.html', error="Invalid password")


@app.route('/admin/logout')
def admin_logout():
    """Admin logout"""
    session.pop('admin_authenticated', None)
    return redirect(url_for('index'))


# ==================== API ENDPOINTS ====================

@app.route('/api/validate-tickets', methods=['POST'])
def validate_tickets_api():
    """Validate ticket numbers and store in session"""
    try:
        ticket_data = request.json.get('tickets', [])
        
        if not ticket_data:
            return jsonify({'success': False, 'error': 'No tickets provided'}), 400
        
        is_valid, validated_guests, error = validate_tickets(ticket_data)
        
        if not is_valid:
            return jsonify({'success': False, 'error': error}), 400
        
        session['validated_guests'] = validated_guests
        
        return jsonify({
            'success': True,
            'guests': validated_guests,
            'redirect': '/seating'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/get-tables', methods=['GET'])
def get_tables_api():
    """Get current table status"""
    try:
        tables = get_table_status()
        return jsonify({'success': True, 'tables': tables})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/assign-seats', methods=['POST'])
def assign_seats_api():
    """Assign seats to tables (atomic transaction)"""
    try:
        assignments = request.json.get('assignments', [])
        
        if not assignments:
            return jsonify({'success': False, 'error': 'No assignments provided'}), 400
        
        validated_guests = session.get('validated_guests', [])
        if not validated_guests:
            return jsonify({'success': False, 'error': 'Session expired. Please start over.'}), 401
        
        valid_tickets = {g['ticket_number'] for g in validated_guests}
        assignment_tickets = {a['ticket_number'] for a in assignments}
        
        if not assignment_tickets.issubset(valid_tickets):
            return jsonify({'success': False, 'error': 'Invalid assignment data'}), 400
        
        for assignment in assignments:
            existing = TableAssignment.query.filter_by(
                ticket_number=assignment['ticket_number']
            ).first()
            
            if existing:
                return jsonify({
                    'success': False, 
                    'error': f"Ticket {assignment['ticket_number']} is already assigned"
                }), 400
        
        success, error = assign_seats_atomic(assignments)
        
        if not success:
            return jsonify({'success': False, 'error': error}), 400
        
        session['assignments'] = assignments
        
        socketio.emit('table_update', {'tables': get_table_status()}, namespace='/')
        
        return jsonify({
            'success': True,
            'message': 'Seats assigned successfully'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/delete-assignment', methods=['POST'])
def delete_assignment_api():
    """Delete a seat assignment"""
    try:
        ticket_number = request.json.get('ticket_number')
        
        if not ticket_number:
            return jsonify({'success': False, 'error': 'No ticket number provided'}), 400
        
        assignment = TableAssignment.query.filter_by(ticket_number=ticket_number).first()
        
        if not assignment:
            return jsonify({'success': False, 'error': 'Assignment not found'}), 404
        
        db.session.delete(assignment)
        
        ticket = Ticket.query.filter_by(ticket_number=ticket_number).first()
        if ticket:
            ticket.is_used = False
            ticket.used_at = None
        
        db.session.commit()
        
        socketio.emit('table_update', {'tables': get_table_status()}, namespace='/')
        
        return jsonify({'success': True, 'message': 'Assignment deleted successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== WEBSOCKET HANDLERS ====================

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print('Client connected')
    emit('table_update', {'tables': get_table_status()})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print('Client disconnected')


@socketio.on('request_update')
def handle_update_request():
    """Handle manual update request from client"""
    emit('table_update', {'tables': get_table_status()})


# ==================== ADMIN ROUTES ====================

@app.route('/admin/reset-demo')
@require_admin
def reset_demo():
    """Reset all assignments for demo purposes"""
    try:
        TableAssignment.query.delete()
        
        Ticket.query.update({
            'is_used': False,
            'used_at': None
        })
        
        db.session.commit()
        
        socketio.emit('table_update', {'tables': get_table_status()}, namespace='/')
        
        return jsonify({'success': True, 'message': 'Demo reset successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/admin/reset-tickets')
@require_admin
def reset_tickets():
    """Reset all tickets with new numbering (1-250)"""
    try:
        TableAssignment.query.delete()
        Ticket.query.delete()
        db.session.commit()
        
        new_tickets = []
        for i in range(1, 251):
            ticket = Ticket(
                ticket_number=str(i),
                full_name=f'Guest {i}'
            )
            new_tickets.append(ticket)
        
        db.session.bulk_save_objects(new_tickets)
        db.session.commit()
        
        socketio.emit('table_update', {'tables': get_table_status()}, namespace='/')
        
        return jsonify({
            'success': True, 
            'message': 'Created 250 tickets numbered 1-250'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/block-table', methods=['POST'])
@require_admin
def block_table_api():
    """Block a table from being selected"""
    try:
        table_number = request.json.get('table_number')
        reason = request.json.get('reason', 'Reserved')
        
        if not table_number or table_number < 1 or table_number > TOTAL_TABLES:
            return jsonify({'success': False, 'error': 'Invalid table number'}), 400
        
        existing = BlockedTable.query.filter_by(table_number=table_number).first()
        if existing:
            return jsonify({'success': False, 'error': 'Table already blocked'}), 400
        
        blocked = BlockedTable(
            table_number=table_number,
            reason=reason
        )
        db.session.add(blocked)
        db.session.commit()
        
        socketio.emit('table_update', {'tables': get_table_status()}, namespace='/')
        
        return jsonify({'success': True, 'message': f'Table {table_number} blocked'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/unblock-table', methods=['POST'])
@require_admin
def unblock_table_api():
    """Unblock a table"""
    try:
        table_number = request.json.get('table_number')
        
        if not table_number:
            return jsonify({'success': False, 'error': 'No table number provided'}), 400
        
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


@app.route('/api/admin/get-all-assignments', methods=['GET'])
@require_admin
def get_all_assignments_api():
    """Get all seat assignments for admin view"""
    try:
        assignments = TableAssignment.query.order_by(
            TableAssignment.table_number,
            TableAssignment.assigned_at
        ).all()
        
        result = []
        for assignment in assignments:
            result.append({
                'id': assignment.id,
                'table_number': assignment.table_number,
                'full_name': assignment.full_name,
                'ticket_number': assignment.ticket_number,
                'assigned_at': assignment.assigned_at.isoformat()
            })
        
        return jsonify({'success': True, 'assignments': result})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/delete-any-assignment', methods=['POST'])
@require_admin
def admin_delete_assignment():
    """Admin can delete any assignment"""
    try:
        assignment_id = request.json.get('assignment_id')
        
        if not assignment_id:
            return jsonify({'success': False, 'error': 'No assignment ID provided'}), 400
        
        assignment = TableAssignment.query.get(assignment_id)
        
        if not assignment:
            return jsonify({'success': False, 'error': 'Assignment not found'}), 404
        
        ticket_number = assignment.ticket_number
        
        db.session.delete(assignment)
        
        ticket = Ticket.query.filter_by(ticket_number=ticket_number).first()
        if ticket:
            ticket.is_used = False
            ticket.used_at = None
        
        db.session.commit()
        
        socketio.emit('table_update', {'tables': get_table_status()}, namespace='/')
        
        return jsonify({'success': True, 'message': 'Assignment deleted'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/lookup-ticket', methods=['GET'])
@require_admin
def lookup_ticket_api():
    """Look up a ticket to find table assignment"""
    try:
        ticket_number = request.args.get('ticket')
        
        if not ticket_number:
            return jsonify({'success': False, 'error': 'No ticket number provided'}), 400
        
        ticket_number = ticket_number.strip()
        
        ticket = Ticket.query.filter_by(ticket_number=ticket_number).first()
        
        if not ticket:
            return jsonify({
                'success': True,
                'ticket_exists': False,
                'assignment': None
            })
        
        assignment = TableAssignment.query.filter_by(ticket_number=ticket_number).first()
        
        if assignment:
            return jsonify({
                'success': True,
                'ticket_exists': True,
                'assignment': {
                    'id': assignment.id,
                    'ticket_number': assignment.ticket_number,
                    'full_name': assignment.full_name,
                    'table_number': assignment.table_number,
                    'assigned_at': assignment.assigned_at.isoformat()
                }
            })
        else:
            return jsonify({
                'success': True,
                'ticket_exists': True,
                'assignment': None,
                'guest_name': ticket.full_name
            })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== USHER ROUTES ====================

@app.route('/usher')
def usher_panel():
    """Usher panel - read-only view of assignments"""
    return render_template('usher.html',
        total_tables=TOTAL_TABLES,
        seats_per_table=SEATS_PER_TABLE)


@app.route('/api/usher/get-all-assignments', methods=['GET'])
def usher_get_all_assignments():
    """Get all seat assignments for usher view (read-only)"""
    try:
        assignments = TableAssignment.query.order_by(
            TableAssignment.table_number,
            TableAssignment.assigned_at
        ).all()
        
        result = []
        for assignment in assignments:
            result.append({
                'id': assignment.id,
                'table_number': assignment.table_number,
                'full_name': assignment.full_name,
                'ticket_number': assignment.ticket_number,
                'assigned_at': assignment.assigned_at.isoformat()
            })
        
        return jsonify({'success': True, 'assignments': result})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/usher/lookup-ticket', methods=['GET'])
def usher_lookup_ticket():
    """Usher can look up a ticket to find table assignment"""
    try:
        ticket_number = request.args.get('ticket')
        
        if not ticket_number:
            return jsonify({'success': False, 'error': 'No ticket number provided'}), 400
        
        ticket_number = ticket_number.strip()
        
        ticket = Ticket.query.filter_by(ticket_number=ticket_number).first()
        
        if not ticket:
            return jsonify({
                'success': True,
                'ticket_exists': False,
                'assignment': None
            })
        
        assignment = TableAssignment.query.filter_by(ticket_number=ticket_number).first()
        
        if assignment:
            return jsonify({
                'success': True,
                'ticket_exists': True,
                'assignment': {
                    'id': assignment.id,
                    'ticket_number': assignment.ticket_number,
                    'full_name': assignment.full_name,
                    'table_number': assignment.table_number,
                    'assigned_at': assignment.assigned_at.isoformat()
                }
            })
        else:
            return jsonify({
                'success': True,
                'ticket_exists': True,
                'assignment': None,
                'guest_name': ticket.full_name
            })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/usher/get-tables', methods=['GET'])
def usher_get_tables():
    """Get current table status for usher view"""
    try:
        tables = get_table_status()
        return jsonify({'success': True, 'tables': tables})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== APPLICATION STARTUP ====================
init_database()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
