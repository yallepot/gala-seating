"""
Gala Seating System - Main Application
Real-time seating assignment with WebSocket support
"""

from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import secrets

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///gala_seating.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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
    
    # Composite index for fast table lookups
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
        # Create all tables
        db.create_all()
        
        # Check if we need to add sample tickets
        if Ticket.query.count() == 0:
            print("Creating sample tickets...")
            sample_tickets = []
            
            # Create 250 sample tickets (25 tables × 10 seats)
            for i in range(1, 251):
                ticket = Ticket(
                    ticket_number=f'GALA-{i:04d}',
                    full_name=f'Guest {i}'
                )
                sample_tickets.append(ticket)
            
            db.session.bulk_save_objects(sample_tickets)
            db.session.commit()
            print(f"Created {len(sample_tickets)} sample tickets")


# ==================== HELPER FUNCTIONS ====================

def get_table_status():
    """Get current status of all tables with real-time occupancy data"""
    tables = []
    
    # Get all blocked tables
    blocked_tables = {bt.table_number: bt.reason for bt in BlockedTable.query.all()}
    
    for table_num in range(1, TOTAL_TABLES + 1):
        # Check if table is blocked
        is_blocked = table_num in blocked_tables
        block_reason = blocked_tables.get(table_num, None)
        
        # Get all assignments for this table
        assignments = TableAssignment.query.filter_by(
            table_number=table_num
        ).order_by(TableAssignment.assigned_at).all()
        
        occupants = [
            {
                'name': assignment.full_name,
                'ticket': assignment.ticket_number
            }
            for assignment in assignments
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
    """
    Validate ticket numbers and check availability
    
    Args:
        ticket_data: List of dicts with 'full_name' and 'ticket_number'
    
    Returns:
        tuple: (is_valid, validated_guests, error_message)
    """
    validated_guests = []
    
    for data in ticket_data:
        ticket_number = data.get('ticket_number', '').strip().upper()
        full_name = data.get('full_name', '').strip()
        
        if not ticket_number or not full_name:
            return False, [], "All fields must be filled out"
        
        # Check if ticket exists
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
    """
    Atomically assign seats to tables
    
    Args:
        assignments: List of dicts with 'ticket_number', 'full_name', 'table_number'
    
    Returns:
        tuple: (success, error_message)
    """
    try:
        # Start transaction
        for assignment_data in assignments:
            table_number = assignment_data['table_number']
            ticket_number = assignment_data['ticket_number']
            full_name = assignment_data['full_name']
            
            # Check if table is blocked
            blocked = BlockedTable.query.filter_by(table_number=table_number).first()
            if blocked:
                db.session.rollback()
                reason = blocked.reason or "reserved"
                return False, f"Table {table_number} is blocked ({reason})"
            
            # Check table capacity
            current_count = TableAssignment.query.filter_by(
                table_number=table_number
            ).count()
            
            if current_count >= SEATS_PER_TABLE:
                db.session.rollback()
                return False, f"Table {table_number} is full ({current_count}/{SEATS_PER_TABLE})"
            
            # Create assignment
            new_assignment = TableAssignment(
                ticket_number=ticket_number,
                full_name=full_name,
                table_number=table_number
            )
            db.session.add(new_assignment)
            
            # Mark ticket as used
            ticket = Ticket.query.filter_by(ticket_number=ticket_number).first()
            ticket.is_used = True
            ticket.used_at = datetime.utcnow()
        
        # Commit all changes atomically
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
    # Check if user has validated guests in session
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
    """Admin panel for managing tables and assignments"""
    return render_template('admin.html',
        total_tables=TOTAL_TABLES,
        seats_per_table=SEATS_PER_TABLE)


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
        
        # Store validated guests in session
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
        
        # Verify session has validated guests
        validated_guests = session.get('validated_guests', [])
        if not validated_guests:
            return jsonify({'success': False, 'error': 'Session expired. Please start over.'}), 401
        
        # Verify all assignments match validated guests
        valid_tickets = {g['ticket_number'] for g in validated_guests}
        assignment_tickets = {a['ticket_number'] for a in assignments}
        
        if not assignment_tickets.issubset(valid_tickets):
            return jsonify({'success': False, 'error': 'Invalid assignment data'}), 400
        
        # Check for existing assignments
        for assignment in assignments:
            existing = TableAssignment.query.filter_by(
                ticket_number=assignment['ticket_number']
            ).first()
            
            if existing:
                return jsonify({
                    'success': False, 
                    'error': f"Ticket {assignment['ticket_number']} is already assigned. Please delete the existing assignment first."
                }), 400
        
        # Perform atomic assignment
        success, error = assign_seats_atomic(assignments)
        
        if not success:
            return jsonify({'success': False, 'error': error}), 400
        
        # Store assignments in session for confirmation page
        session['assignments'] = assignments
        
        # Broadcast update to all connected clients via WebSocket
        socketio.emit('table_update', {'tables': get_table_status()}, broadcast=True)
        
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
        
        # Verify session has validated guests
        validated_guests = session.get('validated_guests', [])
        if not validated_guests:
            return jsonify({'success': False, 'error': 'Session expired. Please start over.'}), 401
        
        # Verify this ticket belongs to the current session
        valid_tickets = {g['ticket_number'] for g in validated_guests}
        if ticket_number not in valid_tickets:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
        # Find and delete the assignment
        assignment = TableAssignment.query.filter_by(ticket_number=ticket_number).first()
        
        if not assignment:
            return jsonify({'success': False, 'error': 'Assignment not found'}), 404
        
        # Delete the assignment
        db.session.delete(assignment)
        
        # Mark ticket as available again
        ticket = Ticket.query.filter_by(ticket_number=ticket_number).first()
        if ticket:
            ticket.is_used = False
            ticket.used_at = None
        
        db.session.commit()
        
        # Broadcast update to all connected clients
        socketio.emit('table_update', {'tables': get_table_status()}, broadcast=True)
        
        return jsonify({'success': True, 'message': 'Assignment deleted successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== WEBSOCKET HANDLERS ====================

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print('Client connected')
    # Send current table status to newly connected client
    emit('table_update', {'tables': get_table_status()})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print('Client disconnected')


@socketio.on('request_update')
def handle_update_request():
    """Handle manual update request from client"""
    emit('table_update', {'tables': get_table_status()})


# ==================== ADMIN ROUTES (Optional) ====================

@app.route('/admin/reset-demo')
def reset_demo():
    """Reset all assignments for demo purposes"""
    try:
        # Delete all assignments
        TableAssignment.query.delete()
        
        # Reset all tickets
        Ticket.query.update({
            'is_used': False,
            'used_at': None
        })
        
        db.session.commit()
        
        # Broadcast update
        socketio.emit('table_update', {'tables': get_table_status()}, broadcast=True)
        
        return jsonify({'success': True, 'message': 'Demo reset successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/block-table', methods=['POST'])
def block_table_api():
    """Block a table from being selected"""
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
        blocked = BlockedTable(
            table_number=table_number,
            reason=reason
        )
        db.session.add(blocked)
        db.session.commit()
        
        # Broadcast update
        socketio.emit('table_update', {'tables': get_table_status()}, broadcast=True)
        
        return jsonify({'success': True, 'message': f'Table {table_number} blocked'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/unblock-table', methods=['POST'])
def unblock_table_api():
    """Unblock a table"""
    try:
        table_number = request.json.get('table_number')
        
        if not table_number:
            return jsonify({'success': False, 'error': 'No table number provided'}), 400
        
        # Find and delete the block
        blocked = BlockedTable.query.filter_by(table_number=table_number).first()
        
        if not blocked:
            return jsonify({'success': False, 'error': 'Table not blocked'}), 404
        
        db.session.delete(blocked)
        db.session.commit()
        
        # Broadcast update
        socketio.emit('table_update', {'tables': get_table_status()}, broadcast=True)
        
        return jsonify({'success': True, 'message': f'Table {table_number} unblocked'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/get-all-assignments', methods=['GET'])
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
def admin_delete_assignment():
    """Admin can delete any assignment"""
    try:
        assignment_id = request.json.get('assignment_id')
        
        if not assignment_id:
            return jsonify({'success': False, 'error': 'No assignment ID provided'}), 400
        
        # Find the assignment
        assignment = TableAssignment.query.get(assignment_id)
        
        if not assignment:
            return jsonify({'success': False, 'error': 'Assignment not found'}), 404
        
        ticket_number = assignment.ticket_number
        
        # Delete the assignment
        db.session.delete(assignment)
        
        # Mark ticket as available again
        ticket = Ticket.query.filter_by(ticket_number=ticket_number).first()
        if ticket:
            ticket.is_used = False
            ticket.used_at = None
        
        db.session.commit()
        
        # Broadcast update
        socketio.emit('table_update', {'tables': get_table_status()}, broadcast=True)
        
        return jsonify({'success': True, 'message': 'Assignment deleted'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/lookup-ticket', methods=['GET'])
def lookup_ticket_api():
    """Look up a ticket to find table assignment"""
    try:
        ticket_number = request.args.get('ticket')
        
        if not ticket_number:
            return jsonify({'success': False, 'error': 'No ticket number provided'}), 400
        
        ticket_number = ticket_number.strip().upper()
        
        # Check if ticket exists
        ticket = Ticket.query.filter_by(ticket_number=ticket_number).first()
        
        if not ticket:
            return jsonify({
                'success': True,
                'ticket_exists': False,
                'assignment': None
            })
        
        # Check if ticket has an assignment
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


# ==================== APPLICATION STARTUP ====================
# Initialize database
init_database()
if __name__ == '__main__':

    
    # Get port from environment (for Render/Heroku)
    port = int(os.environ.get('PORT', 5000))
    
    # Run with SocketIO
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
