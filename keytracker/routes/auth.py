import datetime
import functools
import logging

import requests as http_requests
from authlib.integrations.flask_client import OAuth
from flask import Blueprint, redirect, session, request, url_for, jsonify, flash
from flask_login import login_user, logout_user, login_required, current_user
from keytracker.schema import db, User

blueprint = Blueprint("auth", __name__, url_prefix="/auth")
oauth = OAuth()
logger = logging.getLogger(__name__)


def init_oauth(app):
    oauth.init_app(app)
    oauth.register(
        name="google",
        client_id=app.config.get("GOOGLE_CLIENT_ID"),
        client_secret=app.config.get("GOOGLE_CLIENT_SECRET"),
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )
    if app.config.get("PATREON_CLIENT_ID"):
        oauth.register(
            name="patreon",
            client_id=app.config.get("PATREON_CLIENT_ID"),
            client_secret=app.config.get("PATREON_CLIENT_SECRET"),
            authorize_url="https://www.patreon.com/oauth2/authorize",
            access_token_url="https://www.patreon.com/api/oauth2/token",
            client_kwargs={"scope": "identity identity.memberships"},
        )


def patron_required(f):
    """Decorator that requires the user to be logged in and an active patron."""

    @functools.wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_patron:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Patron membership required"}), 403
            flash("This feature requires an active Patreon membership.")
            return redirect("/account")
        return f(*args, **kwargs)

    return decorated


# --- Google OAuth ---


@blueprint.route("/google/login")
def google_login():
    session["auth_next"] = request.args.get("next", "/")
    redirect_uri = url_for("auth.google_callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@blueprint.route("/google/callback")
def google_callback():
    token = oauth.google.authorize_access_token()
    userinfo = token.get("userinfo")
    if userinfo is None:
        userinfo = oauth.google.userinfo()

    google_id = userinfo["sub"]
    email = userinfo.get("email")
    name = userinfo.get("name")
    avatar_url = userinfo.get("picture")

    # Find existing user by google_id or email
    user = User.query.filter_by(google_id=google_id).first()
    if user is None and email:
        user = User.query.filter_by(email=email).first()
        if user is not None:
            # Link existing account to Google
            user.google_id = google_id
            user.avatar_url = avatar_url
            if name and not user.name:
                user.name = name
            db.session.commit()

    if user is None:
        user = User(
            email=email,
            name=name,
            google_id=google_id,
            avatar_url=avatar_url,
        )
        db.session.add(user)
        db.session.commit()
    else:
        # Update avatar on each login
        if avatar_url and user.avatar_url != avatar_url:
            user.avatar_url = avatar_url
            db.session.commit()

    # Save redirect target before clearing session state.
    next_url = session.pop("auth_next", "/")
    # Clear the entire session (removes OAuth state keys left by authlib and
    # any pre-login session data) to prevent session fixation attacks.
    session.clear()
    session.permanent = True
    # No remember=True: sessions are scoped to this browser and expire after
    # PERMANENT_SESSION_LIFETIME (30 days). Each browser gets its own
    # independent session; there is no cross-device persistent token.
    login_user(user)
    return redirect(next_url)


@blueprint.route("/logout")
def logout():
    logout_user()
    session.clear()
    next_url = request.args.get("next", "/")
    return redirect(next_url)


# --- Patreon OAuth ---


def _fetch_patreon_identity(access_token):
    """Fetch the user's Patreon identity including memberships."""
    url = "https://www.patreon.com/api/oauth2/v2/identity"
    params = {
        "include": "memberships.campaign,memberships.currently_entitled_tiers",
        "fields[member]": "patron_status,currently_entitled_amount_cents",
        "fields[tier]": "title,amount_cents",
        "fields[user]": "full_name,email,image_url",
    }
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = http_requests.get(url, params=params, headers=headers)
    resp.raise_for_status()
    return resp.json()


def _check_campaign_membership(identity_response, campaign_id):
    """Parse JSONAPI response to find membership for our campaign.

    Returns (is_active, tier_title, pledge_cents).
    """
    included = identity_response.get("included", [])
    # Build a map of tier id -> title
    tier_map = {}
    for item in included:
        if item["type"] == "tier":
            tier_map[item["id"]] = item.get("attributes", {}).get("title", "")

    # Find the member record that matches our campaign
    for item in included:
        if item["type"] != "member":
            continue
        # Check if this membership is for our campaign
        campaign_data = (
            item.get("relationships", {}).get("campaign", {}).get("data", {})
        )
        if campaign_data.get("id") != str(campaign_id):
            continue

        attrs = item.get("attributes", {})
        patron_status = attrs.get("patron_status")
        pledge_cents = attrs.get("currently_entitled_amount_cents", 0)
        is_active = patron_status == "active_patron"

        # Get tier title from the entitled tiers
        tier_title = None
        tier_data = (
            item.get("relationships", {})
            .get("currently_entitled_tiers", {})
            .get("data", [])
        )
        if tier_data:
            tier_title = tier_map.get(tier_data[0]["id"])

        return is_active, tier_title, pledge_cents

    return False, None, 0


def _refresh_patreon_token(user):
    """Refresh the user's Patreon access token using the refresh token."""
    from flask import current_app

    resp = http_requests.post(
        "https://www.patreon.com/api/oauth2/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": user.patreon_refresh_token,
            "client_id": current_app.config.get("PATREON_CLIENT_ID"),
            "client_secret": current_app.config.get("PATREON_CLIENT_SECRET"),
        },
    )
    resp.raise_for_status()
    tokens = resp.json()
    user.patreon_access_token = tokens["access_token"]
    user.patreon_refresh_token = tokens["refresh_token"]
    db.session.commit()


