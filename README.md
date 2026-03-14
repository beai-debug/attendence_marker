# Attendance Marker System

A production-grade face recognition-based attendance system built with FastAPI, PostgreSQL, and pgvector.

## Overview

This system provides automated attendance marking using facial recognition technology. It supports:
- Multi-school, multi-session student management
- Face recognition-based attendance marking
- Comprehensive attendance reporting and analytics
- Full audit trail with database change logging

## Key Features

### 🏫 Multi-Tenant Architecture
- Support for multiple schools with isolated data
- Session-based student management (e.g., 2025-26, 2026-27)
- Composite primary key: `(school_name, roll_no, session)`

### 👤 Face Recognition
- Uses InsightFace (buffalo_l model) for accurate face detection
- 512-dimensional face embeddings stored in pgvector
- Cosine similarity for face matching
- Configurable similarity threshold

### 📊 PostgreSQL + pgvector
- Production-grade PostgreSQL database
- pgvector extension for efficient vector similarity search
- IVFFlat indexing for fast face matching
- Connection pooling for high performance

### 🔒 Session-Based Delete Operations
- All delete endpoints require `session` parameter
- Prevents accidental cross-session data deletion
- Full audit logging of all changes

## System Requirements

- Python 3.8+
- PostgreSQL 14+ with pgvector extension
- 4GB+ RAM (for face recognition model)
- Linux/macOS/Windows

---

## 🚀 Quick Start Guide

Follow these steps in order to set up and run the application.

---

### Step 1: Clone the Repository and Navigate to Project

```bash
git clone https://github.com/Deep-Dive-Consulting-Pvt-Ltd/attendence_marker.git
cd attendence_marker/attendence_marker
```

---

### Step 2: Create and Activate Python Virtual Environment (.venv)

**This must be done first before installing any dependencies.**

#### Create the virtual environment:
```bash
python3 -m venv .venv
```

#### Activate the virtual environment:

**Linux / macOS:**
```bash
source .venv/bin/activate
```

**Windows (PowerShell):**
```powershell
.venv\Scripts\Activate
```

**Windows (CMD):**
```cmd
.venv\Scripts\activate.bat
```

> ✅ You should see `(.venv)` at the beginning of your terminal prompt when activated.

---

### Step 3: Install Python Dependencies

```bash
pip install -r requirements.txt
```

---

### Step 4: Set Up PostgreSQL Database

#### Option A: Ubuntu/Debian (Native Installation)

```bash
# Update package list
sudo apt-get update

# Install PostgreSQL
sudo apt-get install -y postgresql postgresql-contrib

# Start PostgreSQL service
sudo service postgresql start

# Install pgvector extension for PostgreSQL 16
sudo apt-get install -y postgresql-16-pgvector

# OR for PostgreSQL 14:
# sudo apt-get install -y postgresql-14-pgvector
```

#### Option B: macOS with Homebrew

```bash
# Install PostgreSQL and pgvector
brew install postgresql pgvector

# Start PostgreSQL service
brew services start postgresql
```

#### Option C: Docker (Recommended for Development)

```bash
# Run PostgreSQL with pgvector pre-installed
docker run -d --name postgres-pgvector \
  -e POSTGRES_PASSWORD=Deepdive \
  -p 5432:5432 \
  ankane/pgvector

# Verify it's running
docker ps
```

---

### Step 5: Configure PostgreSQL Authentication

This step is **required** to allow the application to connect to PostgreSQL.

#### 5.1 Run the setup script to generate pg_hba.conf:
```bash
python setup_postgres.py
```

#### 5.2 Copy the generated configuration file:
```bash
sudo cp /tmp/pg_hba_new.conf /etc/postgresql/16/main/pg_hba.conf
```
> Note: Replace `16` with your PostgreSQL version if different (e.g., `14`, `15`).

#### 5.3 Restart PostgreSQL:
```bash
sudo service postgresql restart
```

#### 5.4 Set the postgres user password:
```bash
psql -U postgres -c "ALTER USER postgres PASSWORD 'Deepdive';"
```

#### 5.5 Verify the connection works:
```bash
PGPASSWORD=Deepdive psql -h localhost -U postgres -c "SELECT 1 as test;"
```

You should see:
```
 test 
------
    1
(1 row)
```

---

### Step 6: Start the Application Server

