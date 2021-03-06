from canaille.models import User


def test_signin_and_out(testclient, slapd_connection, user):
    with testclient.session_transaction() as session:
        assert not session.get("user_dn")

    res = testclient.get("/login", status=200)

    res.form["login"] = "John Doe"
    res = res.form.submit(status=302)
    res = res.follow(status=200)

    with testclient.session_transaction() as session:
        assert "John Doe" == session.get("attempt_login")

    res.form["password"] = "correct horse battery staple"
    res = res.form.submit()
    res = res.follow(status=302)
    res = res.follow(status=200)

    with testclient.session_transaction() as session:
        assert [user.dn] == session.get("user_dn")
        assert "attempt_login" not in session

    res = testclient.get("/logout")
    res = res.follow(status=302)
    res = res.follow(status=200)

    with testclient.session_transaction() as session:
        assert not session.get("user_dn")


def test_signin_wrong_password(testclient, slapd_connection, user):
    with testclient.session_transaction() as session:
        assert not session.get("user_dn")

    res = testclient.get("/login", status=200)

    res.form["login"] = "John Doe"
    res = res.form.submit(status=302)
    res = res.follow(status=200)
    res.form["password"] = "incorrect horse"
    res = res.form.submit(status=200)
    assert "Login failed, please check your information" in res.text


def test_signin_with_alternate_attribute(testclient, slapd_connection, user):
    res = testclient.get("/login", status=200)

    res.form["login"] = "user"
    res = res.form.submit(status=302)
    res = res.follow(status=200)

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
    res = res.form.submit(status=302).follow(status=200)

    assert "First login" in res
    u.delete(conn=slapd_connection)


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
    res = res.form.submit(status=302)
    res = res.follow(status=200)

    res.form["password"] = "incorrect horse"
    res = res.form.submit(status=200)
    assert "The login 'invalid' does not exist" not in res.text

    testclient.app.config["HIDE_INVALID_LOGINS"] = True

    res = testclient.get("/login", status=200)
    res.form["login"] = "invalid"
    res = res.form.submit(status=200)
    assert "The login 'invalid' does not exist" in res.text


def test_admin_self_deletion(testclient, slapd_connection):
    User.ocs_by_name(slapd_connection)
    admin = User(
        objectClass=["inetOrgPerson"],
        cn="Temp admin",
        sn="admin",
        uid="temp",
        mail="temp@temp.com",
        userPassword="{SSHA}Vmgh2jkD0idX3eZHf8RzGos31oerjGiU",
    )
    admin.save(slapd_connection)
    with testclient.session_transaction() as sess:
        sess["user_dn"] = [admin.dn]

    res = testclient.get("/profile/temp")
    res = (
        res.form.submit(name="action", value="delete", status=302)
        .follow(status=302)
        .follow(status=200)
    )

    testclient.app.config["SELF_DELETION"] = True

    testclient.app.config["SELF_DELETION"] = False

    with testclient.app.app_context():
        assert User.get("temp", conn=slapd_connection) is None

    with testclient.session_transaction() as sess:
        assert not sess.get("user_dn")


def test_user_self_deletion(testclient, slapd_connection):
    User.ocs_by_name(slapd_connection)
    user = User(
        objectClass=["inetOrgPerson"],
        cn="Temp user",
        sn="user",
        uid="temp",
        mail="temp@temp.com",
        userPassword="{SSHA}Vmgh2jkD0idX3eZHf8RzGos31oerjGiU",
    )
    user.save(slapd_connection)
    with testclient.session_transaction() as sess:
        sess["user_dn"] = [user.dn]

    testclient.app.config["SELF_DELETION"] = False
    res = testclient.get("/profile/temp")
    assert "Delete my account" not in res

    testclient.app.config["SELF_DELETION"] = True
    res = testclient.get("/profile/temp")
    assert "Delete my account" in res
    res = (
        res.form.submit(name="action", value="delete", status=302)
        .follow(status=302)
        .follow(status=200)
    )

    with testclient.app.app_context():
        assert User.get("temp", conn=slapd_connection) is None

    with testclient.session_transaction() as sess:
        assert not sess.get("user_dn")

    testclient.app.config["SELF_DELETION"] = False
