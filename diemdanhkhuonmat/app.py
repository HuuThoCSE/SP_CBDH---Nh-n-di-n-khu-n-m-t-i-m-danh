from flask import Flask, render_template, request, session, redirect, url_for, Response, jsonify, send_file
import mysql.connector
import cv2
from PIL import Image
import numpy as np
import os
import time
from datetime import date
import secrets
from playsound import playsound
from openpyxl import Workbook
import openpyxl
import datetime

from modules.appDayClass import appDayClass
from modules.appDayRoom import appDayRoom

# IP = '192.168.0.102'
# IP = '172.20.10.3'
IP = 'localhost'

# Device_Video = 1
Device_Video = 'http://192.168.0.102:4747/video'
# Device_Video = 'http://192.168.2.127:4747/video'

app = Flask(__name__, static_folder='static')
app.secret_key = secrets.token_urlsafe(16)

# Đăng ký Blueprints vào app
app.register_blueprint(appDayClass, url_prefix='/DayClass')
app.register_blueprint(appDayRoom, url_prefix='/DayRoom')

cnt = 0
pause_cnt = 0
justscanned = False

mydb = mysql.connector.connect(
    host="localhost",
    user="root",
    passwd="",
    database="flask_db"
)

mycursor = mydb.cursor()

# <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< Generate dataset >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
def generate_dataset(nbr):
    face_classifier = cv2.CascadeClassifier(
        "resources/haarcascade_frontalface_default.xml")

    def face_cropped(img):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_classifier.detectMultiScale(gray, 1.3, 5)
        # scaling factor=1.3
        # Minimum neighbor = 5

        if len(faces) == 0:
            return None
        for (x, y, w, h) in faces:
            cropped_face = img[y:y + h, x:x + w]
        return cropped_face

    cap = cv2.VideoCapture(Device_Video)

    mycursor.execute("select ifnull(max(img_id), 0) from img_dataset")
    row = mycursor.fetchone()
    lastid = row[0]

    img_id = lastid
    max_imgid = img_id + 100
    count_img = 0

    while True:
        ret, img = cap.read()
        if face_cropped(img) is not None:
            count_img += 1
            img_id += 1
            face = cv2.resize(face_cropped(img), (200, 200))
            face = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)

            file_name_path = "dataset/" + nbr + "." + str(img_id) + ".jpg"
            cv2.imwrite(file_name_path, face)
            cv2.putText(face, str(count_img), (50, 50), cv2.FONT_HERSHEY_COMPLEX, 1, (0, 255, 0), 2)

            mycursor.execute("""INSERT INTO img_dataset (img_id, img_person) VALUES ('{}', '{}')""".format(img_id, nbr))
            mydb.commit()

            frame = cv2.imencode('.jpg', face)[1].tobytes()
            yield (b'--frame\r\n'b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

            if cv2.waitKey(1) == 13 or int(img_id) == int(max_imgid):
                break

    cap.release()
    cv2.destroyAllWindows()
# <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< Train Classifier >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
@app.route('/train_classifier/<nbr>')
def train_classifier(nbr):
    dataset_dir = "dataset"

    path = [os.path.join(dataset_dir, f) for f in os.listdir(dataset_dir)]
    faces = []
    ids = []

    for image in path:
        img = Image.open(image).convert('L');
        imageNp = np.array(img, 'uint8')
        id = int(os.path.split(image)[1].split(".")[1])

        faces.append(imageNp)
        ids.append(id)
    ids = np.array(ids)

    # Train the classifier and save
    clf = cv2.face.LBPHFaceRecognizer_create()
    clf.train(faces, ids)
    clf.write("classifier.xml")

    playsound("static\\sound\\ThemNguoidungThanhcong.wav")

    return redirect('/')


# <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< Face Recognition >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
def face_recognition(idDayClass):  # generate frame by frame from camera
    def draw_boundary(img, classifier, scaleFactor, minNeighbors, color, text, clf):
        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # img_tensor = torch.from_numpy(img_gray).cuda()  # Convert to CUDA tensor

        features = classifier.detectMultiScale(img_gray, scaleFactor, minNeighbors)
        # features = classifier.detectMultiScale(img_gray, scaleFactor, minNeighbors)

        global justscanned
        global pause_cnt

        pause_cnt += 1

        coords = []
        

        for (x, y, w, h) in features:
            cv2.rectangle(img, (x, y), (x + w, y + h), color, 2)
            id, pred = clf.predict(img_gray[y:y + h, x:x + w])
            # id, pred = clf(img_tensor[y:y + h, x:x + w])
            confidence = int(100 * (1 - pred / 300))

            if confidence > 70 and not justscanned:
                global cnt
                cnt += 1

                n = (100 / 30) * cnt
                # w_filled = (n / 100) * w
                w_filled = (cnt / 30) * w

                cv2.putText(img, str(int(n)) + ' %', (x + 20, y + h + 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                            (153, 255, 255), 2, cv2.LINE_AA)

                cv2.rectangle(img, (x, y + h + 40), (x + w, y + h + 50), color, 2)
                cv2.rectangle(img, (x, y + h + 40), (x + int(w_filled), y + h + 50), (153, 255, 255), cv2.FILLED)

                mycursor.execute("select a.img_person, b.nameUser "
                                 "  from img_dataset a "
                                 "  left join dUsers b on a.img_person = b.idUser "
                                 " where img_id = " + str(id))
                row = mycursor.fetchone()

                if row:
                    idUser = row[0]
                    pname = row[1]
                else:
                    idUser = "Unknown"
                    pname = "Unknown"

                if int(cnt) == 30:
                    cnt = 0

                    # Lấy id_dayclass cao nhất hiện tại
                    mycursor.execute("SELECT MAX(id_enrolldayclass) FROM enroll_dayclass")
                    max_id = mycursor.fetchone()[0]
                    if max_id is None:
                        new_id = 1  # Bắt đầu từ ID 1 nếu bảng rỗng 
                    else:
                        new_id = int(max_id) + 1

                    try:
                        # Thực hiện chèn hoặc cập nhật
                        # query = "INSERT INTO enroll_dayclass (id_enrolldayclass, id_dayclass, idUser, status) VALUES (%s, %s, %s, %s) ON DUPLICATE KEY UPDATE status = 1"
                        query = "INSERT INTO enroll_dayclass (id_enrolldayclass, idDayClass, idUser, status) VALUES (%s, %s, %s, %s)"
                        values = (str(new_id), idDayClass, idUser, 1)
                        mycursor.execute(query, values)
                        mydb.commit()

                        playsound("static\\sound\\DiemdanhThanhcong.wav")
                    
                    except mysql.connector.errors.IntegrityError as e:
                        if e.errno == 1062:  # Lỗi trùng lặp khóa
                            # show_error_message("Dữ liệu đã tồn tại!")  # Hiển thị thông báo lỗi
                            playsound("static\\sound\\NguoidungDaDiemdanh.wav")

                            # from google.cloud import texttospeech
                            # client = texttospeech.TextToSpeechClient()
                            # text = "Xin chào, đây là thông báo từ hệ thống."
                            # language_code = "vi-VN"
                            # response = client.synthesize_speech(text=text, language_code=language_code)
                            # with open("welcome.wav", "wb") as out:
                            #     out.write(response.audio_content)
                        else:
                            raise e  # Đưa ra các lỗi khác

                    cv2.putText(img, pname, (x - 10, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (153, 255, 255), 2, cv2.LINE_AA)
                    time.sleep(1)

                    justscanned = True
                    pause_cnt = 0
            else:
                if not justscanned:
                    cv2.putText(img, 'UNKNOWN', (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2, cv2.LINE_AA)
                else:
                    cv2.putText(img, ' ', (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2, cv2.LINE_AA)

                if pause_cnt > 80:
                    justscanned = False

            coords = [x, y, w, h]
        return coords

    # def recognize(img_tensor, clf, faceCascade):
    def recognize(img, clf, faceCascade):
        coords = draw_boundary(img, faceCascade, 1.1, 10, (255, 255, 0), "Face", clf)
        # Assuming your faceCascade object has suitable CUDA equivalents
        # coords = draw_boundary(img_tensor, faceCascade, 1.1, 10, (255, 255, 0), "Face", clf) 
        return img
        # return img_tensor

    faceCascade = cv2.CascadeClassifier(
        "resources/haarcascade_frontalface_default.xml")
    clf = cv2.face.LBPHFaceRecognizer_create()
    # clf = clf.to('cuda') 
    clf.read("classifier.xml")

    wCam, hCam = 400, 400

    camera = cv2.VideoCapture(Device_Video)

    camera.set(3, wCam)
    camera.set(4, hCam)

    while True:
        ret, frame = camera.read()
        frame = recognize(frame, clf, faceCascade)

        frame = cv2.imencode('.jpg', frame)[1].tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')

        key = cv2.waitKey(1)
        if key == 27:
            break

def checklogin():
    if 'loggedin' in session:
        idPerm = session.get('idPerm')
        if idPerm == 0:
            return render_template('index_admin.html')
        elif idPerm == 1:
            data=loadCourseClass()
            return render_template('teacher_index.html')
        elif idPerm == 2:
            return render_template('index.html')
        return render_template('index.html')

@app.route('/')
def home():
    if 'loggedin' in session:
        idPerm = session.get('idPerm')
        if idPerm == 1:
            return render_template('index_admin.html')
        elif idPerm == 2:
            return render_template('teacher_index.html')
        elif idPerm == 3:
            return render_template('index.html')
        return render_template('index.html')
    return redirect(url_for('login')) 


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        query = "SELECT users1.*, personal.idPersonal FROM users1 left join Personal on personal.idUser = Users1.idUser WHERE username = %s"
        values = (username,)
        mycursor.execute(query, values)
        result = mycursor.fetchone()

        print(result)
        
        if result:
            fetched_hash = result[2]
            if fetched_hash == password:
                playsound("static\\sound\\DangnhapThanhcong.wav")
                # Đăng nhập thành công
                session['loggedin'] = True
                session['idPersonal'] = result[4]
                session['idPerm'] = result[3]
                return redirect(url_for('home'))
            else:
                # Mật khẩu không đúng
                # error = 'Invalid credentials'
                error = 'Mật khẩu không đúng ' + str(password) + ' - ' + str(fetched_hash)
                return render_template('login.html', error=error)
        else:
            # Tên người dùng không tồn tại
            # error = 'Invalid credentials'
            error = 'Tên người dùng không tồn tại'
            return render_template('login.html', error=error)

    return render_template('login.html') 

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        # password = request.form['password'].encode('utf-8')
        hashed_password = request.form['password'].encode('utf-8')
        # hashed_password = bcrypt.generate_password_hash(password)


        # Kiểm tra tên người dùng đã tồn tại hay chưa
        mycursor.execute("SELECT COUNT(*) FROM users1 WHERE username = %s", (username,))
        count = mycursor.fetchone()[0]

        if count > 0:
            # Tên người dùng đã tồn tại
            error = "Tên người dùng đã được sử dụng!"
            return render_template('register.html', error=error)

        # Tên người dùng hợp lệ, tiến hành thêm vào database
        mycursor.execute("""INSERT INTO users1 (username, password) VALUES (%s, %s)""", (username, hashed_password))
        mydb.commit()

        # Đăng ký thành công, chuyển về trang login
        success = "Đăng ký thành công! Vui lòng đăng nhập."
        return render_template('login.html', success=success)

    return render_template('register.html')


@app.route('/logout')
def logout():
    playsound("static\\sound\\XinchaoTambiec.wav")
    session.pop('loggedin', None)
    session.pop('username', None)
    session.pop('idPerm', None)
    return redirect(url_for('login'))
    


@app.route('/addprsn')
def addprsn():
    mycursor.execute("select ifnull(max(idUser) + 1, 101) from dusers")
    row = mycursor.fetchone()
    nbr = row[0]
    # print(int(nbr))

    return render_template('addprsn.html', newnbr=int(nbr))


@app.route('/addprsn_submit', methods=['POST'])
def addprsn_submit():
    prsnbr = request.form.get('txtnbr')
    prsname = request.form.get('txtname')

    query = ("INSERT INTO dusers (idUser, nameUser) VALUES (%s, %s)")
    values = (prsnbr, prsname)
    mycursor.execute(query, values)
    mydb.commit()

    # return redirect(url_for('home'))
    return redirect(url_for('vfdataset_page', prs=prsnbr))


@app.route('/vfdataset_page/<prs>')
def vfdataset_page(prs):
    return render_template('gendataset.html', prs=prs)


@app.route('/vidfeed_dataset/<nbr>')
def vidfeed_dataset(nbr):
    # Video streaming route. Put this in the src attribute of an img tag
    return Response(generate_dataset(nbr), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/video_feed', methods=['GET', 'POST'])
def video_feed():
    idDayClass = request.args.get('idDayClass')
    # Video streaming route. Put this in the src attribute of an img tag
    return Response(face_recognition(idDayClass), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/fr_page', methods=['GET', 'POST'])
def fr_page():
    idDayClass = request.args.get('idDayClass')
    """Video streaming home page."""
    mycursor.execute("select a.idUser, a.idUser"
                     "  from enroll_dayclass a "
                     "  left join dusers b on a.idUser = b.idUser "
                     " where a.accs_dated = curdate()"
                     " order by 1 desc")
    data = mycursor.fetchall()
    return render_template('fr_page.html', data=data, idDayClass=idDayClass)


@app.route('/countTodayScan', methods=['GET', 'POST'])
def countTodayScan():
    idDayClass = request.args.get('idDayClass')

    mycursor.execute("select count(*)"
                     " from enroll_dayclass"
                     " where idDayClass="+str(idDayClass))
    row = mycursor.fetchone()
    rowcount = row[0]

    return jsonify({'rowcount': rowcount})


@app.route('/loadData', methods=['GET', 'POST'])
def loadData():
    idDayClass = request.args.get('idDayClass')
    mycursor.execute("select a.id_enrolldayclass,a.idUser, b.mssv, b.nameUser, date_format(a.accs_dated, '%H:%i:%s')"
                     " from enroll_dayclass a"
                     " left join dusers b on a.idUser = b.idUser"
                     " where a.idDayClass = "+str(idDayClass)+
                     " order by 1 desc")
    data = mycursor.fetchall()
    return jsonify(response=data)

def update_name(idUser, FirstName):
    mycursor.execute("UPDATE dusers SET prs_name='{}' WHERE dUser={}".format(FirstName, idUser))
    mydb.commit()

def loadDataUser(idUser):
    mycursor.execute("select * from dusers where idUser = %s", (idUser,))
    return mycursor.fetchall()

def checklogin():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
# CourseClass
def loadCourseClass():
    mycursor.execute("SELECT * FROM CourseClass where hide=0 order by 1 desc")
    data = mycursor.fetchall()
    return data

@app.route('/CourseClass', methods=['GET', 'POST'])
def CourseClass():
    checklogin()
    return render_template('pn_CourseClass.html', data=loadCourseClass())

@app.route('/TeacherCourseClass', methods=['GET', 'POST'])
def TeacherCourseClass():
    checklogin()
    namePerm = ''
    if session.get('idPerm') == 1:
        namePerm = 'Techer'
    return render_template('teacher_CourseClass.html', data=loadCourseClass(), namePerm=namePerm)
    
@app.route('/addCourseClass', methods=['POST'])
def addCourseClass():
    codeCourseClass = request.form.get('codeCourseClass')
    nameCourseClass = request.form.get('nameCourseClass')
    mycursor.execute("INSERT INTO CourseClass (codeCourseClass, nameCourseClass) VALUES (%s, %s)", (codeCourseClass, nameCourseClass))
    mydb.commit()

    return render_template('pn_CourseClass.html', data=loadCourseClass())

@app.route('/editCourseClass', methods=['GET', 'POST'])
def editCourseClass():
    idCourseClass = request.args.get('idCourseClass')

    mycursor.execute("SELECT * FROM CourseClass where idCourseClass="+idCourseClass)
    data = mycursor.fetchall()

    return render_template('edit_CourseClass.html', data=data)

# @app.route('/clear_session_variable')
# def clear_session_variable():
#     session.pop('update_success', None) 
#     return 'Session variable cleared', 500 # Trả về  trạng thái ok 

@app.route('/updateCourseClass', methods=['GET', 'POST'])
def updateCourseClass():
    idCourseClass = request.args.get('idCourseClass')
    codeCourseClass = request.form['codeCourseClass']
    nameCourseClass = request.form['nameCourseClass']

    mycursor = mydb.cursor()
    query = ("UPDATE CourseClass SET codeCourseClass = %s,"
             " nameCourseClass = %s"
             " WHERE idCourseClass = %s")
    values = (codeCourseClass, nameCourseClass, idCourseClass)
    mycursor.execute(query, values)
    mydb.commit()

    # Lưu trữ thông báo thành công vàomycursor = mydb.cursor() session
    # session['update_success'] = True
    
    mycursor = mydb.cursor()
    mycursor.execute("SELECT * From CourseClass WHERE idCourseClass=%s", (idCourseClass,))
    data = mycursor.fetchall()
    # return render_template('edit_CourseClass.html', data=data)

    return render_template('edit_CourseClass.html', data=data,
                                alert_message="Cập nhật thành công!", 
                                alert_type="success", 
                                alert_duration=5)


# DayClass
def loadClass(idCourseClass):
    data = mycursor.execute("SELECT * FROM DayClass where idCourseClass=%s", (idCourseClass,))
    return data

@app.route('/DayClass', methods=['GET', 'POST'])
def dayclass():
    checklogin()
    idCourseClass = request.args.get('idCourseClass')
    return render_template('edit_DayClass.html', data=loadClass(idCourseClass), idCourseClass=idCourseClass)

# EnrollDayClass
@app.route('/enrolldayclass', methods=['GET', 'POST'])
def enrolldayclass():
    checklogin()
    idDayClass = request.args.get('idDayClass')
    return render_template('enrolldayclass.html', data=loadDayClass(idDayClass))

@app.route('/editUser', methods=['GET', 'POST'])
def editUser():
    if request.method == 'GET':
        idUser = request.args.get('idUser')

    elif request.method == 'POST':
        idUser = request.form.get('idUser')
        action = request.form.get('action')
        
        if action == 'update_name':
            # print("Hello")
            FirstName = request.form.get('FirstName')
            update_name(idUser, FirstName)

    return render_template('editUser.html', data=loadDataUser(idUser))

@app.route('/exportEnroll', methods=['GET'])
def exportEnroll():
    idDayClass = request.args.get('idDayClass')

    idPersonal = session.get('idPersonal')

    query = """
        SELECT dusers.mssv, dusers.nameUser, enroll_dayclass.accs_dated
        FROM enroll_dayclass
        LEFT JOIN dusers ON enroll_dayclass.idUser = dusers.idUser
        LEFT JOIN DayClass ON enroll_dayclass.idDayClass = DayClass.idDayClass
        LEFT JOIN courseclass ON courseclass.idCourseClass = DayClass.idCourseClass
        WHERE enroll_dayclass.idDayClass = %s
    """
    values = (idDayClass,)
    mycursor.execute(query, values)
    data = mycursor.fetchall()
    # data = mycursor.fetchmany()

    # Chuyển đổi tuple sang list
    data = [list(row) for row in data]

    # Tạo workbook và worksheet mới
    wb = Workbook()
    ws = wb.active

    ws.append(['ID', 'MSSV', 'Họ và tên', 'Thời gian điểm danh'])

    # Sử dụng enumerate để truy cập vị trí dòng và tự động tăng số thứ tự
    for index, row in enumerate(data, start=1):
        # row = list(row)
        row.insert(0, index)
        ws.append(row)

    # Tự động điều chỉnh độ rộng cột
    for column_cells in ws.columns: 
        max_length = 0  # Khởi tạo giá trị
        for cell in column_cells:
            if cell.value:
                max_length = max(max_length, len(str(cell.value)))
        column_letter = openpyxl.utils.get_column_letter(column_cells[0].column)  # Lấy chữ cái cột
        ws.column_dimensions[column_letter].width = max_length + 2  # Điều chỉnh độ rộng

    now = datetime.datetime.now()
    formatted_time = now.strftime("%Y_%m_%d_%H_%M_%S")

    # Lưu workbook tạm thời trên server
    filename = f"data_{str(idPersonal)+"_"+formatted_time}.xlsx"
    wb.save(f"tmp/{filename}")

    # Tạo đường dẫn tải file
    download_url = f"tmp/{filename}"

    # return render_template("index.html", download_url=download_url)
    return redirect(url_for('download', filename=filename))  

@app.route("/download/<filename>")
def download(filename):
    return send_file(f"tmp/{filename}", as_attachment=True)
    

if __name__ == "__main__":
    app.run(host=IP, port=5000, debug=True)