```bash
cd /path/to/attendence_marker/attendence_marker
source .venv/bin/activate  # If not already activated
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

The server will:
1. Automatically create the `attendance_db` database if it doesn't exist
2. Enable pgvector extension
3. Create all tables with proper indexes
4. Initialize the face recognition model (InsightFace buffalo_l)

---

### Step 7: Access API Documentation

Open your browser to: **http://localhost:8000/docs**

---

## 📋 Complete Setup Commands (Copy-Paste Ready)

### For GitHub Codespaces / Linux Dev Containers:

```bash
# Navigate to project directory
cd attendence_marker/attendence_marker

# Step 1: Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Step 2: Install Python dependencies
pip install -r requirements.txt

# Step 3: Install PostgreSQL and pgvector
sudo apt-get update
sudo apt-get install -y postgresql postgresql-contrib
sudo service postgresql start
sudo apt-get install -y postgresql-16-pgvector

# Step 4: Configure PostgreSQL authentication
python setup_postgres.py
sudo cp /tmp/pg_hba_new.conf /etc/postgresql/16/main/pg_hba.conf
sudo service postgresql restart

# Step 5: Set postgres password
psql -U postgres -c "ALTER USER postgres PASSWORD 'Deepdive';"

# Step 6: Verify connection
PGPASSWORD=Deepdive psql -h localhost -U postgres -c "SELECT 1;"

# Step 7: Start the application
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

---

## ⚙️ Configuration

### Default Database Configuration

The system auto-configures with these defaults:
- **Host:** localhost
- **Port:** 5432
- **Database:** attendance_db
- **User:** postgres
- **Password:** Deepdive

### Environment Variables (Optional)

To customize, set environment variables before starting the server:

```bash
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=attendance_db
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=Deepdive
export APP_HOST=0.0.0.0
export APP_PORT=8000
```

| Variable | Default | Description |
|----------|---------|-------------|
| POSTGRES_HOST | localhost | Database host |
| POSTGRES_PORT | 5432 | Database port |
| POSTGRES_DB | attendance_db | Database name |
| POSTGRES_USER | postgres | Database user |
| POSTGRES_PASSWORD | Deepdive | Database password |
| APP_HOST | 0.0.0.0 | API server host |
| APP_PORT | 8000 | API server port |

---

## 📚 API Endpoints Overview

### Enrollment Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/enroll/` | POST | Enroll students with face images |
| `/enroll-new-student/` | POST | Alias for /enroll/ |
| `/enroll-new-batch-with-replacement/` | POST | Enroll with upsert behavior |
| `/update-embedding-via-period/` | POST | Gradually update face embeddings |

### Attendance Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/mark-attendance/` | POST | Mark attendance from photos |
| `/view-attendance-on-date/` | GET | View attendance for specific date |
| `/view-attendance-range/` | GET | View attendance with statistics |

### Delete Endpoints (All Require Session)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/delete-student/` | DELETE | Delete student from both tables |
| `/delete-class/` | DELETE | Delete class data |
| `/delete-student-from-database/` | DELETE | Delete from students only |
| `/delete-student-from-attendance/` | DELETE | Delete attendance only |
| `/delete-student-from-both/` | DELETE | Delete from both tables |
| `/delete-bulk-from-database/` | DELETE | Bulk delete students |
| `/delete-bulk-from-attendance/` | DELETE | Bulk delete attendance |
| `/delete-bulk-from-both/` | DELETE | Bulk delete from both |

### Query Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/enrollment-stats/` | GET | Get enrollment statistics |
| `/view-students/` | GET | Export students as CSV |
| `/database-change-log/` | GET | View audit log |

---

## 📁 Enrollment Process

### ZIP File Structure
```
faces.zip
├── 21045001_aman_meena/
│   ├── photo1.jpg
│   ├── photo2.jpg
│   └── photo3.jpg
├── 21045002_rahul_kumar/
│   ├── photo1.jpg
│   └── photo2.jpg
└── 21045003_priya_sharma/
    └── photo1.jpg
```

### Folder Naming Convention
- Format: `{roll_no}_{student_name}`
- Roll number: Alphanumeric, hyphens, underscores allowed
- Name: Everything after first underscore

### Example Enrollment Request
```bash
curl -X POST "http://localhost:8000/enroll/" \
  -F "school_name=JNV_School" \
  -F "session=2025-26" \
  -F "class_name=10th" \
  -F "section=A" \
  -F "subject=Mathematics" \
  -F "faces_zip=@students.zip"
```

---

