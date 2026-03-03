import sqlite3
import os
import numpy as np
from datetime import datetime
from utils import l2_normalize  # Add this import
import csv
import io

# Define database path
DB_PATH = 'attendance.db'

# Only try to create directory if DB_PATH includes a directory component
db_dir = os.path.dirname(DB_PATH)
if db_dir:  # Only create if there's a directory component
    os.makedirs(db_dir, exist_ok=True)

def get_db():
    return sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)

def init_db():
    """Initialize database tables if they don't exist. Does NOT drop existing data."""
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    
    # Check if old students table exists without school_name or session
    c.execute("PRAGMA table_info(students)")
    columns = [col[1] for col in c.fetchall()]
    
    if 'session' not in columns and columns:
        # Need to migrate to add session field
        print("Migrating database to include session field...")
        
        # Create new students table with composite primary key including session
        c.execute('''CREATE TABLE IF NOT EXISTS students_new
                     (school_name TEXT NOT NULL,
                      roll_no TEXT NOT NULL,
                      session TEXT NOT NULL,
                      name TEXT,
                      class_name TEXT,
                      section TEXT,
                      subject TEXT,
                      face_path TEXT,
                      embedding BLOB,
                      PRIMARY KEY (school_name, roll_no, session))''')
        
        # Migrate existing data with default school name and session
        c.execute('''INSERT INTO students_new (school_name, roll_no, session, name, class_name, section, subject, face_path, embedding)
                     SELECT 
                        COALESCE(school_name, 'default_school'), 
                        roll_no, 
                        '2025-26',
                        name, 
                        class_name, 
                        section, 
                        subject, 
                        face_path, 
                        embedding
                     FROM students''')
        
        # Drop old table and rename new one
        c.execute('DROP TABLE students')
        c.execute('ALTER TABLE students_new RENAME TO students')
        
        # Update attendance table to add school_name and session
        c.execute("PRAGMA table_info(attendance)")
        att_columns = [col[1] for col in c.fetchall()]
        
        if 'session' not in att_columns:
            c.execute('''CREATE TABLE IF NOT EXISTS attendance_new
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                          time TEXT)''')
            
            c.execute('''INSERT INTO attendance_new (school_name, roll_no, session, student_name, class_name, section, subject, similarity_score, status, date, time)
                         SELECT 
                            COALESCE(school_name, 'default_school'), 
                            roll_no, 
                            '2025-26',
                            student_name, 
                            class_name, 
                            section, 
                            subject, 
                            similarity_score, 
                            COALESCE(status, 'P'), 
                            date, 
                            time
                         FROM attendance''')
            
            c.execute('DROP TABLE attendance')
            c.execute('ALTER TABLE attendance_new RENAME TO attendance')
        
        print("Migration complete!")
    else:
        # Create students table with composite primary key (school_name, roll_no, session)
        c.execute('''CREATE TABLE IF NOT EXISTS students
                     (school_name TEXT NOT NULL,
                      roll_no TEXT NOT NULL,
                      session TEXT NOT NULL,
                      name TEXT,
                      class_name TEXT,
                      section TEXT,
                      subject TEXT,
                      face_path TEXT,
                      embedding BLOB,
                      PRIMARY KEY (school_name, roll_no, session))''')
        
        # Create attendance table with school_name, session and status column
        c.execute('''CREATE TABLE IF NOT EXISTS attendance
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                      time TEXT)''')
    
    # Create indexes on attendance table for faster queries
    c.execute('''CREATE INDEX IF NOT EXISTS idx_attendance_roll_no 
                 ON attendance(roll_no)''')
    
    c.execute('''CREATE INDEX IF NOT EXISTS idx_attendance_class 
                 ON attendance(class_name, section, date)''')
    
    c.execute('''CREATE INDEX IF NOT EXISTS idx_attendance_school 
                 ON attendance(school_name)''')
    
    c.execute('''CREATE INDEX IF NOT EXISTS idx_students_school 
                 ON students(school_name)''')
    
    # Create database_change_log table for tracking all database modifications
    c.execute('''CREATE TABLE IF NOT EXISTS database_change_log
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  school_name TEXT,
                  class_name TEXT,
                  section TEXT,
                  subject TEXT,
                  roll_no TEXT,
                  session TEXT,
                  change_type TEXT NOT NULL,
                  endpoint_name TEXT,
                  details TEXT,
                  timestamp TEXT NOT NULL)''')
    
    # Create indexes on database_change_log for faster queries
    c.execute('''CREATE INDEX IF NOT EXISTS idx_change_log_school 
                 ON database_change_log(school_name)''')
    
    c.execute('''CREATE INDEX IF NOT EXISTS idx_change_log_roll_no 
                 ON database_change_log(roll_no)''')
    
    c.execute('''CREATE INDEX IF NOT EXISTS idx_change_log_session 
                 ON database_change_log(session)''')
    
    conn.commit()
    conn.close()


