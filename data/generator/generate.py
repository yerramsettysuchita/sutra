"""Synthetic KSP FIR corpus generator.

Writes a corpus on the exact KSP schema in which person identity is known by
construction, because the generator emitted every row from a known synthetic
person and wrote the map.

This exists because the real corpus has no ground truth identity, which is the
problem SUTRA solves, so it also cannot be used to measure whether SUTRA solved
it. Nothing here is a stand in for real data. It is a measuring instrument.

Run
    python -m data.generator.generate --cases 5000

Output lands in data/corpus, one CSV per table, plus data/corpus/ground_truth.
Seed is fixed at 4471. Two runs produce byte identical output.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from itertools import combinations
from pathlib import Path

from . import SEED
from . import name_variants as NV
from . import reference_data as R

# ---------------------------------------------------------------------------
# Corpus configuration
# ---------------------------------------------------------------------------

CORPUS_START = date(2021, 1, 1)
CORPUS_END = date(2026, 6, 30)
TRANSITION = date(2024, 7, 1)

# Share of cases closed as cstype C, true but undetected. These carry no
# Accused rows and are the input to the Layer 8 candidate matcher. Ground truth
# knows the perpetrator, the corpus does not.
UNDETECTED_SHARE = 0.09

# Accused per detected case.
ACCUSED_COUNT_DIST = [(1, 0.58), (2, 0.24), (3, 0.11), (4, 0.05), (5, 0.02)]

# Appearances per synthetic person. Heavy tailed, because offending is.
APPEARANCE_DIST = [
    ((1, 1), 0.620),
    ((2, 2), 0.170),
    ((3, 3), 0.085),
    ((4, 4), 0.050),
    ((5, 5), 0.030),
    ((6, 8), 0.030),
    ((9, 12), 0.012),
    ((13, 18), 0.003),
]

# Deliberate hard negatives. Distinct people, identical canonical name,
# identical home district. Without these the corpus would reward a name
# matcher, and a name matcher is what we are arguing against.
#
# Expressed as a share of eligible repeat offenders rather than as a count, so
# the density of the trap is the same at 5,000 cases and at 150,000. A fixed
# count would have made the full corpus roughly thirty times easier than the
# development corpus, and every false merge number measured on one would have
# been meaningless on the other.
COLLISION_GROUP_SHARE = 0.0733

# Share of rows whose recorded gender is wrong.
#
# This exists because of a specific mistake. The engine gained a gender channel
# (ADR 028) and the corpus reported that zero of 3,840 true people had two rows
# disagreeing on gender. That was published as a measurement. It was not one.
# The generator copied each person's gender onto every row verbatim, so the
# figure was guaranteed by construction and the channel was being scored against
# a field that could not be wrong.
#
# A binary, directly observed field is genuinely far cleaner than a
# transliterated name, so the rate is low. It is not zero, because clerical
# entry into a coded field is never zero: mis-keyed codes, rows copied from a
# previous FIR, and the recorder guessing from a name they cannot gender.
#
# 1.2% is a parameter and not a discovery. scripts/gender_noise_study.py sweeps
# it from 0 to 5% and reports what the channel is worth at each, because the
# honest question is not "does gender help on our corpus" but "how much of the
# help survives the field being imperfect". See ADR 030.
GENDER_ERROR_RATE = 0.012
GENDER_PASS_SEED_OFFSET = 71351

# Co offending density.
#
# This is a parameter and not a constant, and the reason is documented in
# docs/decisions.md ADR 012.
#
# The criminological finding is that co offending relationships are mostly one
# off. Charette and Papachristos, tracking co arrest dyads across eight years of
# Chicago arrest records, find that co offenders rarely commit more than one
# offence together. Sarnecki's Stockholm work puts only about 2.5% of co
# offending relationships persisting beyond six months. Warr's position is
# stronger still, that delinquent groups are so short lived that speaking of
# groups at all is barely meaningful.
#
# So a generator that makes co offending recur freely is not modelling crime, it
# is manufacturing evidence for Layer 3f. The measured quantity to calibrate
# against is the dyad recurrence rate, the share of co offending pairs who appear
# together in more than one case. audit.py reports it.
#
# Three presets, swept in the Layer 3f ablation rather than picked once. What we
# report is how the relational signal's contribution moves across them, because
# a single number here would be our constant rather than the world's.
CO_OFFENDING_PRESETS = {
    # Co offending is almost entirely opportunistic. Closest to Warr.
    "sparse":   {"gang_share": 0.20, "prefer_gang": 0.00, "gang_fill": 0.30},
    # A persistent minority inside a mostly transient population. Default.
    "moderate": {"gang_share": 0.38, "prefer_gang": 0.35, "gang_fill": 0.70},
    # Organised recurring groups. Above what the literature supports, kept so
    # the sweep has an upper bound to show the signal saturating.
    "dense":    {"gang_share": 0.55, "prefer_gang": 0.80, "gang_fill": 0.90},
}
DEFAULT_CO_OFFENDING = "moderate"

# Probability that an arrest reuses the officer who last arrested this person at
# this station. Beat officers know their repeat offenders and the same names come
# back to the same hands. This is a claim about police work rather than about
# offending, and it is far less contested than co offending recurrence, so it
# stays a constant.
OFFICER_AFFINITY = 0.55

# District weights, loosely tracking where crime volume actually sits. Not
# census accurate and not claimed to be. Bengaluru Urban dominates.
DISTRICT_WEIGHT_OVERRIDES = {
    "Bengaluru Urban": 9.0,
    "Mysuru": 2.6,
    "Belagavi": 2.4,
    "Kalaburagi": 2.0,
    "Dakshina Kannada": 1.9,
    "Dharwad": 1.8,
    "Tumakuru": 1.7,
    "Ballari": 1.6,
    "Shivamogga": 1.5,
    "Bengaluru Rural": 1.5,
}


# ---------------------------------------------------------------------------
# Small numeric helpers, kept local so the generator stays dependency free
# ---------------------------------------------------------------------------

def zipf_weights(n: int, s: float = 0.85) -> list[float]:
    """Zipf like weights over a ranked pool.

    Name frequency in any population is heavily skewed. Sampling uniformly
    would erase that, and erasing it would make the inverse name frequency
    correction in Layer 4 impossible to demonstrate, since every name would
    carry the same evidential weight.
    """
    return [1.0 / ((i + 1) ** s) for i in range(n)]


def pick_weighted(rng: random.Random, items, weights):
    return rng.choices(items, weights=weights, k=1)[0]


def sample_bucket(rng: random.Random, dist):
    r = rng.random()
    acc = 0.0
    for value, prob in dist:
        acc += prob
        if r <= acc:
            return value
    return dist[-1][0]


def sample_appearances(rng: random.Random) -> int:
    lo, hi = sample_bucket(rng, APPEARANCE_DIST)
    return rng.randint(lo, hi)


def jitter(rng: random.Random, value: float, spread: float) -> float:
    return round(value + rng.uniform(-spread, spread), 6)


def random_date(rng: random.Random, start: date, end: date) -> date:
    span = (end - start).days
    return start + timedelta(days=rng.randrange(max(span, 1)))


# ---------------------------------------------------------------------------
# Reference table construction
# ---------------------------------------------------------------------------

RANGE_NAMES = ["Central Range", "Eastern Range", "Northern Range",
               "Southern Range", "Western Range"]


def build_territory(rng: random.Random):
    """Districts, ranges, district units, sub divisions, police stations.

    The Unit tree is real, four levels deep, because Layer 3d walks ParentUnit
    to compute administrative distance, and a flat table would make that signal
    untestable.
    """
    districts, units = [], []
    stations = []
    unit_id = 0

    def new_unit(unit_type_id, district_id, parent, name, name_kn, code, lat, lon):
        nonlocal unit_id
        unit_id += 1
        units.append({
            "UnitID": unit_id,
            "UnitTypeID": unit_type_id,
            "DistrictID": district_id,
            "ParentUnitID": parent,
            "UnitName": name,
            "UnitNameKn": name_kn,
            "UnitCode": code,
            "Latitude": lat,
            "Longitude": lon,
            "Active": "Y",
        })
        return unit_id

    range_ids = {}
    for i, rname in enumerate(RANGE_NAMES):
        range_ids[rname] = new_unit(1, DISTRICTS_ANCHOR_ID, None, rname, None,
                                    f"{9000 + i:04d}", None, None)

    for idx, (dcode, dname, dname_kn, lat, lon) in enumerate(R.DISTRICTS):
        districts.append({
            "DistrictID": dcode,
            "StateID": R.STATE["StateID"],
            "DistrictName": dname,
            "DistrictNameKn": dname_kn,
            "DistrictCode": f"{dcode:04d}",
            "Latitude": lat,
            "Longitude": lon,
            "Active": "Y",
        })
        parent_range = range_ids[RANGE_NAMES[idx % len(RANGE_NAMES)]]
        district_unit = new_unit(2, dcode, parent_range, f"{dname} District Police",
                                 dname_kn, f"{8000 + dcode:04d}", lat, lon)

        station_code = 1000
        for sd in range(rng.randint(2, 3)):
            sub_unit = new_unit(
                3, dcode, district_unit, f"{dname} Sub Division {sd + 1}", None,
                f"{7000 + dcode * 10 + sd:04d}", lat, lon)
            stems = rng.sample(R.LOCALITY_STEMS, rng.randint(3, 5))
            for stem_la, stem_kn in stems:
                station_code += 1
                slat = jitter(rng, lat, 0.35)
                slon = jitter(rng, lon, 0.35)
                sid = new_unit(4, dcode, sub_unit,
                               f"{dname} {stem_la} Police Station",
                               f"{dname_kn} {stem_kn} à²ªà³Šà²²à³€à²¸à³ à² à²¾à²£à³†",
                               f"{station_code:04d}", slat, slon)
                # Each station gets a house habit for script. A station that
                # writes Kannada keeps writing Kannada, so script divergence
                # tracks jurisdiction divergence rather than being independent
                # noise. That correlation is what makes the problem hard in a
                # realistic way.
                bias = pick_weighted(rng, ["kannada", "latin", None], [0.38, 0.42, 0.20])
                stations.append({
                    "UnitID": sid,
                    "DistrictID": dcode,
                    "DistrictName": dname,
                    "DistrictCode": f"{dcode:04d}",
                    "UnitCode": f"{station_code:04d}",
                    "Latitude": slat,
                    "Longitude": slon,
                    "ScriptBias": bias,
                })
    return districts, units, stations


DISTRICTS_ANCHOR_ID = 4  # ranges are pinned to a district for FK validity


def build_personnel(rng: random.Random, stations):
    """Officers, six to eleven per station.

    Employee is the one entity in the source schema with reliable cross case
    identity. Layer 3f uses that asymmetry, since a shared arresting officer
    places two accused rows in one investigative context.
    """
    employees = []
    by_station = defaultdict(list)
    io_by_station = defaultdict(list)
    emp_id = 0

    male_w = zipf_weights(len(R.GIVEN_NAMES_MALE))
    father_w = zipf_weights(len(R.FATHER_NAMES))

    for st in stations:
        for _ in range(rng.randint(6, 11)):
            emp_id += 1
            g_la, g_kn = pick_weighted(rng, R.GIVEN_NAMES_MALE, male_w)
            f_la, f_kn = pick_weighted(rng, R.FATHER_NAMES, father_w)
            identity = {"given_la": g_la, "given_kn": g_kn,
                        "father_la": f_la, "father_kn": f_kn}
            rank_id = pick_weighted(
                rng, [1, 2, 3, 4, 5, 6],
                [0.34, 0.24, 0.14, 0.12, 0.11, 0.05])
            designation = next(
                (d[0] for d in R.DESIGNATIONS if d[2] == rank_id), None)
            employees.append({
                "EmployeeID": emp_id,
                "EmployeeName": f"{g_la} {f_la}",
                "EmployeeNameKn": f"{g_kn} {f_kn}",
                "RankID": rank_id,
                "DesignationID": designation,
                "UnitID": st["UnitID"],
                "BuckleNo": f"KA{st['DistrictCode']}{emp_id:05d}",
                "Active": "Y",
            })
            by_station[st["UnitID"]].append(emp_id)
            if rank_id in R.IO_RANK_IDS:
                io_by_station[st["UnitID"]].append(emp_id)

    # A station with no investigating rank would break case assignment.
    for st in stations:
        if not io_by_station[st["UnitID"]]:
            io_by_station[st["UnitID"]] = by_station[st["UnitID"]][:1]

    return employees, by_station, io_by_station


def build_catalogues():
    """Acts, sections and the IPC to BNS successor links.

    The successor edge lives in the data rather than in engine code, so Layer 9
    reconciliation is a join and correcting a mapping is a data change.
    """
    acts = [{
        "ActID": a[0], "ActName": a[1], "ActAbbr": a[2], "ActYear": a[3],
        "EffectiveFrom": a[4], "EffectiveTo": a[5], "Active": a[6],
    } for a in R.ACTS]

    act_id_by_abbr = {a["ActAbbr"]: a["ActID"] for a in acts}

    sections = []
    sec_id = 0
    ipc_section_id = {}
    bns_section_id = {}

    # BNS first, so the IPC rows can point forward at a known SectionID.
    for ipc_no, bns_no, desc, desc_kn, grav, cog, bail in R.IPC_TO_BNS:
        sec_id += 1
        bns_section_id[ipc_no] = sec_id
        sections.append({
            "SectionID": sec_id, "ActID": act_id_by_abbr["BNS"],
            "SectionNo": bns_no, "SectionDesc": desc, "SectionDescKn": desc_kn,
            "GravityOffenceID": grav, "IsCognizable": cog, "IsBailable": bail,
            "SuccessorSectionID": None, "Active": "Y",
        })
    for ipc_no, bns_no, desc, desc_kn, grav, cog, bail in R.IPC_TO_BNS:
        sec_id += 1
        ipc_section_id[ipc_no] = sec_id
        sections.append({
            "SectionID": sec_id, "ActID": act_id_by_abbr["IPC"],
            "SectionNo": ipc_no, "SectionDesc": desc, "SectionDescKn": desc_kn,
            "GravityOffenceID": grav, "IsCognizable": cog, "IsBailable": bail,
            "SuccessorSectionID": bns_section_id[ipc_no], "Active": "N",
        })

    other_section_id = {}
    for abbr, no, desc, desc_kn, grav, cog, bail in R.OTHER_SECTIONS:
        sec_id += 1
        other_section_id[(abbr, no)] = sec_id
        sections.append({
            "SectionID": sec_id, "ActID": act_id_by_abbr[abbr],
            "SectionNo": no, "SectionDesc": desc, "SectionDescKn": desc_kn,
            "GravityOffenceID": grav, "IsCognizable": cog, "IsBailable": bail,
            "SuccessorSectionID": None, "Active": "Y",
        })

    return acts, sections, act_id_by_abbr, ipc_section_id, bns_section_id, other_section_id


# ---------------------------------------------------------------------------
# Synthetic people
# ---------------------------------------------------------------------------

def name_pools(vocabulary: int | None):
    """Given and patronymic pools, expanded to a target vocabulary.

    `None` keeps the shipped fixture exactly, so every figure measured before
    this parameter existed still reproduces.
    """
    if not vocabulary or vocabulary <= R.BASE_VOCABULARY:
        return R.GIVEN_NAMES_MALE, R.FATHER_NAMES, R.BASE_VOCABULARY
    # Split in the same proportion as the fixture, roughly two given names to
    # one patronymic, so widening the vocabulary does not also change its shape.
    given_target = round(vocabulary * len(R.GIVEN_NAMES_MALE) / R.BASE_VOCABULARY)
    father_target = vocabulary - given_target
    given = R.expand_pool(R.GIVEN_NAMES_MALE, given_target, R.GIVEN_SUFFIXES)
    father = R.expand_pool(R.FATHER_NAMES, father_target, R.FATHER_SUFFIXES,
                           seed_offset=1)
    return given, father, len(given) + len(father)


def build_persons(rng: random.Random, target_slots: int, stations, district_weights,
                  given_pool=None, father_pool=None):
    """Create synthetic people until their appearance quotas cover demand.

    Each person carries everything the engine is meant to recover: a stable
    birth year so implied age is consistent, a home station so the spatial
    prior is real, a modus operandi family so BriefFacts embeddings cluster,
    and an active window so trajectories through time are coherent.
    """
    persons = []
    total = 0
    pid = 0

    given_pool = given_pool or R.GIVEN_NAMES_MALE
    father_pool = father_pool or R.FATHER_NAMES

    male_w = zipf_weights(len(given_pool))
    female_w = zipf_weights(len(R.GIVEN_NAMES_FEMALE))
    father_w = zipf_weights(len(father_pool))
    mo_names = list(R.MO_FAMILIES.keys())

    stations_by_district = defaultdict(list)
    for st in stations:
        stations_by_district[st["DistrictID"]].append(st)
    district_ids = list(stations_by_district.keys())
    dweights = [district_weights[d] for d in district_ids]

    corpus_days = (CORPUS_END - CORPUS_START).days

    while total < target_slots:
        pid += 1
        gender = 1 if rng.random() < 0.92 else 2
        if gender == 1:
            g_la, g_kn = pick_weighted(rng, given_pool, male_w)
        else:
            g_la, g_kn = pick_weighted(rng, R.GIVEN_NAMES_FEMALE, female_w)
        f_la, f_kn = pick_weighted(rng, father_pool, father_w)

        has_moniker = rng.random() < 0.18
        m_la, m_kn = pick_weighted(rng, R.MONIKERS, zipf_weights(len(R.MONIKERS))) \
            if has_moniker else (None, None)

        home_district = pick_weighted(rng, district_ids, dweights)
        home_station = rng.choice(stations_by_district[home_district])

        quota = sample_appearances(rng)
        active_from = CORPUS_START + timedelta(days=rng.randrange(max(corpus_days - 150, 1)))
        active_to = min(active_from + timedelta(days=rng.randint(120, 1500)), CORPUS_END)

        persons.append({
            "TruePersonID": f"P{pid:06d}",
            "given_la": g_la, "given_kn": g_kn,
            "father_la": f_la, "father_kn": f_kn,
            "moniker_la": m_la, "moniker_kn": m_kn,
            # An alternate patronymic marker that appears in real records for
            # some communities. It is a property of how the name is written,
            # never a feature. See docs/ethics.md.
            "use_bin": rng.random() < 0.07,
            "GenderID": gender,
            "BirthYear": rng.randint(1961, 2005),
            "HomeDistrictID": home_district,
            "HomeUnitID": home_station["UnitID"],
            "MOFamily": rng.choice(mo_names),
            # Most offenders work a small territory. A minority range widely,
            # and those are the ones a station level system loses completely.
            "TravelPropensity": 0.42 if rng.random() < 0.15 else 0.09,
            "Quota": quota,
            "Remaining": quota,
            "ActiveFrom": active_from,
            "ActiveTo": active_to,
            "CasteID": rng.randint(*R.CASTE_ID_RANGE),
            "ReligionID": rng.randint(*R.RELIGION_ID_RANGE),
            "OccupationID": rng.randint(*R.OCCUPATION_ID_RANGE),
            "GangID": None,
            "CollisionGroup": None,
        })
        total += quota

    # Trim the final person so quotas sum to demand exactly.
    overshoot = total - target_slots
    if overshoot > 0:
        last = persons[-1]
        if last["Quota"] > overshoot:
            last["Quota"] -= overshoot
            last["Remaining"] = last["Quota"]
        else:
            persons.pop()

    return persons


def plant_collisions(rng: random.Random, persons):
    """Force distinct people onto identical names in identical districts.

    This is the trap. A system that resolves on the name string will merge
    these and report a clean result, and the false merge rate is the only place
    that error becomes visible. Half the groups get close birth years so age
    cannot separate them either, which leaves only territory, method and
    relational evidence.
    """
    eligible = [p for p in persons if p["Quota"] >= 2]
    rng.shuffle(eligible)
    groups = []
    cursor = 0
    n_groups = max(1, int(len(eligible) * COLLISION_GROUP_SHARE))
    for gid in range(n_groups):
        size = 2 if rng.random() < 0.75 else 3
        if cursor + size > len(eligible):
            break
        members = eligible[cursor:cursor + size]
        cursor += size
        anchor = members[0]
        tight_age = rng.random() < 0.5
        for m in members[1:]:
            m["given_la"] = anchor["given_la"]
            m["given_kn"] = anchor["given_kn"]
            m["father_la"] = anchor["father_la"]
            m["father_kn"] = anchor["father_kn"]
            m["HomeDistrictID"] = anchor["HomeDistrictID"]
            m["HomeUnitID"] = anchor["HomeUnitID"]
            m["moniker_la"] = anchor["moniker_la"]
            m["moniker_kn"] = anchor["moniker_kn"]
            if tight_age:
                m["BirthYear"] = anchor["BirthYear"] + rng.choice([-1, 0, 1])
        for m in members:
            m["CollisionGroup"] = f"C{gid:04d}"
        groups.append({
            "CollisionGroup": f"C{gid:04d}",
            "Members": [m["TruePersonID"] for m in members],
            "CanonicalName": f"{anchor['given_la']} {anchor['father_la']}",
            "DistrictID": anchor["HomeDistrictID"],
            "TightAge": tight_age,
        })
    return groups


def plant_gangs(rng: random.Random, persons, gang_share: float):
    """Recurring co offending groups.

    Layer 3f has nothing to read unless offenders reappear together. These
    groups are also what makes Layer 6 necessary, because merging two records
    creates an edge that changes the evidence for a third pair.
    """
    repeat = [p for p in persons if p["Quota"] >= 2]
    rng.shuffle(repeat)
    pool = repeat[:int(len(repeat) * gang_share)]
    by_district = defaultdict(list)
    for p in pool:
        by_district[p["HomeDistrictID"]].append(p)

    gangs = []
    gid = 0
    for district, members in by_district.items():
        rng.shuffle(members)
        i = 0
        while i + 1 < len(members):
            size = min(rng.randint(2, 4), len(members) - i)
            if size < 2:
                break
            gid += 1
            gang_id = f"G{gid:05d}"
            for m in members[i:i + size]:
                m["GangID"] = gang_id
            gangs.append({
                "GangID": gang_id,
                "DistrictID": district,
                "Members": [m["TruePersonID"] for m in members[i:i + size]],
            })
            i += size
    return gangs


# ---------------------------------------------------------------------------
# BriefFacts
# ---------------------------------------------------------------------------

def make_brief_facts(rng: random.Random, family_key, district_name, kannada_probability=0.15):
    family = R.MO_FAMILIES[family_key]
    use_kn = bool(family.get("kn")) and rng.random() < kannada_probability
    template = rng.choice(family["kn"] if use_kn else family["en"])
    stem = rng.choice(R.LOCALITY_STEMS)[0]
    fills = {
        "place": f"{stem}, {district_name}" if rng.random() < 0.5
                 else f"{rng.choice(R.PLACE_TYPES)} at {stem}, {district_name}",
        "time": f"{rng.randrange(0, 24):02d}.{rng.choice(['00', '15', '30', '45'])}",
        "vehicle": rng.choice(R.VEHICLES),
        "regno": f"KA{rng.randrange(1, 68):02d}{rng.choice('ABCDEFGHJKLMNPQRSTUVWXYZ')}"
                 f"{rng.choice('ABCDEFGHJKLMNPQRSTUVWXYZ')}{rng.randrange(1000, 9999)}",
        "value": f"{rng.randrange(3, 900) * 500:,}",
        "weight": rng.choice(["8", "12", "16", "20", "24", "32", "40"]),
        "count": rng.randint(2, 12),
        "brand": rng.choice(R.BRANDS),
        "direction": rng.choice(R.DIRECTIONS),
        "dispute": rng.choice(R.DISPUTES),
    }
    return template.format(**fills), ("kn" if use_kn else "en")


# ---------------------------------------------------------------------------
# Case construction
# ---------------------------------------------------------------------------

def sections_for_case(family_key, case_date, ipc_id, bns_id, other_id, act_by_abbr):
    """Resolve a modus operandi family to Act and Section rows for a date.

    Before 1 July 2024 the case cites IPC. On or after it, the same conduct
    cites the BNS successor. That switch is the entire reason Layer 9 exists,
    and a corpus that did not contain it could not test the reconciliation.
    """
    family = R.MO_FAMILIES[family_key]
    out = []
    use_bns = case_date >= TRANSITION
    for ipc_no in family.get("ipc", []):
        if use_bns:
            out.append((act_by_abbr["BNS"], bns_id[ipc_no]))
        else:
            out.append((act_by_abbr["IPC"], ipc_id[ipc_no]))
    for abbr, no in family.get("extra", []):
        out.append((act_by_abbr[abbr], other_id[(abbr, no)]))
    return out


def build_corpus(rng: random.Random, n_cases: int,
                 co_offending: str = DEFAULT_CO_OFFENDING,
                 name_pool: int | None = None,
                 seed: int = SEED,
                 gender_error_rate: float = GENDER_ERROR_RATE):
    if co_offending not in CO_OFFENDING_PRESETS:
        raise ValueError(
            f"unknown co offending preset {co_offending!r}, "
            f"expected one of {sorted(CO_OFFENDING_PRESETS)}")
    preset = CO_OFFENDING_PRESETS[co_offending]

    districts, units, stations = build_territory(rng)
    employees, emp_by_station, io_by_station = build_personnel(rng, stations)
    acts, sections, act_by_abbr, ipc_id, bns_id, other_id = build_catalogues()

    district_name = {d["DistrictID"]: d["DistrictName"] for d in districts}
    district_weights = {
        d["DistrictID"]: DISTRICT_WEIGHT_OVERRIDES.get(d["DistrictName"], 1.0)
        for d in districts
    }
    station_by_id = {s["UnitID"]: s for s in stations}
    stations_by_district = defaultdict(list)
    for st in stations:
        stations_by_district[st["DistrictID"]].append(st)
    all_station_ids = [s["UnitID"] for s in stations]
    all_station_weights = [district_weights[s["DistrictID"]] for s in stations]

    n_undetected = int(round(n_cases * UNDETECTED_SHARE))
    n_detected = n_cases - n_undetected

    # Pass one, decide how many accused each detected case carries, so the
    # person pool can be sized to exactly meet demand.
    accused_counts = [sample_bucket(rng, ACCUSED_COUNT_DIST) for _ in range(n_detected)]
    total_slots = sum(accused_counts)

    # Only the accused name pool widens. Officers, victims and complainants
    # keep the fixture pool, so the sweep isolates the effect of name
    # vocabulary on the entity resolution actually targets.
    given_pool, father_pool, vocabulary = name_pools(name_pool)
    persons = build_persons(rng, total_slots, stations, district_weights,
                            given_pool=given_pool, father_pool=father_pool)
    collisions = plant_collisions(rng, persons)
    gangs = plant_gangs(rng, persons, preset["gang_share"])

    person_by_id = {p["TruePersonID"]: p for p in persons}
    gang_members = defaultdict(list)
    for p in persons:
        if p["GangID"]:
            gang_members[p["GangID"]].append(p["TruePersonID"])

    # Rows
    case_rows, accused_rows, victim_rows = [], [], []
    complainant_rows, arrest_rows, chargesheet_rows, asa_rows = [], [], [], []
    identity_map, undetected_truth = [], []

    serial = defaultdict(int)
    # (TruePersonID, UnitID) to the officer who last arrested them there.
    officer_affinity = {}
    case_id = accused_id = victim_id = complainant_id = 0
    arrest_id = chargesheet_id = asa_id = 0

    male_w = zipf_weights(len(R.GIVEN_NAMES_MALE))
    female_w = zipf_weights(len(R.GIVEN_NAMES_FEMALE))
    father_w = zipf_weights(len(R.FATHER_NAMES))
    mo_names = list(R.MO_FAMILIES.keys())

    def available(pool):
        return [p for p in pool if p["Remaining"] > 0]

    # ---- offender selection, and why it is built this way ---------------
    #
    # The obvious implementation rescans the person pool on every case to find
    # who still has quota, then samples weighted by remaining quota. Both steps
    # are linear in the number of people, so the generator is quadratic in
    # corpus size. At 5,000 cases that is invisible. At 150,000 cases it is
    # roughly ten billion operations and the run does not finish.
    #
    # Instead the appearance schedule is decided up front. A slot list holds
    # each person once per unit of quota, shuffled. Drawing a lead is then a
    # cursor advance rather than a scan, and sampling proportional to remaining
    # quota falls out of the slot list automatically, because a person with
    # five appearances occupies five slots.
    #
    # Slots whose person has since been consumed as a co accused are skipped.
    # Each slot is skipped at most once, so the total skip work across the run
    # is linear in the number of slots rather than in cases times people.

    lead_slots = [p["TruePersonID"] for p in persons for _ in range(p["Quota"])]
    rng.shuffle(lead_slots)
    gang_slots = [pid for pid in lead_slots if person_by_id[pid]["GangID"]]
    lead_cursor = gang_cursor = 0

    # Persons with quota left, bucketed by home district, compacted lazily by
    # swap removal rather than by rebuilding the list.
    district_live = defaultdict(list)
    for p in persons:
        district_live[p["HomeDistrictID"]].append(p)

    def _has_live_gang_mate(person):
        gid = person["GangID"]
        if not gid:
            return False
        for m in gang_members[gid]:
            if m != person["TruePersonID"] and person_by_id[m]["Remaining"] > 0:
                return True
        return False

    def draw_lead(prefer_gang=False):
        nonlocal lead_cursor, gang_cursor
        if prefer_gang and rng.random() < preset["prefer_gang"]:
            while gang_cursor < len(gang_slots):
                person = person_by_id[gang_slots[gang_cursor]]
                if person["Remaining"] > 0 and _has_live_gang_mate(person):
                    return person
                gang_cursor += 1
        while lead_cursor < len(lead_slots):
            person = person_by_id[lead_slots[lead_cursor]]
            if person["Remaining"] > 0:
                return person
            lead_cursor += 1
        return None

    def draw_local(district_id, exclude, wanted):
        """Persons with quota left in one district, without scanning the pool."""
        bucket = district_live[district_id]
        picked, attempts = [], 0
        while bucket and len(picked) < wanted and attempts < 40:
            attempts += 1
            i = rng.randrange(len(bucket))
            candidate = bucket[i]
            if candidate["Remaining"] <= 0:
                bucket[i] = bucket[-1]
                bucket.pop()
                continue
            if candidate["TruePersonID"] in exclude:
                continue
            if candidate not in picked:
                picked.append(candidate)
        return picked

    def new_case(station, when, family_key, cstype_hint):
        nonlocal case_id, asa_id, complainant_id, victim_id, chargesheet_id
        case_id += 1
        d_id = station["DistrictID"]
        family = R.MO_FAMILIES[family_key]
        category = family["category"]
        key = (station["UnitID"], when.year)
        serial[key] += 1
        crime_no = (f"{category:01d}{int(station['DistrictCode']):04d}"
                    f"{int(station['UnitCode']):04d}{when.year:04d}{serial[key]:05d}")

        lo, hi = family["hours"]
        hour = rng.randrange(lo, hi) % 24
        occurrence_from = when - timedelta(days=rng.choice([0, 0, 0, 1, 1, 2, 3]))
        brief, brief_lang = make_brief_facts(rng, family_key, district_name[d_id])
        subhead = family["subhead"]
        head = next(s[1] for s in R.CRIME_SUBHEADS if s[0] == subhead)

        io = rng.choice(io_by_station[station["UnitID"]])
        case_rows.append({
            "CaseMasterID": case_id,
            "CrimeNo": crime_no,
            "UnitID": station["UnitID"],
            "DistrictID": d_id,
            "CaseCategoryID": category,
            "CrimeHeadID": head,
            "CrimeSubHeadID": subhead,
            "GravityOffenceID": family["gravity"],
            "CrimeRegisteredDate": when.isoformat(),
            "CrimeRegisteredTime": f"{hour:02d}:{rng.randrange(0, 60):02d}",
            "OccurrenceFromDate": occurrence_from.isoformat(),
            "OccurrenceToDate": when.isoformat(),
            "Latitude": jitter(rng, station["Latitude"], 0.08),
            "Longitude": jitter(rng, station["Longitude"], 0.08),
            "PlaceOfOffence": f"{rng.choice(R.PLACE_TYPES)}, {district_name[d_id]}",
            "BriefFacts": brief,
            "IOEmployeeID": io,
            "CaseStatus": "Under Investigation",
            "Active": "Y",
        })

        for act_ref, section_ref in sections_for_case(
                family_key, when, ipc_id, bns_id, other_id, act_by_abbr):
            asa_id += 1
            asa_rows.append({
                "ActSectionAssocID": asa_id, "CaseMasterID": case_id,
                "ActID": act_ref, "SectionID": section_ref,
            })

        # Complainant, always present. Note that this row has an address and a
        # phone number while the Accused row has neither. That asymmetry is
        # faithful to the source schema and it is the direct cause of the gap.
        complainant_id += 1
        g_la, g_kn = pick_weighted(rng, R.GIVEN_NAMES_MALE, male_w) \
            if rng.random() < 0.7 else pick_weighted(rng, R.GIVEN_NAMES_FEMALE, female_w)
        f_la, f_kn = pick_weighted(rng, R.FATHER_NAMES, father_w)
        complainant_rows.append({
            "ComplainantID": complainant_id,
            "CaseMasterID": case_id,
            "ComplainantName": NV.render_plain(
                {"given_la": g_la, "given_kn": g_kn,
                 "father_la": f_la, "father_kn": f_kn}, rng),
            "AgeYear": rng.randint(21, 68),
            "GenderID": rng.choice([1, 1, 2]),
            "Address": f"{rng.choice(R.LOCALITY_STEMS)[0]}, {district_name[d_id]}",
            "PhoneNumber": f"9{rng.randrange(100000000, 999999999)}",
            "RelationToVictim": rng.choice(["Self", "Father", "Husband", "Brother", "Owner"]),
        })

        if head in (1, 3):
            victim_id += 1
            vg_la, vg_kn = pick_weighted(rng, R.GIVEN_NAMES_FEMALE, female_w) \
                if head == 3 else pick_weighted(rng, R.GIVEN_NAMES_MALE, male_w)
            vf_la, vf_kn = pick_weighted(rng, R.FATHER_NAMES, father_w)
            victim_rows.append({
                "VictimID": victim_id,
                "CaseMasterID": case_id,
                "PersonID": "V1",
                "VictimName": NV.render_plain(
                    {"given_la": vg_la, "given_kn": vg_kn,
                     "father_la": vf_la, "father_kn": vf_kn}, rng),
                "AgeYear": rng.randint(16, 72),
                "GenderID": 2 if head == 3 else rng.choice([1, 1, 2]),
                "CasteID": rng.randint(*R.CASTE_ID_RANGE),
                "ReligionID": rng.randint(*R.RELIGION_ID_RANGE),
                "OccupationID": rng.randint(*R.OCCUPATION_ID_RANGE),
                "InjuryType": rng.choice(["Simple", "Grievous", "Fatal", "None"]),
            })

        # Final report classification.
        if cstype_hint == "C":
            cstype = "C"
        else:
            cstype = pick_weighted(rng, ["A", "B", "D", None], [0.78, 0.09, 0.05, 0.08])
        if cstype:
            chargesheet_id += 1
            filed = when + timedelta(days=rng.randint(20, 240))
            chargesheet_rows.append({
                "ChargesheetID": chargesheet_id,
                "CaseMasterID": case_id,
                "cstype": cstype,
                "ChargesheetNo": f"{chargesheet_id:06d}/{filed.year}" if cstype == "A" else None,
                "ChargesheetDate": filed.isoformat() if filed <= CORPUS_END else None,
                "FiledByEmployeeID": io,
                "CourtName": f"{rng.choice(R.COURT_NAMES)}, {district_name[d_id]}"
                             if cstype == "A" else None,
                "Remarks": {
                    "A": "Chargesheet filed against accused.",
                    "B": "Complaint found to be false on investigation.",
                    "C": "Offence true but accused not traced. Filed as undetected.",
                    "D": "Non cognizable. No further action.",
                }[cstype],
            })
            case_rows[-1]["CaseStatus"] = {
                "A": "Chargesheeted", "B": "Closed False",
                "C": "Undetected", "D": "Closed NC",
            }[cstype]

        return case_id, station

    def add_accused(cid, station, person, label, when):
        nonlocal accused_id, arrest_id
        accused_id += 1
        variant = NV.choose_variant(person, rng, script_bias=station["ScriptBias"])
        rendered = NV.render(person, variant, rng)

        # Implied birth year is year(CrimeRegisteredDate) minus AgeYear.
        # Station recorded ages are estimates, so noise is planted here and the
        # plus or minus two tolerance in Layer 3c has to absorb it. The tail
        # beyond two years is deliberate, since it is where the temporal signal
        # genuinely fails and the engine must not pretend otherwise.
        age_noise = pick_weighted(rng, [0, 1, -1, 2, -2, 3, -3, 4, -5],
                                  [0.46, 0.13, 0.13, 0.08, 0.08, 0.045, 0.045, 0.02, 0.01])
        true_age = when.year - person["BirthYear"]
        age = None if rng.random() < 0.04 else max(16, true_age + age_noise)

        accused_rows.append({
            "AccusedMasterID": accused_id,
            "CaseMasterID": cid,
            "PersonID": label,
            "AccusedName": rendered["rendered"],
            "AgeYear": age,
            "GenderID": person["GenderID"],
            "CasteID": person["CasteID"],
            "ReligionID": person["ReligionID"],
            "OccupationID": person["OccupationID"],
            "AccusedType": pick_weighted(rng, ["Known", "Absconding"], [0.9, 0.1]),
            "Nationality": "Indian",
            "Active": "Y",
        })

        arrested = rng.random() < 0.62
        officer = None
        if arrested:
            arrest_id += 1
            affinity_key = (person["TruePersonID"], station["UnitID"])
            previous = officer_affinity.get(affinity_key)
            if previous is not None and rng.random() < OFFICER_AFFINITY:
                officer = previous
            else:
                officer = rng.choice(emp_by_station[station["UnitID"]])
                officer_affinity[affinity_key] = officer
            adate = when + timedelta(days=rng.randint(0, 45))
            arrest_rows.append({
                "ArrestSurrenderID": arrest_id,
                "CaseMasterID": cid,
                "AccusedMasterID": accused_id,
                "ArrestType": pick_weighted(rng, ["Arrest", "Surrender"], [0.88, 0.12]),
                "ArrestDate": adate.isoformat(),
                "ArrestTime": f"{rng.randrange(0, 24):02d}:{rng.randrange(0, 60):02d}",
                "ArrestPlace": rng.choice(R.ARREST_PLACES),
                "ArrestingOfficerID": officer,
                "RemandDate": (adate + timedelta(days=1)).isoformat(),
                "BailFlag": pick_weighted(rng, ["Y", "N"], [0.55, 0.45]),
            })

        identity_map.append({
            "AccusedMasterID": accused_id,
            "CaseMasterID": cid,
            "TruePersonID": person["TruePersonID"],
            "PersonLabel": label,
            "RenderedName": rendered["rendered"],
            "CanonicalName": f"{person['given_la']} {person['father_la']}",
            "Variant": rendered["variant"],
            "Script": rendered["script"],
            "Perturbations": "|".join(rendered["perturbations"]),
            "Noise": "|".join(rendered["noise"]),
            "CarriesFather": "Y" if rendered["carries_father"] else "N",
            "CarriesMoniker": "Y" if rendered["carries_moniker"] else "N",
            "FatherAbbreviated": "Y" if rendered["father_abbreviated"] else "N",
            "AgeRecorded": age if age is not None else "",
            "TrueBirthYear": person["BirthYear"],
            "AgeNoise": age_noise if age is not None else "",
            "DistrictID": station["DistrictID"],
            "UnitID": station["UnitID"],
            "ArrestingOfficerID": officer if officer else "",
            "CrimeRegisteredDate": when.isoformat(),
            "MOFamily": person["MOFamily"],
            "GangID": person["GangID"] or "",
            "CollisionGroup": person["CollisionGroup"] or "",
        })

    # ---- detected cases -------------------------------------------------
    for n_accused in accused_counts:
        lead = draw_lead(prefer_gang=n_accused > 1)
        if lead is None:
            break

        if rng.random() < lead["TravelPropensity"]:
            station = station_by_id[pick_weighted(rng, all_station_ids, all_station_weights)]
        else:
            station = station_by_id[lead["HomeUnitID"]]

        when = random_date(rng, lead["ActiveFrom"], lead["ActiveTo"])
        family_key = lead["MOFamily"] if rng.random() < 0.85 else rng.choice(mo_names)

        cid, station = new_case(station, when, family_key, cstype_hint=None)

        chosen = [lead]
        lead["Remaining"] -= 1

        if n_accused > 1:
            # Gang mates first. Cannot link is respected by construction, since
            # a person is never drawn twice into the same case.
            pool = []
            if lead["GangID"] and rng.random() < preset["gang_fill"]:
                pool = [person_by_id[m] for m in gang_members[lead["GangID"]]
                        if m != lead["TruePersonID"]]
            pool = available(pool)
            rng.shuffle(pool)
            if len(pool) < n_accused - 1:
                pool = pool + draw_local(
                    station["DistrictID"],
                    exclude={lead["TruePersonID"]},
                    wanted=n_accused - 1 - len(pool))
            taken = {lead["TruePersonID"]}
            for candidate in pool:
                if len(chosen) >= n_accused:
                    break
                if candidate["TruePersonID"] in taken:
                    continue
                taken.add(candidate["TruePersonID"])
                chosen.append(candidate)
                candidate["Remaining"] -= 1

        for i, person in enumerate(chosen, start=1):
            add_accused(cid, station, person, f"A{i}", when)

    # ---- undetected cases, cstype C -------------------------------------
    # These carry no Accused rows. Ground truth records who did it, so the
    # Layer 8 candidate ranking has something to be scored against. Only people
    # with three or more appearances are used, since a perpetrator who appears
    # nowhere else is unrecoverable by any method and would only add noise to
    # the measurement.
    resolvable = [p for p in persons if p["Quota"] >= 3]
    for _ in range(n_undetected):
        if not resolvable:
            break
        culprit = rng.choice(resolvable)
        if rng.random() < culprit["TravelPropensity"]:
            station = station_by_id[pick_weighted(rng, all_station_ids, all_station_weights)]
        else:
            station = station_by_id[culprit["HomeUnitID"]]
        when = random_date(rng, culprit["ActiveFrom"], culprit["ActiveTo"])
        family_key = culprit["MOFamily"] if rng.random() < 0.90 else rng.choice(mo_names)
        cid, _ = new_case(station, when, family_key, cstype_hint="C")
        undetected_truth.append({
            "CaseMasterID": cid,
            "TruePersonID": culprit["TruePersonID"],
            "MOFamily": family_key,
            "DistrictID": station["DistrictID"],
            "UnitID": station["UnitID"],
            "CrimeRegisteredDate": when.isoformat(),
            "CulpritAppearances": culprit["Quota"],
        })

    victim_identity, complainant_identity = assign_other_person_identities(
        seed, victim_rows, complainant_rows, district_name)

    gender_noise = apply_gender_noise(
        seed, accused_rows, victim_rows, complainant_rows,
        rate=gender_error_rate)

    return {
        "districts": districts, "units": units, "stations": stations,
        "employees": employees, "acts": acts, "sections": sections,
        "cases": case_rows, "accused": accused_rows, "victims": victim_rows,
        "complainants": complainant_rows, "arrests": arrest_rows,
        "chargesheets": chargesheet_rows, "act_sections": asa_rows,
        "persons": persons, "identity_map": identity_map,
        "undetected_truth": undetected_truth,
        "collisions": collisions, "gangs": gangs,
        "victim_identity": victim_identity,
        "complainant_identity": complainant_identity,
        "gender_noise": gender_noise,
    }


def apply_gender_noise(seed, accused_rows, victim_rows, complainant_rows,
                       rate: float = GENDER_ERROR_RATE):
    """Flip the recorded gender on a small share of rows.

    Runs after the main loop from its own random stream, so every name, case,
    date and age is unchanged and this isolates one field. A before and after
    comparison therefore measures the gender channel and nothing else.

    Only the *recorded* value moves. Ground truth still knows who the person is,
    so a flipped row is a row where the record is wrong about a real person,
    which is exactly the situation the engine has to survive.
    """
    rng = random.Random(seed + GENDER_PASS_SEED_OFFSET)
    flipped = {"accused": 0, "victim": 0, "complainant": 0}

    def flip(rows, key):
        for row in rows:
            current = row.get("GenderID")
            if current in (None, ""):
                continue
            if rng.random() >= rate:
                continue
            row["GenderID"] = 2 if int(current) == 1 else 1
            flipped[key] += 1

    flip(accused_rows, "accused")
    flip(victim_rows, "victim")
    flip(complainant_rows, "complainant")

    total = sum(flipped.values())
    rows = len(accused_rows) + len(victim_rows) + len(complainant_rows)
    return {
        "rate_requested": rate,
        "rows_flipped": flipped,
        "total_flipped": total,
        "total_rows": rows,
        "rate_realised": round(total / rows, 6) if rows else 0.0,
        "note": ("Recorded gender is wrong on these rows. Ground truth is "
                 "unchanged, so the engine sees a field that disagrees with "
                 "itself across a person's appearances, which is what real "
                 "records do and what the corpus previously could not."),
    }


# ---------------------------------------------------------------------------
# Victims and complainants get a person entity too
# ---------------------------------------------------------------------------

# The share of victim and complainant rows that are a person already in the
# record rather than someone new. Repeat victimisation is real and measured:
# the Crime Survey for England and Wales has consistently found a small
# minority of victims accounting for a large share of incidents, and property
# crime against the same shop or household recurs. These are set below the
# accused recurrence rate, because a person who offends repeatedly is by
# definition a repeat visitor to the record and a victim usually is not.
VICTIM_REPEAT_SHARE = 0.18
COMPLAINANT_REPEAT_SHARE = 0.22

# Offset so this draws from its own stream. The main generator's rng is not
# touched by anything below, which is what keeps the accused corpus, and
# therefore the published headline, byte for byte identical to before victims
# and complainants had identities at all.
IDENTITY_PASS_SEED_OFFSET = 90210


def assign_other_person_identities(seed, victim_rows, complainant_rows,
                                   district_name):
    """Give victim and complainant rows a true person identity.

    Runs after the main loop, from its own random stream, and rewrites only the
    name and age on rows that already exist. The row count, the case each row
    belongs to, and every draw the main generator made are unchanged.

    Why this exists. Victim and ComplainantDetails carry exactly the same
    missing person entity as Accused. Neither has a key that survives across
    FIRs. Until now the corpus did not model that, because every victim and
    complainant was an independent draw, so there was no repeat person to find
    and no ground truth to measure against. A resolver run over that would have
    scored near zero precision by construction and measured nothing.

    The asymmetry the schema itself comments on is preserved and is the
    interesting part. A complainant row carries an address and a phone number.
    An accused row carries neither. So the complainant is the easy case and the
    accused is the hard one, and running the same engine over all three is what
    turns that observation into a number.
    """
    rng = random.Random(seed + IDENTITY_PASS_SEED_OFFSET)

    def build(rows, name_field, id_field, repeat_share, prefix):
        pool: list[dict] = []
        mapping = []
        for row in rows:
            reuse = pool and rng.random() < repeat_share
            if reuse:
                # Weighted to the front so a few people recur often, which is
                # how repeat victimisation actually distributes.
                person = pool[int(rng.betavariate(1.0, 2.2) * len(pool))]
            else:
                given_la, given_kn = (
                    pick_weighted(rng, R.GIVEN_NAMES_FEMALE, None)
                    if rng.random() < 0.42
                    else pick_weighted(rng, R.GIVEN_NAMES_MALE, None))
                father_la, father_kn = pick_weighted(rng, R.FATHER_NAMES, None)
                person = {
                    "id": f"{prefix}{len(pool) + 1:06d}",
                    "given_la": given_la, "given_kn": given_kn,
                    "father_la": father_la, "father_kn": father_kn,
                    "moniker_la": None, "moniker_kn": None,
                    "birth_year": rng.randint(1958, 2006),
                    "appearances": 0,
                }
                pool.append(person)

            person["appearances"] += 1
            variant = NV.choose_variant(person, rng)
            rendered = NV.render(person, variant, rng)
            row[name_field] = rendered["rendered"]

            # Age is re-derived from the person's birth year so it is
            # consistent across their appearances, with the same station
            # rounding noise the accused rows carry.
            age = 2026 - person["birth_year"] + rng.choice(
                [0, 0, 0, 0, -1, 1, -2, 2, 5, -5])
            row["AgeYear"] = max(16, age)

            mapping.append({
                id_field: row[id_field],
                "CaseMasterID": row["CaseMasterID"],
                "TruePersonID": person["id"],
                "RenderedName": rendered["rendered"],
                "CanonicalName": f"{person['given_la']} {person['father_la']}",
                "Variant": variant,
                "Script": NV.script_of_string(rendered["rendered"]),
                "AgeRecorded": row["AgeYear"],
                "TrueBirthYear": person["birth_year"],
            })
        return pool, mapping

    _, victim_map = build(victim_rows, "VictimName", "VictimID",
                          VICTIM_REPEAT_SHARE, "V")
    _, complainant_map = build(complainant_rows, "ComplainantName",
                               "ComplainantID", COMPLAINANT_REPEAT_SHARE, "C")

    # The complainant's address and phone belong to the person, not to the
    # filing, so a repeat complainant carries the same ones. That is precisely
    # the signal the accused row does not have, and it is why this table is the
    # easy case.
    contact: dict[str, tuple[str, str]] = {}
    by_complainant = {m["ComplainantID"]: m for m in complainant_map}
    for row in complainant_rows:
        person = by_complainant[row["ComplainantID"]]["TruePersonID"]
        if person not in contact:
            contact[person] = (row["Address"], row["PhoneNumber"])
        row["Address"], row["PhoneNumber"] = contact[person]

    return victim_map, complainant_map


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

def write_csv(path: Path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: ("" if row.get(k) is None else row.get(k))
                             for k in fieldnames})


def write_corpus(corpus, out_dir: Path):
    gt = out_dir / "ground_truth"

    write_csv(out_dir / "State.csv", [R.STATE],
              ["StateID", "StateName", "StateNameKn", "StateCode"])
    write_csv(out_dir / "District.csv", corpus["districts"],
              ["DistrictID", "StateID", "DistrictName", "DistrictNameKn",
               "DistrictCode", "Latitude", "Longitude", "Active"])
    write_csv(out_dir / "UnitType.csv",
              [{"UnitTypeID": u[0], "UnitTypeName": u[1], "HierarchyLevel": u[2]}
               for u in R.UNIT_TYPES],
              ["UnitTypeID", "UnitTypeName", "HierarchyLevel"])
    write_csv(out_dir / "Unit.csv", corpus["units"],
              ["UnitID", "UnitTypeID", "DistrictID", "ParentUnitID", "UnitName",
               "UnitNameKn", "UnitCode", "Latitude", "Longitude", "Active"])
    write_csv(out_dir / "Rank.csv",
              [{"RankID": r[0], "RankName": r[1], "RankAbbr": r[2],
                "SeniorityOrder": r[3]} for r in R.RANKS],
              ["RankID", "RankName", "RankAbbr", "SeniorityOrder"])
    write_csv(out_dir / "Designation.csv",
              [{"DesignationID": d[0], "DesignationName": d[1], "RankID": d[2]}
               for d in R.DESIGNATIONS],
              ["DesignationID", "DesignationName", "RankID"])
    write_csv(out_dir / "Employee.csv", corpus["employees"],
              ["EmployeeID", "EmployeeName", "EmployeeNameKn", "RankID",
               "DesignationID", "UnitID", "BuckleNo", "Active"])
    write_csv(out_dir / "CaseCategory.csv",
              [{"CaseCategoryID": c[0], "CaseCategoryName": c[1]}
               for c in R.CASE_CATEGORIES],
              ["CaseCategoryID", "CaseCategoryName"])
    write_csv(out_dir / "GravityOffence.csv",
              [{"GravityOffenceID": g[0], "GravityName": g[1], "GravityRank": g[2]}
               for g in R.GRAVITY],
              ["GravityOffenceID", "GravityName", "GravityRank"])
    write_csv(out_dir / "CrimeHead.csv",
              [{"CrimeHeadID": c[0], "CrimeHeadName": c[1], "CrimeHeadNameKn": c[2]}
               for c in R.CRIME_HEADS],
              ["CrimeHeadID", "CrimeHeadName", "CrimeHeadNameKn"])
    write_csv(out_dir / "CrimeSubHead.csv",
              [{"CrimeSubHeadID": c[0], "CrimeHeadID": c[1],
                "CrimeSubHeadName": c[2], "CrimeSubHeadNameKn": c[3]}
               for c in R.CRIME_SUBHEADS],
              ["CrimeSubHeadID", "CrimeHeadID", "CrimeSubHeadName", "CrimeSubHeadNameKn"])
    write_csv(out_dir / "Act.csv", corpus["acts"],
              ["ActID", "ActName", "ActAbbr", "ActYear", "EffectiveFrom",
               "EffectiveTo", "Active"])
    write_csv(out_dir / "Section.csv", corpus["sections"],
              ["SectionID", "ActID", "SectionNo", "SectionDesc", "SectionDescKn",
               "GravityOffenceID", "IsCognizable", "IsBailable",
               "SuccessorSectionID", "Active"])
    write_csv(out_dir / "CaseMaster.csv", corpus["cases"],
              ["CaseMasterID", "CrimeNo", "UnitID", "DistrictID", "CaseCategoryID",
               "CrimeHeadID", "CrimeSubHeadID", "GravityOffenceID",
               "CrimeRegisteredDate", "CrimeRegisteredTime", "OccurrenceFromDate",
               "OccurrenceToDate", "Latitude", "Longitude", "PlaceOfOffence",
               "BriefFacts", "IOEmployeeID", "CaseStatus", "Active"])
    write_csv(out_dir / "ActSectionAssociation.csv", corpus["act_sections"],
              ["ActSectionAssocID", "CaseMasterID", "ActID", "SectionID"])
    write_csv(out_dir / "Accused.csv", corpus["accused"],
              ["AccusedMasterID", "CaseMasterID", "PersonID", "AccusedName",
               "AgeYear", "GenderID", "CasteID", "ReligionID", "OccupationID",
               "AccusedType", "Nationality", "Active"])
    write_csv(out_dir / "Victim.csv", corpus["victims"],
              ["VictimID", "CaseMasterID", "PersonID", "VictimName", "AgeYear",
               "GenderID", "CasteID", "ReligionID", "OccupationID", "InjuryType"])
    write_csv(out_dir / "ComplainantDetails.csv", corpus["complainants"],
              ["ComplainantID", "CaseMasterID", "ComplainantName", "AgeYear",
               "GenderID", "Address", "PhoneNumber", "RelationToVictim"])
    write_csv(out_dir / "ArrestSurrender.csv", corpus["arrests"],
              ["ArrestSurrenderID", "CaseMasterID", "AccusedMasterID", "ArrestType",
               "ArrestDate", "ArrestTime", "ArrestPlace", "ArrestingOfficerID",
               "RemandDate", "BailFlag"])
    write_csv(out_dir / "ChargesheetDetails.csv", corpus["chargesheets"],
              ["ChargesheetID", "CaseMasterID", "cstype", "ChargesheetNo",
               "ChargesheetDate", "FiledByEmployeeID", "CourtName", "Remarks"])

    # Ground truth. Never joined by the engine. Read only by eval.
    write_csv(gt / "persons.csv",
              [{**p,
                "ActiveFrom": p["ActiveFrom"].isoformat(),
                "ActiveTo": p["ActiveTo"].isoformat(),
                "CanonicalName": f"{p['given_la']} {p['father_la']}",
                "CanonicalNameKn": f"{p['given_kn']} {p['father_kn']}",
                "Moniker": p["moniker_la"] or "",
                "GangID": p["GangID"] or "",
                "CollisionGroup": p["CollisionGroup"] or ""}
               for p in corpus["persons"]],
              ["TruePersonID", "CanonicalName", "CanonicalNameKn", "Moniker",
               "GenderID", "BirthYear", "HomeDistrictID", "HomeUnitID", "MOFamily",
               "TravelPropensity", "Quota", "ActiveFrom", "ActiveTo",
               "GangID", "CollisionGroup"])
    write_csv(gt / "identity_map.csv", corpus["identity_map"],
              ["AccusedMasterID", "CaseMasterID", "TruePersonID", "PersonLabel",
               "RenderedName", "CanonicalName", "Variant", "Script",
               "Perturbations", "Noise", "CarriesFather", "CarriesMoniker",
               "FatherAbbreviated", "AgeRecorded", "TrueBirthYear", "AgeNoise",
               "DistrictID", "UnitID", "ArrestingOfficerID",
               "CrimeRegisteredDate", "MOFamily", "GangID", "CollisionGroup"])
    write_csv(gt / "undetected_truth.csv", corpus["undetected_truth"],
              ["CaseMasterID", "TruePersonID", "MOFamily", "DistrictID", "UnitID",
               "CrimeRegisteredDate", "CulpritAppearances"])

    # Victim and ComplainantDetails carry the same missing person entity as
    # Accused. Until these maps existed there was no ground truth for either,
    # so a resolver run over them measured nothing. See ADR 024.
    write_csv(gt / "victim_identity_map.csv", corpus["victim_identity"],
              ["VictimID", "CaseMasterID", "TruePersonID", "RenderedName",
               "CanonicalName", "Variant", "Script", "AgeRecorded",
               "TrueBirthYear"])
    write_csv(gt / "complainant_identity_map.csv", corpus["complainant_identity"],
              ["ComplainantID", "CaseMasterID", "TruePersonID", "RenderedName",
               "CanonicalName", "Variant", "Script", "AgeRecorded",
               "TrueBirthYear"])
    write_csv(gt / "name_collisions.csv",
              [{"CollisionGroup": c["CollisionGroup"],
                "CanonicalName": c["CanonicalName"],
                "DistrictID": c["DistrictID"],
                "TightAge": "Y" if c["TightAge"] else "N",
                "MemberCount": len(c["Members"]),
                "Members": "|".join(c["Members"])} for c in corpus["collisions"]],
              ["CollisionGroup", "CanonicalName", "DistrictID", "TightAge",
               "MemberCount", "Members"])
    write_csv(gt / "gangs.csv",
              [{"GangID": g["GangID"], "DistrictID": g["DistrictID"],
                "MemberCount": len(g["Members"]),
                "Members": "|".join(g["Members"])} for g in corpus["gangs"]],
              ["GangID", "DistrictID", "MemberCount", "Members"])


def dyad_recurrence(corpus):
    """Share of co offending dyads that appear together in more than one case.

    This is the quantity the criminological literature actually reports, so it
    is the one the generator has to be calibrated against. See ADR 012.
    """
    by_case = defaultdict(set)
    for row in corpus["identity_map"]:
        by_case[row["CaseMasterID"]].add(row["TruePersonID"])
    dyads = Counter()
    for people in by_case.values():
        for pair in combinations(sorted(people), 2):
            dyads[pair] += 1
    if not dyads:
        return {"dyads": 0, "recurring": 0, "rate_pct": 0.0}
    recurring = sum(1 for v in dyads.values() if v > 1)
    return {
        "dyads": len(dyads),
        "recurring": recurring,
        "rate_pct": round(100.0 * recurring / len(dyads), 3),
        "max_repeats": max(dyads.values()),
    }


def write_manifest(corpus, out_dir: Path, n_cases: int,
                   co_offending: str = DEFAULT_CO_OFFENDING,
                   name_vocabulary: int = R.BASE_VOCABULARY):
    appearances = Counter(r["TruePersonID"] for r in corpus["identity_map"])
    manifest = {
        "generator": "sutra.data.generator",
        "seed": SEED,
        "gender_noise": corpus.get("gender_noise"),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "co_offending_preset": co_offending,
        "co_offending_parameters": CO_OFFENDING_PRESETS[co_offending],
        "name_vocabulary": name_vocabulary,
        "dyad_recurrence": dyad_recurrence(corpus),
        "corpus_start": CORPUS_START.isoformat(),
        "corpus_end": CORPUS_END.isoformat(),
        "bns_transition": TRANSITION.isoformat(),
        "requested_cases": n_cases,
        "counts": {
            "districts": len(corpus["districts"]),
            "units": len(corpus["units"]),
            "police_stations": len(corpus["stations"]),
            "employees": len(corpus["employees"]),
            "acts": len(corpus["acts"]),
            "sections": len(corpus["sections"]),
            "cases": len(corpus["cases"]),
            "accused_rows": len(corpus["accused"]),
            "victims": len(corpus["victims"]),
            "complainants": len(corpus["complainants"]),
            "arrests": len(corpus["arrests"]),
            "chargesheets": len(corpus["chargesheets"]),
            "act_section_links": len(corpus["act_sections"]),
            "true_persons": len(corpus["persons"]),
            "true_persons_appearing": len(appearances),
            "undetected_cases": len(corpus["undetected_truth"]),
            "collision_groups": len(corpus["collisions"]),
            "gangs": len(corpus["gangs"]),
        },
        "excluded_from_features": ["CasteID", "ReligionID", "OccupationID"],
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate the synthetic KSP FIR corpus.")
    parser.add_argument("--cases", type=int, default=5000,
                        help="5000 is the fast development default. "
                             "150000 is the full corpus, see the Makefile.")
    parser.add_argument("--out", type=Path,
                        default=Path(__file__).resolve().parents[2] / "data" / "corpus")
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--gender-error-rate", type=float,
                        default=GENDER_ERROR_RATE,
                        help="share of rows with a wrong recorded gender, ADR 030")
    parser.add_argument("--name-pool", type=int, default=None,
                        help="target distinct given plus patronymic forms. "
                             "Default keeps the fixture pool of 86.")
    parser.add_argument("--co-offending", default=DEFAULT_CO_OFFENDING,
                        choices=sorted(CO_OFFENDING_PRESETS),
                        help="co offending density preset, see ADR 012")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    corpus = build_corpus(rng, args.cases, co_offending=args.co_offending,
                          name_pool=args.name_pool, seed=args.seed,
                          gender_error_rate=args.gender_error_rate)
    _, _, vocabulary = name_pools(args.name_pool)
    write_corpus(corpus, args.out)
    manifest = write_manifest(corpus, args.out, args.cases,
                              co_offending=args.co_offending)

    print(f"corpus written to {args.out}")
    print(f"  co offending preset      {args.co_offending}")
    print(f"  name vocabulary          {vocabulary:>7,} given plus patronymic forms")
    dr = manifest["dyad_recurrence"]
    print(f"  dyad recurrence rate     {dr['rate_pct']:>7.2f}%"
          f"  ({dr['recurring']:,} of {dr['dyads']:,} dyads)")
    for key, value in manifest["counts"].items():
        print(f"  {key:<24} {value:>8,}")
    print("\nRun the audit for corpus statistics and the recoverability check:")
    print("  python -m data.generator.audit")


if __name__ == "__main__":
    main()
