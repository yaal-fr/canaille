import mock
from canaille.account import profile_hash
from canaille.models import User


def test_login_and_out(testclient, slapd_connection, user):
    with testclient.session_transaction() as session:
        assert not session.get("user_dn")

    res = testclient.get("/login", status=200)

    res.form["login"] = "John Doe"
    res.form["password"] = "correct horse battery staple"
    res = res.form.submit()
    res = res.follow(status=302)
    res = res.follow(status=200)

    with testclient.session_transaction() as session:
        assert [user.dn] == session.get("user_dn")

    res = testclient.get("/logout")
    res = res.follow(status=302)
    res = res.follow(status=200)

    with testclient.session_transaction() as session:
        assert not session.get("user_dn")


def test_login_wrong_password(testclient, slapd_connection, user):
    with testclient.session_transaction() as session:
        assert not session.get("user_dn")

    res = testclient.get("/login", status=200)

    res.form["login"] = "John Doe"
    res.form["password"] = "incorrect horse"
    res = res.form.submit(status=200)
    assert "Login failed, please check your information" in res.text


def test_login_no_password(testclient, slapd_connection, user):
    with testclient.session_transaction() as session:
        assert not session.get("user_dn")

    res = testclient.get("/login", status=200)

    res.form["login"] = "John Doe"
    res.form["password"] = ""
    res = res.form.submit(status=200)
    assert "Login failed, please check your information" in res.text


def test_login_with_alternate_attribute(testclient, slapd_connection, user):
    res = testclient.get("/login", status=200)

    res.form["login"] = "user"
    res.form["password"] = "correct horse battery staple"
    res = res.form.submit()
    res = res.follow(status=302)
    res = res.follow(status=200)

    with testclient.session_transaction() as session:
        assert [user.dn] == session.get("user_dn")


def test_user_without_password_first_login(testclient, slapd_connection):
    User.ocs_by_name(slapd_connection)
    u = User(
        objectClass=["inetOrgPerson"],
        cn="Temp User",
        sn="Temp",
        uid="temp",
        mail="john@doe.com",
    )
    u.save(slapd_connection)

    res = testclient.get("/login", status=200)
    res.form["login"] = "Temp User"
    res.form["password"] = "anything"
    res = res.form.submit(status=302).follow(status=200)

    assert "First login" in res
    u.delete(conn=slapd_connection)


@mock.patch("smtplib.SMTP")
def test_password_forgotten(SMTP, testclient, slapd_connection, user):
    res = testclient.get("/reset", status=200)

    res.form["login"] = "user"
    res = res.form.submit(status=200)
    assert "A password reset link has been sent at your email address." in res.text

    SMTP.assert_called_once_with(host="localhost", port=25)


@mock.patch("smtplib.SMTP")
def test_password_forgotten_invalid_form(SMTP, testclient, slapd_connection, user):
    res = testclient.get("/reset", status=200)

    res.form["login"] = ""
    res = res.form.submit(status=200)
    assert "Could not send the password reset link." in res.text

    SMTP.assert_not_called()


@mock.patch("smtplib.SMTP")
def test_password_forgotten_invalid(SMTP, testclient, slapd_connection, user):
    testclient.app.config["HIDE_INVALID_LOGINS"] = False
    res = testclient.get("/reset", status=200)

    res.form["login"] = "i-dont-really-exist"
    res = res.form.submit(status=200)
    assert "A password reset link has been sent at your email address." in res.text
    assert "The login 'i-dont-really-exist' does not exist" not in res.text

    testclient.app.config["HIDE_INVALID_LOGINS"] = True
    res = testclient.get("/reset", status=200)

    res.form["login"] = "i-dont-really-exist"
    res = res.form.submit(status=200)
    assert "A password reset link has been sent at your email address." not in res.text
    assert "The login 'i-dont-really-exist' does not exist" in res.text

    SMTP.assert_not_called()


def test_password_reset(testclient, slapd_connection, user):
    user.attr_type_by_name(conn=slapd_connection)
    user.reload(conn=slapd_connection)
    with testclient.app.app_context():
        hash = profile_hash("user", user.userPassword[0])

    res = testclient.get("/reset/user/" + hash, status=200)

    res.form["password"] = "foobarbaz"
    res.form["confirmation"] = "foobarbaz"
    res = res.form.submit(status=302)

    res = res.follow(status=200)

    with testclient.app.app_context():
        assert user.check_password("foobarbaz")
    assert "Your password has been updated successfuly" in res.text
    user.set_password("correct horse battery staple", conn=slapd_connection)

    res = testclient.get("/reset/user/" + hash)
    res = res.follow()
    res = res.follow()
    assert "The password reset link that brought you here was invalid." in res.text


def test_password_reset_bad_link(testclient, slapd_connection, user):
    user.attr_type_by_name(conn=slapd_connection)
    user.reload(conn=slapd_connection)

    res = testclient.get("/reset/user/foobarbaz")
    res = res.follow()
    res = res.follow()
    assert "The password reset link that brought you here was invalid." in res.text


def test_password_reset_bad_password(testclient, slapd_connection, user):
    user.attr_type_by_name(conn=slapd_connection)
    user.reload(conn=slapd_connection)
    with testclient.app.app_context():
        hash = profile_hash("user", user.userPassword[0])

    res = testclient.get("/reset/user/" + hash, status=200)

    res.form["password"] = "foobarbaz"
    res.form["confirmation"] = "typo"
    res = res.form.submit(status=200)

    with testclient.app.app_context():
        assert user.check_password("correct horse battery staple")


def test_user_deleted_in_session(testclient, slapd_connection):
    User.ocs_by_name(slapd_connection)
    u = User(
        objectClass=["inetOrgPerson"],
        cn="Jake Doe",
        sn="Jake",
        uid="jake",
        mail="jake@doe.com",
        userPassword="{SSHA}fw9DYeF/gHTHuVMepsQzVYAkffGcU8Fz",
    )
    u.save(slapd_connection)
    testclient.get("/profile/jake", status=403)

    with testclient.session_transaction() as session:
        session["user_dn"] = [u.dn]

    testclient.get("/profile/jake", status=200)
    u.delete(conn=slapd_connection)

    testclient.get("/profile/jake", status=403)
    with testclient.session_transaction() as session:
        assert not session.get("user_dn")


def test_impersonate(testclient, slapd_connection, logged_admin, user):
    res = testclient.get("/", status=302).follow(status=200)
    assert "admin" == res.form["uid"].value

    res = (
        testclient.get("/impersonate/user", status=302)
        .follow(status=302)
        .follow(status=200)
    )
    assert "user" == res.form["uid"].value

    testclient.get("/logout", status=302).follow(status=302).follow(status=200)

    res = testclient.get("/", status=302).follow(status=200)
    assert "admin" == res.form["uid"].value


def test_wrong_login(testclient, slapd_connection, user):
    testclient.app.config["HIDE_INVALID_LOGINS"] = False

    res = testclient.get("/login", status=200)
    res.form["login"] = "invalid"
    res.form["password"] = "incorrect horse"
    res = res.form.submit(status=200)
    assert "The login 'invalid' does not exist" not in res.text

    testclient.app.config["HIDE_INVALID_LOGINS"] = True

    res = testclient.get("/login", status=200)
    res.form["login"] = "invalid"
    res.form["password"] = "incorrect horse"
    res = res.form.submit(status=200)
    assert "The login 'invalid' does not exist" in res.text