# ==================== DATABASE CHANGE LOG FUNCTIONS ====================

def log_database_change(school_name=None, class_name=None, section=None, subject=None, 
                        roll_no=None, session=None, change_type=None, endpoint_name=None, details=None):
    """Log a database change to the change log table"""
    conn = get_db()
    try:
        cur = conn.cursor()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        cur.execute('''
            INSERT INTO database_change_log 
            (school_name, class_name, section, subject, roll_no, session, change_type, endpoint_name, details, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (school_name, class_name, section, subject, roll_no, session, change_type, endpoint_name, details, timestamp))
        conn.commit()
    finally:
        conn.close()


def get_database_change_log(school_name=None, roll_no=None, session=None, class_name=None, 
                            section=None, subject=None, change_type=None, start_date=None, end_date=None):
    """
    Get database change log entries with flexible filtering.
    At least one of school_name, roll_no, or session must be provided.
    """
    conn = get_db()
    try:
        cur = conn.cursor()
        
        # Build query dynamically based on filters
        query = '''
            SELECT school_name, class_name, section, subject, roll_no, session, 
                   change_type, endpoint_name, details, timestamp
            FROM database_change_log
            WHERE 1=1
        '''
        params = []
        
        # At least one of these must be provided
        if school_name:
            query += ' AND school_name = ?'
            params.append(school_name)
        
        if roll_no:
            query += ' AND roll_no = ?'
            params.append(roll_no)
        
        if session:
            query += ' AND session = ?'
            params.append(session)
        
        # Optional additional filters
        if class_name:
            query += ' AND class_name = ?'
            params.append(class_name)
        
        if section:
            query += ' AND section = ?'
            params.append(section)
        
        if subject:
            query += ' AND subject = ?'
            params.append(subject)
        
        if change_type:
            query += ' AND change_type = ?'
            params.append(change_type)
        
        if start_date:
            query += ' AND timestamp >= ?'
            params.append(start_date)
        
        if end_date:
            query += ' AND timestamp <= ?'
            params.append(end_date + ' 23:59:59.999')
        
        query += ' ORDER BY timestamp DESC'
        
        cur.execute(query, params)
        rows = cur.fetchall()
        
        return [{
            "school_name": row[0],
            "class_name": row[1],
            "section": row[2],
            "subject": row[3],
            "roll_no": row[4],
            "session": row[5],
            "change_type": row[6],
            "endpoint_name": row[7],
            "details": row[8],
            "timestamp": row[9]
        } for row in rows]
    finally:
        conn.close()


def get_change_log_as_csv(school_name=None, roll_no=None, session=None, class_name=None, 
                          section=None, subject=None, change_type=None, start_date=None, end_date=None):
    """Get database change log as CSV string"""
    logs = get_database_change_log(school_name, roll_no, session, class_name, 
                                   section, subject, change_type, start_date, end_date)
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(["school_name", "class_name", "section", "subject", "roll_no", 
                     "session", "change_type", "endpoint_name", "details", "timestamp"])
    
    # Write data rows
    for log in logs:
        writer.writerow([
            log["school_name"] or "",
            log["class_name"] or "",
            log["section"] or "",
            log["subject"] or "",
            log["roll_no"] or "",
            log["session"] or "",
            log["change_type"] or "",
            log["endpoint_name"] or "",
            log["details"] or "",
            log["timestamp"] or ""
        ])
    
    output.seek(0)
    return output.getvalue()


def save_student(school_name, roll_no, session, name, class_name, section, subject, face_path, face_encoding):
    """Save a student with school_name, roll_no, and session as composite primary key"""
    # Ensure face_encoding is float32 and normalized before saving
    face_encoding = np.array(face_encoding, dtype=np.float32)
    face_encoding = l2_normalize(face_encoding)
    
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute('''
            INSERT OR REPLACE INTO students 
            (school_name, roll_no, session, name, class_name, section, subject, face_path, embedding)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (school_name, roll_no, session, name, class_name, section, subject, face_path, face_encoding))
        conn.commit()
    finally:
        conn.close()

