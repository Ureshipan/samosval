PRAGMA foreign_keys = ON;

-- Users
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    is_active INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

-- Image requests
CREATE TABLE IF NOT EXISTS image_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_name TEXT NOT NULL,
    repo_url TEXT NOT NULL,
    repo_branch TEXT NOT NULL,
    update_mode TEXT NOT NULL,
    target_commit TEXT,
    base_image TEXT NOT NULL,
    run_commands TEXT,
    entrypoint TEXT,
    dockerfile_content TEXT,
    ram_mb INTEGER NOT NULL,
    vcpu REAL NOT NULL,
    version_tag TEXT NOT NULL,
    owner_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    collaborators TEXT,
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (owner_id) REFERENCES users (id),
    FOREIGN KEY (created_by) REFERENCES users (id)
);

-- Images
CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    image_tag TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (request_id) REFERENCES image_requests (id)
);

-- Builds
CREATE TABLE IF NOT EXISTS builds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL,
    image_id INTEGER,
    status TEXT NOT NULL,
    build_log TEXT,
    error_message TEXT,
    built_by INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (request_id) REFERENCES image_requests (id),
    FOREIGN KEY (image_id) REFERENCES images (id),
    FOREIGN KEY (built_by) REFERENCES users (id)
);

-- Deployments
CREATE TABLE IF NOT EXISTS deployments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    environment TEXT NOT NULL,
    status TEXT NOT NULL,
    replicas INTEGER NOT NULL,
    ports TEXT,
    stopped_by_operator INTEGER NOT NULL,
    needs_restart INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (image_id) REFERENCES images (id)
);

-- Alerts
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_type TEXT NOT NULL,
    target_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    resolved INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

-- Audit log
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,
    target_id INTEGER,
    details TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id)
);


