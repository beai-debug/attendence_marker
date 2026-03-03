"""
Main CLI interface for testing attendance system backend operations
"""
import sqlite3
from database import (
    init_db, 
    save_student, 
    get_students, 
    save_attendance, 
    delete_student_by_roll_no, 
    delete_class_data,
    get_enrollment_stats,
    get_students_for_export
)
import numpy as np
from datetime import datetime

def print_menu():
    print("\n" + "="*60)
    print("ATTENDANCE SYSTEM - BACKEND TESTING")
    print("="*60)
    print("1. View all students")
    print("2. View students by school/class/section/subject")
    print("3. View all attendance records")
    print("4. View attendance by school/class/section")
    print("5. Add sample student (for testing)")
    print("6. Delete student by school and roll number")
    print("7. Delete class data")
    print("8. View enrollment statistics")
    print("9. Export students to CSV")
    print("10. Clear all data (reset database)")
    print("11. Exit")
    print("="*60)

def view_all_students():
    """Display all students in the database"""
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute('SELECT school_name, roll_no, name, class_name, section, subject FROM students ORDER BY school_name, class_name, section')
    rows = c.fetchall()
    conn.close()
    
    if not rows:
        print("\nNo students found in database.")
        return
    
    print(f"\n{'School':<20} {'Roll No':<15} {'Name':<20} {'Class':<10} {'Section':<10} {'Subject':<15}")
    print("-" * 100)
    for row in rows:
        school_name, roll_no, name, class_name, section, subject = row
        subject_display = subject if subject else "N/A"
        print(f"{school_name:<20} {roll_no:<15} {name:<20} {class_name:<10} {section:<10} {subject_display:<15}")
    print(f"\nTotal students: {len(rows)}")

def view_students_by_class():
    """Display students filtered by school/class/section/subject"""
    school_name = input("Enter school name: ").strip()
    class_name = input("Enter class name: ").strip()
    section = input("Enter section: ").strip()
    subject = input("Enter subject (press Enter to skip): ").strip()
    
    if not subject:
        subject = None
    
    try:
        roll_nos, names, encodings = get_students(school_name, class_name, section, subject)
        
        if not roll_nos:
            print(f"\nNo students found for school {school_name}, class {class_name}, section {section}" + 
                  (f", subject {subject}" if subject else ""))
            return
        
        print(f"\n{'Roll No':<15} {'Name':<20}")
        print("-" * 35)
        for roll_no, name in zip(roll_nos, names):
            print(f"{roll_no:<15} {name:<20}")
        print(f"\nTotal students: {len(roll_nos)}")
    except Exception as e:
        print(f"Error: {e}")

def view_all_attendance():
    """Display all attendance records"""
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute('SELECT school_name, roll_no, student_name, class_name, section, subject, similarity_score, date, time FROM attendance ORDER BY date DESC, time DESC')
    rows = c.fetchall()
    conn.close()
    
    if not rows:
        print("\nNo attendance records found.")
        return
    
    print(f"\n{'School':<15} {'Roll No':<12} {'Name':<15} {'Class':<8} {'Section':<8} {'Subject':<10} {'Score':<8} {'Date':<12} {'Time':<12}")
    print("-" * 120)
    for row in rows:
        school_name, roll_no, name, class_name, section, subject, score, date, time = row
        subject_display = subject if subject else "N/A"
        school_display = school_name[:14] if school_name else "N/A"
        print(f"{school_display:<15} {roll_no:<12} {name:<15} {class_name:<8} {section:<8} {subject_display:<10} {score:<8.4f} {date:<12} {time:<12}")
    print(f"\nTotal records: {len(rows)}")

