"""Database schema and models for SQLite cache."""

SCHEMA = """
-- PDF text cache (invalidated by file checksum)
CREATE TABLE IF NOT EXISTS pdf_text_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pdf_path TEXT NOT NULL,
    page_number INTEGER NOT NULL,
    text_content TEXT,
    file_checksum TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(pdf_path, page_number)
);

-- AI categorization cache with hierarchical group support (keyed by content hash)
CREATE TABLE IF NOT EXISTS categorization_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    context_hash TEXT UNIQUE NOT NULL,
    search_term TEXT NOT NULL,
    category_group TEXT NOT NULL,  -- "Surgical/Anatomical" or "Theoretical"
    category TEXT NOT NULL,        -- Specific subcategory
    confidence REAL NOT NULL,
    reasoning TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Search history for autocomplete
CREATE TABLE IF NOT EXISTS search_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    result_count INTEGER,
    searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Library structure cache
CREATE TABLE IF NOT EXISTS library_structure (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pdf_path TEXT UNIQUE NOT NULL,
    book_series TEXT,
    book_title TEXT,
    chapter_number INTEGER,
    chapter_title TEXT,
    file_size INTEGER,
    page_count INTEGER,
    file_checksum TEXT,
    last_scanned TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tracked files for auto-update detection (NEW)
CREATE TABLE IF NOT EXISTS tracked_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pdf_path TEXT UNIQUE NOT NULL,
    file_checksum TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_indexed BOOLEAN DEFAULT 0,
    book_series TEXT,
    chapter_title TEXT,
    page_count INTEGER DEFAULT 0
);

-- Semantic search index tracking
CREATE TABLE IF NOT EXISTS semantic_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pdf_path TEXT NOT NULL,
    page_number INTEGER NOT NULL,
    file_checksum TEXT NOT NULL,
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(pdf_path, page_number)
);

-- Synthesis history for tracking NeuroSynth sessions
CREATE TABLE IF NOT EXISTS synthesis_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    search_query TEXT,
    search_mode TEXT,
    source_count INTEGER DEFAULT 0,
    surgical_count INTEGER DEFAULT 0,
    theoretical_count INTEGER DEFAULT 0,
    template_used TEXT,
    output_path TEXT,
    success BOOLEAN DEFAULT 0,
    error_message TEXT,
    manifest_json TEXT,  -- Store the full manifest for reference
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Synthesis source junction table (tracks which sources were used)
CREATE TABLE IF NOT EXISTS synthesis_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    synthesis_id INTEGER NOT NULL,
    original_source TEXT NOT NULL,
    pdf_path TEXT,
    category_group TEXT,
    category TEXT,
    pages TEXT,  -- JSON array of page numbers
    FOREIGN KEY (synthesis_id) REFERENCES synthesis_history(id)
);

-- Visual elements cache (extracted figures from PDFs)
CREATE TABLE IF NOT EXISTS visual_elements (
    id TEXT PRIMARY KEY,
    pdf_path TEXT NOT NULL,
    page_number INTEGER NOT NULL,
    image_path TEXT,
    format TEXT DEFAULT 'png',
    width INTEGER,
    height INTEGER,
    bbox TEXT,                    -- JSON: [x0, y0, x1, y1]
    caption TEXT,
    caption_confidence REAL,
    image_type TEXT,              -- surgical_step, anatomical, imaging, etc.
    type_confidence REAL,
    context_text TEXT,
    visual_hash TEXT,             -- Perceptual hash for dedup
    file_checksum TEXT NOT NULL,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(pdf_path, page_number, visual_hash)
);

-- Visual embeddings tracking (for ColPali/Qdrant integration)
CREATE TABLE IF NOT EXISTS visual_embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    element_id TEXT NOT NULL,
    qdrant_point_id TEXT,
    embedding_model TEXT,
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (element_id) REFERENCES visual_elements(id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_pdf_path ON pdf_text_cache(pdf_path);
CREATE INDEX IF NOT EXISTS idx_context_hash ON categorization_cache(context_hash);
CREATE INDEX IF NOT EXISTS idx_search_query ON search_history(query);
CREATE INDEX IF NOT EXISTS idx_library_path ON library_structure(pdf_path);
CREATE INDEX IF NOT EXISTS idx_tracked_indexed ON tracked_files(is_indexed);
CREATE INDEX IF NOT EXISTS idx_tracked_first_seen ON tracked_files(first_seen);
CREATE INDEX IF NOT EXISTS idx_semantic_path ON semantic_index(pdf_path);
CREATE INDEX IF NOT EXISTS idx_synthesis_topic ON synthesis_history(topic);
CREATE INDEX IF NOT EXISTS idx_synthesis_created ON synthesis_history(created_at);
CREATE INDEX IF NOT EXISTS idx_synthesis_sources_id ON synthesis_sources(synthesis_id);
CREATE INDEX IF NOT EXISTS idx_visual_pdf ON visual_elements(pdf_path);
CREATE INDEX IF NOT EXISTS idx_visual_type ON visual_elements(image_type);
CREATE INDEX IF NOT EXISTS idx_visual_caption ON visual_elements(caption);
CREATE INDEX IF NOT EXISTS idx_visual_hash ON visual_elements(visual_hash);
CREATE INDEX IF NOT EXISTS idx_visual_embed_element ON visual_embeddings(element_id);

-- FTS5 Full-Text Search Index (60x faster keyword search)
-- Uses porter tokenizer for stemming and case-insensitive search
CREATE VIRTUAL TABLE IF NOT EXISTS pdf_text_fts USING fts5(
    pdf_path,           -- PDF file path (for filtering)
    page_number,        -- Page number (for result context)
    text_content,       -- Full text content to search
    content='pdf_text_cache',       -- External content table
    content_rowid='id',             -- Link to main table rowid
    tokenize='porter unicode61'     -- Porter stemming + Unicode support
);

-- Triggers to keep FTS index synchronized with pdf_text_cache
CREATE TRIGGER IF NOT EXISTS pdf_text_fts_insert AFTER INSERT ON pdf_text_cache BEGIN
    INSERT INTO pdf_text_fts(rowid, pdf_path, page_number, text_content)
    VALUES (new.id, new.pdf_path, new.page_number, new.text_content);
END;

CREATE TRIGGER IF NOT EXISTS pdf_text_fts_delete AFTER DELETE ON pdf_text_cache BEGIN
    INSERT INTO pdf_text_fts(pdf_text_fts, rowid, pdf_path, page_number, text_content)
    VALUES ('delete', old.id, old.pdf_path, old.page_number, old.text_content);
END;

CREATE TRIGGER IF NOT EXISTS pdf_text_fts_update AFTER UPDATE ON pdf_text_cache BEGIN
    INSERT INTO pdf_text_fts(pdf_text_fts, rowid, pdf_path, page_number, text_content)
    VALUES ('delete', old.id, old.pdf_path, old.page_number, old.text_content);
    INSERT INTO pdf_text_fts(rowid, pdf_path, page_number, text_content)
    VALUES (new.id, new.pdf_path, new.page_number, new.text_content);
END;

-- FTS5 index for visual element captions and context
CREATE VIRTUAL TABLE IF NOT EXISTS visual_caption_fts USING fts5(
    pdf_path,
    page_number,
    caption,
    context_text,
    content='visual_elements',
    content_rowid='rowid',
    tokenize='porter unicode61'
);

-- Triggers for visual caption FTS
CREATE TRIGGER IF NOT EXISTS visual_fts_insert AFTER INSERT ON visual_elements BEGIN
    INSERT INTO visual_caption_fts(rowid, pdf_path, page_number, caption, context_text)
    VALUES (new.rowid, new.pdf_path, new.page_number, new.caption, new.context_text);
END;

CREATE TRIGGER IF NOT EXISTS visual_fts_delete AFTER DELETE ON visual_elements BEGIN
    INSERT INTO visual_caption_fts(visual_caption_fts, rowid, pdf_path, page_number, caption, context_text)
    VALUES ('delete', old.rowid, old.pdf_path, old.page_number, old.caption, old.context_text);
END;

CREATE TRIGGER IF NOT EXISTS visual_fts_update AFTER UPDATE ON visual_elements BEGIN
    INSERT INTO visual_caption_fts(visual_caption_fts, rowid, pdf_path, page_number, caption, context_text)
    VALUES ('delete', old.rowid, old.pdf_path, old.page_number, old.caption, old.context_text);
    INSERT INTO visual_caption_fts(rowid, pdf_path, page_number, caption, context_text)
    VALUES (new.rowid, new.pdf_path, new.page_number, new.caption, new.context_text);
END;
"""


# FTS5 rebuild command (use after bulk inserts)
FTS_REBUILD_SQL = """
INSERT INTO pdf_text_fts(pdf_text_fts) VALUES('rebuild');
INSERT INTO visual_caption_fts(visual_caption_fts) VALUES('rebuild');
"""

# Example FTS5 queries:
# Basic search: SELECT * FROM pdf_text_fts WHERE text_content MATCH 'craniotomy';
# Phrase search: SELECT * FROM pdf_text_fts WHERE text_content MATCH '"surgical approach"';
# Boolean: SELECT * FROM pdf_text_fts WHERE text_content MATCH 'craniotomy AND tumor';
# Ranking: SELECT *, bm25(pdf_text_fts) FROM pdf_text_fts WHERE text_content MATCH 'craniotomy' ORDER BY bm25(pdf_text_fts);
