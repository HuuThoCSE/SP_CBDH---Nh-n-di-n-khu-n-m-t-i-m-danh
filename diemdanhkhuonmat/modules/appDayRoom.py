from flask import Blueprint, request, render_template, session, url_for, redirect, jsonify, Response
import mysql.connector
from playsound import playsound
from PIL import Image
import numpy as np
import os
import cv2
import time

from openpyxl import Workbook
import openpyxl
import datetime

Device_Video = 'http://192.168.0.102:4747/video'
# Device_Video = 1

cnt = 0
pause_cnt = 0
justscanned = False

# Tạo Blueprint cho module 2
appDayRoom = Blueprint('appDayRoom', __name__, static_folder='../static')

mydb = mysql.connector.connect(
    host="localhost",
    user="root",
    passwd="",
    database="flask_db"
)
mycursor = mydb.cursor()

def loadRoom(idPersonal):
    mycursor.execute("SELECT * FROM DayRoom WHERE idPersonal=%s order by 1 desc", (idPersonal,))
    return mycursor.fetchall()

# Định nghĩa route
@appDayRoom.route('/', methods=['GET', 'POST'])
def home():
    if 'idPersonal' not in session:
        return redirect('/login')
    idPersonal = session.get('idPersonal')
    return render_template('list_Room.html', data=loadRoom(idPersonal), idPersonal=idPersonal)

@appDayRoom.route('/add', methods=['POST'])
def addDayRoom():
    if 'idPersonal' not in session:
        return redirect('/login')
    
    idPersonal = session.get('idPersonal')
    nameRoom = request.form['nameRoom']
    datetimeRoom = request.form['datetimeRoom']
    mycursor.execute("INSERT INTO DayRoom (idPersonal, nameRoom, datetimeRoom) VALUES (%s, %s, %s)", (idPersonal, nameRoom, datetimeRoom))
    mydb.commit()
    return render_template('list_Room.html', data=loadRoom(idPersonal))


@appDayRoom.route('/edit', methods=['GET', 'POST'])
def editDayRoom():
    if 'idPersonal' not in session:
        return redirect('/login')

    idDayRoom = request.args.get('idDayRoom')
    mycursor.execute("SELECT * FROM DayRoom where idDayRoom="+str(idDayRoom))
    data = mycursor.fetchall()
    return render_template('edit_DayRoom.html', data=data)

@appDayRoom.route('/update', methods=['GET', 'POST'])
def updateDayClass():
    idDayRoom = request.args.get('idDayRoom')
    nameRoom = request.form['nameRoom']
    datetimeRoom = request.form['datetimeRoom']

    mycursor = mydb.cursor()
    mycursor.execute(
        "UPDATE DayRoom SET nameRoom = %s, datetimeRoom = %s WHERE idDayRoom = %s",
        (nameRoom, datetimeRoom, idDayRoom)
    )
    mydb.commit()

    # Lưu trữ thông báo thành công vào session
    session['update_success'] = True

    mycursor.execute("SELECT * FROM DayRoom where idDayRoom="+str(idDayRoom))
    data = mycursor.fetchall()
    return render_template('edit_DayRoom.html', data=data,
                                alert_message="Cập nhật thành công!", 
                                alert_type="success", 
                                alert_duration=5)

@appDayRoom.route('scanRoom', methods=['GET'])
def scanRoom():
    if 'idPersonal' not in session:
        return redirect('/login')

    idRoom = request.args.get('idRoom')
    """Video streaming home page."""
    mycursor.execute("select a.idUser, a.idUser"
                     "  from enrollRoom a "
                     "  left join dusers b on a.idUser = b.idUser "
                     " where a.accs_dated = curdate()"
                     " order by 1 desc")
    data = mycursor.fetchall()
    return render_template('scanRoom.html', data=data, idRoom=idRoom)

@appDayRoom.route('/loadData', methods=['GET', 'POST'])
def loadData():
    idRoom = request.args.get('idRoom')
    mycursor = mydb.cursor()
    mycursor.execute("select a.idEnrollRoom,a.idUser, b.mssv, b.nameUser, date_format(a.accs_dated, '%H:%i:%s')"
                     " from enrollRoom a"
                     " left join dusers b on a.idUser = b.idUser"
                     " where a.idRoom = "+str(idRoom)+
                     " order by 1 desc")
    data = mycursor.fetchall()
    return jsonify(response=data)


@appDayRoom.route('/countTodayScan', methods=['GET', 'POST'])
def countTodayScan():
    idRoom = request.args.get('idRoom')
    mycursor.execute("select count(*)"
                     " from enrollRoom"
                     " where idRoom="+str(idRoom))
    row = mycursor.fetchone()
    rowcount = row[0]
    return jsonify({'rowcount': rowcount})

# <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< Face Recognition >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
def face_recognition(idRoom):  # generate frame by frame from camera
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
                    mycursor.execute("SELECT MAX(idRoom) FROM DayRoom")
                    max_id = mycursor.fetchone()[0]
                    if max_id is None:
                        new_id = 1  # Bắt đầu từ ID 1 nếu bảng rỗng 
                    else:
                        new_id = int(max_id) + 1

                    try:
                        # Thực hiện chèn hoặc cập nhật
                        query = "INSERT INTO enrollRoom (idEnrollRoom, idRoom, idUser, status) VALUES (%s, %s, %s, %s)"
                        values = (str(new_id), idRoom, idUser, 1)
                        mycursor.execute(query, values)
                        mydb.commit()

                        playsound("static\\sound\\DiemdanhThanhcong.wav")
                    
                    except mysql.connector.errors.IntegrityError as e:
                        if e.errno == 1062:  # Lỗi trùng lặp khóa
                            # show_error_message("Dữ liệu đã tồn tại!")  # Hiển thị thông báo lỗi
                            playsound("static\\sound\\NguoidungDaDiemdanh.wav")

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
        return img

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

@appDayRoom.route('/video_feed', methods=['GET', 'POST'])
def video_feed():
    idRoom = request.args.get('idRoom')
    # Video streaming route. Put this in the src attribute of an img tag
    return Response(face_recognition(idRoom), mimetype='multipart/x-mixed-replace; boundary=frame')


@appDayRoom.route('/exportRoom', methods=['GET'])
def exportRoom():
    if 'idPersonal' not in session:
        return redirect('/login')

    idRoom = request.args.get('idRoom')

    idPersonal = session.get('idPersonal')

    query = """
        SELECT dusers.mssv, dusers.nameUser, enrollroom.accs_dated
        FROM enrollroom
        LEFT JOIN dusers ON enrollroom.idUser = dusers.idUser
        LEFT JOIN DayRoom ON enrollroom.idRoom = DayRoom.idRoom
        WHERE enrollroom.idRoom = %s
    """
    values = (idRoom,)
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