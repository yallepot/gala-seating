from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class TableAssignment(db.Model):
    __tablename__ = 'table_assignments'
    
    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(200), nullable=False)
    table_number = db.Column(db.Integer, nullable=False)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'ticket_number': self.ticket_number,
            'full_name': self.full_name,
            'table_number': self.table_number,
            'assigned_at': self.assigned_at.isoformat()
        }

class BlockedTable(db.Model):
    __tablename__ = 'blocked_tables'
    
    id = db.Column(db.Integer, primary_key=True)
    table_number = db.Column(db.Integer, unique=True, nullable=False)
    reason = db.Column(db.String(200))
    blocked_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'table_number': self.table_number,
            'reason': self.reason,
            'blocked_at': self.blocked_at.isoformat()
        }
