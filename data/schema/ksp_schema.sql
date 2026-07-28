-- SUTRA
-- DDL mirroring the Karnataka State Police FIR entity relationship diagram.
--
-- This file is a faithful mirror, not an improvement. Where the source schema
-- lacks something we need, the lack is annotated and left in place. The gaps
-- are the finding, so papering over them here would erase the result.
--
-- Dialect is SQLite compatible ANSI. Column naming follows the KSP diagram in
-- PascalCase rather than this file's own preference.

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- Territorial hierarchy
-- ---------------------------------------------------------------------------

CREATE TABLE State (
    StateID           INTEGER PRIMARY KEY,
    StateName         TEXT    NOT NULL,
    StateNameKn       TEXT,
    StateCode         TEXT    NOT NULL
);

CREATE TABLE District (
    DistrictID        INTEGER PRIMARY KEY,
    StateID           INTEGER NOT NULL REFERENCES State(StateID),
    DistrictName      TEXT    NOT NULL,
    DistrictNameKn    TEXT,
    DistrictCode      TEXT    NOT NULL,   -- 4 digits, embedded in CrimeNo
    Latitude          REAL,
    Longitude         REAL,
    Active            TEXT    NOT NULL DEFAULT 'Y' CHECK (Active IN ('Y','N'))
);

CREATE TABLE UnitType (
    UnitTypeID        INTEGER PRIMARY KEY,
    UnitTypeName      TEXT    NOT NULL,   -- Police Station, Sub Division, District, Range
    HierarchyLevel    INTEGER NOT NULL
);

-- Unit is self referencing through ParentUnitID. Layer 3d walks this edge to
-- compute administrative distance, which is a different quantity from physical
-- distance and is not derivable from latitude and longitude.
CREATE TABLE Unit (
    UnitID            INTEGER PRIMARY KEY,
    UnitTypeID        INTEGER NOT NULL REFERENCES UnitType(UnitTypeID),
    DistrictID        INTEGER NOT NULL REFERENCES District(DistrictID),
    ParentUnitID      INTEGER REFERENCES Unit(UnitID),
    UnitName          TEXT    NOT NULL,
    UnitNameKn        TEXT,
    UnitCode          TEXT    NOT NULL,   -- 4 digits, embedded in CrimeNo
    Latitude          REAL,
    Longitude         REAL,
    Active            TEXT    NOT NULL DEFAULT 'Y' CHECK (Active IN ('Y','N'))
);

CREATE INDEX ix_unit_district ON Unit(DistrictID);
CREATE INDEX ix_unit_parent   ON Unit(ParentUnitID);

-- ---------------------------------------------------------------------------
-- Personnel
-- ---------------------------------------------------------------------------

CREATE TABLE Rank (
    RankID            INTEGER PRIMARY KEY,
    RankName          TEXT    NOT NULL,
    RankAbbr          TEXT    NOT NULL,
    SeniorityOrder    INTEGER NOT NULL
);

CREATE TABLE Designation (
    DesignationID     INTEGER PRIMARY KEY,
    DesignationName   TEXT    NOT NULL,
    RankID            INTEGER REFERENCES Rank(RankID)
);

-- Employee is the only reliable cross case identity in the source schema.
-- Officers have a stable key. The people they arrest do not. Layer 3f exploits
-- the asymmetry, since a shared arresting officer is weak but genuine evidence
-- that two accused rows sit in one investigative context.
CREATE TABLE Employee (
    EmployeeID        INTEGER PRIMARY KEY,
    EmployeeName      TEXT    NOT NULL,
    EmployeeNameKn    TEXT,
    RankID            INTEGER NOT NULL REFERENCES Rank(RankID),
    DesignationID     INTEGER REFERENCES Designation(DesignationID),
    UnitID            INTEGER NOT NULL REFERENCES Unit(UnitID),
    BuckleNo          TEXT,
    Active            TEXT    NOT NULL DEFAULT 'Y' CHECK (Active IN ('Y','N'))
);