def save_attendance(school_name, roll_no, session, student_name, class_name, section, subject, similarity_score, status, date, time):
    """Save attendance record with school_name, session and status (P=Present, A=Absent)"""
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    
    c.execute('''INSERT INTO attendance 
                 (school_name, roll_no, session, student_name, class_name, section, subject, similarity_score, status, date, time)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (school_name, roll_no, session, student_name, class_name, section, subject, similarity_score, status, date, time))
    
    conn.commit()
    conn.close()

def get_all_students_for_attendance(school_name, class_name, section, subject=None):
    """Get all students for attendance marking (returns roll_no, name pairs)"""
    conn = get_db()
    try:
        cur = conn.cursor()
        if subject:
            query = '''
                SELECT roll_no, name 
                FROM students 
                WHERE school_name=? AND class_name=? AND section=? AND subject=?
            '''
            params = (school_name, class_name, section, subject)
        else:
            query = '''
                SELECT roll_no, name 
                FROM students 
                WHERE school_name=? AND class_name=? AND section=?
            '''
            params = (school_name, class_name, section)
        
        cur.execute(query, params)
        rows = cur.fetchall()
        return {row[0]: row[1] for row in rows}  # {roll_no: name}
    finally:
        conn.close()

def get_student_details(school_name, roll_no):
    """Get student details by school_name and roll_no"""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT school_name, roll_no, name, class_name, section, subject 
            FROM students 
            WHERE school_name = ? AND roll_no = ?
        ''', (school_name, roll_no))
        row = cur.fetchone()
        if row:
            return {
                "school_name": row[0],
                "roll_no": row[1],
                "name": row[2],
                "class_name": row[3],
                "section": row[4],
                "subject": row[5]
            }
        return None
    finally:
        conn.close()

def delete_student_from_database_only(school_name, roll_no):
    """Delete a student from students table only (not attendance)"""
    conn = get_db()
    try:
        cur = conn.cursor()
        # Get student details before deletion
        cur.execute('''
            SELECT school_name, roll_no, name, class_name, section, subject 
            FROM students 
            WHERE school_name = ? AND roll_no = ?
        ''', (school_name, roll_no))
        student = cur.fetchone()
        
        if not student:
            return None
        
        student_info = {
            "school_name": student[0],
            "roll_no": student[1],
            "name": student[2],
            "class_name": student[3],
            "section": student[4],
            "subject": student[5]
        }
        
        # Delete from students table only
        cur.execute('DELETE FROM students WHERE school_name = ? AND roll_no = ?', (school_name, roll_no))
        conn.commit()
        
        return student_info
    finally:
        conn.close()

