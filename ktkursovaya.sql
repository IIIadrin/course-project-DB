-- Таблица типов договоров
CREATE TABLE contract_types (
    contract_type_code SERIAL PRIMARY KEY,
    type_name VARCHAR(100) NOT NULL UNIQUE
);

-- Таблица стадий исполнения
CREATE TABLE execution_stages (
    stage_code SERIAL PRIMARY KEY,
    stage_name VARCHAR(100) NOT NULL UNIQUE
);

-- Таблица ставок НДС
CREATE TABLE vat_rates (
    vat_code SERIAL PRIMARY KEY,
    percentage DECIMAL(5,2) NOT NULL CHECK (percentage >= 0 AND percentage <= 100),
    description VARCHAR(50)
);

-- Таблица организаций
CREATE TABLE organizations (
    organization_code SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    postal_index VARCHAR(20),
    address TEXT,
    phone VARCHAR(50),
    fax VARCHAR(50),
    inn VARCHAR(20) UNIQUE,
    correspondent_account VARCHAR(50),
    bank_name VARCHAR(255),
    settlement_account VARCHAR(50),
    okonh VARCHAR(20),
    okpo VARCHAR(20),
    bik VARCHAR(20),
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Таблица видов оплат
CREATE TABLE payment_types (
    payment_type_code SERIAL PRIMARY KEY,
    payment_type_name VARCHAR(100) NOT NULL UNIQUE
);

-- Основная таблица договоров
CREATE TABLE contracts (
    contract_code SERIAL PRIMARY KEY,
    conclusion_date DATE NOT NULL DEFAULT CURRENT_DATE,
    customer_code INTEGER NOT NULL,
    executor_code INTEGER NOT NULL,
    contract_type_code INTEGER NOT NULL,
    execution_stage_code INTEGER NOT NULL DEFAULT 1,
    vat_code INTEGER NOT NULL,
    execution_date DATE,
    topic VARCHAR(500) NOT NULL,
    notes TEXT,
    total_amount DECIMAL(15,2) CHECK (total_amount >= 0),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_customer FOREIGN KEY (customer_code) 
        REFERENCES organizations(organization_code) ON DELETE RESTRICT,
    CONSTRAINT fk_executor FOREIGN KEY (executor_code) 
        REFERENCES organizations(organization_code) ON DELETE RESTRICT,
    CONSTRAINT fk_contract_type FOREIGN KEY (contract_type_code) 
        REFERENCES contract_types(contract_type_code) ON DELETE RESTRICT,
    CONSTRAINT fk_execution_stage FOREIGN KEY (execution_stage_code) 
        REFERENCES execution_stages(stage_code) ON DELETE RESTRICT,
    CONSTRAINT fk_vat FOREIGN KEY (vat_code) 
        REFERENCES vat_rates(vat_code) ON DELETE RESTRICT,
    CONSTRAINT chk_dates CHECK (execution_date IS NULL OR execution_date >= conclusion_date),
    CONSTRAINT chk_customer_executor CHECK (customer_code != executor_code)
);

-- Таблица этапов договоров
CREATE TABLE contract_stages (
    contract_code INTEGER NOT NULL,
    stage_number INTEGER NOT NULL,
    stage_execution_date DATE,
    stage_code INTEGER NOT NULL,
    stage_amount DECIMAL(15,2) NOT NULL CHECK (stage_amount >= 0),
    advance_amount DECIMAL(15,2) DEFAULT 0 CHECK (advance_amount >= 0),
    topic VARCHAR(500),
    notes TEXT,
    
    PRIMARY KEY (contract_code, stage_number),
    CONSTRAINT fk_contract FOREIGN KEY (contract_code) 
        REFERENCES contracts(contract_code) ON DELETE CASCADE,
    CONSTRAINT fk_stage FOREIGN KEY (stage_code) 
        REFERENCES execution_stages(stage_code) ON DELETE RESTRICT,
    CONSTRAINT chk_advance CHECK (advance_amount <= stage_amount)
);

-- Таблица оплат
CREATE TABLE payments (
    payment_id SERIAL PRIMARY KEY,
    contract_code INTEGER NOT NULL,
    payment_date DATE NOT NULL DEFAULT CURRENT_DATE,
    payment_amount DECIMAL(15,2) NOT NULL CHECK (payment_amount > 0),
    payment_type_code INTEGER NOT NULL,
    payment_document_number VARCHAR(100),
    
    CONSTRAINT fk_payment_contract FOREIGN KEY (contract_code) 
        REFERENCES contracts(contract_code) ON DELETE CASCADE,
    CONSTRAINT fk_payment_type FOREIGN KEY (payment_type_code) 
        REFERENCES payment_types(payment_type_code) ON DELETE RESTRICT
);
-- 1. Для быстрого поиска договоров по заказчику и дате
CREATE INDEX idx_contracts_customer_date ON contracts(customer_code, conclusion_date);

-- 2. Для поиска договоров по исполнителю
CREATE INDEX idx_contracts_executor ON contracts(executor_code);

-- 3. Для поиска платежей по договору и дате (самые частые запросы)
CREATE INDEX idx_payments_contract_date ON payments(contract_code, payment_date);

-- 4. Для поиска организаций по ИНН и названию
CREATE INDEX idx_organizations_inn_name ON organizations(inn, name);
-- VIEW по одной таблице: активные договоры
CREATE VIEW active_contracts_view AS
SELECT 
    contract_code,
    conclusion_date,
    execution_date,
    topic,
    total_amount
FROM contracts
WHERE execution_date IS NULL OR execution_date >= CURRENT_DATE;

-- VIEW по нескольким таблицам: детальная информация о договорах
CREATE VIEW contracts_detailed_view AS
SELECT 
    c.contract_code,
    c.conclusion_date,
    c.execution_date,
    c.topic,
    c.total_amount,
    ct.type_name as contract_type,
    es.stage_name as execution_stage,
    cust.name as customer_name,
    exec.name as executor_name,
    v.percentage as vat_percentage
FROM contracts c
JOIN contract_types ct ON c.contract_type_code = ct.contract_type_code
JOIN execution_stages es ON c.execution_stage_code = es.stage_code
JOIN organizations cust ON c.customer_code = cust.organization_code
JOIN organizations exec ON c.executor_code = exec.organization_code
JOIN vat_rates v ON c.vat_code = v.vat_code;

-- VIEW с GROUP BY и HAVING: заказчики с общей суммой договоров более 1 млн
CREATE VIEW top_customers_view AS
SELECT 
    o.organization_code,
    o.name as customer_name,
    COUNT(c.contract_code) as contract_count,
    SUM(COALESCE(c.total_amount, 0)) as total_contract_amount
FROM organizations o
JOIN contracts c ON o.organization_code = c.customer_code
GROUP BY o.organization_code, o.name
HAVING SUM(COALESCE(c.total_amount, 0)) > 1000000
ORDER BY total_contract_amount DESC;

-- VIEW для отслеживания платежей по договорам
CREATE VIEW contract_payments_summary_view AS
SELECT 
    c.contract_code,
    c.topic,
    c.total_amount,
    COALESCE(SUM(p.payment_amount), 0) as total_paid,
    (c.total_amount - COALESCE(SUM(p.payment_amount), 0)) as remaining_amount
FROM contracts c
LEFT JOIN payments p ON c.contract_code = p.contract_code
GROUP BY c.contract_code, c.topic, c.total_amount;
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();  
    RETURN NEW;              
END;
$$ LANGUAGE plpgsql;         
--триггер автоматического поддержания денормализованных данных
CREATE TRIGGER update_contracts_updated_at 
    BEFORE UPDATE ON contracts 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();