import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime



app = Flask(__name__)
app.secret_key = "supersecretkey"
UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def update_ads_table():
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        # Добавляем колонку user_id в таблицу ads
        cursor.execute("""
        ALTER TABLE ads ADD COLUMN user_id INTEGER REFERENCES users(id)
        """)
        conn.commit()

try:
    update_ads_table()
except sqlite3.OperationalError:
    pass  # Колонка уже существуе

def init_db():
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            fio TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            about TEXT DEFAULT '',
            avatar TEXT DEFAULT 'static/default_avatar.png',
            role TEXT DEFAULT 'user' CHECK(role IN ('user', 'moderator', 'admin'))
        );
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            address TEXT,
            price REAL,
            phone TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user1_id INTEGER NOT NULL,
            user2_id INTEGER NOT NULL,
            last_message TEXT,
            last_message_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user1_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (user2_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (receiver_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """)
        conn.commit()

# Перезапустите init_db(), чтобы применить ON DELETE CASCADE
init_db()




# Главная страница
@app.route("/")
def home():
    return render_template("index.html")

# Регистрация
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        hashed_password = generate_password_hash(password)
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                    (username, email, hashed_password)
                )
                conn.commit()
                flash("Регистрация прошла успешно!")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("Email уже зарегистрирован!")
    return render_template("register.html")

# Вход
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
            user = cursor.fetchone()
            if user and check_password_hash(user[3], password):
                session["user_id"] = user[0]
                session["username"] = user[1]
                session["role"] = user[8]  # Проверяем, что роль сохраняется
                flash("Вы успешно вошли!")
                return redirect(url_for("cabinet"))
            else:
                flash("Неверный email или пароль!")
    return render_template("login.html")



UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/cabinet", methods=["GET", "POST"])
def cabinet():
    if "user_id" not in session:
        flash("Вы должны быть авторизованы для доступа к личному кабинету.")
        return redirect(url_for("login"))

    user_id = session["user_id"]

    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()

    if not user:
        flash("Пользователь не найден. Возможно, вы были удалены.")
        return redirect(url_for("logout"))

    username = user[1] if len(user) > 1 else ""
    email = user[2] if len(user) > 2 else ""
    fio = user[4] if len(user) > 4 else ""
    phone = user[5] if len(user) > 5 else ""
    about = user[6] if len(user) > 6 else ""
    avatar = user[7] if len(user) > 7 else "static/default_avatar.png"
    role = user[8] if len(user) > 8 else "user"  # Добавляем role

    if request.method == "POST":
        username = request.form.get("username")
        fio = request.form.get("fio")
        phone = request.form.get("phone")
        email = request.form.get("email")
        about = request.form.get("about")
        photo = request.files.get("photo")

        avatar_path = avatar
        if photo and allowed_file(photo.filename):
            filename = secure_filename(photo.filename)
            avatar_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            photo.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users 
                SET username = ?, email = ?, fio = ?, phone = ?, about = ?, avatar = ? 
                WHERE id = ?
            """, (username, email, fio, phone, about, avatar_path, user_id))
            conn.commit()

        session["username"] = username
        session["role"] = role  # Обновляем роль в сессии
        flash("Данные успешно обновлены!")
        return redirect(url_for("cabinet"))

    return render_template(
        "cabinet.html",
        username=username,
        fio=fio,
        phone=phone,
        email=email,
        about=about,
        avatar=avatar,
        role=role  # Передаем роль в шаблон
    )


# Выход
@app.route("/logout")
def logout():
    session.clear()
    flash("Вы вышли из системы.")
    return redirect(url_for("home"))



@app.route("/delete_account", methods=["POST"])
def delete_account():
    if "user_id" not in session:
        flash("Вы должны быть авторизованы для удаления аккаунта.")
        return redirect(url_for("login"))

    user_id = session["user_id"]

    # Получаем данные о пользователе перед удалением
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()

    if user:
        # Удаление аккаунта
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()

        session.pop("user_id", None)  # Удаляем ID из сессии
        flash("Ваш аккаунт был успешно удалён.")
        return redirect(url_for("home"))

    flash("Ошибка при удалении аккаунта.")
    return redirect(url_for("cabinet"))





@app.route("/ads")
def ads():
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT ads.id, ads.title, ads.description, users.username, users.avatar, users.id 
        FROM ads 
        JOIN users ON ads.user_id = users.id
        WHERE ads.type = 'general'
        """)
        ads_list = cursor.fetchall()

    return render_template("ads.html", ads=ads_list)



@app.route("/create_ad", methods=["GET", "POST"])
def create_ad():
    if "user_id" not in session:
        flash("Вы должны войти в систему, чтобы создавать объявления.")
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        user_id = session["user_id"]

        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO ads (title, description, user_id, type) 
            VALUES (?, ?, ?, 'general')
            """, (title, description, user_id))
            conn.commit()

        flash("Объявление успешно создано!")
        return redirect(url_for("ads"))

    return render_template("create_ad.html")





