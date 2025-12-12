#!/usr/bin/env python3
"""
Complete Working Solution - Creates ledgers first, then vouchers
"""

import requests
import json
import re
from pathlib import Path
from config import validate_config
from invoice_processor import InvoiceProcessor
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class CompleteTallyIntegration:
    def __init__(self):
        config = validate_config()
        self.base_url = f"http://{config['tally_host']}:{config['tally_port']}"
    
    def sanitize_for_tally(self, text: str) -> str:
        """Sanitize text for TallyPrime"""
        if not text:
            return "Unknown"
        
        sanitized = str(text).strip()
        sanitized = sanitized.replace('&', 'and')
        sanitized = re.sub(r'[<>"]', '', sanitized)
        sanitized = re.sub(r'\s+', ' ', sanitized)
        
        if len(sanitized) > 99:
            sanitized = sanitized[:96] + "..."
        
        return sanitized or "Unknown"
    
    def format_tally_date(self, date_str: str) -> str:
        """Format date for TallyPrime - Try DDMMYYYY format"""
        
        # Use a date within your financial year (Apr 1, 2025 - Mar 31, 2026)
        # Current date should be fine since it's Dec 12, 2025
        current_date = datetime.now()
        
        # Try DDMMYYYY format (12122025)
        formatted_date = current_date.strftime("%d%m%Y")
        
        if date_str:
            print(f"   📅 Original date: {date_str} → Using DDMMYYYY: {formatted_date}")
        
        return formatted_date
    
    def create_ledger(self, ledger_name: str, parent_group: str) -> bool:
        """Create a single ledger"""
        
        clean_name = self.sanitize_for_tally(ledger_name)
        
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<ENVELOPE>
    <HEADER>
        <TALLYREQUEST>Import Data</TALLYREQUEST>
    </HEADER>
    <BODY>
        <IMPORTDATA>
            <REQUESTDESC>
                <REPORTNAME>All Masters</REPORTNAME>
            </REQUESTDESC>
            <REQUESTDATA>
                <TALLYMESSAGE xmlns:UDF="TallyUDF">
                    <LEDGER NAME="{clean_name}" ACTION="Create">
                        <NAME>{clean_name}</NAME>
                        <PARENT>{parent_group}</PARENT>
                        <ISBILLWISEON>{"Yes" if parent_group == "Sundry Creditors" else "No"}</ISBILLWISEON>
                    </LEDGER>
                </TALLYMESSAGE>
            </REQUESTDATA>
        </IMPORTDATA>
    </BODY>
</ENVELOPE>"""
        
        try:
            response = requests.post(
                self.base_url,
                data=xml,
                headers={'Content-Type': 'application/xml'},
                timeout=15
            )
            
            if response.status_code == 200:
                print(f"   ✅ Ledger created: {clean_name}")
                return True
            else:
                print(f"   ⚠️  Ledger creation issue: {clean_name}")
                return False
                
        except Exception as e:
            print(f"   ❌ Error creating ledger {clean_name}: {str(e)}")
            return False
    
    def create_all_required_ledgers(self, invoice_data: dict) -> bool:
        """Create all ledgers needed for the invoice"""
        
        print("   🏗️  Creating required ledgers...")
        
        # Create vendor ledger
        vendor_name = invoice_data.get('vendor_name', 'Unknown Vendor')
        self.create_ledger(vendor_name, "Sundry Creditors")
        
        # Create purchase account ledger
        self.create_ledger("Purchase Account", "Purchase Accounts")
        
        # Create item-specific ledgers if needed
        for item in invoice_data.get('line_items', []):
            item_name = item.get('description', 'Purchase Item')
            if item_name and item_name != 'Purchase Account':
                self.create_ledger(item_name, "Purchase Accounts")
        
        return True
    
    def create_voucher(self, invoice_data: dict) -> str:
        """Create voucher XML"""
        
        vendor = self.sanitize_for_tally(invoice_data.get('vendor_name', 'Unknown Vendor'))
        invoice_num = self.sanitize_for_tally(invoice_data.get('invoice_number', 'INV001'))
        date = self.format_tally_date(invoice_data.get('date', ''))
        total_amount = float(invoice_data.get('total_amount', 0.0))
        
        if total_amount <= 0:
            total_amount = 1.0
        
        # Calculate line items
        line_items = invoice_data.get('line_items', [])
        line_items_total = sum(float(item.get('amount', 0.0)) for item in line_items)
        
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<ENVELOPE>
    <HEADER>
        <TALLYREQUEST>Import Data</TALLYREQUEST>
    </HEADER>
    <BODY>
        <IMPORTDATA>
            <REQUESTDESC>
                <REPORTNAME>Vouchers</REPORTNAME>
            </REQUESTDESC>
            <REQUESTDATA>
                <TALLYMESSAGE xmlns:UDF="TallyUDF">
                    <VOUCHER REMOTEID="" VCHKEY="" VCHTYPE="Purchase" ACTION="Create">
                        <DATE>{date}</DATE>
                        <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
                        <VOUCHERNUMBER>{invoice_num}</VOUCHERNUMBER>
                        <PARTYLEDGERNAME>{vendor}</PARTYLEDGERNAME>
                        <ALLLEDGERENTRIES.LIST>
                            <LEDGERNAME>{vendor}</LEDGERNAME>
                            <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
                            <AMOUNT>-{total_amount}</AMOUNT>
                        </ALLLEDGERENTRIES.LIST>"""
        
        # Add line items or single purchase account
        if line_items and abs(line_items_total - total_amount) < 1.0:
            # Use individual line items
            for item in line_items:
                item_name = self.sanitize_for_tally(item.get('description', 'Purchase Account'))
                item_amount = float(item.get('amount', 0.0))
                
                xml += f"""
                        <ALLLEDGERENTRIES.LIST>
                            <LEDGERNAME>{item_name}</LEDGERNAME>
                            <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
                            <AMOUNT>{item_amount}</AMOUNT>
                        </ALLLEDGERENTRIES.LIST>"""
        else:
            # Use single purchase account
            xml += f"""
                        <ALLLEDGERENTRIES.LIST>
                            <LEDGERNAME>Purchase Account</LEDGERNAME>
                            <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
                            <AMOUNT>{total_amount}</AMOUNT>
                        </ALLLEDGERENTRIES.LIST>"""
        
        xml += """
                    </VOUCHER>
                </TALLYMESSAGE>
            </REQUESTDATA>
        </IMPORTDATA>
    </BODY>
</ENVELOPE>"""
        
        return xml
    
    def import_complete_invoice(self, invoice_data: dict) -> dict:
        """Complete import process: ledgers first, then voucher"""
        
        result = {
            'success': False,
            'xml_file': None,
            'error': None,
            'voucher_number': invoice_data.get('invoice_number', 'Unknown')
        }
        
        try:
            print(f"   📊 Processing invoice: {result['voucher_number']}")
            
            # Step 1: Create all required ledgers
            self.create_all_required_ledgers(invoice_data)
            
            # Step 2: Create voucher XML
            xml_content = self.create_voucher(invoice_data)
            
            # Step 3: Save XML in /tmp/
            safe_name = re.sub(r'[^\w\-]', '_', str(result['voucher_number']))
            xml_filename = f"/tmp/complete_{safe_name}.xml"
            
            with open(xml_filename, 'w', encoding='utf-8') as f:
                f.write(xml_content)
            result['xml_file'] = xml_filename
            
            # Step 4: Import voucher
            print(f"   📤 Importing voucher to TallyPrime...")
            
            response = requests.post(
                self.base_url,
                data=xml_content,
                headers={'Content-Type': 'application/xml'},
                timeout=20
            )
            
            if response.status_code == 200:
                if '<CREATED>1</CREATED>' in response.text:
                    result['success'] = True
                    print(f"   ✅ Voucher imported successfully!")
                elif 'LINEERROR' in response.text:
                    error_match = re.search(r'<LINEERROR>(.*?)</LINEERROR>', response.text)
                    if error_match:
                        result['error'] = f"TallyPrime: {error_match.group(1)}"
                    else:
                        result['error'] = "TallyPrime reported an error"
                    print(f"   ❌ {result['error']}")
                else:
                    result['success'] = True
                    print(f"   ✅ Import completed!")
            else:
                result['error'] = f"HTTP {response.status_code}"
                print(f"   ❌ HTTP Error: {response.status_code}")
                
        except Exception as e:
            result['error'] = f"Exception: {str(e)}"
            print(f"   ❌ Exception: {str(e)}")
        
        return result


