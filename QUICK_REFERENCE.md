# 📚 Quick Reference Guide - Gala Seating System

## 🚀 Getting Started (Choose One)

### Option 1: Quick Start Scripts (Easiest)

**Windows:**
```bash
start.bat
```

**Mac/Linux:**
```bash
./start.sh
```

### Option 2: Manual Setup

```bash
# Create virtual environment
python -m venv venv

# Activate it
source venv/bin/activate  # Mac/Linux
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Run application
python app.py
```

Access at: **http://localhost:5000**

---

## 🎫 Managing Tickets

### View Current Tickets

```python
python
>>> from app import app, db, Ticket
>>> with app.app_context():
>>>     tickets = Ticket.query.all()
>>>     for t in tickets[:5]:
>>>         print(f"{t.ticket_number}: {t.full_name} - Used: {t.is_used}")
```

### Add Tickets from CSV

**1. Create tickets.csv:**
```csv
ticket_number,full_name
GALA-0001,John Smith
GALA-0002,Jane Doe
```

**2. Import:**
```bash
python import_tickets.py
```

**3. Create sample CSV:**
```bash
python import_tickets.py --sample
```

**4. View statistics:**
```bash
python import_tickets.py --stats
```

### Add Tickets Manually

```python
from app import app, db, Ticket

with app.app_context():
    ticket = Ticket(
        ticket_number='VIP-001',
        full_name='John Smith'
    )
    db.session.add(ticket)
    db.session.commit()
```

---

## 🔧 Common Operations

### Reset All Assignments (Keep Tickets)

**Via Browser:**
```
http://localhost:5000/admin/reset-demo
```

**Via Python:**
```python
from app import app, db, TableAssignment, Ticket

with app.app_context():
    TableAssignment.query.delete()
    Ticket.query.update({'is_used': False, 'used_at': None})
    db.session.commit()
```

### View All Assignments

```python
from app import app, TableAssignment

with app.app_context():
    assignments = TableAssignment.query.all()
    for a in assignments:
        print(f"Table {a.table_number}: {a.full_name} ({a.ticket_number})")
```

### Check Table Occupancy

```python
from app import app, TableAssignment

with app.app_context():
    for table_num in range(1, 26):
        count = TableAssignment.query.filter_by(table_number=table_num).count()
        print(f"Table {table_num}: {count}/10 seats")
```

### Export Assignments to CSV

```python
from app import app, TableAssignment
import csv

with app.app_context():
    assignments = TableAssignment.query.order_by(
        TableAssignment.table_number, 
        TableAssignment.assigned_at
    ).all()
    
    with open('assignments.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Table', 'Name', 'Ticket', 'Assigned At'])
        for a in assignments:
            writer.writerow([a.table_number, a.full_name, a.ticket_number, a.assigned_at])
```

---

## 🎨 Customization

### Change Number of Tables/Seats

Edit `app.py`:
```python
TOTAL_TABLES = 30      # Change this
SEATS_PER_TABLE = 8    # Change this
```

### Change Color Scheme

Edit template files (`templates/*.html`), find the `<style>` section:
```css
/* Main gradient */
background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);

/* Change to your colors */
background: linear-gradient(135deg, #YOUR_COLOR1 0%, #YOUR_COLOR2 100%);
```

### Add Logo

Edit `templates/index.html`, add before `<h1>`:
```html
<img src="your-logo-url.png" alt="Logo" style="max-width: 200px; margin-bottom: 20px;">
```

---

## 🌐 Deployment Commands

### Deploy to Render

```bash
# Initialize git
git init
git add .
git commit -m "Initial commit"

# Push to GitHub
git remote add origin https://github.com/YOUR_USERNAME/gala-seating.git
git push -u origin main

# Then follow Render deployment steps in DEPLOYMENT.md
```

### Update Deployed App

```bash
# Make your changes
git add .
git commit -m "Update description"
git push

# Render/Railway auto-deploys from GitHub
```

### View Production Logs

**Render:**
- Dashboard → Your service → "Logs" tab

**Railway:**
- Project → Deployment → Logs

---

## 🐛 Troubleshooting

### Database is Locked

```bash
# Delete database and restart
rm gala_seating.db
python app.py
```

### Can't Connect to App

```bash
# Check if running
ps aux | grep python

# Kill old processes
killall python

# Restart
python app.py
```

### WebSocket Not Working

**Check browser console (F12):**
- Should see: "Connected to server"
- If not, verify Socket.IO library loaded

