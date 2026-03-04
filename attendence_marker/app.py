"""
Production-Grade FastAPI Attendance Marker System
Using PostgreSQL + pgvector for face recognition and attendance management.
"""

from fastapi import FastAPI, UploadFile, Form, File, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import Optional
import shutil
import os
from insightface.app import FaceAnalysis
import cv2
import numpy as np
from database import (
    init_db, 
    save_student, 
    get_students, 
    save_attendance, 
    delete_student_by_roll_no, 
    delete_class_data,
    get_enrollment_stats,
    get_students_for_export,
    get_all_students_for_attendance,
    delete_student_from_database_only,
    delete_student_from_attendance_only,
    delete_student_from_both,
    delete_bulk_from_database,
    delete_bulk_from_attendance,
    delete_bulk_from_both_tables,
    get_attendance_on_date,
    get_attendance_in_range,
    get_student_embedding,
    update_student_embedding,
    get_students_by_filters,
    log_database_change,
    get_database_change_log,
    get_change_log_as_csv,
    close_pool
)
from utils import l2_normalize
import tempfile
import zipfile
from pathlib import Path
from datetime import datetime
import logging
import re
import io
import csv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Attendance Marker API",
    description="Production-grade face recognition attendance system using PostgreSQL + pgvector",
    version="2.0.0"
)

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    logger.info("Initializing PostgreSQL database with pgvector...")
    init_db()
    logger.info("Database initialized successfully")

# Cleanup on shutdown
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Closing database connection pool...")
    close_pool()
    logger.info("Database connection pool closed")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMP_DIR = "temp_uploads"
os.makedirs(TEMP_DIR, exist_ok=True)

DATA_DIR = "data"
FACES_DIR = os.path.join(DATA_DIR, "faces")
ATTENDANCE_CROPS_DIR = os.path.join(DATA_DIR, "attendance_crops")
os.makedirs(FACES_DIR, exist_ok=True)
os.makedirs(ATTENDANCE_CROPS_DIR, exist_ok=True)

# Initialize face recognition model
logger.info("Loading InsightFace model...")
face_app = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])
face_app.prepare(ctx_id=0, det_size=(640, 640))
logger.info("InsightFace model loaded successfully")


def validate_roll_no(roll_no: str) -> bool:
    """
    Validate roll number format.
    Accepts alphanumeric characters, hyphens, and underscores.
    """
    if not roll_no:
        return False
    # Allow alphanumeric, hyphens, and underscores
    pattern = r'^[a-zA-Z0-9\-_]+$'
    return bool(re.match(pattern, roll_no))


def parse_student_folder_name(folder_name: str):
    """
    Parse student folder name to extract roll number and name.
    Expected format: {roll_no}_{name}
    Example: 21045001_aman_meena
    
    Returns:
        tuple: (roll_no, name) or (None, None) if parsing fails
    """
    # Split on first underscore
    parts = folder_name.split('_', 1)
    
    if len(parts) < 2:
        logger.warning(f"Skipping folder '{folder_name}': Does not contain underscore separator")
        return None, None
    
    roll_no = parts[0].strip()
    name = parts[1].strip()
    
    # Validate roll_no
    if not validate_roll_no(roll_no):
        logger.warning(f"Skipping folder '{folder_name}': Invalid roll number format '{roll_no}'")
        return None, None
    
    if not name:
        logger.warning(f"Skipping folder '{folder_name}': Empty name after roll number")
        return None, None
    
    return roll_no, name

# ==================== HELPER FUNCTION FOR ENROLLMENT ====================

async def _process_enrollment(
    school_name: str,
    session: str,
    class_name: Optional[str],
    section: Optional[str],
    subject: Optional[str],
    faces_zip: UploadFile,
    endpoint_name: str
):
    """
    Common enrollment processing logic used by all enrollment endpoints.
    """
    logger.info(f"Starting enrollment ({endpoint_name}) for school={school_name}, session={session}, class={class_name}, section={section}, subject={subject}")
    
    # Create temp directory for processing
    temp_dir = tempfile.mkdtemp(dir=TEMP_DIR)
    zip_path = os.path.join(temp_dir, "upload.zip")
    
    # Save and extract zip file
    with open(zip_path, "wb") as f:
        shutil.copyfileobj(faces_zip.file, f)
    
    # Extract to faces directory with school name, class name and section
    class_dir = os.path.join(FACES_DIR, f"{school_name}_{class_name}_{section}")
    os.makedirs(class_dir, exist_ok=True)
    
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(class_dir)
    
    enrolled = []
    skipped = []
    processed_roll_nos = set()
    
    # Process each student directory
    for student_dir in os.listdir(class_dir):
        full_student_path = os.path.join(class_dir, student_dir)
        if not os.path.isdir(full_student_path):
            continue
        
        # Parse and validate folder name
        roll_no, name = parse_student_folder_name(student_dir)
        if roll_no is None or name is None:
            skipped.append({"folder": student_dir, "reason": "Invalid folder name format"})
            continue
        
        # Check for duplicate roll numbers in this upload
        if roll_no in processed_roll_nos:
            logger.warning(f"Duplicate roll number '{roll_no}' found in folder '{student_dir}'. Skipping.")
            skipped.append({"folder": student_dir, "reason": f"Duplicate roll number: {roll_no}"})
            continue
        
        processed_roll_nos.add(roll_no)
            
        emb_list = []
        img_count = 0
        
        # Use full path when listing files
        for img_file in os.listdir(full_student_path):
            if not img_file.lower().endswith(('.jpg', '.jpeg', '.png')):
                continue
            
            img_count += 1
            img_path = os.path.join(full_student_path, img_file)
            img = cv2.imread(img_path)
            if img is None:
                logger.warning(f"Could not read image: {img_path}")
                continue
                
            faces = face_app.get(img)
            if not faces:
                logger.warning(f"No face detected in image: {img_path}")
                continue
                
            f = max(faces, key=lambda x: (x.bbox[2]-x.bbox[0])*(x.bbox[3]-x.bbox[1]))
            emb = l2_normalize(f.embedding)
            emb_list.append(emb)
        
        if not emb_list:
            logger.warning(f"No valid face embeddings for student '{roll_no}' ({name}). Processed {img_count} images.")
            skipped.append({"folder": student_dir, "reason": "No valid face embeddings found"})
            continue
            
        # Ensure proper stacking and normalization of embeddings
        emb_stack = np.stack([np.array(e, dtype=np.float32) for e in emb_list], axis=0)
        mean_emb = l2_normalize(np.mean(emb_stack, axis=0))
        save_student(school_name, roll_no, session, name, class_name, section, subject, full_student_path, mean_emb)
        
        # Log the database change
        log_database_change(
            school_name=school_name,
            class_name=class_name,
            section=section,
            subject=subject,
            roll_no=roll_no,
            session=session,
            change_type="insert",
            endpoint_name=endpoint_name,
            details=f"Enrolled student: {name} with {len(emb_list)} images"
        )
        
        logger.info(f"Successfully enrolled: {roll_no} - {name} (from {len(emb_list)} images)")
        enrolled.append({"roll_no": roll_no, "name": name, "images_processed": len(emb_list)})
    
    # Cleanup temp directory
    shutil.rmtree(temp_dir)
    
    logger.info(f"Enrollment complete ({endpoint_name}): {len(enrolled)} students enrolled, {len(skipped)} skipped")
    
    result = {
        "enrolled_students": enrolled, 
        "school_name": school_name,
        "session": session,
        "class_name": class_name,
        "section": section,
        "subject": subject,
        "endpoint": endpoint_name
    }
    if skipped:
        result["skipped"] = skipped
    
    return result