@blueprint.route("/patreon/link")
@login_required
def patreon_link():
    redirect_uri = url_for("auth.patreon_callback", _external=True)
    return oauth.patreon.authorize_redirect(redirect_uri)


@blueprint.route("/patreon/callback")
@login_required
def patreon_callback():
    from flask import current_app

    try:
        token = oauth.patreon.authorize_access_token()
    except Exception:
        logger.exception("Failed to exchange Patreon OAuth code")
        return redirect("/account?patreon_error=oauth_failed")

    access_token = token["access_token"]
    refresh_token = token.get("refresh_token")

    try:
        identity = _fetch_patreon_identity(access_token)
    except Exception:
        logger.exception("Failed to fetch Patreon identity")
        return redirect("/account?patreon_error=identity_failed")

    patreon_user_id = identity.get("data", {}).get("id")
    campaign_id = current_app.config.get("PATREON_CAMPAIGN_ID", "")
    is_active, tier_title, pledge_cents = _check_campaign_membership(
        identity, campaign_id
    )

    # Check if this Patreon account is already linked to another user
    existing = User.query.filter_by(patreon_id=patreon_user_id).first()
    if existing and existing.id != current_user.id:
        return redirect("/account?patreon_error=already_linked")

    current_user.patreon_id = patreon_user_id
    current_user.patreon_access_token = access_token
    current_user.patreon_refresh_token = refresh_token
    current_user.is_patron = is_active
    current_user.patreon_tier_title = tier_title
    current_user.patreon_pledge_cents = pledge_cents
    current_user.patreon_linked_at = datetime.datetime.utcnow()
    db.session.commit()

    return redirect("/account?patreon_linked=true")


@blueprint.route("/patreon/unlink")
@login_required
def patreon_unlink():
    current_user.patreon_id = None
    current_user.patreon_access_token = None
    current_user.patreon_refresh_token = None
    current_user.is_patron = False
    current_user.patreon_tier_title = None
    current_user.patreon_pledge_cents = None
    current_user.patreon_linked_at = None
    db.session.commit()
    return redirect("/account")


@blueprint.route("/patreon/refresh")
@login_required
def patreon_refresh():
    from flask import current_app

    if not current_user.patreon_id:
        return redirect("/account?patreon_error=not_linked")

    try:
        _refresh_patreon_token(current_user)
    except Exception:
        logger.exception("Failed to refresh Patreon token")
        return redirect("/account?patreon_error=refresh_failed")

    try:
        identity = _fetch_patreon_identity(current_user.patreon_access_token)
    except Exception:
        logger.exception("Failed to fetch Patreon identity after refresh")
        return redirect("/account?patreon_error=identity_failed")

    campaign_id = current_app.config.get("PATREON_CAMPAIGN_ID", "")
    is_active, tier_title, pledge_cents = _check_campaign_membership(
        identity, campaign_id
    )

    current_user.is_patron = is_active
    current_user.patreon_tier_title = tier_title
    current_user.patreon_pledge_cents = pledge_cents
    db.session.commit()

    return redirect("/account?patreon_refreshed=true")
