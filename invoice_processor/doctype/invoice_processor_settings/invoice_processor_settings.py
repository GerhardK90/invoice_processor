import frappe
from frappe.model.document import Document
import requests

class InvoiceProcessorSettings(Document):
    def validate(self):
        if not self.openai_api_key:
            frappe.throw("API Key is required")

@frappe.whitelist()
def test_api_key(api_key):
    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": "test"}],
                "max_tokens": 5
            }
        )
        return response.status_code == 200
    except:
        return False 