@app.post("/enroll/")
async def enroll_students(
    school_name: str = Form(...),
    session: str = Form(...),
    class_name: Optional[str] = Form(None),
    section: Optional[str] = Form(None),
    subject: Optional[str] = Form(None),
    faces_zip: UploadFile = File(...)
):
    """
    Enroll students by uploading a ZIP file containing student face images.
    
    **Required:**
    - school_name: School identifier
    - session: Academic session (e.g., 2025-26)
    - faces_zip: ZIP file with student folders (format: rollno_name/images)
    
    **Optional:**
    - class_name, section, subject: Classification fields
    """
    return await _process_enrollment(
        school_name=school_name,
        session=session,
        class_name=class_name,
        section=section,
        subject=subject,
        faces_zip=faces_zip,
        endpoint_name="/enroll/"
    )


@app.post("/enroll-new-student/")
async def enroll_new_student(
    school_name: str = Form(...),
    session: str = Form(...),
    class_name: Optional[str] = Form(None),
    section: Optional[str] = Form(None),
    subject: Optional[str] = Form(None),
    faces_zip: UploadFile = File(...)
):
    """
    Enroll new student(s) - Same functionality as /enroll/ endpoint.
    
    **Required:**
    - school_name: School identifier
    - session: Academic session (e.g., 2025-26)
    - faces_zip: ZIP file with student folders (format: rollno_name/images)
    
    **Optional:**
    - class_name, section, subject: Classification fields
    
    This endpoint is an alias for /enroll/ with the same input and functionality.
    """
    return await _process_enrollment(
        school_name=school_name,
        session=session,
        class_name=class_name,
        section=section,
        subject=subject,
        faces_zip=faces_zip,
        endpoint_name="/enroll-new-student/"
    )


@app.post("/enroll-new-batch-with-replacement/")
async def enroll_new_batch_with_replacement(
    school_name: str = Form(...),
    session: str = Form(...),
    class_name: Optional[str] = Form(None),
    section: Optional[str] = Form(None),
    subject: Optional[str] = Form(None),
    faces_zip: UploadFile = File(...)
):
    """
    Enroll new batch with replacement - Same functionality as /enroll/ endpoint.
    
    **Required:**
    - school_name: School identifier
    - session: Academic session (e.g., 2025-26)
    - faces_zip: ZIP file with student folders (format: rollno_name/images)
    
    **Optional:**
    - class_name, section, subject: Classification fields
    
    This endpoint is an alias for /enroll/ with the same input and functionality.
    Uses INSERT OR REPLACE to update existing students with same composite key.
    """
    return await _process_enrollment(
        school_name=school_name,
        session=session,
        class_name=class_name,
        section=section,
        subject=subject,
        faces_zip=faces_zip,
        endpoint_name="/enroll-new-batch-with-replacement/"
    )


