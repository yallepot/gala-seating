# 🏗️ System Architecture - Gala Seating System

## Overview

The Gala Seating System is a real-time web application built with Flask and WebSockets, designed to handle concurrent seat assignments for 25 tables with 10 seats each.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        CLIENT SIDE                           │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Browser    │    │   Browser    │    │   Browser    │  │
│  │   Guest 1    │    │   Guest 2    │    │   Guest N    │  │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘  │
│         │                   │                   │            │
│         │ HTTP + WebSocket  │                   │            │
│         └───────────────────┴───────────────────┘            │
│                             │                                │
└─────────────────────────────┼────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        SERVER SIDE                           │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Flask Application (app.py)              │    │
│  ├─────────────────────────────────────────────────────┤    │
│  │                                                       │    │
│  │  Routes:                  WebSocket Handlers:        │    │
│  │  • /                      • connect                  │    │
│  │  • /seating               • disconnect               │    │
│  │  • /confirmation          • request_update           │    │
│  │                                                       │    │
│  │  API Endpoints:                                      │    │
│  │  • /api/validate-tickets                            │    │
│  │  • /api/get-tables                                  │    │
│  │  • /api/assign-seats                                │    │
│  │  • /admin/reset-demo                                │    │
│  │                                                       │    │
│  └───────────────────┬───────────────────────────────────┘    │
│                      │                                        │
│                      ▼                                        │
│  ┌─────────────────────────────────────────────────────┐    │
│  │         Flask-SocketIO (WebSocket Server)           │    │
│  │                                                       │    │
│  │  • Real-time bidirectional communication             │    │
│  │  • Broadcasts table updates to all clients           │    │
│  │  • Event-driven architecture                         │    │
│  │                                                       │    │
│  └───────────────────┬───────────────────────────────────┘    │
│                      │                                        │
│                      ▼                                        │
│  ┌─────────────────────────────────────────────────────┐    │
│  │          SQLAlchemy (ORM Layer)                      │    │
│  │                                                       │    │
│  │  Models:                                             │    │
│  │  • Ticket         - Stores valid tickets             │    │
│  │  • TableAssignment - Stores seat assignments         │    │
│  │                                                       │    │
│  │  Features:                                           │    │
│  │  • Atomic transactions                               │    │
│  │  • Race condition prevention                         │    │
│  │  • Optimistic concurrency control                    │    │
│  │                                                       │    │
│  └───────────────────┬───────────────────────────────────┘    │
│                      │                                        │
│                      ▼                                        │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Database Layer                          │    │
│  │                                                       │    │
│  │  Production: PostgreSQL                              │    │
│  │  Development: SQLite                                 │    │
│  │                                                       │    │
│  │  Tables:                                             │    │
│  │  • tickets                                           │    │
│  │  • table_assignments                                 │    │
│  │                                                       │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Ticket Registration Flow

```
User → /api/validate-tickets → Database Lookup → Session Storage → /seating
   │                              │
   │                              ├─ Check ticket exists
   │                              ├─ Verify not already used
   │                              └─ Store in session
   │
   └─ Redirect to seating page
```

### 2. Real-Time Table Updates Flow

```
Client A                    Server                      Database                Client B
   │                          │                           │                         │
   │  Connect WebSocket       │                           │                         │
   ├─────────────────────────>│                           │                         │
   │                          │  Get current tables       │                         │
   │                          ├──────────────────────────>│                         │
   │                          │<──────────────────────────┤                         │
   │  Send table data         │                           │                         │
   │<─────────────────────────┤                           │                         │
   │                          │                           │                         │
   │  Assign seats (POST)     │                           │                         │
   ├─────────────────────────>│                           │                         │
   │                          │  Atomic transaction       │                         │
   │                          ├──────────────────────────>│                         │
   │                          │  • Check capacity         │                         │
   │                          │  • Insert assignments     │                         │
   │                          │  • Mark tickets used      │                         │
   │                          │<──────────────────────────┤                         │
   │                          │                           │                         │
   │                          │  Broadcast update         │                         │
   │  Update notification     │──────────────────────────────────────────────────> │
   │<─────────────────────────┤                           │  Update notification    │
   │                          │                           │                         │
```

### 3. Race Condition Prevention

```
Guest A                     Database                     Guest B
   │                           │                           │
   │  Attempt seat at Table 5  │                           │
   ├──────────────────────────>│                           │
   │                           │  Begin transaction        │
   │                           │  Count = 9/10 seats       │
   │                           │                           │  Attempt same table
   │                           │<──────────────────────────┤
   │                           │  Begin transaction        │
   │                           │  Count = 9/10 seats       │
   │                           │                           │
   │                           │  Insert Guest A (10/10)   │
   │  Success                  │  Commit transaction       │
   │<──────────────────────────┤                           │
   │                           │                           │
   │                           │  Insert Guest B (11/10)   │
   │                           │  ❌ CAPACITY CHECK FAILS  │
   │                           │  Rollback transaction     │
   │                           ├──────────────────────────>│
   │                           │                           │  Error: Table full
   │                           │                           │
   │  Broadcast: Table 5 full  │                           │
   ├──────────────────────────────────────────────────────>│
   │                           │                           │  Real-time update
```

## Technology Stack

