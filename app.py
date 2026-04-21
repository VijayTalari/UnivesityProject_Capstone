from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message

app = Flask(__name__)
app.secret_key = "supersecretkey"

# Email configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'helpdesk.praneeth@gmail.com'
app.config['MAIL_PASSWORD'] = 'hxvvwbnzlqjqlzmq'

mail = Mail(app)

def send_ticket_email(to_email, subject, body):

    msg = Message(
        subject,
        sender=app.config['MAIL_USERNAME'],
        recipients=[to_email]
    )

    msg.body = body

    mail.send(msg)

# SQLite configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# -------------------------
# User Model
# -------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)

from datetime import datetime

# -------------------------
# Ticket Model
# -------------------------
class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    priority = db.Column(db.String(50), nullable=False, default="Medium")
    status = db.Column(db.String(50), nullable=False, default="Open")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('tickets', lazy=True))

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    sender_id = db.Column(db.Integer)   # who triggered
    receiver_id = db.Column(db.Integer) # who gets it

    message = db.Column(db.String(255))
    is_read = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

def notify(sender_id, receiver_id, message):
    n = Notification(
        sender_id=sender_id,
        receiver_id=receiver_id,
        message=message
    )
    db.session.add(n)
    db.session.commit()

    # -------------------------
# AI Helper Functions
# -------------------------

def detect_intent(message):
    message = message.lower()

    # Greeting
    if any(word in message for word in ["hi", "hello", "hey"]):
        return "greeting"

    # Knowledge
    if any(word in message for word in ["how", "what", "help", "guide"]):
        return "knowledge"

    # ✅ IMPROVED ISSUE DETECTION (THIS IS THE FIX)
    if any(word in message for word in [
        # network
        "vpn", "network", "internet", "wifi", "slow", "connection",

        # access
        "password", "login", "access", "permission",

        # hardware
        "laptop", "keyboard", "mouse", "screen", "battery",

        # software
        "software", "app", "application", "error", "crash",

        # general
        "issue", "problem", "not working", "fail"
    ]):
        return "issue"

    return "unknown"


from sqlalchemy import or_

def search_knowledge_base(message):
    message = message.lower()

    # ✅ Important keywords only
    keywords = [
        "email", "vpn", "network", "internet", "wifi",
        "login", "password", "access",
        "software", "application", "app",
        "laptop", "keyboard", "mouse",
        "error", "issue", "problem"
    ]

    matched_words = [word for word in keywords if word in message]

    if not matched_words:
        return []

    filters = []
    for word in matched_words:
        filters.append(Article.title.ilike(f"%{word}%"))
        filters.append(Article.content.ilike(f"%{word}%"))

    return Article.query.filter(or_(*filters)).all()

def get_ai_response(message):
    message = message.lower()

    # Greetings
    if any(word in message for word in ["hi", "hello", "hey"]):
        return "Hello 👋 How can I assist you today?"

    # VPN / Network
    elif any(word in message for word in ["vpn", "network", "internet"]):
        return "It seems like a network issue 🌐. Try restarting your router or reconnecting VPN."

    # Password issues
    elif "password" in message:
        return "You can reset your password using Ctrl+Alt+Delete or contact admin."

    # Software issues
    elif "software" in message or "sap" in message or "login" in message:
        return "Try restarting the application or clearing cache."

    # Hardware issues
    elif "laptop" in message or "keyboard" in message:
        return "Please check hardware connections or restart your device."

    # General help
    elif "help" in message:
        return "Please describe your issue. I will try to assist or create a ticket."

    # Default
    else:
        return "I'm analyzing your issue 🤖. Can you please provide more details?"

class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    content = db.Column(db.Text)
    category = db.Column(db.String(100))

# Create database
with app.app_context():
    db.create_all()

# -------------------------
# ROUTES
# -------------------------
# -------------------------
# AI Ticket Classification
# -------------------------

def classify_ticket(description):
    description = description.lower()

    # Category detection
    if any(word in description for word in ["vpn", "network", "internet", "wifi"]):
        category = "Network"
    elif any(word in description for word in ["sap", "application", "software", "login"]):
        category = "Software"
    elif any(word in description for word in ["laptop", "keyboard", "mouse", "hardware"]):
        category = "Hardware"
    elif any(word in description for word in ["access", "permission", "password"]):
        category = "Access"
    else:
        category = "Software"

    # Priority detection
    if any(word in description for word in ["urgent", "immediately", "critical", "asap"]):
        priority = "High"
    elif any(word in description for word in ["slow", "minor", "later", "small"]):
        priority = "Low"
    else:
        priority = "Medium"

    return category, priority

