import sqlite3
from flask import Flask, render_template
from markupsafe import escape
from datetime import date

def treatment_date_limits_in_effect(conn, as_of_date):
    QUERY = '''
    SELECT p.description as plant, tt.description as treatment, date(t.date) as treatmentDate, date(t.date + l.daysBetweenApplications) as safeToRepeatDate
      FROM AppliedTreatment t
      LEFT JOIN Plant p
      ON t.plantId = p.id
      INNER JOIN SafetyLimit l
      ON t.treatmentTypeId = l.treatmentTypeId AND l.speciesId = p.speciesId
      LEFT JOIN TreatmentType tt
      ON t.treatmentTypeId = tt.id
      WHERE t.date <= julianday(?) AND t.date + l.daysBetweenApplications >= julianday(?)
    '''
    return conn.execute(QUERY, (as_of_date, as_of_date))

def safe_to_consume_dates(conn, as_of_date):
    QUERY='''
    SELECT plant, treatment, treatmentDate, max(safeToConsumeDate) as safeToConsumeDate
      FROM
      (SELECT p.description as plant, tt.description as treatment, date(t.date) as treatmentDate, date(t.date + l.minDaysBeforeConsumption) as safeToConsumeDate
      FROM AppliedTreatment t
      LEFT JOIN Plant p
      ON t.plantId = p.id
      INNER JOIN SafetyLimit l
      ON t.treatmentTypeId = l.treatmentTypeId AND l.speciesId = p.speciesId
      LEFT JOIN TreatmentType tt
      ON t.treatmentTypeId = tt.id
      WHERE t.date <= julianday(?) AND t.date + l.minDaysBeforeConsumption >= julianday(?)
      )
      GROUP BY plant
    '''
    return conn.execute(QUERY, (as_of_date, as_of_date))

def treatments_no_longer_applicable(conn, as_of_date):
    QUERY='''
    SELECT plantDescription, treatmentDescription, treatments, maxApplications
    FROM
    (SELECT plantId, plantDescription, treatmentTypeId, treatmentDescription, COUNT(treatmentDate) as treatments, maxApplications
    FROM
    (SELECT p.id as plantId, p.description as plantDescription, t.treatmentTypeId as treatmentTypeId, tt.description as treatmentDescription, t.date as treatmentDate, l.maxApplications as maxApplications
    FROM AppliedTreatment t
    LEFT JOIN Plant p
    ON t.plantId = p.id
    INNER JOIN SafetyLimit l
    ON t.treatmentTypeId = l.treatmentTypeId AND l.speciesId = p.speciesId
    LEFT JOIN TreatmentType tt
    ON t.treatmentTypeId = tt.id
    WHERE t.date <= julianday(?) and t.date >= julianday(?)
    )
    GROUP BY plantId, treatmentTypeId
    )
    WHERE treatments >= maxApplications
    '''
    
    start_of_year = as_of_date[0:4] + '-01-01'
    return conn.execute(QUERY, (as_of_date, start_of_year))

def treatments_applied_without_limit_info(conn, as_of_date):
    QUERY='''
    SELECT tt.description as treatment, date(t.date) as date, p.description as plant
    FROM AppliedTreatment t
    LEFT JOIN Plant p
    ON t.plantId = p.id
    LEFT JOIN SafetyLimit l
    ON t.treatmentTypeId = l.treatmentTypeId AND l.speciesId = p.speciesId
    LEFT JOIN TreatmentType tt
    ON t.treatmentTypeId = tt.id
    WHERE l.id IS NULL AND t.date >= julianday(?)
    '''

    start_of_year = as_of_date[0:4] + '-01-01'
    return conn.execute(QUERY, (start_of_year,))

def all_limit_info_for_treatment(conn, treatment_id):
    QUERY='''
    SELECT t.description as treatment,
       p.name as species,
       l.maxApplications as maxApplications,
       l.daysBetweenApplications as daysBetweenApplications,
       l.applyBefore as applyBefore,
       l.minDaysBeforeConsumption as minDaysBeforeConsumption
    FROM TreatmentType t
    LEFT JOIN SafetyLimit l
    ON t.id = l.treatmentTypeId
    LEFT JOIN PlantSpecies p
    ON l.speciesId = p.id
    WHERE t.id = ?
    '''
    return conn.execute(QUERY, (treatment_id,))

