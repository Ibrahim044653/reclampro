"""E2E — Authentification et MFA."""
import re
import pyotp


def test_login_admin_redirige_vers_dashboard(page, live_server):
    page.goto(f"{live_server}/login.html")
    page.fill('input[name="username"]', "admin")
    page.fill('input[name="password"]', "admin123")
    page.click('button[type="submit"]')
    page.wait_for_url(f"{live_server}/")
    # La sidebar contient bien le nom de l'utilisateur
    assert page.get_by_text("Konan Diabaté").is_visible()
    # Et au moins un KPI est rendu (donc le dashboard a chargé via l'API)
    assert page.locator(".kpi-value, .mini-kpi .v").first.is_visible()


def test_login_mauvais_mdp_affiche_erreur(page, live_server):
    page.goto(f"{live_server}/login.html")
    page.fill('input[name="username"]', "admin")
    page.fill('input[name="password"]', "wrong-password")
    page.click('button[type="submit"]')
    erreur = page.locator(".alert-error")
    erreur.wait_for(state="visible")
    assert "Identifiants invalides" in erreur.text_content()
    # On reste sur la page login
    assert page.url.endswith("/login.html")


def test_logout_redirige_vers_login(admin_page, live_server):
    admin_page.click("#btn_logout")
    admin_page.wait_for_url(f"{live_server}/login.html")
    assert "username" in admin_page.content()


def test_routes_protegees_redirigent_vers_login_si_non_connecte(page, live_server):
    """Accéder à /reclamations.html sans token redirige vers le login."""
    # On s'assure que localStorage est vide
    page.goto(f"{live_server}/login.html")
    page.evaluate("() => localStorage.clear()")
    page.goto(f"{live_server}/reclamations.html")
    page.wait_for_url(f"{live_server}/login.html")


def test_demo_credentials_affiches_sur_login(page, live_server):
    page.goto(f"{live_server}/login.html")
    contenu = page.locator(".demo-credentials").text_content()
    assert "admin / admin123" in contenu
    assert "agent / agent123" in contenu


def test_lien_portail_public_visible_sur_login(page, live_server):
    page.goto(f"{live_server}/login.html")
    lien = page.get_by_role("link", name=re.compile("portail|réclamation|client", re.I))
    assert lien.first.is_visible()
