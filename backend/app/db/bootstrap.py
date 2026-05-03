"""会话与消息表初始化（Phase 3）及医药营销演示星型模型（Phase 5）。"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from app.db import sqlite

DDL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '新会话',
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    sql_text TEXT,
    assistant_meta TEXT,
    created_at INTEGER NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, created_at);
"""

# 医药营销：日历 / 地理 / 医院 / 组织与人 / SKU / 销量事实 / 目标（适中数据量，便于 NL2SQL 与 LIMIT）
PHARMA_DDL = """
CREATE TABLE IF NOT EXISTS dim_cal_dt (
    date_key INTEGER PRIMARY KEY,
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    month INTEGER NOT NULL,
    day INTEGER NOT NULL,
    year_month TEXT NOT NULL,
    iso_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_geo (
    geo_id INTEGER PRIMARY KEY AUTOINCREMENT,
    province_name TEXT NOT NULL,
    city_name TEXT NOT NULL,
    district_name TEXT NOT NULL,
    region_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_hospital (
    hospital_id INTEGER PRIMARY KEY AUTOINCREMENT,
    hospital_name TEXT NOT NULL,
    hospital_level TEXT,
    geo_id INTEGER NOT NULL REFERENCES dim_geo(geo_id),
    status TEXT NOT NULL DEFAULT 'ACTIVE'
);

CREATE TABLE IF NOT EXISTS dim_org_unit (
    org_unit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    org_unit_name TEXT NOT NULL,
    org_level_code TEXT NOT NULL,
    parent_org_unit_id INTEGER REFERENCES dim_org_unit(org_unit_id),
    root_region_org_unit_id INTEGER REFERENCES dim_org_unit(org_unit_id),
    sort_order INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS dim_person (
    person_id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_code TEXT NOT NULL UNIQUE,
    person_name TEXT NOT NULL,
    position_code TEXT NOT NULL,
    org_unit_id INTEGER NOT NULL REFERENCES dim_org_unit(org_unit_id)
);

CREATE TABLE IF NOT EXISTS dim_product_sku (
    sku_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku_code TEXT NOT NULL UNIQUE,
    sku_name TEXT NOT NULL,
    unit_of_measure TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS fact_pharma_sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date_key INTEGER NOT NULL REFERENCES dim_cal_dt(date_key),
    hospital_id INTEGER NOT NULL REFERENCES dim_hospital(hospital_id),
    sku_id INTEGER NOT NULL REFERENCES dim_product_sku(sku_id),
    rep_person_id INTEGER NOT NULL REFERENCES dim_person(person_id),
    qty REAL NOT NULL,
    amount REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fps_date ON fact_pharma_sales(date_key);
CREATE INDEX IF NOT EXISTS idx_fps_hospital ON fact_pharma_sales(hospital_id);
CREATE INDEX IF NOT EXISTS idx_fps_sku ON fact_pharma_sales(sku_id);
CREATE INDEX IF NOT EXISTS idx_fps_rep ON fact_pharma_sales(rep_person_id);

CREATE TABLE IF NOT EXISTS fact_pharma_target (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_type TEXT NOT NULL,
    period_key TEXT NOT NULL,
    org_unit_id INTEGER NOT NULL REFERENCES dim_org_unit(org_unit_id),
    sku_id INTEGER NOT NULL REFERENCES dim_product_sku(sku_id),
    target_amount REAL NOT NULL,
    UNIQUE(period_type, period_key, org_unit_id, sku_id)
);
"""


def _ymd_to_date_key(d: date) -> int:
    return d.year * 10000 + d.month * 100 + d.day