def view_attendance_by_class():
    """Display attendance records filtered by school/class/section"""
    school_name = input("Enter school name: ").strip()
    class_name = input("Enter class name: ").strip()
    section = input("Enter section: ").strip()
    
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute('SELECT roll_no, student_name, subject, similarity_score, date, time FROM attendance WHERE school_name=? AND class_name=? AND section=? ORDER BY date DESC, time DESC',
              (school_name, class_name, section))
    rows = c.fetchall()
    conn.close()
    
    if not rows:
        print(f"\nNo attendance records found for school {school_name}, class {class_name}, section {section}")
        return
    
    print(f"\n{'Roll No':<12} {'Name':<20} {'Subject':<15} {'Score':<8} {'Date':<12} {'Time':<12}")
    print("-" * 85)
    for row in rows:
        roll_no, name, subject, score, date, time = row
        subject_display = subject if subject else "N/A"
        print(f"{roll_no:<12} {name:<20} {subject_display:<15} {score:<8.4f} {date:<12} {time:<12}")
    print(f"\nTotal records: {len(rows)}")

def add_sample_student():
    """Add a sample student for testing"""
    print("\nAdd Sample Student")
    school_name = input("Enter school name (e.g., ABC_School): ").strip()
    roll_no = input("Enter roll number (e.g., 21045001): ").strip()
    name = input("Enter name (e.g., aman_meena): ").strip()
    class_name = input("Enter class name (e.g., 10th): ").strip()
    section = input("Enter section (e.g., A): ").strip()
    subject = input("Enter subject (press Enter to skip): ").strip()
    
    if not subject:
        subject = None
    
    # Create a dummy embedding (512-dimensional for InsightFace)
    dummy_embedding = np.random.randn(512).astype(np.float32)
    dummy_embedding = dummy_embedding / np.linalg.norm(dummy_embedding)  # Normalize
    
    face_path = f"data/faces/{school_name}_{class_name}_{section}/{roll_no}_{name}"
    
    try:
        save_student(school_name, roll_no, name, class_name, section, subject, face_path, dummy_embedding)
        print(f"\n✓ Student {name} (Roll No: {roll_no}) from school {school_name} added successfully!")
    except Exception as e:
        print(f"\n✗ Error adding student: {e}")

