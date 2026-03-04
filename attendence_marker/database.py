"""
Production-Grade PostgreSQL + pgvector Database Module
Automatic configuration on server start with no manual password entry required.
"""

import os
import numpy as np
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
import logging
import csv
import io

import psycopg2
from psycopg2 import pool, sql
from psycopg2.extras import execute_values, RealDictCursor
from pgvector.psycopg2 import register_vector

from config import db_config
from utils import l2_normalize

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Connection pool (initialized on startup)
connection_pool: Optional[pool.ThreadedConnectionPool] = None


# ==================== DATABASE CONNECTION MANAGEMENT ====================

def create_database_if_not_exists():
    """Create the database if it doesn't exist (connects to postgres db first)"""
    try:
        # Connect to default postgres database
        conn = psycopg2.connect(
            host=db_config.host,
            port=db_config.port,
            database="postgres",
            user=db_config.user,
            password=db_config.password
        )
        conn.autocommit = True
        cur = conn.cursor()
        
        # Check if database exists
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_config.database,))
        exists = cur.fetchone()
        
        if not exists:
            logger.info(f"Creating database: {db_config.database}")
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_config.database)))
            logger.info(f"Database {db_config.database} created successfully")
        else:
            logger.info(f"Database {db_config.database} already exists")
        
        cur.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error creating database: {e}")
        return False


def init_connection_pool():
    """Initialize the connection pool"""
    global connection_pool
    
    try:
        connection_pool = pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=db_config.pool_size,
            host=db_config.host,
            port=db_config.port,
            database=db_config.database,
            user=db_config.user,
            password=db_config.password
        )
        logger.info("Connection pool initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Error initializing connection pool: {e}")
        return False


def get_db(register_vec=True):
    """Get a connection from the pool"""
    global connection_pool
    
    if connection_pool is None:
        init_connection_pool()
    
    conn = connection_pool.getconn()
    if register_vec:
        register_vector(conn)
    return conn


def release_db(conn):
    """Release a connection back to the pool"""
    global connection_pool
    if connection_pool and conn:
        connection_pool.putconn(conn)


def close_pool():
    """Close all connections in the pool"""
    global connection_pool
    if connection_pool:
        connection_pool.closeall()
        connection_pool = None
        logger.info("Connection pool closed")


# ==================== DATABASE INITIALIZATION ====================

def init_db():
    """
    Initialize database with production-grade schema.
    Automatically creates database, enables pgvector, and sets up all tables with proper indexing.
    No manual password entry required.
    """
    logger.info("Starting database initialization...")
    
    # Step 1: Create database if not exists
    if not create_database_if_not_exists():
        raise Exception("Failed to create database")
    
    # Step 2: Initialize connection pool
    if not init_connection_pool():
        raise Exception("Failed to initialize connection pool")
    
    # Get connection WITHOUT registering vector (extension doesn't exist yet)
    conn = get_db(register_vec=False)
    try:
        cur = conn.cursor()
        
        # Step 3: Enable pgvector extension
        logger.info("Enabling pgvector extension...")
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.commit()
        
        # Now register the vector type after extension is created
        register_vector(conn)
        
        # Step 4: Create students table with vector embedding
        logger.info("Creating students table...")
        cur.execute('''
            CREATE TABLE IF NOT EXISTS students (
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
            )
        ''')
        
        # Step 5: Create attendance table
        logger.info("Creating attendance table...")
        cur.execute('''
            CREATE TABLE IF NOT EXISTS attendance (
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
            )
        ''')
        
        # Step 6: Create database_change_log table
        logger.info("Creating database_change_log table...")
        cur.execute('''
            CREATE TABLE IF NOT EXISTS database_change_log (
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
            )
        ''')
        
        # Step 7: Create production-grade indexes
        logger.info("Creating indexes...")
        
        # Students table indexes
        cur.execute('''
            CREATE INDEX IF NOT EXISTS idx_students_school 
            ON students(school_name)
        ''')
        cur.execute('''
            CREATE INDEX IF NOT EXISTS idx_students_class_section 
            ON students(school_name, class_name, section)
        ''')
        cur.execute('''
            CREATE INDEX IF NOT EXISTS idx_students_session 
            ON students(session)
        ''')
        cur.execute('''
            CREATE INDEX IF NOT EXISTS idx_students_roll_no 
            ON students(roll_no)
        ''')
        
        # Attendance table indexes
        cur.execute('''
            CREATE INDEX IF NOT EXISTS idx_attendance_school 
            ON attendance(school_name)
        ''')
        cur.execute('''
            CREATE INDEX IF NOT EXISTS idx_attendance_roll_no 
            ON attendance(roll_no)
        ''')
        cur.execute('''
            CREATE INDEX IF NOT EXISTS idx_attendance_date 
            ON attendance(date)
        ''')
        cur.execute('''
            CREATE INDEX IF NOT EXISTS idx_attendance_class_section_date 
            ON attendance(school_name, class_name, section, date)
        ''')
        cur.execute('''
            CREATE INDEX IF NOT EXISTS idx_attendance_session 
            ON attendance(session)
        ''')
        
        # Change log indexes
        cur.execute('''
            CREATE INDEX IF NOT EXISTS idx_change_log_school 
            ON database_change_log(school_name)
        ''')
        cur.execute('''
            CREATE INDEX IF NOT EXISTS idx_change_log_roll_no 
            ON database_change_log(roll_no)
        ''')
        cur.execute('''
            CREATE INDEX IF NOT EXISTS idx_change_log_session 
            ON database_change_log(session)
        ''')
        cur.execute('''
            CREATE INDEX IF NOT EXISTS idx_change_log_timestamp 
            ON database_change_log(timestamp)
        ''')
        
        # Step 8: Create vector similarity search index (IVFFlat for production)
        logger.info("Creating vector similarity index...")
        cur.execute('''
            CREATE INDEX IF NOT EXISTS idx_students_embedding 
            ON students USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        ''')
        
        conn.commit()
        logger.info("Database initialization completed successfully!")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error during database initialization: {e}")
        raise
    finally:
        release_db(conn)


