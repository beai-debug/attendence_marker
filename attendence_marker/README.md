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

## Quick Start

### 1. Install PostgreSQL with pgvector

#### Option A: Ubuntu/Debian (Native Installation)

```bash
# Update package list
sudo apt-get update

# Install PostgreSQL
sudo apt-get install -y postgresql postgresql-contrib

# Start PostgreSQL service
sudo service postgresql start

# Install pgvector extension (PostgreSQL 14+)
sudo apt-get install -y postgresql-14-pgvector
# OR for PostgreSQL 16:
# sudo apt-get install -y postgresql-16-pgvector

# Configure PostgreSQL user password
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'Deepdive';"

# Enable password authentication (if needed)
# Edit /etc/postgresql/*/main/pg_hba.conf and change 'peer' to 'md5' for local connections
# Then restart: sudo service postgresql restart
```

#### Option B: macOS with Homebrew

```bash
# Install PostgreSQL and pgvector
brew install postgresql pgvector

# Start PostgreSQL service
brew services start postgresql

# Set password for postgres user
psql -U postgres -c "ALTER USER postgres PASSWORD 'Deepdive';"
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

#### Option D: GitHub Codespaces / Dev Containers

```bash
# Install PostgreSQL
sudo apt-get update
sudo apt-get install -y postgresql postgresql-contrib

# Start PostgreSQL service
sudo service postgresql start

# Set postgres user password
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'Deepdive';"

# Install pgvector from source (if not available via apt)
cd /tmp
git clone --branch v0.7.0 https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install

# Enable pgvector extension (done automatically by the app)
sudo -u postgres psql -d postgres -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

#### Verify PostgreSQL Installation

```bash
# Check PostgreSQL is running
sudo service postgresql status
# OR
pg_isready -h localhost -p 5432

# Test connection
psql -U postgres -h localhost -c "SELECT version();"
```

### 2. Install Python Dependencies

```bash
cd attendence_marker

```
#### create  .venv and activate it 
python3 -m venv .venv

#### Activate .venv
   Windows (PowerShell)

``` bash
 .venv\Scripts\Activate ```

Windows (CMD)

``` bash
.venv\Scripts\activate.bat```


Linux / Mac

``` bash
source .venv/bin/activate ```


pip install -r requirements.txt
```

### 3. Configure Database (Optional)

The system auto-configures with these defaults:
- **Host:** localhost
- **Port:** 5432
- **Database:** attendance_db
- **User:** postgres
- **Password:** Deepdive

To customize, set environment variables:
```bash
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=attendance_db
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=Deepdive
```

### 4. Start the Server

```bash
cd attendence_marker
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

The server will:
1. Automatically create the database if it doesn't exist
2. Enable pgvector extension
3. Create all tables with proper indexes
4. Initialize the face recognition model

### 5. Access API Documentation

Open your browser to: `http://localhost:8000/docs`

## API Endpoints Overview

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

## Enrollment Process

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

## Attendance Marking

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

## Delete Operations

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

## Configuration

### Database Configuration (config.py)
```python
@dataclass
class DatabaseConfig:
    host: str = "localhost"
    port: int = 5432
    database: str = "attendance_db"
    user: str = "postgres"
    password: str = "Deepdive"
    pool_size: int = 10
    vector_dimension: int = 512
```

### Environment Variables
| Variable | Default | Description |
|----------|---------|-------------|
| POSTGRES_HOST | localhost | Database host |
| POSTGRES_PORT | 5432 | Database port |
| POSTGRES_DB | attendance_db | Database name |
| POSTGRES_USER | postgres | Database user |
| POSTGRES_PASSWORD | Deepdive | Database password |
| APP_HOST | 0.0.0.0 | API server host |
| APP_PORT | 8000 | API server port |

## File Structure

```
attendence_marker/
├── app.py                    # FastAPI application
├── database.py               # PostgreSQL + pgvector operations
├── config.py                 # Configuration settings
├── utils.py                  # Utility functions
├── requirements.txt          # Python dependencies
├── README.md                 # This file
├── API_DOCUMENTATION.md      # Detailed API docs
├── DATABASE_STRUCTURE.md     # Database schema docs
├── data/
│   ├── faces/               # Enrolled face images
│   └── attendance_crops/    # Attendance face crops
└── temp_uploads/            # Temporary file storage
```

## Best Practices

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

## Troubleshooting

### Connection Refused Error

If you see this error when starting the application:
```
ERROR:database:Error creating database: connection to server at "localhost" (::1), port 5432 failed: Connection refused
        Is the server running on that host and accepting TCP/IP connections?
```

**Solution:**

1. **Check if PostgreSQL is installed:**
   ```bash
   which psql
   # If not found, install PostgreSQL first (see installation instructions above)
   ```

2. **Start PostgreSQL service:**
   ```bash
   # Linux (systemd)
   sudo systemctl start postgresql
   
   # Linux (service command - for containers)
   sudo service postgresql start
   
   # macOS
   brew services start postgresql
   
   # Docker
   docker start postgres-pgvector
   ```

3. **Verify PostgreSQL is running:**
   ```bash
   # Check service status
   sudo service postgresql status
   
   # Or test connection
   pg_isready -h localhost -p 5432
   
   # Or try connecting
   psql -U postgres -h localhost -c "SELECT 1;"
   ```

4. **Check PostgreSQL is listening on the correct port:**
   ```bash
   # Check listening ports
   sudo netstat -tlnp | grep 5432
   # OR
   sudo ss -tlnp | grep 5432
   ```

5. **If using Docker, ensure the container is running:**
   ```bash
   docker ps | grep postgres
   # If not running:
   docker start postgres-pgvector
   ```

### Database Connection Issues
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql
# OR for containers:
sudo service postgresql status

# Check pgvector extension
psql -U postgres -d attendance_db -c "SELECT * FROM pg_extension WHERE extname = 'vector';"
```

### Authentication Failed Error

If you see "password authentication failed":

1. **Reset postgres password:**
   ```bash
   sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'Deepdive';"
   ```

2. **Check pg_hba.conf authentication method:**
   ```bash
   # Find pg_hba.conf location
   sudo -u postgres psql -c "SHOW hba_file;"
   
   # Edit the file and ensure local connections use md5 or scram-sha-256
   # Change 'peer' to 'md5' for local connections if needed
   sudo nano /etc/postgresql/*/main/pg_hba.conf
   
   # Restart PostgreSQL
   sudo service postgresql restart
   ```

3. **Use environment variables to set custom credentials:**
   ```bash
   export POSTGRES_USER=your_user
   export POSTGRES_PASSWORD=your_password
   ```

### pgvector Extension Not Found

If you see "extension vector does not exist":

1. **Install pgvector from source:**
   ```bash
   cd /tmp
   git clone --branch v0.7.0 https://github.com/pgvector/pgvector.git
   cd pgvector
   make
   sudo make install
   ```

2. **Enable the extension:**
   ```bash
   sudo -u postgres psql -d attendance_db -c "CREATE EXTENSION IF NOT EXISTS vector;"
   ```

### Face Recognition Issues
- Ensure images are clear and well-lit
- Check that faces are not obscured
- Try lowering the threshold value

### Memory Issues
- InsightFace model requires ~2GB RAM
- Consider using GPU for better performance

## License

[Add your license information here]

## Support

For issues and questions:
1. Check the API documentation at `/docs`
2. Review the database change log
3. Use the GitHub issue tracker