def delete_student():
    """Delete a student by school name and roll number"""
    print("\nDelete Student")
    school_name = input("Enter school name: ").strip()
    roll_no = input("Enter roll number to delete: ").strip()
    
    confirm = input(f"Are you sure you want to delete student with roll number {roll_no} from school {school_name}? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("Delete cancelled.")
        return
    
    try:
        success = delete_student_by_roll_no(school_name, roll_no)
        if success:
            print(f"\n✓ Student with roll number {roll_no} from school {school_name} deleted successfully!")
        else:
            print(f"\n✗ Student with roll number {roll_no} from school {school_name} not found.")
    except Exception as e:
        print(f"\n✗ Error deleting student: {e}")

def delete_class():
    """Delete class data"""
    print("\nDelete Class Data")
    school_name = input("Enter school name: ").strip()
    class_name = input("Enter class name: ").strip()
    section = input("Enter section (press Enter to delete entire class): ").strip()
    subject = input("Enter subject (press Enter to skip): ").strip()
    
    if not section:
        section = None
    if not subject:
        subject = None
    
    confirm_msg = f"school {school_name}, class {class_name}"
    if section:
        confirm_msg += f", section {section}"
    if subject:
        confirm_msg += f", subject {subject}"
    
    confirm = input(f"Are you sure you want to delete data for {confirm_msg}? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("Delete cancelled.")
        return
    
    try:
        success = delete_class_data(school_name, class_name, section, subject)
        if success:
            print(f"\n✓ Data for {confirm_msg} deleted successfully!")
        else:
            print(f"\n✗ No data found for {confirm_msg}.")
    except Exception as e:
        print(f"\n✗ Error deleting class data: {e}")

def view_enrollment_stats():
    """View enrollment statistics grouped by school, class, section, subject"""
    print("\nEnrollment Statistics")
    print("=" * 60)
    
    try:
        stats = get_enrollment_stats()
        
        print(f"\nTotal Students Enrolled: {stats['total_students']}")
        print("-" * 60)
        
        for school in stats['by_school']:
            print(f"\n📚 School: {school['school_name']} (Total: {school['total']})")
            
            for cls in school['by_class']:
                print(f"   📖 Class: {cls['class_name']} (Total: {cls['total']})")
                
                for section in cls['by_section']:
                    print(f"      📝 Section: {section['section']} (Total: {section['total']})")
                    
                    for subj in section['by_subject']:
                        print(f"         📌 Subject: {subj['subject']} - {subj['count']} students")
        
        if not stats['by_school']:
            print("\nNo enrollment data found.")
            
    except Exception as e:
        print(f"\n✗ Error fetching enrollment stats: {e}")

def export_students_csv():
    """Export students to CSV format"""
    print("\nExport Students to CSV")
    school_name = input("Enter school name (required): ").strip()
    
    if not school_name:
        print("School name is required!")
        return
    
    class_name = input("Enter class name (press Enter to skip): ").strip()
    section = input("Enter section (press Enter to skip): ").strip()
    subject = input("Enter subject (press Enter to skip): ").strip()
    
    if not class_name:
        class_name = None
    if not section:
        section = None
    if not subject:
        subject = None
    
    try:
        students = get_students_for_export(school_name, class_name, section, subject)
        
        if not students:
            print("\nNo students found matching the criteria.")
            return
        
        # Print CSV format
        print("\n" + "=" * 80)
        print("CSV OUTPUT:")
        print("=" * 80)
        print("school,roll_number,name,class,section,subject")
        
        for student in students:
            school, roll_no, name, cls, sec, subj = student
            subj_display = subj if subj else ""
            print(f"{school},{roll_no},{name},{cls},{sec},{subj_display}")
        
        print("=" * 80)
        print(f"\nTotal students: {len(students)}")
        
        # Option to save to file
        save_option = input("\nSave to file? (yes/no): ").strip().lower()
        if save_option == 'yes':
            filename_parts = [school_name]
            if class_name:
                filename_parts.append(class_name)
            if section:
                filename_parts.append(section)
            if subject:
                filename_parts.append(subject)
            filename = "_".join(filename_parts) + "_students.csv"
            
            with open(filename, 'w') as f:
                f.write("school,roll_number,name,class,section,subject\n")
                for student in students:
                    school, roll_no, name, cls, sec, subj = student
                    subj_display = subj if subj else ""
                    f.write(f"{school},{roll_no},{name},{cls},{sec},{subj_display}\n")
            
            print(f"\n✓ CSV saved to: {filename}")
            
    except Exception as e:
        print(f"\n✗ Error exporting students: {e}")

def clear_all_data():
    """Clear all data and reinitialize database"""
    print("\n⚠️  WARNING: This will delete ALL students and attendance records!")
    confirm = input("Type 'DELETE ALL' to confirm: ").strip()
    
    if confirm != 'DELETE ALL':
        print("Operation cancelled.")
        return
    
    try:
        conn = sqlite3.connect('attendance.db')
        c = conn.cursor()
        c.execute('DELETE FROM students')
        c.execute('DELETE FROM attendance')
        conn.commit()
        conn.close()
        print("\n✓ All data cleared successfully!")
    except Exception as e:
        print(f"\n✗ Error clearing data: {e}")

def main():
    """Main CLI loop"""
    # Initialize database
    init_db()
    
    while True:
        print_menu()
        choice = input("\nEnter your choice (1-11): ").strip()
        
        if choice == '1':
            view_all_students()
        elif choice == '2':
            view_students_by_class()
        elif choice == '3':
            view_all_attendance()
        elif choice == '4':
            view_attendance_by_class()
        elif choice == '5':
            add_sample_student()
        elif choice == '6':
            delete_student()
        elif choice == '7':
            delete_class()
        elif choice == '8':
            view_enrollment_stats()
        elif choice == '9':
            export_students_csv()
        elif choice == '10':
            clear_all_data()
        elif choice == '11':
            print("\nExiting... Goodbye!")
            break
        else:
            print("\n✗ Invalid choice. Please enter a number between 1 and 11.")
        
        input("\nPress Enter to continue...")

if __name__ == "__main__":
    print("\n" + "="*60)
    print("ATTENDANCE SYSTEM - Backend Testing Interface")
    print("="*60)
    print("This CLI tool allows you to test database operations directly")
    print("without using the FastAPI server.")
    print("="*60)
    
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Exiting...")
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
