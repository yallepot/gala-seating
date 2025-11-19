"""
Import tickets from CSV file
CSV format: ticket_number,full_name
Example: GALA-0001,John Smith
"""

import csv
import sys
from app import app, db, Ticket

def import_tickets_from_csv(filename='tickets.csv'):
    """Import tickets from CSV file"""
    
    with app.app_context():
        try:
            # Read CSV file
            with open(filename, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                
                # Validate headers
                if 'ticket_number' not in reader.fieldnames or 'full_name' not in reader.fieldnames:
                    print("❌ Error: CSV must have columns 'ticket_number' and 'full_name'")
                    return False
                
                tickets_to_add = []
                line_num = 1
                
                for row in reader:
                    line_num += 1
                    ticket_number = row['ticket_number'].strip().upper()
                    full_name = row['full_name'].strip()
                    
                    if not ticket_number or not full_name:
                        print(f"⚠️  Warning: Skipping empty row at line {line_num}")
                        continue
                    
                    # Check if ticket already exists
                    existing = Ticket.query.filter_by(ticket_number=ticket_number).first()
                    if existing:
                        print(f"⚠️  Warning: Ticket {ticket_number} already exists, skipping")
                        continue
                    
                    ticket = Ticket(
                        ticket_number=ticket_number,
                        full_name=full_name,
                        is_used=False
                    )
                    tickets_to_add.append(ticket)
                
                # Add all tickets
                if tickets_to_add:
                    db.session.bulk_save_objects(tickets_to_add)
                    db.session.commit()
                    print(f"\n✅ Successfully imported {len(tickets_to_add)} tickets!")
                    
                    # Show sample
                    print("\nSample tickets:")
                    for ticket in tickets_to_add[:5]:
                        print(f"  {ticket.ticket_number}: {ticket.full_name}")
                    
                    if len(tickets_to_add) > 5:
                        print(f"  ... and {len(tickets_to_add) - 5} more")
                    
                    return True
                else:
                    print("⚠️  No new tickets to import")
                    return False
                    
        except FileNotFoundError:
            print(f"❌ Error: File '{filename}' not found")
            print("\nCreate a CSV file with this format:")
            print("ticket_number,full_name")
            print("GALA-0001,John Smith")
            print("GALA-0002,Jane Doe")
            return False
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            db.session.rollback()
            return False

def show_ticket_stats():
    """Display current ticket statistics"""
    with app.app_context():
        total = Ticket.query.count()
        used = Ticket.query.filter_by(is_used=True).count()
        available = total - used
        
        print("\n" + "="*50)
        print("TICKET STATISTICS")
        print("="*50)
        print(f"Total tickets:     {total}")
        print(f"Used tickets:      {used}")
        print(f"Available tickets: {available}")
        print("="*50)

def create_sample_csv():
    """Create a sample CSV file"""
    sample_data = [
        ['ticket_number', 'full_name'],
        ['GALA-0001', 'John Smith'],
        ['GALA-0002', 'Jane Doe'],
        ['GALA-0003', 'Bob Johnson'],
        ['GALA-0004', 'Alice Williams'],
        ['GALA-0005', 'Charlie Brown']
    ]
    
    filename = 'tickets_sample.csv'
    with open(filename, 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerows(sample_data)
    
    print(f"✅ Created sample file: {filename}")
    print("Edit this file with your real ticket data, then run:")
    print(f"python import_tickets.py {filename}")

if __name__ == '__main__':
    print("="*50)
    print("GALA SEATING - TICKET IMPORT UTILITY")
    print("="*50)
    print()
    
    # Check command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == '--sample':
            create_sample_csv()
        elif sys.argv[1] == '--stats':
            show_ticket_stats()
        else:
            filename = sys.argv[1]
            print(f"Importing from: {filename}\n")
            if import_tickets_from_csv(filename):
                show_ticket_stats()
    else:
        # Default: import from tickets.csv
        print("Importing from: tickets.csv\n")
        if import_tickets_from_csv('tickets.csv'):
            show_ticket_stats()
        else:
            print("\n💡 Need help?")
            print("  Create sample: python import_tickets.py --sample")
            print("  Show stats:    python import_tickets.py --stats")
            print("  Import file:   python import_tickets.py your_file.csv")