@app.post("/update-embedding-via-period/")
async def update_embedding_via_period(
    school_name: str = Form(...),
    session: str = Form(...),
    alpha: float = Form(...),
    class_name: Optional[str] = Form(None),
    section: Optional[str] = Form(None),
    subject: Optional[str] = Form(None),
    faces_zip: UploadFile = File(...)
):
    """
    Gradually update student embeddings using weighted average.
    
    Formula: new_embedding = (current_embedding * alpha) + (new_embedding * (1 - alpha))
    
    Required:
    - school_name: School identifier
    - session: Academic session (e.g., 2025-26)
    - alpha: Weight for current embedding (must be < 1)
    
    Optional:
    - class_name, section, subject: Filters for students
    - faces_zip: ZIP file with student photos
    
    Behavior:
    - If student exists: Update embedding using weighted average
    - If student doesn't exist: Add new record with the new embedding
    """
    logger.info(f"Starting embedding update for school={school_name}, session={session}, alpha={alpha}")
    
    # Validate alpha
    if alpha >= 1:
        return {"error": "alpha must be less than 1"}
    
    if alpha < 0:
        return {"error": "alpha must be non-negative"}
    
    # Create temp directory for processing
    temp_dir = tempfile.mkdtemp(dir=TEMP_DIR)
    zip_path = os.path.join(temp_dir, "upload.zip")
    
    # Save and extract zip file
    with open(zip_path, "wb") as f:
        shutil.copyfileobj(faces_zip.file, f)
    
    # Extract to temp directory
    extract_dir = os.path.join(temp_dir, "extracted")
    os.makedirs(extract_dir, exist_ok=True)
    
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)
    
    updated = []
    added = []
    skipped = []
    processed_roll_nos = set()
    
    # Process each student directory
    for student_dir in os.listdir(extract_dir):
        full_student_path = os.path.join(extract_dir, student_dir)
        if not os.path.isdir(full_student_path):
            continue
        
        # Parse and validate folder name
        roll_no, name = parse_student_folder_name(student_dir)
        if roll_no is None or name is None:
            skipped.append({"folder": student_dir, "reason": "Invalid folder name format"})
            continue
        
        # Check for duplicate roll numbers in this upload
        if roll_no in processed_roll_nos:
            logger.warning(f"Duplicate roll number '{roll_no}' found in folder '{student_dir}'. Skipping.")
            skipped.append({"folder": student_dir, "reason": f"Duplicate roll number: {roll_no}"})
            continue
        
        processed_roll_nos.add(roll_no)
        
        emb_list = []
        img_count = 0
        
        # Process images to get new embedding
        for img_file in os.listdir(full_student_path):
            if not img_file.lower().endswith(('.jpg', '.jpeg', '.png')):
                continue
            
            img_count += 1
            img_path = os.path.join(full_student_path, img_file)
            img = cv2.imread(img_path)
            if img is None:
                logger.warning(f"Could not read image: {img_path}")
                continue
                
            faces = face_app.get(img)
            if not faces:
                logger.warning(f"No face detected in image: {img_path}")
                continue
                
            f = max(faces, key=lambda x: (x.bbox[2]-x.bbox[0])*(x.bbox[3]-x.bbox[1]))
            emb = l2_normalize(f.embedding)
            emb_list.append(emb)
        
        if not emb_list:
            logger.warning(f"No valid face embeddings for student '{roll_no}' ({name}). Processed {img_count} images.")
            skipped.append({"folder": student_dir, "reason": "No valid face embeddings found"})
            continue
        
        # Calculate mean embedding from new images
        emb_stack = np.stack([np.array(e, dtype=np.float32) for e in emb_list], axis=0)
        new_emb = l2_normalize(np.mean(emb_stack, axis=0))
        
        # Check if student exists
        existing_student = get_student_embedding(school_name, roll_no, session)
        
        if existing_student:
            # Student exists - update with weighted average
            current_emb = existing_student["embedding"]
            
            # Weighted average: (current * alpha) + (new * (1 - alpha))
            updated_emb = (current_emb * alpha) + (new_emb * (1 - alpha))
            updated_emb = l2_normalize(updated_emb)
            
            # Update in database
            update_student_embedding(school_name, roll_no, session, updated_emb)
            
            # Log the embedding update
            log_database_change(
                school_name=school_name,
                class_name=existing_student.get("class_name"),
                section=existing_student.get("section"),
                subject=existing_student.get("subject"),
                roll_no=roll_no,
                session=session,
                change_type="embedding_update",
                endpoint_name="/update-embedding-via-period/",
                details=f"Updated embedding for {existing_student['name']} with alpha={alpha}, {len(emb_list)} images"
            )
            
            logger.info(f"Updated embedding for: {roll_no} - {name} (alpha={alpha})")
            updated.append({
                "roll_no": roll_no,
                "name": existing_student["name"],
                "images_processed": len(emb_list),
                "action": "updated"
            })
        else:
            # Student doesn't exist - add new record
            # Determine class_name, section, subject from parameters or folder structure
            student_class = class_name if class_name else "Unknown"
            student_section = section if section else "Unknown"
            student_subject = subject
            
            # Save new student
            face_path = full_student_path
            save_student(school_name, roll_no, session, name, student_class, student_section, student_subject, face_path, new_emb)
            
            # Log the insert
            log_database_change(
                school_name=school_name,
                class_name=student_class,
                section=student_section,
                subject=student_subject,
                roll_no=roll_no,
                session=session,
                change_type="insert",
                endpoint_name="/update-embedding-via-period/",
                details=f"Added new student: {name} with {len(emb_list)} images"
            )
            
            logger.info(f"Added new student: {roll_no} - {name}")
            added.append({
                "roll_no": roll_no,
                "name": name,
                "images_processed": len(emb_list),
                "action": "added"
            })
    
    # Cleanup temp directory
    shutil.rmtree(temp_dir)
    
    logger.info(f"Embedding update complete: {len(updated)} updated, {len(added)} added, {len(skipped)} skipped")
    
    result = {
        "school_name": school_name,
        "session": session,
        "alpha": alpha,
        "updated_count": len(updated),
        "added_count": len(added),
        "updated_students": updated,
        "added_students": added
    }
    
    if skipped:
        result["skipped"] = skipped
    
    return result

def get_current_datetime():
    now = datetime.now()
    return {
        'date': now.strftime('%Y-%m-%d'),
        'time': now.strftime('%H:%M:%S.%f')[:-3],  # Include milliseconds
        'timestamp': now.strftime('%Y%m%d_%H%M%S_%f')[:-3]
    }

