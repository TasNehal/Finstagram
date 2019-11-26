from flask import Flask, render_template, request, session, redirect, url_for, send_file
import os
import uuid
import hashlib
import pymysql.cursors
from functools import wraps
import time

#Finstagram base made using provided sample code from dannnylin

app = Flask(__name__)
app.secret_key = "super secret key"
IMAGES_DIR = os.path.join(os.getcwd(), "images")

connection = pymysql.connect(host="localhost",
                             user="root",
                             password="",
                             db="finstagram",
                             charset="utf8mb4",
                             port=3306,
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)

SALT = 'cs3083'

def login_required(f):
    @wraps(f)
    def dec(*args, **kwargs):
        if not "username" in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return dec

@app.route("/")
def index():
    if "username" in session:
        return redirect(url_for("home"))
    return render_template("index.html")

@app.route("/home")
@login_required
def home():
    return render_template("home.html", username=session["username"])

@app.route("/upload", methods=["GET"])
@login_required
def upload():
    return render_template("upload.html")

@app.route("/images", methods=["GET"])
@login_required
def images():
    query = "SELECT * FROM photo"
    with connection.cursor() as cursor:
        cursor.execute(query)
    data = cursor.fetchall()
    return render_template("images.html", images=data)

@app.route("/image/<image_name>", methods=["GET"])
def image(image_name):
    image_location = os.path.join(IMAGES_DIR, image_name)
    if os.path.isfile(image_location):
        return send_file(image_location, mimetype="image/jpg")

@app.route("/login", methods=["GET"])
def login():
    return render_template("login.html")

@app.route("/register", methods=["GET"])
def register():
    return render_template("register.html")

@app.route("/loginAuth", methods=["POST"])
def loginAuth():
    if request.form:
        requestData = request.form
        username = requestData["username"]
        plaintextPasword = requestData["password"] + SALT
        hashedPassword = hashlib.sha256(plaintextPasword.encode("utf-8")).hexdigest()

        with connection.cursor() as cursor:
            query = "SELECT * FROM person WHERE username = %s AND password = %s"
            cursor.execute(query, (username, hashedPassword))
        data = cursor.fetchone()
        if data:
            session["username"] = username
            return redirect(url_for("home"))

        error = "Incorrect username or password."
        return render_template("login.html", error=error)

    error = "An unknown error has occurred. Please try again."
    return render_template("login.html", error=error)


@app.route("/registerAuth", methods=["POST"])
def registerAuth():
    if request.form:
        requestData = request.form
        username = requestData["username"]
        plaintextPasword = requestData["password"] + SALT
        hashedPassword = hashlib.sha256(plaintextPasword.encode("utf-8")).hexdigest()
        firstName = requestData["fname"]
        lastName = requestData["lname"]
        bio = requestData["bio"]

        try:
            with connection.cursor() as cursor:
                query = "INSERT INTO person (username, password, firstName, lastName, bio) VALUES (%s, %s, %s, %s, %s)"
                cursor.execute(query, (username, hashedPassword, firstName, lastName, bio))
        except pymysql.err.IntegrityError:
            error = "%s is already taken." % (username)
            return render_template('register.html', error=error)

        return redirect(url_for("login"))

    error = "An error has occurred. Please try again."
    return render_template("register.html", error=error)

#These are my methods for makiing a Friendgroup

#This method creates the html forms entering a groupname and description
@app.route("/createGroup", methods=["GET"])
def createGroup():
    return render_template("createGroup.html")

#This method handles processing the data sent by these forms and creates a group
@app.route("/makeGroup", methods=["POST"])
@login_required
def makeGroup():
    if request.form:
        requestData = request.form
        groupOwner = session["username"]
        groupName = requestData["groupName"]
        description = requestData["description"]

        try:
            with connection.cursor() as cursor:
                query = "INSERT INTO Friendgroup (groupOwner, groupName, description) VALUES (%s, %s, %s)"
                cursor.execute(query, (groupOwner, groupName, description))
                query2 = "INSERT INTO BelongTo (member_username, owner_username, groupName) VALUES (%s, %s, %s)"
                cursor.execute(query2, (groupOwner, groupOwner, groupName))
        except pymysql.err.IntegrityError:
            error = "%s is already taken." % (groupName)
            return render_template('createGroup.html', error=error)

        error = "Group %s has been successfully made." % (groupName)
        return render_template('createGroup.html', error=error)

    error = "An error has occurred. Please try again."
    return render_template("createGroup.html", error=error)

#my methods to add someone to a Friendgroup