def _seed_calendar(conn: sqlite3.Connection) -> None:
    start = date(2026, 1, 1)
    end = date(2026, 3, 31)
    cur = start
    rows: list[tuple[int, int, int, int, int, str, str]] = []
    while cur <= end:
        dk = _ymd_to_date_key(cur)
        q = (cur.month - 1) // 3 + 1
        ym = f"{cur.year}{cur.month:02d}"
        iso = cur.isoformat()
        rows.append((dk, cur.year, q, cur.month, cur.day, ym, iso))
        cur += timedelta(days=1)
    conn.executemany(
        """INSERT OR IGNORE INTO dim_cal_dt
        (date_key, year, quarter, month, day, year_month, iso_date) VALUES (?,?,?,?,?,?,?)""",
        rows,
    )


def _fill_org_root_regions(conn: sqlite3.Connection) -> None:
    units = conn.execute(
        "SELECT org_unit_id, parent_org_unit_id, org_level_code FROM dim_org_unit"
    ).fetchall()
    info = {r[0]: (r[1], r[2]) for r in units}

    def root_region(oid: int) -> int | None:
        seen = oid
        for _ in range(64):
            row = info.get(seen)
            if row is None:
                return None
            parent, lvl = row
            if lvl == "REGION":
                return seen
            if parent is None:
                return None
            seen = parent
        return None

    for oid in info:
        rid = root_region(oid)
        conn.execute(
            "UPDATE dim_org_unit SET root_region_org_unit_id = ? WHERE org_unit_id = ?",
            (rid, oid),
        )


