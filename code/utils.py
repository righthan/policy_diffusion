import ujson
import base64


def bill_source_to_json(url,source,date):
    jsonObj = {}
    jsonObj['url'] = url
    jsonObj['date'] = date
    jsonObj['source'] = base64.b64encode(source)
    
    return ujson.encode(jsonObj)


