"""Schémas Pydantic : validation entrée / sortie de l'API."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr, ConfigDict


CANAUX = {"EMAIL", "AGENCE", "TELEPHONE", "WEB", "WHATSAPP", "COURRIER"}
CATEGORIES = {"FINANCIERE", "CONTRACTUELLE", "SERVICE", "FRAUDE"}
PRIORITES = {"STANDARD", "URGENT", "CRITIQUE"}
STATUTS = {
    "NOUVEAU", "QUALIF", "AFFECTE", "EN_COURS", "ATT_CLIENT",
    "ALERTE", "ESCALADE", "VALIDATION", "DECISION", "CLOTURE", "REOUVRE", "REJETE",
}
MOTIFS_CLOTURE = {"FAVORABLE", "PARTIEL", "DEFAVORABLE", "SANS_SUITE", "MEDIATION"}


class ClientBase(BaseModel):
    nom: str
    prenom: str
    type: str = "PHYSIQUE"
    telephone: Optional[str] = None
    email: Optional[str] = None
    numero_compte: Optional[str] = None


class ClientCreate(ClientBase):
    pass


class ClientOut(ClientBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


ROLES = {"AGENT", "GESTIONNAIRE", "SUPERVISEUR", "CONFORMITE", "ADMIN"}


class AgentBase(BaseModel):
    nom: str
    prenom: str
    email_pro: EmailStr
    role: str = "AGENT"
    service: Optional[str] = None


class EquipeOut(BaseModel):
    id: int
    code: str
    libelle: str
    description: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class AgentOut(AgentBase):
    id: int
    actif: bool
    username: Optional[str] = None
    mfa_active: bool = False
    id_equipe: Optional[int] = None
    equipe: Optional[EquipeOut] = None
    model_config = ConfigDict(from_attributes=True)


class UserCreate(AgentBase):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)


class UserUpdate(BaseModel):
    nom: Optional[str] = None
    prenom: Optional[str] = None
    email_pro: Optional[EmailStr] = None
    role: Optional[str] = None
    service: Optional[str] = None
    actif: Optional[bool] = None


class PasswordResetRequest(BaseModel):
    new_password: str = Field(..., min_length=6)


class ReclamationCreate(BaseModel):
    canal: str = Field(..., description="EMAIL / AGENCE / TELEPHONE / WEB / WHATSAPP / COURRIER")
    categorie: str
    sous_categorie: Optional[str] = None
    priorite: str = "STANDARD"
    description: str = Field(..., min_length=10)
    montant_enjeu: float = 0.0
    client: ClientCreate
    id_agent_creation: Optional[int] = None


class InteractionOut(BaseModel):
    id: int
    type: str
    contenu: str
    auteur: str
    date_heure: datetime
    valeur_avant: Optional[str] = None
    valeur_apres: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class ReclamationOut(BaseModel):
    id: int
    code: str
    canal: str
    statut: str
    categorie: str
    sous_categorie: Optional[str] = None
    priorite: str
    description: str
    montant_enjeu: float
    client: ClientOut
    agent_creation: Optional[AgentOut] = None
    agent_affecte: Optional[AgentOut] = None
    equipe_affectee: Optional[EquipeOut] = None
    date_reception: datetime
    date_echeance_sla: datetime
    date_cloture: Optional[datetime] = None
    motif_cloture: Optional[str] = None
    sla_pourcentage: Optional[float] = None
    sla_statut: Optional[str] = None
    token_suivi: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class ReclamationDetail(ReclamationOut):
    interactions: List[InteractionOut] = []


class ChangeStatutRequest(BaseModel):
    nouveau_statut: str
    commentaire: Optional[str] = None
    auteur: str = "agent"


class AffectationRequest(BaseModel):
    id_agent_affecte: int
    auteur: str = "superviseur"


class TransfertEquipeRequest(BaseModel):
    id_equipe_cible: int
    motif: str = Field(..., min_length=3)
    auteur: str = "superviseur"


class ModeleReponseBase(BaseModel):
    code: str = Field(..., min_length=3, max_length=50)
    libelle: str = Field(..., min_length=3, max_length=150)
    categorie_cible: Optional[str] = None
    sujet: str = Field(..., min_length=3)
    corps: str = Field(..., min_length=10)
    actif: bool = True


class ModeleReponseCreate(ModeleReponseBase):
    pass


class ModeleReponseOut(ModeleReponseBase):
    id: int
    date_creation: datetime
    model_config = ConfigDict(from_attributes=True)


class TemplateRenduRequest(BaseModel):
    code_reclamation: str


class TemplateRenduResponse(BaseModel):
    sujet: str
    corps: str


class ApprobationNiveauOut(BaseModel):
    id: int
    ordre: int
    role_requis: str
    approuve_par: Optional[int] = None
    date_approbation: Optional[datetime] = None
    commentaire: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class InitierValidationRequest(BaseModel):
    roles_chaine: list[str] = Field(..., min_length=1, max_length=5,
                                     description="Rôles dans l'ordre d'approbation")


class ApprouverNiveauRequest(BaseModel):
    commentaire: Optional[str] = None


class DoublonItem(BaseModel):
    code: str
    statut: str
    categorie: str
    sous_categorie: Optional[str] = None
    date_reception: datetime
    score_similarite: float = Field(..., description="Score entre 0 et 1")


class DetectionDoublonsRequest(BaseModel):
    email: Optional[str] = None
    sous_categorie: Optional[str] = None
    categorie: Optional[str] = None
    description: Optional[str] = None
    jours: int = Field(7, ge=1, le=90)


class DetectionDoublonsResponse(BaseModel):
    doublons: list[DoublonItem]
    nb_potentiels: int


class SuggestionIARequest(BaseModel):
    description: str = Field(..., min_length=5)


class VoisinIA(BaseModel):
    code: str
    categorie: str
    priorite: str
    sous_categorie: Optional[str] = None


class SuggestionIAResponse(BaseModel):
    categorie_suggeree: str
    score_categorie: float
    priorite_suggeree: str
    score_priorite: float
    explication: str
    voisins_similaires: list[VoisinIA]


class PieceJointeOut(BaseModel):
    id: int
    nom_fichier: str
    type_mime: str
    taille_octets: int
    checksum_sha256: str
    auteur: str
    date_upload: datetime
    model_config = ConfigDict(from_attributes=True)


class NotificationOut(BaseModel):
    id: int
    type: str
    contenu: str
    lue: bool
    date_creation: datetime
    code_reclamation: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class CommentaireRequest(BaseModel):
    contenu: str = Field(..., min_length=1)
    auteur: str = "agent"


class ClotureRequest(BaseModel):
    motif: str
    commentaire: Optional[str] = None
    auteur: str = "agent"


class DashboardKPI(BaseModel):
    recues_mois: int
    en_cours: int
    en_alerte_sla: int
    cloturees: int
    sla_depasses: int
    taux_resolution_5j: float


class RepartitionItem(BaseModel):
    label: str
    valeur: int
    pourcentage: float


class DashboardData(BaseModel):
    kpi: DashboardKPI
    repartition_canal: List[RepartitionItem]
    repartition_categorie: List[RepartitionItem]
    repartition_priorite: List[RepartitionItem]
    repartition_sla: List[RepartitionItem]
    volume_hebdo: List[dict]
    volume_mensuel: List[dict]
    alertes_sla: List[ReclamationOut]
    echeances_jour: int
    aujourd_hui: str
