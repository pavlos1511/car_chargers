import csv
import io
from typing import List, Type, Any
from pydantic import BaseModel
from fastapi import Request
from fastapi.responses import JSONResponse
from datetime import datetime

def to_csv(data: List[Any], schema: Type[BaseModel]) -> str:
    """
    Μετατρέπει μια λίστα από ORM αντικείμενα (data) σε CSV string.
    Συμβατό με Pydantic V2.
    """
    if not data:
        return ""

    # 1. Μετατροπή των ORM objects σε dictionaries
    #    ΑΛΛΑΓΗ: Χρησιμοποιούμε model_validate αντί για from_orm (Pydantic V2)
    rows = [schema.model_validate(item).model_dump(by_alias=True) for item in data]

    # 2. Ετοιμασία CSV buffer
    output = io.StringIO()
    
    # 3. Λήψη επικεφαλίδων (Headers)
    if rows:
        fieldnames = rows[0].keys()
    else:
        return "" # Κενό αν δεν υπάρχουν δεδομένα
    
    writer = csv.DictWriter(output, fieldnames=fieldnames, delimiter=',') 
    
    # 4. Εγγραφή
    writer.writeheader()
    writer.writerows(rows)
    
    return output.getvalue()

def create_error_response(request: Request, status_code: int, error_msg: str, debug_info: str = None):
    
    # 1. Βρίσκουμε την IP (originator)
    # Αν τρέχουμε πίσω από proxy (πχ Docker), το client.host μπορεί να είναι internal IP.
    # Για την εργασία αυτό είναι OK.
    originator = request.client.host if request.client else "unknown"

    # 2. Φτιάχνουμε το περιεχόμενο (Error Log)
    content = {
        "call": str(request.url),
        "timeref": datetime.now().strftime('%Y-%m-%d %H:%M'), # Μορφή: "YYYY-MM-DD hh:mm"
        "originator": originator,
        "return_code": status_code, # Το όνομα με κενό όπως ζητάει το PDF
        "error": error_msg,
        "debuginfo": debug_info
    }

    # 3. Επιστρέφουμε JSONResponse με τον σωστό κωδικό HTTP
    return JSONResponse(status_code=status_code, content=content)