### Backend
- **Flask 3.0.0**: Web framework
- **Flask-SocketIO 5.3.5**: WebSocket implementation
- **SQLAlchemy 3.1.1**: ORM for database operations
- **Gunicorn 21.2.0**: WSGI HTTP Server
- **Eventlet 0.33.3**: Networking library for WebSocket support
- **PostgreSQL**: Production database
- **SQLite**: Development database

### Frontend
- **Vanilla JavaScript**: No framework dependencies
- **Socket.IO Client 4.5.4**: WebSocket client
- **CSS3**: Modern styling with gradients, animations
- **HTML5**: Semantic markup

### Deployment
- **Render/Railway/Heroku**: Free hosting platforms
- **PostgreSQL**: Hosted database
- **Git**: Version control

## Security Features

### 1. Session-Based Validation
```python
# Tickets validated and stored in server-side session
session['validated_guests'] = validated_guests

# Only guests in session can assign seats
if 'validated_guests' not in session:
    return error("Unauthorized")
```

### 2. Atomic Transactions
```python
try:
    # All operations succeed or all fail
    db.session.add(assignment)
    db.session.commit()
except:
    db.session.rollback()  # Undo all changes
```

### 3. Server-Side Validation
```python
# Never trust client data
current_count = TableAssignment.query.filter_by(
    table_number=table_number
).count()

if current_count >= SEATS_PER_TABLE:
    return error("Table full")
```

### 4. Input Sanitization
```python
ticket_number = data.get('ticket_number', '').strip().upper()
full_name = data.get('full_name', '').strip()
```

## Database Schema

### Tickets Table
```sql
CREATE TABLE tickets (
    id INTEGER PRIMARY KEY,
    ticket_number VARCHAR(50) UNIQUE NOT NULL,
    full_name VARCHAR(200) NOT NULL,
    is_used BOOLEAN DEFAULT FALSE,
    used_at DATETIME
);

CREATE INDEX idx_ticket_number ON tickets(ticket_number);
```

### Table Assignments Table
```sql
CREATE TABLE table_assignments (
    id INTEGER PRIMARY KEY,
    ticket_number VARCHAR(50) REFERENCES tickets(ticket_number),
    full_name VARCHAR(200) NOT NULL,
    table_number INTEGER NOT NULL,
    assigned_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_table_lookup ON table_assignments(table_number, assigned_at);
```

## Performance Considerations

### 1. Database Indexing
- Ticket number indexed for O(1) lookup
- Table number indexed for fast occupancy queries

### 2. WebSocket Efficiency
- Only broadcasts on actual changes
- Sends minimal data (table updates only)
- Connection pooling with eventlet

### 3. Session Management
- Server-side sessions prevent token tampering
- Session data cleared after confirmation

### 4. Query Optimization
```python
# Bulk operations
db.session.bulk_save_objects(tickets)

# Efficient counting
TableAssignment.query.filter_by(table_number=1).count()

# Early return on full tables
if table.is_full:
    option.disabled = True
```

## Scalability

### Current Capacity
- **Tables**: 25 (configurable)
- **Seats per table**: 10 (configurable)
- **Total capacity**: 250 guests
- **Concurrent users**: 100+ (limited by free hosting)

### Scaling Options

**Vertical Scaling** (Upgrade hosting plan):
- More RAM → More concurrent connections
- More CPU → Faster processing
- Dedicated workers

**Horizontal Scaling** (Multiple instances):
- Redis for session storage (shared sessions)
- Redis for pub/sub (WebSocket broadcasts)
- Load balancer

**Database Scaling**:
- Connection pooling
- Read replicas for table status
- Caching layer (Redis)

## Deployment Architecture

```
┌─────────────┐
│   Internet  │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Cloud Load  │  (Render/Railway/Heroku)
│  Balancer   │
└──────┬──────┘
       │
       ▼
┌─────────────────────────┐
│   Application Server    │
│  (Gunicorn + Eventlet)  │
│                         │
│  ┌──────────────────┐  │
│  │  Flask App       │  │
│  │  + SocketIO      │  │
│  └──────────────────┘  │
└──────┬──────────────────┘
       │
       ▼
┌─────────────────┐
│   PostgreSQL    │
│    Database     │
└─────────────────┘
```

## Monitoring & Logging

### Application Logs
```python
print('Client connected')  # Connection events
print('Received table update')  # WebSocket events
```

### Error Handling
```python
try:
    # Operation
except Exception as e:
    print(f"Error: {str(e)}")
    db.session.rollback()
    return error_response()
```

### Platform Monitoring
- Render: Built-in logs viewer
- Railway: Deployment logs
- Heroku: Papertrail addon

## Future Enhancements

1. **Admin Dashboard**
   - View all assignments
   - Export to CSV/Excel
   - Reset specific tables

2. **Email Confirmations**
   - Automatic confirmation emails
   - QR code with seat assignment

3. **Advanced Analytics**
   - Real-time occupancy charts
   - Assignment patterns
   - Popular table tracking

4. **Guest Preferences**
   - Dietary restrictions
   - Accessibility needs
   - Group seating preferences

5. **Mobile App**
   - Native iOS/Android
   - Push notifications
   - Offline support

## Summary

This architecture provides:
- ✅ Real-time updates via WebSockets
- ✅ Atomic transactions for data integrity
- ✅ Race condition prevention
- ✅ Scalable design
- ✅ Secure validation
- ✅ Free hosting capability
- ✅ Mobile-optimized interface
- ✅ Easy deployment

Perfect for managing your 250-guest gala with 25 tables! 🎊
