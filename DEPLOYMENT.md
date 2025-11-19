# 🚀 Complete Deployment Guide - Gala Seating System

This guide will walk you through deploying your Gala Seating System to a free hosting platform.

## 📌 Prerequisites

- GitHub account (free)
- Render account (free) OR Railway account (free)
- Your gala seating code

## 🎯 Option 1: Deploy to Render (Recommended - Easiest)

### Step 1: Prepare Your GitHub Repository

1. **Create a GitHub account** (if you don't have one)
   - Go to https://github.com
   - Click "Sign up"

2. **Create a new repository**
   - Click the "+" icon → "New repository"
   - Name: `gala-seating`
   - Description: "Real-time gala seating system"
   - Make it **Public** (required for free tier)
   - Do NOT initialize with README
   - Click "Create repository"

3. **Upload your code to GitHub**
   
   **Option A: Using Git (if installed)**
   ```bash
   cd gala-seating
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/gala-seating.git
   git push -u origin main
   ```

   **Option B: Using GitHub Web Interface**
   - On your repository page, click "uploading an existing file"
   - Drag and drop all files from gala-seating folder
   - Click "Commit changes"

### Step 2: Deploy on Render

1. **Create Render account**
   - Go to https://render.com
   - Click "Get Started"
   - Sign up with GitHub (recommended)

2. **Create new Web Service**
   - Click "New +" → "Web Service"
   - Click "Connect GitHub"
   - Find and select your `gala-seating` repository
   - Click "Connect"

3. **Configure the service**
   - **Name**: `gala-seating` (or your custom name)
   - **Region**: Select closest to you
   - **Branch**: `main`
   - **Root Directory**: Leave empty
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn --worker-class eventlet -w 1 app:app`

4. **Select plan**
   - Choose **Free** tier
   - Click "Advanced" to expand

5. **Add Environment Variables**
   Click "Add Environment Variable" and add:
   
   **SECRET_KEY**
   - Key: `SECRET_KEY`
   - Value: Generate one using Python:
     ```python
     python -c "import secrets; print(secrets.token_hex(32))"
     ```
   - Copy the output and paste as value

6. **Create Web Service**
   - Click "Create Web Service"
   - Wait 5-10 minutes for deployment

### Step 3: Add PostgreSQL Database

1. **Create database**
   - In Render dashboard, click "New +" → "PostgreSQL"
   - **Name**: `gala-seating-db`
   - **Database**: `gala_seating`
   - **User**: `gala_user`
   - **Region**: Same as your web service
   - **PostgreSQL Version**: 15
   - **Plan**: Free
   - Click "Create Database"

2. **Link database to web service**
   - Wait for database to finish creating
   - Copy the "Internal Database URL"
   - Go to your web service → "Environment"
   - Click "Add Environment Variable"
   - Key: `DATABASE_URL`
   - Value: Paste the Internal Database URL
   - Click "Save Changes"

3. **Restart service**
   - Render will automatically redeploy
   - Wait for deployment to complete

### Step 4: Access Your Application

Your app will be live at:
```
https://gala-seating.onrender.com
```
(Replace with your actual service name)

**Important Notes:**
- Free tier sleeps after 15 minutes of inactivity
- First request after sleep takes 30-60 seconds
- Upgrade to paid tier ($7/month) for always-on

---

## 🎯 Option 2: Deploy to Railway

### Step 1: Prepare GitHub (same as Render Step 1)

### Step 2: Deploy on Railway

1. **Create Railway account**
   - Go to https://railway.app
   - Click "Login with GitHub"
   - Authorize Railway

2. **Create new project**
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Find your `gala-seating` repository
   - Click on it

3. **Configure deployment**
   Railway auto-detects Python!
   - It will automatically use `requirements.txt`
   - It will automatically use `Procfile`

4. **Add environment variables**
   - Click "Variables" tab
   - Click "New Variable"
   - Add `SECRET_KEY`:
     ```python
     python -c "import secrets; print(secrets.token_hex(32))"
     ```

5. **Add PostgreSQL**
   - Click "New" → "Database" → "Add PostgreSQL"
   - Railway automatically creates `DATABASE_URL` variable

6. **Generate domain**
   - Click "Settings" tab
   - Click "Generate Domain"
   - Your app will be at: `https://gala-seating-production.up.railway.app`

### Step 3: Deploy!

Railway deploys automatically. Wait 3-5 minutes.

---

## 🎯 Option 3: Deploy to Heroku (Classic Option)

### Step 1: Prepare GitHub (same as Render)

### Step 2: Deploy on Heroku

1. **Create Heroku account**
   - Go to https://heroku.com
   - Sign up for free

2. **Install Heroku CLI** (optional)
   - Download from https://devcenter.heroku.com/articles/heroku-cli

3. **Create new app**
   - Dashboard → "New" → "Create new app"
   - App name: `gala-seating` (must be unique globally)
   - Region: Choose closest
   - Click "Create app"

4. **Connect GitHub**
   - "Deploy" tab
   - Deployment method: "GitHub"
   - Search for `gala-seating`
   - Click "Connect"

5. **Add PostgreSQL**
   - "Resources" tab
   - Add-ons → Search "Heroku Postgres"
   - Select "Heroku Postgres"
   - Plan: "Hobby Dev - Free"
   - Submit Order Form

6. **Set environment variables**
   - "Settings" tab → "Config Vars" → "Reveal Config Vars"
   - Add `SECRET_KEY` (generate as shown before)
   - `DATABASE_URL` is auto-added by Postgres addon

7. **Deploy**
   - "Deploy" tab
   - Scroll to "Manual deploy"
   - Select branch: `main`
   - Click "Deploy Branch"

Your app: `https://gala-seating.herokuapp.com`

**Note**: Heroku free tier has limited hours per month.

---

## 🎫 Adding Your Real Tickets

After deployment, you need to add your actual ticket data.

### Method 1: Modify app.py Before Deployment

Edit `init_database()` function in `app.py`:

```python
def init_database():
    with app.app_context():
        db.create_all()
        
        if Ticket.query.count() == 0:
            # Your real tickets
            tickets = [
                Ticket(ticket_number='VIP-001', full_name='John Smith'),
                Ticket(ticket_number='VIP-002', full_name='Jane Doe'),
                # Add all your tickets here
            ]
            
            db.session.bulk_save_objects(tickets)
            db.session.commit()
```

Then redeploy.

### Method 2: Import from CSV (Recommended)

1. Create `import_tickets.py` (already in project)

2. Create `tickets.csv`:
   ```csv
   ticket_number,full_name
   GALA-001,John Smith
   GALA-002,Jane Doe
   GALA-003,Bob Johnson
   ```

3. Run locally first to test:
   ```bash
   python import_tickets.py
   ```

4. For production, use Render Shell:
   - Go to your service in Render
   - Click "Shell" tab
   - Upload `tickets.csv`
   - Run: `python import_tickets.py`

---

## 🔧 Post-Deployment Configuration

### Custom Domain (Optional)

**Render:**
- Service → Settings → Custom Domain
- Add your domain
- Update DNS records as shown

**Railway:**
- Settings → Custom Domain
- Add domain and update DNS

### Email Notifications (Optional)

Add to `app.py`:

```python
from flask_mail import Mail, Message

app.config.update(
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USERNAME=os.environ.get('MAIL_USERNAME'),
    MAIL_PASSWORD=os.environ.get('MAIL_PASSWORD')
)

mail = Mail(app)
```

Add environment variables for email credentials.

---

## 📊 Monitoring Your Application

### Render Logs
- Dashboard → Your service → "Logs" tab
- See real-time application logs

### Railway Logs
- Project → "Deployments" → Click on deployment
- See build and runtime logs

### Database Access

**Render:**
- Dashboard → Database → "Connect"
- Use provided credentials with any PostgreSQL client

**Railway:**
- Database → "Connect" tab
- Copy connection URL

---

## 🐛 Common Issues & Solutions

### Issue: "Application error" or crash

**Solution:**
1. Check logs in hosting platform
2. Verify environment variables are set
3. Ensure DATABASE_URL is correct
4. Check Python version matches runtime.txt

### Issue: Database connection failed

**Solution:**
1. Verify DATABASE_URL environment variable
2. Ensure database is in same region as app
3. Check database is running (not paused)

### Issue: WebSockets not working

**Solution:**
1. Ensure using `eventlet` worker
2. Check start command: `gunicorn --worker-class eventlet -w 1 app:app`
3. Verify Socket.IO client version matches server

### Issue: Tickets not loading

**Solution:**
1. Run database initialization
2. Check if tickets were imported
3. Access shell and run:
   ```python
   from app import app, db, Ticket
   with app.app_context():
       print(Ticket.query.count())
   ```

---

## ✅ Deployment Checklist

Before going live:

- [ ] All code uploaded to GitHub
- [ ] Web service deployed and running
- [ ] PostgreSQL database created and linked
- [ ] Environment variables set (SECRET_KEY, DATABASE_URL)
- [ ] Real tickets imported to database
- [ ] Test ticket validation works
- [ ] Test real-time updates work (open 2 browsers)
- [ ] Test on mobile device
- [ ] Verify confirmation emails (if configured)
- [ ] Share URL with test users
- [ ] Monitor logs for any errors

---

## 🎉 You're Live!

Your Gala Seating System is now deployed and ready for your event!

**Share this URL with your guests:**
- Render: `https://your-service-name.onrender.com`
- Railway: `https://your-app.up.railway.app`
- Heroku: `https://your-app.herokuapp.com`

**Need help?**
- Check application logs in your hosting platform
- Review the troubleshooting section
- Test locally first before blaming the deployment

Good luck with your gala! 🎊