def update_users_table():
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        # Добавляем колонку avatar в таблицу users
        cursor.execute("""
        ALTER TABLE users ADD COLUMN avatar TEXT
        """)
        conn.commit()

try:
    update_users_table()
except sqlite3.OperationalError:
    pass  # Колонка уже существует






def init_messages_table():
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
          # Таблица сообщений
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sender_id) REFERENCES users (id),
            FOREIGN KEY (receiver_id) REFERENCES users (id)
        )
        """)
        conn.commit()

# Инициализация таблицы сообщений
init_messages_table()




@app.route("/chat/<int:user_id>", methods=["GET", "POST"])
def chat(user_id):
    if "user_id" not in session:
        flash("Вы должны быть авторизованы, чтобы участвовать в чате.")
        return redirect(url_for("login"))

    current_user_id = session["user_id"]

    # Получение имени получателя
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM users WHERE id = ?", (user_id,))
        recipient = cursor.fetchone()

        if not recipient:
            flash("Пользователь не найден.")
            return redirect(url_for("chats"))

        recipient_name = recipient[0]

        # Отправка нового сообщения
        if request.method == "POST":
            message_text = request.form["message"]
            cursor.execute("""
                INSERT INTO messages (sender_id, receiver_id, message, timestamp)
                VALUES (?, ?, ?, datetime('now'))
            """, (current_user_id, user_id, message_text))
            conn.commit()
            flash("Сообщение отправлено!")

        # Получение всех сообщений между пользователями
        cursor.execute("""
            SELECT sender_id, message, timestamp
            FROM messages
            WHERE (sender_id = ? AND receiver_id = ?)
               OR (sender_id = ? AND receiver_id = ?)
            ORDER BY timestamp ASC
        """, (current_user_id, user_id, user_id, current_user_id))
        messages = cursor.fetchall()

    return render_template("chat.html", messages=messages, recipient=(recipient_name, user_id), current_user_id=current_user_id)






@app.route("/chats")
def chats():
    if "user_id" not in session:
        flash("Вы должны быть авторизованы, чтобы видеть список чатов.")
        return redirect(url_for("login"))

    current_user_id = session["user_id"]

    # Получение списка уникальных пользователей, с которыми есть сообщения
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT 
                CASE 
                    WHEN sender_id = ? THEN receiver_id 
                    ELSE sender_id 
                END AS user_id
            FROM messages
            WHERE sender_id = ? OR receiver_id = ?
        """, (current_user_id, current_user_id, current_user_id))
        chat_user_ids = cursor.fetchall()

        # Получение имен пользователей для каждого user_id
        chats = []
        for chat_user_id in chat_user_ids:
            cursor.execute("SELECT username FROM users WHERE id = ?", (chat_user_id[0],))
            username = cursor.fetchone()
            if username:
                chats.append((chat_user_id[0], username[0]))

    return render_template("chats.html", chats=chats)


def update_ads_table_with_type():
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("ALTER TABLE ads ADD COLUMN type TEXT DEFAULT 'general'")
            conn.commit()
            # Установим тип 'general' для существующих объявлений
            cursor.execute("UPDATE ads SET type = 'general' WHERE type IS NULL")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Колонка уже существует

# Вызовите эту функцию после init_db()
init_db()
update_ads_table_with_type()


@app.route("/create_apartment_ad", methods=["GET", "POST"])
def create_apartment_ad():
    if "user_id" not in session:
        flash("Вы должны быть авторизованы, чтобы создавать объявления.")
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form.get("title", "Название не указано")
        description = request.form["description"]
        address = request.form["address"]
        price = request.form["price"]
        phone = request.form["phone"]
        user_id = session["user_id"]

        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO ads (title, description, address, price, phone, user_id, type) 
                VALUES (?, ?, ?, ?, ?, ?, 'apartment')
            """, (title, description, address, price, phone, user_id))
            conn.commit()

        flash("Объявление успешно создано!")
        return redirect(url_for("apartments"))

    return render_template("create_apartment_ad.html")


@app.route("/apartments")
def apartments():
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ads.id, ads.title, ads.address, ads.price, ads.phone, ads.description, users.username, users.id 
            FROM ads 
            JOIN users ON ads.user_id = users.id
            WHERE ads.type = 'apartment'
        """)
        apartments_list = cursor.fetchall()

    return render_template("apartments.html", apartments=apartments_list)