## 📸 Attendance Marking

### Process
1. Upload classroom photos as ZIP
2. System detects all faces in photos
3. Matches faces against enrolled students
4. Marks present (P) for matched, absent (A) for unmatched

### Example Request
```bash
curl -X POST "http://localhost:8000/mark-attendance/" \
  -F "school_name=JNV_School" \
  -F "class_name=10th" \
  -F "section=A" \
  -F "photos_zip=@classroom.zip" \
  -F "threshold=0.3"
```

---

## 🗑️ Delete Operations

**Important:** All delete endpoints now require the `session` parameter.

### Delete Single Student
```bash
curl -X DELETE "http://localhost:8000/delete-student/?school_name=JNV_School&roll_no=21045001&session=2025-26"
```

### Delete Class Data
```bash
curl -X DELETE "http://localhost:8000/delete-class/?school_name=JNV_School&class_name=10th&session=2025-26&section=A"
```

### Bulk Delete
```bash
curl -X DELETE "http://localhost:8000/delete-bulk-from-both/?school_name=JNV_School&class_name=10th&section=A&session=2025-26"
```

---

## 📂 File Structure

```
attendence_marker/
├── app.py                    # FastAPI application
├── database.py               # PostgreSQL + pgvector operations
├── config.py                 # Configuration settings
├── utils.py                  # Utility functions
├── setup_postgres.py         # PostgreSQL setup helper script
├── requirements.txt          # Python dependencies
├── README.md                 # This file
├── API_DOCUMENTATION.md      # Detailed API docs
├── DATABASE_STRUCTURE.md     # Database schema docs
├── .venv/                    # Python virtual environment (created by you)
├── data/
│   ├── faces/               # Enrolled face images
│   └── attendance_crops/    # Attendance face crops
└── temp_uploads/            # Temporary file storage
```

---

## 💡 Best Practices

### Image Quality
- Use clear, well-lit face photos
- Minimum 3 images per student recommended
- Supported formats: JPG, JPEG, PNG
- Face should be clearly visible

### Threshold Selection
- Default: 0.3 (30% similarity)
- Higher threshold = stricter matching
- Lower threshold = more lenient matching
- Recommended range: 0.25 - 0.45

### Session Management
- Use consistent session format (e.g., "2025-26")
- Session allows tracking across academic years
- Same roll_no can exist in different sessions

---

## 🔧 Troubleshooting

### Error: "Connection refused"

```
ERROR:database:Error creating database: connection to server at "localhost" (::1), port 5432 failed: Connection refused
```

**Solution:**
```bash
# Start PostgreSQL service
sudo service postgresql start

# Verify it's running
pg_isready -h localhost -p 5432
```

### Error: "Password authentication failed"

```
FATAL: password authentication failed for user "postgres"
```

**Solution:**
```bash
# Run setup script
python setup_postgres.py

# Copy configuration
sudo cp /tmp/pg_hba_new.conf /etc/postgresql/16/main/pg_hba.conf

# Restart PostgreSQL
sudo service postgresql restart

# Set password
psql -U postgres -c "ALTER USER postgres PASSWORD 'Deepdive';"
```

### Error: "Extension vector does not exist"

```
ERROR: extension "vector" must be installed in the system
```

**Solution:**
```bash
# Install pgvector for PostgreSQL 16
sudo apt-get install -y postgresql-16-pgvector

# Restart PostgreSQL
sudo service postgresql restart
```

### Error: "InsightFace model loading issues"

**Solution:**
- Ensure you have at least 4GB RAM available
- The model downloads automatically on first run (~500MB)
- Check internet connectivity for model download

### Virtual Environment Not Activated

If you see errors about missing packages:
```bash
# Make sure you're in the correct directory
cd attendence_marker/attendence_marker

# Activate the virtual environment
source .venv/bin/activate  # Linux/macOS
# OR
.venv\Scripts\Activate     # Windows PowerShell
```

---

## 📖 Additional Documentation

- **API Documentation:** See `API_DOCUMENTATION.md` for detailed endpoint specifications
- **Database Schema:** See `DATABASE_STRUCTURE.md` for table structures
- **Interactive API Docs:** Visit `http://localhost:8000/docs` when server is running

---

## 📄 License

[Add your license information here]

---

## 🆘 Support

For issues and questions:
1. Check the API documentation at `/docs`
2. Review the database change log endpoint
3. Use the GitHub issue tracker