@app.route("/")
def home():
    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        role = request.form.get("role")

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("Email already exists!")
            return redirect(url_for("signup"))

        hashed_password = generate_password_hash(password)

        new_user = User(email=email, password=hashed_password, role=role)
        db.session.add(new_user)
        db.session.commit()

        flash("Signup successful! Please login.")
        return redirect(url_for("home"))

    return render_template("signup.html")

@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("email")
    password = request.form.get("password")
    role = request.form.get("role")

    user = User.query.filter_by(email=email).first()

    if user and check_password_hash(user.password, password):
        if user.role == role:
            session["user_id"] = user.id   # 🔥 IMPORTANT FIX
            session["user"] = user.email
            session["role"] = user.role

            if role == "admin":
                return redirect("/admin")
            else:
                return redirect("/user")
        else:
            flash("Role mismatch!")
    else:
        flash("Invalid credentials!")

    return redirect(url_for("home"))
# -------------------------
# Raise Ticket
# -------------------------

@app.route("/raise-ticket", methods=["GET", "POST"])
def raise_ticket():
    if "user" not in session:
        return redirect(url_for("home"))

    if request.method == "POST":
        description = request.form.get("description")
        # AI Classification
        category, priority = classify_ticket(description)

        # Get logged-in user
        user = User.query.filter_by(email=session["user"]).first()

        new_ticket = Ticket(
            user_id=user.id,
            description=description,
            category=category,
            priority=priority,
            status="Open"
        )

        db.session.add(new_ticket)
        db.session.commit()

        admins = User.query.filter_by(role="admin").all()

        for admin in admins:
            notify(user.id, admin.id, f"🆕 New ticket raised: #{new_ticket.id}")

        email_body = f"""
        Hello,

        Your ticket has been created successfully.

        Description: {description}
        Category: {category}
        Priority: {priority}
        Status: Open

        Thank you,
        Smart Helpdesk System
        """

        send_ticket_email(
            session["user"],
            "Smart Helpdesk - Ticket Created",
            email_body
        )

        flash("Ticket raised successfully!")
        return redirect(url_for("user_dashboard"))

    return render_template("raise_ticket.html")

# -------------------------
# My Tickets Page
# -------------------------

@app.route("/my-tickets")
def my_tickets():
    if "user" not in session:
        return redirect(url_for("home"))

    user = User.query.filter_by(email=session["user"]).first()

    tickets = Ticket.query.filter_by(user_id=user.id) \
                          .order_by(Ticket.created_at.desc()) \
                          .all()

    return render_template("my_tickets.html", tickets=tickets)

@app.route("/user")
def user_dashboard():

    # ✅ Check login
    if "user" not in session:
        return redirect(url_for("home"))

    # ✅ Get user
    user = User.query.filter_by(email=session["user"]).first()

    # ✅ Tickets
    tickets = Ticket.query.filter_by(user_id=user.id).all()

    total_tickets = len(tickets)
    in_progress = len([t for t in tickets if t.status == "In Progress"])
    resolved = len([t for t in tickets if t.status == "Resolved"])

    recent_tickets = Ticket.query.filter_by(user_id=user.id) \
        .order_by(Ticket.created_at.desc()) \
        .limit(3).all()

    # ✅ FIX: get user_id FIRST
    receiver_id = session.get("user_id")

    if not receiver_id:
        return redirect(url_for("home"))

    # ✅ Notifications
    notifications = Notification.query.filter_by(
        receiver_id=receiver_id
    ).order_by(Notification.created_at.desc()).limit(5).all()

    unread_count = Notification.query.filter_by(
        receiver_id=receiver_id,
        is_read=False
    ).count()

    return render_template(
        "user_dashboard.html",
        email=session["user"],
        total_tickets=total_tickets,
        in_progress=in_progress,
        resolved=resolved,
        recent_tickets=recent_tickets,
        notifications=notifications,
        unread_count=unread_count
    )

@app.route("/mark-notifications-read")
def mark_notifications_read():
    if "user_id" not in session:
        return redirect(url_for("home"))

    Notification.query.filter_by(
        receiver_id=session["user_id"],
        is_read=False
    ).update({"is_read": True})

    db.session.commit()

    return "", 204  # no content

@app.route("/search-kb")
def search_kb():
    query = request.args.get("q", "")

    if not query:
        return {"results": []}

    articles = KnowledgeBase.query.filter(
        KnowledgeBase.title.ilike(f"%{query}%") |
        KnowledgeBase.content.ilike(f"%{query}%")
    ).limit(5).all()

    results = []
    for a in articles:
        results.append({
            "title": a.title,
            "content": a.content[:120]
        })

    return {"results": results}

# -------------------------
# Admin - View & Manage Tickets
# -------------------------

from sqlalchemy import or_

