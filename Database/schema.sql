CREATE TABLE user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    email TEXT UNIQUE,
    password_hash TEXT,
    target_focus_min INTEGER,
    target_break_min INTEGER,
    daily_screen_limit_min INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE session (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    start_time TEXT,
    end_time TEXT,
    duration_minutes INTEGER,
    presence_ratio REAL,
    status TEXT,
    FOREIGN KEY (user_id) REFERENCES user (id)
);

CREATE TABLE alert (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    timestamp TEXT,
    alert_type TEXT,
    actuator_triggered TEXT,
    acknowledged INTEGER DEFAULT 0,
    FOREIGN KEY (session_id) REFERENCES session (id)
);

CREATE TABLE sensor_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    timestamp TEXT,
    pressure_detected INTEGER,
    motion_detected INTEGER,
    FOREIGN KEY (session_id) REFERENCES session (id)
);