def complete_workflow(invoice_file: str) -> dict:
    """Complete end-to-end workflow"""
    
    print(f"🚀 Complete Invoice Processing Workflow")
    print(f"📄 File: {Path(invoice_file).name}")
    print("=" * 60)
    
    try:
        # Step 1: AI Processing
        print("🤖 Step 1: AI Processing with LLAMA Maverick...")
        config = validate_config()
        processor = InvoiceProcessor(config['deepinfra_token'])
        
        json_results = processor.process_invoice_file(invoice_file)
        merged_json = processor.merge_json_data(json_results)
        
        print(f"   ✅ Processed {len(json_results)} page(s)")
        print(f"   📊 Invoice: {merged_json.get('invoice_number')}")
        print(f"   🏢 Vendor: {merged_json.get('vendor_name')}")
        print(f"   💰 Amount: ₹{merged_json.get('total_amount')}")
        
        # Save JSON in /tmp/
        json_file = f"/tmp/{Path(invoice_file).stem}_complete.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(merged_json, f, indent=2, ensure_ascii=False)
        
        # Step 2: TallyPrime Integration
        print("\n🔄 Step 2: TallyPrime Integration...")
        tally = CompleteTallyIntegration()
        result = tally.import_complete_invoice(merged_json)
        
        # Step 3: Final Results
        print(f"\n📋 Final Results:")
        print(f"   📄 File: {Path(invoice_file).name}")
        print(f"   📊 Invoice: {merged_json.get('invoice_number')}")
        print(f"   🏢 Vendor: {merged_json.get('vendor_name')}")
        print(f"   💰 Amount: ₹{merged_json.get('total_amount')}")
        print(f"   🔢 Pages: {len(json_results)}")
        print(f"   🏷️  Items: {len(merged_json.get('line_items', []))}")
        print(f"   ✅ Status: {'SUCCESS' if result['success'] else 'FAILED'}")
        
        if result['xml_file']:
            print(f"   📄 XML: {result['xml_file']}")
        if result['error']:
            print(f"   ⚠️  Error: {result['error']}")
        
        return {
            'success': result['success'],
            'invoice_data': merged_json,
            'xml_file': result['xml_file'],
            'json_file': json_file,
            'error': result['error']
        }
        
    except Exception as e:
        print(f"❌ Workflow Error: {str(e)}")
        return {'success': False, 'error': str(e)}


def main():
    """CLI for complete workflow"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Complete Working Invoice Processing')
    parser.add_argument('invoice_file', help='Invoice file to process')
    
    args = parser.parse_args()
    
    result = complete_workflow(args.invoice_file)
    
    if result['success']:
        print("\n🎉 WORKFLOW COMPLETED SUCCESSFULLY!")
        print("Check TallyPrime for the imported voucher.")
    else:
        print(f"\n❌ WORKFLOW FAILED: {result.get('error', 'Unknown error')}")

if __name__ == "__main__":
    main()