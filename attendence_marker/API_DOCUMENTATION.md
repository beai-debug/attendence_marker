# API Documentation

## Attendance Marker System - Complete API Reference

**Base URL:** `http://localhost:8000`  
**API Version:** 2.0.0  
**Documentation:** `/docs` (Swagger UI) or `/redoc` (ReDoc)

---

## Table of Contents

1. [Enrollment Endpoints](#enrollment-endpoints)
2. [Attendance Endpoints](#attendance-endpoints)
3. [Delete Endpoints](#delete-endpoints-all-require-session)
4. [Query Endpoints](#query-endpoints)
5. [Database Change Log](#database-change-log)
6. [Error Handling](#error-handling)

---

## Enrollment Endpoints

### POST `/enroll/`

Enroll students by uploading a ZIP file containing student face images.

**Request:**
```
Content-Type: multipart/form-data
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| school_name | string | ✅ Yes | School identifier |
| session | string | ✅ Yes | Academic session (e.g., "2025-26") |
| class_name | string | ❌ No | Class name |
| section | string | ❌ No | Section |
| subject | string | ❌ No | Subject |
| faces_zip | file | ✅ Yes | ZIP file with student folders |

**ZIP File Structure:**
```
faces.zip
├── 21045001_aman_meena/
│   ├── photo1.jpg
│   ├── photo2.jpg
│   └── photo3.jpg
├── 21045002_rahul_kumar/
│   └── photo1.jpg
```

**Response (200 OK):**
```json
{
  "enrolled_students": [
    {
      "roll_no": "21045001",
      "name": "aman_meena",
      "images_processed": 3
    }
  ],
  "school_name": "JNV_School",
  "session": "2025-26",
  "class_name": "10th",
  "section": "A",
  "subject": "Mathematics",
  "endpoint": "/enroll/",
  "skipped": [
    {
      "folder": "invalid_folder",
      "reason": "Invalid folder name format"
    }
  ]
}
```

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/enroll/" \
  -F "school_name=JNV_School" \
  -F "session=2025-26" \
  -F "class_name=10th" \
  -F "section=A" \
  -F "faces_zip=@students.zip"
```

---

### POST `/enroll-new-student/`

Alias for `/enroll/` - Same functionality.

---

### POST `/enroll-new-batch-with-replacement/`

Enroll students with upsert behavior (INSERT OR REPLACE).

Same parameters as `/enroll/`. Existing students with matching composite key will be updated.

---

### POST `/update-embedding-via-period/`

Gradually update student embeddings using weighted average.

**Formula:** `new_embedding = (current_embedding × alpha) + (new_embedding × (1 - alpha))`

**Request:**
```
Content-Type: multipart/form-data
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| school_name | string | ✅ Yes | School identifier |
| session | string | ✅ Yes | Academic session |
| alpha | float | ✅ Yes | Weight for current embedding (0 ≤ alpha < 1) |
| class_name | string | ❌ No | Class name |
| section | string | ❌ No | Section |
| subject | string | ❌ No | Subject |
| faces_zip | file | ✅ Yes | ZIP file with student photos |

**Alpha Values Guide:**
| Alpha | Effect |
|-------|--------|
| 0.9 | 90% old + 10% new (slow update) |
| 0.7 | 70% old + 30% new (moderate) |
| 0.5 | 50% old + 50% new (balanced) |
| 0.3 | 30% old + 70% new (fast update) |

**Response (200 OK):**
```json
{
  "school_name": "JNV_School",
  "session": "2025-26",
  "alpha": 0.7,
  "updated_count": 2,
  "added_count": 1,
  "updated_students": [
    {
      "roll_no": "21045001",
      "name": "aman_meena",
      "images_processed": 3,
      "action": "updated"
    }
  ],
  "added_students": [
    {
      "roll_no": "21045003",
      "name": "new_student",
      "images_processed": 2,
      "action": "added"
    }
  ]
}
```

---

## Attendance Endpoints

### POST `/mark-attendance/`

Mark attendance for enrolled students based on classroom photos.

**Request:**
```
Content-Type: multipart/form-data
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| school_name | string | ✅ Yes | School identifier |
| class_name | string | ✅ Yes | Class name |
| section | string | ✅ Yes | Section |
| subject | string | ❌ No | Subject |
| photos_zip | file | ✅ Yes | ZIP file with classroom photos |
| threshold | float | ❌ No | Face match threshold (default: 0.3) |

**Response (200 OK):**
```json
{
  "school_name": "JNV_School",
  "class_name": "10th",
  "section": "A",
  "subject": "Mathematics",
  "date": "2026-03-04",
  "time": "10:30:45.123",
  "total_enrolled": 30,
  "present_count": 25,
  "absent_count": 5,
  "present_students": [
    {
      "roll_no": "21045001",
      "name": "aman_meena",
      "similarity": 0.87,
      "status": "P"
    }
  ],
  "absent_students": [
    {
      "roll_no": "21045002",
      "name": "rahul_kumar",
      "status": "A"
    }
  ]
}
```

---

### GET `/view-attendance-on-date/`

View attendance records for a specific date.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| school_name | string | ✅ Yes | School identifier |
| date | string | ✅ Yes | Date in DD-MM-YYYY format |
| roll_no | string | ❌ No | Filter by roll number |
| class_name | string | ❌ No | Filter by class |
| section | string | ❌ No | Filter by section |
| subject | string | ❌ No | Filter by subject |

**Response (200 OK):**
```json
{
  "total_records": 30,
  "date": "04-03-2026",
  "school_name": "JNV_School",
  "data": [
    {
      "date": "04-03-2026",
      "school": "JNV_School",
      "roll_number": "21045001",
      "name": "aman_meena",
      "class": "10th",
      "subject": "Mathematics",
      "section": "A",
      "attendance_record": "P"
    }
  ]
}
```

---

### GET `/view-attendance-range/`

View attendance records for a date range with statistics.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| school_name | string | ✅ Yes | School identifier |
| start_date | string | ✅ Yes | Start date (DD-MM-YYYY, inclusive) |
| end_date | string | ✅ Yes | End date (DD-MM-YYYY, inclusive) |
| roll_no | string | ❌ No | Filter by roll number |
| class_name | string | ❌ No | Filter by class |
| section | string | ❌ No | Filter by section |
| subject | string | ❌ No | Filter by subject |

**Response (200 OK):**
```json
{
  "total_students": 30,
  "date_range": {
    "start_date": "01-03-2026",
    "end_date": "04-03-2026",
    "total_days": 4
  },
  "dates": ["01-03-2026", "02-03-2026", "03-03-2026", "04-03-2026"],
  "school_name": "JNV_School",
  "data": [
    {
      "school": "JNV_School",
      "roll_number": "21045001",
      "name": "aman_meena",
      "class": "10th",
      "subject": "Mathematics",
      "section": "A",
      "01-03-2026": "P",
      "02-03-2026": "P",
      "03-03-2026": "A",
      "04-03-2026": "P",
      "total_days": 4,
      "total_present": 3,
      "total_absent": 1,
      "attendance_percentage": 75.0,
      "below_75_percent": "No"
    }
  ]
}
```

---

## Delete Endpoints (All Require Session)

> ⚠️ **Important:** All delete endpoints require the `session` parameter to prevent accidental cross-session data deletion.

### DELETE `/delete-student/`

Delete a student from both students and attendance tables.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| school_name | string | ✅ Yes | School identifier |
| roll_no | string | ✅ Yes | Student roll number |
| session | string | ✅ Yes | Academic session (e.g., "2025-26") |

**Response (200 OK):**
```json
{
  "message": "Student with roll number 21045001 from school JNV_School, session 2025-26 deleted successfully",
  "school_name": "JNV_School",
  "roll_no": "21045001",
  "session": "2025-26"
}
```

**cURL Example:**
```bash
curl -X DELETE "http://localhost:8000/delete-student/?school_name=JNV_School&roll_no=21045001&session=2025-26"
```

---

### DELETE `/delete-class/`

Delete class data by school, class, and session.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| school_name | string | ✅ Yes | School identifier |
| class_name | string | ✅ Yes | Class name |
| session | string | ✅ Yes | Academic session |
| section | string | ❌ No | Filter by section |
| subject | string | ❌ No | Filter by subject |

**Response (200 OK):**
```json
{
  "message": "Deleted data for school JNV_School, class 10th, session 2025-26, section A",
  "school_name": "JNV_School",
  "class_name": "10th",
  "session": "2025-26",
  "section": "A",
  "subject": null
}
```

---

### DELETE `/delete-student-from-database/`

Delete a student from the students table only (preserves attendance records).

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| school_name | string | ✅ Yes | School identifier |
| roll_no | string | ✅ Yes | Student roll number |
| session | string | ✅ Yes | Academic session |

**Response (200 OK):**
```json
{
  "message": "Student deleted from database successfully",
  "deleted_student": {
    "school_name": "JNV_School",
    "roll_no": "21045001",
    "session": "2025-26",
    "name": "aman_meena",
    "class_name": "10th",
    "section": "A",
    "subject": "Mathematics"
  }
}
```

---

### DELETE `/delete-student-from-attendance/`

Delete a student's attendance records only (preserves student database record).

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| school_name | string | ✅ Yes | School identifier |
| roll_no | string | ✅ Yes | Student roll number |
| session | string | ✅ Yes | Academic session |

**Response (200 OK):**
```json
{
  "message": "Student attendance records deleted successfully",
  "deleted_info": {
    "roll_no": "21045001",
    "school_name": "JNV_School",
    "session": "2025-26",
    "attendance_records_deleted": 45,
    "name": "aman_meena",
    "class_name": "10th",
    "section": "A"
  }
}
```

---

### DELETE `/delete-student-from-both/`

Delete a student from both students and attendance tables.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| school_name | string | ✅ Yes | School identifier |
| roll_no | string | ✅ Yes | Student roll number |
| session | string | ✅ Yes | Academic session |

**Response (200 OK):**
```json
{
  "message": "Student deleted from both database and attendance records",
  "deleted_info": {
    "roll_no": "21045001",
    "school_name": "JNV_School",
    "session": "2025-26",
    "deleted_from_database": true,
    "attendance_records_deleted": 45,
    "name": "aman_meena",
    "class_name": "10th",
    "section": "A"
  }
}
```

---

### DELETE `/delete-bulk-from-database/`

Bulk delete students from database only.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| school_name | string | ✅ Yes | School identifier |
| class_name | string | ✅ Yes | Class name |
| section | string | ✅ Yes | Section |
| session | string | ✅ Yes | Academic session |
| subject | string | ❌ No | Filter by subject |

**Response (200 OK):**
```json
{
  "message": "Bulk delete from database successful",
  "filter": "school=JNV_School, class=10th, section=A, session=2025-26",
  "students_deleted": 30
}
```

---

### DELETE `/delete-bulk-from-attendance/`

Bulk delete attendance records only.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| school_name | string | ✅ Yes | School identifier |
| class_name | string | ✅ Yes | Class name |
| section | string | ✅ Yes | Section |
| session | string | ✅ Yes | Academic session |
| subject | string | ❌ No | Filter by subject |

**Response (200 OK):**
```json
{
  "message": "Bulk delete from attendance successful",
  "filter": "school=JNV_School, class=10th, section=A, session=2025-26",
  "attendance_records_deleted": 1350
}
```

---

### DELETE `/delete-bulk-from-both/`

Bulk delete from both students and attendance tables.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| school_name | string | ✅ Yes | School identifier |
| class_name | string | ✅ Yes | Class name |
| section | string | ✅ Yes | Section |
| session | string | ✅ Yes | Academic session |
| subject | string | ❌ No | Filter by subject |

**Response (200 OK):**
```json
{
  "message": "Bulk delete from both database and attendance successful",
  "filter": "school=JNV_School, class=10th, section=A, session=2025-26",
  "students_deleted": 30,
  "attendance_records_deleted": 1350
}
```

---

## Query Endpoints

### GET `/enrollment-stats/`

Get enrollment statistics grouped by school, class, section, and subject.

**Response (200 OK):**
```json
{
  "total_students": 500,
  "by_school": [
    {
      "school_name": "JNV_School",
      "total": 300,
      "by_class": [
        {
          "class_name": "10th",
          "total": 100,
          "by_section": [
            {
              "section": "A",
              "total": 50,
              "by_subject": [
                {"subject": "Mathematics", "count": 50}
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

---

### GET `/view-students/`

Export students as CSV file.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| school_name | string | ✅ Yes | School identifier |
| class_name | string | ❌ No | Filter by class |
| section | string | ❌ No | Filter by section |
| subject | string | ❌ No | Filter by subject |

**Response:** CSV file download with columns:
- school, roll_number, name, class, section, subject

---

## Database Change Log

### GET `/database-change-log/`

View audit log of all database changes.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| school_name | string | ⚡ At least one | School identifier |
| roll_no | string | ⚡ At least one | Roll number |
| session | string | ⚡ At least one | Academic session |
| class_name | string | ❌ No | Filter by class |
| section | string | ❌ No | Filter by section |
| subject | string | ❌ No | Filter by subject |
| change_type | string | ❌ No | Filter: insert, update, delete, embedding_update |
| start_date | string | ❌ No | Start date (YYYY-MM-DD) |
| end_date | string | ❌ No | End date (YYYY-MM-DD) |
| format | string | ❌ No | Output: "json" (default) or "csv" |

**Response (200 OK):**
```json
{
  "total_records": 150,
  "filters": {
    "school_name": "JNV_School",
    "session": "2025-26"
  },
  "data": [
    {
      "school_name": "JNV_School",
      "class_name": "10th",
      "section": "A",
      "subject": "Mathematics",
      "roll_no": "21045001",
      "session": "2025-26",
      "change_type": "insert",
      "endpoint_name": "/enroll/",
      "details": "Enrolled student: aman_meena with 3 images",
      "timestamp": "2026-03-04 10:30:45.123"
    }
  ]
}
```

---

## Error Handling

### Common Error Responses

**Student Not Found:**
```json
{
  "error": "Student not found",
  "school_name": "JNV_School",
  "roll_no": "21045001",
  "session": "2025-26"
}
```

**Invalid Date Format:**
```json
{
  "error": "Invalid date format. Please use DD-MM-YYYY format (e.g., 25-02-2026)"
}
```

**No Data Found:**
```json
{
  "error": "No students found matching the criteria"
}
```

**Missing Required Parameter:**
```json
{
  "error": "At least one of school_name, roll_no, or session is required"
}
```

**Invalid Alpha Value:**
```json
{
  "error": "alpha must be less than 1"
}
```

---

## Date Formats

| Context | Format | Example |
|---------|--------|---------|
| API Input/Output | DD-MM-YYYY | 04-03-2026 |
| Database Storage | YYYY-MM-DD | 2026-03-04 |
| Change Log Filter | YYYY-MM-DD | 2026-03-04 |

---

## Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad Request (invalid parameters) |
| 404 | Not Found |
| 422 | Validation Error |
| 500 | Internal Server Error |

---

## Rate Limiting

No rate limiting is implemented by default. For production deployments, consider adding rate limiting middleware.

---

## Authentication

No authentication is implemented by default. For production deployments, consider adding JWT or API key authentication.