# ==================== DATABASE CHANGE LOG FUNCTIONS ====================

def log_database_change(school_name=None, class_name=None, section=None, subject=None, 
                        roll_no=None, session=None, change_type=None, endpoint_name=None, details=None):
    """Log a database change to the change log table"""
    conn = get_db()
    try:
        cur = conn.cursor()
        timestamp = datetime.now()
        cur.execute('''
            INSERT INTO database_change_log 
            (school_name, class_name, section, subject, roll_no, session, change_type, endpoint_name, details, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (school_name, class_name, section, subject, roll_no, session, change_type, endpoint_name, details, timestamp))
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Error logging database change: {e}")
    finally:
        release_db(conn)


def get_database_change_log(school_name=None, roll_no=None, session=None, class_name=None, 
                            section=None, subject=None, change_type=None, start_date=None, end_date=None):
    """
    Get database change log entries with flexible filtering.
    At least one of school_name, roll_no, or session must be provided.
    """
    conn = get_db()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        query = '''
            SELECT school_name, class_name, section, subject, roll_no, session, 
                   change_type, endpoint_name, details, timestamp
            FROM database_change_log
            WHERE 1=1
        '''
        params = []
        
        if school_name:
            query += ' AND school_name = %s'
            params.append(school_name)
        
        if roll_no:
            query += ' AND roll_no = %s'
            params.append(roll_no)
        
        if session:
            query += ' AND session = %s'
            params.append(session)
        
        if class_name:
            query += ' AND class_name = %s'
            params.append(class_name)
        
        if section:
            query += ' AND section = %s'
            params.append(section)
        
        if subject:
            query += ' AND subject = %s'
            params.append(subject)
        
        if change_type:
            query += ' AND change_type = %s'
            params.append(change_type)
        
        if start_date:
            query += ' AND timestamp >= %s'
            params.append(start_date)
        
        if end_date:
            query += ' AND timestamp <= %s'
            params.append(end_date + ' 23:59:59.999')
        
        query += ' ORDER BY timestamp DESC'
        
        cur.execute(query, params)
        rows = cur.fetchall()
        
        return [{
            "school_name": row["school_name"],
            "class_name": row["class_name"],
            "section": row["section"],
            "subject": row["subject"],
            "roll_no": row["roll_no"],
            "session": row["session"],
            "change_type": row["change_type"],
            "endpoint_name": row["endpoint_name"],
            "details": row["details"],
            "timestamp": row["timestamp"].strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] if row["timestamp"] else None
        } for row in rows]
    finally:
        release_db(conn)


def get_change_log_as_csv(school_name=None, roll_no=None, session=None, class_name=None, 
                          section=None, subject=None, change_type=None, start_date=None, end_date=None):
    """Get database change log as CSV string"""
    logs = get_database_change_log(school_name, roll_no, session, class_name, 
                                   section, subject, change_type, start_date, end_date)
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(["school_name", "class_name", "section", "subject", "roll_no", 
                     "session", "change_type", "endpoint_name", "details", "timestamp"])
    
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


# ==================== STUDENT CRUD OPERATIONS ====================

def save_student(school_name, roll_no, session, name, class_name, section, subject, face_path, face_encoding):
    """Save a student with school_name, roll_no, and session as composite primary key"""
    face_encoding = np.array(face_encoding, dtype=np.float32)
    face_encoding = l2_normalize(face_encoding)
    
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO students 
            (school_name, roll_no, session, name, class_name, section, subject, face_path, embedding, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (school_name, roll_no, session) 
            DO UPDATE SET 
                name = EXCLUDED.name,
                class_name = EXCLUDED.class_name,
                section = EXCLUDED.section,
                subject = EXCLUDED.subject,
                face_path = EXCLUDED.face_path,
                embedding = EXCLUDED.embedding,
                updated_at = CURRENT_TIMESTAMP
        ''', (school_name, roll_no, session, name, class_name, section, subject, face_path, face_encoding.tolist()))
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Error saving student: {e}")
        raise
    finally:
        release_db(conn)


