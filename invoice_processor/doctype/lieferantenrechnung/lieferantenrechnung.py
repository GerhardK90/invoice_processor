import frappe
from frappe.model.document import Document
import requests
import json
import os
from frappe.utils.file_manager import get_file_path
import fitz  # PyMuPDF
from typing import Dict, Any, List

class Lieferantenrechnung(Document):
    def validate(self):
        if self.pdf_datei and not self.status == "Abgeschlossen":
            self.status = "Verarbeitung"
            self.process_invoice()

    def process_invoice(self):
        try:
            # Extract text from PDF
            pdf_path = get_file_path(self.pdf_datei)
            text = self.extract_text_from_pdf(pdf_path)
            
            # Process with AI
            invoice_data = self.process_with_ai(text)
            
            # Update document fields
            self.update_fields(invoice_data)
            
            # Create or update supplier
            if not self.lieferant:
                self.create_supplier()
            
            # Create items if they don't exist
            self.create_items()
            
            # Create purchase invoice
            self.create_purchase_invoice()
            
            self.status = "Abgeschlossen"
            
        except Exception as e:
            self.status = "Fehler"
            frappe.log_error(f"Fehler bei der Rechnungsverarbeitung: {str(e)}", "Invoice Processing Error")
            raise

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()
        return text

    def process_with_ai(self, text: str) -> Dict[str, Any]:
        # Replace with your AI model API endpoint and key
        api_endpoint = "https://api.openai.com/v1/chat/completions"
        api_key = frappe.get_value("Invoice Processor Settings", None, "openai_api_key")
        
        if not api_key:
            frappe.throw("OpenAI API Key nicht konfiguriert")

        prompt = f"""
        Extrahiere die folgenden Informationen aus der Rechnung:
        - Lieferantenname
        - Lieferantenadresse
        - Rechnungsnummer
        - Rechnungsdatum (YYYY-MM-DD)
        - Fälligkeitsdatum (YYYY-MM-DD)
        - Nettobetrag
        - Mehrwertsteuer
        - Bruttobetrag
        - Artikel (Liste mit: Name, Menge, Einheit, Einzelpreis, Mehrwertsteuersatz)

        Rechnungstext:
        {text}

        Antworte im JSON Format.
        """

        response = requests.post(
            api_endpoint,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3
            }
        )

        if response.status_code != 200:
            frappe.throw(f"Fehler bei der AI-Verarbeitung: {response.text}")

        return json.loads(response.json()["choices"][0]["message"]["content"])

    def update_fields(self, invoice_data: Dict[str, Any]):
        self.lieferant_name = invoice_data.get("Lieferantenname")
        self.lieferant_adresse = invoice_data.get("Lieferantenadresse")
        self.rechnungsnummer = invoice_data.get("Rechnungsnummer")
        self.rechnungsdatum = invoice_data.get("Rechnungsdatum")
        self.faelligkeitsdatum = invoice_data.get("Fälligkeitsdatum")
        self.nettobetrag = invoice_data.get("Nettobetrag")
        self.mehrwertsteuer = invoice_data.get("Mehrwertsteuer")
        self.bruttobetrag = invoice_data.get("Bruttobetrag")
        
        self.positionen = []
        for item in invoice_data.get("Artikel", []):
            self.append("positionen", {
                "artikel_name": item["Name"],
                "menge": item["Menge"],
                "einheit": item["Einheit"],
                "einzelpreis": item["Einzelpreis"],
                "mehrwertsteuer": item["Mehrwertsteuersatz"],
                "gesamtpreis": float(item["Menge"]) * float(item["Einzelpreis"])
            })

    def create_supplier(self):
        if not frappe.db.exists("Supplier", {"supplier_name": self.lieferant_name}):
            supplier = frappe.get_doc({
                "doctype": "Supplier",
                "supplier_name": self.lieferant_name,
                "supplier_group": "Alle Lieferanten",  # Adjust as needed
                "supplier_type": "Company",  # Adjust as needed
                "address_line1": self.lieferant_adresse
            })
            supplier.insert()
            self.lieferant = supplier.name
        else:
            self.lieferant = frappe.get_value("Supplier", {"supplier_name": self.lieferant_name}, "name")

    def create_items(self):
        for item in self.positionen:
            if not item.artikel and item.artikel_name:
                if not frappe.db.exists("Item", {"item_name": item.artikel_name}):
                    new_item = frappe.get_doc({
                        "doctype": "Item",
                        "item_name": item.artikel_name,
                        "item_code": frappe.generate_hash("", 10),
                        "item_group": "Alle Artikel",  # Adjust as needed
                        "stock_uom": item.einheit or "Stück",
                        "is_stock_item": 1,
                        "standard_rate": item.einzelpreis
                    })
                    new_item.insert()
                    item.artikel = new_item.name
                else:
                    item.artikel = frappe.get_value("Item", {"item_name": item.artikel_name}, "name")

    def create_purchase_invoice(self):
        if not self.erstellte_lieferantenrechnung:
            pi = frappe.get_doc({
                "doctype": "Purchase Invoice",
                "supplier": self.lieferant,
                "posting_date": self.rechnungsdatum,
                "due_date": self.faelligkeitsdatum,
                "bill_no": self.rechnungsnummer,
                "items": [
                    {
                        "item_code": pos.artikel,
                        "qty": pos.menge,
                        "rate": pos.einzelpreis,
                        "uom": pos.einheit
                    }
                    for pos in self.positionen if pos.artikel
                ]
            })
            pi.insert()
            self.erstellte_lieferantenrechnung = pi.name 