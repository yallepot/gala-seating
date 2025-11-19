# 🎊 Gala Seating System

A complete, production-ready Python web application for managing gala seating with real-time updates using WebSockets. Designed for 25 tables with 10 seats each.

## ✨ Features

- **Real-Time Updates**: WebSocket integration ensures all users see instant seat availability changes
- **Ticket Validation**: Verifies ticket numbers against a secure database
- **Atomic Transactions**: Prevents race conditions when multiple users select seats simultaneously
- **Mobile Optimized**: Fully responsive design works on all devices
- **Free Hosting Ready**: Configured for deployment on Render, Heroku, or Railway

## 🏗️ Architecture

### Backend (Python/Flask)
- **Flask**: Web framework
- **Flask-SocketIO**: Real-time WebSocket communication
- **SQLAlchemy**: Database ORM with atomic transactions
- **PostgreSQL**: Production database (SQLite for local development)

### Frontend
- Pure HTML/CSS/JavaScript (no framework required)
- Socket.IO client for real-time updates
- Mobile-first responsive design

## 📋 Requirements

- Python 3.11+
- PostgreSQL (for production) or SQLite (for local)

## 🚀 Quick Start (Local Development)

### 1. Clone and Setup

```bash
# Navigate to project directory
cd gala-seating

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Initialize Database

```bash
python app.py
```

This will:
- Create the SQLite database
- Generate 250 sample tickets (GALA-0001 through GALA-0250)
- Start the application on http://localhost:5000

### 3. Test the Application

Open your browser to `http://localhost:5000` and:
1. Register with sample tickets (e.g., GALA-0001, GALA-0002)
2. Select seats at different tables
3. Open a second browser window to see real-time updates

## 🌐 Deployment to Render (FREE)

### Step 1: Prepare Your Code

1. Ensure all files are in your project directory
2. Initialize git repository:

```bash
git init
git add .
git commit -m "Initial commit"
```

### Step 2: Create GitHub Repository

1. Go to https://github.com and create a new repository
2. Push your code:

```bash
git remote add origin https://github.com/YOUR_USERNAME/gala-seating.git
git branch -M main
git push -u origin main
```

### Step 3: Deploy on Render

1. Go to https://render.com and sign up/login
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Configure:
   - **Name**: gala-seating
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn --worker-class eventlet -w 1 app:app`
   - **Instance Type**: Free

5. Add Environment Variables:
   - Click "Advanced" → "Add Environment Variable"
   - Add: `DATABASE_URL` (Render will auto-configure PostgreSQL)
   - Add: `SECRET_KEY` = (generate with: `python -c "import secrets; print(secrets.token_hex(32))"`)

6. Click "Create Web Service"

### Step 4: Add PostgreSQL Database

1. In Render dashboard, click "New +" → "PostgreSQL"
2. Configure:
   - **Name**: gala-seating-db
   - **Database**: gala_seating
   - **Instance Type**: Free
3. Click "Create Database"
4. Copy the "Internal Database URL"
5. Go back to your web service → Environment → Edit `DATABASE_URL` → Paste the URL

### Step 5: Deploy!

Render will automatically deploy. Your app will be available at:
`https://gala-seating.onrender.com` (or your custom name)

**Note**: Free tier spins down after 15 minutes of inactivity and takes 30-60 seconds to restart.

## 🎯 Alternative: Deploy to Railway (FREE)

### Step 1: Prepare Repository
(Same as Render Step 1-2)

### Step 2: Deploy on Railway

1. Go to https://railway.app and sign up
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your repository
4. Railway auto-detects Python and deploys
5. Click "Add Variable" and add:
   - `SECRET_KEY` = (generate random string)
6. Add PostgreSQL:
   - Click "New" → "Database" → "Add PostgreSQL"
   - Railway auto-links the DATABASE_URL

Your app will be at: `https://gala-seating-production.up.railway.app`

## 📁 Project Structure

