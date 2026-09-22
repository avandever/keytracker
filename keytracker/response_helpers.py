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
    # "no-cache" means store it but check before reusing, which is what makes
    # the ETag worth having: without it the browser has no instruction to
    # revalidate, so it either refetches in full or serves something stale.
    # "private" keeps a per-user payload out of any shared cache.
    cache_control = "private, no-cache"
    if _matches(request.headers.get("If-None-Match"), etag):
        return Response(
            status=304,
            headers={"ETag": etag, "Cache-Control": cache_control},
        )
    resp.headers["ETag"] = etag
    resp.headers["Cache-Control"] = cache_control
    return resp


def _normalize(tag: str) -> str:
    """An ETag reduced to the value both sides agree on.

    Compared as raw strings, a revalidation that should hit never does. A proxy
    that compresses the response marks the tag weak, so the client sends back
    W/"abc" for a tag issued as "abc"; a client may also send several tags, or
    the wildcard.
    """
    tag = tag.strip()
    if tag.startswith("W/"):
        tag = tag[2:]
    return tag.strip().strip('"')


def _matches(if_none_match, etag: str) -> bool:
    """Does the request's If-None-Match cover this ETag?"""
    if not if_none_match:
        return False
    if if_none_match.strip() == "*":
        return True
    wanted = _normalize(etag)
    return any(_normalize(part) == wanted for part in if_none_match.split(","))