def get_attendance_crop_path(school_name: str, class_name: str, section: str, subject: Optional[str] = None) -> str:
    dt = get_current_datetime()
    base_path = os.path.join(ATTENDANCE_CROPS_DIR, dt['date'], school_name, class_name, section)
    if subject:
        base_path = os.path.join(base_path, subject)
    os.makedirs(base_path, exist_ok=True)
    return base_path, dt['timestamp']

@app.post("/mark-attendance/")
async def mark_attendance_endpoint(
    school_name: str = Form(...),
    class_name: str = Form(...),
    section: str = Form(...),
    subject: Optional[str] = Form(None),
    photos_zip: UploadFile = File(...),
    threshold: float = Form(0.3)
):
    """
    Mark attendance for all enrolled students based on classroom photo.
    - Students detected in photo are marked as 'P' (Present)
    - Students NOT detected in photo are marked as 'A' (Absent)
    """
    logger.info(f"Marking attendance for school={school_name}, class={class_name}, section={section}, subject={subject}")
    
    # Create temp directory for processing
    temp_dir = tempfile.mkdtemp(dir=TEMP_DIR)
    zip_path = os.path.join(temp_dir, "photos.zip")
    photos_dir = os.path.join(temp_dir, "extracted")
    
    # Save and extract zip file
    with open(zip_path, "wb") as f:
        shutil.copyfileobj(photos_zip.file, f)
    
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(photos_dir)
    
    # Get enrolled students for this school/class/section (with embeddings for face matching)
    roll_nos, names, known_encodings = get_students(school_name, class_name, section, subject)
    
    # Get all students for attendance marking (roll_no -> name mapping)
    all_students = get_all_students_for_attendance(school_name, class_name, section, subject)
    
    if not all_students:
        shutil.rmtree(temp_dir)
        return {"error": "No students enrolled for this class/section", "school_name": school_name}

    present_students = []
    absent_students = []
    present_roll_nos = set()
    
    # Process each photo in extracted directory to find present students
    for root, _, files in os.walk(photos_dir):
        for photo_name in files:
            if not photo_name.lower().endswith(('.jpg', '.jpeg', '.png')):
                continue
                
            img_path = os.path.join(root, photo_name)
            img = cv2.imread(img_path)
            if img is None:
                continue
                
            faces = face_app.get(img)
            for f in faces:
                # Ensure proper embedding format and normalization
                emb = np.array(f.embedding, dtype=np.float32)
                emb = l2_normalize(emb)
                scores = np.array([np.dot(emb, k) for k in known_encodings])
                
                if len(scores) > 0:
                    best_idx = np.argmax(scores)
                    best_score = scores[best_idx]
                    
                    if best_score >= threshold:
                        roll_no = roll_nos[best_idx]
                        student_name = names[best_idx]
                        if roll_no not in present_roll_nos:
                            present_students.append({
                                "roll_no": roll_no,
                                "name": student_name,
                                "similarity": float(best_score),
                                "status": "P"
                            })
                            
                            # Save cropped face
                            crops_dir, timestamp = get_attendance_crop_path(school_name, class_name, section, subject)
                            bbox = f.bbox.astype(int)
                            face_crop = img[bbox[1]:bbox[3], bbox[0]:bbox[2]]
                            crop_filename = f"{roll_no}_{student_name}_{timestamp}.jpg"
                            crop_path = os.path.join(crops_dir, crop_filename)
                            cv2.imwrite(crop_path, face_crop)
                            
                            present_roll_nos.add(roll_no)

    # Get current date and time for all attendance records
    dt = get_current_datetime()
    
    # Note: For attendance marking, we use a default session since it's not provided
    # In production, you may want to add session as a parameter
    default_session = "2025-26"
    
    # Save attendance for PRESENT students (P)
    for student in present_students:
        save_attendance(
            school_name, 
            student["roll_no"],
            default_session,
            student["name"], 
            class_name, 
            section, 
            subject, 
            student["similarity"],
            "P",  # Present
            dt['date'], 
            dt['time']
        )
    
    # Mark ABSENT students (A) - students in database but not detected in photo
    for roll_no, name in all_students.items():
        if roll_no not in present_roll_nos:
            absent_students.append({
                "roll_no": roll_no,
                "name": name,
                "status": "A"
            })
            # Save attendance record with status 'A' (Absent)
            save_attendance(
                school_name, 
                roll_no,
                default_session,
                name, 
                class_name, 
                section, 
                subject, 
                0.0,  # No similarity score for absent
                "A",  # Absent
                dt['date'], 
                dt['time']
            )

    # Cleanup
    shutil.rmtree(temp_dir)
    
    return {
        "school_name": school_name,
        "class_name": class_name,
        "section": section,
        "subject": subject,
        "date": dt['date'],
        "time": dt['time'],
        "total_enrolled": len(all_students),
        "present_count": len(present_students),
        "absent_count": len(absent_students),
        "present_students": present_students,
        "absent_students": absent_students
    }


@app.delete("/delete-student/")
async def delete_student(
    school_name: str = Query(..., description="School name (required)"),
    roll_no: str = Query(..., description="Student roll number (required)"),
    session: str = Query(..., description="Academic session (required, e.g., 2025-26)")
):
    """
    Delete a student by school_name, roll_no, and session (composite key).
    
    **Required Parameters:**
    - school_name: School identifier
    - roll_no: Student roll number
    - session: Academic session (e.g., 2025-26)
    
    Deletes from both students and attendance tables.
    """
    # Delete student by composite key (school_name, roll_no, session)
    success = delete_student_by_roll_no(school_name, roll_no, session)
    logger.info(f"Delete operation result for {school_name}/{roll_no}/{session}: {success}")
    
    if success:
        # Log the delete operation
        log_database_change(
            school_name=school_name,
            roll_no=roll_no,
            session=session,
            change_type="delete",
            endpoint_name="/delete-student/",
            details=f"Deleted student with roll_no {roll_no}, session {session} from both students and attendance tables"
        )
        return {
            "message": f"Student with roll number {roll_no} from school {school_name}, session {session} deleted successfully",
            "school_name": school_name,
            "roll_no": roll_no,
            "session": session
        }
    else:
        return {"error": "Student not found", "school_name": school_name, "roll_no": roll_no, "session": session}

