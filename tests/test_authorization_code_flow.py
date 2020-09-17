from . import client_credentials
from authlib.oauth2.rfc7636 import create_s256_code_challenge
from urllib.parse import urlsplit, parse_qs
from oidc_ldap_bridge.models import AuthorizationCode, Token, Consent
from werkzeug.security import gen_salt


def test_authorization_code_flow(testclient, slapd_connection, logged_user, client):
    res = testclient.get(
        "/oauth/authorize",
        params=dict(
            response_type="code",
            client_id=client.oauthClientID,
            scope="profile",
            nonce="somenonce",
        ),
    )
    assert 200 == res.status_code

    res = res.forms["accept"].submit()
    assert 302 == res.status_code

    assert res.location.startswith(client.oauthRedirectURIs[0])
    params = parse_qs(urlsplit(res.location).query)
    code = params["code"][0]
    authcode = AuthorizationCode.get(code, conn=slapd_connection)
    assert authcode is not None

    res = testclient.post(
        "/oauth/token",
        params=dict(
            grant_type="authorization_code",
            code=code,
            scope="profile",
            redirect_uri=client.oauthRedirectURIs[0],
        ),
        headers={"Authorization": f"Basic {client_credentials(client)}"},
    )
    assert 200 == res.status_code
    access_token = res.json["access_token"]

    token = Token.get(access_token, conn=slapd_connection)
    assert token.oauthClient == client.dn
    assert token.oauthSubject == logged_user.dn

    res = testclient.get("/api/me", headers={"Authorization": f"Bearer {access_token}"})
    assert 200 == res.status_code
    assert {"foo": "bar"} == res.json


def test_logout_login(testclient, slapd_connection, logged_user, client):
    res = testclient.get(
        "/oauth/authorize",
        params=dict(
            response_type="code",
            client_id=client.oauthClientID,
            scope="profile",
            nonce="somenonce",
        ),
    )
    assert 200 == res.status_code

    res = res.forms["logout"].submit()
    assert 302 == res.status_code
    res = res.follow()
    assert 200 == res.status_code

    res.form["login"] = logged_user.name
    res.form["password"] = "wrong password"
    res = res.form.submit()
    assert 200 == res.status_code
    assert b"Login failed, please check your information" in res.body

    res.form["login"] = logged_user.name
    res.form["password"] = "correct horse battery staple"
    res = res.form.submit()
    assert 302 == res.status_code
    res = res.follow()
    assert 302 == res.status_code

    assert res.location.startswith(client.oauthRedirectURIs[0])
    params = parse_qs(urlsplit(res.location).query)
    code = params["code"][0]
    authcode = AuthorizationCode.get(code, conn=slapd_connection)
    assert authcode is not None

    res = testclient.post(
        "/oauth/token",
        params=dict(
            grant_type="authorization_code",
            code=code,
            scope="profile",
            redirect_uri=client.oauthRedirectURIs[0],
        ),
        headers={"Authorization": f"Basic {client_credentials(client)}"},
    )
    assert 200 == res.status_code
    access_token = res.json["access_token"]

    token = Token.get(access_token, conn=slapd_connection)
    assert token.oauthClient == client.dn
    assert token.oauthSubject == logged_user.dn

    res = testclient.get("/api/me", headers={"Authorization": f"Bearer {access_token}"})
    assert 200 == res.status_code
    assert {"foo": "bar"} == res.json


def test_refresh_token(testclient, slapd_connection, logged_user, client):
    res = testclient.get(
        "/oauth/authorize",
        params=dict(
            response_type="code",
            client_id=client.oauthClientID,
            scope="profile",
            nonce="somenonce",
        ),
    )
    assert 200 == res.status_code

    res = res.forms["accept"].submit()
    assert 302 == res.status_code

    assert res.location.startswith(client.oauthRedirectURIs[0])
    params = parse_qs(urlsplit(res.location).query)
    code = params["code"][0]
    authcode = AuthorizationCode.get(code, conn=slapd_connection)
    assert authcode is not None

    res = testclient.post(
        "/oauth/token",
        params=dict(
            grant_type="authorization_code",
            code=code,
            scope="profile",
            redirect_uri=client.oauthRedirectURIs[0],
        ),
        headers={"Authorization": f"Basic {client_credentials(client)}"},
    )
    assert 200 == res.status_code
    access_token = res.json["access_token"]
    old_token = Token.get(access_token, conn=slapd_connection)
    assert old_token is not None
    assert not old_token.revoked

    res = testclient.post(
        "/oauth/token",
        params=dict(
            grant_type="refresh_token",
            refresh_token=res.json["refresh_token"],
        ),
        headers={"Authorization": f"Basic {client_credentials(client)}"},
    )
    assert 200 == res.status_code
    access_token = res.json["access_token"]
    new_token = Token.get(access_token, conn=slapd_connection)
    assert new_token is not None
    old_token.reload(slapd_connection)
    assert old_token.revoked

    res = testclient.get("/api/me", headers={"Authorization": f"Bearer {access_token}"})
    assert 200 == res.status_code
    assert {"foo": "bar"} == res.json


