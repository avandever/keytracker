from authlib.integrations.flask_client import OAuth
from flask import Blueprint, redirect, session, request, url_for
from flask_login import login_user, logout_user
from keytracker.schema import db, User

blueprint = Blueprint("auth", __name__, url_prefix="/auth")
oauth = OAuth()


def init_oauth(app):
    oauth.init_app(app)
    oauth.register(
        name="google",
        client_id=app.config.get("GOOGLE_CLIENT_ID"),
        client_secret=app.config.get("GOOGLE_CLIENT_SECRET"),
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )


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

    login_user(user, remember=True)
    next_url = session.pop("auth_next", "/")
    return redirect(next_url)


@blueprint.route("/logout")
def logout():
    logout_user()
    next_url = request.args.get("next", "/")
    return redirect(next_url)
