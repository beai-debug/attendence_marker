# Attendance Marker System

An automated face recognition-based attendance system built with FastAPI and InsightFace.

## Overview

This system allows you to:
- Enroll students with their facial recognition data using roll numbers
- Mark attendance automatically from group photos
- Manage student records and attendance data
- Delete students and class data with fine-grained control
- **View attendance records** for specific dates or date ranges with statistics

## Features

- **Roll Number Based System**: Students are identified by unique roll numbers (primary key)
- **Face Recognition**: Uses InsightFace for accurate face detection and recognition
- **Batch Enrollment**: Upload ZIP files containing student face images
- **Automated Attendance**: Process group photos to mark attendance automatically
- **Flexible Deletion**: Delete students by roll number or entire class data with optional filters
- **Attendance Reports**: View attendance on specific dates or date ranges with statistics
- **CLI Testing Tool**: Test database operations without running the web server

## Recent Updates (March 2026)

### New Attendance Viewing Endpoints ✅
1. **View Attendance on Date** (`GET /view-attendance-on-date/`): Get attendance records for a specific date
2. **View Attendance Range** (`GET /view-attendance-range/`): Get attendance records for a date range with statistics including:
   - Total days
   - Total present/absent
   - Attendance percentage
   - Below 75% indicator

### Previous Updates (November 2025)

#### Critical Bug Fixes ✅
1. **Database Persistence Issue Fixed**: Database no longer resets on multiple uploads or server restarts
2. **Roll Number Validation**: Added proper validation for folder names during enrollment
3. **Duplicate Detection**: System now detects and prevents duplicate roll numbers within same upload
4. **Enhanced Logging**: Comprehensive logging added for debugging enrollment issues

#### Database Schema Changes
- **Roll Number as Primary Key**: Students are now identified by roll numbers instead of names
- **Enhanced Attendance Table**: Stores both roll number and student name with auto-increment ID
- **Database Indexes**: Added indexes for faster queries on attendance records
- **Subject Support**: Optional subject parameter for better organization
- **Data Persistence**: Database now persists across server restarts and multiple uploads

## Installation

### Prerequisites
- Python 3.8+
- pip

### Setup

1. Clone the repository:
```bash
git clone https://github.com/Jatin28sahu/attendence_marker.git
cd attendence_marker
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Initialize the database:
```bash
python -c "from database import init_db; init_db()"
```

## Usage

### Option 1: FastAPI Server

Start the FastAPI server:
```bash
uvicorn app:app --reload
```

Access the API documentation at: `http://localhost:8000/docs`

---

## API Endpoints

### 1. Enroll Students
```http
POST /enroll/
Content-Type: multipart/form-data
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| school_name | string | Yes | School name |
| class_name | string | Yes | Class name |
| section | string | Yes | Section |
| subject | string | No | Subject (optional) |
| faces_zip | file | Yes | ZIP file containing student face images |

**Folder Structure in ZIP:**
```
faces.zip
├── 21045001_aman_meena/
│   ├── image1.jpg
│   ├── image2.jpg
│   └── image3.jpg
├── 21045002_ambuj_yadav/
│   ├── image1.jpg
│   └── image2.jpg
└── 21045003_avinash_sharma/
    └── image1.jpg
```

**Response:**
```json
{
  "enrolled_students": [
    {"roll_no": "21045001", "name": "aman_meena", "images_processed": 5},
    {"roll_no": "21045002", "name": "ambuj_yadav", "images_processed": 3}
  ],
  "school_name": "ABC School",
  "skipped": [
    {"folder": "invalid_folder_name", "reason": "Invalid folder name format"}
  ]
}
```

---

### 2. Mark Attendance
```http
POST /mark-attendance/
Content-Type: multipart/form-data
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| school_name | string | Yes | School name |
| class_name | string | Yes | Class name |
| section | string | Yes | Section |
| subject | string | No | Subject (optional) |
| photos_zip | file | Yes | ZIP file containing classroom photos |
| threshold | float | No | Face match threshold (default: 0.3) |

**Response:**
```json
{
  "school_name": "ABC School",
  "class_name": "10th",
  "section": "A",
  "subject": "Math",
  "date": "2026-02-25",
  "time": "10:30:45.123",
  "total_enrolled": 30,
  "present_count": 25,
  "absent_count": 5,
  "present_students": [
    {"roll_no": "21045001", "name": "aman_meena", "similarity": 0.87, "status": "P"}
  ],
  "absent_students": [
    {"roll_no": "21045002", "name": "ambuj_yadav", "status": "A"}
  ]
}
```