CREATE INDEX ix_employee_unit ON Employee(UnitID);

-- ---------------------------------------------------------------------------
-- Offence classification
-- ---------------------------------------------------------------------------

CREATE TABLE CaseCategory (
    CaseCategoryID    INTEGER PRIMARY KEY,   -- 1 digit, leads CrimeNo
    CaseCategoryName  TEXT    NOT NULL
);

CREATE TABLE GravityOffence (
    GravityOffenceID  INTEGER PRIMARY KEY,
    GravityName       TEXT    NOT NULL,      -- Heinous, Serious, Ordinary, Minor
    GravityRank       INTEGER NOT NULL
);

CREATE TABLE CrimeHead (
    CrimeHeadID       INTEGER PRIMARY KEY,
    CrimeHeadName     TEXT    NOT NULL,
    CrimeHeadNameKn   TEXT
);

CREATE TABLE CrimeSubHead (
    CrimeSubHeadID    INTEGER PRIMARY KEY,
    CrimeHeadID       INTEGER NOT NULL REFERENCES CrimeHead(CrimeHeadID),
    CrimeSubHeadName  TEXT    NOT NULL,
    CrimeSubHeadNameKn TEXT
);

-- Act.Active and Section.Active carry the July 2024 IPC to BNS transition.
-- Layer 9 reads EffectiveFrom and EffectiveTo to reconcile trend queries that
-- cross 2024-07-01. Without that reconciliation every offence series shows a
-- cliff at the transition date that is an artefact of legislation.
CREATE TABLE Act (
    ActID             INTEGER PRIMARY KEY,
    ActName           TEXT    NOT NULL,
    ActAbbr           TEXT    NOT NULL,
    ActYear           INTEGER,
    EffectiveFrom     TEXT,
    EffectiveTo       TEXT,
    Active            TEXT    NOT NULL DEFAULT 'Y' CHECK (Active IN ('Y','N'))
);

CREATE TABLE Section (
    SectionID         INTEGER PRIMARY KEY,
    ActID             INTEGER NOT NULL REFERENCES Act(ActID),
    SectionNo         TEXT    NOT NULL,
    SectionDesc       TEXT,
    SectionDescKn     TEXT,
    GravityOffenceID  INTEGER REFERENCES GravityOffence(GravityOffenceID),
    IsCognizable      TEXT    CHECK (IsCognizable IN ('Y','N')),
    IsBailable        TEXT    CHECK (IsBailable IN ('Y','N')),
    SuccessorSectionID INTEGER REFERENCES Section(SectionID),  -- IPC row points to its BNS row
    Active            TEXT    NOT NULL DEFAULT 'Y' CHECK (Active IN ('Y','N'))
);

CREATE INDEX ix_section_act       ON Section(ActID);
CREATE INDEX ix_section_successor ON Section(SuccessorSectionID);

-- ---------------------------------------------------------------------------
-- The case
-- ---------------------------------------------------------------------------

CREATE TABLE CaseMaster (
    CaseMasterID      INTEGER PRIMARY KEY,
    -- 18 characters. 1 case category, 4 district, 4 station, 4 year, 5 serial.
    CrimeNo           TEXT    NOT NULL UNIQUE,
    UnitID            INTEGER NOT NULL REFERENCES Unit(UnitID),
    DistrictID        INTEGER NOT NULL REFERENCES District(DistrictID),
    CaseCategoryID    INTEGER NOT NULL REFERENCES CaseCategory(CaseCategoryID),
    CrimeHeadID       INTEGER REFERENCES CrimeHead(CrimeHeadID),
    CrimeSubHeadID    INTEGER REFERENCES CrimeSubHead(CrimeSubHeadID),
    GravityOffenceID  INTEGER REFERENCES GravityOffence(GravityOffenceID),
    CrimeRegisteredDate TEXT  NOT NULL,     -- ISO 8601 date
    CrimeRegisteredTime TEXT,
    OccurrenceFromDate  TEXT,
    OccurrenceToDate    TEXT,
    -- Layer 3d reads these directly. They are per incident, not per station.
    Latitude          REAL,
    Longitude         REAL,
    PlaceOfOffence    TEXT,
    -- Layer 3e embeds this field. It is the only free text carrying modus
    -- operandi, and it is written in Kannada or English depending on the
    -- station, so the embedding model has to be multilingual.
    BriefFacts        TEXT,
    IOEmployeeID      INTEGER REFERENCES Employee(EmployeeID),
    CaseStatus        TEXT,
    Active            TEXT    NOT NULL DEFAULT 'Y' CHECK (Active IN ('Y','N'))
);

