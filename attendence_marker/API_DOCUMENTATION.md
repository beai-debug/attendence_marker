# API Documentation - New Endpoints

## Overview
This document describes the two new endpoints added to the attendance system that support session-based enrollment and gradual embedding updates.

## Database Schema Changes

### Composite Key Structure
Both `students` and `attendance` tables now use a composite primary key:
- **school_name** + **roll_no** + **session**

This allows the same student (roll_no) to exist across different sessions while maintaining data integrity.

### Tables

#### Students Table
```sql
CREATE TABLE students (
    school_name TEXT NOT NULL,
    roll_no TEXT NOT NULL,
    session TEXT NOT NULL,
    name TEXT,
    class_name TEXT,
    section TEXT,
    subject TEXT,
    face_path TEXT,
    embedding BLOB,
    PRIMARY KEY (school_name, roll_no, session)
)
```

#### Attendance Table
```sql
CREATE TABLE attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_name TEXT,
    roll_no TEXT,
    session TEXT,
    student_name TEXT,
    class_name TEXT,
    section TEXT,
    subject TEXT,
    similarity_score REAL,
    status TEXT DEFAULT 'A',
    date TEXT,
    time TEXT
)
```

---

## Endpoint A: `/enroll/`

### Purpose
Register or overwrite student embeddings with session support.

### Method
`POST`

### Required Parameters
- **school_name** (string): School identifier
- **session** (string): Academic session (e.g., "2025-26")
- **faces_zip** (file): ZIP file containing student face images

### Optional Parameters
- **class_name** (string): Class identifier
- **section** (string): Section identifier
- **subject** (string): Subject identifier

### Request Format
```
Content-Type: multipart/form-data

school_name: "JNV_School"
session: "2025-26"
class_name: "10th"
section: "A"
subject: "Mathematics"
faces_zip: <binary file>
```

### ZIP File Structure
The `faces_zip` file should contain folders named in the format: `{roll_no}_{student_name}`

Example:
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
    ├── photo1.jpg
    ├── photo2.jpg
    └── photo3.jpg
```

### Behavior
1. **If student exists** (matching school_name + roll_no + session):
   - Overwrites the existing embedding
   - Updates all student information

2. **If student doesn't exist**:
   - Creates a new record with the provided information
   - Generates embedding from uploaded face images

### Response Format

#### Success Response
```json
{
  "enrolled_students": [
    {
      "roll_no": "21045001",
      "name": "aman_meena",
      "images_processed": 3
    },
    {
      "roll_no": "21045002",
      "name": "rahul_kumar",
      "images_processed": 2
    }
  ],
  "school_name": "JNV_School",
  "session": "2025-26",
  "class_name": "10th",
  "section": "A",
  "subject": "Mathematics",
  "skipped": [
    {
      "folder": "invalid_folder",
      "reason": "Invalid folder name format"
    }
  ]
}
```

### Example cURL Request
```bash
curl -X POST "http://localhost:8000/enroll/" \
  -F "school_name=JNV_School" \
  -F "session=2025-26" \
  -F "class_name=10th" \
  -F "section=A" \
  -F "subject=Mathematics" \
  -F "faces_zip=@students_faces.zip"
```

---

## Endpoint B: `/update-embedding-via-period/`

### Purpose
Gradually update student embeddings using weighted average, allowing embeddings to evolve over time as students' appearances change.

### Method
`POST`

### Required Parameters
- **school_name** (string): School identifier
- **session** (string): Academic session (e.g., "2025-26")
- **alpha** (float): Weight for current embedding (must be < 1)
- **faces_zip** (file): ZIP file containing student face images

### Optional Parameters
- **class_name** (string): Class identifier
- **section** (string): Section identifier
- **subject** (string): Subject identifier

### Request Format
```
Content-Type: multipart/form-data

school_name: "JNV_School"
session: "2025-26"
alpha: 0.7
class_name: "10th"
section: "A"
subject: "Mathematics"
faces_zip: <binary file>
```

### Alpha Parameter
The `alpha` parameter controls how much weight is given to the existing embedding:
- **alpha = 0.9**: 90% old embedding + 10% new embedding (slow update)
- **alpha = 0.7**: 70% old embedding + 30% new embedding (moderate update)
- **alpha = 0.5**: 50% old embedding + 50% new embedding (balanced update)
- **alpha = 0.3**: 30% old embedding + 70% new embedding (fast update)

**Constraint**: alpha must be < 1 (alpha < 1.0)

### Update Formula
```
new_embedding = (current_embedding × alpha) + (new_embedding × (1 - alpha))
```

After calculation, the embedding is L2-normalized to maintain unit length.

### ZIP File Structure
Same as `/enroll/` endpoint - folders named `{roll_no}_{student_name}` containing face images.

### Behavior

1. **If student exists** (matching school_name + roll_no + session):
   - Calculates new embedding from uploaded images
   - Applies weighted average with existing embedding
   - Updates the embedding in database
   - Returns as "updated"

2. **If student doesn't exist**:
   - Creates a new record with the new embedding
   - Uses provided class_name, section, subject (or defaults to "Unknown")
   - Returns as "added"

### Response Format

#### Success Response
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
    },
    {
      "roll_no": "21045002",
      "name": "rahul_kumar",
      "images_processed": 2,
      "action": "updated"
    }
  ],
  "added_students": [
    {
      "roll_no": "21045003",
      "name": "priya_sharma",
      "images_processed": 3,
      "action": "added"
    }
  ],
  "skipped": [
    {
      "folder": "invalid_folder",
      "reason": "No valid face embeddings found"
    }
  ]
}
```

