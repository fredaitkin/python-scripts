#!/usr/bin/env python3
"""
Script to connect to the 'jukebox' MySQL database and read records from the 'songs' table.
"""

import mysql.connector
from mysql.connector import Error
import csv
import argparse

# Database connection constants
DB_HOST = 'localhost'
DB_USER = 'jbadmin'
DB_PASSWORD = 'jbadmin'
DB_NAME = 'jukebox'

# Query parameters
DEFAULT_YEAR = 2023
DEFAULT_OUTPUT_FILE = 'songs_output.csv'

# Year validation constants
MIN_YEAR = 1900
MAX_YEAR = 2100


def connect_to_database():
    """Establish connection to the MySQL database."""
    try:
        connection = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        return connection
    except Error as err:
        if err.errno == 2003:
            print("Error: Unable to connect to MySQL server. Check if it's running.")
        elif err.errno == 1045:
            print("Error: Invalid username or password.")
        elif err.errno == 1049:
            print("Error: Database 'jukebox' does not exist.")
        else:
            print(f"Error: {err}")
        return None


def read_songs(connection, year=None):
    """Read records from the songs table.
    
    Args:
        connection: Database connection object
        year: Optional year to filter songs (if None, returns all songs)
    
    Returns:
        List of tuples containing song records, or None if error occurs
    """
    # Validate year parameter if provided
    if year is not None:
        try:
            year = int(year)
        except (ValueError, TypeError):
            print(f"Error: Year must be a valid integer, got '{year}'.")
            return None
        
        if year < MIN_YEAR or year > MAX_YEAR:
            print(f"Error: Year must be between {MIN_YEAR} and {MAX_YEAR}, got {year}.")
            return None
    
    try:
        cursor = connection.cursor()

        if year is None:
            query = "SELECT ID, title FROM songs"
            cursor.execute(query)
        else:
            query = "SELECT ID, title FROM songs WHERE year = %s"
            cursor.execute(query, (year,))

        # Fetch all results
        records = cursor.fetchall()
        cursor.close()
        return records

    except Error as err:
        print(f"Error reading from database: {err}")
        return None


def display_songs(records, year=None, output_file=None):
    """Display and optionally write song records to file.

    Args:
        records: List of song records from read_songs()
        year: Optional year to include in output message
        output_file: Optional file path to write results to (CSV)
    """
    if not records:
        result_message = f"songs from {year}" if year else "songs"
        print(f"No {result_message} found in the database.")
        return

    # Determine result message
    result_message = f"songs from {year}" if year else "songs"

    # Prepare output lines for console
    output_lines = [
        f"\nFound {len(records)} {result_message}:\n",
        "-" * 80
    ]
    for record in records:
        output_lines.append(str(record))
    output_lines.append("-" * 80)

    # Display results to console
    for line in output_lines:
        print(line)

    # Write to CSV if specified
    if output_file:
        try:
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                # header
                writer.writerow(["ID", "title"])
                # rows
                for record in records:
                    writer.writerow(record)
            print(f"\nResults written to {output_file}")
        except IOError as io_err:
            print(f"Error writing to file {output_file}: {io_err}")

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Read songs from the jukebox database")
    parser.add_argument("--year", "-y", type=int, default=None,
                        help=f"Year to filter songs (default: None)")
    parser.add_argument("--output", "-o", default=None,
                        help="CSV output file path (optional)")
    args = parser.parse_args()

    connection = connect_to_database()

    if connection and connection.is_connected():
        print("Successfully connected to the jukebox database")
        
        # Read songs (filtered by year)
        records = read_songs(connection, args.year)
        # Display and optionally write to CSV
        display_songs(records, year=args.year, output_file=args.output)
        
        connection.close()
        print("\nDatabase connection closed.")
    else:
        print("Failed to connect to the database.")


if __name__ == "__main__":
    main()