def test_code_challenge(testclient, slapd_connection, logged_user, client):
    client.oauthTokenEndpointAuthMethod = "none"
    client.save(slapd_connection)

    code_verifier = gen_salt(48)
    code_challenge = create_s256_code_challenge(code_verifier)

    res = testclient.get(
        "/oauth/authorize",
        params=dict(
            code_challenge=code_challenge,
            code_challenge_method="S256",
            response_type="code",
            client_id=client.oauthClientID,
            scope="profile",
            nonce="somenonce",
        ),
    )
    assert 200 == res.status_code

    res = res.forms["accept"].submit()
    assert 302 == res.status_code

    assert res.location.startswith(client.oauthRedirectURIs[0])
    params = parse_qs(urlsplit(res.location).query)
    code = params["code"][0]
    authcode = AuthorizationCode.get(code, conn=slapd_connection)
    assert authcode is not None

    res = testclient.post(
        "/oauth/token",
        params=dict(
            grant_type="authorization_code",
            code=code,
            scope="profile",
            code_verifier=code_verifier,
            redirect_uri=client.oauthRedirectURIs[0],
            client_id=client.oauthClientID,
        ),
    )
    assert 200 == res.status_code
    access_token = res.json["access_token"]

    token = Token.get(access_token, conn=slapd_connection)
    assert token.oauthClient == client.dn
    assert token.oauthSubject == logged_user.dn

    res = testclient.get("/api/me", headers={"Authorization": f"Bearer {access_token}"})
    assert 200 == res.status_code
    assert {"foo": "bar"} == res.json

    client.oauthTokenEndpointAuthMethod = "client_secret_basic"
    client.save(slapd_connection)


def test_authorization_code_flow_when_consent_already_given(
    testclient, slapd_connection, logged_user, client
):
    assert not Consent.filter(conn=slapd_connection)

    res = testclient.get(
        "/oauth/authorize",
        params=dict(
            response_type="code",
            client_id=client.oauthClientID,
            scope="profile",
            nonce="somenonce",
        ),
    )
    assert 200 == res.status_code

    res = res.forms["accept"].submit()
    assert 302 == res.status_code

    assert res.location.startswith(client.oauthRedirectURIs[0])
    params = parse_qs(urlsplit(res.location).query)
    code = params["code"][0]
    authcode = AuthorizationCode.get(code, conn=slapd_connection)
    assert authcode is not None

    consents = Consent.filter(
        oauthClient=client.dn, oauthSubject=logged_user.dn, conn=slapd_connection
    )
    assert "profile" in consents[0].oauthScope

    res = testclient.post(
        "/oauth/token",
        params=dict(
            grant_type="authorization_code",
            code=code,
            scope="profile",
            redirect_uri=client.oauthRedirectURIs[0],
        ),
        headers={"Authorization": f"Basic {client_credentials(client)}"},
    )
    assert 200 == res.status_code
    assert "access_token" in res.json

    res = testclient.get(
        "/oauth/authorize",
        params=dict(
            response_type="code",
            client_id=client.oauthClientID,
            scope="profile",
            nonce="somenonce",
        ),
    )
    assert 302 == res.status_code
    assert res.location.startswith(client.oauthRedirectURIs[0])
    params = parse_qs(urlsplit(res.location).query)
    assert "code" in params


def test_prompt_none(testclient, slapd_connection, logged_user, client):
    Consent(
        oauthClient=client.dn,
        oauthSubject=logged_user.dn,
        oauthScope=["openid", "profile"],
    ).save(conn=slapd_connection)

    res = testclient.get(
        "/oauth/authorize",
        params=dict(
            response_type="code",
            client_id=client.oauthClientID,
            scope="profile",
            nonce="somenonce",
            prompt="none",
        ),
    )
    assert 302 == res.status_code
    assert res.location.startswith(client.oauthRedirectURIs[0])
    params = parse_qs(urlsplit(res.location).query)
    assert "code" in params


def test_prompt_not_logged(testclient, slapd_connection, user, client):
    Consent(
        oauthClient=client.dn,
        oauthSubject=user.dn,
        oauthScope=["openid", "profile"],
    ).save(conn=slapd_connection)

    res = testclient.get(
        "/oauth/authorize",
        params=dict(
            response_type="code",
            client_id=client.oauthClientID,
            scope="profile",
            nonce="somenonce",
            prompt="none",
        ),
    )
    assert 200 == res.status_code
    assert "login_required" == res.json.get("error")


def test_prompt_no_consent(testclient, slapd_connection, logged_user, client):
    res = testclient.get(
        "/oauth/authorize",
        params=dict(
            response_type="code",
            client_id=client.oauthClientID,
            scope="profile",
            nonce="somenonce",
            prompt="none",
        ),
    )
    assert 200 == res.status_code
    assert "consent_required" == res.json.get("error")
