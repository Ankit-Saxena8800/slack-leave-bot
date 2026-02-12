-- Slack Leave Bot Analytics Database Schema
-- SQLite database for tracking leave events, reminders, and compliance metrics

-- Leave events tracking table
-- Records all leave/WFH mentions detected in Slack messages
CREATE TABLE IF NOT EXISTS leave_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    user_id TEXT NOT NULL,
    user_email TEXT NOT NULL,
    user_name TEXT NOT NULL,
    event_type TEXT NOT NULL,  -- 'leave_mentioned', 'wfh_mentioned'
    message_ts TEXT NOT NULL UNIQUE,  -- Slack message timestamp (unique identifier)
    leave_dates TEXT,  -- JSON array of leave dates
    zoho_applied BOOLEAN,  -- Whether leave was found in Zoho
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Reminder events tracking table
-- Records all reminders sent and their outcomes
CREATE TABLE IF NOT EXISTS reminder_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    user_id TEXT NOT NULL,
    user_email TEXT,
    reminder_type TEXT NOT NULL,  -- 'first', 'followup_12hr', 'second_escalation', 'urgent', 'resolved'
    message_ts TEXT NOT NULL,  -- Original message timestamp
    action_taken TEXT,  -- 'thread_reply', 'dm_sent', 'admin_notified'
    reminder_level INTEGER DEFAULT 0,  -- 0=initial, 1=first_followup, 2=second_escalation, 3=urgent
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Daily aggregates for performance
-- Pre-computed metrics for faster dashboard queries
CREATE TABLE IF NOT EXISTS daily_aggregates (
    date DATE PRIMARY KEY,
    total_leaves INTEGER DEFAULT 0,
    compliant_count INTEGER DEFAULT 0,
    non_compliant_count INTEGER DEFAULT 0,
    reminders_sent INTEGER DEFAULT 0,
    compliance_rate REAL,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_leave_timestamp ON leave_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_leave_user_email ON leave_events(user_email);
CREATE INDEX IF NOT EXISTS idx_leave_user_id ON leave_events(user_id);
CREATE INDEX IF NOT EXISTS idx_leave_event_type ON leave_events(event_type);
CREATE INDEX IF NOT EXISTS idx_leave_created_at ON leave_events(created_at);

CREATE INDEX IF NOT EXISTS idx_reminder_timestamp ON reminder_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_reminder_user_id ON reminder_events(user_id);
CREATE INDEX IF NOT EXISTS idx_reminder_type ON reminder_events(reminder_type);
CREATE INDEX IF NOT EXISTS idx_reminder_message_ts ON reminder_events(message_ts);
CREATE INDEX IF NOT EXISTS idx_reminder_created_at ON reminder_events(created_at);

CREATE INDEX IF NOT EXISTS idx_daily_date ON daily_aggregates(date);