**Check server output:**
- Should see: "Client connected"

### Import Tickets Fails

```bash
# Check file exists
ls tickets.csv

# Check format
head -n 3 tickets.csv

# Should show:
# ticket_number,full_name
# GALA-0001,John Smith
# GALA-0002,Jane Doe
```

---

## 📊 Useful Queries

### Find All Used Tickets

```python
from app import app, Ticket

with app.app_context():
    used = Ticket.query.filter_by(is_used=True).all()
    for t in used:
        print(f"{t.ticket_number}: {t.full_name} - Used at {t.used_at}")
```

### Find Tickets By Name

```python
from app import app, Ticket

with app.app_context():
    results = Ticket.query.filter(Ticket.full_name.like('%Smith%')).all()
    for t in results:
        print(f"{t.ticket_number}: {t.full_name}")
```

### Count Assignments Per Table

```python
from app import app, db, TableAssignment
from sqlalchemy import func

with app.app_context():
    counts = db.session.query(
        TableAssignment.table_number,
        func.count(TableAssignment.id)
    ).group_by(TableAssignment.table_number).all()
    
    for table, count in counts:
        print(f"Table {table}: {count} guests")
```

---

## 🔐 Security Best Practices

### Generate Secure Secret Key

```python
import secrets
print(secrets.token_hex(32))
```

### Environment Variables (Production)

**Render/Railway:**
- Never commit secret keys to GitHub
- Add via platform dashboard
- Use environment variables

**Required variables:**
- `SECRET_KEY`: Generated token
- `DATABASE_URL`: Auto-set by database addon

---

## 📱 Testing on Mobile

### Test Locally on Phone

```bash
# Find your local IP
ipconfig getifaddr en0  # Mac
ip addr show            # Linux
ipconfig               # Windows

# Run app
python app.py

# Access from phone on same WiFi
http://YOUR_IP:5000
```

### Test Production

Simply visit your deployed URL on mobile browser.

---

## 💾 Backup & Restore

### Backup Database (SQLite)

```bash
cp gala_seating.db gala_seating_backup_$(date +%Y%m%d).db
```

### Restore Database

```bash
cp gala_seating_backup_20250115.db gala_seating.db
```

### Export PostgreSQL (Production)

**Render:**
```bash
# Get connection URL from dashboard
pg_dump DATABASE_URL > backup.sql
```

---

## 🎯 Performance Tips

### Speed Up Development

```bash
# Use SQLite for development (default)
# Faster startup, no external database needed
python app.py
```

### Optimize for Production

1. Use PostgreSQL
2. Enable connection pooling
3. Add caching for table status
4. Use CDN for static assets

---

## 📝 Common File Locations

- **Application**: `app.py`
- **Templates**: `templates/*.html`
- **Requirements**: `requirements.txt`
- **Database** (dev): `gala_seating.db`
- **Tickets Import**: `import_tickets.py`
- **Documentation**: `README.md`, `DEPLOYMENT.md`, `ARCHITECTURE.md`

---

## ⚡ Quick Commands Reference

| Task | Command |
|------|---------|
| Start app | `python app.py` |
| Run tests | `python test_app.py` |
| Import tickets | `python import_tickets.py` |
| Create sample CSV | `python import_tickets.py --sample` |
| View stats | `python import_tickets.py --stats` |
| Reset demo | Visit `/admin/reset-demo` |
| Activate venv (Mac/Linux) | `source venv/bin/activate` |
| Activate venv (Windows) | `venv\Scripts\activate` |
| Install deps | `pip install -r requirements.txt` |

---

## 🆘 Need More Help?

1. **Check logs**: Look at application output for errors
2. **Read docs**: See `README.md` for full documentation
3. **Test locally**: Always test changes locally first
4. **Review code**: Application is well-commented
5. **Deployment guide**: See `DEPLOYMENT.md` for hosting help

---

## ✅ Pre-Event Checklist

- [ ] All tickets imported to database
- [ ] Test ticket validation (try valid/invalid tickets)
- [ ] Test seat assignment (assign and verify)
- [ ] Test real-time updates (open 2 browser windows)
- [ ] Test on mobile device
- [ ] Deploy to production
- [ ] Test production URL
- [ ] Share link with test users
- [ ] Monitor logs for errors
- [ ] Prepare backup plan

---

## 🎉 You're Ready!

This system is now fully operational and ready to manage your gala seating. The real-time WebSocket updates ensure all guests see accurate availability, and atomic transactions prevent double-booking.

Good luck with your event! 🎊