@app.route("/admin-tickets", methods=["GET", "POST"])
def admin_tickets():
    if "user" not in session or session["role"] != "admin":
        return redirect(url_for("home"))

    if request.method == "POST":
        ticket_id = request.form.get("ticket_id")
        new_status = request.form.get("status")
        new_priority = request.form.get("priority")

        ticket = Ticket.query.get(ticket_id)
        if ticket:
            ticket.status = new_status
            ticket.priority = new_priority
            db.session.commit()

            # 🔔 ADD THIS (IMPORTANT)
            notify(
                session.get("user_id"),   # admin (sender)
                ticket.user_id,       # user (receiver)
                f"🔄 Your ticket #{ticket.id} updated → Status: {ticket.status}, Priority: {ticket.priority}"
            )
            email_body = f"""
            Hello,

            Your ticket #{ticket.id} has been updated.

            Status: {ticket.status}
            Priority: {ticket.priority}

            Thank you,
            Smart Helpdesk System
            """

            send_ticket_email(
                ticket.user.email,
                "Smart Helpdesk - Ticket Updated",
                email_body
            )

        return redirect(url_for("admin_tickets"))

    # Get filters
    status_filter = request.args.get("status")
    priority_filter = request.args.get("priority")
    category_filter = request.args.get("category")
    search_query = request.args.get("search")

    query = Ticket.query

    if status_filter and status_filter != "All":
        query = query.filter_by(status=status_filter)

    if priority_filter and priority_filter != "All":
        query = query.filter_by(priority=priority_filter)

    if category_filter and category_filter != "All":
        query = query.filter_by(category=category_filter)

    if search_query:
        query = query.filter(
            or_(
                Ticket.description.ilike(f"%{search_query}%"),
                Ticket.category.ilike(f"%{search_query}%")
            )
        )

    tickets = query.order_by(Ticket.created_at.desc()).all()

    return render_template("admin_tickets.html", tickets=tickets)

@app.route('/assign-tickets', methods=['GET', 'POST'])
def assign_tickets():

    # ✅ FIX: check correct session key
    if "user" not in session or session.get("role") != "admin":
        return redirect('/')

    if request.method == 'POST':
        ticket_id = request.form.get('ticket_id')
        assigned_to = request.form.get('assigned_to')

        if ticket_id and assigned_to:
            ticket = Ticket.query.get(ticket_id)
            ticket.assigned_to = assigned_to
            db.session.commit()

            notify(session.get("user_id"), ticket.user_id,
                f"📌 Your ticket #{ticket.id} has been assigned")

    tickets = Ticket.query.all()
    admins = User.query.filter_by(role='admin').all()

    return render_template(
        'assign_tickets.html',
        tickets=tickets,
        admins=admins
    )

@app.route('/admin-knowledge-base', methods=['GET', 'POST'])
def admin_kb():

    if "user" not in session or session.get("role") != "admin":
        return redirect('/')

    if request.method == "POST":
        title = request.form.get("title")
        content = request.form.get("content")
        category = request.form.get("category")

        new_article = Article(
            title=title,
            content=content,
            category=category
        )

        db.session.add(new_article)
        db.session.commit()

    articles = Article.query.all()

    return render_template("knowledge_base.html", articles=articles)

@app.route('/delete-article/<int:id>')
def delete_article(id):

    article = Article.query.get(id)
    db.session.delete(article)
    db.session.commit()

    return redirect('/admin-knowledge-base')

@app.route('/edit-article/<int:id>', methods=['GET', 'POST'])
def edit_article(id):

    article = Article.query.get(id)

    if request.method == "POST":
        article.title = request.form.get("title")
        article.content = request.form.get("content")
        article.category = request.form.get("category")

        db.session.commit()
        return redirect('/admin-knowledge-base')

    return render_template("edit_article.html", article=article)

from sqlalchemy import or_

@app.route('/user-knowledge-base')
def user_kb():

    query = request.args.get('search')

    if query:
        message = query.lower()

        # ✅ keywords list
        keywords = [
            "email", "vpn", "network", "internet", "wifi",
            "login", "password", "access",
            "software", "application", "app",
            "laptop", "keyboard", "mouse",
            "error", "system"
        ]

        matched_words = [word for word in keywords if word in message]

        if matched_words:
            filters = []
            for word in matched_words:
                filters.append(Article.title.ilike(f"%{word}%"))
                filters.append(Article.content.ilike(f"%{word}%"))

            articles = Article.query.filter(or_(*filters)).all()
        else:
            articles = []

    else:
        articles = Article.query.all()

    return render_template(
        "user_knowledge_base.html",
        articles=articles,
        query=query
    )