def _seed_pharma_demo(conn: sqlite3.Connection) -> None:
    n_geo = conn.execute("SELECT COUNT(1) FROM dim_geo").fetchone()[0]
    if int(n_geo) > 0:
        return

    geos = [
        ("上海市", "上海市", "浦东新区", "华东"),
        ("上海市", "上海市", "黄浦区", "华东"),
        ("江苏省", "南京市", "鼓楼区", "华东"),
        ("江苏省", "苏州市", "姑苏区", "华东"),
        ("浙江省", "杭州市", "西湖区", "华东"),
        ("广东省", "广州市", "天河区", "华南"),
        ("广东省", "深圳市", "南山区", "华南"),
        ("四川省", "成都市", "武侯区", "华南"),
    ]
    conn.executemany(
        "INSERT INTO dim_geo (province_name, city_name, district_name, region_name) VALUES (?,?,?,?)",
        geos,
    )
    geo_rows = conn.execute("SELECT geo_id FROM dim_geo ORDER BY geo_id").fetchall()
    geo_ids = [r[0] for r in geo_rows]

    hospitals = [
        ("华山医院·浦东院区", "三甲", geo_ids[0]),
        ("瑞金医院", "三甲", geo_ids[1]),
        ("鼓楼医院", "三甲", geo_ids[2]),
        ("苏大附一院", "三甲", geo_ids[3]),
        ("浙一医院", "三甲", geo_ids[4]),
        ("中山一院", "三甲", geo_ids[5]),
        ("深圳人民医院", "三甲", geo_ids[6]),
        ("华西医院", "三甲", geo_ids[7]),
        ("华山医院·虹桥院区", "三甲", geo_ids[0]),
        ("社区医院·浦东", "一级", geo_ids[0]),
        ("社区医院·姑苏", "一级", geo_ids[3]),
        ("天河中医院", "二甲", geo_ids[5]),
        ("南山妇幼保健院", "二甲", geo_ids[6]),
        ("成都军区总医院", "三甲", geo_ids[7]),
        ("浙江省肿瘤医院", "三甲", geo_ids[4]),
    ]
    conn.executemany(
        """INSERT INTO dim_hospital (hospital_name, hospital_level, geo_id, status)
        VALUES (?,?,?, 'ACTIVE')""",
        hospitals,
    )

    # 组织：全国 -> 华东大区 / 华南大区 -> 片区 -> 地区 -> 小组；附 region root 用于上卷
    org_sql = """
    INSERT INTO dim_org_unit (org_unit_name, org_level_code, parent_org_unit_id, sort_order) VALUES (?,?,?,?)
    """
    conn.execute(org_sql, ("总部·心血管BU", "BU", None, 1))
    bu_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    conn.execute(org_sql, ("华东大区", "REGION", bu_id, 10))
    east = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(org_sql, ("华南大区", "REGION", bu_id, 20))
    south = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def ins_child(name: str, level: str, parent: int, order: int) -> int:
        conn.execute(org_sql, (name, level, parent, order))
        return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])

    sh_area = ins_child("上海片区", "AREA", east, 1)
    js_area = ins_child("江苏片区", "AREA", east, 2)
    zj_area = ins_child("浙江片区", "AREA", east, 3)
    gd_area = ins_child("粤东片区", "AREA", south, 1)
    sc_area = ins_child("川渝片区", "AREA", south, 2)

    sh_dist = ins_child("上海浦东地区", "DISTRICT", sh_area, 1)
    js_dist = ins_child("南京苏州联防", "DISTRICT", js_area, 1)
    zj_dist = ins_child("杭嘉湖地区", "DISTRICT", zj_area, 1)
    gd_sz = ins_child("广深联防", "DISTRICT", gd_area, 1)
    sc_cd = ins_child("成都地区", "DISTRICT", sc_area, 1)

    # 小组挂在地区下
    t_sh = ins_child("浦东一组", "TEAM", sh_dist, 1)
    t_js = ins_child("宁苏二组", "TEAM", js_dist, 1)
    t_zj = ins_child("杭州一组", "TEAM", zj_dist, 1)
    t_gd = ins_child("广深一组", "TEAM", gd_sz, 1)
    t_sc = ins_child("成都一组", "TEAM", sc_cd, 1)

    _fill_org_root_regions(conn)

    people = [
        ("E001", "张伟", "REGION_MGR", east),
        ("E002", "李娜", "REGION_MGR", south),
        ("E010", "王强", "AREA_MGR", sh_area),
        ("E011", "赵敏", "AREA_MGR", gd_area),
        ("E020", "刘洋", "REP", t_sh),
        ("E021", "陈晨", "REP", t_sh),
        ("E022", "周杰", "REP", t_js),
        ("E023", "吴倩", "REP", t_zj),
        ("E024", "郑凯", "REP", t_gd),
        ("E025", "孙悦", "REP", t_sc),
    ]
    conn.executemany(
        """INSERT INTO dim_person (employee_code, person_name, position_code, org_unit_id)
        VALUES (?,?,?,?)""",
        people,
    )

    skus = [
        ("SKU-A01", "卡韦缓释片 10mg×28", "盒"),
        ("SKU-A02", "卡韦缓释片 5mg×28", "盒"),
        ("SKU-B01", "立普妥对标药 20mg×7", "盒"),
        ("SKU-C01", "抗生素胶囊 0.25g×24", "盒"),
        ("SKU-D01", "胰岛素笔芯 3ml×5", "支"),
        ("SKU-E01", "降压复方片 30片", "盒"),
    ]
    conn.executemany(
        """INSERT INTO dim_product_sku (sku_code, sku_name, unit_of_measure, is_active)
        VALUES (?,?,?,1)""",
        skus,
    )

    hid_rows = conn.execute(
        "SELECT hospital_id FROM dim_hospital ORDER BY hospital_id"
    ).fetchall()
    hids = [r[0] for r in hid_rows]
    sku_rows = conn.execute("SELECT sku_id FROM dim_product_sku ORDER BY sku_id").fetchall()
    sids = [r[0] for r in sku_rows]
    rep_rows = conn.execute(
        "SELECT person_id FROM dim_person WHERE position_code = 'REP' ORDER BY person_id"
    ).fetchall()
    rids = [r[0] for r in rep_rows]

    date_rows = conn.execute(
        "SELECT date_key FROM dim_cal_dt ORDER BY date_key"
    ).fetchall()
    dkeys = [r[0] for r in date_rows]

    # ~900 行：每日若干笔，确定性分配避免随机模块
    sales_rows: list[tuple[int, int, int, int, float, float]] = []
    salt = 0
    for dk in dkeys:
        for k in range(10):
            h = hids[(salt + k * 3) % len(hids)]
            s = sids[(salt + k) % len(sids)]
            r = rids[(salt + k * 2) % len(rids)]
            qty = float(5 + (salt % 12) + k)
            amount = round(qty * (180.0 + (salt % 7) * 10 + k * 5), 2)
            sales_rows.append((dk, h, s, r, qty, amount))
            salt += 1

    conn.executemany(
        """INSERT INTO fact_pharma_sales (date_key, hospital_id, sku_id, rep_person_id, qty, amount)
        VALUES (?,?,?,?,?,?)""",
        sales_rows,
    )

    # 月度目标：大区 × SKU，202601–202603
    targets: list[tuple[str, str, int, int, float]] = []
    for ym in ("202601", "202602", "202603"):
        for reg in (east, south):
            for sid in sids:
                targets.append(
                    (
                        "MONTH",
                        ym,
                        reg,
                        sid,
                        float(120_000 + (sid * 7_000) + int(ym[-1]) * 3_000),
                    )
                )
    conn.executemany(
        """INSERT INTO fact_pharma_target
        (period_type, period_key, org_unit_id, sku_id, target_amount) VALUES (?,?,?,?,?)""",
        targets,
    )


