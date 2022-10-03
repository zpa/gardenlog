import sqlite3

conn = sqlite3.connect("test.db")
conn.row_factory = sqlite3.Row

def run_query(sql, param):
    cur = conn.cursor()
    cur.execute(sql, param)
    return cur.lastrowid


class PlantSpecies:
    TABLE = '''
    CREATE TABLE PlantSpecies (
      id INTEGER PRIMARY KEY,
      name TEXT NOT NULL
    );
    '''
    
    def __init__(self, name):
        self.name = name
        self.species_id = run_query('INSERT INTO PlantSpecies(name) VALUES(?)', (name,))

    @staticmethod
    def dbInit():
        run_query(PlantSpecies.TABLE, ())

        
class Plant:
    TABLE = '''
    CREATE TABLE Plant (
       id INTEGER PRIMARY KEY,
       speciesId INTEGER NOT NULL,
       description TEXT NOT NULL,
       FOREIGN KEY(speciesId) REFERENCES PlantSpecies(id)
       );
    '''
        
    def __init__(self, species, description):
        self.description = description
        self.species_id = species.species_id
        self.plant_id = run_query('INSERT INTO Plant(speciesId, description) VALUES(?,?)', (self.species_id, description))

    @staticmethod
    def dbInit():
        run_query(Plant.TABLE, ())


class TreatmentType:
    TABLE = '''
    CREATE TABLE TreatmentType (
      id INTEGER PRIMARY KEY,
      description TEXT NOT NULL
    );
    '''
            
    def __init__(self, description):
        self.description = description
        self.treatment_type_id = run_query('INSERT INTO TreatmentType(description) VALUES(?)', (description,))

    @staticmethod
    def dbInit():
        run_query(TreatmentType.TABLE, ())


class AppliedTreatment:
    TABLE = '''
    CREATE TABLE AppliedTreatment (
       id INTEGER PRIMARY KEY,
       treatmentTypeId INTEGER NOT NULL,
       plantId INTEGER NOT NULL,
       date REAL NOT NULL,
       FOREIGN KEY(treatmentTypeId) REFERENCES TreatmentType(id),
       FOREIGN KEY(plantId) REFERENCES Plant(id)
       );
    '''

    def __init__(self, treatment: TreatmentType, plant: Plant, date):
        self.treatment_type_id = treatment.treatment_type_id
        self.plant_id = plant.plant_id
        self.treatment_date = date
        self.applied_treatment_id = run_query('INSERT INTO AppliedTreatment(treatmentTypeId,plantId,date) VALUES(?,?,julianday(?))', (self.treatment_type_id, self.plant_id, self.treatment_date))
    
    @staticmethod
    def dbInit():
        run_query(AppliedTreatment.TABLE, ())

def apply_treatment(treatment, plants, date):
    try:
        for plant in plants:
            AppliedTreatment(treatment, plant, date)
    except TypeError:
        AppliedTreatment(treatment, plants, date)

        
class SafetyLimit:
    TABLE = '''
    CREATE TABLE SafetyLimit (
       id INTEGER PRIMARY KEY,
       treatmentTypeId INTEGER NOT NULL,
       speciesId INTEGER NOT NULL,
       maxApplications INTEGER NOT NULL,
       daysBetweenApplications INTEGER NOT NULL,
       applyBefore TEXT NOT NULL,
       minDaysBeforeConsumption INTEGER NOT NULL,
       FOREIGN KEY(treatmentTypeId) REFERENCES TreatmentType(id),
       FOREIGN KEY(speciesId) REFERENCES PlantSpecies(id),
       UNIQUE(treatmentTypeId,speciesId)
       );
    '''

    def __init__(self, treatment: TreatmentType, species: PlantSpecies, max_applications, days_between_applications, apply_before, min_days_before_consumption):
        self.treatment_type_id = treatment.treatment_type_id
        self.species_id = species.species_id
        self.max_applications = max_applications
        self.days_between_applications = days_between_applications
        self.apply_before = apply_before
        self.min_days_before_consumption = min_days_before_consumption
        try:
            self.id = run_query('INSERT INTO SafetyLimit(treatmentTypeId,speciesId,maxApplications,daysBetweenApplications,applyBefore,minDaysBeforeConsumption) VALUES(?,?,?,?,?,?)', (self.treatment_type_id, self.species_id, self.max_applications, self.days_between_applications,self.apply_before, self.min_days_before_consumption))    
        except sqlite3.IntegrityError:
            print('WARNING: Duplicate safety limit for treatmentType', self.treatment_type_id, ', speciesId', self.species_id, 'ignored!')
            
    @staticmethod
    def dbInit():
        run_query(SafetyLimit.TABLE, ())


