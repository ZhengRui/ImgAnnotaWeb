import os
from flask import Flask, render_template, session, request, flash, url_for, redirect, json, jsonify, send_file
from flask.ext.sqlalchemy import SQLAlchemy
from werkzeug import generate_password_hash, check_password_hash, secure_filename
from flask_wtf import Form
from wtforms import TextField, PasswordField, SubmitField, validators, ValidationError
import StringIO


app = Flask(__name__)
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = set(['bmp', 'png', 'jpg', 'jpeg'])

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://testusr:testpsd@localhost/orasiscloudcad'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
app.config['SECRET_KEY'] = 'randomkey'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


db = SQLAlchemy()
db.init_app(app)


class User(db.Model):
    __tablename__ = 'users'
    uid = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(80), unique=True)
    pwdhash = db.Column(db.String(80))

    def __init__(self, email, password):
        self.email = email.lower()
        self.set_password(password)

    def set_password(self, password):
        self.pwdhash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.pwdhash, password)

class Task(db.Model):
    __tablename__ = 'tasks'
    tid = db.Column(db.Integer, primary_key=True)
    uid = db.Column(db.Integer, db.ForeignKey('users.uid'))
    tname = db.Column(db.String(100))
    imgnumttl = db.Column(db.Integer)
    imgnummrk = db.Column(db.Integer)
    state = db.Column(db.Boolean)

    def __init__(self, uid, tname):
        self.uid = uid
        self.tname = tname
        self.imgnumttl = 0
        self.imgnummrk = 0
        self.state = False

class Image(db.Model):
    __tablename__ = 'images'
    iid = db.Column(db.Integer, primary_key=True)
    tid = db.Column(db.Integer, db.ForeignKey('tasks.tid'))
    imgname = db.Column(db.String(100))
    bbx = db.Column(db.Text)
    bbxnum = db.Column(db.Integer)

    def __init__(self, tid, imgname):
        self.tid = tid
        self.imgname = imgname
        self.bbxnum = 0

class Celltype(db.Model):
    __tablename__ = 'celltypes'
    ctid = db.Column(db.Integer, primary_key=True)
    ctname = db.Column(db.String(100))
    ctcolor = db.Column(db.String(100))

    def __init__(self, ctname, ctcolor):
        self.ctname = ctname
        self.ctcolor = ctcolor

class SignupForm(Form):
    email = TextField("Email", [validators.Required("Please enter your email address."), validators.Email("Please enter your email address.")])
    password = PasswordField('Password', [validators.Required("Please enter a password.")])
    submit = SubmitField("Create account")

    def __init__(self, *args, **kwargs):
        Form.__init__(self, *args, **kwargs)

    def validate(self):
        if not Form.validate(self):
            return False

        user = User.query.filter_by(email = self.email.data.lower()).first()
        if user:
            self.email.errors.append("That email is already taken")
            return False
        else:
            return True

class SigninForm(Form):
    email = TextField("Email", [validators.Required("Please enter your email address."), validators.Email("Please enter your email address.")])
    password = PasswordField('Password', [validators.Required("Please enter a password.")])
    submit = SubmitField("Sign In")

    def __init__(self, *args, **kwargs):
        Form.__init__(self, *args, **kwargs)

    def validate(self):
        if not Form.validate(self):
            return False

        user = User.query.filter_by(email = self.email.data.lower()).first()
        if user and user.check_password(self.password.data):
            return True 
        else:
            self.email.errors.append("Invalid e-mail or password")
            return False