def _create_views(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP VIEW IF EXISTS v_pharma_sales_enriched;
        CREATE VIEW v_pharma_sales_enriched AS
        SELECT
            s.id AS sale_id,
            s.date_key,
            cal.year AS cal_year,
            cal.quarter AS cal_quarter,
            cal.month AS cal_month,
            cal.day AS cal_day,
            cal.year_month,
            cal.iso_date AS sale_iso_date,
            g.region_name AS sales_region,
            g.province_name,
            g.city_name,
            g.district_name,
            h.hospital_name,
            h.hospital_level,
            sk.sku_code,
            sk.sku_name AS product_name,
            sk.unit_of_measure,
            rep.person_name AS rep_name,
            rep.employee_code AS rep_code,
            rep.position_code AS rep_position,
            reg.org_unit_name AS big_region_name,
            ou.org_unit_name AS rep_org_unit_name,
            ou.org_level_code AS rep_org_level,
            s.qty,
            s.amount
        FROM fact_pharma_sales s
        JOIN dim_cal_dt cal ON s.date_key = cal.date_key
        JOIN dim_hospital h ON s.hospital_id = h.hospital_id
        JOIN dim_geo g ON h.geo_id = g.geo_id
        JOIN dim_product_sku sk ON s.sku_id = sk.sku_id
        JOIN dim_person rep ON s.rep_person_id = rep.person_id
        JOIN dim_org_unit ou ON rep.org_unit_id = ou.org_unit_id
        JOIN dim_org_unit reg ON ou.root_region_org_unit_id = reg.org_unit_id;

        DROP VIEW IF EXISTS sales_fact;
        CREATE VIEW sales_fact AS
        SELECT
            s.id AS id,
            sk.sku_name AS product_name,
            g.region_name AS region,
            cal.iso_date AS sale_date,
            s.amount AS amount
        FROM fact_pharma_sales s
        JOIN dim_cal_dt cal ON s.date_key = cal.date_key
        JOIN dim_hospital h ON s.hospital_id = h.hospital_id
        JOIN dim_geo g ON h.geo_id = g.geo_id
        JOIN dim_product_sku sk ON s.sku_id = sk.sku_id;
        """
    )


def init_db() -> None:
    sqlite.ensure_parent_dir_exists()
    conn = sqlite.connect()
    try:
        conn.executescript(DDL)
        conn.executescript(PHARMA_DDL)
        # 旧版宽表或同名视图：先 drop view 再 drop table，避免二次启动报「应使用 DROP VIEW」
        conn.execute("DROP VIEW IF EXISTS sales_fact")
        conn.execute("DROP TABLE IF EXISTS sales_fact")
        _seed_calendar(conn)
        _seed_pharma_demo(conn)
        _create_views(conn)
        conn.commit()
    finally:
        conn.close()
