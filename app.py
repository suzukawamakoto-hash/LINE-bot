from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'my-secret-key-change-later')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bbs.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'ログインしてください'

# NGワードリスト（自由に追加OK）
NG_WORDS = {"出会い", "会おう", "LINE教えて", "電話番号", "メアド"}

def check_ng(text):
    text = text or ""
    return any(word in text for word in NG_WORDS)

# ユーザー
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(60), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    posts = db.relationship('Post', backref='author', lazy=True)

    def set_password(self, pw):
        self.password_hash = bcrypt.generate_password_hash(pw).decode('utf-8')
    def check_password(self, pw):
        return bcrypt.check_password_hash(self.password_hash, pw)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# 投稿
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# トップページ
@app.route('/')
def index():
    posts = Post.query.order_by(Post.created_at.desc()).all()
    return render_template('index.html', posts=posts)

# 新規登録
@app.route('/register', methods=['GET','POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        un = request.form['username']
        em = request.form['email']
        pw = request.form['password']
        if User.query.filter_by(username=un).first():
            flash('ユーザー名が使われています')
            return redirect(url_for('register'))
        if User.query.filter_by(email=em).first():
            flash('メールアドレスが登録済みです')
            return redirect(url_for('register'))
        user = User(username=un, email=em)
        user.set_password(pw)
        db.session.add(user)
        db.session.commit()
        flash('登録完了！ログインしてね✨')
        return redirect(url_for('login'))
    return render_template('register.html')

# ログイン
@app.route('/login', methods=['GET','POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user and user.check_password(request.form['password']):
            login_user(user)
            return redirect(url_for('index'))
        flash('メールかパスワードが違います')
    return render_template('login.html')

# ログアウト
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# 投稿
@app.route('/post', methods=['GET','POST'])
@login_required
def create_post():
    if request.method == 'POST':
        t = request.form['title']
        c = request.form['content']
        if check_ng(t) or check_ng(c):
            flash('不適切な言葉が含まれています')
            return redirect(url_for('create_post'))
        post = Post(title=t, content=c, user_id=current_user.id)
        db.session.add(post)
        db.session.commit()
        flash('投稿しました！')
        return redirect(url_for('index'))
    return render_template('post.html')

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
