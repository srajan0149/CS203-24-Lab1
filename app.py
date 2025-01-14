from flask import Flask, render_template, json, request, redirect, url_for
import logging
from opentelemetry import trace,metrics

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# creating tracers
default_tracer = trace.get_tracer("default.tracer")
new_course_tracer = trace.get_tracer("new_course.tracer")
course_tracer = trace.get_tracer("course.tracer")

# creating meter
meter = metrics.get_meter("default.meter")

# page counter
counter = meter.create_counter(
    "page_visits",
    description="number of times page is visited"
)

# course counter
course_counter = meter.create_counter(
    "course",
    description="number of courses added"
)

# load json file in memory
with open("courses.json") as file:
        data = json.load(file)
        logger.info("Database loaded successfully")

# save updated data into json file
def save_data(data):
    with default_tracer.start_as_current_span("save_data") as span:
        trace.get_current_span().set_attribute("operation.status","running")
        trace.get_current_span().set_attribute("operation.method",request.method)
        with open("courses.json","w") as file:
                json.dump(data,file)
        logger.info("Updated database")
        trace.get_current_span().set_attribute("operation.status","successful")

# home page
@app.route("/")
def index():
    counter.add(1,{"page":"/"})
    return render_template("index.html",page='index')

# course catalog
@app.route("/courses")
def courses(info=""):
        counter.add(1,{"page":"/courses"})
        return render_template("courses.html",page='courses',data=data, info=info)

# course under <branch> with code <code>
@app.route("/course/<branch>/<code>")
def course(branch,code):
    with course_tracer.start_as_current_span(f"course:{branch}{code}") as span:
        counter.add(1,{"page":f"/{branch}/{code}"})
        trace.get_current_span().set_attribute("operation.branch",branch)
        trace.get_current_span().set_attribute("operation.course_code",code)
        trace.get_current_span().set_attribute("operation.method",request.method)
        return render_template("course.html",data=data[branch][code])

# course add/remove page
@app.route("/manage_courses")
def manage_courses():
        counter.add(1,{"page":"/manage_courses"})
        return render_template("manage_courses.html",data=data)

# request handler for changes
@app.route("/save_changes",methods=["GET","POST"])
def save_changes():
        logger.info(request.headers)
        counter.add(1,{"page":"/manage_courses"})
        if request.method == "GET":

            with default_tracer.start_as_current_span("Trying to redirect user") as child:
                return redirect(url_for('courses',data=data))

        if request.headers["Content-Type"]=="application/x-www-form-urlencoded":

            with new_course_tracer.start_as_current_span("Form data received") as child:
                req = request.form
                trace.get_current_span().set_attribute("operation.form_data",req)
                branch = req["Branch"]
                code = req["Course Code"]
                data[branch][code] = {}
                for i in req:
                    data[branch][code][i] = req[i]
                save_data(data)
                return render_template("courses.html",data=data,info=[0,f"Course {code} has been added from the database"])
        
        req = request.get_json()
        if(req["type"]=="remove"):

            with default_tracer.start_as_current_span("Course remove request") as child:
                trace.get_current_span().set_attribute("operation.courses_to_remove",req["courses"])
                for code in req["courses"]:
                    branch, code = code.strip().split('/')
                    data[branch].pop(code,None)
                    logger.info(f"Removing course {code} from {branch}")
                
                save_data(data)
                return redirect(url_for("courses",info=[0,f"Selected course(s) has been removed from the database"]))

        logger.info("Invalid request")
        return redirect(url_for("courses",info=[-1,"Invalid request"]))

# new course form
@app.route("/add_course_form/<branch>")
def add_course_form(branch):
        if branch in data:
            return render_template("course_form.html",branch=branch)
        return render_template("404.html")

# redirector
@app.route("/redirected")
def redirected(info):
    return render_template("/courses.html",data=data,info=info)