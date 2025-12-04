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
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///seating.db')

# Fix for Render PostgreSQL URL
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Configuration
TOTAL_TABLES = 25
SEATS_PER_TABLE = 10
TOTAL_TICKETS = 250
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

# Models
class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(50), unique=True, nullable=False)
    full_name = db.Column(db.String(200), nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    used_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class TableAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(50), unique=True, nullable=False)
    full_name = db.Column(db.String(200), nullable=False)
    table_number = db.Column(db.Integer, nullable=False)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)

class BlockedTable(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    table_number = db.Column(db.Integer, unique=True, nullable=False)
    reason = db.Column(db.String(200))
    blocked_at = db.Column(db.DateTime, default=datetime.utcnow)

# Initialize database
with app.app_context():
    db.create_all()

# Helper Functions
def get_table_status():
    """Get current status of all tables"""
    tables = []
    blocked_tables = {bt.table_number: bt.reason for bt in BlockedTable.query.all()}
    
    for table_num in range(1, TOTAL_TABLES + 1):
        assignments = TableAssignment.query.filter_by(table_number=table_num).all()
        occupied = len(assignments)
        available = SEATS_PER_TABLE - occupied
        is_blocked = table_num in blocked_tables
        
        occupants = []
        for assignment in assignments:
            occupants.append({
                'ticket': assignment.ticket_number,
                'name': assignment.full_name
            })
        
        tables.append({
            'number': table_num,
            'capacity': SEATS_PER_TABLE,
            'occupied': occupied,
            'available': available,
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
        
        # Check for duplicates in current request
        if ticket_number in ticket_numbers_in_request:
            return False, [], f"Ticket {ticket_number} appears multiple times in your entry. Please remove duplicates."
        
        ticket_numbers_in_request.append(ticket_number)
        
        # Check if ticket exists in database
        ticket = Ticket.query.filter_by(ticket_number=ticket_number).first()
        
        if not ticket:
            return False, [], f"Ticket {ticket_number} is invalid or does not exist"
        
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

def require_admin(f):
    """Decorator to require admin authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def index():
    """Landing page for ticket entry"""
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
        is_valid, validated_guests, error_msg = validate_tickets(tickets)
        
        if not is_valid:
            return jsonify({'success': False, 'error': error_msg}), 400
        
        # Store in session
        session['guests'] = validated_guests
        session['ticket_numbers'] = [g['ticket_number'] for g in validated_guests]
        
        return jsonify({
            'success': True,
            'redirect': url_for('seating')
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/seating')
def seating():
    """Seating selection page"""
    if 'guests' not in session:
        return redirect(url_for('index'))
    
    guests = session.get('guests', [])
    return render_template('seating.html', guests=guests)

@app.route('/api/get-tables')
def get_tables_api():
    """API endpoint to get table status"""
    try:
        tables = get_table_status()
        return jsonify({
            'success': True,
            'tables': tables
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/assign-seats', methods=['POST'])
def assign_seats_api():
    """API endpoint to assign seats"""
    try:
        if 'guests' not in session:
            return jsonify({'success': False, 'error': 'Session expired. Please start over.'}), 400
        
        assignments = request.json.get('assignments', [])
        
        if not assignments:
            return jsonify({'success': False, 'error': 'No assignments provided'}), 400
        
        # Validate all assignments first
        for assignment in assignments:
            ticket_number = assignment.get('ticket_number')
            table_number = assignment.get('table_number')
            
            # Check if ticket is in session
            if ticket_number not in session.get('ticket_numbers', []):
                return jsonify({'success': False, 'error': f'Invalid ticket {ticket_number}'}), 400
            
            # Check table capacity
            current_occupancy = TableAssignment.query.filter_by(table_number=table_number).count()
            if current_occupancy >= SEATS_PER_TABLE:
                return jsonify({'success': False, 'error': f'Table {table_number} is now full'}), 400
            
            # Check if table is blocked
            blocked = BlockedTable.query.filter_by(table_number=table_number).first()
            if blocked:
                return jsonify({'success': False, 'error': f'Table {table_number} is blocked'}), 400
        
        # All validations passed, now create assignments
        for assignment in assignments:
            ticket_number = assignment.get('ticket_number')
            full_name = assignment.get('full_name')
            table_number = assignment.get('table_number')
            
            # Create assignment
            new_assignment = TableAssignment(
                ticket_number=ticket_number,
                full_name=full_name,
                table_number=table_number
            )
            db.session.add(new_assignment)
            
            # Mark ticket as used
            ticket = Ticket.query.filter_by(ticket_number=ticket_number).first()
            if ticket:
                ticket.is_used = True
                ticket.used_at = datetime.utcnow()
        
        db.session.commit()
        
        # Store assignments in session for confirmation page
        session['confirmed_assignments'] = assignments
        
        # Broadcast table update via WebSocket
        socketio.emit('table_update', {'tables': get_table_status()}, namespace='/')
        
        return jsonify({
            'success': True,
            'message': 'Seats assigned successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/confirmation')
def confirmation():
    """Confirmation page"""
    if 'confirmed_assignments' not in session:
        return redirect(url_for('index'))
    
    assignments = session.get('confirmed_assignments', [])
    return render_template('confirmation.html', assignments=assignments)

# Admin Routes
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
    if request.method == 'POST':
        password = request.form.get('password')
        
        if password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_panel'))
        else:
            return render_template('admin_login.html', error='Invalid password')
    
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    """Admin logout"""
    session.pop('admin_logged_in', None)
    return redirect(url_for('index'))

@app.route('/admin')
@require_admin
def admin_panel():
    """Admin control panel"""
    return render_template('admin.html', total_tables=TOTAL_TABLES)

@app.route('/api/admin/get-all-assignments')
@require_admin
def get_all_assignments_api():
    """Get all seat assignments for admin"""
    try:
        assignments = TableAssignment.query.order_by(TableAssignment.table_number, TableAssignment.assigned_at).all()
        
        assignments_data = []
        for assignment in assignments:
            assignments_data.append({
                'id': assignment.id,
                'ticket_number': assignment.ticket_number,
                'full_name': assignment.full_name,
                'table_number': assignment.table_number,
                'assigned_at': assignment.assigned_at.isoformat()
            })
        
        return jsonify({
            'success': True,
            'assignments': assignments_data
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/delete-any-assignment', methods=['POST'])
@require_admin
def delete_any_assignment_api():
    """Delete any assignment - ADMIN ONLY"""
    try:
        assignment_id = request.json.get('assignment_id')
        
        if not assignment_id:
            return jsonify({'success': False, 'error': 'Assignment ID required'}), 400
        
        assignment = TableAssignment.query.get(assignment_id)
        
        if not assignment:
            return jsonify({'success': False, 'error': 'Assignment not found'}), 404
        
        ticket_number = assignment.ticket_number
        
        # Delete assignment
        db.session.delete(assignment)
        
        # Free up ticket
        ticket = Ticket.query.filter_by(ticket_number=ticket_number).first()
        if ticket:
            ticket.is_used = False
            ticket.used_at = None
        
        db.session.commit()
        
        # Broadcast update
        socketio.emit('table_update', {'tables': get_table_status()}, namespace='/')
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/block-table', methods=['POST'])
@require_admin
def block_table_api():
    """Block a table - ADMIN ONLY"""
    try:
        table_number = request.json.get('table_number')
        reason = request.json.get('reason', 'Reserved')
        
        if not table_number or table_number < 1 or table_number > TOTAL_TABLES:
            return jsonify({'success': False, 'error': 'Invalid table number'}), 400
        
        # Check if already blocked
        existing = BlockedTable.query.filter_by(table_number=table_number).first()
        if existing:
            return jsonify({'success': False, 'error': 'Table already blocked'}), 400
        
        # Create block
        blocked = BlockedTable(table_number=table_number, reason=reason)
        db.session.add(blocked)
        db.session.commit()
        
        # Broadcast update
        socketio.emit('table_update', {'tables': get_table_status()}, namespace='/')
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/unblock-table', methods=['POST'])
@require_admin
def unblock_table_api():
    """Unblock a table - ADMIN ONLY"""
    try:
        table_number = request.json.get('table_number')
        
        if not table_number:
            return jsonify({'success': False, 'error': 'Table number required'}), 400
        
        blocked = BlockedTable.query.filter_by(table_number=table_number).first()
        
        if not blocked:
            return jsonify({'success': False, 'error': 'Table is not blocked'}), 404
        
        db.session.delete(blocked)
        db.session.commit()
        
        # Broadcast update
        socketio.emit('table_update', {'tables': get_table_status()}, namespace='/')
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/lookup-ticket')
@require_admin
def lookup_ticket_api():
    """Look up ticket information - ADMIN ONLY"""
    try:
        ticket_number = request.args.get('ticket', '').strip()
        
        if not ticket_number:
            return jsonify({'success': False, 'error': 'Ticket number required'}), 400
        
        # Check if ticket exists
        ticket = Ticket.query.filter_by(ticket_number=ticket_number).first()
        
        if not ticket:
            return jsonify({
                'success': True,
                'ticket_exists': False,
                'assignment': None
            })
        
        # Check if assigned
        assignment = TableAssignment.query.filter_by(ticket_number=ticket_number).first()
        
        if assignment:
            return jsonify({
                'success': True,
                'ticket_exists': True,
                'assignment': {
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
                'guest_name': ticket.full_name,
                'assignment': None
            })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/reset-demo', methods=['GET'])
@require_admin
def reset_demo():
    """Reset all assignments - ADMIN ONLY"""
    try:
        # Delete all assignments
        TableAssignment.query.delete()
        
        # Delete all blocked tables
        BlockedTable.query.delete()
        
        # Reset all tickets
        tickets = Ticket.query.all()
        for ticket in tickets:
            ticket.is_used = False
            ticket.used_at = None
        
        db.session.commit()
        
        # Broadcast update
        socketio.emit('table_update', {'tables': get_table_status()}, namespace='/')
        
        return jsonify({'success': True, 'message': 'All assignments reset'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/reset-tickets', methods=['GET'])
@require_admin
def reset_tickets():
    """Reset all tickets to 1-250 - ADMIN ONLY"""
    try:
        # Delete all existing tickets
        Ticket.query.delete()
        
        # Delete all assignments
        TableAssignment.query.delete()
        
        # Delete all blocked tables
        BlockedTable.query.delete()
        
        # Create new tickets 1-250 (but they can be any number from 1-1000)
        # For initialization, we'll create tickets 1-250
        for i in range(1, TOTAL_TICKETS + 1):
            ticket = Ticket(
                ticket_number=str(i),
                full_name=f"Guest {i}",
                is_used=False
            )
            db.session.add(ticket)
        
        db.session.commit()
        
        # Broadcast update
        socketio.emit('table_update', {'tables': get_table_status()}, namespace='/')
        
        return jsonify({
            'success': True,
            'message': f'All tickets reset! Created tickets 1-{TOTAL_TICKETS}. Admins can add tickets with any number 1-1000.'
        })
        
    except Exception as e:
        db.session.rollback()
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
        
        # Create assignment
        new_assignment = TableAssignment(
            ticket_number=ticket_number,
            full_name=full_name,
            table_number=table_number
        )
        db.session.add(new_assignment)
        
        # Mark ticket as used if it exists, or create it if it doesn't
        ticket = Ticket.query.filter_by(ticket_number=ticket_number).first()
        if ticket:
            ticket.is_used = True
            ticket.used_at = datetime.utcnow()
        else:
            # Create ticket if it doesn't exist (for manual entries)
            new_ticket = Ticket(
                ticket_number=ticket_number,
                full_name=full_name,
                is_used=True,
                used_at=datetime.utcnow()
            )
            db.session.add(new_ticket)
        
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
    """Edit an existing assignment - change ticket number, name, or table - ADMIN ONLY"""
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
            
            # Free up old ticket
            old_ticket = Ticket.query.filter_by(ticket_number=old_ticket_number).first()
            if old_ticket:
                old_ticket.is_used = False
                old_ticket.used_at = None
            
            # Mark new ticket as used or create it
            new_ticket = Ticket.query.filter_by(ticket_number=new_ticket_number).first()
            if new_ticket:
                new_ticket.is_used = True
                new_ticket.used_at = datetime.utcnow()
            else:
                # Create ticket if doesn't exist
                created_ticket = Ticket(
                    ticket_number=new_ticket_number,
                    full_name=new_full_name if new_full_name else assignment.full_name,
                    is_used=True,
                    used_at=datetime.utcnow()
                )
                db.session.add(created_ticket)
            
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

@app.route('/api/admin/add-ticket', methods=['POST'])
@require_admin
def add_ticket_api():
    """Add a new ticket manually - ADMIN ONLY - ticket numbers can be 1-1000"""
    try:
        ticket_number = request.json.get('ticket_number', '').strip()
        full_name = request.json.get('full_name', '').strip()
        
        if not ticket_number or not full_name:
            return jsonify({'success': False, 'error': 'Ticket number and name required'}), 400
        
        # Validate ticket number is within range
        try:
            ticket_num = int(ticket_number)
            if ticket_num < 1 or ticket_num > 1000:
                return jsonify({'success': False, 'error': 'Ticket number must be between 1 and 1000'}), 400
        except ValueError:
            return jsonify({'success': False, 'error': 'Ticket number must be a valid number'}), 400
        
        # Check if ticket already exists
        existing = Ticket.query.filter_by(ticket_number=ticket_number).first()
        if existing:
            return jsonify({'success': False, 'error': f'Ticket {ticket_number} already exists'}), 400
        
        # Create ticket
        new_ticket = Ticket(
            ticket_number=ticket_number,
            full_name=full_name,
            is_used=False
        )
        db.session.add(new_ticket)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Ticket {ticket_number} added successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# WebSocket Events
@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    emit('table_update', {'tables': get_table_status()})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)

# ==================== USHER ROUTES ====================

@app.route('/usher')
def usher_dashboard():
    """Usher dashboard - no authentication required"""
    return render_template('usher.html')

@app.route('/api/usher/get-tables')
def usher_get_tables():
    """Get table status for ushers"""
    try:
        tables = get_table_status()
        return jsonify({'success': True, 'tables': tables})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/usher/get-all-assignments')
def usher_get_all_assignments():
    """Get all assignments for ushers"""
    try:
        assignments = TableAssignment.query.order_by(
            TableAssignment.table_number, 
            TableAssignment.assigned_at
        ).all()
        
        assignments_data = [{
            'ticket_number': a.ticket_number,
            'full_name': a.full_name,
            'table_number': a.table_number,
            'assigned_at': a.assigned_at.isoformat()
        } for a in assignments]
        
        return jsonify({'success': True, 'assignments': assignments_data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/usher/lookup-ticket')
def usher_lookup_ticket():
    """Look up a ticket for ushers"""
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
                'ticket_exists': True,
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