CREATE INDEX ix_case_unit     ON CaseMaster(UnitID);
CREATE INDEX ix_case_district ON CaseMaster(DistrictID);
CREATE INDEX ix_case_date     ON CaseMaster(CrimeRegisteredDate);

CREATE TABLE ActSectionAssociation (
    ActSectionAssocID INTEGER PRIMARY KEY,
    CaseMasterID      INTEGER NOT NULL REFERENCES CaseMaster(CaseMasterID),
    ActID             INTEGER NOT NULL REFERENCES Act(ActID),
    SectionID         INTEGER NOT NULL REFERENCES Section(SectionID)
);

CREATE INDEX ix_asa_case    ON ActSectionAssociation(CaseMasterID);
CREATE INDEX ix_asa_section ON ActSectionAssociation(SectionID);

-- ---------------------------------------------------------------------------
-- People in the case
-- ---------------------------------------------------------------------------

-- THE FINDING.
--
-- This table is the reason SUTRA exists. Read the columns.
--
-- AccusedMasterID is a surrogate key scoped to one row of one FIR. It does not
-- identify a person. The same man arrested in Hubballi and again in Belagavi
-- gets two AccusedMasterID values with nothing connecting them.
--
-- PersonID holds A1, A2, A3. It is an ordering label within a single FIR. It
-- carries no meaning across CaseMasterID and must never be joined on.
--
-- There is no FatherName column. No Address. No PhoneNumber. No biometric
-- reference, no UID, no fingerprint slip number. Confirm that by reading the
-- column list rather than by taking our word for it.
--
-- What remains is AccusedName, free text, written in Kannada script or Latin
-- transliteration at the discretion of the station writer, sometimes carrying
-- a patronymic inside the string and sometimes not.
--
-- Therefore there is no cross case person key in this schema, and criminal
-- network analysis over these rows as supplied is not possible. Layers 1 to 7
-- construct the key. This comment stays here permanently as the statement of
-- what was wrong.
--
-- One thing the table does give us, and it is valuable. Two rows sharing a
-- CaseMasterID are A1 and A2 of the same FIR and are therefore provably
-- different people. Layer 5 takes that as a hard cannot link constraint. It is
-- the only identity fact in the schema that is certain.
CREATE TABLE Accused (
    AccusedMasterID   INTEGER PRIMARY KEY,
    CaseMasterID      INTEGER NOT NULL REFERENCES CaseMaster(CaseMasterID),
    PersonID          TEXT    NOT NULL,     -- A1, A2, A3. Within FIR only.
    AccusedName       TEXT    NOT NULL,
    AgeYear           INTEGER,              -- station estimate, often rounded
    GenderID          INTEGER,
    -- Present because the source schema has them. Never a model feature.
    -- Blocked at engine/policy.py, which raises rather than warns. See
    -- docs/ethics.md section 5.
    CasteID           INTEGER,
    ReligionID        INTEGER,
    OccupationID      INTEGER,
    AccusedType       TEXT,                 -- Known, Unknown, Absconding
    Nationality       TEXT,
    Active            TEXT    NOT NULL DEFAULT 'Y' CHECK (Active IN ('Y','N'))
);

CREATE INDEX ix_accused_case ON Accused(CaseMasterID);
CREATE INDEX ix_accused_name ON Accused(AccusedName);

