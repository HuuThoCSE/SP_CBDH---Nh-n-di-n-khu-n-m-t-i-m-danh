from flask import Blueprint, request, render_template, session, url_for, redirect
import mysql.connector

# Tạo Blueprint cho module 2
appDayClass = Blueprint('DayClass', __name__, static_folder='../static')

mydb = mysql.connector.connect(
    host="localhost",
    user="root",
    passwd="",
    database="flask_db"
)

mycursor = mydb.cursor()

def loadDayClass(idCourseClass):
    mycursor = mydb.cursor()
    mycursor.execute("SELECT DayClass.*, CourseClass.codeCourseClass, CourseClass.nameCourseClass"
                     " FROM DayClass"
                     " INNER JOIN CourseClass ON DayClass.idCourseClass = CourseClass.idCourseClass "
                     " WHERE Dayclass.idCourseClass=%s order by 1 desc", (idCourseClass,))
    data = mycursor.fetchall()
    mycursor.close()

    return data

# Định nghĩa route trong module 2
@appDayClass.route('/panel', methods=['GET', 'POST'])
def DayClassPanel():
    idCourseClass = request.args.get('idCourseClass')
    namePerm = ''
    if session.get('idPerm') == 1:
        namePerm = 'Techer'
    return render_template('pn_DayClass.html', data=loadDayClass(idCourseClass), idCourseClass=idCourseClass, namePerm=namePerm)


@appDayClass.route('/add', methods=['GET', 'POST'])
def addDayClass():
    try:
        idCourseClass = request.args.get('idCourseClass')
        nameDayClass = request.form['nameDayClass']
        datetimeStart = request.form['datetimeStart']
        datetimeEnd = request.form['datetimeEnd']
        
        mycursor = mydb.cursor()
        query= ("INSERT INTO DayClass (idCourseClass, nameDayClass, datetimeStartDayClass, datetimeEndDayClass) VALUES (%s, %s, %s, %s)")
        values = (idCourseClass, nameDayClass, datetimeStart, datetimeEnd,)
        mycursor.execute(query, values)
        mydb.commit()

        return render_template('pn_DayClass.html', data=loadDayClass(idCourseClass), idCourseClass=idCourseClass)
    except Exception as e:
        print(e)
        return str(e), 500

@appDayClass.route('/edit', methods=['GET', 'POST'])
def editDayClass():
    idDayClass = request.args.get('idDayClass')

    mycursor = mydb.cursor()
    mycursor.execute("SELECT * FROM DayClass where idDayClass="+idDayClass)
    data = mycursor.fetchall()
    
    return render_template('edit_DayClass.html', data=data)

@appDayClass.route('/update', methods=['GET', 'POST'])
def updateDayClass():
    idDayClass = request.args.get('idDayClass')
    nameDayClass = request.form['nameDayClass']
    datetime = request.form['datetime']

    mycursor = mydb.cursor()
    mycursor.execute(
        "UPDATE DayClass SET nameDayClass = %s, datetimeStartDayClass = %s WHERE idDayClass = %s",
        (nameDayClass, datetime, idDayClass)
    )
    mydb.commit() # Lưu thay đổi

    # Lưu trữ thông báo thành công vào session
    session['update_success'] = True

    mycursor.execute("SELECT * From DayClass WHERE idDayClass=%s", (idDayClass,))
    data = mycursor.fetchall()
    return render_template('edit_DayClass.html', data=data,
                                alert_message="Cập nhật thành công!", 
                                alert_type="success", 
                                alert_duration=5)