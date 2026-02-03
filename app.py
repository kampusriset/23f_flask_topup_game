from flask import Flask, render_template, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_db
import config
import os
from werkzeug.utils import secure_filename
from flask import send_file
from openpyxl import Workbook
import io
from flask import send_from_directory


app = Flask(__name__)
app.secret_key = config.SECRET_KEY

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png','jpg','jpeg'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE username=%s", (username,))
        user = cur.fetchone()
        cur.close()
        db.close()

        # CEK USER & PASSWORD
        if user and check_password_hash(user['password'], password):
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']

            # REDIRECT SESUAI ROLE
            if user['role'] == 'admin':
                return redirect('/admin')
            else:
                return redirect('/user')

        # LOGIN GAGAL → BALIK KE LOGIN + SHAKE
        return render_template(
            'login.html',
            error=True
        )

    return render_template('login.html')

@app.route('/export-excel')
def export_excel():
    # proteksi admin
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect('/')

    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute("""
        SELECT 
            t.id,
            u.username,
            t.game,
            t.player_id,
            t.nominal,
            t.payment,
            t.status,
            t.created_at
        FROM transactions t
        JOIN users u ON t.user_id = u.id
        ORDER BY t.created_at DESC
    """)
    data = cur.fetchall()

    cur.close()
    db.close()

    # ======================
    # BUAT FILE EXCEL
    # ======================
    wb = Workbook()
    ws = wb.active
    ws.title = "Data Topup"

    # HEADER
    headers = [
        "ID Transaksi", "Username", "Game", "Player ID",
        "Nominal", "Payment", "Status", "Tanggal"
    ]
    ws.append(headers)

    # DATA
    for d in data:
        ws.append([
            d['id'],
            d['username'],
            d['game'],
            d['player_id'],
            d['nominal'],
            d['payment'],
            d['status'],
            d['created_at'].strftime('%Y-%m-%d %H:%M')
        ])

    # SIMPAN KE MEMORY
    file_stream = io.BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)

    return send_file(
        file_stream,
        as_attachment=True,
        download_name="laporan_topup.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.route('/topup/<int:game_id>')
def topup_page(game_id):
    if 'username' not in session:
        return redirect('/')

    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute("SELECT * FROM games WHERE id=%s", (game_id,))
    game = cur.fetchone()

    cur.execute("SELECT * FROM nominals WHERE game_id=%s", (game_id,))
    nominals = cur.fetchall()

    cur.close()
    db.close()

    return render_template(
        'user/topup.html',
        game=game,
        nominals=nominals
    )

@app.route('/topup/process', methods=['POST'])
def topup_process():
    if 'username' not in session:
        return redirect('/')

    game_id = request.form['game_id']
    nominal_id = request.form['nominal_id']
    payment = request.form['payment']
    game_user_id = request.form['game_user_id']
    file = request.files['bukti']

    filename = secure_filename(file.filename)

    upload_path = os.path.join('static/uploads', filename)
    file.save(upload_path)

    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute(
        "SELECT id FROM users WHERE username=%s",
        (session['username'],)
    )
    user = cur.fetchone()

    cur.execute("""
        INSERT INTO transactions 
        (user_id, game_id, nominal_id, game_user_id, payment, bukti_bayar, status)
        VALUES (%s,%s,%s,%s,%s,%s,'pending')
    """, (
        user['id'],
        game_id,
        nominal_id,
        game_user_id,
        payment,
        filename
    ))

    db.commit()
    cur.close()
    db.close()

    return redirect('/user')

# ================= REGISTER =================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        hashed = generate_password_hash(password)

        db = get_db()
        cur = db.cursor()

        cur.execute("SELECT id FROM users WHERE username=%s", (username,))
        if cur.fetchone():
            cur.close()
            db.close()
            return "Username sudah ada"

        cur.execute(
            "INSERT INTO users (username, password, role) VALUES (%s,%s,%s)",
            (username, hashed, 'user')
        )
        db.commit()
        cur.close()
        db.close()

        return redirect('/')

    return render_template('register.html')


@app.route('/admin')
def admin_dashboard():
    # proteksi admin
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect('/')

    db = get_db()
    cur = db.cursor(dictionary=True)

    # ======================
    # STATISTIK
    # ======================
    cur.execute("SELECT COUNT(*) AS total FROM users")
    total_user = cur.fetchone()['total']

    cur.execute("SELECT COUNT(*) AS total FROM transactions")
    total_transaksi = cur.fetchone()['total']

    cur.execute("SELECT IFNULL(SUM(nominal),0) AS total FROM transactions")
    total_penjualan = cur.fetchone()['total']

    # ======================
    # TRANSAKSI TERBARU
    # ======================
    cur.execute("""
        SELECT 
            t.id,
            u.username,
            t.game,
            t.nominal
        FROM transactions t
        JOIN users u ON t.user_id = u.id
        ORDER BY t.created_at DESC
        LIMIT 10
    """)
    transaksi_terbaru = cur.fetchall()

    # ======================
    # DATA GRAFIK (INI JAWABAN KAMU)
    # ======================
    cur.execute("""
        SELECT 
            DATE(created_at) AS tgl,
            SUM(nominal) AS total
        FROM transactions
        WHERE created_at IS NOT NULL
        GROUP BY DATE(created_at)
        ORDER BY DATE(created_at)
    """)
    chart = cur.fetchall()

    labels = [str(c['tgl']) for c in chart]
    data = [int(c['total']) for c in chart]

    # ======================
    # FILTER TAHUN
    # ======================
    cur.execute("SELECT DISTINCT YEAR(created_at) AS tahun FROM transactions")
    tahun_list = [t['tahun'] for t in cur.fetchall()]

    cur.close()
    db.close()

    return render_template(
        'admin/dashboard.html',
        total_user=total_user,
        total_transaksi=total_transaksi,
        total_penjualan=total_penjualan,
        transaksi_terbaru=transaksi_terbaru,
        labels=labels,
        data=data,
        tahun_list=tahun_list
    )



@app.route('/user')
def user_dashboard():
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM games")
    games = cur.fetchall()
    cur.close()
    db.close()
    return render_template('user/dashboard.html', games=games)

@app.route('/topup', methods=['GET', 'POST'])
def topup():
    if 'user_id' not in session:
        return redirect('/')

    if request.method == 'POST':
        game = request.form['game']
        player_id = request.form['player_id']
        server = request.form.get('server')
        nominal = request.form['nominal']
        payment = request.form['payment']
        contact = request.form['contact']
        voucher = request.form.get('voucher')

        # ===== INI NIH TEMPATNYA 🔥 =====
        file = request.files.get('proof')

        if not file or file.filename == '':
            return "Bukti pembayaran wajib diupload", 400

        filename = secure_filename(file.filename)
        file.save(os.path.join('static/uploads', filename))
        # ===== SAMPE SINI =====

        db = get_db()
        cur = db.cursor()

        cur.execute("""
            INSERT INTO transactions 
            (user_id, game, player_id, server, nominal, payment, contact, voucher, proof, status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'SUCCESS')
        """, (
            session['user_id'],
            game,
            player_id,
            server,
            nominal,
            payment,
            contact,
            voucher,
            filename
        ))

        db.commit()
        return redirect('/success')

    return render_template('user/topup.html')

@app.route('/success')
def success():
    return render_template('user/success.html')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory('static/uploads', filename)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


if __name__ == '__main__':
    app.run(debug=True)