def delete_student_from_attendance_only(school_name, roll_no):
    """Delete a student from attendance table only (not students database)"""
    conn = get_db()
    try:
        cur = conn.cursor()
        
        # Get student details from students table (for return info)
        cur.execute('''
            SELECT school_name, roll_no, name, class_name, section, subject 
            FROM students 
            WHERE school_name = ? AND roll_no = ?
        ''', (school_name, roll_no))
        student = cur.fetchone()
        
        # Count attendance records before deletion
        cur.execute('SELECT COUNT(*) FROM attendance WHERE school_name = ? AND roll_no = ?', (school_name, roll_no))
        attendance_count = cur.fetchone()[0]
        
        if attendance_count == 0:
            return None
        
        # Delete from attendance table only
        cur.execute('DELETE FROM attendance WHERE school_name = ? AND roll_no = ?', (school_name, roll_no))
        conn.commit()
        
        result = {
            "roll_no": roll_no,
            "school_name": school_name,
            "attendance_records_deleted": attendance_count
        }
        
        if student:
            result["name"] = student[2]
            result["class_name"] = student[3]
            result["section"] = student[4]
            result["subject"] = student[5]
        
        return result
    finally:
        conn.close()

def delete_student_from_both(school_name, roll_no):
    """Delete a student from both students and attendance tables"""
    conn = get_db()
    try:
        cur = conn.cursor()
        
        # Get student details before deletion
        cur.execute('''
            SELECT school_name, roll_no, name, class_name, section, subject 
            FROM students 
            WHERE school_name = ? AND roll_no = ?
        ''', (school_name, roll_no))
        student = cur.fetchone()
        
        # Count attendance records
        cur.execute('SELECT COUNT(*) FROM attendance WHERE school_name = ? AND roll_no = ?', (school_name, roll_no))
        attendance_count = cur.fetchone()[0]
        
        if not student and attendance_count == 0:
            return None
        
        # Delete from both tables
        cur.execute('DELETE FROM students WHERE school_name = ? AND roll_no = ?', (school_name, roll_no))
        students_deleted = cur.rowcount
        
        cur.execute('DELETE FROM attendance WHERE school_name = ? AND roll_no = ?', (school_name, roll_no))
        
        conn.commit()
        
        result = {
            "roll_no": roll_no,
            "school_name": school_name,
            "deleted_from_database": students_deleted > 0,
            "attendance_records_deleted": attendance_count
        }
        
        if student:
            result["name"] = student[2]
            result["class_name"] = student[3]
            result["section"] = student[4]
            result["subject"] = student[5]
        
        return result
    finally:
        conn.close()

def delete_bulk_from_database(school_name, class_name, section, subject=None):
    """Delete bulk students from database only"""
    conn = get_db()
    try:
        cur = conn.cursor()
        
        if subject:
            cur.execute('SELECT COUNT(*) FROM students WHERE school_name = ? AND class_name = ? AND section = ? AND subject = ?',
                       (school_name, class_name, section, subject))
            count = cur.fetchone()[0]
            
            cur.execute('DELETE FROM students WHERE school_name = ? AND class_name = ? AND section = ? AND subject = ?',
                       (school_name, class_name, section, subject))
        else:
            cur.execute('SELECT COUNT(*) FROM students WHERE school_name = ? AND class_name = ? AND section = ?',
                       (school_name, class_name, section))
            count = cur.fetchone()[0]
            
            cur.execute('DELETE FROM students WHERE school_name = ? AND class_name = ? AND section = ?',
                       (school_name, class_name, section))
        
        conn.commit()
        return count
    finally:
        conn.close()

def delete_bulk_from_attendance(school_name, class_name, section, subject=None):
    """Delete bulk attendance records only"""
    conn = get_db()
    try:
        cur = conn.cursor()
        
        if subject:
            cur.execute('SELECT COUNT(*) FROM attendance WHERE school_name = ? AND class_name = ? AND section = ? AND subject = ?',
                       (school_name, class_name, section, subject))
            count = cur.fetchone()[0]
            
            cur.execute('DELETE FROM attendance WHERE school_name = ? AND class_name = ? AND section = ? AND subject = ?',
                       (school_name, class_name, section, subject))
        else:
            cur.execute('SELECT COUNT(*) FROM attendance WHERE school_name = ? AND class_name = ? AND section = ?',
                       (school_name, class_name, section))
            count = cur.fetchone()[0]
            
            cur.execute('DELETE FROM attendance WHERE school_name = ? AND class_name = ? AND section = ?',
                       (school_name, class_name, section))
        
        conn.commit()
        return count
    finally:
        conn.close()