def get_students(school_name, class_name, section, subject=None):
    """Get students filtered by school_name, class_name, section, and optionally subject"""
    conn = get_db()
    try:
        cur = conn.cursor()
        
        if subject:
            query = '''
                SELECT roll_no, name, embedding 
                FROM students 
                WHERE school_name=%s AND class_name=%s AND section=%s AND subject=%s
            '''
            params = (school_name, class_name, section, subject)
        else:
            query = '''
                SELECT roll_no, name, embedding 
                FROM students 
                WHERE school_name=%s AND class_name=%s AND section=%s
            '''
            params = (school_name, class_name, section)
        
        cur.execute(query, params)
        rows = cur.fetchall()
        
        roll_nos = [row[0] for row in rows]
        names = [row[1] for row in rows]
        encodings = [l2_normalize(np.array(row[2], dtype=np.float32)) for row in rows]
        return roll_nos, names, encodings
    finally:
        release_db(conn)


def get_all_students_for_attendance(school_name, class_name, section, subject=None):
    """Get all students for attendance marking (returns roll_no, name pairs)"""
    conn = get_db()
    try:
        cur = conn.cursor()
        
        if subject:
            query = '''
                SELECT roll_no, name 
                FROM students 
                WHERE school_name=%s AND class_name=%s AND section=%s AND subject=%s
            '''
            params = (school_name, class_name, section, subject)
        else:
            query = '''
                SELECT roll_no, name 
                FROM students 
                WHERE school_name=%s AND class_name=%s AND section=%s
            '''
            params = (school_name, class_name, section)
        
        cur.execute(query, params)
        rows = cur.fetchall()
        return {row[0]: row[1] for row in rows}
    finally:
        release_db(conn)


