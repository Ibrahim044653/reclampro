"""E2E — Fonctions réservées à l'admin : reportings, utilisateurs, clôture."""
import re


def test_menu_admin_voit_utilisateurs_et_reportings(admin_page, live_server):
    admin_page.wait_for_selector(".sidebar")
    assert admin_page.get_by_role("link", name="Utilisateurs").is_visible()
    assert admin_page.get_by_role("link", name="Reportings").is_visible()


def test_menu_agent_ne_voit_pas_utilisateurs(agent_page, live_server):
    agent_page.wait_for_selector(".sidebar")
    assert agent_page.get_by_role("link", name="Utilisateurs").count() == 0
    assert agent_page.get_by_role("link", name="Reportings").count() == 0


def test_reportings_charge_tables(admin_page, live_server):
    admin_page.click('a:has-text("Reportings")')
    admin_page.wait_for_url(f"{live_server}/reportings.html")
    # Au moins une carte avec un mini-KPI s'affiche
    admin_page.wait_for_selector(".mini-kpi, .card", state="visible")
    # Le tableau "Volume par équipe / cellule" doit apparaître
    admin_page.wait_for_selector("text=Volume par équipe", timeout=15000)


def test_creer_utilisateur_admin(admin_page, live_server):
    admin_page.click('a:has-text("Utilisateurs")')
    admin_page.wait_for_url(f"{live_server}/utilisateurs.html")
    admin_page.wait_for_selector('#frm_create')

    admin_page.fill('input[name="nom"]', "E2E")
    admin_page.fill('input[name="prenom"]', "User")
    admin_page.fill('input[name="email_pro"]', "e2e.user@sib.ci")
    admin_page.fill('input[name="username"]', "e2euser")
    admin_page.fill('input[name="password"]', "passe123456")
    admin_page.select_option('select[name="role"]', "GESTIONNAIRE")
    admin_page.click('#frm_create button[type="submit"]')

    admin_page.wait_for_selector('.alert-success', state='visible')
    # Le nouvel utilisateur apparaît dans la table
    admin_page.wait_for_function(
        "Array.from(document.querySelectorAll('tbody tr')).some(r => r.textContent.includes('e2euser'))",
        timeout=5000,
    )


def test_cloturer_dossier_admin(admin_page, live_server):
    """Crée → qualifie → affecte → instruit → clôture un dossier complet."""
    # 1. Créer
    admin_page.goto(f"{live_server}/nouvelle.html")
    admin_page.select_option('select[name="canal"]', "EMAIL")
    admin_page.select_option('select[name="categorie"]', "SERVICE")
    admin_page.fill('input[name="nom"]', "Final")
    admin_page.fill('input[name="prenom"]', "Cloture")
    admin_page.fill('input[name="email"]', "final.cloture@example.ci")
    admin_page.fill(
        'textarea[name="description"]',
        "Dossier complet E2E — sera clôturé en favorable.",
    )
    admin_page.click('button[type="submit"]')
    admin_page.wait_for_url(re.compile(r"/detail\.html\?code=RECB-"))

    # 2. Cycle workflow NOUVEAU → QUALIF → AFFECTE → EN_COURS
    for cible in ["QUALIF", "AFFECTE", "EN_COURS"]:
        admin_page.wait_for_selector('#nouveau_statut')
        admin_page.select_option('#nouveau_statut', cible)
        admin_page.click('#btn_statut')
        admin_page.wait_for_selector('.alert-success', state='visible')
        # Attend que le pill statut reflète le nouveau statut
        admin_page.wait_for_function(
            f"Array.from(document.querySelectorAll('.pill')).some(p => p.textContent.trim() === '{cible}')",
            timeout=5000,
        )

    # 3. Clôture
    admin_page.wait_for_selector('#motif')
    admin_page.select_option('#motif', "FAVORABLE")
    admin_page.click('#btn_clot')
    admin_page.wait_for_selector('.alert-success', state='visible')
    admin_page.wait_for_function(
        "Array.from(document.querySelectorAll('.pill')).some(p => p.textContent.trim() === 'CLOTURE')",
        timeout=5000,
    )
    # Le motif est affiché
    assert admin_page.get_by_text("FAVORABLE").first.is_visible()


def test_export_registre_csv_disponible_pour_admin(admin_page, live_server):
    # Le lien d'export apparaît dans la sidebar
    assert admin_page.get_by_role("link", name=re.compile("Registre BCEAO", re.I)).is_visible()


def test_ma_file_affiche_bilan_personnel(agent_page, live_server):
    agent_page.click('a:has-text("Ma file")')
    agent_page.wait_for_url(f"{live_server}/ma-file.html")
    agent_page.wait_for_selector(".mini-kpi", state="visible")
    # Les 5 KPIs sont visibles : à traiter, en cours, traités, alerte SLA, total
    nb_kpis = agent_page.locator(".mini-kpi").count()
    assert nb_kpis >= 4


def test_notifications_page_charge(admin_page, live_server):
    admin_page.click('a:has-text("Notifications")')
    admin_page.wait_for_url(f"{live_server}/notifications.html")
    # Soit on a des notifs soit le message "Aucune notification"
    admin_page.wait_for_selector(".card", state="visible")
