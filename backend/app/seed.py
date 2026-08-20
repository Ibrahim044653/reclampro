"""Données de démo — lance avec : python -m app.seed"""
from datetime import datetime, timedelta
import random

from .database import Base, engine, SessionLocal
from . import models
from .services import id_generator, sla, audit, auth

ENTITES_DEMO = [
    ("SIB", "Banque SIB-CI", "BANQUE"),
    ("NSIA", "Assurance NSIA-CI", "ASSURANCE"),
]

# (code_equipe, libelle, description, code_entite)
EQUIPES_DEMO = [
    ("FRONT_OFFICE", "Front-office",   "Accueil et premier traitement", "SIB"),
    ("BACK_OFFICE",  "Back-office",    "Instruction des dossiers",      "SIB"),
    ("FRAUDE",       "Cellule Fraude", "Investigations de fraude",      "SIB"),
    ("CONFORMITE",   "Conformité",     "Reporting BCEAO/CIMA",          "SIB"),
    ("NSIA_GESTION", "Gestion sinistres", "Traitement sinistres assurance", "NSIA"),
]

TEMPLATES_DEMO = [
    ("ACCUSE_GENERIQUE", "Accusé de réception générique", None,
     "Accusé de réception de votre réclamation {reclamation.code}",
     "Bonjour {client.prenom},\n\nNous accusons réception de votre réclamation "
     "{reclamation.code} concernant {reclamation.categorie}.\n"
     "Elle sera traitée avant le {reclamation.date_echeance_sla}.\n\nCordialement,"),
    ("REPONSE_FRAUDE", "Réponse — Fraude", "FRAUDE",
     "Suivi de votre dossier de fraude {reclamation.code}",
     "Bonjour {client.prenom} {client.nom},\n\nVotre signalement de fraude "
     "(dossier {reclamation.code}) est en cours d'investigation par notre cellule "
     "dédiée. Pour des raisons de sécurité, nous vous demanderons peut-être des "
     "informations complémentaires.\n\nCordialement,"),
    ("REPONSE_FAVORABLE", "Réponse favorable", None,
     "Issue favorable de votre réclamation {reclamation.code}",
     "Bonjour {client.prenom},\n\nNous avons étudié votre réclamation "
     "{reclamation.code} et nous y donnons une suite favorable.\n"
     "Le montant de {reclamation.montant_enjeu} sera régularisé sous 48h ouvrées.\n\n"
     "Cordialement,"),
]

# (nom, prénom, email_pro, role, code_equipe, username, mdp)
AGENTS_DEMO = [
    ("Diabaté", "Konan", "admin@sib.ci", "ADMIN", "CONFORMITE", "admin", "admin123"),
    ("Koné", "Aïcha", "akone@sib.ci", "AGENT", "FRONT_OFFICE", "agent", "agent123"),
    ("Ouédraogo", "Mariam", "mouedraogo@sib.ci", "AGENT", "FRONT_OFFICE", None, None),
    ("Bamba", "Souleymane", "sbamba@sib.ci", "GESTIONNAIRE", "BACK_OFFICE", None, None),
    ("Touré", "Djeneba", "dtoure@sib.ci", "GESTIONNAIRE", "BACK_OFFICE", None, None),
    ("Diallo", "Fatoumata", "fdiallo@sib.ci", "AGENT", "FRAUDE", None, None),
]

CLIENTS_DEMO = [
    ("Bamba", "Adjoua", "adjoua.bamba@example.ci", "+225 07 01 02 03 04"),
    ("Coulibaly", "Moussa", "moussa.c@example.ci", "+225 07 02 03 04 05"),
    ("Konaté", "Awa", "awa.konate@example.ci", "+225 07 03 04 05 06"),
    ("Diallo", "Ibrahim", "i.diallo@example.ci", "+225 07 04 05 06 07"),
    ("Traoré", "Fatou", "fatou.traore@example.ci", "+225 07 05 06 07 08"),
    ("Yao", "Akissi", "akissi.yao@example.ci", "+225 07 06 07 08 09"),
    ("N'Guessan", "Kouamé", "k.nguessan@example.ci", "+225 07 07 08 09 10"),
]

GABARITS_RECLAMATIONS = [
    ("FINANCIERE", "Débit non autorisé", "CRITIQUE", "EMAIL",
     "Un débit de 250 000 FCFA a été constaté sur mon compte sans autorisation.", 250_000),
    ("FINANCIERE", "Frais contestés", "URGENT", "AGENCE",
     "Des frais de tenue de compte injustifiés ont été prélevés ce mois-ci.", 15_000),
    ("FINANCIERE", "Virement erroné", "URGENT", "EMAIL",
     "Le virement vers mon fournisseur a été crédité sur un autre compte.", 750_000),
    ("SERVICE", "Comportement agent", "STANDARD", "WEB",
     "L'agent en agence a tenu des propos discourtois lors de ma visite.", 0),
    ("FRAUDE", "Usurpation identité", "CRITIQUE", "TELEPHONE",
     "Quelqu'un a ouvert un compte à mon nom sans mon consentement.", 0),
    ("SERVICE", "Délai excessif", "STANDARD", "EMAIL",
     "Cela fait 3 semaines que j'attends la réédition de mon RIB.", 0),
    ("CONTRACTUELLE", "Non-respect des conditions", "STANDARD", "AGENCE",
     "Le taux d'intérêt appliqué ne correspond pas à mon contrat.", 50_000),
]


