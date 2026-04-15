CREATE TABLE IF NOT EXISTS world_info_items (
  id BIGINT NOT NULL AUTO_INCREMENT,
  project_id VARCHAR(64) NOT NULL,
  title VARCHAR(255) NULL,
  source VARCHAR(512) NULL,
  source_type VARCHAR(64) NULL,
  raw_content LONGTEXT NOT NULL,
  summary TEXT NOT NULL,
  published_at DATETIME NULL,
  content_hash CHAR(64) NOT NULL,
  metadata_json JSON NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_world_info_project_hash (project_id, content_hash),
  KEY idx_world_info_project_updated (project_id, updated_at),
  KEY idx_world_info_project_published (project_id, published_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS world_info_chunks (
  id BIGINT NOT NULL AUTO_INCREMENT,
  item_id BIGINT NOT NULL,
  project_id VARCHAR(64) NOT NULL,
  chunk_index INT NOT NULL,
  chunk_text TEXT NOT NULL,
  chunk_summary VARCHAR(512) NOT NULL,
  chroma_doc_id VARCHAR(128) NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_world_info_item_chunk (item_id, chunk_index),
  UNIQUE KEY uq_world_info_chroma_doc_id (chroma_doc_id),
  KEY idx_world_info_chunks_project_item (project_id, item_id),
  CONSTRAINT fk_world_info_chunks_item
    FOREIGN KEY (item_id) REFERENCES world_info_items(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
