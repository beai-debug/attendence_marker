# Database Structure Documentation

## Attendance Marker System - PostgreSQL + pgvector Schema

**Database:** PostgreSQL 14+  
**Extension:** pgvector  
**Password:** Deepdive  
**Auto-Configuration:** Yes (on server start)

---

## Overview

The system uses PostgreSQL with the pgvector extension for efficient vector similarity search. The database is automatically created and configured when the server starts.

### Key Features
- **Composite Primary Keys** for multi-tenant support
- **pgvector** for 512-dimensional face embeddings
- **IVFFlat Indexing** for fast similarity search
- **Connection Pooling** for high performance
- **Automatic Schema Migration**

---

## Database Configuration

### Default Settings
```
Host:     localhost
Port:     5432
Database: attendance_db
User:     postgres
Password: Deepdive
```

### Environment Variables
```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=attendance_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=Deepdive
```

### Connection Pool Settings
```python
pool_size: 10
max_overflow: 20
pool_timeout: 30
pool_recycle: 1800  # 30 minutes
```

---

## Tables

### 1. Students Table

Stores enrolled student information with face embeddings.

```sql
CREATE TABLE students (
    id SERIAL,
    school_name VARCHAR(255) NOT NULL,
    roll_no VARCHAR(100) NOT NULL,
    session VARCHAR(50) NOT NULL,
    name VARCHAR(255),
    class_name VARCHAR(100),
    section VARCHAR(50),
    subject VARCHAR(100),
    face_path TEXT,
    embedding vector(512),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (school_name, roll_no, session)
);
```

#### Columns

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | SERIAL | No | Auto-increment ID |
| school_name | VARCHAR(255) | No | School identifier (part of PK) |
| roll_no | VARCHAR(100) | No | Student roll number (part of PK) |
| session | VARCHAR(50) | No | Academic session (part of PK) |
| name | VARCHAR(255) | Yes | Student name |
| class_name | VARCHAR(100) | Yes | Class name |
| section | VARCHAR(50) | Yes | Section |
| subject | VARCHAR(100) | Yes | Subject |
| face_path | TEXT | Yes | Path to face images |
| embedding | vector(512) | Yes | Face embedding (pgvector) |
| created_at | TIMESTAMP | Yes | Record creation time |
| updated_at | TIMESTAMP | Yes | Last update time |

#### Primary Key
```
(school_name, roll_no, session)
```

This composite key allows:
- Same roll_no across different schools
- Same roll_no across different sessions
- Unique identification within school+session

---

### 2. Attendance Table

Stores attendance records with status (Present/Absent).

