import hashlib
from flask import jsonify, request, Response


def etag_response(data):
    """Return a JSON response with an ETag header.

    Computes an MD5 hash of the serialized response body and includes it as an
    ETag header. If the request carries a matching ``If-None-Match`` header the
    server returns 304 Not Modified (empty body) instead of the full payload,
    allowing clients to skip redundant work when data has not changed.
    """
    resp = jsonify(data)
    body = resp.get_data()
    etag = '"' + hashlib.md5(body).hexdigest() + '"'
    if request.headers.get("If-None-Match") == etag:
        return Response(status=304, headers={"ETag": etag})
    resp.headers["ETag"] = etag
    return resp
