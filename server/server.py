from flask import Flask, render_template, request, redirect, url_for, make_response, flash
from flask_mail import Mail, Message
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from datetime import timezone
import pickle

app = Flask(__name__, template_folder="../src", static_folder='../src', static_url_path='/')

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db' #three slashes in relative path four is absolute path
app.config['SQLALCHEMY_BINDS'] = {'courses' : 'sqlite:///courses.db'}
db = SQLAlchemy(app) #initialize databse with app settings

app.config['MAIL_SERVER']='smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = '' #Blank on purpose
app.config['MAIL_PASSWORD'] = '' #Blank on purpose
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
mail = Mail(app)


class User(db.Model):
    username = db.Column(db.String, primary_key=True)
    password = db.Column(db.String)
    email = db.Column(db.String)

    def __repr__(self):
        return '<Users %r>' % self.description


class Courses(db.Model):
    __bind_key__ = 'courses'
    request_number = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String)
    course_to_drop = db.Column(db.String)
    course_to_add = db.Column(db.String)
    time = db.Column(db.Integer)
    status = db.Column(db.String)




class GenerateRequest:
    @classmethod
    def generateRequest(self):
        with open('count.val', 'rb') as count_val_file:
            count = pickle.load(count_val_file)
        count = count +  1
        with open('count.val', 'wb') as count_val_file:
            pickle.dump(count, count_val_file)
        return count


@app.route("/")
def index():
    message = request.args.get('message')
    if (message == None):
        message = ''
    return render_template('index.html', message=message)

@app.route('/login', methods=['get', 'post'])
def login():
    message = ''
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        for user in db.session.query(User).filter_by(username=username):
            if user.password == password:
                #add something so that this times out if no activity from user
                response = make_response(redirect(url_for('home')))
                print(url_for('home'))
                response.set_cookie('username', value=username, max_age=3600)
                return response
                
    message = "Wrong username or password"
    return redirect(url_for('index', message=message))

@app.route("/createAccount", methods=['get', 'post'])
def createAccount():
    if request.method == "POST":
        fullName = request.form.get('full-name')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        print (fullName + " " + username + " " + email + " " + password)

        #Add password hashing
        user = User(username=username, password=password, email=email)
        db.session.add(user)
        db.session.commit()

        return redirect(url_for('index', message='Account creation successful'))
    else:   
        return app.send_static_file('createAccount.html') #Add in handling here for incorrect account creation


@app.route("/home", methods=['get', 'post'])
def home():
    username = request.cookies.get('username')
    if request.method == "POST":
        if request.form.get('type') == 'add':
            dt_now = datetime.now(tz=timezone.utc)
            courses = Courses(course_to_add=request.form.get('course-to-add'), course_to_drop=request.form.get('course-to-drop'), 
                username=username, time=dt_now, status='Awaiting Match', request_number=GenerateRequest.generateRequest())
            db.session.add(courses)
            db.session.commit()
            findPartner(courses)
        elif request.form.get('type') == 'delete':
            courses = Courses(course_to_add=request.form.get('course-to-add'), course_to_drop=request.form.get('course-to-drop'), 
                username=username, time=request.form.get('time'), status='Match Found', request_number=-1)
            deselect(courses)
            db.session.query(Courses).filter_by(request_number=request.form.get('request_number')).delete()
            db.session.commit()


    tasks = db.session.query(Courses).filter_by(username=username)

    return render_template("accountHome.html", username=username, tasks=tasks)

def deselect(courses):
    username = request.cookies.get('username')
    possibleMatches = db.session.query(Courses).filter_by(course_to_add=courses.course_to_drop, course_to_drop=courses.course_to_add).all()

    minTimeObj = datetime.now(tz=timezone.utc)
    minTime = str(minTimeObj)[:26]
    bestMatch = None
    for match in possibleMatches:
        if match.username == username or match.status == 'Awaiting Match':
            continue
        elif datetime.strptime(minTime,'%Y-%m-%d %H:%M:%S.%f') > datetime.strptime(match.time[:26], '%Y-%m-%d %H:%M:%S.%f'):
            minTime = match.time
            bestMatch = match
    if bestMatch == None:
        return

    match.status = "Awaiting Match"
    db.session.commit()

def findPartner(courses):
    username = request.cookies.get('username')
    course_to_drop = courses.course_to_drop
    course_to_add = courses.course_to_add
    possibleMatches = db.session.query(Courses).filter_by(course_to_add=course_to_drop, course_to_drop=course_to_add).all()

    minTimeObj = datetime.now(tz=timezone.utc)
    minTime = str(minTimeObj)[:26]
    bestMatch = None
    for match in possibleMatches:
        if match.username == username or match.status == 'Match Found':
            continue
        elif datetime.strptime(minTime,'%Y-%m-%d %H:%M:%S.%f') > datetime.strptime(match.time[:26], '%Y-%m-%d %H:%M:%S.%f'):
            minTime = match.time
            bestMatch = match

    if bestMatch == None:
        return

    user1 =  db.session.query(User).filter_by(username=match.username).first()
    #add email code here!

    #Sets website status to be updated
    match.status = "Match Found"
    courses.status = "Match Found"
    db.session.commit()

    user2 = db.session.query(User).filter_by(username=username).first()
    msg = Message('Penn Course Swap Match Found!', sender = 'vikrambala2002@gmail.com', recipients = [user1.email, user2.email])
    msg.body = "A match has been found for the courses: {}, {}. Here's the contact info for both of you to contact each other: {} - {}, {} - {}".format(course_to_add, course_to_drop, user1.username, user1.email, user2.username, user2.email)
    mail.send(msg)
    print("Sent message to {} + {}".format(user1.email, user2.email))


@app.route("/about")
def about():
    return app.send_static_file('about.html')
    

if __name__ == "__main__":
    app.run()