def delete_bulk_from_both_tables(school_name, class_name, section, subject=None):
    """Delete bulk from both students and attendance tables"""
    conn = get_db()
    try:
        cur = conn.cursor()
        
        if subject:
            # Count before deletion
            cur.execute('SELECT COUNT(*) FROM students WHERE school_name = ? AND class_name = ? AND section = ? AND subject = ?',
                       (school_name, class_name, section, subject))
            students_count = cur.fetchone()[0]
            
            cur.execute('SELECT COUNT(*) FROM attendance WHERE school_name = ? AND class_name = ? AND section = ? AND subject = ?',
                       (school_name, class_name, section, subject))
            attendance_count = cur.fetchone()[0]
            
            # Delete
            cur.execute('DELETE FROM students WHERE school_name = ? AND class_name = ? AND section = ? AND subject = ?',
                       (school_name, class_name, section, subject))
            cur.execute('DELETE FROM attendance WHERE school_name = ? AND class_name = ? AND section = ? AND subject = ?',
                       (school_name, class_name, section, subject))
        else:
            # Count before deletion
            cur.execute('SELECT COUNT(*) FROM students WHERE school_name = ? AND class_name = ? AND section = ?',
                       (school_name, class_name, section))
            students_count = cur.fetchone()[0]
            
            cur.execute('SELECT COUNT(*) FROM attendance WHERE school_name = ? AND class_name = ? AND section = ?',
                       (school_name, class_name, section))
            attendance_count = cur.fetchone()[0]
            
            # Delete
            cur.execute('DELETE FROM students WHERE school_name = ? AND class_name = ? AND section = ?',
                       (school_name, class_name, section))
            cur.execute('DELETE FROM attendance WHERE school_name = ? AND class_name = ? AND section = ?',
                       (school_name, class_name, section))
        
        conn.commit()
        return {"students_deleted": students_count, "attendance_records_deleted": attendance_count}
    finally:
        conn.close()

def get_students(school_name, class_name, section, subject=None):
    """Get students filtered by school_name, class_name, section, and optionally subject"""
    conn = get_db()
    try:
        cur = conn.cursor()
        if subject:
            query = '''
                SELECT roll_no, name, embedding 
                FROM students 
                WHERE school_name=? AND class_name=? AND section=? AND subject=?
            '''
            params = (school_name, class_name, section, subject)
        else:
            query = '''
                SELECT roll_no, name, embedding 
                FROM students 
                WHERE school_name=? AND class_name=? AND section=?
            '''
            params = (school_name, class_name, section)
        
        cur.execute(query, params)
        rows = cur.fetchall()
        # Ensure embeddings are properly normalized when retrieved
        roll_nos = [row[0] for row in rows]
        names = [row[1] for row in rows]
        encodings = [l2_normalize(row[2]) for row in rows]
        return roll_nos, names, encodings
    finally:
        conn.close()

def delete_student_by_roll_no(school_name, roll_no):
    """Delete a student by school_name and roll_no (composite key)"""
    conn = get_db()
    try:
        cur = conn.cursor()
        # Delete from students table using composite key
        cur.execute('DELETE FROM students WHERE school_name = ? AND roll_no = ?', (school_name, roll_no))
        students_deleted = cur.rowcount
        
        # Delete from attendance table
        cur.execute('DELETE FROM attendance WHERE school_name = ? AND roll_no = ?', (school_name, roll_no))
        attendance_deleted = cur.rowcount
        
        conn.commit()
        # Return True if anything was deleted from either table
        return students_deleted > 0 or attendance_deleted > 0
    finally:
        conn.close()
        
