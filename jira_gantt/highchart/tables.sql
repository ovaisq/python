CREATE TABLE IF NOT EXISTS project (
    project_id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS projectdata (
    projectdata_id SERIAL PRIMARY KEY,
    project_id INT REFERENCES project(project_id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    id VARCHAR(255) NOT NULL,
    parent VARCHAR(255),
    dependency VARCHAR(255),
    start_date DATE,
    end_date DATE,
    milestone BOOLEAN,
    owner VARCHAR(255),
    completed_amount FLOAT,
    completed_fill VARCHAR(7)
);
