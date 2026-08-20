"""Modèles ORM — entités principales du CDC §9.1.

Le minimum viable pour respecter :
- BR001 (dossier unique non duplicable)
- BR002 (traçabilité immuable : on n'expose pas de DELETE)
- BR007 (escalade SLA)
- RG007 (ID au format RECx-AAAAMM-NNNNN)
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, Text, ForeignKey, Float, Boolean, Index,
)
from sqlalchemy.orm import relationship

from .database import Base
from .services.crypto import EncryptedString


class Entite(Base):
    """Entité organisationnelle isolée (banque, assurance, filiale).

    Chaque utilisateur appartient à une entité (sauf ADMIN qui voit tout).
    Chaque réclamation est rattachée à une entité — l'isolation est appliquée
    sur tous les endpoints de listing (BR009 + NFR004).
    """
    __tablename__ = "entites"
    id = Column(Integer, primary_key=True)
    code = Column(String(30), unique=True, nullable=False, index=True)
    libelle = Column(String(100), nullable=False)
    type = Column(String(20), default="BANQUE")  # BANQUE / ASSURANCE / AUTRE


class Equipe(Base):
    """Équipe de traitement (front-office, back-office, fraude, juridique…).

    On rattache chaque agent à une équipe et chaque réclamation peut être
    transférée d'une équipe à une autre.
    """
    __tablename__ = "equipes"
    id = Column(Integer, primary_key=True)
    code = Column(String(30), unique=True, nullable=False, index=True)
    libelle = Column(String(100), nullable=False)
    description = Column(Text)
    id_entite = Column(Integer, ForeignKey("entites.id"))

    membres = relationship("Agent", back_populates="equipe")
    entite = relationship("Entite")


class Client(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True)
    nom = Column(String(100), nullable=False)
    prenom = Column(String(100), nullable=False)
    type = Column(String(20), default="PHYSIQUE")
    # Champs personnels chiffrés (NFR005). Longueurs augmentées pour absorber
    # l'expansion du chiffrement Fernet (~ +110 octets).
    telephone = Column(EncryptedString(500))
    email = Column(EncryptedString(500))
    numero_compte = Column(EncryptedString(500))
    # Hash SHA-256 de l'email (indexable, non-réversible) pour la déduplication.
    email_hash = Column(String(64), index=True)

    reclamations = relationship("Reclamation", back_populates="client")


class Agent(Base):
    __tablename__ = "agents"
    id = Column(Integer, primary_key=True)
    nom = Column(String(100), nullable=False)
    prenom = Column(String(100), nullable=False)
    email_pro = Column(String(150), unique=True, nullable=False)
    role = Column(String(30), default="AGENT")
    service = Column(String(50))
    actif = Column(Boolean, default=True)
    username = Column(String(50), unique=True, index=True)
    password_hash = Column(String(200))
    totp_secret = Column(String(64))
    mfa_active = Column(Boolean, default=False, nullable=False)
    id_equipe = Column(Integer, ForeignKey("equipes.id"))
    equipe = relationship("Equipe", back_populates="membres")
    id_entite = Column(Integer, ForeignKey("entites.id"))
    entite = relationship("Entite")

    reclamations_creees = relationship(
        "Reclamation", back_populates="agent_creation",
        foreign_keys="Reclamation.id_agent_creation",
    )
    reclamations_affectees = relationship(
        "Reclamation", back_populates="agent_affecte",
        foreign_keys="Reclamation.id_agent_affecte",
    )


class Reclamation(Base):
    __tablename__ = "reclamations"

    id = Column(Integer, primary_key=True)
    code = Column(String(30), unique=True, nullable=False, index=True)

    canal = Column(String(20), nullable=False)
    statut = Column(String(20), default="NOUVEAU", nullable=False, index=True)
    categorie = Column(String(50), nullable=False)
    sous_categorie = Column(String(80))
    priorite = Column(String(20), default="STANDARD", nullable=False)
    description = Column(Text, nullable=False)
    montant_enjeu = Column(Float, default=0.0)

    id_client = Column(Integer, ForeignKey("clients.id"), nullable=False)
    id_agent_creation = Column(Integer, ForeignKey("agents.id"))
    id_agent_affecte = Column(Integer, ForeignKey("agents.id"))
    id_equipe_affectee = Column(Integer, ForeignKey("equipes.id"))
    id_entite = Column(Integer, ForeignKey("entites.id"), index=True)

    date_reception = Column(DateTime, default=datetime.utcnow, nullable=False)
    date_echeance_sla = Column(DateTime, nullable=False)
    date_cloture = Column(DateTime)
    motif_cloture = Column(String(40))
    # Token opaque envoyé au client pour le suivi public (FR033).
    token_suivi = Column(String(80), unique=True, index=True)
    # Conservation BCEAO/CIMA (RG011).
    archivee = Column(Boolean, default=False, nullable=False, index=True)
    date_archivage = Column(DateTime)
    anonymisee = Column(Boolean, default=False, nullable=False, index=True)
    date_anonymisation = Column(DateTime)

    client = relationship("Client", back_populates="reclamations")
    agent_creation = relationship(
        "Agent", foreign_keys=[id_agent_creation], back_populates="reclamations_creees")
    agent_affecte = relationship(
        "Agent", foreign_keys=[id_agent_affecte], back_populates="reclamations_affectees")
    equipe_affectee = relationship("Equipe", foreign_keys=[id_equipe_affectee])
    interactions = relationship(
        "Interaction", back_populates="reclamation", order_by="Interaction.date_heure")

    __table_args__ = (
        Index("ix_reclamations_priorite_statut", "priorite", "statut"),
    )


class Interaction(Base):
    """Journal immuable d'une réclamation (BR002, FR021).

    Aucun endpoint ne permet de supprimer ou modifier une interaction.
    """
    __tablename__ = "interactions"

    id = Column(Integer, primary_key=True)
    id_reclamation = Column(Integer, ForeignKey("reclamations.id"), nullable=False, index=True)
    type = Column(String(30), nullable=False)
    contenu = Column(Text, nullable=False)
    auteur = Column(String(150), default="système")
    date_heure = Column(DateTime, default=datetime.utcnow, nullable=False)
    valeur_avant = Column(Text)
    valeur_apres = Column(Text)

    reclamation = relationship("Reclamation", back_populates="interactions")


class SequenceCompteur(Base):
    """Compteur mensuel pour générer un ID strictement croissant (RG007)."""
    __tablename__ = "sequence_compteurs"
    periode = Column(String(7), primary_key=True)
    dernier_numero = Column(Integer, default=0, nullable=False)


class ApprobationNiveau(Base):
    """Niveau d'approbation dans la chaîne hiérarchique.

    Chaque niveau cible un rôle ; toutes les approbations doivent être obtenues
    dans l'ordre pour passer du statut VALIDATION à DECISION (FR025).
    """
    __tablename__ = "approbations_niveaux"
    id = Column(Integer, primary_key=True)
    id_reclamation = Column(Integer, ForeignKey("reclamations.id"), nullable=False, index=True)
    ordre = Column(Integer, nullable=False)
    role_requis = Column(String(30), nullable=False)
    approuve_par = Column(Integer, ForeignKey("agents.id"))
    date_approbation = Column(DateTime)
    commentaire = Column(Text)


class ModeleReponse(Base):
    """Bibliothèque de modèles de réponse (FR024).

    Variables disponibles dans `corps` : {client.nom}, {client.prenom},
    {reclamation.code}, {reclamation.categorie}, {reclamation.priorite},
    {reclamation.date_reception}, {reclamation.date_echeance_sla}, etc.
    """
    __tablename__ = "modeles_reponse"
    id = Column(Integer, primary_key=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    libelle = Column(String(150), nullable=False)
    categorie_cible = Column(String(50))  # None = générique
    sujet = Column(String(255), nullable=False)
    corps = Column(Text, nullable=False)
    actif = Column(Boolean, default=True, nullable=False)
    date_creation = Column(DateTime, default=datetime.utcnow, nullable=False)


class PieceJointe(Base):
    """Pièce jointe attachée à un dossier (FR022).

    Le fichier physique est stocké sur disque ; la table conserve les méta-données
    + un checksum SHA-256 pour intégrité.
    """
    __tablename__ = "pieces_jointes"
    id = Column(Integer, primary_key=True)
    id_reclamation = Column(Integer, ForeignKey("reclamations.id"), nullable=False, index=True)
    nom_fichier = Column(String(255), nullable=False)
    type_mime = Column(String(100), nullable=False)
    taille_octets = Column(Integer, nullable=False)
    checksum_sha256 = Column(String(64), nullable=False)
    chemin_stockage = Column(String(500), nullable=False)
    auteur = Column(String(150), default="système")
    date_upload = Column(DateTime, default=datetime.utcnow, nullable=False)

    reclamation = relationship("Reclamation")


class Notification(Base):
    """Notification ciblée d'un agent (transfert, affectation, échéance…).

    Pour les transferts vers une équipe : on crée une notification par
    membre actif de l'équipe cible. C'est plus simple pour le modèle de
    lecture (chacun ne voit que ses propres notifs).
    """
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True)
    id_destinataire = Column(Integer, ForeignKey("agents.id"), nullable=False, index=True)
    type = Column(String(30), nullable=False)
    contenu = Column(Text, nullable=False)
    lue = Column(Boolean, default=False, nullable=False, index=True)
    date_creation = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    id_reclamation = Column(Integer, ForeignKey("reclamations.id"))
    code_reclamation = Column(String(30))