---

### 3. View Attendance on Date (NEW)
```http
GET /view-attendance-on-date/
```

View attendance records for a specific date.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| school_name | string | Yes | School name |
| date | string | Yes | Date in DD-MM-YYYY format |
| roll_no | string | No | Filter by roll number |
| class_name | string | No | Filter by class |
| section | string | No | Filter by section |
| subject | string | No | Filter by subject |

**Example Request:**
```
GET /view-attendance-on-date/?school_name=ABC%20School&date=25-02-2026&class_name=10th&section=A
```

**Response:**
```json
{
  "total_records": 3,
  "date": "25-02-2026",
  "school_name": "ABC School",
  "data": [
    {
      "date": "25-02-2026",
      "school": "ABC School",
      "roll_number": "21045001",
      "name": "aman_meena",
      "class": "10th",
      "subject": "Math",
      "section": "A",
      "attendance_record": "P"
    },
    {
      "date": "25-02-2026",
      "school": "ABC School",
      "roll_number": "21045002",
      "name": "ambuj_yadav",
      "class": "10th",
      "subject": "Math",
      "section": "A",
      "attendance_record": "A"
    }
  ]
}
```

**Attendance Record Values:**
- `P` = Present
- `A` = Absent

---

### 4. View Attendance Range (NEW)
```http
GET /view-attendance-range/
```

View overall attendance records for a date range with statistics.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| school_name | string | Yes | School name |
| start_date | string | Yes | Start date in DD-MM-YYYY format (inclusive) |
| end_date | string | Yes | End date in DD-MM-YYYY format (inclusive) |
| roll_no | string | No | Filter by roll number |
| class_name | string | No | Filter by class |
| section | string | No | Filter by section |
| subject | string | No | Filter by subject |

**Example Request:**
```
GET /view-attendance-range/?school_name=ABC%20School&start_date=25-02-2026&end_date=28-02-2026&class_name=10th&section=A
```

**Response:**
```json
{
  "total_students": 3,
  "date_range": {
    "start_date": "25-02-2026",
    "end_date": "28-02-2026",
    "total_days": 4
  },
  "dates": ["25-02-2026", "26-02-2026", "27-02-2026", "28-02-2026"],
  "school_name": "ABC School",
  "data": [
    {
      "school": "ABC School",
      "roll_number": "21045001",
      "name": "aman_meena",
      "class": "10th",
      "subject": "Math",
      "section": "A",
      "25-02-2026": "P",
      "26-02-2026": "P",
      "27-02-2026": "A",
      "28-02-2026": "P",
      "total_days": 4,
      "total_present": 3,
      "total_absent": 1,
      "attendance_percentage": 75.0,
      "below_75_percent": "No"
    },
    {
      "school": "ABC School",
      "roll_number": "21045002",
      "name": "ambuj_yadav",
      "class": "10th",
      "subject": "Math",
      "section": "A",
      "25-02-2026": "A",
      "26-02-2026": "P",
      "27-02-2026": "A",
      "28-02-2026": "A",
      "total_days": 4,
      "total_present": 1,
      "total_absent": 3,
      "attendance_percentage": 25.0,
      "below_75_percent": "Yes"
    }
  ]
}
```

**Statistics Columns:**
| Column | Type | Description |
|--------|------|-------------|
| total_days | int | Total number of days in the range |
| total_present | int | Number of days marked Present (P) |
| total_absent | int | Number of days marked Absent (A) |
| attendance_percentage | float | (total_present / total_days) × 100 |
| below_75_percent | string | "Yes" if percentage < 75%, else "No" |

---

