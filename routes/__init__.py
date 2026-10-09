from flask import request
from services.errors import ValidationError

def json_body():
    data=request.get_json(silent=True)
    if not isinstance(data,dict): raise ValidationError('Request body must be a JSON object.')
    return data