def list_of_treatments(conn):
    QUERY='''
    SELECT id, description
    FROM TreatmentType
    '''
    return conn.execute(QUERY)

def treatment_description(conn, treatment_id):
    QUERY='''
    SELECT description
    FROM TreatmentType
    WHERE id = ?
    '''
    return conn.execute(QUERY, (treatment_id,))

def all_treatments_for_plant(conn, as_of_date, plant_id):
    QUERY='''SELECT p.id as plantId, p.description as plantDescription, t.treatmentTypeId as treatmentTypeId, tt.description as treatmentDescription, date(t.date) as treatmentDate
    FROM AppliedTreatment t
    LEFT JOIN Plant p
    ON t.plantId = p.id
    LEFT JOIN TreatmentType tt
    ON t.treatmentTypeId = tt.id
    WHERE t.date <= julianday(?) and t.date >= julianday(?) and p.id = ?
    '''
    start_of_year = as_of_date[0:4] + '-01-01'
    return conn.execute(QUERY, (as_of_date, start_of_year, plant_id))
    
def list_of_plants(conn):
    QUERY='''
    SELECT id, description
    FROM Plant
    '''
    return conn.execute(QUERY)

def plant_description(conn, plant_id):
    QUERY='''
    SELECT description
    FROM Plant
    WHERE id = ?
    '''
    return conn.execute(QUERY, (plant_id,))


app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect("test.db")
    conn.row_factory = sqlite3.Row
    return conn
    
@app.route('/')
@app.route('/index/')
def index():
    today = date.today()
    as_of = today.strftime("%Y-%m-%d")
    conn = get_db_connection()
    treatment_list = list_of_treatments(conn).fetchall()
    plant_list = list_of_plants(conn).fetchall()
    conn.close()
    return render_template('index.html', as_of = as_of, treatments = treatment_list, plants = plant_list)

@app.route('/date_limits/<as_of_date>')
def date_limits(as_of_date):
    conn = get_db_connection()
    current_limits = treatment_date_limits_in_effect(conn, as_of_date).fetchall()
    conn.close()
    return render_template('date_limits.html', as_of = as_of_date, date_limits = current_limits)

@app.route('/safe/<as_of_date>')
def safe(as_of_date):
    conn = get_db_connection()
    dates = safe_to_consume_dates(conn, as_of_date).fetchall()
    conn.close()
    return render_template('safe.html', as_of = as_of_date, dates = dates)

@app.route('/not_applicable/<as_of_date>')
def not_applicable(as_of_date):
    conn = get_db_connection()
    treatments = treatments_no_longer_applicable(conn, as_of_date).fetchall()
    conn.close()
    return render_template('not_applicable.html', as_of = as_of_date, treatments = treatments)

@app.route('/no_info/<as_of_date>')
def no_info(as_of_date):
    conn = get_db_connection()
    treatments = treatments_applied_without_limit_info(conn, as_of_date).fetchall()
    conn.close()
    return render_template('no_info.html', as_of = as_of_date, treatments = treatments)

@app.route('/treatment_info/<treatment_id>')
def treatment_info(treatment_id):
    conn = get_db_connection()
    treatment_info = all_limit_info_for_treatment(conn, treatment_id).fetchall()
    selected_treatment = treatment_description(conn, treatment_id).fetchone()
    conn.close()
    return render_template('treatment_info.html', treatment = selected_treatment['description'], treatment_info = treatment_info)

@app.route('/plant_info/<as_of_date>/<plant_id>')
def plant_info(as_of_date, plant_id):
    conn = get_db_connection()
    plant_info = all_treatments_for_plant(conn, as_of_date, plant_id).fetchall()
    selected_plant = plant_description(conn, plant_id).fetchone()
    conn.close()
    return render_template('plant_info.html', plant = selected_plant['description'], plant_info = plant_info)

