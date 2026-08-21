"""E2E — Portail public client (sans login)."""
import re


def test_portail_soumission_affiche_code_et_lien_suivi(page, live_server):
    page.goto(f"{live_server}/portail.html")
    page.fill('input[name="nom"]', "Tester")
    page.fill('input[name="prenom"]', "Public")
    page.fill('input[name="email"]', "tester.public@example.ci")
    page.fill('input[name="telephone"]', "+225 07 00 00 00 00")
    page.select_option('select[name="categorie"]', "SERVICE")
    page.select_option('select[name="priorite"]', "STANDARD")
    page.fill(
        'textarea[name="description"]',
        "Test E2E de soumission depuis le portail public — service injoignable.",
    )
    page.click('button[type="submit"]')

    # On attend l'écran de confirmation
    page.wait_for_selector("#resultat", state="visible")
    code_text = page.locator("#r_code").text_content()
    assert re.match(r"RECB-\d{6}-\d{5}", code_text), f"Code invalide : {code_text}"

    lien = page.locator("#r_lien").get_attribute("href")
    assert "/portail-suivi.html?token=" in lien
    assert len(lien.split("token=")[1]) > 30


def test_portail_suivi_via_lien_complet(page, live_server):
    # 1. Soumission préalable pour obtenir un token
    page.goto(f"{live_server}/portail.html")
    page.fill('input[name="nom"]', "Suivi")
    page.fill('input[name="prenom"]', "Token")
    page.fill('input[name="email"]', "suivi.token@example.ci")
    page.select_option('select[name="categorie"]', "FINANCIERE")
    page.select_option('select[name="priorite"]', "URGENT")
    page.fill(
        'textarea[name="description"]',
        "Suivi public via token — vérification UX.",
    )
    page.click('button[type="submit"]')
    page.wait_for_selector("#resultat", state="visible")
    lien_suivi = page.locator("#r_lien").get_attribute("href")

    # 2. On consulte le lien
    page.goto(lien_suivi)
    page.wait_for_selector(".progress-step.active", state="visible")
    # Le code RECB-... est affiché quelque part dans le DOM
    assert page.get_by_text(re.compile(r"RECB-\d{6}-\d{5}")).first.is_visible()
    # Barre de progression : statut "Reçu" actif
    actif = page.locator(".progress-step.active").text_content()
    assert "Reçu" in actif


def test_portail_suivi_token_invalide_affiche_erreur(page, live_server):
    page.goto(f"{live_server}/portail-suivi.html?token=" + "X" * 40)
    page.wait_for_selector(".alert-error", state="visible")
    err = page.locator(".alert-error").text_content()
    assert "introuvable" in err.lower() or "invalide" in err.lower() or "expir" in err.lower()


def test_portail_description_trop_courte_bloque_soumission(page, live_server):
    page.goto(f"{live_server}/portail.html")
    page.fill('input[name="nom"]', "X")
    page.fill('input[name="prenom"]', "Y")
    page.fill('input[name="email"]', "x@y.ci")
    page.select_option('select[name="categorie"]', "SERVICE")
    page.fill('textarea[name="description"]', "court")  # < 10 chars
    page.click('button[type="submit"]')
    # HTML5 validation bloque l'envoi — on reste sur la page formulaire
    assert page.locator("#formulaire").is_visible()
    assert not page.locator("#resultat").is_visible()