#### Error Response (Invalid Alpha)
```json
{
  "error": "alpha must be less than 1"
}
```

### Example cURL Request
```bash
curl -X POST "http://localhost:8000/update-embedding-via-period/" \
  -F "school_name=JNV_School" \
  -F "session=2025-26" \
  -F "alpha=0.7" \
  -F "class_name=10th" \
  -F "section=A" \
  -F "subject=Mathematics" \
  -F "faces_zip=@updated_faces.zip"
```

---

## Use Cases

### Use Case 1: Initial Enrollment
Use `/enroll/` to register students at the beginning of a session:
```bash
# Enroll students for session 2025-26
POST /enroll/
  school_name: "JNV_School"
  session: "2025-26"
  class_name: "10th"
  section: "A"
  faces_zip: initial_photos.zip
```

### Use Case 2: Mid-Session Update
Use `/update-embedding-via-period/` to gradually update embeddings as students' appearances change:
```bash
# Update embeddings after 3 months (alpha=0.7 means 70% old, 30% new)
POST /update-embedding-via-period/
  school_name: "JNV_School"
  session: "2025-26"
  alpha: 0.7
  class_name: "10th"
  section: "A"
  faces_zip: updated_photos.zip
```

### Use Case 3: Re-enrollment for New Session
Use `/enroll/` with a new session to register the same students for a new academic year:
```bash
# Re-enroll same students for new session 2026-27
POST /enroll/
  school_name: "JNV_School"
  session: "2026-27"
  class_name: "11th"
  section: "A"
  faces_zip: new_session_photos.zip
```

### Use Case 4: Overwrite Incorrect Enrollment
Use `/enroll/` to completely replace embeddings if initial enrollment was incorrect:
```bash
# Overwrite existing embeddings
POST /enroll/
  school_name: "JNV_School"
  session: "2025-26"
  class_name: "10th"
  section: "A"
  faces_zip: corrected_photos.zip
```

---

## Best Practices

### 1. Choosing Alpha Values
- **Start of session**: Use `/enroll/` (no alpha needed)
- **After 1-2 months**: alpha = 0.8-0.9 (minor adjustments)
- **After 3-4 months**: alpha = 0.6-0.7 (moderate changes)
- **After 6+ months**: alpha = 0.4-0.5 (significant changes)

### 2. Image Quality
- Use clear, well-lit face photos
- Include 2-5 images per student for better embedding quality
- Ensure faces are clearly visible and not obscured

### 3. Folder Naming
- Always use format: `{roll_no}_{student_name}`
- Roll numbers should be alphanumeric (letters, numbers, hyphens, underscores)
- Avoid special characters in names

### 4. Session Management
- Use consistent session format (e.g., "2025-26", "2026-27")
- Session allows tracking students across academic years
- Same roll_no can exist in different sessions

### 5. Error Handling
- Check the `skipped` array in responses for failed enrollments
- Common reasons: invalid folder names, no faces detected, poor image quality

---

## Migration Notes

### Existing Data
The database automatically migrates existing data:
- Old records without `session` field are assigned default session "2025-26"
- Composite key is updated to include session
- All existing functionality remains compatible

### Backward Compatibility
- Existing endpoints continue to work
- Default session "2025-26" is used for attendance marking
- No breaking changes to existing API contracts

---

## Error Codes

| Error | Description | Solution |
|-------|-------------|----------|
| "alpha must be less than 1" | Alpha parameter >= 1 | Use alpha < 1 (e.g., 0.7) |
| "alpha must be non-negative" | Alpha parameter < 0 | Use alpha >= 0 |
| "Invalid folder name format" | Folder doesn't match pattern | Use format: `rollno_name` |
| "No valid face embeddings found" | No faces detected in images | Use clearer face photos |
| "Duplicate roll number" | Same roll_no appears twice in ZIP | Remove duplicate folders |

---

## Testing

### Test Endpoint A (Enroll)
```python
import requests

files = {'faces_zip': open('test_faces.zip', 'rb')}
data = {
    'school_name': 'Test_School',
    'session': '2025-26',
    'class_name': '10th',
    'section': 'A'
}

response = requests.post('http://localhost:8000/enroll/', files=files, data=data)
print(response.json())
```

### Test Endpoint B (Update Embedding)
```python
import requests

files = {'faces_zip': open('updated_faces.zip', 'rb')}
data = {
    'school_name': 'Test_School',
    'session': '2025-26',
    'alpha': 0.7,
    'class_name': '10th',
    'section': 'A'
}

response = requests.post('http://localhost:8000/update-embedding-via-period/', files=files, data=data)
print(response.json())
```

---

## Support

For issues or questions:
1. Check the `skipped` array in API responses for specific error messages
2. Verify ZIP file structure matches the expected format
3. Ensure alpha parameter is within valid range (0 <= alpha < 1)
4. Confirm session format is consistent across requests
