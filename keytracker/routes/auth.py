import datetime
import functools
import logging
import secrets

import requests as http_requests
from authlib.integrations.flask_client import OAuth
from flask import (
    Blueprint,
    redirect,
    session,
    request,
    url_for,
    jsonify,
    flash,
    current_app,
)
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


def member_required(f):
    """Decorator that requires the user to be logged in and a member (patron or free membership)."""

    @functools.wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_member:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Membership required"}), 403
            flash("This feature requires a membership.")
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
    login_user(user)
    return redirect(next_url)


@blueprint.route("/google/link")
@login_required
def google_link():
    redirect_uri = url_for("auth.google_link_callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@blueprint.route("/google/link_callback")
@login_required
def google_link_callback():
    try:
        token = oauth.google.authorize_access_token()
    except Exception:
        logger.exception("Failed to exchange Google OAuth code during link")
        return redirect("/account?google_error=oauth_failed")

    userinfo = token.get("userinfo") or oauth.google.userinfo()
    google_id = userinfo["sub"]
    avatar_url = userinfo.get("picture")

    # Check if already linked to another account
    existing = User.query.filter_by(google_id=google_id).first()
    if existing and existing.id != current_user.id:
        return redirect("/account?google_error=already_linked")

    current_user.google_id = google_id
    current_user.avatar_url = avatar_url
    db.session.commit()
    return redirect("/account?google_linked=true")


@blueprint.route("/google/unlink")
@login_required
def google_unlink():
    # Safety: don't allow unlink if user has no password fallback
    if not current_user.password_hash:
        return redirect("/account?google_error=cannot_unlink_no_password")
    current_user.google_id = None
    current_user.avatar_url = None
    db.session.commit()
    return redirect("/account")


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


# --- Email/password authentication ---

_MIN_PASSWORD_LENGTH = 8
_RECAPTCHA_VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"
_RECAPTCHA_SCORE_THRESHOLD = 0.5


def _app_base_url() -> str:
    return current_app.config.get("APP_BASE_URL", request.host_url.rstrip("/"))


def _verify_recaptcha(token: str) -> bool:
    secret = current_app.config.get("RECAPTCHA_SECRET_KEY", "")
    if not secret:
        return True  # Not configured — skip in dev
    try:
        resp = http_requests.post(
            _RECAPTCHA_VERIFY_URL,
            data={"secret": secret, "response": token},
            timeout=5,
        )
        result = resp.json()
        logger.debug("reCAPTCHA response: %s", result)
        return (
            bool(result.get("success"))
            and result.get("score", 0) >= _RECAPTCHA_SCORE_THRESHOLD
        )
    except Exception:
        logger.exception("reCAPTCHA verification request failed")
        return False


@blueprint.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    name = (data.get("name") or "").strip()
    password = data.get("password") or ""
    recaptcha_token = data.get("recaptcha_token") or ""

    secret_key = current_app.config.get("RECAPTCHA_SECRET_KEY", "")
    if secret_key and not recaptcha_token:
        return jsonify({"error": "reCAPTCHA verification required."}), 400
    if recaptcha_token and not _verify_recaptcha(recaptcha_token):
        return (
            jsonify({"error": "reCAPTCHA verification failed. Please try again."}),
            400,
        )

    if not email or not password or not name:
        return jsonify({"error": "Email, name, and password are required."}), 400

    if len(password) < _MIN_PASSWORD_LENGTH:
        return (
            jsonify(
                {
                    "error": f"Password must be at least {_MIN_PASSWORD_LENGTH} characters."
                }
            ),
            400,
        )

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "An account with this email already exists."}), 409

    user = User(email=email, name=name, email_verified=False)
    user.set_password(password)
    user.email_verification_token = secrets.token_urlsafe(32)
    user.verification_token_expires_at = (
        datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    )
    db.session.add(user)
    db.session.commit()

    try:
        from keytracker.utils import send_verification_email

        send_verification_email(user, _app_base_url())
    except Exception:
        logger.exception("Failed to send verification email to %s", email)

    session.clear()
    session.permanent = True
    login_user(user)
    return jsonify({"redirect": "/verify-email"}), 201