```sql
CREATE TABLE attendance (
    id SERIAL PRIMARY KEY,
    school_name VARCHAR(255),
    roll_no VARCHAR(100),
    session VARCHAR(50),
    student_name VARCHAR(255),
    class_name VARCHAR(100),
    section VARCHAR(50),
    subject VARCHAR(100),
    similarity_score REAL,
    status VARCHAR(10) DEFAULT 'A',
    date DATE,
    time TIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Columns

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | SERIAL | No | Auto-increment primary key |
| school_name | VARCHAR(255) | Yes | School identifier |
| roll_no | VARCHAR(100) | Yes | Student roll number |
| session | VARCHAR(50) | Yes | Academic session |
| student_name | VARCHAR(255) | Yes | Student name |
| class_name | VARCHAR(100) | Yes | Class name |
| section | VARCHAR(50) | Yes | Section |
| subject | VARCHAR(100) | Yes | Subject |
| similarity_score | REAL | Yes | Face match confidence (0-1) |
| status | VARCHAR(10) | Yes | 'P' (Present) or 'A' (Absent) |
| date | DATE | Yes | Attendance date |
| time | TIME | Yes | Attendance time |
| created_at | TIMESTAMP | Yes | Record creation time |

#### Status Values
| Value | Description |
|-------|-------------|
| P | Present (face detected and matched) |
| A | Absent (face not detected) |

---

### 3. Database Change Log Table

Audit trail for all database modifications.

```sql
CREATE TABLE database_change_log (
    id SERIAL PRIMARY KEY,
    school_name VARCHAR(255),
    class_name VARCHAR(100),
    section VARCHAR(50),
    subject VARCHAR(100),
    roll_no VARCHAR(100),
    session VARCHAR(50),
    change_type VARCHAR(50) NOT NULL,
    endpoint_name VARCHAR(255),
    details TEXT,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

#### Columns

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | SERIAL | No | Auto-increment primary key |
| school_name | VARCHAR(255) | Yes | School identifier |
| class_name | VARCHAR(100) | Yes | Class name |
| section | VARCHAR(50) | Yes | Section |
| subject | VARCHAR(100) | Yes | Subject |
| roll_no | VARCHAR(100) | Yes | Student roll number |
| session | VARCHAR(50) | Yes | Academic session |
| change_type | VARCHAR(50) | No | Type of change |
| endpoint_name | VARCHAR(255) | Yes | API endpoint that made the change |
| details | TEXT | Yes | Human-readable description |
| timestamp | TIMESTAMP | No | When the change occurred |

#### Change Types
| Type | Description |
|------|-------------|
| insert | New record created |
| update | Record modified |
| delete | Record deleted |
| embedding_update | Face embedding updated |

---

## Indexes

### Students Table Indexes

```sql
-- School-based queries
CREATE INDEX idx_students_school 
ON students(school_name);

-- Class/section queries
CREATE INDEX idx_students_class_section 
ON students(school_name, class_name, section);

-- Session-based queries
CREATE INDEX idx_students_session 
ON students(session);

-- Roll number lookups
CREATE INDEX idx_students_roll_no 
ON students(roll_no);

-- Vector similarity search (IVFFlat)
CREATE INDEX idx_students_embedding 
ON students USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

### Attendance Table Indexes

```sql
-- School-based queries
CREATE INDEX idx_attendance_school 
ON attendance(school_name);

-- Roll number lookups
CREATE INDEX idx_attendance_roll_no 
ON attendance(roll_no);

-- Date-based queries
CREATE INDEX idx_attendance_date 
ON attendance(date);

-- Combined queries
CREATE INDEX idx_attendance_class_section_date 
ON attendance(school_name, class_name, section, date);

-- Session-based queries
CREATE INDEX idx_attendance_session 
ON attendance(session);
```

### Change Log Indexes

```sql
-- School-based queries
CREATE INDEX idx_change_log_school 
ON database_change_log(school_name);

-- Roll number lookups
CREATE INDEX idx_change_log_roll_no 
ON database_change_log(roll_no);

-- Session-based queries
CREATE INDEX idx_change_log_session 
ON database_change_log(session);

-- Time-based queries
CREATE INDEX idx_change_log_timestamp 
ON database_change_log(timestamp);
```

---

## pgvector Configuration

### Extension Setup
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### Vector Column
```sql
embedding vector(512)
```
- **Dimension:** 512 (InsightFace embedding size)
- **Type:** pgvector vector type

### Similarity Search Index
```sql
CREATE INDEX idx_students_embedding 
ON students USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

- **Index Type:** IVFFlat (Inverted File with Flat compression)
- **Operator:** vector_cosine_ops (cosine similarity)
- **Lists:** 100 (number of clusters)

### Similarity Query
```sql
SELECT roll_no, name, 1 - (embedding <=> %s::vector) as similarity
FROM students
WHERE school_name = %s AND class_name = %s AND section = %s
  AND 1 - (embedding <=> %s::vector) >= %s
ORDER BY similarity DESC
LIMIT %s;
```

- **Operator `<=>`:** Cosine distance
- **Formula:** `similarity = 1 - cosine_distance`

---

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        STUDENTS                              │
├─────────────────────────────────────────────────────────────┤
│ PK: (school_name, roll_no, session)                         │
│                                                              │
│ id              SERIAL                                       │
│ school_name     VARCHAR(255)  NOT NULL                       │
│ roll_no         VARCHAR(100)  NOT NULL                       │
│ session         VARCHAR(50)   NOT NULL                       │
│ name            VARCHAR(255)                                 │
│ class_name      VARCHAR(100)                                 │
│ section         VARCHAR(50)                                  │
│ subject         VARCHAR(100)                                 │
│ face_path       TEXT                                         │
│ embedding       vector(512)                                  │
│ created_at      TIMESTAMP                                    │
│ updated_at      TIMESTAMP                                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ References (logical)
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       ATTENDANCE                             │
├─────────────────────────────────────────────────────────────┤
│ PK: id                                                       │
│                                                              │
│ id              SERIAL        PRIMARY KEY                    │
│ school_name     VARCHAR(255)                                 │
│ roll_no         VARCHAR(100)                                 │
│ session         VARCHAR(50)                                  │
│ student_name    VARCHAR(255)                                 │
│ class_name      VARCHAR(100)                                 │
│ section         VARCHAR(50)                                  │
│ subject         VARCHAR(100)                                 │
│ similarity_score REAL                                        │
│ status          VARCHAR(10)   DEFAULT 'A'                    │
│ date            DATE                                         │
│ time            TIME                                         │
│ created_at      TIMESTAMP                                    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                   DATABASE_CHANGE_LOG                        │
├─────────────────────────────────────────────────────────────┤
│ PK: id                                                       │
│                                                              │
│ id              SERIAL        PRIMARY KEY                    │
│ school_name     VARCHAR(255)                                 │
│ class_name      VARCHAR(100)                                 │
│ section         VARCHAR(50)                                  │
│ subject         VARCHAR(100)                                 │
│ roll_no         VARCHAR(100)                                 │
│ session         VARCHAR(50)                                  │
│ change_type     VARCHAR(50)   NOT NULL                       │
│ endpoint_name   VARCHAR(255)                                 │
│ details         TEXT                                         │
│ timestamp       TIMESTAMP     NOT NULL                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### Enrollment Flow
```
1. Upload ZIP file with student photos
2. Extract and process each student folder
3. Generate face embeddings using InsightFace
4. L2 normalize embeddings
5. INSERT/UPDATE into students table
6. Log change to database_change_log
```

### Attendance Flow
```
1. Upload classroom photos
2. Detect faces in photos
3. Generate embeddings for detected faces
4. Query students table using vector similarity
5. Match faces above threshold → Present (P)
6. Unmatched students → Absent (A)
7. INSERT attendance records
```

### Delete Flow
```
1. Validate session parameter (required)
2. Execute DELETE on target table(s)
3. Log change to database_change_log
4. Return affected row counts
```

---

## Performance Considerations

### Connection Pooling
- Min connections: 2
- Max connections: 10
- Prevents connection overhead

### Vector Index Tuning
- **lists = 100:** Good for datasets up to 100K vectors
- For larger datasets, increase lists: `lists = sqrt(num_vectors)`

### Query Optimization
- Use composite indexes for multi-column queries
- Session-based filtering reduces search space
- Date-based indexes for attendance queries

---

## Backup and Recovery

### Backup Command
```bash
pg_dump -U postgres -d attendance_db > backup.sql
```

### Restore Command
```bash
psql -U postgres -d attendance_db < backup.sql
```

### Vector Data Backup
pgvector data is included in standard pg_dump backups.

---

## Maintenance

### Vacuum and Analyze
```sql
VACUUM ANALYZE students;
VACUUM ANALYZE attendance;
VACUUM ANALYZE database_change_log;
```

### Reindex Vector Index
```sql
REINDEX INDEX idx_students_embedding;
```

### Check Index Usage
```sql
SELECT indexrelname, idx_scan, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes
WHERE schemaname = 'public';
```
