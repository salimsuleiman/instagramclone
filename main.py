from flask import *
from flask_sqlalchemy import SQLAlchemy, sqlalchemy
from flask_login import current_user, login_user, logout_user, LoginManager, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from flask_uploads import UploadSet, configure_uploads, IMAGES
import timeago
import datetime
from werkzeug.utils import secure_filename
import os


uri = os.environ.get("DATABASE_URL",'sqlite:///db/database.db')
#if uri.startswith("postgres://"):
#     uri = uri.replace("postgres://", "postgresql://", 1)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'swefghjhgfdfgnhgfdsfghmhgfvb345'
app.config['UPLOADED_PHOTOS_DEST'] = 'static/upload'

ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


db = SQLAlchemy(app)
login_manager = LoginManager(app)
photos = UploadSet('photos', IMAGES)
configure_uploads(app, (photos))


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


class PostLike(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'))
    user = None
    post = None


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    email = db.Column(db.String, nullable=False)
    username = db.Column(db.String, unique=True, nullable=False)
    password = db.Column(db.String, nullable=False)
    posts = db.relationship('Post', back_populates='author')  # lists

    date_joined = db.Column(
        db.String(), default=datetime.datetime.now(),  nullable=False)

    def get_liked_posts(self):
        posts = PostLike.query.filter_by(user_id=self.id)
        return posts

    def likes(self):
        likes = 0
        for post in self.posts:
            likes += len(post.get_liked_users())
        print(likes)
        return likes

    def already_liked(self, post):
        for user in post.get_liked_users():
            if user.user_id == self.id:
                return True
        return False

    def like_post(self, post):
        post = post
        db.session.add(post)
        db.session.commit()

    def unlike_post(self, post):
        post_like = PostLike.query.filter_by(
            post_id=post.id, user_id=current_user.id).first()
        db.session.delete(post_like)
        db.session.commit()


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey(
        'user.id'),  nullable=False,)
    author = db.relationship('User', back_populates='posts')
    post_img = db.Column(db.String(), nullable=False)
    post_date = db.Column(
        db.String(), default=datetime.datetime.now(),  nullable=False)

    def get_liked_users(self):
        users = [user for user in PostLike.query.filter_by(post_id=self.id)]
        return users

    def __repr__(self):
        return f'<{self.author}, <{self.id}> {self.likes}>'


db.create_all()


@app.get('/')
def home_page():
    posts = Post.query.all()
    today = datetime.datetime.now()
    return render_template(
        'index.html',
        current_user=current_user,
        posts=posts,
        timeago=timeago,
        datetime=datetime.datetime.now
    )


@app.get('/login')
def login_page():
    return render_template('login.html')


@app.get('/register')
def register_page():
    return render_template('signup.html')


# POST Reqs-

# login
@app.post('/')
def login():
    user = User.query.filter_by(email=request.form.get('email')).first()
    if user is None:
        flash('User not found')
        return redirect(url_for('login_page'))
    else:
        password = request.form.get('password')
        if check_password_hash(pwhash=user.password, password=password):
            login_user(user)
            flash('Logged in')
            return redirect(url_for('home_page'))
        else:
            flash('Wrong password')
            return redirect(url_for('login_page'))


# register
@app.post('/register')
def register():
    if request.form.get('password') == request.form.get('passoword_again'):
        user = User(
            name=request.form.get('name'),
            email=request.form.get('email'),
            username=request.form.get('username'),
            password=generate_password_hash(request.form.get(
                'password'), method='pbkdf2:sha256', salt_length=8)
        )
        db.session.add(user)
        try:
            db.session.commit()
        except sqlalchemy.exc.IntegrityError:
            flash('Username already exist')
            return redirect(url_for('register_page'))
        login_user(user)

        flash('Successfully register')
        return redirect(url_for('home_page'))
    else:
        flash("Password dosen't match")
        return redirect(url_for('register_page'))


# logout
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home_page'))


@app.get('/<string:username>')
def profile_page(username):
    today = datetime.datetime.now()
    user = User.query.filter_by(username=username).first()
    return render_template('profile.html',
                           timeago=timeago,
                           datetime=datetime.datetime.now,
                           user=user)


# POsts
@app.post('/post')
def post():
    if current_user.is_authenticated:
        if 'post-img' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['post-img']

        if file.filename == '':
            flash('No image selected for uploading')
            return redirect(url_for('home_page'))
        else:
            filename = secure_filename(file.filename)
            if allowed_file(filename):
                file.save(os.path.join('static/upload/images/', filename))
                img_url = f'images/{filename}'
            else:
                file.save(os.path.join('static/upload/videos/', filename))
                img_url = f'videos/{filename}'

            post = Post(
                text=request.form.get('post-body'),
                author=current_user,
                post_img=img_url
            )

            db.session.add(post)
            db.session.commit()

            flash('Post Added')
            return redirect(url_for('home_page'))
    else:
        return 'login first'


@app.get('/delete/<string:post_id>')
def delete(post_id):
    post = Post.query.get(post_id)
    if post is None:
        return 'wrong post'

    if current_user.id == post.author_id:
        for post_like in post.get_liked_users():
            db.session.delete(post_like)
        db.session.delete(post)
        db.session.commit()
        flash('post delete')
        return redirect(url_for('home_page'))
    else:
        return 'not your post'


@app.get('/like/post/<string:user_id>/<int:post_id>')
def like(user_id, post_id):
    if current_user.is_authenticated:
        post = Post.query.filter_by(id=post_id).first()
        user = User.query.get(user_id)
        if post is None:
            return 'None Post!!!'

        if user.id == current_user.id:
            if current_user.already_liked(post):
                current_user.unlike_post(post)
                return redirect(url_for('home_page'))
            else:
                db.session.add(PostLike(
                    user_id=current_user.id,
                    post_id=post.id,
                    post=post,
                    user=current_user
                ))
                db.session.commit()
                return redirect(url_for('home_page'))

    else:
        return 'login first'


# starting the server
if __name__ == '__main__':
    app.run(debug=True)