@app.route("/apartment/<int:ad_id>")
def apartment_detail(ad_id):
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ads.id, ads.title, ads.address, ads.price, ads.phone, ads.description, users.username, users.id 
            FROM ads 
            JOIN users ON ads.user_id = users.id
            WHERE ads.id = ?
        """, (ad_id,))
        apartment = cursor.fetchone()

    if not apartment:
        flash("Объявление не найдено.", "danger")
        return redirect(url_for("apartments"))

    return render_template("apartment_detail.html", apartment=apartment)


# Добавьте это после существующего кода, перед if __name__ == "__main__":

# Страница модерации (доступна только модераторам и админам)
@app.route("/moderation")
def moderation():
    if "user_id" not in session:
        flash("Вы должны войти в систему!")
        return redirect(url_for("login"))
    
    user_id = session["user_id"]
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT role FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        if not user or user[0] not in ["moderator", "admin"]:
            flash("Доступ запрещен! Требуются права модератора или администратора.")
            return redirect(url_for("home"))
        
        # Получение списка пользователей
        cursor.execute("SELECT id, username, email, role FROM users")
        users = cursor.fetchall()
        # Получение списка объявлений
        cursor.execute("""
            SELECT ads.id, ads.title, ads.description, users.username 
            FROM ads 
            JOIN users ON ads.user_id = users.id
        """)
        ads = cursor.fetchall()
    
    return render_template("moderation.html", users=users, ads=ads)

# Удаление объявления модератором
@app.route("/delete_ad_mod/<int:ad_id>", methods=["POST"])
def delete_ad_mod(ad_id):
    if "user_id" not in session or session.get("role") not in ["moderator", "admin"]:
        flash("Нет прав на удаление объявления!")
        return redirect(url_for("moderation"))
    
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ads WHERE id = ?", (ad_id,))
        conn.commit()
    
    flash("Объявление успешно удалено!")
    return redirect(url_for("moderation"))

# Удаление аккаунта модератором
@app.route("/delete_user_mod/<int:user_id>", methods=["POST"])
def delete_user_mod(user_id):
    if "user_id" not in session or session.get("role") not in ["moderator", "admin"]:
        flash("Нет прав на удаление аккаунта!")
        return redirect(url_for("moderation"))
    
    if session["user_id"] == user_id:
        flash("Нельзя удалить собственный аккаунт через панель модерации!")
        return redirect(url_for("moderation"))
    
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
    
    flash("Аккаунт успешно удален!")
    return redirect(url_for("moderation"))

# Замените только эти маршруты в предыдущем дополнении:

@app.route("/add_moderator", methods=["POST"])
def add_moderator():
    if "user_id" not in session or session.get("role") != "admin":
        flash("Только администратор может назначать модераторов!")
        return redirect(url_for("moderation"))
    
    email = request.form.get("email")
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, role FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        
        if user:
            if user[1] == "admin":
                flash(f"Пользователь {email} уже администратор и не может быть изменен!")
            else:
                cursor.execute("UPDATE users SET role = 'moderator' WHERE email = ?", (email,))
                conn.commit()
                flash(f"Пользователь с email {email} назначен модератором!")
        else:
            # Создаем нового пользователя с ролью модератора
            username = email.split('@')[0]  # Берем часть до @
            password = generate_password_hash("default_password")  # Установите свой пароль
            cursor.execute("""
                INSERT INTO users (username, email, password, role)
                VALUES (?, ?, ?, 'moderator')
            """, (username, email, password))
            conn.commit()
            flash(f"Создан новый модератор с email {email}!")
        
        print(f"Attempted to add moderator: Email={email}, User found={user is not None}, New role set={'moderator'}")
    
    return redirect(url_for("moderation"))

# Снятие статуса модератора (только для админа) по email
@app.route("/remove_moderator", methods=["POST"])
def remove_moderator():
    if "user_id" not in session or session.get("role") != "admin":
        flash("Только администратор может снимать модераторов!")
        return redirect(url_for("moderation"))
    
    email = request.form.get("email")
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email = ? AND role = 'moderator'", (email,))
        user = cursor.fetchone()
        if user:
            cursor.execute("UPDATE users SET role = 'user' WHERE email = ? AND role = 'moderator'", (email,))
            conn.commit()
            flash(f"Статус модератора снят с пользователя {email}!")
        else:
            flash("Модератор с таким email не найден!")
    
    return redirect(url_for("moderation"))

# Остальные маршруты (moderation, delete_ad_mod, delete_user_mod) остаются без изменений

def set_admin(email='04artthur@gmail.com'):  # Укажите нужный email по умолчанию
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        # Проверяем, существует ли пользователь
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        
        if user:
            # Если пользователь существует, обновляем его роль
            cursor.execute("UPDATE users SET role = 'admin' WHERE email = ?", (email,))
            conn.commit()
            print(f"Пользователь с email {email} назначен администратором.")
        else:
            # Если пользователя нет, создаем нового
            cursor.execute("""
                INSERT INTO users (username, email, password, role) 
                VALUES (?, ?, ?, ?)
            """, (email.split('@')[0], email, generate_password_hash('default_password'), 'admin'))
            conn.commit()
            print(f"Создан новый администратор с email {email}.")

# Вызовите функцию где-нибудь в коде, например, после init_db()
init_db()
set_admin('04artthur@gmail.com')  # Замените на нужный email

# Запуск сервера
if __name__ == "__main__":
    app.run(debug=True)


#if __name__ == "__main__":
    #from waitress import serve
    #serve(app, host="0.0.0.0", port=7777)