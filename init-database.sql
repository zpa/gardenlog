CREATE TABLE PlantSpecies (
       id INTEGER PRIMARY KEY,
       name TEXT NOT NULL
       );

CREATE TABLE Plant (
       id INTEGER PRIMARY KEY,
       speciesId INTEGER NOT NULL,
       description TEXT NOT NULL,
       FOREIGN KEY(speciesId) REFERENCES PlantSpecies(id)
       );

CREATE TABLE TreatmentType (
       id INTEGER PRIMARY KEY,
       description TEXT NOT NULL
       );

CREATE TABLE AppliedTreatment (
       id INTEGER PRIMARY KEY,
       treatmentTypeId INTEGER NOT NULL,
       plantId INTEGER NOT NULL,
       treatmentDate REAL NOT NULL,
       FOREIGN KEY(treatmentTypeId) REFERENCES TreatmentType(id),
       FOREIGN KEY(plantId) REFERENCES Plant(id)
       );

CREATE TABLE SafetyLimits (
       id INTEGER PRIMARY KEY,
       treatmentTypeId INTEGER NOT NULL,
       speciesId INTEGER NOT NULL,
       daysToWait INTEGER NOT NULL,
       maxApplications INTEGER NOT NULL,
       applyBefore TEXT NOT NULL,
       FOREIGN KEY(treatmentTypeId) REFERENCES TreatmentType(id),
       FOREIGN KEY(speciesId) REFERENCES PlantSpecies(id)
       );

queries to write:
(1) check which plants are forbidden to treat with what because of date limit
(2) check which plants are forbidden to eat because of what until when
(3) check which plants are forbidden to treat with what because of max number limit
(4) check which plants should be consumed with care because of which treatment (no safety limit defined for species)
(5) list treatment safety limits for all species (related to (4))

(1) does not take into accunt max repeats!!!
SELECT p.description as plant, tt.description as treatment, date(t.date) as treatmentDate, date(t.date + l.daysBetweenApplications) as safeToRepeatDate
FROM AppliedTreatment t
LEFT JOIN Plant p
ON t.plantId = p.id
INNER JOIN SafetyLimit l
ON t.treatmentTypeId = l.treatmentTypeId AND l.speciesId = p.speciesId
LEFT JOIN TreatmentType tt
ON t.treatmentTypeId = tt.id
WHERE t.date <= julianday('2022-07-27') AND t.date + l.daysBetweenApplications >= julianday('2022-07-27')

(2) when can I consume which fruits?
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
WHERE t.date <= julianday('2022-07-27') AND t.date + l.minDaysBeforeConsumption >= julianday('2022-07-27')
)
GROUP BY plant

(3)
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
WHERE t.date <= julianday('2022-07-27') and t.date >= julianday('2022-01-01')
)
GROUP BY plantId, treatmentTypeId
)
WHERE treatments >= maxApplications


(4) treatments applied without limit information:
SELECT tt.description as treatment, date(t.date) as date, p.description as plant
FROM AppliedTreatment t
LEFT JOIN Plant p
ON t.plantId = p.id
LEFT JOIN SafetyLimit l
ON t.treatmentTypeId = l.treatmentTypeId AND l.speciesId = p.speciesId
LEFT JOIN TreatmentType tt
ON t.treatmentTypeId = tt.id
WHERE l.id IS NULL AND t.date >= julianday('2022-01-01');


(5) all limit information available for a particular treatment
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
WHERE t.description = 'Signum';

(6)
SELECT p.id as plantId, p.description as plantDescription, t.treatmentTypeId as treatmentTypeId, tt.description as treatmentDescription, date(t.date) as treatmentDate
FROM AppliedTreatment t
LEFT JOIN Plant p
ON t.plantId = p.id
LEFT JOIN TreatmentType tt
ON t.treatmentTypeId = tt.id
WHERE t.date <= julianday('2022-07-27') and t.date >= julianday('2022-01-01') and p.id = 1