CREATE TABLE Victim (
    VictimID          INTEGER PRIMARY KEY,
    CaseMasterID      INTEGER NOT NULL REFERENCES CaseMaster(CaseMasterID),
    PersonID          TEXT,                 -- V1, V2. Same within FIR limitation.
    VictimName        TEXT    NOT NULL,
    AgeYear           INTEGER,
    GenderID          INTEGER,
    CasteID           INTEGER,
    ReligionID        INTEGER,
    OccupationID      INTEGER,
    InjuryType        TEXT
);

CREATE INDEX ix_victim_case ON Victim(CaseMasterID);

CREATE TABLE ComplainantDetails (
    ComplainantID     INTEGER PRIMARY KEY,
    CaseMasterID      INTEGER NOT NULL REFERENCES CaseMaster(CaseMasterID),
    ComplainantName   TEXT    NOT NULL,
    AgeYear           INTEGER,
    GenderID          INTEGER,
    Address           TEXT,                 -- present here, absent on Accused
    PhoneNumber       TEXT,                 -- present here, absent on Accused
    RelationToVictim  TEXT
);

CREATE INDEX ix_complainant_case ON ComplainantDetails(CaseMasterID);

-- Note the asymmetry above. The complainant has an address and a phone. The
-- accused has neither. That is a records design choice with a rationale, and it
-- is also the direct cause of the identity gap.

CREATE TABLE ArrestSurrender (
    ArrestSurrenderID INTEGER PRIMARY KEY,
    CaseMasterID      INTEGER NOT NULL REFERENCES CaseMaster(CaseMasterID),
    AccusedMasterID   INTEGER NOT NULL REFERENCES Accused(AccusedMasterID),
    ArrestType        TEXT,                 -- Arrest, Surrender
    ArrestDate        TEXT,
    ArrestTime        TEXT,
    ArrestPlace       TEXT,
    -- Layer 3f relational evidence. Officers have stable identity, so a shared
    -- arresting officer links two accused rows into one investigative context.
    ArrestingOfficerID INTEGER REFERENCES Employee(EmployeeID),
    RemandDate        TEXT,
    BailFlag          TEXT CHECK (BailFlag IN ('Y','N'))
);

CREATE INDEX ix_arrest_case    ON ArrestSurrender(CaseMasterID);
CREATE INDEX ix_arrest_accused ON ArrestSurrender(AccusedMasterID);
CREATE INDEX ix_arrest_officer ON ArrestSurrender(ArrestingOfficerID);

-- cstype is the final report classification.
--   A  true and detected, chargesheet filed
--   B  false, mistake of fact or of law
--   C  true but undetected, offender not traced
--   D  non cognizable, no further action
-- Layer 8 ranks candidate suspects for cstype C only. See docs/ethics.md
-- section 4 for why that ranking is retrieval over cases and not prediction
-- about a person.
CREATE TABLE ChargesheetDetails (
    ChargesheetID     INTEGER PRIMARY KEY,
    CaseMasterID      INTEGER NOT NULL REFERENCES CaseMaster(CaseMasterID),
    cstype            TEXT    NOT NULL CHECK (cstype IN ('A','B','C','D')),
    ChargesheetNo     TEXT,
    ChargesheetDate   TEXT,
    FiledByEmployeeID INTEGER REFERENCES Employee(EmployeeID),
    CourtName         TEXT,
    Remarks           TEXT
);

CREATE INDEX ix_chargesheet_case ON ChargesheetDetails(CaseMasterID);
CREATE INDEX ix_chargesheet_type ON ChargesheetDetails(cstype);

-- ---------------------------------------------------------------------------
-- What is deliberately absent
-- ---------------------------------------------------------------------------
--
-- There is no Person table and no PersonCaseLink table in this file, because
-- there is none in the KSP schema. Layers 1 to 7 construct them, and their DDL
-- lives in data/schema/resolved_schema.sql, which does not exist yet because
-- the engine does not exist yet.
--
-- Keeping the two files apart is the point. This one is the record as it is.
-- The other is what SUTRA adds. Nothing in this file will be edited to make the
-- engine's job easier.