@app.delete("/delete-class/")
async def delete_class(
    school_name: str = Query(..., description="School name (required)"),
    class_name: str = Query(..., description="Class name (required)"),
    session: str = Query(..., description="Academic session (required, e.g., 2025-26)"),
    section: Optional[str] = Query(None, description="Section (optional filter)"),
    subject: Optional[str] = Query(None, description="Subject (optional filter)")
):
    """
    Delete class data by school_name, class_name, and session.
    
    **Required Parameters:**
    - school_name: School identifier
    - class_name: Class name
    - session: Academic session (e.g., 2025-26)
    
    **Optional Parameters:**
    - section: Filter by section
    - subject: Filter by subject
    
    Deletes from both students and attendance tables.
    """
    # Delete class data with school_name, class_name, session and optional section/subject parameters
    success = delete_class_data(school_name, class_name, session, section, subject)
    
    if success:
        # Log the delete operation
        log_database_change(
            school_name=school_name,
            class_name=class_name,
            section=section,
            subject=subject,
            session=session,
            change_type="delete",
            endpoint_name="/delete-class/",
            details=f"Deleted class data for {class_name}, session {session}"
        )
        
        message = f"Deleted data for school {school_name}, class {class_name}, session {session}"
        if section:
            message += f", section {section}"
        if subject:
            message += f", subject {subject}"
        return {
            "message": message,
            "school_name": school_name,
            "class_name": class_name,
            "session": session,
            "section": section,
            "subject": subject
        }
    else:
        return {"error": "No matching data found to delete"}


# ==================== DELETE ENDPOINTS (ALL REQUIRE SESSION) ====================

# 1. Delete student from database only (not attendance records)
@app.delete("/delete-student-from-database/")
async def delete_student_from_database_endpoint(
    school_name: str = Query(..., description="School name (required)"),
    roll_no: str = Query(..., description="Student roll number (required)"),
    session: str = Query(..., description="Academic session (required, e.g., 2025-26)")
):
    """
    Delete a student from the students database only.
    Does NOT delete their attendance records.
    
    **Required Parameters:**
    - school_name: School identifier
    - roll_no: Student roll number
    - session: Academic session (e.g., 2025-26)
    
    Returns: Student details (name, class, section, subject) if found and deleted.
    """
    result = delete_student_from_database_only(school_name, roll_no, session)
    
    if result:
        # Log the delete operation
        log_database_change(
            school_name=school_name,
            roll_no=roll_no,
            session=session,
            class_name=result.get("class_name"),
            section=result.get("section"),
            subject=result.get("subject"),
            change_type="delete",
            endpoint_name="/delete-student-from-database/",
            details=f"Deleted student {result.get('name')} from database only (attendance records preserved)"
        )
        return {
            "message": "Student deleted from database successfully",
            "deleted_student": result
        }
    else:
        return {"error": f"Student with roll number {roll_no}, session {session} not found in school {school_name}"}


# 2. Delete student from attendance records only (not database)
@app.delete("/delete-student-from-attendance/")
async def delete_student_from_attendance_endpoint(
    school_name: str = Query(..., description="School name (required)"),
    roll_no: str = Query(..., description="Student roll number (required)"),
    session: str = Query(..., description="Academic session (required, e.g., 2025-26)")
):
    """
    Delete a student's attendance records only.
    Does NOT delete them from the students database.
    
    **Required Parameters:**
    - school_name: School identifier
    - roll_no: Student roll number
    - session: Academic session (e.g., 2025-26)
    
    Returns: Student details and number of attendance records deleted.
    """
    result = delete_student_from_attendance_only(school_name, roll_no, session)
    
    if result:
        # Log the delete operation
        log_database_change(
            school_name=school_name,
            roll_no=roll_no,
            session=session,
            class_name=result.get("class_name"),
            section=result.get("section"),
            subject=result.get("subject"),
            change_type="delete",
            endpoint_name="/delete-student-from-attendance/",
            details=f"Deleted {result.get('attendance_records_deleted', 0)} attendance records (student database record preserved)"
        )
        return {
            "message": "Student attendance records deleted successfully",
            "deleted_info": result
        }
    else:
        return {"error": f"No attendance records found for roll number {roll_no}, session {session} in school {school_name}"}


# 3. Delete student from both database and attendance records
@app.delete("/delete-student-from-both/")
async def delete_student_from_both_endpoint(
    school_name: str = Query(..., description="School name (required)"),
    roll_no: str = Query(..., description="Student roll number (required)"),
    session: str = Query(..., description="Academic session (required, e.g., 2025-26)")
):
    """
    Delete a student from both the students database AND attendance records.
    
    **Required Parameters:**
    - school_name: School identifier
    - roll_no: Student roll number
    - session: Academic session (e.g., 2025-26)
    
    Returns: Student details and counts from both tables.
    """
    result = delete_student_from_both(school_name, roll_no, session)
    
    if result:
        # Log the delete operation
        log_database_change(
            school_name=school_name,
            roll_no=roll_no,
            session=session,
            class_name=result.get("class_name"),
            section=result.get("section"),
            subject=result.get("subject"),
            change_type="delete",
            endpoint_name="/delete-student-from-both/",
            details=f"Deleted student {result.get('name')} from both database and attendance ({result.get('attendance_records_deleted', 0)} records)"
        )
        return {
            "message": "Student deleted from both database and attendance records",
            "deleted_info": result
        }
    else:
        return {"error": f"Student with roll number {roll_no}, session {session} not found in school {school_name}"}