#This method shows all the groups the current user owns and
#creates the html forms for adding another user to this group
#redirects user back to home if user isnt part of any groups
@app.route("/addFriend", methods=["GET"])
@login_required
def addFriend():
    query = "SELECT DISTINCT groupName, owner_username FROM BelongTo WHERE member_username=%s"
    currentUser = session["username"]
    with connection.cursor() as cursor:
        cursor.execute(query, (currentUser))
    data = cursor.fetchall()
    if (not data):
        error = "You need to be part of a group first"
        return render_template("home.html", error=error)
    return render_template("addFriend.html", groups=data)

#This method handles the form processing for adding someone to a Friendgroup
@app.route("/addMember", methods=["POST"])
@login_required
def addMember():
    if request.form:
        requestData = request.form
        owner_username = (requestData["groupName"].split(","))[1]
        groupName = (requestData["groupName"].split(","))[0]
        member_username = requestData["member_username"]

        #was getting an issue where i could add a nonexisting user into any groups
        #despite the foreign key constraint resolved this by manually checking if user exists first
        try:
            with connection.cursor() as cursor:
                query = "SELECT username FROM Person WHERE username = %s"
                cursor.execute(query, (member_username))
                exist = cursor.fetchall()
                if (not exist):
                    error = "%s does not exist." % (member_username)
                    return render_template("home.html", error=error)
                query = "SELECT * FROM BelongTo WHERE member_username=%s AND owner_username=%s AND groupName=%s"
                cursor.execute(query, (member_username, owner_username, groupName))
                exist = cursor.fetchall()
                if (exist):
                    error = "%s is already in the group %s made by %s." % (member_username, groupName, owner_username)
                    return render_template("home.html", error=error)

                query2 = "INSERT INTO BelongTo (member_username, owner_username, groupName) VALUES (%s, %s, %s)"
                cursor.execute(query2, (member_username, owner_username, groupName))

        except pymysql.err.IntegrityError:
            error = "%s is already in the group %s made by %s or does not exist." % (member_username, groupName, owner_username)
            return render_template("addFriend.html", error=error)

        return redirect(url_for("home"))

    error = "An error has occurred. Please try again."
    return render_template("addFriend.html", error=error)

#These are my methods for sending someone a follow requset

#This creates the html forms
@app.route("/follow", methods=["GET"])
def follow():
    return render_template("follow.html")

#This method proccesses the form and validates any query for sending a follow request
@app.route("/sendFollow", methods=["POST"])
@login_required
def addMember():
    if request.form:
        requestData = request.form
        username_followed = requestData["username_followed"]
        username_follower = session["username"]
        followstatus = False

        #was getting an issue where i could add a nonexisting user into any groups
        #despite the foreign key constraint resolved this by manually checking if user exists first
        try:
            with connection.cursor() as cursor:
                #query = "SELECT username FROM Person WHERE username = %s"
                #cursor.execute(query, (member_username))
                #exist = cursor.fetchall()
                #if (not exist):
                #    error = "%s does not exist." % (member_username)
                #    return render_template("home.html", error=error)
                #query = "SELECT * FROM BelongTo WHERE member_username=%s AND owner_username=%s AND groupName=%s"
                #cursor.execute(query, (member_username, owner_username, groupName))
                #exist = cursor.fetchall()
                #if (exist):
                #    error = "%s is already in the group %s made by %s." % (member_username, groupName, owner_username)
                #    return render_template("home.html", error=error)

                query = "INSERT INTO Follow (username_followed, username_follower, followstatus) VALUES (%s, %s, %s)"
                cursor.execute(query, (username_followed, username_follower, followstatus))
        except pymysql.err.IntegrityError:
            error = "%s does not exist or you have already sent a follow request." % (username_followed)
            return render_template("follow.html", error=error)

        return redirect(url_for("home"))


@app.route("/logout", methods=["GET"])
def logout():
    session.pop("username")
    return redirect("/")

@app.route("/uploadImage", methods=["POST"])
@login_required
def upload_image():
    if request.files:
        image_file = request.files.get("imageToUpload", "")
        image_name = image_file.filename
        filepath = os.path.join(IMAGES_DIR, image_name)
        image_file.save(filepath)
        query = "INSERT INTO photo (timestamp, filePath) VALUES (%s, %s)"
        with connection.cursor() as cursor:
            cursor.execute(query, (time.strftime('%Y-%m-%d %H:%M:%S'), image_name))
        message = "Image has been successfully uploaded."
        return render_template("upload.html", message=message)
    else:
        message = "Failed to upload image."
        return render_template("upload.html", message=message)

if __name__ == "__main__":
    if not os.path.isdir("images"):
        os.mkdir(IMAGES_DIR)
    app.run(debug=True)
