"""E2E — Création de dossier par agent + suggestion IA + détail + commentaire."""
import re


def test_navigation_dashboard_vers_liste(admin_page, live_server):
    admin_page.click('a:has-text("Réclamations")')
    admin_page.wait_for_url(f"{live_server}/reclamations.html")
    admin_page.wait_for_selector("table.tbl, .empty", state="visible")


def test_creation_nouvelle_reclamation_par_agent(agent_page, live_server):
    agent_page.click('a:has-text("Nouveau dossier")')
    agent_page.wait_for_url(f"{live_server}/nouvelle.html")
    agent_page.wait_for_selector('form#frm')

    agent_page.select_option('select[name="canal"]', "EMAIL")
    agent_page.select_option('select[name="categorie"]', "SERVICE")
    agent_page.select_option('select[name="priorite"]', "STANDARD")
    agent_page.fill('input[name="nom"]', "Koffi")
    agent_page.fill('input[name="prenom"]', "Aya")
    agent_page.fill('input[name="email"]', "aya.koffi@example.ci")
    agent_page.fill(
        'textarea[name="description"]',
        "Test E2E création — long délai d'attente en agence ce matin.",
    )
    agent_page.click('button[type="submit"]')

    # Redirection vers /detail.html?code=...
    agent_page.wait_for_url(re.compile(r"/detail\.html\?code=RECB-"))
    # Attendre que la page détail soit chargée (timeline rendue après fetch API)
    agent_page.wait_for_selector(".timeline-item", timeout=10000)
    # Le code RECB-... apparaît
    assert agent_page.get_by_text(re.compile(r"RECB-\d{6}-\d{5}")).first.is_visible()
    # Le client aussi
    assert agent_page.get_by_text("Aya Koffi").is_visible()


def test_suggestion_ia_dans_formulaire(agent_page, live_server):
    agent_page.goto(f"{live_server}/nouvelle.html")
    agent_page.wait_for_selector('#btn_ia')
    agent_page.fill(
        'textarea#description',
        "Mon compte a été victime d'une fraude bancaire — usurpation d'identité et débit non autorisé de 500000 FCFA.",
    )
    agent_page.click('#btn_ia')
    # La zone de suggestion s'affiche
    agent_page.wait_for_selector('#suggestion_ia .alert-success', state='visible')
    suggestion = agent_page.locator('#suggestion_ia').text_content()
    assert "FRAUDE" in suggestion or "FINANCIERE" in suggestion
    assert "CRITIQUE" in suggestion or "URGENT" in suggestion
    # Le bouton "Appliquer" est présent
    assert agent_page.locator('#btn_appliquer_ia').is_visible()


def test_ajouter_commentaire_sur_dossier(admin_page, live_server):
    # Aller sur la liste puis ouvrir le premier dossier
    admin_page.goto(f"{live_server}/reclamations.html")
    admin_page.wait_for_selector("table.tbl tbody tr")
    admin_page.locator("table.tbl tbody tr").first.click()
    admin_page.wait_for_url(re.compile(r"/detail\.html\?code=RECB-"))

    # Attendre que la timeline soit rendue
    admin_page.wait_for_selector(".timeline-item", timeout=10000)
    avant = admin_page.locator(".timeline-item").count()

    # Ajouter un commentaire (texte simple sans accent pour éviter les soucis d'encodage console)
    commentaire = "Commentaire E2E ajoute pour test"
    admin_page.fill('#cmt', commentaire)
    admin_page.click('#btn_cmt')
    admin_page.wait_for_selector('.alert-success', state='visible')
    # Rechargement automatique → on attend que les interactions augmentent
    admin_page.wait_for_function(
        f"document.querySelectorAll('.timeline-item').length > {avant}",
        timeout=10000,
    )
    apres = admin_page.locator(".timeline-item").count()
    assert apres > avant
    # Le commentaire apparaît dans la timeline
    assert admin_page.get_by_text(commentaire).is_visible()


def test_changer_statut_dossier(admin_page, live_server):
    """Trouve un dossier NOUVEAU et le passe à QUALIF."""
    # Filtre pour ne voir que les dossiers NOUVEAU
    admin_page.goto(f"{live_server}/reclamations.html?statut=NOUVEAU")
    admin_page.wait_for_selector("table.tbl tbody tr, .empty")
    if admin_page.locator(".empty").is_visible():
        # Pas de dossier en NOUVEAU dans le seed — on en crée un
        admin_page.goto(f"{live_server}/nouvelle.html")
        admin_page.select_option('select[name="canal"]', "EMAIL")
        admin_page.select_option('select[name="categorie"]', "SERVICE")
        admin_page.fill('input[name="nom"]', "Test")
        admin_page.fill('input[name="prenom"]', "Statut")
        admin_page.fill('input[name="email"]', "test.statut@example.ci")
        admin_page.fill('textarea[name="description"]', "Dossier pour test E2E changement statut.")
        admin_page.click('button[type="submit"]')
        admin_page.wait_for_url(re.compile(r"/detail\.html\?code=RECB-"))
    else:
        admin_page.locator("table.tbl tbody tr").first.click()
        admin_page.wait_for_url(re.compile(r"/detail\.html\?code=RECB-"))

    # Maintenant on est sur le détail avec un dossier en NOUVEAU (ou autre, on s'adapte)
    admin_page.wait_for_selector('#nouveau_statut, .empty', timeout=5000)
    if admin_page.locator('#nouveau_statut').count() > 0:
        admin_page.select_option('#nouveau_statut', "QUALIF")
        admin_page.click('#btn_statut')
        admin_page.wait_for_selector('.alert-success', state='visible')
        # Après rechargement, le pill statut doit être QUALIF
        admin_page.wait_for_function(
            "Array.from(document.querySelectorAll('.pill')).some(p => p.textContent.trim() === 'QUALIF')",
            timeout=5000,
        )