# 4. Delete bulk students from database only
@app.delete("/delete-bulk-from-database/")
async def delete_bulk_from_database_endpoint(
    school_name: str = Query(..., description="School name (required)"),
    class_name: str = Query(..., description="Class name (required)"),
    section: str = Query(..., description="Section (required)"),
    session: str = Query(..., description="Academic session (required, e.g., 2025-26)"),
    subject: Optional[str] = Query(None, description="Subject (optional filter)")
):
    """
    Delete all students matching the criteria from the students database only.
    Does NOT delete their attendance records.
    
    **Required Parameters:**
    - school_name: School identifier
    - class_name: Class name
    - section: Section
    - session: Academic session (e.g., 2025-26)
    
    **Optional Parameters:**
    - subject: Filter by subject
    
    Returns: Number of students deleted.
    """
    count = delete_bulk_from_database(school_name, class_name, section, session, subject)
    
    if count > 0:
        filter_info = f"school={school_name}, class={class_name}, section={section}, session={session}"
        if subject:
            filter_info += f", subject={subject}"
        
        # Log the delete operation
        log_database_change(
            school_name=school_name,
            class_name=class_name,
            section=section,
            subject=subject,
            session=session,
            change_type="delete",
            endpoint_name="/delete-bulk-from-database/",
            details=f"Bulk deleted {count} students from database only (attendance records preserved)"
        )
        
        return {
            "message": f"Bulk delete from database successful",
            "filter": filter_info,
            "students_deleted": count
        }
    else:
        return {"error": "No students found matching the criteria"}


# 5. Delete bulk attendance records only
@app.delete("/delete-bulk-from-attendance/")
async def delete_bulk_from_attendance_endpoint(
    school_name: str = Query(..., description="School name (required)"),
    class_name: str = Query(..., description="Class name (required)"),
    section: str = Query(..., description="Section (required)"),
    session: str = Query(..., description="Academic session (required, e.g., 2025-26)"),
    subject: Optional[str] = Query(None, description="Subject (optional filter)")
):
    """
    Delete all attendance records matching the criteria.
    Does NOT delete students from the database.
    
    **Required Parameters:**
    - school_name: School identifier
    - class_name: Class name
    - section: Section
    - session: Academic session (e.g., 2025-26)
    
    **Optional Parameters:**
    - subject: Filter by subject
    
    Returns: Number of attendance records deleted.
    """
    count = delete_bulk_from_attendance(school_name, class_name, section, session, subject)
    
    if count > 0:
        filter_info = f"school={school_name}, class={class_name}, section={section}, session={session}"
        if subject:
            filter_info += f", subject={subject}"
        
        # Log the delete operation
        log_database_change(
            school_name=school_name,
            class_name=class_name,
            section=section,
            subject=subject,
            session=session,
            change_type="delete",
            endpoint_name="/delete-bulk-from-attendance/",
            details=f"Bulk deleted {count} attendance records (student database records preserved)"
        )
        
        return {
            "message": f"Bulk delete from attendance successful",
            "filter": filter_info,
            "attendance_records_deleted": count
        }
    else:
        return {"error": "No attendance records found matching the criteria"}


# 6. Delete bulk from both database and attendance
@app.delete("/delete-bulk-from-both/")
async def delete_bulk_from_both_endpoint(
    school_name: str = Query(..., description="School name (required)"),
    class_name: str = Query(..., description="Class name (required)"),
    section: str = Query(..., description="Section (required)"),
    session: str = Query(..., description="Academic session (required, e.g., 2025-26)"),
    subject: Optional[str] = Query(None, description="Subject (optional filter)")
):
    """
    Delete all students AND attendance records matching the criteria.
    
    **Required Parameters:**
    - school_name: School identifier
    - class_name: Class name
    - section: Section
    - session: Academic session (e.g., 2025-26)
    
    **Optional Parameters:**
    - subject: Filter by subject
    
    Returns: Number of students and attendance records deleted.
    """
    result = delete_bulk_from_both_tables(school_name, class_name, section, session, subject)
    
    if result["students_deleted"] > 0 or result["attendance_records_deleted"] > 0:
        filter_info = f"school={school_name}, class={class_name}, section={section}, session={session}"
        if subject:
            filter_info += f", subject={subject}"
        
        # Log the delete operation
        log_database_change(
            school_name=school_name,
            class_name=class_name,
            section=section,
            subject=subject,
            session=session,
            change_type="delete",
            endpoint_name="/delete-bulk-from-both/",
            details=f"Bulk deleted {result['students_deleted']} students and {result['attendance_records_deleted']} attendance records"
        )
        
        return {
            "message": "Bulk delete from both database and attendance successful",
            "filter": filter_info,
            "students_deleted": result["students_deleted"],
            "attendance_records_deleted": result["attendance_records_deleted"]
        }
    else:
        return {"error": "No data found matching the criteria"}


@app.get("/enrollment-stats/")
async def enrollment_stats():
    """
    Get total enrollment numbers grouped by school, class, section, and subject.
    Returns hierarchical statistics of all enrolled students.
    """
    stats = get_enrollment_stats()
    return stats