def add_safety_limit(treatment, species_list, max_applications, days_between_applications, apply_before, min_days_before_consumption):
    try:
        for species in species_list:
            SafetyLimit(treatment, species, max_applications, days_between_applications, apply_before, min_days_before_consumption)
    except TypeError:
        SafetyLimit(treatment, species_list, max_applications, days_between_applications, apply_before, min_days_before_consumption)

def treatment_date_limits_in_effect(as_of_date):
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

def safe_to_consume_dates(as_of_date):
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

def treatments_no_longer_applicable(as_of_date):
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

def treatments_applied_without_limit_info(as_of_date):
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

def all_limit_info_for_treatment(treatment):
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
    WHERE t.description = ?
    '''
    return conn.execute(QUERY, (treatment,))


PlantSpecies.dbInit()
Plant.dbInit()
TreatmentType.dbInit()
AppliedTreatment.dbInit()
SafetyLimit.dbInit()

alma = PlantSpecies('alma')
korte = PlantSpecies('korte')
meggy = PlantSpecies('meggy')
cseresznye = PlantSpecies('cseresznye')
oszi = PlantSpecies('oszibarack')
szilva = PlantSpecies('szilva')
sargabarack = PlantSpecies('sargabarack')
mandula = PlantSpecies('mandula')
szolo = PlantSpecies('szolo')
malna = PlantSpecies('malna')
ribizli = PlantSpecies('ribizli')
rozsa = PlantSpecies('rozsa')

almatermesuek = (alma, korte)
csonthejasok = (cseresznye, meggy, oszi, szilva, sargabarack, mandula)
bogyosok = (malna, ribizli)
diszfak = (rozsa,)

almafa = Plant(alma, 'Jonagored almafa')
hatso_almafa = Plant(alma, 'husveti almafa')
elso_kortefa = Plant(korte, 'elso kortefa')
hatso_kortefa = Plant(korte, 'hatso kortefa, bosc')
nagy_meggyfa = Plant(meggy, 'nagy meggyfa, Erdi botermo')
oszibarackfa = Plant(oszi, 'oszibarackfa, Mariska')
lenti_ringlofa = Plant(szilva, 'lenti ringlofa')
elso_ringlofa = Plant(szilva, 'elso ringlofa')
kozepso_ringlofa = Plant(szilva, 'kozepso ringlofa')
hatso_ringlofa = Plant(szilva, 'hatso ringlofa')
sargabarackfa = Plant(sargabarack, 'sargabarackfa, Cegledi orias')
lenti_meggyfa = Plant(meggy, 'lenti meggyfa')
utcai_mandulafa = Plant(mandula, 'utcai mandulafa')
szolotoke = Plant(szolo, 'szolo')
malnabokor = Plant(malna, 'egyszer termo malna')
ribizlibokor = Plant(ribizli, 'ribizli')
rozsabokor_hintanal = Plant(rozsa, 'rozsa a hintanal')
rozsabokor_sargabaracknal = Plant(rozsa, 'rozsa a sargabaracknal')
rozsabokrok_elokertben = Plant(rozsa, 'rozsabokrok az elokertben')

benti_fak = (almafa, hatso_almafa, elso_kortefa, hatso_kortefa, nagy_meggyfa, oszibarackfa, lenti_ringlofa, elso_ringlofa, kozepso_ringlofa, hatso_ringlofa, sargabarackfa, lenti_meggyfa)
kinti_fak = (utcai_mandulafa,)
osszes_fa = benti_fak + kinti_fak

olajos_rezken = TreatmentType('Olajos Rezken')
dithane = TreatmentType('Dithane')
mospilan = TreatmentType('Mospilan')
topas = TreatmentType('Topas')
lamdex = TreatmentType('Lamdex')
score = TreatmentType('Score')
flumite = TreatmentType('Flumite')
champion = TreatmentType('Champion')
signum = TreatmentType('Signum')
kaliszappan = TreatmentType('Kaliszappan')
bordoile = TreatmentType('Bordoile NEO')

# olajos rezken
add_safety_limit(treatment = olajos_rezken, species_list = almatermesuek, max_applications = 2, days_between_applications = 10, apply_before = 'rugypattanas elott (BBCH 07)', min_days_before_consumption = 0)
add_safety_limit(treatment = olajos_rezken, species_list = szolo, max_applications = 2, days_between_applications = 10, apply_before = 'rugypattanas elott (BBCH 07)', min_days_before_consumption = 0)
add_safety_limit(treatment = olajos_rezken, species_list = csonthejasok, max_applications = 2, days_between_applications = 10, apply_before = 'rugypattanas elott (BBCH 07)', min_days_before_consumption = 0)
add_safety_limit(treatment = olajos_rezken, species_list = bogyosok, max_applications = 2, days_between_applications = 10, apply_before = 'rugypattanas elott (BBCH 07)', min_days_before_consumption = 0)
add_safety_limit(treatment = olajos_rezken, species_list = diszfak, max_applications = 2, days_between_applications = 10, apply_before = 'rugypattanas elott (BBCH 07)', min_days_before_consumption = 0)

# dithane
add_safety_limit(treatment = dithane, species_list = almatermesuek, max_applications = 99, days_between_applications = 7, apply_before = 'N/A', min_days_before_consumption = 30)
add_safety_limit(treatment = dithane, species_list = csonthejasok, max_applications = 99, days_between_applications = 7, apply_before = 'N/A', min_days_before_consumption = 21)
add_safety_limit(treatment = dithane, species_list = szolo, max_applications = 99, days_between_applications = 7, apply_before = 'N/A', min_days_before_consumption = 30)
add_safety_limit(treatment = dithane, species_list = diszfak, max_applications = 99, days_between_applications = 7, apply_before = 'N/A', min_days_before_consumption = 0)

# mospilan
add_safety_limit(treatment = mospilan,
                 species_list = alma,
                 max_applications = 2,
                 days_between_applications = 7,
                 apply_before = 'eres (BBCH 82)',
                 min_days_before_consumption = 14)
add_safety_limit(treatment = mospilan,
                 species_list = korte,
                 max_applications = 1,
                 days_between_applications = 199,
                 apply_before = '50%-os gyumolcsmeret (BBCH 82)',
                 min_days_before_consumption = 14)
add_safety_limit(treatment = mospilan,
                 species_list = (cseresznye, meggy),
                 max_applications = 1,
                 days_between_applications = 199,
                 apply_before = 'eres kezdete (BBCH 82)',
                 min_days_before_consumption = 14)
add_safety_limit(treatment = mospilan,
                 species_list = szilva,
                 max_applications = 2,
                 days_between_applications = 7,
                 apply_before = 'eres (BBCH 82)',
                 min_days_before_consumption = 14)
add_safety_limit(treatment = mospilan,
                 species_list = oszi,
                 max_applications = 2,
                 days_between_applications = 7,
                 apply_before = 'eres (BBCH 82)',
                 min_days_before_consumption = 14)
add_safety_limit(treatment = mospilan,
                 species_list = sargabarack,
                 max_applications = 2,
                 days_between_applications = 7,
                 apply_before = 'eres (BBCH 82)',
                 min_days_before_consumption = 14)
add_safety_limit(treatment = mospilan,
                 species_list = szolo,
                 max_applications = 1,
                 days_between_applications = 199,
                 apply_before = 'eres (BBCH 82)',
                 min_days_before_consumption = 7)
add_safety_limit(treatment = mospilan,
                 species_list = diszfak,
                 max_applications = 2,
                 days_between_applications = 7,
                 apply_before = 'N/A',
                 min_days_before_consumption = 0)

# topas
add_safety_limit(treatment = topas, species_list = almatermesuek, max_applications = 3, days_between_applications = 10, apply_before = '2 hettel betakaritas elott (BBCH 84)', min_days_before_consumption = 14)
add_safety_limit(treatment = topas, species_list = (cseresznye,meggy,szilva,oszi,sargabarack), max_applications = 4, days_between_applications = 7, apply_before = '1 hettel betakaritas elott (BBCH 86)', min_days_before_consumption = 7)
add_safety_limit(treatment = topas, species_list = diszfak, max_applications = 2, days_between_applications = 10, apply_before = 'N/A', min_days_before_consumption = 0)
add_safety_limit(treatment = topas, species_list = szolo, max_applications = 4, days_between_applications = 10, apply_before = 'furtzarodas (BBCH 78)', min_days_before_consumption = 14)
add_safety_limit(treatment = topas, species_list = mandula, max_applications = 3, days_between_applications = 7, apply_before = '2 hettel betakaritas elott (BBCH 84)', min_days_before_consumption = 14)
add_safety_limit(treatment = topas, species_list = ribizli, max_applications = 4, days_between_applications = 8, apply_before = '90%-os bogyofejlettseg (BBCH 79)', min_days_before_consumption = 21)

# lamdex
add_safety_limit(treatment = lamdex,
                 species_list = almatermesuek,
                 max_applications = 99,
                 days_between_applications = 8,
                 apply_before = 'N/A',
                 min_days_before_consumption = 3)
add_safety_limit(treatment = lamdex,
                 species_list = (oszi,sargabarack,szilva,cseresznye,meggy),
                 max_applications = 99,
                 days_between_applications = 8,
                 apply_before = 'N/A',
                 min_days_before_consumption = 3)
add_safety_limit(treatment = lamdex,
                 species_list = szolo,
                 max_applications = 99,
                 days_between_applications = 10,
                 apply_before = 'N/A',
                 min_days_before_consumption = 3)

# score
add_safety_limit(treatment = score,
                 species_list = alma,
                 max_applications = 4,
                 days_between_applications = 8,
                 apply_before = 'a gyumolcsok zold dio nagysagaig',
                 min_days_before_consumption = 14)
add_safety_limit(treatment = score,
                 species_list = korte,
                 max_applications = 4,
                 days_between_applications = 8,
                 apply_before = 'a gyumolcsok zold dio nagysagaig',
                 min_days_before_consumption = 14)
add_safety_limit(treatment = score,
                 species_list = oszi,
                 max_applications = 3,
                 days_between_applications = 8,
                 apply_before = 'rugypattanas utan 2-3 kezeles',
                 min_days_before_consumption = 14)

# flumite
add_safety_limit(treatment = flumite,
                 species_list = (alma, korte),
                 max_applications = 1,
                 days_between_applications = 0,
                 apply_before = 'N/A',
                 min_days_before_consumption = 28)
add_safety_limit(treatment = flumite,
                 species_list = (oszi, szilva),
                 max_applications = 1,
                 days_between_applications = 0,
                 apply_before = 'N/A',
                 min_days_before_consumption = 28)
add_safety_limit(treatment = flumite,
                 species_list = szolo,
                 max_applications = 1,
                 days_between_applications = 0,
                 apply_before = 'tavasszal 2-4 leveles allapotban vagy viragzas elotti idoszakban',
                 min_days_before_consumption = 28)
add_safety_limit(treatment = flumite,
                 species_list = malna,
                 max_applications = 1,
                 days_between_applications = 0,
                 apply_before = 'viragzas elott',
                 min_days_before_consumption = 28)
# champion
add_safety_limit(treatment = champion,
                 species_list = szolo,
                 max_applications = 4,
                 days_between_applications = 7,
                 apply_before = 'BBCH 15-81, 91-96',
                 min_days_before_consumption = 21)
add_safety_limit(treatment = champion,
                 species_list = almatermesuek,
                 max_applications = 4,
                 days_between_applications = 7,
                 apply_before = 'februar-marcius vagy BBCH 10-53, 93-99',
                 min_days_before_consumption = 0)
add_safety_limit(treatment = champion,
                 species_list = csonthejasok,
                 max_applications = 4,
                 days_between_applications = 14,
                 apply_before = 'BBCH 10-53, 95-99',
                 min_days_before_consumption = 0)
add_safety_limit(treatment = champion,
                 species_list = diszfak,
                 max_applications = 3,
                 days_between_applications = 7,
                 apply_before = 'okiratban megadva',
                 min_days_before_consumption = 0)

# signum
add_safety_limit(treatment = signum, species_list = (cseresznye,meggy,oszi,szilva,sargabarack), max_applications = 3, days_between_applications = 7, apply_before = 'fajtara jellemzo szinezodes kialakulasaig (BBCH 85)', min_days_before_consumption = 7)
add_safety_limit(treatment = signum, species_list = mandula, max_applications = 2, days_between_applications = 7, apply_before = 'fajtara jellemzo szinezodes kialakulasaig (BBCH 85)', min_days_before_consumption = 28)
add_safety_limit(treatment = signum, species_list = malna, max_applications = 2, days_between_applications = 7, apply_before = '1 hettel betakaritas elottig (BBCH 86)', min_days_before_consumption =  7)
add_safety_limit(treatment = signum, species_list = ribizli, max_applications = 2, days_between_applications = 7, apply_before = '2 hettel betakaritas elottig (BBCH 84)', min_days_before_consumption = 14)

# kaliszappan
add_safety_limit(treatment = kaliszappan,
                 species_list = almatermesuek + csonthejasok + (szolo,),
                 max_applications = 99,
                 days_between_applications = 0,
                 apply_before = 'nincs korlatozas',
                 min_days_before_consumption = 0)

# bordoile
add_safety_limit(treatment = bordoile,
                 species_list = alma,
                 max_applications = 6,
                 days_between_applications = 7,
                 apply_before = 'BBCH 10-77 vagy BBCH 77-83',
                 min_days_before_consumption = 21)
add_safety_limit(treatment = bordoile,
                 species_list = korte,
                 max_applications = 5,
                 days_between_applications = 7,
                 apply_before = 'BBCH 10-69 vagy BBCH 77-83',
                 min_days_before_consumption = 21)
add_safety_limit(treatment = bordoile,
                 species_list = (sargabarack,oszi,szilva,meggy,cseresznye),
                 max_applications = 6,
                 days_between_applications = 7,
                 apply_before = 'BBCH 7-83',
                 min_days_before_consumption = 21)
add_safety_limit(treatment = bordoile,
                 species_list = szolo,
                 max_applications = 6,
                 days_between_applications = 7,
                 apply_before = 'lemoso (2x) vagy BBCH 14-79 (4x)',
                 min_days_before_consumption = 21)

# kezelesek

apply_treatment(olajos_rezken, osszes_fa, '2022-03-05')

apply_treatment(dithane, osszes_fa, '2022-04-17')

apply_treatment(dithane, osszes_fa, '2022-05-01')

apply_treatment(mospilan, osszes_fa, '2022-05-05')
apply_treatment(topas, osszes_fa, '2022-05-05')
apply_treatment(lamdex, osszes_fa, '2022-05-05')

apply_treatment(mospilan, (utcai_mandulafa, lenti_ringlofa, elso_ringlofa, kozepso_ringlofa, hatso_ringlofa, oszibarackfa), '2022-05-28')

apply_treatment(lamdex, sargabarackfa, '2022-05-30')
apply_treatment(mospilan, (almafa, hatso_almafa, elso_kortefa, hatso_kortefa, ribizlibokor), '2022-05-30')
apply_treatment(topas, (almafa, hatso_almafa, elso_kortefa, hatso_kortefa, ribizlibokor), '2022-05-30')
apply_treatment(lamdex, (almafa, hatso_almafa, elso_kortefa, hatso_kortefa, ribizlibokor), '2022-05-30')

apply_treatment(score, (elso_kortefa, hatso_kortefa), '2022-06-02')

apply_treatment(flumite, szolotoke, '2022-06-20')

apply_treatment(mospilan, szolotoke, '2022-07-08')

apply_treatment(champion, (almafa, hatso_kortefa, utcai_mandulafa), '2022-07-09')
apply_treatment(signum, (almafa, hatso_kortefa, utcai_mandulafa), '2022-07-09')
apply_treatment(kaliszappan, (almafa, hatso_kortefa, utcai_mandulafa), '2022-07-09')

apply_treatment(bordoile, (almafa, hatso_kortefa, szolotoke), '2022-08-01')

conn.commit()

as_of_date = '2022-07-28'

print('================')

print('Treatment date limits in effect')
current_limits = treatment_date_limits_in_effect(as_of_date)
for limit in current_limits:
    print(limit['plant'], '+', limit['treatment'], ':', limit['treatmentDate'], '==>', limit['safeToRepeatDate'])

print('================')
    
print('Safe to consume dates')
current_dates = safe_to_consume_dates(as_of_date)
for date_entry in current_dates:
    print(date_entry['plant'], '+', date_entry['treatment'], ':', date_entry['treatmentDate'], '==>', date_entry['safeToConsumeDate'])
    
print('================')

print('Treatments no longer applicable')
treatments = treatments_no_longer_applicable(as_of_date)
for treatment in treatments:
    print(treatment['plantDescription'], '+', treatment['treatmentDescription'], ':', treatment['treatments'], '>=', treatment['maxApplications'])

print('================')

print('Treatments applied this year without limit info')
treatments = treatments_applied_without_limit_info(as_of_date)
for treatment in treatments:
    print(treatment['plant'], '+', treatment['treatment'], ':', treatment['date'])
    
print('================')

treatment = 'Signum'
print('All limit info for a treatment (', treatment, ')')
limits = all_limit_info_for_treatment(treatment)
for limit in limits:
    print(limit['species'], '+', treatment, ': max', limit['maxApplications'], 'x with delay', limit['daysBetweenApplications'], 'days, applied', limit['applyBefore'], ', and safe to consume after', limit['minDaysBeforeConsumption'], 'days') 

print('================')

conn.close()