```
gala-seating/
├── app.py                  # Main Flask application
├── requirements.txt        # Python dependencies
├── Procfile               # Deployment configuration
├── runtime.txt            # Python version
├── .gitignore            # Git ignore rules
├── README.md             # This file
└── templates/
    ├── index.html        # Ticket registration page
    ├── seating.html      # Real-time seating selection
    ├── confirmation.html # Confirmation page
    └── error.html        # Error page
```

## 🎫 Managing Tickets

### Adding Real Tickets

Edit `app.py` and modify the `init_database()` function:

```python
def init_database():
    with app.app_context():
        db.create_all()
        
        if Ticket.query.count() == 0:
            # Import your real ticket data
            real_tickets = [
                {'ticket_number': 'VIP-001', 'full_name': 'John Smith'},
                {'ticket_number': 'VIP-002', 'full_name': 'Jane Doe'},
                # ... add all your tickets
            ]
            
            for ticket_data in real_tickets:
                ticket = Ticket(
                    ticket_number=ticket_data['ticket_number'],
                    full_name=ticket_data['full_name']
                )
                db.session.add(ticket)
            
            db.session.commit()
```

### Importing from CSV

Create `import_tickets.py`:

```python
import csv
from app import app, db, Ticket

def import_from_csv(filename):
    with app.app_context():
        with open(filename, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                ticket = Ticket(
                    ticket_number=row['ticket_number'],
                    full_name=row['full_name']
                )
                db.session.add(ticket)
        db.session.commit()
        print(f"Imported tickets from {filename}")

if __name__ == '__main__':
    import_from_csv('tickets.csv')
```

CSV format:
```csv
ticket_number,full_name
GALA-001,John Smith
GALA-002,Jane Doe
```

## 🔧 Configuration

### Customizing Table/Seat Numbers

In `app.py`, modify:

```python
TOTAL_TABLES = 25        # Change number of tables
SEATS_PER_TABLE = 10     # Change seats per table
```

### Security

The app uses:
- **Session-based validation**: Prevents unauthorized seat assignments
- **Atomic transactions**: Prevents race conditions
- **Server-side validation**: All ticket checks happen on backend
- **CSRF protection**: Built into Flask sessions

## 🐛 Troubleshooting

### Database Issues

**Problem**: "Could not connect to database"
**Solution**: Check DATABASE_URL environment variable

**Problem**: "Table doesn't exist"
**Solution**: Delete database and restart app to recreate

### WebSocket Issues

**Problem**: "Real-time updates not working"
**Solution**: Ensure Socket.IO client version matches server (4.5.4)

### Deployment Issues

**Problem**: App crashes on Render
**Solution**: Check logs in Render dashboard → "Logs" tab

## 📊 Admin Features

### Reset Demo Data

Visit: `/admin/reset-demo`

This will:
- Clear all seat assignments
- Reset all tickets to unused
- Broadcast updates to all connected clients

### View Database (Development)

```bash
python
>>> from app import app, db, Ticket, TableAssignment
>>> with app.app_context():
>>>     print(f"Total tickets: {Ticket.query.count()}")
>>>     print(f"Used tickets: {Ticket.query.filter_by(is_used=True).count()}")
>>>     print(f"Assignments: {TableAssignment.query.count()}")
```

## 🎨 Customization

### Branding

Edit templates to change:
- Colors in `<style>` sections
- Logo/title in headers
- Text content

### Email Notifications

Add to `app.py` after successful assignment:

```python
from flask_mail import Mail, Message

# Configure mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')

mail = Mail(app)

# In assign_seats_api() after success:
msg = Message('Gala Seating Confirmation',
              recipients=['guest@example.com'])
msg.body = f'Your seats: {assignments}'
mail.send(msg)
```

## 📝 License

This is a custom application. Modify as needed for your event.

## 🤝 Support

For issues or questions:
1. Check the Troubleshooting section
2. Review application logs
3. Verify environment variables are set correctly

## 🎉 Ready to Use!

Your gala seating system is now ready. The application handles:
- ✅ Ticket validation
- ✅ Real-time seat availability
- ✅ Atomic seat assignments
- ✅ Mobile-friendly interface
- ✅ Free hosting deployment

Perfect for your 25-table, 250-guest gala event!