@app.get("/view-students/")
async def view_students(
    school_name: str = Query(..., description="School name (required)"),
    class_name: Optional[str] = Query(None, description="Class name (optional filter)"),
    section: Optional[str] = Query(None, description="Section (optional filter)"),
    subject: Optional[str] = Query(None, description="Subject (optional filter)")
):
    """
    View students as CSV file with filters.
    
    - school_name: Required - the school to filter by
    - class_name: Optional - filter by class
    - section: Optional - filter by section
    - subject: Optional - filter by subject
    
    Returns a CSV file with columns: school, roll_number, name, class, section, subject
    """
    # Get students from database
    students = get_students_for_export(school_name, class_name, section, subject)
    
    if not students:
        return {"error": "No students found matching the criteria"}
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(["school", "roll_number", "name", "class", "section", "subject"])
    
    # Write data rows
    for student in students:
        school, roll_no, name, cls, sec, subj = student
        writer.writerow([school, roll_no, name, cls, sec, subj if subj else ""])
    
    # Prepare response
    output.seek(0)
    
    # Generate filename based on filters
    filename_parts = [school_name]
    if class_name:
        filename_parts.append(class_name)
    if section:
        filename_parts.append(section)
    if subject:
        filename_parts.append(subject)
    filename = "_".join(filename_parts) + "_students.csv"
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ==================== ATTENDANCE RECORD VIEWING ENDPOINTS ====================

def convert_date_format(date_str: str, from_format: str, to_format: str) -> str:
    """Convert date string from one format to another"""
    try:
        date_obj = datetime.strptime(date_str, from_format)
        return date_obj.strftime(to_format)
    except ValueError:
        return None


def validate_date_format(date_str: str) -> bool:
    """Validate that date is in DD-MM-YYYY format"""
    try:
        datetime.strptime(date_str, "%d-%m-%Y")
        return True
    except ValueError:
        return False


@app.get("/view-attendance-on-date/")
async def view_attendance_on_date(
    school_name: str = Query(..., description="School name (required)"),
    date: str = Query(..., description="Date in DD-MM-YYYY format (required)"),
    roll_no: Optional[str] = Query(None, description="Roll number (optional filter)"),
    class_name: Optional[str] = Query(None, description="Class name (optional filter)"),
    section: Optional[str] = Query(None, description="Section (optional filter)"),
    subject: Optional[str] = Query(None, description="Subject (optional filter)")
):
    """
    View attendance records for a specific date.
    
    **Input Parameters:**
    - school_name: Required - the school to filter by
    - date: Required - date in DD-MM-YYYY format
    - roll_no: Optional - filter by specific student roll number
    - class_name: Optional - filter by class
    - section: Optional - filter by section
    - subject: Optional - filter by subject
    
    **Output:** JSON array with attendance records
    - Each record contains: date, school, roll_number, name, class, subject, section, attendance_record (P/A)
    """
    # Validate date format
    if not validate_date_format(date):
        return {"error": "Invalid date format. Please use DD-MM-YYYY format (e.g., 25-02-2026)"}
    
    # Convert date from DD-MM-YYYY to YYYY-MM-DD for database query
    db_date = convert_date_format(date, "%d-%m-%Y", "%Y-%m-%d")
    if not db_date:
        return {"error": "Failed to parse date"}
    
    # Get attendance records from database
    records = get_attendance_on_date(school_name, db_date, roll_no, class_name, section, subject)
    
    if not records:
        return {"error": "No attendance records found matching the criteria", "date": date}
    
    # Build JSON response array
    attendance_data = []
    for record in records:
        school, roll, name, cls, sec, subj, status, rec_date = record
        # Convert date back to DD-MM-YYYY format for display
        display_date = convert_date_format(rec_date, "%Y-%m-%d", "%d-%m-%Y")
        attendance_data.append({
            "date": display_date,
            "school": school,
            "roll_number": roll,
            "name": name,
            "class": cls,
            "subject": subj if subj else "",
            "section": sec,
            "attendance_record": status  # P or A
        })
    
    return {
        "total_records": len(attendance_data),
        "date": date,
        "school_name": school_name,
        "data": attendance_data
    }