def delete_class_data(school_name, class_name, section=None, subject=None):
    """Delete class data filtered by school_name and optionally section/subject"""
    conn = get_db()
    try:
        cur = conn.cursor()
        
        # Build query based on provided parameters
        if section and subject:
            # Delete with school, class, section, and subject
            cur.execute('DELETE FROM students WHERE school_name = ? AND class_name = ? AND section = ? AND subject = ?', 
                       (school_name, class_name, section, subject))
            students_deleted = cur.rowcount
            
            cur.execute('DELETE FROM attendance WHERE school_name = ? AND class_name = ? AND section = ? AND subject = ?', 
                       (school_name, class_name, section, subject))
            attendance_deleted = cur.rowcount
        elif section:
            # Delete with school, class and section only
            cur.execute('DELETE FROM students WHERE school_name = ? AND class_name = ? AND section = ?', 
                       (school_name, class_name, section))
            students_deleted = cur.rowcount
            
            cur.execute('DELETE FROM attendance WHERE school_name = ? AND class_name = ? AND section = ?', 
                       (school_name, class_name, section))
            attendance_deleted = cur.rowcount
        else:
            # Delete with just school and class
            cur.execute('DELETE FROM students WHERE school_name = ? AND class_name = ?', (school_name, class_name))
            students_deleted = cur.rowcount
            
            cur.execute('DELETE FROM attendance WHERE school_name = ? AND class_name = ?', (school_name, class_name))
            attendance_deleted = cur.rowcount
            
        conn.commit()
        # Return True if anything was deleted from either table
        return students_deleted > 0 or attendance_deleted > 0
    finally:
        conn.close()

def get_enrollment_stats():
    """Get enrollment statistics grouped by school, class, section, and subject"""
    conn = get_db()
    try:
        cur = conn.cursor()
        
        # Get total count
        cur.execute('SELECT COUNT(*) FROM students')
        total_students = cur.fetchone()[0]
        
        # Get grouped data
        cur.execute('''
            SELECT school_name, class_name, section, subject, COUNT(*) as count
            FROM students
            GROUP BY school_name, class_name, section, subject
            ORDER BY school_name, class_name, section, subject
        ''')
        rows = cur.fetchall()
        
        # Build hierarchical structure
        stats = {
            "total_students": total_students,
            "by_school": []
        }
        
        school_dict = {}
        for row in rows:
            school_name, class_name, section, subject, count = row
            subject = subject if subject else "No Subject"
            
            if school_name not in school_dict:
                school_dict[school_name] = {
                    "school_name": school_name,
                    "total": 0,
                    "by_class": {}
                }
            
            school_dict[school_name]["total"] += count
            
            if class_name not in school_dict[school_name]["by_class"]:
                school_dict[school_name]["by_class"][class_name] = {
                    "class_name": class_name,
                    "total": 0,
                    "by_section": {}
                }
            
            school_dict[school_name]["by_class"][class_name]["total"] += count
            
            if section not in school_dict[school_name]["by_class"][class_name]["by_section"]:
                school_dict[school_name]["by_class"][class_name]["by_section"][section] = {
                    "section": section,
                    "total": 0,
                    "by_subject": []
                }
            
            school_dict[school_name]["by_class"][class_name]["by_section"][section]["total"] += count
            school_dict[school_name]["by_class"][class_name]["by_section"][section]["by_subject"].append({
                "subject": subject,
                "count": count
            })
        
        # Convert nested dicts to lists
        for school_name, school_data in school_dict.items():
            school_entry = {
                "school_name": school_data["school_name"],
                "total": school_data["total"],
                "by_class": []
            }
            
            for class_name, class_data in school_data["by_class"].items():
                class_entry = {
                    "class_name": class_data["class_name"],
                    "total": class_data["total"],
                    "by_section": []
                }
                
                for section, section_data in class_data["by_section"].items():
                    class_entry["by_section"].append(section_data)
                
                school_entry["by_class"].append(class_entry)
            
            stats["by_school"].append(school_entry)
        
        return stats
    finally:
        conn.close()

def get_students_for_export(school_name, class_name=None, section=None, subject=None):
    """Get students for CSV export with optional filters"""
    conn = get_db()
    try:
        cur = conn.cursor()
        
        # Build query dynamically based on filters
        query = 'SELECT school_name, roll_no, name, class_name, section, subject FROM students WHERE school_name = ?'
        params = [school_name]
        
        if class_name:
            query += ' AND class_name = ?'
            params.append(class_name)
        
        if section:
            query += ' AND section = ?'
            params.append(section)
        
        if subject:
            query += ' AND subject = ?'
            params.append(subject)
        
        query += ' ORDER BY school_name, class_name, section, roll_no'
        
        cur.execute(query, params)
        rows = cur.fetchall()
        
        return rows
    finally:
        conn.close()