@app.route('/')
@app.route('/index')
def home():
    if 'uid' in session:
        return redirect(url_for('marking'))
    else:
        return redirect(url_for('signin'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    form = SignupForm()

    if request.method == 'POST':
        if form.validate() == False:
            return render_template('signup.html', form=form)
        else:
            newuser = User(form.email.data, form.password.data)
            db.session.add(newuser)
            db.session.commit()
            session['uid'] = newuser.uid    # only after commit(), newuser will get a valid uid value
            return redirect(url_for('marking'))

    elif request.method == 'GET':
        return render_template('signup.html', form=form)

@app.route('/signin', methods=['GET', 'POST'])
def signin():
    form = SigninForm()

    if request.method == 'POST':
        if form.validate() == False:
            return render_template('signin.html', form=form)
        else:
            user = User.query.filter_by(email = form.email.data).first()
            session['uid'] = user.uid
            return redirect(url_for('marking'))

    elif request.method == 'GET':
        return render_template('signin.html', form=form)

@app.route('/signout')
def signout():
    if 'uid' not in session:
        return redirect(url_for('signin'))

    session.pop('uid', None)
    return redirect(url_for('home'))

@app.route('/marking')
def marking():
    if 'uid' not in session:
        return redirect(url_for('signin'))

    tasklist = Task.query.filter_by(uid = session['uid']).all()
    celltypes = Celltype.query.all()
    return render_template('marking.html', tasklist = tasklist, celltypes = celltypes)


@app.route('/newtask', methods=['POST'])
def newtask():
    tname = request.form['tname']
    task = Task(session['uid'], tname)
    db.session.add(task)
    db.session.commit()
    os.mkdir(os.path.join(app.config['UPLOAD_FOLDER'], str(task.tid)))
    return json.dumps({'success':'1'})

@app.route('/gettasklist')
def gettasklist():
    if 'uid' not in session:
        return redirect(url_for('signin'))

    tasklist = db.session.query(Task.tid, Task.tname).filter_by(uid = session['uid'])
    return json.dumps(dict(tasklist))

@app.route('/gettaskinfo')
def gettaskinfo():
    if 'uid' not in session:
        return redirect(url_for('signin'))

    tid = request.args.get('tid', type=int)
    task = Task.query.filter_by(tid = tid).first()
    imgs = {}
    if task.imgnumttl:
        imgs = dict(db.session.query(Image.iid, Image.imgname).filter_by(tid = tid).all())
    return json.dumps({'imgnumttl':task.imgnumttl, 'imgnummrk':task.imgnummrk, 'state':task.state, 'imglist':imgs})

@app.route('/getresultsall')
def getresultsall():
    if 'uid' not in session:
        return redirect(url_for('signin'))

    tasklist = Task.query.filter_by(uid = session['uid']).all()
    return json.dumps({'injecthtml': render_template('allresults.html', tasklist=tasklist)})


@app.route('/getresultdetail/<tid>')
def getresultdetail(tid):
    if 'uid' not in session:
        return redirect(url_for('signin'))

    task = Task.query.filter_by(tid = tid).first()
    user = User.query.filter_by(uid = session['uid']).first()
    taskdet = 'Taskname: ' +  task.tname + '\r\nCreator: ' + user.email + '\r\n-------------------------\r\n'
    imagelist = Image.query.filter_by(tid = tid).all()
    celltypes = Celltype.query.all()
    taskdet += 'Image name, Mark Type, Cell Type, Intensity, Mark Location\r\n'
    for image in imagelist:
        if image.bbxnum:
            marks = json.loads(image.bbx)
            for mark in marks:
                if mark['type'] == 'circle':
                    taskdet += image.imgname + ', ' + mark['type'] + ', ' + celltypes[int(mark['cellidx'])-1].ctname +', ' + mark['cellint'] + ', (' + str(mark['ox']) + ', ' + str(mark['oy']) + ')\r\n'
                if mark['type'] == 'rect':
                    taskdet += image.imgname + ', ' + mark['type'] + ', ' + celltypes[int(mark['cellidx'])-1].ctname +', ' + mark['cellint'] + ', (' + str(mark['left']) + ', ' + str(mark['top']) + ', ' + str(mark['width']) + ', ' + str(mark['height']) + ')\r\n'



    strIO = StringIO.StringIO()
    strIO.write(str(taskdet))
    strIO.seek(0)
    return send_file(strIO,
            attachment_filename="report-task-" + str(tid) + ".txt",
            as_attachment=True)


def allowed_file(filename):
    return '.' in filename and \
            filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/uploadimgs', methods=['POST'])
def uploadimgs():
    newimgs = request.files.getlist('newimgs')
    tid = request.form['tid']
    oldimgs = db.session.query(Image.imgname).filter_by(tid = tid).all()
    oldimglist = [i for j in oldimgs for i in j]
    incre = 0
    for img in newimgs:
        imgname = secure_filename(img.filename)
        if imgname and allowed_file(imgname) and imgname not in oldimglist:
            img.save(os.path.join(app.config['UPLOAD_FOLDER'], tid, imgname))
            image = Image(tid, imgname)
            db.session.add(image)
            incre += 1

    if incre:
        task = Task.query.filter_by(tid = tid).first()
        task.imgnumttl += incre
        task.state = False
    db.session.commit()

    imgs = {}
    if len(oldimglist) or incre:
        imgs = dict(db.session.query(Image.iid, Image.imgname).filter_by(tid = tid).all())

    return json.dumps({'success':'1', 'imglist':imgs})

@app.route('/savemarks')
def savemarks():
    if 'uid' not in session:
        return redirect(url_for('signin'))

    iid = request.args.get('iid', type=int)
    if iid is None:
        return json.dumps({'success':'0', 'error':'no image specified'})

    bbx = request.args.get('marksjsonstring')
    marks = json.loads(bbx)
    image = Image.query.filter_by(iid = iid).first()
    task = Task.query.filter_by(tid = image.tid).first()
    if not image.bbxnum and len(marks):
        task.imgnummrk += 1
    if not len(marks) and image.bbxnum:
        task.imgnummrk -= 1
    image.bbx = bbx
    image.bbxnum = len(marks)
    if task.imgnummrk == task.imgnumttl:
        task.state = True
    else:
        task.state = False
    db.session.commit()
    return json.dumps({'success':'1'})

@app.route('/getmarks')
def getmarks():
    if 'uid' not in session:
        return redirect(url_for('signin'))

    iid = request.args.get('iid', type=int)
    if iid is None:
        return json.dumps({'success':'0', 'error':'no image specified'})
    image = Image.query.filter_by(iid = iid).first()
    return json.dumps({'success':'1', 'marksjsonstring':image.bbx})

if __name__ == "__main__":
    app.run(debug=True)