@app.get("/view-attendance-range/")
async def view_attendance_range(
    school_name: str = Query(..., description="School name (required)"),
    start_date: str = Query(..., description="Start date in DD-MM-YYYY format (required, inclusive)"),
    end_date: str = Query(..., description="End date in DD-MM-YYYY format (required, inclusive)"),
    roll_no: Optional[str] = Query(None, description="Roll number (optional filter)"),
    class_name: Optional[str] = Query(None, description="Class name (optional filter)"),
    section: Optional[str] = Query(None, description="Section (optional filter)"),
    subject: Optional[str] = Query(None, description="Subject (optional filter)")
):
    """
    View overall attendance records for a date range with statistics.
    
    **Input Parameters:**
    - school_name: Required - the school to filter by
    - start_date: Required - start date in DD-MM-YYYY format (inclusive)
    - end_date: Required - end date in DD-MM-YYYY format (inclusive)
    - roll_no: Optional - filter by specific student roll number
    - class_name: Optional - filter by class
    - section: Optional - filter by section
    - subject: Optional - filter by subject
    
    **Output:** JSON array with attendance records per student
    - Each record contains: school, roll_number, name, class, subject, section
    - Date columns (DD-MM-YYYY format) with P/A values
    - Statistics: total_days, total_present, total_absent, attendance_percentage, below_75_percent
    """
    # Validate date formats
    if not validate_date_format(start_date):
        return {"error": "Invalid start_date format. Please use DD-MM-YYYY format (e.g., 25-02-2026)"}
    
    if not validate_date_format(end_date):
        return {"error": "Invalid end_date format. Please use DD-MM-YYYY format (e.g., 27-02-2026)"}
    
    # Convert dates from DD-MM-YYYY to YYYY-MM-DD for database query
    db_start_date = convert_date_format(start_date, "%d-%m-%Y", "%Y-%m-%d")
    db_end_date = convert_date_format(end_date, "%d-%m-%Y", "%Y-%m-%d")
    
    if not db_start_date or not db_end_date:
        return {"error": "Failed to parse dates"}
    
    # Validate that start_date is before or equal to end_date
    if db_start_date > db_end_date:
        return {"error": "start_date must be before or equal to end_date"}
    
    # Get attendance records from database
    records = get_attendance_in_range(school_name, db_start_date, db_end_date, roll_no, class_name, section, subject)
    
    if not records:
        return {"error": "No attendance records found matching the criteria", "start_date": start_date, "end_date": end_date}
    
    # Organize data by student
    # Structure: {roll_no: {info: {...}, dates: {date: status}}}
    students_data = {}
    all_dates = set()
    
    for record in records:
        school, roll, name, cls, sec, subj, status, rec_date = record
        
        # Convert date to DD-MM-YYYY format for display
        display_date = convert_date_format(rec_date, "%Y-%m-%d", "%d-%m-%Y")
        all_dates.add(display_date)
        
        if roll not in students_data:
            students_data[roll] = {
                "info": {
                    "school": school,
                    "roll_number": roll,
                    "name": name,
                    "class": cls,
                    "subject": subj if subj else "",
                    "section": sec
                },
                "dates": {}
            }
        
        students_data[roll]["dates"][display_date] = status
    
    # Sort dates chronologically
    sorted_dates = sorted(all_dates, key=lambda x: datetime.strptime(x, "%d-%m-%Y"))
    
    # Build response data with statistics
    attendance_data = []
    
    for roll_no, student_info in students_data.items():
        record = student_info["info"].copy()
        
        # Add date columns
        total_present = 0
        total_absent = 0
        
        for date in sorted_dates:
            status = student_info["dates"].get(date, "-")  # "-" if no record for that date
            record[date] = status
            if status == "P":
                total_present += 1
            elif status == "A":
                total_absent += 1
        
        # Calculate statistics
        total_days = len(sorted_dates)
        attendance_percentage = round((total_present / total_days) * 100, 2) if total_days > 0 else 0
        below_75_percent = "Yes" if attendance_percentage < 75 else "No"
        
        # Add statistics to record
        record["total_days"] = total_days
        record["total_present"] = total_present
        record["total_absent"] = total_absent
        record["attendance_percentage"] = attendance_percentage
        record["below_75_percent"] = below_75_percent
        
        attendance_data.append(record)
    
    # Sort by roll number
    attendance_data.sort(key=lambda x: x["roll_number"])
    
    return {
        "total_students": len(attendance_data),
        "date_range": {
            "start_date": start_date,
            "end_date": end_date,
            "total_days": len(sorted_dates)
        },
        "dates": sorted_dates,
        "school_name": school_name,
        "data": attendance_data
    }


# ==================== DATABASE CHANGE LOG ENDPOINT ====================

@app.get("/database-change-log/")
async def database_change_log(
    school_name: Optional[str] = Query(None, description="School name (at least one of school_name, roll_no, or session required)"),
    roll_no: Optional[str] = Query(None, description="Roll number (at least one of school_name, roll_no, or session required)"),
    session: Optional[str] = Query(None, description="Session (at least one of school_name, roll_no, or session required)"),
    class_name: Optional[str] = Query(None, description="Class name (optional filter)"),
    section: Optional[str] = Query(None, description="Section (optional filter)"),
    subject: Optional[str] = Query(None, description="Subject (optional filter)"),
    change_type: Optional[str] = Query(None, description="Change type filter: insert, update, delete, embedding_update"),
    start_date: Optional[str] = Query(None, description="Start date filter (YYYY-MM-DD format)"),
    end_date: Optional[str] = Query(None, description="End date filter (YYYY-MM-DD format)"),
    format: Optional[str] = Query("json", description="Output format: json or csv")
):
    """
    View database change log with flexible filtering.
    
    **Required (at least one):**
    - school_name: Filter by school name
    - roll_no: Filter by roll number
    - session: Filter by session
    
    **Optional filters:**
    - class_name, section, subject: Additional filters
    - change_type: Filter by type (insert, update, delete, embedding_update)
    - start_date, end_date: Date range filter (YYYY-MM-DD format)
    - format: Output format - "json" (default) or "csv"
    
    **Logged change types:**
    - insert: New student enrollment
    - update: Student data update
    - delete: Student or attendance deletion
    - embedding_update: Face embedding update
    
    **Each log entry includes:**
    - school_name, class_name, section, subject, roll_no, session
    - change_type, endpoint_name, details, timestamp
    """
    # Validate that at least one required filter is provided
    if not school_name and not roll_no and not session:
        return {"error": "At least one of school_name, roll_no, or session is required"}
    
    # Get logs based on format
    if format.lower() == "csv":
        csv_content = get_change_log_as_csv(
            school_name=school_name,
            roll_no=roll_no,
            session=session,
            class_name=class_name,
            section=section,
            subject=subject,
            change_type=change_type,
            start_date=start_date,
            end_date=end_date
        )
        
        # Generate filename
        filename_parts = ["database_change_log"]
        if school_name:
            filename_parts.append(school_name)
        if session:
            filename_parts.append(session)
        filename = "_".join(filename_parts) + ".csv"
        
        return StreamingResponse(
            iter([csv_content]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    else:
        # JSON format
        logs = get_database_change_log(
            school_name=school_name,
            roll_no=roll_no,
            session=session,
            class_name=class_name,
            section=section,
            subject=subject,
            change_type=change_type,
            start_date=start_date,
            end_date=end_date
        )
        
        if not logs:
            return {"error": "No change log entries found matching the criteria", "total_records": 0}
        
        return {
            "total_records": len(logs),
            "filters": {
                "school_name": school_name,
                "roll_no": roll_no,
                "session": session,
                "class_name": class_name,
                "section": section,
                "subject": subject,
                "change_type": change_type,
                "start_date": start_date,
                "end_date": end_date
            },
            "data": logs
        }