def reset_et_seed():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        entites_par_code = {}
        for code, lib, type_ in ENTITES_DEMO:
            e = models.Entite(code=code, libelle=lib, type=type_)
            db.add(e)
            entites_par_code[code] = e
        db.flush()

        equipes_par_code = {}
        for code, lib, desc, code_ent in EQUIPES_DEMO:
            eq = models.Equipe(
                code=code, libelle=lib, description=desc,
                id_entite=entites_par_code[code_ent].id,
            )
            db.add(eq)
            equipes_par_code[code] = eq
        db.flush()

        for tpl_code, tpl_lib, tpl_cat, tpl_sujet, tpl_corps in TEMPLATES_DEMO:
            db.add(models.ModeleReponse(
                code=tpl_code, libelle=tpl_lib, categorie_cible=tpl_cat,
                sujet=tpl_sujet, corps=tpl_corps,
            ))
        db.flush()

        agents = []
        for nom, prenom, email, role, code_eq, username, mdp in AGENTS_DEMO:
            eq = equipes_par_code[code_eq]
            a = models.Agent(
                nom=nom, prenom=prenom, email_pro=email,
                role=role, service=eq.libelle,
                username=username,
                password_hash=auth.hasher_mot_de_passe(mdp) if mdp else None,
                id_equipe=eq.id,
                id_entite=eq.id_entite,
            )
            db.add(a)
            agents.append(a)
        db.flush()

        clients = []
        for nom, prenom, email, tel in CLIENTS_DEMO:
            c = models.Client(nom=nom, prenom=prenom, email=email, telephone=tel)
            db.add(c)
            clients.append(c)
        db.flush()

        random.seed(42)
        maintenant = datetime.utcnow()

        for i in range(25):
            gabarit = random.choice(GABARITS_RECLAMATIONS)
            categorie, sous_cat, priorite, canal, desc, montant = gabarit
            client = random.choice(clients)
            agent_c = random.choice(agents[1:5])

            jours_en_arriere = random.randint(0, 30)
            date_reception = maintenant - timedelta(
                days=jours_en_arriere,
                hours=random.randint(0, 23),
            )

            r = models.Reclamation(
                code=id_generator.generer_code(db, date_reception),
                canal=canal,
                statut="NOUVEAU",
                categorie=categorie,
                sous_categorie=sous_cat,
                priorite=priorite,
                description=desc,
                montant_enjeu=montant,
                id_client=client.id,
                id_agent_creation=agent_c.id,
                id_entite=agent_c.id_entite,
                date_reception=date_reception,
                date_echeance_sla=sla.calculer_echeance(date_reception, priorite),
            )
            db.add(r)
            db.flush()

            audit.enregistrer(
                db, r.id, "CREATION", f"Dossier créé via {canal}.",
                auteur=str(agent_c.id),
            )
            audit.enregistrer(db, r.id, "ACR", "Accusé de réception envoyé.", auteur="système")

            evolution = random.random()
            if evolution > 0.3:
                r.statut = "QUALIF"
                audit.enregistrer(db, r.id, "CHANGEMENT_STATUT", "Qualifié.",
                                  auteur=str(agent_c.id), valeur_avant="NOUVEAU", valeur_apres="QUALIF")
            if evolution > 0.45:
                r.statut = "AFFECTE"
                # affectation à un agent du back-office par défaut, fraude pour les FRAUDE
                pool = agents[5:6] if categorie == "FRAUDE" else agents[3:5]
                agent_aff = random.choice(pool)
                r.id_agent_affecte = agent_aff.id
                r.id_equipe_affectee = agent_aff.id_equipe
                audit.enregistrer(db, r.id, "AFFECTATION",
                                  f"Affecté à {agent_aff.prenom} {agent_aff.nom}.",
                                  auteur="superviseur")
            if evolution > 0.55:
                r.statut = "EN_COURS"
                audit.enregistrer(db, r.id, "CHANGEMENT_STATUT", "Instruction démarrée.",
                                  auteur=str(r.id_agent_affecte))
            if evolution > 0.7 and jours_en_arriere > 3:
                r.statut = "CLOTURE"
                r.motif_cloture = random.choice(["FAVORABLE", "PARTIEL", "DEFAVORABLE"])
                r.date_cloture = date_reception + timedelta(days=random.randint(2, 6))
                audit.enregistrer(db, r.id, "CLOTURE",
                                  f"Clôture motif {r.motif_cloture}.", auteur=str(r.id_agent_affecte))

        db.commit()
        print(f"[OK] Seed termine : {len(agents)} agents, {len(clients)} clients, 25 reclamations.")
        print("[OK] Comptes de connexion :")
        print("       admin / admin123   (role ADMIN — tous droits)")
        print("       agent / agent123   (role AGENT — lecture + creation + commentaire)")
    finally:
        db.close()


if __name__ == "__main__":
    reset_et_seed()