def get_attendance_on_date(school_name, date, roll_no=None, class_name=None, section=None, subject=None):
    """Get attendance records for a specific date with optional filters"""
    conn = get_db()
    try:
        cur = conn.cursor()

        # Build query dynamically based on filters
        query = '''
            SELECT school_name, roll_no, student_name, class_name, section, subject, status, date
            FROM attendance
            WHERE school_name = ? AND date = ?
        '''
        params = [school_name, date]

        if roll_no:
            query += ' AND roll_no = ?'
            params.append(roll_no)

        if class_name:
            query += ' AND class_name = ?'
            params.append(class_name)

        if section:
            query += ' AND section = ?'
            params.append(section)

        if subject:
            query += ' AND subject = ?'
            params.append(subject)

        query += ' ORDER BY school_name, class_name, section, roll_no'

        cur.execute(query, params)
        rows = cur.fetchall()
        
        return rows
    finally:
        conn.close()


def get_attendance_in_range(school_name, start_date, end_date, roll_no=None, class_name=None, section=None, subject=None):
    """Get attendance records for a date range with optional filters"""
    conn = get_db()
    try:
        cur = conn.cursor()

        # Build query dynamically based on filters
        query = '''
            SELECT school_name, roll_no, student_name, class_name, section, subject, status, date
            FROM attendance
            WHERE school_name = ? AND date >= ? AND date <= ?
        '''
        params = [school_name, start_date, end_date]

        if roll_no:
            query += ' AND roll_no = ?'
            params.append(roll_no)

        if class_name:
            query += ' AND class_name = ?'
            params.append(class_name)

        if section:
            query += ' AND section = ?'
            params.append(section)

        if subject:
            query += ' AND subject = ?'
            params.append(subject)

        query += ' ORDER BY roll_no, date'

        cur.execute(query, params)
        rows = cur.fetchall()
        
        return rows
    finally:
        conn.close()


def get_student_embedding(school_name, roll_no, session):
    """Get student embedding by composite key"""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT embedding, name, class_name, section, subject
            FROM students 
            WHERE school_name = ? AND roll_no = ? AND session = ?
        ''', (school_name, roll_no, session))
        row = cur.fetchone()
        if row:
            return {
                "embedding": row[0],
                "name": row[1],
                "class_name": row[2],
                "section": row[3],
                "subject": row[4]
            }
        return None
    finally:
        conn.close()


def update_student_embedding(school_name, roll_no, session, new_embedding):
    """Update student embedding using composite key"""
    new_embedding = np.array(new_embedding, dtype=np.float32)
    new_embedding = l2_normalize(new_embedding)
    
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute('''
            UPDATE students 
            SET embedding = ?
            WHERE school_name = ? AND roll_no = ? AND session = ?
        ''', (new_embedding, school_name, roll_no, session))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_students_by_filters(school_name, session, class_name=None, section=None, subject=None):
    """Get students filtered by school_name, session, and optional filters"""
    conn = get_db()
    try:
        cur = conn.cursor()
        
        query = '''
            SELECT roll_no, name, class_name, section, subject, embedding 
            FROM students 
            WHERE school_name = ? AND session = ?
        '''
        params = [school_name, session]
        
        if class_name:
            query += ' AND class_name = ?'
            params.append(class_name)
        
        if section:
            query += ' AND section = ?'
            params.append(section)
        
        if subject:
            query += ' AND subject = ?'
            params.append(subject)
        
        cur.execute(query, params)
        rows = cur.fetchall()
        
        return [{
            "roll_no": row[0],
            "name": row[1],
            "class_name": row[2],
            "section": row[3],
            "subject": row[4],
            "embedding": row[5]
        } for row in rows]
    finally:
        conn.close()


# Database will be initialized when app starts, not on module import
