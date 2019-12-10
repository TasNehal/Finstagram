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

#These methods show all the pictures of a user not shared to all followers and allows them to
#pick an available group to share it too
@app.route("/images", methods=["GET"])
@login_required
def images():
    query = "SELECT * FROM photo WHERE photoPoster=%s AND allFollowers=%s"
    groupQuery = "SELECT DISTINCT groupName, owner_username FROM BelongTo WHERE member_username=%s"
    currentUser=session["username"]
    try:
        with connection.cursor() as cursor:
            cursor.execute(query, (currentUser, False))
        data = cursor.fetchall()
        if (not data):
            error = "You don't currently have any photos that aren't shared with all followers"
            return render_template('home.html', error=error)
        with connection.cursor() as cursor:
            cursor.execute(groupQuery, (currentUser))
        groupData=cursor.fetchall()
        if (not groupData):
            error = "You are not currently part of any groups"
            return render_template('home.html', error=error)
        return render_template("images.html", images=data, groups=groupData)
    except pymysql.err.IntegrityError:
        error = "An error has occured, please try again later"
        return render_template("home.html", error=error)

@app.route("/sharePhoto", methods=["POST"])
@login_required
def sharePhoto():
    if request.form:
        requestData = request.form
        requestData = request.form
        groupOwner = (requestData["groupName"].split(","))[1]
        groupName = (requestData["groupName"].split(","))[0]
        photoID = requestData["photoID"]

        try:
            with connection.cursor() as cursor:
                query = "INSERT INTO SharedWith (groupOwner, groupName, photoID) VALUES (%s, %s, %s)"
                cursor.execute(query, (groupOwner, groupName, photoID))
        except pymysql.err.IntegrityError:
            error = "This photo was already shared with %s" % (groupName)
            return render_template('home.html', error=error)

        error = "Photo has been successfully shared with %s" % (groupName)
        return render_template('home.html', error=error)

    error = "An error has occurred. Please try again."
    return render_template("home.html", error=error)

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

        #originally had checking code here but that was made redundant after changing database engine to InnoDB, no foreign key issues now
        try:
            with connection.cursor() as cursor:

                query = "INSERT INTO BelongTo (member_username, owner_username, groupName) VALUES (%s, %s, %s)"
                cursor.execute(query, (member_username, owner_username, groupName))

        except pymysql.err.IntegrityError:
            error = "%s is already in the group %s made by %s or does not exist." % (member_username, groupName, owner_username)
            return render_template("addFriend.html", error=error)

        return redirect(url_for("home"))

    error = "An error has occurred. Please try again."
    return render_template("addFriend.html", error=error)

#These are my methods for sending someone a follow request and for the and for the followed user to manage that request

#This creates the html forms
@app.route("/follow", methods=["GET"])
def follow():
    return render_template("follow.html")

#This method proccesses the form and validates any query for sending a follow request
@app.route("/sendFollow", methods=["POST"])
@login_required
def sendFollow():
    if request.form:
        requestData = request.form
        username_followed = requestData["username_followed"]
        username_follower = session["username"]
        followstatus = False

        try:
            with connection.cursor() as cursor:
                query = "SELECT * FROM Follow WHERE username_followed=%s AND username_follower=%s"
                cursor.execute(query, (username_follower, username_followed))
                exist = cursor.fetchall()
                if exist:
                    error = "There is already an existing follow request from %s or you are already following each other." % (username_followed)
                    return render_template("follow.html", error=error)
                query = "INSERT INTO Follow (username_followed, username_follower, followstatus) VALUES (%s, %s, %s)"
                cursor.execute(query, (username_followed, username_follower, followstatus))

        except pymysql.err.IntegrityError:
            error = "%s does not exist or follow request already sent." % (username_followed)
            return render_template("follow.html", error=error)

        return redirect(url_for("home"))

#Abstracted pages for accepting and rejecting follows (easier to code)
#accept and reject display current follow requests and renders forms to choose requests
@app.route("/accept", methods=["GET"])
@login_required
def accept():
    query = "SELECT * FROM Follow WHERE username_followed=%s AND followstatus=False"
    currentUser = session["username"]
    with connection.cursor() as cursor:
        cursor.execute(query, (currentUser))
    data = cursor.fetchall()
    if (not data):
        error = "You need to recieve a follow request first"
        return render_template("home.html", error=error)
    return render_template("accept.html", requests=data)

@app.route("/reject", methods=["GET"])
@login_required
def reject():
    query = "SELECT * FROM Follow WHERE username_followed=%s AND followstatus=False"
    currentUser = session["username"]
    with connection.cursor() as cursor:
        cursor.execute(query, (currentUser))
    data = cursor.fetchall()
    if (not data):
        error = "You need to recieve a follow request first"
        return render_template("home.html", error=error)
    return render_template("reject.html", requests=data)

