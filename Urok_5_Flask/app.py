import sqlite3
import uuid
from datetime import date
from collections import Counter
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.json.ensure_ascii = False
app.secret_key = 'travel-agency-secret-key'

# Сезонний коефіцієнт ціни: ключ — номер місяця
SEASON_FACTORS = {
    1: 1.0, 2: 0.95, 3: 1.0, 4: 1.05, 5: 1.1, 6: 1.25,
    7: 1.3, 8: 1.3, 9: 1.0, 10: 0.9, 11: 0.8, 12: 1.15,
}
SEASON_NAMES = {
    1: 'Зима', 2: 'Зима', 3: 'Весна', 4: 'Весна', 5: 'Весна', 6: 'Літо',
    7: 'Літо', 8: 'Літо', 9: 'Осінь', 10: 'Осінь', 11: 'Осінь', 12: 'Зима',
}


# ---------- База даних ----------

def get_db():
    conn = sqlite3.connect('tours.db')
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tours (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            image TEXT,
            views INTEGER NOT NULL DEFAULT 0,
            depart_date TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            visitor_id TEXT NOT NULL,
            visit_date TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tour_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT,
            created TEXT NOT NULL
        )
    ''')

    # Якщо tours.db створено раніше (без нових колонок), додаємо їх
    columns = []
    for row in conn.execute('PRAGMA table_info(tours)').fetchall():
        columns.append(row['name'])
    if 'views' not in columns:
        conn.execute('ALTER TABLE tours ADD COLUMN views INTEGER NOT NULL DEFAULT 0')
    if 'depart_date' not in columns:
        conn.execute('ALTER TABLE tours ADD COLUMN depart_date TEXT')

    conn.commit()
    conn.close()


# ---------- Допоміжні функції ----------

def season_factor(month):
    return SEASON_FACTORS[month]


def days_word(n):
    if n % 10 == 1 and n % 100 != 11:
        return 'день'
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return 'дні'
    return 'днів'


def add_extras(row):
    # Перетворюємо рядок з бази на словник і додаємо обчислені поля
    tour = dict(row)
    today = date.today()

    if tour['depart_date']:
        depart = date.fromisoformat(tour['depart_date'])
        month = depart.month
        days = (depart - today).days
        tour['depart_text'] = depart.strftime('%d.%m.%Y')
        if days < 0:
            tour['days_text'] = 'Тур завершено'
            tour['finished'] = True
        elif days == 0:
            tour['days_text'] = 'Вирушаємо сьогодні!'
            tour['finished'] = False
        else:
            tour['days_text'] = 'До відльоту ' + str(days) + ' ' + days_word(days)
            tour['finished'] = False
    else:
        month = today.month
        tour['depart_text'] = 'не вказано'
        tour['days_text'] = 'Дату виїзду ще не визначено'
        tour['finished'] = False

    factor = season_factor(month)
    tour['factor'] = factor
    tour['season_name'] = SEASON_NAMES[month]
    tour['base_price'] = round(tour['price'])
    tour['final_price'] = round(tour['price'] * factor)

    avg = tour['avg_rating']
    if avg is None:
        stars = 0
        tour['rating_text'] = 'Ще немає оцінок'
    else:
        stars = int(avg + 0.5)
        tour['rating_text'] = str(round(avg, 1)) + ' (' + str(tour['review_count']) + ')'
    tour['stars'] = '★' * stars + '☆' * (5 - stars)
    return tour


def get_all_tours():
    conn = get_db()
    rows = conn.execute('''
        SELECT tours.*, AVG(reviews.rating) AS avg_rating, COUNT(reviews.id) AS review_count
        FROM tours
        LEFT JOIN reviews ON reviews.tour_id = tours.id
        GROUP BY tours.id
        ORDER BY tours.id
    ''').fetchall()
    conn.close()
    result = []
    for row in rows:
        result.append(add_extras(row))
    return result


def get_tour(tour_id):
    conn = get_db()
    row = conn.execute('''
        SELECT tours.*, AVG(reviews.rating) AS avg_rating, COUNT(reviews.id) AS review_count
        FROM tours
        LEFT JOIN reviews ON reviews.tour_id = tours.id
        WHERE tours.id = ?
        GROUP BY tours.id
    ''', (tour_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return add_extras(row)


def get_popular_tours():
    conn = get_db()
    rows = conn.execute('''
        SELECT tours.*, AVG(reviews.rating) AS avg_rating, COUNT(reviews.id) AS review_count
        FROM tours
        LEFT JOIN reviews ON reviews.tour_id = tours.id
        WHERE tours.views > 0
        GROUP BY tours.id
        ORDER BY tours.views DESC
        LIMIT 3
    ''').fetchall()
    conn.close()
    result = []
    for row in rows:
        result.append(add_extras(row))
    return result


def get_visits():
    conn = get_db()
    total = conn.execute('SELECT COUNT(*) FROM visits').fetchone()[0]
    unique = conn.execute('SELECT COUNT(DISTINCT visitor_id) FROM visits').fetchone()[0]
    conn.close()
    return {'total': total, 'unique': unique}


def get_total(tour):
    return tour['total']


def render_tour(tour_id, error=''):
    tour = get_tour(tour_id)
    reviews = []
    if tour is not None:
        conn = get_db()
        reviews = conn.execute(
            'SELECT * FROM reviews WHERE tour_id = ? ORDER BY id DESC', (tour_id,)
        ).fetchall()
        conn.close()
    return render_template('tour.html', tour=tour, reviews=reviews,
                           error=error, visits=get_visits())


# ---------- Лічильник відвідувачів ----------

@app.before_request
def count_visit():
    if request.method != 'GET':
        return
    if request.endpoint is None or request.endpoint == 'static':
        return

    if 'visitor_id' not in session:
        session['visitor_id'] = str(uuid.uuid4())

    conn = get_db()
    conn.execute('INSERT INTO visits (visitor_id, visit_date) VALUES (?, ?)',
                 (session['visitor_id'], str(date.today())))
    conn.commit()
    conn.close()


# ---------- Сторінки ----------

@app.route('/')
def index():
    # Тур дня: однаковий весь день, а завтра інший
    available = []
    for tour in get_all_tours():
        if not tour['finished']:
            available.append(tour)

    tour_of_day = None
    if len(available) > 0:
        number = date.today().toordinal() % len(available)
        tour_of_day = available[number]

    return render_template('index.html', tour_of_day=tour_of_day,
                           popular=get_popular_tours(), visits=get_visits())


@app.route('/about')
def about():
    return render_template('about.html', visits=get_visits())


@app.route('/tours')
def tours():
    tour_list = get_all_tours()
    return render_template('tours.html', tours=tour_list, visits=get_visits())


@app.route('/tour/<int:tour_id>')
def tour_page(tour_id):
    conn = get_db()
    conn.execute('UPDATE tours SET views = views + 1 WHERE id = ?', (tour_id,))
    conn.commit()
    conn.close()
    return render_tour(tour_id)


@app.route('/tour/<int:tour_id>/review', methods=['GET', 'POST'])
def add_review(tour_id):
    if request.method == 'GET':
        return redirect(url_for('tour_page', tour_id=tour_id))

    name = request.form['name'].strip()
    comment = request.form['comment'].strip()
    try:
        rating = int(request.form['rating'])
    except ValueError:
        rating = 0

    if name == '' or rating < 1 or rating > 5:
        return render_tour(tour_id, "Введіть ім'я та оцінку від 1 до 5")
    if get_tour(tour_id) is None:
        return render_tour(tour_id)

    conn = get_db()
    conn.execute(
        'INSERT INTO reviews (tour_id, name, rating, comment, created) VALUES (?, ?, ?, ?, ?)',
        (tour_id, name, rating, comment, str(date.today()))
    )
    conn.commit()
    conn.close()
    return redirect(url_for('tour_page', tour_id=tour_id))


@app.route('/add_tour', methods=['GET', 'POST'])
def add_tour():
    if request.method == 'GET':
        return render_template('add_tour.html', error='', visits=get_visits())

    title = request.form['title'].strip()
    description = request.form['description'].strip()
    price_text = request.form['price']
    image = request.form['image'].strip()
    depart_date = request.form['depart_date'].strip()

    try:
        price = float(price_text)
    except ValueError:
        price = 0

    error = ''
    if title == '' or price <= 0:
        error = 'Введіть назву та ціну більше нуля'
    if depart_date != '':
        try:
            date.fromisoformat(depart_date)
        except ValueError:
            error = 'Некоректна дата виїзду'

    if error != '':
        return render_template('add_tour.html', error=error, visits=get_visits())

    conn = get_db()
    conn.execute(
        'INSERT INTO tours (title, description, price, image, depart_date) VALUES (?, ?, ?, ?, ?)',
        (title, description, price, image, depart_date)
    )
    conn.commit()
    conn.close()
    return redirect(url_for('tours'))


@app.route('/pick')
def pick():
    budget_text = request.args.get('budget')
    people_text = request.args.get('people')
    sort = request.args.get('sort', 'cheap')

    found = None   # None означає, що форму ще не відправляли
    error = ''

    if budget_text is not None and people_text is not None:
        try:
            budget = float(budget_text)
            people = int(people_text)
        except ValueError:
            budget = 0
            people = 0

        if budget <= 0 or people < 1:
            error = 'Введіть бюджет більше нуля та кількість людей від 1'
        else:
            found = []
            for tour in get_all_tours():
                if tour['finished']:
                    continue
                total = tour['final_price'] * people
                if total <= budget:
                    tour['total'] = total
                    tour['left'] = round(budget - total)
                    found.append(tour)
            found = sorted(found, key=get_total, reverse=(sort == 'expensive'))

    return render_template('pick.html', found=found, error=error,
                           budget=budget_text or '', people=people_text or '',
                           sort=sort, visits=get_visits())


@app.route('/compare')
def compare():
    a = request.args.get('a')
    b = request.args.get('b')

    a_id = None
    b_id = None
    if a is not None and a.isdigit():
        a_id = int(a)
    if b is not None and b.isdigit():
        b_id = int(b)

    compared = []
    result = None
    message = ''

    if a is None or b is None:
        message = 'Оберіть два тури, щоб порівняти їх'
    else:
        tour_a = None
        tour_b = None
        if a_id is not None:
            tour_a = get_tour(a_id)
        if b_id is not None:
            tour_b = get_tour(b_id)

        if tour_a is None or tour_b is None:
            message = 'Один із турів не знайдено'
        elif tour_a['id'] == tour_b['id']:
            message = 'Оберіть два різні тури'
        else:
            if tour_a['final_price'] <= tour_b['final_price']:
                cheaper = tour_a
                pricier = tour_b
            else:
                cheaper = tour_b
                pricier = tour_a
            diff = pricier['final_price'] - cheaper['final_price']
            percent = 0
            if cheaper['final_price'] > 0:
                percent = round(diff / cheaper['final_price'] * 100)
            result = {'cheaper': cheaper, 'pricier': pricier,
                      'diff': diff, 'percent': percent}
            compared = [tour_a, tour_b]

    return render_template('compare.html', all_tours=get_all_tours(),
                           a_id=a_id, b_id=b_id, compared=compared,
                           result=result, message=message, visits=get_visits())


@app.route('/stats')
def stats():
    tour_list = get_all_tours()

    # Відвідування за останні 7 днів (GROUP BY)
    conn = get_db()
    rows = conn.execute('''
        SELECT visit_date, COUNT(*) AS cnt
        FROM visits
        GROUP BY visit_date
        ORDER BY visit_date DESC
        LIMIT 7
    ''').fetchall()
    conn.close()

    days = []
    for row in rows:
        label = row['visit_date'][8:10] + '.' + row['visit_date'][5:7]
        days.append({'label': label, 'value': row['cnt']})
    days.reverse()

    # Кількість турів за ціновими категоріями (Counter) і ціни
    categories = Counter()
    prices = []
    for tour in tour_list:
        price = tour['final_price']
        prices.append(price)
        if price < 5000:
            categories['до 5000 грн'] += 1
        elif price <= 15000:
            categories['5000–15000 грн'] += 1
        else:
            categories['понад 15000 грн'] += 1

    price_chart = []
    for name in ['до 5000 грн', '5000–15000 грн', 'понад 15000 грн']:
        price_chart.append({'label': name, 'value': categories[name]})

    average = 0
    lowest = 0
    highest = 0
    if len(prices) > 0:
        average = round(sum(prices) / len(prices))
        lowest = min(prices)
        highest = max(prices)

    return render_template('stats.html', tours=tour_list, days=days,
                           price_chart=price_chart, average=average,
                           lowest=lowest, highest=highest, visits=get_visits())


@app.route('/gallery')
def gallery():
    photos = [
        ('beach.jpg', 'Пляж'),
        ('mountains.jpg', 'Гори'),
        ('city.jpg', 'Місто'),
        ('forest.jpg', 'Ліс'),
        ('lake.jpg', 'Озеро'),
        ('desert.jpg', 'Пустеля'),
    ]
    return render_template('gallery.html', photos=photos, visits=get_visits())


@app.route('/contacts')
def contacts():
    info = {
        'address': 'м. Івано-Франківськ, вул. Незалежності, 10',
        'phone': '+380 67 123 45 67',
        'email': 'info@travel-agency.ua',
        'hours': 'Пн–Пт: 9:00–18:00, Сб: 10:00–14:00',
    }
    return render_template('contacts.html', info=info, visits=get_visits())


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