@app.route("/chatbot", methods=["GET", "POST"])
def chatbot():
    if "user" not in session:
        return redirect(url_for("home"))

    if "chat_history" not in session:
        session["chat_history"] = []

    if request.method == "POST":

        message = request.form.get("message")

        # Store user message
        session["chat_history"].append({"sender": "user", "text": message})

        # Get AI response
        ai_reply = get_ai_response(message)

        # Try knowledge base also
        articles = search_knowledge_base(message)

        if articles:
            kb_text = "\n\n📚 Suggested Solutions:\n"

            for a in articles:
                kb_text += f"\n🔹 {a.title}\n{a.content[:150]}...\n"

            ai_reply = kb_text   # ✅ PRIORITIZE KB over AI

        message_lower = message.lower()
        intent = detect_intent(message)

        # ✅ STEP 1: Greeting → STOP everything
        if intent == "greeting":
            reply = "Hello 👋 How can I assist you today?"

        # ✅ STEP 2: YES → create ticket
        elif message_lower in ["yes", "create ticket"]:
            pending_issue = session.get("pending_issue")

            if pending_issue:
                category, priority = classify_ticket(pending_issue)

                user = User.query.filter_by(email=session["user"]).first()

                new_ticket = Ticket(
                    user_id=user.id,
                    description=pending_issue,
                    category=category,
                    priority=priority,
                    status="Open"
                )

                db.session.add(new_ticket)
                db.session.commit()

                admins = User.query.filter_by(role="admin").all()
                for admin in admins:
                    notify(user.id, admin.id, f"🆕 New ticket raised: #{new_ticket.id}")

                session.pop("pending_issue")

                reply = f"✅ Ticket created!\nCategory: {category}, Priority: {priority}"

            else:
                reply = "No issue found to create ticket."

        # ❌ NO → cancel
        elif message_lower == "no":
            session.pop("pending_issue", None)
            reply = "👍 Okay, no ticket created."

        # ✅ STEP 3: ISSUE → NOW search KB
        elif intent == "issue":

            articles = search_knowledge_base(message)

            if articles:
                kb_text = "\n\n📚 Suggested Solutions:\n"
                for a in articles:
                    kb_text += f"\n🔹 {a.title}\n{a.content[:150]}...\n"

                reply = f"""{kb_text}

        👉 Do you want me to create a ticket? (yes/no)
        """
            else:
                ai_reply = get_ai_response(message)

                reply = f"""{ai_reply}

        👉 Do you want me to create a ticket? (yes/no)
        """

            session["pending_issue"] = message

        # ✅ DEFAULT
        else:
            reply = get_ai_response(message)


        # ✅ ALWAYS STORE BOT MESSAGE
        session["chat_history"].append({"sender": "bot", "text": reply})
        session.modified = True

    return render_template("chatbot.html", chat_history=session["chat_history"])

from datetime import datetime

@app.route("/admin")
def admin_dashboard():
    if "user" not in session or session["role"] != "admin":
        return redirect(url_for("home"))

    tickets = Ticket.query.all()

    open_count = len([t for t in tickets if t.status == "Open"])
    progress_count = len([t for t in tickets if t.status == "In Progress"])
    high_priority = len([t for t in tickets if t.priority == "High"])
    resolved_count = Ticket.query.filter_by(status="Resolved").count()


    recent_tickets = Ticket.query.order_by(
        Ticket.created_at.desc()
    ).limit(5).all()

    # Count by category
    category_counts = {}
    for t in tickets:
        category_counts[t.category] = category_counts.get(t.category, 0) + 1

    notifications = Notification.query.filter_by(
    receiver_id=session.get("user_id")
    ).order_by(Notification.created_at.desc()).limit(5).all()

    unread_count = Notification.query.filter_by(
        receiver_id=session.get("user_id"),
        is_read=False
    ).count()

    low_count = Ticket.query.filter_by(priority="Low").count()
    medium_count = Ticket.query.filter_by(priority="Medium").count()
    high_count = Ticket.query.filter_by(priority="High").count()

    from sqlalchemy import func

    tickets_by_day = db.session.query(
        func.date(Ticket.created_at),
        func.count(Ticket.id)
    ).group_by(func.date(Ticket.created_at)).all()

    dates = [str(t[0]) for t in tickets_by_day]
    counts = [t[1] for t in tickets_by_day]

    return render_template(
        "admin_dashboard.html",
        email=session["user"],
        open_count=open_count,
        progress_count=progress_count,
        high_priority=high_priority,
        recent_tickets=recent_tickets,
        category_counts=category_counts,
        notifications=notifications,
        unread_count=unread_count,
        resolved_count=resolved_count,
        dates=dates,
        counts=counts,
        low_count=low_count,
        medium_count=medium_count,
        high_count=high_count
    )

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(debug=True)