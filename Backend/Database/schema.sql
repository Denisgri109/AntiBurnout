CREATE TABLE user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    email TEXT UNIQUE,
    password_hash TEXT,
    target_focus_min INTEGER DEFAULT 25,
    target_break_min INTEGER DEFAULT 5,
    daily_screen_limit_min INTEGER DEFAULT 480,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE session (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    start_time TEXT DEFAULT CURRENT_TIMESTAMP,
    end_time TEXT,
    duration_minutes INTEGER DEFAULT 0,
    presence_ratio REAL DEFAULT 0.0,
    status TEXT DEFAULT 'ACTIVE',
    FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE
);

CREATE TABLE alert (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    alert_type TEXT,
    actuator_triggered TEXT,
    acknowledged INTEGER DEFAULT 0,
    FOREIGN KEY (session_id) REFERENCES session (id) ON DELETE CASCADE
);

CREATE TABLE sensor_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    pressure_detected INTEGER DEFAULT 0,
    motion_detected INTEGER DEFAULT 0,
    FOREIGN KEY (session_id) REFERENCES session (id) ON DELETE CASCADE
);