#The accept/rejectFollow methods processes the forms and updates the tables
@app.route("/acceptFollow", methods=["POST"])
@login_required
def acceptFollow():
    if request.form:
        requestData = request.form
        username_follower = requestData["username_follower"]
        username_followed = session["username"]
        followstatus = True

        try:
            with connection.cursor() as cursor:
                query = "UPDATE Follow SET followstatus=%s WHERE username_followed=%s AND username_follower=%s"
                cursor.execute(query, (followstatus, username_followed, username_follower))

        except pymysql.err.IntegrityError:
            error = "An error has occurred. Please try again."
            return render_template("home.html", error=error)

        error = "Follow request from %s was accepted" % (username_follower)
        return render_template("home.html", error=error)

    error = "An error has occurred. Please try again."
    return render_template("home.html", error=error)

@app.route("/rejectFollow", methods=["POST"])
@login_required
def rejectFollow():
    if request.form:
        requestData = request.form
        username_follower = requestData["username_follower"]
        username_followed = session["username"]

        try:
            with connection.cursor() as cursor:
                query = "DELETE FROM Follow WHERE username_follower=%s AND username_followed=%s"
                cursor.execute(query, (username_follower, username_followed))

        except pymysql.err.IntegrityError:
            error = "An error has occurred. Please try again."
            return render_template("home.html", error=error)

        error = "Follow request from %s was rejected" % (username_follower)
        return render_template("home.html", error=error)

    error = "An error has occurred. Please try again."
    return render_template("home.html", error=error)

#function to see other people's photos and additional info like id, time, likes, etc.
@app.route("/gallery", methods=["GET"])
@login_required
def gallery():
    #3 queries to get the visible photos, tags, and Likes
    #select everything from likes and tags and use the jinja template in gallery.html to display the right values
    photoQuery = "SELECT DISTINCT photoID, postingdate, caption, photoPoster, filepath, firstName, lastName FROM photo INNER JOIN person ON person.username = photo.photoPoster WHERE photoPoster IN (SELECT username_followed FROM follow WHERE followstatus = 1 AND username_follower=%s) OR photoID IN ( SELECT photoID FROM sharedwith NATURAL JOIN belongto WHERE member_username=%s) ORDER BY postingdate DESC"
    tagQuery = "SELECT * FROM tagged NATURAL JOIN person WHERE tagstatus=True"
    likeQuery = "SELECT * FROM likes NATURAL JOIN person"
    currentUser=session["username"]

    with connection.cursor() as cursor:
        cursor.execute(photoQuery, (currentUser, currentUser))
        photos=cursor.fetchall()

        cursor.execute(tagQuery)
        tags=cursor.fetchall()

        cursor.execute(likeQuery)
        likes=cursor.fetchall()

    return render_template("gallery.html", photos=photos, likes=likes, tags=tags)






@app.route("/logout", methods=["GET"])
def logout():
    session.pop("username")
    return redirect("/")

#redesigned upload image so that if you dont pick allfollowers, there is another
#function that lets you choose which group gets to see the chosen photo
@app.route("/uploadImage", methods=["POST"])
@login_required
def upload_image():
    if request.files:
        requestData = request.form
        image_file = request.files.get("imageToUpload", "")
        image_name = image_file.filename
        filepath = os.path.join(IMAGES_DIR, image_name)
        image_file.save(filepath)
        caption=requestData["caption"]
        photoPoster=session["username"]
        if (requestData["status"] == "True"):
            allFollowers=True
        else:
            allFollowers=False
        photoQuery = "INSERT INTO photo (postingdate, filePath, allFollowers, caption, photoPoster) VALUES (%s, %s, %s, %s, %s)"
        with connection.cursor() as cursor:
            cursor.execute(photoQuery, (time.strftime('%Y-%m-%d %H:%M:%S'), image_name, allFollowers, caption, photoPoster))
            if (allFollowers):
                searchQuery = "SELECT DISTINCT groupName, owner_username FROM BelongTo WHERE member_username=%s"
                cursor.execute(searchQuery, (photoPoster))
                groups=cursor.fetchall()
                idQuery = "SELECT MAX(photoID) as id FROM photo"
                cursor.execute(idQuery)
                photoID = cursor.fetchone()["id"]
                sharedQuery = "INSERT INTO SharedWith (groupOwner, groupName, photoID) VALUES (%s, %s, %s)"
                for group in groups:
                    groupName=group["groupName"]
                    groupOwner=group["owner_username"]
                    cursor.execute(sharedQuery, (groupOwner, groupName, photoID))

        message = "Image has been successfully uploaded."
        return render_template("upload.html", message=message)
    else:
        message = "Failed to upload image."
        return render_template("upload.html", message=message)

if __name__ == "__main__":
    if not os.path.isdir("images"):
        os.mkdir(IMAGES_DIR)
    app.run(debug=True)
