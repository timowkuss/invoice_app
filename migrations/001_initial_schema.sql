-- Invoice App - Initial PostgreSQL Schema
-- Migration 001: Core tables

-- ============================================================
-- STORES (Магазины)
-- ============================================================
CREATE TABLE IF NOT EXISTS stores (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) UNIQUE NOT NULL,
    address TEXT,
    phone VARCHAR(50),
    inn VARCHAR(20),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- USERS (Пользователи)
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    store_id INTEGER REFERENCES stores(id) ON DELETE SET NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(20) NOT NULL CHECK (role IN ('super_admin', 'store_admin', 'operator')),
    telegram_chat_id BIGINT UNIQUE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_users_store ON users(store_id);
CREATE INDEX idx_users_role ON users(role);

-- ============================================================
-- 1C CONNECTIONS (Подключения к 1С)
-- ============================================================
CREATE TABLE IF NOT EXISTS one_c_connections (
    id SERIAL PRIMARY KEY,
    store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    base_url VARCHAR(500),
    username VARCHAR(100),
    password_encrypted VARCHAR(500),
    odata_path VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    last_sync_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_one_c_connections_store ON one_c_connections(store_id);

-- ============================================================
-- PRODUCTS (Каталог товаров из 1С)
-- ============================================================
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    one_c_id VARCHAR(100) NOT NULL,
    name VARCHAR(500) NOT NULL,
    article VARCHAR(100),
    barcode VARCHAR(100),
    unit VARCHAR(50),
    weight DECIMAL(10,3),
    volume DECIMAL(10,3),
    fat_content DECIMAL(5,2),
    category VARCHAR(255),
    price DECIMAL(12,2),
    is_active BOOLEAN DEFAULT TRUE,
    synced_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(store_id, one_c_id)
);

CREATE INDEX idx_products_store ON products(store_id);
CREATE INDEX idx_products_name ON products USING gin(to_tsvector('russian', name));
CREATE INDEX idx_products_article ON products(store_id, article);
CREATE INDEX idx_products_barcode ON products(store_id, barcode);

-- ============================================================
-- PRODUCT ALIASES (Синонимы OCR → товар 1С)
-- ============================================================
CREATE TABLE IF NOT EXISTS product_aliases (
    id SERIAL PRIMARY KEY,
    store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    ocr_text VARCHAR(500) NOT NULL,
    normalized_text VARCHAR(500) NOT NULL,
    confidence DECIMAL(5,2) DEFAULT 100.0,
    usage_count INTEGER DEFAULT 0,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_product_aliases_store ON product_aliases(store_id);
CREATE INDEX idx_product_aliases_normalized ON product_aliases(store_id, normalized_text);
CREATE INDEX idx_product_aliases_product ON product_aliases(product_id);

-- ============================================================
-- DOCUMENTS (Накладные)
-- ============================================================
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    supplier VARCHAR(500),
    document_number VARCHAR(100),
    document_date DATE,
    status VARCHAR(20) NOT NULL DEFAULT 'received'
        CHECK (status IN (
            'received', 'processing', 'recognized', 'matching',
            'needs_review', 'confirmed', 'sent_to_1c', 'completed', 'error',
            'retry_pending'
        )),
    original_file_url VARCHAR(1000),
    original_file_hash VARCHAR(64),
    telegram_message_id BIGINT,
    telegram_chat_id BIGINT,
    sent_by_user_id INTEGER REFERENCES users(id),
    total_items INTEGER DEFAULT 0,
    matched_items INTEGER DEFAULT 0,
    needs_review_items INTEGER DEFAULT 0,
    error_message TEXT,
    processed_at TIMESTAMP,
    confirmed_at TIMESTAMP,
    sent_to_1c_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_documents_store ON documents(store_id);
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_date ON documents(document_date);
CREATE INDEX idx_documents_supplier ON documents(store_id, supplier);
CREATE INDEX idx_documents_hash ON documents(original_file_hash);
CREATE INDEX idx_documents_telegram ON documents(telegram_message_id);

-- ============================================================
-- DOCUMENT ITEMS (Строки накладных)
-- ============================================================
CREATE TABLE IF NOT EXISTS document_items (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
    row_number INTEGER NOT NULL,
    ocr_text VARCHAR(500),
    product_name VARCHAR(500),
    article VARCHAR(100),
    barcode VARCHAR(100),
    quantity DECIMAL(10,3),
    price DECIMAL(12,2),
    total DECIMAL(12,2),
    unit VARCHAR(50),
    confidence DECIMAL(5,2),
    match_status VARCHAR(20) DEFAULT 'pending'
        CHECK (match_status IN ('pending', 'matched', 'manual', 'not_found')),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_document_items_document ON document_items(document_id);
CREATE INDEX idx_document_items_product ON document_items(product_id);
CREATE INDEX idx_document_items_status ON document_items(match_status);

-- ============================================================
-- AI REQUESTS (Запросы к Mistral)
-- ============================================================
CREATE TABLE IF NOT EXISTS ai_requests (
    id SERIAL PRIMARY KEY,
    store_id INTEGER REFERENCES stores(id) ON DELETE SET NULL,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    document_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,
    provider VARCHAR(50) NOT NULL DEFAULT 'mistral',
    model VARCHAR(100) NOT NULL DEFAULT 'mistral-ocr-latest',
    request_type VARCHAR(50) NOT NULL CHECK (request_type IN ('ocr', 'matching', 'other')),
    status VARCHAR(20) NOT NULL CHECK (status IN ('success', 'error', 'timeout')),
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    cost DECIMAL(10,6) DEFAULT 0,
    error_message TEXT,
    duration_ms INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_ai_requests_store ON ai_requests(store_id);
CREATE INDEX idx_ai_requests_document ON ai_requests(document_id);
CREATE INDEX idx_ai_requests_created ON ai_requests(created_at);
CREATE INDEX idx_ai_requests_provider ON ai_requests(provider, created_at);

-- ============================================================
-- AUDIT LOGS (История изменений)
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    store_id INTEGER REFERENCES stores(id) ON DELETE SET NULL,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    document_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id INTEGER,
    old_value JSONB,
    new_value JSONB,
    ip_address VARCHAR(45),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_store ON audit_logs(store_id);
CREATE INDEX idx_audit_logs_document ON audit_logs(document_id);
CREATE INDEX idx_audit_logs_user ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_created ON audit_logs(created_at);

-- ============================================================
-- SETTINGS (Глобальные настройки)
-- ============================================================
CREATE TABLE IF NOT EXISTS app_settings (
    key VARCHAR(100) PRIMARY KEY,
    value JSONB NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Default settings
INSERT INTO app_settings (key, value, description) VALUES
    ('matching.auto_match_threshold', '85', 'Порог автоматического сопоставления (0-100)'),
    ('matching.review_threshold', '60', 'Порог ручной проверки (0-100)'),
    ('matching.max_results', '5', 'Максимальное количество кандидатов для matching')
ON CONFLICT (key) DO NOTHING;