### 5. View Students
```http
GET /view-students/
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| school_name | string | Yes | School name |
| class_name | string | No | Filter by class |
| section | string | No | Filter by section |
| subject | string | No | Filter by subject |

**Response:** CSV file download with columns: school, roll_number, name, class, section, subject

---

### 6. Enrollment Stats
```http
GET /enrollment-stats/
```

Get total enrollment numbers grouped by school, class, section, and subject.

---

### 7. Delete Student
```http
DELETE /delete-student/?school_name=ABC%20School&roll_no=21045001
```

---

### 8. Delete Class
```http
DELETE /delete-class/?school_name=ABC%20School&class_name=10th&section=A&subject=Math
```

---

### 9. Advanced Delete Endpoints

| Endpoint | Description |
|----------|-------------|
| `DELETE /delete-student-from-database/` | Delete student from database only (keeps attendance) |
| `DELETE /delete-student-from-attendance/` | Delete attendance records only (keeps student) |
| `DELETE /delete-student-from-both/` | Delete from both tables |
| `DELETE /delete-bulk-from-database/` | Bulk delete students from database |
| `DELETE /delete-bulk-from-attendance/` | Bulk delete attendance records |
| `DELETE /delete-bulk-from-both/` | Bulk delete from both tables |

---

## Database Schema

### Students Table
| Column | Type | Description |
|--------|------|-------------|
| school_name | TEXT | School name (part of composite key) |
| roll_no | TEXT | Student roll number (part of composite key) |
| name | TEXT | Student name |
| class_name | TEXT | Class name |
| section | TEXT | Section |
| subject | TEXT | Subject (optional) |
| face_path | TEXT | Path to face images |
| embedding | BLOB | Face embedding vector (512-dim) |

**Primary Key:** (school_name, roll_no)

### Attendance Table
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Auto-increment primary key |
| school_name | TEXT | School name |
| roll_no | TEXT | Student roll number |
| student_name | TEXT | Student name |
| class_name | TEXT | Class name |
| section | TEXT | Section |
| subject | TEXT | Subject (optional) |
| similarity_score | REAL | Face match confidence |
| status | TEXT | 'P' (Present) or 'A' (Absent) |
| date | TEXT | Attendance date (YYYY-MM-DD) |
| time | TEXT | Attendance time |

---

## File Structure

```
attendence_marker/
├── app.py                 # FastAPI application
├── database.py            # Database operations
├── main.py                # CLI testing tool
├── utils.py               # Utility functions
├── requirements.txt       # Python dependencies
├── README.md              # This file
├── attendance.db          # SQLite database (auto-generated)
├── data/
│   ├── faces/             # Enrolled face images
│   └── attendance_crops/  # Attendance face crops
└── temp_uploads/          # Temporary file storage
```

---

## Date Format

All date inputs and outputs use the **DD-MM-YYYY** format:
- Input: `25-02-2026`
- Output: `25-02-2026`

The database internally stores dates in YYYY-MM-DD format, but the API handles conversion automatically.

---

## Important Notes

### Roll Number Format
- Roll numbers are parsed from folder names using the format: `{roll_no}_{name}`
- Example: `21045001_aman_meena` → Roll No: `21045001`, Name: `aman_meena`

### Face Recognition
- Minimum 3 images per student recommended for better accuracy
- Images should be clear, well-lit, and show the face clearly
- Supported formats: JPG, JPEG, PNG

### Attendance Status
- **P** = Present (student detected in photo)
- **A** = Absent (student not detected in photo)

### Attendance Percentage
- Calculated as: `(total_present / total_days) × 100`
- Students with less than 75% attendance are flagged with `below_75_percent: "Yes"`

---

## CLI Testing Tool

For quick testing without running the FastAPI server:

```bash
python main.py
```

**Available Operations:**
1. View all students
2. View students by class/section/subject
3. View all attendance records
4. View attendance by class/section
5. Add sample student (for testing)
6. Delete student by roll number
7. Delete class data
8. Clear all data (reset database)
9. Exit

---

## Troubleshooting

### Common Issues

1. **"Invalid date format" error**
   - Ensure date is in DD-MM-YYYY format (e.g., `25-02-2026`)
   - Use dashes (-) as separators, not slashes (/)

2. **"No attendance records found"**
   - Verify the date range contains attendance data
   - Check that school_name matches exactly (case-sensitive)

3. **"Student not found" when deleting**
   - Verify the roll number exists using the CLI tool
   - Roll numbers are case-sensitive

4. **Face not recognized during attendance**
   - Ensure good quality enrollment images
   - Adjust the `threshold` parameter (lower = more lenient)
   - Default threshold is 0.3

5. **Database locked errors**
   - Ensure only one process is accessing the database at a time
   - Close the CLI tool before running the FastAPI server

---

## API Testing

Use FastAPI's built-in docs:
```bash
uvicorn app:app --reload
# Visit http://localhost:8000/docs
```

---

## Changelog

### Version 3.0 (March 2026) - Latest
- Added `GET /view-attendance-on-date/` endpoint
- Added `GET /view-attendance-range/` endpoint with statistics
- Attendance percentage calculation
- Below 75% attendance indicator
- Date format standardized to DD-MM-YYYY

### Version 2.0 (November 2025)
- Added roll number as primary key
- Enhanced delete operations with subject support
- Created CLI testing tool
- Improved folder name parsing for enrollment

### Version 1.0
- Initial release
- Basic enrollment and attendance functionality

---

## License

[Add your license information here]

## Contact

For issues and questions, please use the GitHub issue tracker.
