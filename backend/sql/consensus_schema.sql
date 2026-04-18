CREATE TABLE IF NOT EXISTS consensus_tasks (
  id BIGINT NOT NULL AUTO_INCREMENT,
  question TEXT NOT NULL,
  threshold_percent TINYINT UNSIGNED NOT NULL,
  total_agents TINYINT UNSIGNED NOT NULL DEFAULT 10,
  required_ready_count TINYINT UNSIGNED NOT NULL,
  round_interval_seconds INT UNSIGNED NOT NULL DEFAULT 60,
  model_name VARCHAR(128) NULL,
  status VARCHAR(20) NOT NULL,
  current_round INT UNSIGNED NOT NULL DEFAULT 0,
  latest_ready_count TINYINT UNSIGNED NOT NULL DEFAULT 0,
  accepted_ratio DECIMAL(5,2) NOT NULL DEFAULT 0.00,
  final_answer MEDIUMTEXT NULL,
  final_evidence_text MEDIUMTEXT NULL,
  consecutive_error_rounds INT UNSIGNED NOT NULL DEFAULT 0,
  error_text TEXT NULL,
  last_round_started_at DATETIME NULL,
  last_round_finished_at DATETIME NULL,
  next_round_at DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  answered_at DATETIME NULL,
  stopped_at DATETIME NULL,
  failed_at DATETIME NULL,
  running_slot TINYINT GENERATED ALWAYS AS (
    CASE WHEN status = 'running' THEN 1 ELSE NULL END
  ) STORED,
  PRIMARY KEY (id),
  UNIQUE KEY uq_consensus_single_running (running_slot),
  KEY idx_consensus_tasks_status_next_round (status, next_round_at),
  KEY idx_consensus_tasks_created_at (created_at),
  KEY idx_consensus_tasks_updated_at (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS consensus_agent_logs (
  id BIGINT NOT NULL AUTO_INCREMENT,
  task_id BIGINT NOT NULL,
  round_no INT UNSIGNED NOT NULL,
  agent_id VARCHAR(64) NOT NULL,
  agent_name VARCHAR(128) NOT NULL,
  content_short VARCHAR(160) NOT NULL,
  is_ready_to_answer TINYINT(1) NOT NULL DEFAULT 0,
  candidate_answer TEXT NULL,
  evidence_title VARCHAR(255) NULL,
  evidence_url VARCHAR(500) NULL,
  evidence_time VARCHAR(64) NULL,
  error_text VARCHAR(255) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_consensus_task_round_agent (task_id, round_no, agent_id),
  KEY idx_consensus_logs_task_agent_round (task_id, agent_id, round_no),
  KEY idx_consensus_logs_task_round_ready (task_id, round_no, is_ready_to_answer),
  KEY idx_consensus_logs_task_created_at (task_id, created_at),
  CONSTRAINT fk_consensus_logs_task
    FOREIGN KEY (task_id) REFERENCES consensus_tasks(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