@blueprint.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    next_url = data.get("next") or "/"

    user = User.query.filter_by(email=email).first()
    if user is None or not user.check_password(password):
        return jsonify({"error": "Invalid email or password."}), 401

    if not user.email_verified:
        session.clear()
        session.permanent = True
        login_user(user)
        return jsonify({"redirect": "/verify-email"}), 200

    session.clear()
    session.permanent = True
    login_user(user)
    return jsonify({"redirect": next_url}), 200


@blueprint.route("/verify-email/<token>")
def verify_email(token):
    user = User.query.filter_by(email_verification_token=token).first()
    if user is None:
        return redirect("/login?error=invalid_token")
    if (
        user.verification_token_expires_at
        and datetime.datetime.utcnow() > user.verification_token_expires_at
    ):
        return redirect("/verify-email?expired=1")

    user.email_verified = True
    user.email_verification_token = None
    user.verification_token_expires_at = None
    db.session.commit()

    if not current_user.is_authenticated:
        session.clear()
        session.permanent = True
        login_user(user)

    return redirect("/?verified=1")


@blueprint.route("/resend-verification", methods=["POST"])
@login_required
def resend_verification():
    if current_user.email_verified:
        return jsonify({"message": "Email already verified."}), 200

    current_user.email_verification_token = secrets.token_urlsafe(32)
    current_user.verification_token_expires_at = (
        datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    )
    db.session.commit()

    try:
        from keytracker.utils import send_verification_email

        send_verification_email(current_user, _app_base_url())
    except Exception:
        logger.exception(
            "Failed to resend verification email to %s", current_user.email
        )
        return jsonify({"error": "Failed to send email. Please try again later."}), 500

    return jsonify({"message": "Verification email sent."}), 200


@blueprint.route("/forgot-password", methods=["POST"])
def forgot_password():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()

    user = User.query.filter_by(email=email).first()
    if user:
        user.password_reset_token = secrets.token_urlsafe(32)
        user.password_reset_token_expires_at = (
            datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        )
        db.session.commit()
        logger.info(f"Sending mail to {email}")
        try:
            from keytracker.utils import send_password_reset_email

            send_password_reset_email(user, _app_base_url())
        except Exception:
            logger.exception("Failed to send password reset email to %s", email)

    else:
        logger.error(f"No user found with email {email}")
    # Always succeed — don't reveal whether email exists
    return (
        jsonify({"message": "If that email exists, a reset link has been sent."}),
        200,
    )


@blueprint.route("/reset-password/<token>", methods=["GET"])
def reset_password_get(token):
    user = User.query.filter_by(password_reset_token=token).first()
    if user is None or (
        user.password_reset_token_expires_at
        and datetime.datetime.utcnow() > user.password_reset_token_expires_at
    ):
        return redirect("/forgot-password?expired=1")
    return redirect(f"/reset-password?token={token}")


@blueprint.route("/reset-password/<token>", methods=["POST"])
def reset_password_post(token):
    user = User.query.filter_by(password_reset_token=token).first()
    if user is None:
        return jsonify({"error": "Invalid or expired reset link."}), 400
    if (
        user.password_reset_token_expires_at
        and datetime.datetime.utcnow() > user.password_reset_token_expires_at
    ):
        return (
            jsonify(
                {"error": "This reset link has expired. Please request a new one."}
            ),
            400,
        )

    data = request.get_json(silent=True) or {}
    password = data.get("password") or ""
    if len(password) < _MIN_PASSWORD_LENGTH:
        return (
            jsonify(
                {
                    "error": f"Password must be at least {_MIN_PASSWORD_LENGTH} characters."
                }
            ),
            400,
        )

    user.set_password(password)
    user.password_reset_token = None
    user.password_reset_token_expires_at = None
    user.email_verified = True  # Verifying via reset link also confirms email ownership
    db.session.commit()

    session.clear()
    session.permanent = True
    login_user(user)
    return jsonify({"redirect": "/?reset=1"}), 200
