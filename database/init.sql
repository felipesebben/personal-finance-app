-- Create Dimension Tables

-- Dimension: Person
CREATE TABLE Dim_Person (
    PersonID SERIAL PRIMARY KEY,
    PersonName VARCHAR(255) NOT NULL UNIQUE
);

-- Dimension: Payment Method
CREATE TABLE Dim_PaymentMethod (
    PaymentMethodID SERIAL PRIMARY KEY,
    MethodName VARCHAR(255) NOT NULL,
    Institution VARCHAR(255)
);

-- Dimension: Category
CREATE TABLE Dim_Category (
    CategoryID SERIAL PRIMARY KEY,
    PrimaryCategory VARCHAR(255) NOT NULL,
    SubCategory VARCHAR(255) NOT NULL,
    CostType VARCHAR(50) -- e.g., 'Fixed', 'Variable'
    Nature VARCHAR(50), --e.g., 'Normal', 'Extraordinary'
    UNIQUE (PrimaryCategory, SubCategory) -- Avoids creating repeated combinations of PrimaryCategory and SubCategory
);

-- Create Fact Table

-- Fact: Expenditures
CREATE TABLE Fact_Expenditures(
    ExpenditureID SERIAL PRIMARY KEY,
    TransactionTimeStamp TIMESTAMPZ NOT NULL, -- Timestamp with Time Zone
    Price DECIMAL(10, 2) NOT NULL,

    -- Foreign Keys
    PersonID INT REFERENCES Dim_Person(PersonID),
    CategoryID INT REFERENCES Dim_Category(CategoryID),
    PaymentMethodID INT REFERENCES Dim_PaymentMethod(PaymentMethodID)
);

-- Add some initial data to the dimension tables for testing

INSERT INTO Dim_Person (PersonName) VALUES ('John Doe'), ('Jane Doe');

INSERT INTO Dim_Category (PrimaryCategory, SubCategory, CostType, Nature)
VALUES
('Food', 'Groceries', 'Variable', 'Normal'),
('Home', 'Mortgage', 'Fixed', 'Normal'),
('Transportation', 'Gas', 'Variable', 'Normal');