#!/usr/bin/env python3
"""
PostgreSQL Setup Script for Attendance Marker System
This script configures PostgreSQL for local development without requiring sudo password.
"""

import subprocess
import sys
import os

def run_command(cmd, check=True, capture_output=True):
    """Run a shell command and return the result"""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=capture_output, text=True)
    if capture_output:
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
    return result

def main():
    print("=" * 60)
    print("PostgreSQL Setup for Attendance Marker System")
    print("=" * 60)
    
    # Step 1: Check if PostgreSQL is installed
    print("\n[1/6] Checking PostgreSQL installation...")
    result = run_command("which psql")
    if result.returncode != 0:
        print("ERROR: PostgreSQL is not installed.")
        print("Please install PostgreSQL first:")
        print("  sudo apt-get update && sudo apt-get install -y postgresql postgresql-contrib")
        sys.exit(1)
    print("✓ PostgreSQL client found")
    
    # Step 2: Check if PostgreSQL service is running
    print("\n[2/6] Checking PostgreSQL service status...")
    result = run_command("service postgresql status 2>&1 || true", check=False)
    if "online" not in result.stdout.lower() and "active" not in result.stdout.lower():
        print("PostgreSQL is not running. Starting service...")
        result = run_command("service postgresql start 2>&1 || echo 'May need sudo'", check=False)
        if result.returncode != 0:
            print("NOTE: You may need to start PostgreSQL manually:")
            print("  sudo service postgresql start")
    else:
        print("✓ PostgreSQL service is running")
    
    # Step 3: Create pg_hba.conf with trust authentication for setup
    print("\n[3/6] Creating pg_hba.conf configuration...")
    pg_hba_content = """# PostgreSQL Client Authentication Configuration File
# TYPE  DATABASE        USER            ADDRESS                 METHOD

# Local connections - trust for postgres user (for initial setup)
local   all             postgres                                trust
local   all             all                                     trust

# IPv4 local connections - use md5 (password) authentication
host    all             all             127.0.0.1/32            md5

# IPv6 local connections - use md5 (password) authentication  
host    all             all             ::1/128                 md5

# Replication connections
local   replication     all                                     trust
host    replication     all             127.0.0.1/32            md5
host    replication     all             ::1/128                 md5
"""
    
    with open("/tmp/pg_hba_new.conf", "w") as f:
        f.write(pg_hba_content)
    print("✓ Created /tmp/pg_hba_new.conf")
    
    # Step 4: Find and update pg_hba.conf
    print("\n[4/6] Locating pg_hba.conf...")
    result = run_command("find /etc/postgresql -name 'pg_hba.conf' 2>/dev/null | head -1", check=False)
    pg_hba_path = result.stdout.strip()
    
    if pg_hba_path:
        print(f"Found pg_hba.conf at: {pg_hba_path}")
        print("\nTo apply the new configuration, run these commands:")
        print(f"  sudo cp /tmp/pg_hba_new.conf {pg_hba_path}")
        print("  sudo service postgresql restart")
    else:
        print("Could not find pg_hba.conf automatically")
        print("Please locate it manually and replace with /tmp/pg_hba_new.conf")
    
    # Step 5: Try to connect and set password
    print("\n[5/6] Attempting to connect to PostgreSQL...")
    
    # Try local socket connection first
    result = run_command("psql -U postgres -c 'SELECT 1;' 2>&1", check=False)
    
    if result.returncode == 0:
        print("✓ Connected to PostgreSQL successfully!")
        
        # Set password
        print("\n[6/6] Setting postgres user password...")
        result = run_command("psql -U postgres -c \"ALTER USER postgres PASSWORD 'Deepdive';\"", check=False)
        if result.returncode == 0:
            print("✓ Password set successfully!")
            
            # Install pgvector extension
            print("\nInstalling pgvector extension...")
            result = run_command("psql -U postgres -c 'CREATE EXTENSION IF NOT EXISTS vector;' 2>&1", check=False)
            if "ERROR" in result.stdout or "ERROR" in result.stderr:
                print("NOTE: pgvector extension may need to be installed:")
                print("  cd /tmp && git clone --branch v0.7.0 https://github.com/pgvector/pgvector.git")
                print("  cd pgvector && make && sudo make install")
            else:
                print("✓ pgvector extension ready")
            
            print("\n" + "=" * 60)
            print("Setup complete! You can now run the application:")
            print("  cd attendence_marker")
            print("  uvicorn app:app --host 0.0.0.0 --port 8000 --reload")
            print("=" * 60)
        else:
            print("Could not set password. Please run manually:")
            print("  psql -U postgres -c \"ALTER USER postgres PASSWORD 'Deepdive';\"")
    else:
        print("Could not connect to PostgreSQL.")
        print("\nPlease run these commands manually:")
        print("  1. sudo cp /tmp/pg_hba_new.conf /etc/postgresql/*/main/pg_hba.conf")
        print("  2. sudo service postgresql restart")
        print("  3. psql -U postgres -c \"ALTER USER postgres PASSWORD 'Deepdive';\"")
        print("  4. python setup_postgres.py  # Run this script again")

if __name__ == "__main__":
    main()
