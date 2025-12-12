#!/usr/bin/env python3
"""
Invoice Processing Workflow
Processes invoice images/PDFs -> JSON -> Tally XML -> TallyPrime integration
"""

import os
import json
import base64
import requests
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class InvoiceProcessor:
    def __init__(self, deepinfra_token: str):
        self.deepinfra_token = deepinfra_token
        self.api_url = "https://api.deepinfra.com/v1/openai/chat/completions"
        self.model = "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8"
    
    def encode_image_to_base64(self, image_path: str) -> str:
        """Convert image to base64 for API"""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    def process_image_with_llm(self, image_path: str) -> Dict[str, Any]:
        """Process single image through LLAMA Maverick API"""
        try:
            # Encode image
            base64_image = self.encode_image_to_base64(image_path)
            data_url = f"data:image/jpeg;base64,{base64_image}"
            
            # Prepare API request
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.deepinfra_token}"
            }
            
            payload = {
                "model": self.model,
                "max_tokens": 4092,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": """Extract invoice data and return as JSON with this structure:
                                {
                                    "invoice_number": "",
                                    "date": "",
                                    "vendor_name": "",
                                    "vendor_address": "",
                                    "total_amount": 0.0,
                                    "tax_amount": 0.0,
                                    "line_items": [
                                        {
                                            "description": "",
                                            "quantity": 0,
                                            "rate": 0.0,
                                            "amount": 0.0
                                        }
                                    ]
                                }"""
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": data_url}
                            }
                        ]
                    }
                ]
            }
            
            response = requests.post(self.api_url, headers=headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            content = result['choices'][0]['message']['content']
            
            # Extract JSON from response
            try:
                # Try to parse as JSON directly
                return json.loads(content)
            except json.JSONDecodeError:
                # If not direct JSON, try to extract JSON block
                import re
                json_match = re.search(r'```json\n(.*?)\n```', content, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(1))
                else:
                    # Fallback: try to find JSON-like structure
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        return json.loads(json_match.group(0))
                    else:
                        raise ValueError("Could not extract JSON from LLM response")
                        
        except Exception as e:
            logger.error(f"Error processing image {image_path}: {str(e)}")
            raise
    
    def process_invoice_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Process invoice file (handles PDF pages and single images)"""
        file_path = Path(file_path)
        
        if file_path.suffix.lower() == '.pdf':
            return self.process_pdf(file_path)
        else:
            # Single image
            result = self.process_image_with_llm(str(file_path))
            return [result]
    
    def process_pdf(self, pdf_path: Path) -> List[Dict[str, Any]]:
        """Convert PDF pages to images and process each"""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise ImportError("PyMuPDF is required for PDF processing. Install with: pip install PyMuPDF")
        
        results = []
        doc = fitz.open(pdf_path)
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            pix = page.get_pixmap()
            
            # Save page as temporary image in /tmp/
            temp_image_path = f"/tmp/temp_page_{page_num}.png"
            pix.save(temp_image_path)
            
            try:
                # Process page through LLM
                page_result = self.process_image_with_llm(temp_image_path)
                results.append(page_result)
            finally:
                # Clean up temp file
                if os.path.exists(temp_image_path):
                    os.remove(temp_image_path)
        
        doc.close()
        return results
    def merge_json_data(self, json_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge multiple JSON extractions into one consolidated result"""
        if not json_list:
            return {}
        
        if len(json_list) == 1:
            return json_list[0]
        
        # Merge logic for multi-page invoices
        merged = json_list[0].copy()
        
        # Combine line items from all pages
        all_line_items = []
        total_amount = 0.0
        total_tax = 0.0
        
        for json_data in json_list:
            if 'line_items' in json_data:
                all_line_items.extend(json_data.get('line_items', []))
            
            # Sum amounts (take the highest total if different)
            if 'total_amount' in json_data:
                total_amount = max(total_amount, json_data.get('total_amount', 0.0))
            
            if 'tax_amount' in json_data:
                total_tax = max(total_tax, json_data.get('tax_amount', 0.0))
        
        merged['line_items'] = all_line_items
        merged['total_amount'] = total_amount
        merged['tax_amount'] = total_tax
        
        return merged
    
    def json_to_tally_xml(self, json_data: Dict[str, Any]) -> str:
        """Convert extracted JSON to Tally-friendly XML format"""
        from datetime import datetime
        
        # Format date properly for Tally (YYYYMMDD)
        date_str = json_data.get('date', '')
        try:
            # Try to parse various date formats
            if '-' in date_str:
                if len(date_str.split('-')[2]) == 4:  # DD-MM-YYYY
                    dt = datetime.strptime(date_str, '%d-%b-%Y')
                else:  # DD-MM-YY
                    dt = datetime.strptime(date_str, '%d-%m-%y')
            else:
                dt = datetime.now()
            tally_date = dt.strftime('%Y%m%d')
        except:
            tally_date = datetime.now().strftime('%Y%m%d')
        
        # Create proper Tally XML
        xml_content = f"""<ENVELOPE>
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
                    <VOUCHER REMOTEID="" VCHKEY="" VCHTYPE="Purchase" ACTION="Create" OBJVIEW="Invoice Voucher View">
                        <DATE>{tally_date}</DATE>
                        <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
                        <VOUCHERNUMBER>{json_data.get('invoice_number', 'AUTO')}</VOUCHERNUMBER>
                        <PARTYLEDGERNAME>{json_data.get('vendor_name', 'Sundry Creditors')}</PARTYLEDGERNAME>
                        <CSTFORMISSUETYPE/>
                        <CSTFORMRECVTYPE/>
                        <FBTPAYMENTTYPE>Default</FBTPAYMENTTYPE>
                        <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
                        <VCHGSTCLASS/>
                        <DIFFACTUALQTY>No</DIFFACTUALQTY>
                        <ISMSTFROMSYNC>No</ISMSTFROMSYNC>
                        <ASORIGINAL>No</ASORIGINAL>
                        <AUDITED>No</AUDITED>
                        <FORJOBCOSTING>No</FORJOBCOSTING>
                        <ISOPTIONAL>No</ISOPTIONAL>
                        <EFFECTIVEDATE>{tally_date}</EFFECTIVEDATE>
                        <USEFOREXCISE>No</USEFOREXCISE>
                        <ISFORJOBWORKIN>No</ISFORJOBWORKIN>
                        <ALLOWCONSUMPTION>No</ALLOWCONSUMPTION>
                        <USEFORINTEREST>No</USEFORINTEREST>
                        <USEFORGAINLOSS>No</USEFORGAINLOSS>
                        <USEFORGODOWNTRANSFER>No</USEFORGODOWNTRANSFER>
                        <USEFORCOMPOUND>No</USEFORCOMPOUND>
                        <USEFORSERVICETAX>No</USEFORSERVICETAX>
                        <ISEXCISEVOUCHER>No</ISEXCISEVOUCHER>
                        <EXCISETAXOVERRIDE>No</EXCISETAXOVERRIDE>
                        <USEFORTAXUNITTRANSFER>No</USEFORTAXUNITTRANSFER>
                        <IGNOREPOSVALIDATION>No</IGNOREPOSVALIDATION>
                        <EXCISEOPENING>No</EXCISEOPENING>
                        <USEFORFINALPRODUCTION>No</USEFORFINALPRODUCTION>
                        <ISTDSOVERRIDDEN>No</ISTDSOVERRIDDEN>
                        <ISTCSOVERRIDDEN>No</ISTCSOVERRIDDEN>
                        <ISTDSTCSCASHVCH>No</ISTDSTCSCASHVCH>
                        <INCLUDEADVPYMTVCH>No</INCLUDEADVPYMTVCH>
                        <ISSUBWORKSCONTRACT>No</ISSUBWORKSCONTRACT>
                        <ISVATOVERRIDDEN>No</ISVATOVERRIDDEN>
                        <IGNOREORIGVCHDATE>No</IGNOREORIGVCHDATE>
                        <ISVATPAIDATCUSTOMS>No</ISVATPAIDATCUSTOMS>
                        <ISDECLAREDTOCUSTOMS>No</ISDECLAREDTOCUSTOMS>
                        <ISSERVICETAXOVERRIDDEN>No</ISSERVICETAXOVERRIDDEN>
                        <ISISDVOUCHER>No</ISISDVOUCHER>
                        <ISEXCISEOVERRIDDEN>No</ISEXCISEOVERRIDDEN>
                        <ISEXCISESUPPLYVCH>No</ISEXCISESUPPLYVCH>
                        <ISGSTOVERRIDDEN>No</ISGSTOVERRIDDEN>
                        <GSTNOTEXPORTED>No</GSTNOTEXPORTED>
                        <IGNOREGSTINVALIDATION>No</IGNOREGSTINVALIDATION>
                        <ISGSTREFUND>No</ISGSTREFUND>
                        <OVRDNEWAYBILLTHRESHOLD>No</OVRDNEWAYBILLTHRESHOLD>
                        <ISGSTSECSEVENAPPLICABLE>No</ISGSTSECSEVENAPPLICABLE>
                        <ISVATPRINCIPALACCOUNT>No</ISVATPRINCIPALACCOUNT>
                        <VCHSTATUSISVCHNUMUSED>No</VCHSTATUSISVCHNUMUSED>
                        <VCHGSTSTATUSISINCLUDED>No</VCHGSTSTATUSISINCLUDED>
                        <VCHGSTSTATUSISUNCERTAIN>No</VCHGSTSTATUSISUNCERTAIN>
                        <VCHGSTSTATUSISEXCLUDED>No</VCHGSTSTATUSISEXCLUDED>
                        <VCHGSTSTATUSISAPPLICABLE>No</VCHGSTSTATUSISAPPLICABLE>
                        <VCHGSTSTATUSISGSTR2BRECONCILED>No</VCHGSTSTATUSISGSTR2BRECONCILED>
                        <VCHGSTSTATUSISGSTR2BONLYINPORTAL>No</VCHGSTSTATUSISGSTR2BONLYINPORTAL>
                        <VCHGSTSTATUSISGSTR2BONLYINBOOKS>No</VCHGSTSTATUSISGSTR2BONLYINBOOKS>
                        <VCHGSTSTATUSISGSTR2BMISMATCH>No</VCHGSTSTATUSISGSTR2BMISMATCH>
                        <VCHGSTSTATUSISGSTR2BINDIFFPERIOD>No</VCHGSTSTATUSISGSTR2BINDIFFPERIOD>
                        <VCHGSTSTATUSISRETEFFDATEOVERRDN>No</VCHGSTSTATUSISRETEFFDATEOVERRDN>
                        <VCHGSTSTATUSISOVERRDN>No</VCHGSTSTATUSISOVERRDN>
                        <VCHGSTSTATUSISSTATINDIFFDATE>No</VCHGSTSTATUSISSTATINDIFFDATE>
                        <VCHGSTSTATUSISRETINDIFFDATE>No</VCHGSTSTATUSISRETINDIFFDATE>
                        <VCHGSTSTATUSMAINSECTIONEXCLUDED>No</VCHGSTSTATUSMAINSECTIONEXCLUDED>
                        <VCHGSTSTATUSISBRANCHTRANSFEROUT>No</VCHGSTSTATUSISBRANCHTRANSFEROUT>
                        <VCHGSTSTATUSISSYSTEMGENERATED>No</VCHGSTSTATUSISSYSTEMGENERATED>
                        <VCHSTATUSISUNREGISTEREDRCM>No</VCHSTATUSISUNREGISTEREDRCM>
                        <VCHSTATUSISOPTIONAL>No</VCHSTATUSISOPTIONAL>
                        <VCHSTATUSISCANCELLED>No</VCHSTATUSISCANCELLED>
                        <VCHSTATUSISDELETED>No</VCHSTATUSISDELETED>
                        <VCHSTATUSISOPENINGBALANCE>No</VCHSTATUSISOPENINGBALANCE>
                        <VCHSTATUSISFETCHEDONLY>No</VCHSTATUSISFETCHEDONLY>
                        <PAYMENTLINKHASMULTIREF>No</PAYMENTLINKHASMULTIREF>
                        <ISSHIPPINGWITHINSTATE>No</ISSHIPPINGWITHINSTATE>
                        <ISOVERSEASTOURISTTRANS>No</ISOVERSEASTOURISTTRANS>
                        <ISDESIGNATEDZONEPARTY>No</ISDESIGNATEDZONEPARTY>
                        <HASCASHFLOW>Yes</HASCASHFLOW>
                        <ISPOSTDATED>No</ISPOSTDATED>
                        <USETRACKINGNUMBER>No</USETRACKINGNUMBER>
                        <ISINVOICE>Yes</ISINVOICE>
                        <MFGJOURNAL>No</MFGJOURNAL>
                        <HASDISCOUNTS>No</HASDISCOUNTS>
                        <ASPAYSLIP>No</ASPAYSLIP>
                        <ISCOSTCENTRE>No</ISCOSTCENTRE>
                        <ISSTXNONREALIZEDVCH>No</ISSTXNONREALIZEDVCH>
                        <ISEXCISEMANUFACTURERVCH>No</ISEXCISEMANUFACTURERVCH>
                        <ISBLANKCHEQUE>No</ISBLANKCHEQUE>
                        <ISVOID>No</ISVOID>
                        <ORDERLINESTATUS>No</ORDERLINESTATUS>
                        <VATISAGNSTCANCSALES>No</VATISAGNSTCANCSALES>
                        <VATISPURCEXEMPTED>No</VATISPURCEXEMPTED>
                        <ISVATRESTAXINVOICE>No</ISVATRESTAXINVOICE>
                        <VATISASSESABLECALCVCH>No</VATISASSESABLECALCVCH>
                        <ISVATDUTYPAID>Yes</ISVATDUTYPAID>
                        <ISDELIVERYSAMEASCONSIGNEE>No</ISDELIVERYSAMEASCONSIGNEE>
                        <ISDISPATCHSAMEASCONSIGNOR>No</ISDISPATCHSAMEASCONSIGNOR>
                        <CHANGEVCHMODE>No</CHANGEVCHMODE>
                        <RESETIRNQRCODE>No</RESETIRNQRCODE>
                        <ALTERID>1</ALTERID>
                        <MASTERID>2</MASTERID>
                        <VOUCHERKEY>192837465019283746502</VOUCHERKEY>
                        <ALLLEDGERENTRIES.LIST>
                            <LEDGERNAME>{json_data.get('vendor_name', 'Sundry Creditors')}</LEDGERNAME>
                            <GSTCLASS/>
                            <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
                            <LEDGERFROMITEM>No</LEDGERFROMITEM>
                            <REMOVEZEROENTRIES>No</REMOVEZEROENTRIES>
                            <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
                            <AMOUNT>-{json_data.get('total_amount', 0.0)}</AMOUNT>
                        </ALLLEDGERENTRIES.LIST>"""
        
        # Add line items
        for item in json_data.get('line_items', []):
            xml_content += f"""
                        <ALLLEDGERENTRIES.LIST>
                            <LEDGERNAME>Purchase Account</LEDGERNAME>
                            <GSTCLASS/>
                            <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
                            <LEDGERFROMITEM>No</LEDGERFROMITEM>
                            <REMOVEZEROENTRIES>No</REMOVEZEROENTRIES>
                            <ISPARTYLEDGER>No</ISPARTYLEDGER>
                            <AMOUNT>{item.get('amount', 0.0)}</AMOUNT>
                        </ALLLEDGERENTRIES.LIST>"""
        
        # Add tax if applicable
        if json_data.get('tax_amount', 0.0) > 0:
            xml_content += f"""
                        <ALLLEDGERENTRIES.LIST>
                            <LEDGERNAME>Input Tax</LEDGERNAME>
                            <GSTCLASS/>
                            <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
                            <LEDGERFROMITEM>No</LEDGERFROMITEM>
                            <REMOVEZEROENTRIES>No</REMOVEZEROENTRIES>
                            <ISPARTYLEDGER>No</ISPARTYLEDGER>
                            <AMOUNT>{json_data.get('tax_amount', 0.0)}</AMOUNT>
                        </ALLLEDGERENTRIES.LIST>"""
        
        xml_content += """
                    </VOUCHER>
                </TALLYMESSAGE>
            </REQUESTDATA>
        </IMPORTDATA>
    </BODY>
</ENVELOPE>"""
        
        return xml_content
    
    def save_xml(self, xml_content: str, output_path: str) -> None:
        """Save XML content to file"""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(xml_content)
        logger.info(f"XML saved to {output_path}")
    
    def process_workflow(self, input_file: str, output_xml: str = None) -> str:
        """Complete end-to-end workflow"""
        logger.info(f"Starting workflow for {input_file}")
        
        # Step 1: Process invoice file
        json_results = self.process_invoice_file(input_file)
        logger.info(f"Extracted {len(json_results)} JSON results")
        
        # Step 2: Merge JSON data (for multi-page PDFs)
        merged_json = self.merge_json_data(json_results)
        
        # Save intermediate JSON in /tmp/
        json_output = f"/tmp/{Path(input_file).stem}_extracted.json"
        with open(json_output, 'w') as f:
            json.dump(merged_json, f, indent=2)
        logger.info(f"Merged JSON saved to {json_output}")
        
        # Step 3: Convert to Tally XML
        xml_content = self.json_to_tally_xml(merged_json)
        
        # Step 4: Save XML in /tmp/
        if not output_xml:
            output_xml = f"/tmp/{Path(input_file).stem}_tally.xml"
        
        self.save_xml(xml_content, output_xml)
        
        return output_xml


def main():
    """Main function for CLI usage"""
    import argparse
    from config import validate_config
    
    parser = argparse.ArgumentParser(description='Process invoices for Tally integration')
    parser.add_argument('input_file', help='Input invoice file (PDF/JPG/PNG)')
    parser.add_argument('--output', '-o', help='Output XML file path')
    parser.add_argument('--token', help='DeepInfra API token (overrides config)')
    
    args = parser.parse_args()
    
    try:
        # Get configuration
        config = validate_config()
        token = args.token or config['deepinfra_token']
    except ValueError as e:
        print(f"Configuration Error: {e}")
        return 1
    
    try:
        processor = InvoiceProcessor(token)
        output_file = processor.process_workflow(args.input_file, args.output)
        print(f"Success! Tally XML generated: {output_file}")
        return 0
    except Exception as e:
        print(f"Error: {str(e)}")
        return 1


if __name__ == "__main__":
    exit(main())