def get_student_embedding(school_name, roll_no, session):
    """Get student embedding by composite key"""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT embedding, name, class_name, section, subject
            FROM students 
            WHERE school_name = %s AND roll_no = %s AND session = %s
        ''', (school_name, roll_no, session))
        row = cur.fetchone()
        if row:
            return {
                "embedding": np.array(row[0], dtype=np.float32),
                "name": row[1],
                "class_name": row[2],
                "section": row[3],
                "subject": row[4]
            }
        return None
    finally:
        release_db(conn)


def update_student_embedding(school_name, roll_no, session, new_embedding):
    """Update student embedding using composite key"""
    new_embedding = np.array(new_embedding, dtype=np.float32)
    new_embedding = l2_normalize(new_embedding)
    
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute('''
            UPDATE students 
            SET embedding = %s, updated_at = CURRENT_TIMESTAMP
            WHERE school_name = %s AND roll_no = %s AND session = %s
        ''', (new_embedding.tolist(), school_name, roll_no, session))
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating student embedding: {e}")
        return False
    finally:
        release_db(conn)


def get_students_by_filters(school_name, session, class_name=None, section=None, subject=None):
    """Get students filtered by school_name, session, and optional filters"""
    conn = get_db()
    try:
        cur = conn.cursor()
        
        query = '''
            SELECT roll_no, name, class_name, section, subject, embedding 
            FROM students 
            WHERE school_name = %s AND session = %s
        '''
        params = [school_name, session]
        
        if class_name:
            query += ' AND class_name = %s'
            params.append(class_name)
        
        if section:
            query += ' AND section = %s'
            params.append(section)
        
        if subject:
            query += ' AND subject = %s'
            params.append(subject)
        
        cur.execute(query, params)
        rows = cur.fetchall()
        
        return [{
            "roll_no": row[0],
            "name": row[1],
            "class_name": row[2],
            "section": row[3],
            "subject": row[4],
            "embedding": np.array(row[5], dtype=np.float32) if row[5] else None
        } for row in rows]
    finally:
        release_db(conn)


def get_students_for_export(school_name, class_name=None, section=None, subject=None):
    """Get students for CSV export with optional filters"""
    conn = get_db()
    try:
        cur = conn.cursor()
        
        query = 'SELECT school_name, roll_no, name, class_name, section, subject FROM students WHERE school_name = %s'
        params = [school_name]
        
        if class_name:
            query += ' AND class_name = %s'
            params.append(class_name)
        
        if section:
            query += ' AND section = %s'
            params.append(section)
        
        if subject:
            query += ' AND subject = %s'
            params.append(subject)
        
        query += ' ORDER BY school_name, class_name, section, roll_no'
        
        cur.execute(query, params)
        return cur.fetchall()
    finally:
        release_db(conn)


# ==================== ATTENDANCE OPERATIONS ====================

def save_attendance(school_name, roll_no, session, student_name, class_name, section, subject, similarity_score, status, date, time):
    """Save attendance record with school_name, session and status (P=Present, A=Absent)"""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO attendance 
            (school_name, roll_no, session, student_name, class_name, section, subject, similarity_score, status, date, time)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (school_name, roll_no, session, student_name, class_name, section, subject, similarity_score, status, date, time))
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Error saving attendance: {e}")
        raise
    finally:
        release_db(conn)


def get_attendance_on_date(school_name, date, roll_no=None, class_name=None, section=None, subject=None):
    """Get attendance records for a specific date with optional filters"""
    conn = get_db()
    try:
        cur = conn.cursor()

        query = '''
            SELECT school_name, roll_no, student_name, class_name, section, subject, status, date
            FROM attendance
            WHERE school_name = %s AND date = %s
        '''
        params = [school_name, date]

        if roll_no:
            query += ' AND roll_no = %s'
            params.append(roll_no)

        if class_name:
            query += ' AND class_name = %s'
            params.append(class_name)

        if section:
            query += ' AND section = %s'
            params.append(section)

        if subject:
            query += ' AND subject = %s'
            params.append(subject)

        query += ' ORDER BY school_name, class_name, section, roll_no'

        cur.execute(query, params)
        rows = cur.fetchall()
        
        # Convert date objects to strings
        return [(row[0], row[1], row[2], row[3], row[4], row[5], row[6], 
                 row[7].strftime('%Y-%m-%d') if row[7] else None) for row in rows]
    finally:
        release_db(conn)


def get_attendance_in_range(school_name, start_date, end_date, roll_no=None, class_name=None, section=None, subject=None):
    """Get attendance records for a date range with optional filters"""
    conn = get_db()
    try:
        cur = conn.cursor()

        query = '''
            SELECT school_name, roll_no, student_name, class_name, section, subject, status, date
            FROM attendance
            WHERE school_name = %s AND date >= %s AND date <= %s
        '''
        params = [school_name, start_date, end_date]

        if roll_no:
            query += ' AND roll_no = %s'
            params.append(roll_no)

        if class_name:
            query += ' AND class_name = %s'
            params.append(class_name)

        if section:
            query += ' AND section = %s'
            params.append(section)

        if subject:
            query += ' AND subject = %s'
            params.append(subject)

        query += ' ORDER BY roll_no, date'

        cur.execute(query, params)
        rows = cur.fetchall()
        
        return [(row[0], row[1], row[2], row[3], row[4], row[5], row[6], 
                 row[7].strftime('%Y-%m-%d') if row[7] else None) for row in rows]
    finally:
        release_db(conn)


# ==================== DELETE OPERATIONS (ALL REQUIRE SESSION) ====================

def delete_student_by_roll_no(school_name, roll_no, session):
    """Delete a student by school_name, roll_no, and session (composite key)"""
    conn = get_db()
    try:
        cur = conn.cursor()
        
        # Delete from students table using composite key
        cur.execute('DELETE FROM students WHERE school_name = %s AND roll_no = %s AND session = %s', 
                   (school_name, roll_no, session))
        students_deleted = cur.rowcount
        
        # Delete from attendance table
        cur.execute('DELETE FROM attendance WHERE school_name = %s AND roll_no = %s AND session = %s', 
                   (school_name, roll_no, session))
        attendance_deleted = cur.rowcount
        
        conn.commit()
        return students_deleted > 0 or attendance_deleted > 0
    except Exception as e:
        conn.rollback()
        logger.error(f"Error deleting student: {e}")
        return False
    finally:
        release_db(conn)


def delete_class_data(school_name, class_name, session, section=None, subject=None):
    """Delete class data filtered by school_name, session and optionally section/subject"""
    conn = get_db()
    try:
        cur = conn.cursor()
        
        if section and subject:
            cur.execute('DELETE FROM students WHERE school_name = %s AND class_name = %s AND session = %s AND section = %s AND subject = %s', 
                       (school_name, class_name, session, section, subject))
            students_deleted = cur.rowcount
            
            cur.execute('DELETE FROM attendance WHERE school_name = %s AND class_name = %s AND session = %s AND section = %s AND subject = %s', 
                       (school_name, class_name, session, section, subject))
            attendance_deleted = cur.rowcount
        elif section:
            cur.execute('DELETE FROM students WHERE school_name = %s AND class_name = %s AND session = %s AND section = %s', 
                       (school_name, class_name, session, section))
            students_deleted = cur.rowcount
            
            cur.execute('DELETE FROM attendance WHERE school_name = %s AND class_name = %s AND session = %s AND section = %s', 
                       (school_name, class_name, session, section))
            attendance_deleted = cur.rowcount
        else:
            cur.execute('DELETE FROM students WHERE school_name = %s AND class_name = %s AND session = %s', 
                       (school_name, class_name, session))
            students_deleted = cur.rowcount
            
            cur.execute('DELETE FROM attendance WHERE school_name = %s AND class_name = %s AND session = %s', 
                       (school_name, class_name, session))
            attendance_deleted = cur.rowcount
            
        conn.commit()
        return students_deleted > 0 or attendance_deleted > 0
    except Exception as e:
        conn.rollback()
        logger.error(f"Error deleting class data: {e}")
        return False
    finally:
        release_db(conn)


def delete_student_from_database_only(school_name, roll_no, session):
    """Delete a student from students table only (not attendance) - requires session"""
    conn = get_db()
    try:
        cur = conn.cursor()
        
        # Get student details before deletion
        cur.execute('''
            SELECT school_name, roll_no, session, name, class_name, section, subject 
            FROM students 
            WHERE school_name = %s AND roll_no = %s AND session = %s
        ''', (school_name, roll_no, session))
        student = cur.fetchone()
        
        if not student:
            return None
        
        student_info = {
            "school_name": student[0],
            "roll_no": student[1],
            "session": student[2],
            "name": student[3],
            "class_name": student[4],
            "section": student[5],
            "subject": student[6]
        }
        
        # Delete from students table only
        cur.execute('DELETE FROM students WHERE school_name = %s AND roll_no = %s AND session = %s', 
                   (school_name, roll_no, session))
        conn.commit()
        
        return student_info
    except Exception as e:
        conn.rollback()
        logger.error(f"Error deleting student from database: {e}")
        return None
    finally:
        release_db(conn)


def delete_student_from_attendance_only(school_name, roll_no, session):
    """Delete a student from attendance table only (not students database) - requires session"""
    conn = get_db()
    try:
        cur = conn.cursor()
        
        # Get student details from students table (for return info)
        cur.execute('''
            SELECT school_name, roll_no, session, name, class_name, section, subject 
            FROM students 
            WHERE school_name = %s AND roll_no = %s AND session = %s
        ''', (school_name, roll_no, session))
        student = cur.fetchone()
        
        # Count attendance records before deletion
        cur.execute('SELECT COUNT(*) FROM attendance WHERE school_name = %s AND roll_no = %s AND session = %s', 
                   (school_name, roll_no, session))
        attendance_count = cur.fetchone()[0]
        
        if attendance_count == 0:
            return None
        
        # Delete from attendance table only
        cur.execute('DELETE FROM attendance WHERE school_name = %s AND roll_no = %s AND session = %s', 
                   (school_name, roll_no, session))
        conn.commit()
        
        result = {
            "roll_no": roll_no,
            "school_name": school_name,
            "session": session,
            "attendance_records_deleted": attendance_count
        }
        
        if student:
            result["name"] = student[3]
            result["class_name"] = student[4]
            result["section"] = student[5]
            result["subject"] = student[6]
        
        return result
    except Exception as e:
        conn.rollback()
        logger.error(f"Error deleting student from attendance: {e}")
        return None
    finally:
        release_db(conn)


def delete_student_from_both(school_name, roll_no, session):
    """Delete a student from both students and attendance tables - requires session"""
    conn = get_db()
    try:
        cur = conn.cursor()
        
        # Get student details before deletion
        cur.execute('''
            SELECT school_name, roll_no, session, name, class_name, section, subject 
            FROM students 
            WHERE school_name = %s AND roll_no = %s AND session = %s
        ''', (school_name, roll_no, session))
        student = cur.fetchone()
        
        # Count attendance records
        cur.execute('SELECT COUNT(*) FROM attendance WHERE school_name = %s AND roll_no = %s AND session = %s', 
                   (school_name, roll_no, session))
        attendance_count = cur.fetchone()[0]
        
        if not student and attendance_count == 0:
            return None
        
        # Delete from both tables
        cur.execute('DELETE FROM students WHERE school_name = %s AND roll_no = %s AND session = %s', 
                   (school_name, roll_no, session))
        students_deleted = cur.rowcount
        
        cur.execute('DELETE FROM attendance WHERE school_name = %s AND roll_no = %s AND session = %s', 
                   (school_name, roll_no, session))
        
        conn.commit()
        
        result = {
            "roll_no": roll_no,
            "school_name": school_name,
            "session": session,
            "deleted_from_database": students_deleted > 0,
            "attendance_records_deleted": attendance_count
        }
        
        if student:
            result["name"] = student[3]
            result["class_name"] = student[4]
            result["section"] = student[5]
            result["subject"] = student[6]
        
        return result
    except Exception as e:
        conn.rollback()
        logger.error(f"Error deleting student from both tables: {e}")
        return None
    finally:
        release_db(conn)


def delete_bulk_from_database(school_name, class_name, section, session, subject=None):
    """Delete bulk students from database only - requires session"""
    conn = get_db()
    try:
        cur = conn.cursor()
        
        if subject:
            cur.execute('SELECT COUNT(*) FROM students WHERE school_name = %s AND class_name = %s AND section = %s AND session = %s AND subject = %s',
                       (school_name, class_name, section, session, subject))
            count = cur.fetchone()[0]
            
            cur.execute('DELETE FROM students WHERE school_name = %s AND class_name = %s AND section = %s AND session = %s AND subject = %s',
                       (school_name, class_name, section, session, subject))
        else:
            cur.execute('SELECT COUNT(*) FROM students WHERE school_name = %s AND class_name = %s AND section = %s AND session = %s',
                       (school_name, class_name, section, session))
            count = cur.fetchone()[0]
            
            cur.execute('DELETE FROM students WHERE school_name = %s AND class_name = %s AND section = %s AND session = %s',
                       (school_name, class_name, section, session))
        
        conn.commit()
        return count
    except Exception as e:
        conn.rollback()
        logger.error(f"Error bulk deleting from database: {e}")
        return 0
    finally:
        release_db(conn)


def delete_bulk_from_attendance(school_name, class_name, section, session, subject=None):
    """Delete bulk attendance records only - requires session"""
    conn = get_db()
    try:
        cur = conn.cursor()
        
        if subject:
            cur.execute('SELECT COUNT(*) FROM attendance WHERE school_name = %s AND class_name = %s AND section = %s AND session = %s AND subject = %s',
                       (school_name, class_name, section, session, subject))
            count = cur.fetchone()[0]
            
            cur.execute('DELETE FROM attendance WHERE school_name = %s AND class_name = %s AND section = %s AND session = %s AND subject = %s',
                       (school_name, class_name, section, session, subject))
        else:
            cur.execute('SELECT COUNT(*) FROM attendance WHERE school_name = %s AND class_name = %s AND section = %s AND session = %s',
                       (school_name, class_name, section, session))
            count = cur.fetchone()[0]
            
            cur.execute('DELETE FROM attendance WHERE school_name = %s AND class_name = %s AND section = %s AND session = %s',
                       (school_name, class_name, section, session))
        
        conn.commit()
        return count
    except Exception as e:
        conn.rollback()
        logger.error(f"Error bulk deleting from attendance: {e}")
        return 0
    finally:
        release_db(conn)


def delete_bulk_from_both_tables(school_name, class_name, section, session, subject=None):
    """Delete bulk from both students and attendance tables - requires session"""
    conn = get_db()
    try:
        cur = conn.cursor()
        
        if subject:
            cur.execute('SELECT COUNT(*) FROM students WHERE school_name = %s AND class_name = %s AND section = %s AND session = %s AND subject = %s',
                       (school_name, class_name, section, session, subject))
            students_count = cur.fetchone()[0]
            
            cur.execute('SELECT COUNT(*) FROM attendance WHERE school_name = %s AND class_name = %s AND section = %s AND session = %s AND subject = %s',
                       (school_name, class_name, section, session, subject))
            attendance_count = cur.fetchone()[0]
            
            cur.execute('DELETE FROM students WHERE school_name = %s AND class_name = %s AND section = %s AND session = %s AND subject = %s',
                       (school_name, class_name, section, session, subject))
            cur.execute('DELETE FROM attendance WHERE school_name = %s AND class_name = %s AND section = %s AND session = %s AND subject = %s',
                       (school_name, class_name, section, session, subject))
        else:
            cur.execute('SELECT COUNT(*) FROM students WHERE school_name = %s AND class_name = %s AND section = %s AND session = %s',
                       (school_name, class_name, section, session))
            students_count = cur.fetchone()[0]
            
            cur.execute('SELECT COUNT(*) FROM attendance WHERE school_name = %s AND class_name = %s AND section = %s AND session = %s',
                       (school_name, class_name, section, session))
            attendance_count = cur.fetchone()[0]
            
            cur.execute('DELETE FROM students WHERE school_name = %s AND class_name = %s AND section = %s AND session = %s',
                       (school_name, class_name, section, session))
            cur.execute('DELETE FROM attendance WHERE school_name = %s AND class_name = %s AND section = %s AND session = %s',
                       (school_name, class_name, section, session))
        
        conn.commit()
        return {"students_deleted": students_count, "attendance_records_deleted": attendance_count}
    except Exception as e:
        conn.rollback()
        logger.error(f"Error bulk deleting from both tables: {e}")
        return {"students_deleted": 0, "attendance_records_deleted": 0}
    finally:
        release_db(conn)


# ==================== STATISTICS AND EXPORT ====================

def get_enrollment_stats():
    """Get enrollment statistics grouped by school, class, section, and subject"""
    conn = get_db()
    try:
        cur = conn.cursor()
        
        cur.execute('SELECT COUNT(*) FROM students')
        total_students = cur.fetchone()[0]
        
        cur.execute('''
            SELECT school_name, class_name, section, subject, COUNT(*) as count
            FROM students
            GROUP BY school_name, class_name, section, subject
            ORDER BY school_name, class_name, section, subject
        ''')
        rows = cur.fetchall()
        
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
        release_db(conn)


# ==================== VECTOR SIMILARITY SEARCH ====================

def find_similar_faces(embedding, school_name, class_name, section, subject=None, limit=10, threshold=0.3):
    """
    Find similar faces using pgvector cosine similarity.
    Returns students with similarity score above threshold.
    """
    embedding = np.array(embedding, dtype=np.float32)
    embedding = l2_normalize(embedding)
    
    conn = get_db()
    try:
        cur = conn.cursor()
        
        query = '''
            SELECT roll_no, name, 1 - (embedding <=> %s::vector) as similarity
            FROM students
            WHERE school_name = %s AND class_name = %s AND section = %s
        '''
        params = [embedding.tolist(), school_name, class_name, section]
        
        if subject:
            query += ' AND subject = %s'
            params.append(subject)
        
        query += '''
            AND 1 - (embedding <=> %s::vector) >= %s
            ORDER BY similarity DESC
            LIMIT %s
        '''
        params.extend([embedding.tolist(), threshold, limit])
        
        cur.execute(query, params)
        rows = cur.fetchall()
        
        return [{
            "roll_no": row[0],
            "name": row[1],
            "similarity": float(row[2])
        } for row in rows]
    finally:
        release_db(conn)
