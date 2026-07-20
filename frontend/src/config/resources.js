/**
 * Registre déclaratif des ressources CRUD du SPA. Chaque entrée décrit
 * l'endpoint API, les colonnes de la liste, les filtres, et (pour les
 * ressources modifiables) les champs du formulaire et la clé de permission.
 *
 * `optionsKey` référence une liste renvoyée par /api/crud/options/.
 */
export const RESOURCES = {
  projects: {
    endpoint: 'projects',
    title: 'Projets',
    singular: 'Projet',
    writable: true,
    permKey: 'project',
    titleField: 'nom',
    columns: [
      { key: 'nom', label: 'Nom' },
      { key: 'code', label: 'Code' },
      { key: 'country_label', label: 'Pays' },
      { key: 'programs_count', label: 'Programmes', align: 'right' },
    ],
    filters: [
      { key: 'country', label: 'Pays', optionsKey: 'countries' },
    ],
    fields: [
      { name: 'code', label: 'Code', required: true, half: true },
      { name: 'nom', label: 'Nom', required: true, half: true },
      { name: 'country', label: 'Pays', type: 'select', optionsKey: 'countries', half: true },
      { name: 'place', label: 'Lieu', type: 'select', optionsKey: 'places', half: true },
      { name: 'address', label: 'Adresse', type: 'textarea' },
      { name: 'description', label: 'Description', type: 'textarea' },
    ],
  },

  programs: {
    endpoint: 'programs',
    title: 'Programmes',
    singular: 'Programme',
    writable: true,
    permKey: 'program',
    titleField: 'name',
    columns: [
      { key: 'name', label: 'Nom' },
      { key: 'code', label: 'Code' },
      { key: 'project_label', label: 'Projet' },
      { key: 'status_display', label: 'Statut', badge: true },
      { key: 'parcels_count', label: 'Parcelles', align: 'right' },
    ],
    filters: [
      { key: 'project', label: 'Projet', optionsKey: 'projects' },
      { key: 'status', label: 'Statut', optionsKey: 'program_statuses' },
      { key: 'program_type', label: 'Type', optionsKey: 'program_types' },
    ],
    fields: [
      { name: 'code', label: 'Code', required: true, half: true },
      { name: 'name', label: 'Nom', required: true, half: true },
      { name: 'project', label: 'Projet', type: 'select', optionsKey: 'projects', required: true, half: true },
      { name: 'program_type', label: 'Type de programme', type: 'select', optionsKey: 'program_types', half: true },
      { name: 'status', label: 'Statut', type: 'select', optionsKey: 'program_statuses', half: true },
      { name: 'marketing_title', label: 'Titre marketing', half: true },
      { name: 'country', label: 'Pays', type: 'select', optionsKey: 'countries', required: true, half: true },
      { name: 'place', label: 'Lieu', type: 'select', optionsKey: 'places', half: true },
      { name: 'total_area_m2', label: 'Superficie (m²)', type: 'number', half: true },
      { name: 'estimated_lot_count', label: 'Nb lots estimé', type: 'number', half: true },
      { name: 'launch_date', label: 'Date de lancement', type: 'date', half: true },
      { name: 'closing_date', label: 'Date de clôture', type: 'date', half: true },
      { name: 'manager_name', label: 'Responsable', half: true },
      { name: 'manager_phone', label: 'Tél. responsable', half: true },
      { name: 'manager_email', label: 'Email responsable', type: 'email', half: true },
      { name: 'address', label: 'Adresse', type: 'textarea' },
      { name: 'description', label: 'Description', type: 'textarea' },
    ],
  },

  customers: {
    endpoint: 'customers',
    title: 'Clients',
    singular: 'Client',
    writable: true,
    permKey: 'customer',
    titleField: 'display_name',
    columns: [
      { key: 'display_name', label: 'Nom' },
      { key: 'customer_type_display', label: 'Type', badge: true },
      { key: 'phone', label: 'Téléphone' },
      { key: 'email', label: 'Email' },
    ],
    filters: [
      { key: 'customer_type', label: 'Type', optionsKey: 'customer_types' },
      { key: 'country', label: 'Pays', optionsKey: 'countries' },
    ],
    fields: [
      { name: 'customer_type', label: 'Type de client', type: 'select', optionsKey: 'customer_types', required: true, half: true },
      { name: 'first_name', label: 'Prénom', half: true },
      { name: 'last_name', label: 'Nom', half: true },
      { name: 'company_name', label: 'Raison sociale', half: true },
      { name: 'phone', label: 'Téléphone', half: true },
      { name: 'email', label: 'Email', type: 'email', half: true },
      { name: 'country', label: 'Pays', type: 'select', optionsKey: 'countries', half: true },
      { name: 'place', label: 'Lieu', type: 'select', optionsKey: 'places', half: true },
      { name: 'id_type', label: 'Type de pièce', half: true },
      { name: 'id_number', label: 'N° de pièce', half: true },
      { name: 'address', label: 'Adresse', type: 'textarea' },
      { name: 'notes', label: 'Notes', type: 'textarea' },
    ],
  },

  parcels: {
    endpoint: 'parcels',
    title: 'Parcelles',
    singular: 'Parcelle',
    writable: false,
    titleField: 'lot_number',
    columns: [
      { key: 'lot_number', label: 'Lot' },
      { key: 'parcel_code', label: 'Référence' },
      { key: 'program_label', label: 'Programme' },
      { key: 'commercial_status_display', label: 'Statut', badge: true },
      { key: 'area', label: 'Surface', align: 'right' },
    ],
    filters: [
      { key: 'program', label: 'Programme', optionsKey: 'programs' },
      { key: 'commercial_status', label: 'Statut', optionsKey: 'parcel_commercial_statuses' },
    ],
  },

  reservations: {
    endpoint: 'reservations',
    title: 'Réservations',
    singular: 'Réservation',
    writable: false,
    titleField: 'reservation_number',
    columns: [
      { key: 'reservation_number', label: 'N°' },
      { key: 'customer_label', label: 'Client' },
      { key: 'program_label', label: 'Programme' },
      { key: 'reserved_price_display', label: 'Prix réservé', align: 'right' },
      { key: 'status_display', label: 'Statut', badge: true },
      { key: 'reservation_date', label: 'Date', type: 'date' },
    ],
    filters: [
      { key: 'program', label: 'Programme', optionsKey: 'programs' },
      { key: 'status', label: 'Statut', optionsKey: 'reservation_statuses' },
    ],
  },

  sales: {
    endpoint: 'sales',
    title: 'Ventes',
    singular: 'Vente',
    writable: false,
    titleField: 'sale_number',
    columns: [
      { key: 'sale_number', label: 'N°' },
      { key: 'customer_label', label: 'Client' },
      { key: 'program_label', label: 'Programme' },
      { key: 'net_price_display', label: 'Prix net', align: 'right' },
      { key: 'status_display', label: 'Statut', badge: true },
      { key: 'sale_date', label: 'Date', type: 'date' },
    ],
    filters: [
      { key: 'program', label: 'Programme', optionsKey: 'programs' },
      { key: 'status', label: 'Statut', optionsKey: 'sale_statuses' },
    ],
  },

  payments: {
    endpoint: 'payments',
    title: 'Paiements',
    singular: 'Paiement',
    writable: false,
    titleField: 'payment_number',
    columns: [
      { key: 'payment_number', label: 'N°' },
      { key: 'sale_label', label: 'Dossier de vente' },
      { key: 'amount_display', label: 'Montant', align: 'right' },
      { key: 'payment_method', label: 'Moyen' },
      { key: 'status_display', label: 'Statut', badge: true },
      { key: 'payment_date', label: 'Date', type: 'date' },
    ],
    filters: [
      { key: 'status', label: 'Statut', optionsKey: 'payment_statuses' },
    ],
  },

  leads: {
    endpoint: 'leads',
    title: 'Prospects',
    singular: 'Prospect',
    writable: false,
    titleField: 'customer_label',
    columns: [
      { key: 'customer_label', label: 'Client' },
      { key: 'program_label', label: 'Programme' },
      { key: 'status_display', label: 'Statut', badge: true },
      { key: 'source', label: 'Source' },
      { key: 'budget_max_display', label: 'Budget max', align: 'right' },
    ],
    filters: [
      { key: 'program', label: 'Programme', optionsKey: 'programs' },
      { key: 'status', label: 'Statut', optionsKey: 'lead_statuses' },
    ],
  },

  phases: {
    endpoint: 'phases',
    title: 'Phases',
    singular: 'Phase',
    writable: false,
    titleField: 'name',
    columns: [
      { key: 'code', label: 'Code' },
      { key: 'name', label: 'Nom' },
      { key: 'program_label', label: 'Programme' },
      { key: 'status_display', label: 'Statut', badge: true },
      { key: 'order', label: 'Ordre', align: 'right' },
    ],
    filters: [
      { key: 'program', label: 'Programme', optionsKey: 'programs' },
      { key: 'status', label: 'Statut', optionsKey: 'phase_statuses' },
    ],
  },

  datasets: {
    endpoint: 'datasets',
    title: 'Jeux de données',
    singular: 'Jeu de données',
    writable: false,
    titleField: 'name',
    columns: [
      { key: 'name', label: 'Nom' },
      { key: 'program_label', label: 'Programme' },
      { key: 'version', label: 'Version' },
      { key: 'is_current', label: 'Courant', type: 'bool' },
      { key: 'imported_by', label: 'Importé par' },
    ],
    filters: [
      { key: 'program', label: 'Programme', optionsKey: 'programs' },
    ],
  },

  blocks: {
    endpoint: 'blocks',
    title: 'Îlots',
    singular: 'Îlot',
    writable: false,
    titleField: 'label',
    columns: [
      { key: 'code', label: 'Code' },
      { key: 'label', label: 'Libellé' },
      { key: 'program_label', label: 'Programme' },
      { key: 'area', label: 'Superficie', align: 'right' },
    ],
    filters: [
      { key: 'program', label: 'Programme', optionsKey: 'programs' },
    ],
  },

  assets: {
    endpoint: 'assets',
    title: 'Actifs',
    singular: 'Actif',
    writable: false,
    titleField: 'label',
    columns: [
      { key: 'code', label: 'Code' },
      { key: 'label', label: 'Libellé' },
      { key: 'program_label', label: 'Programme' },
      { key: 'status_display', label: 'Statut', badge: true },
      { key: 'sale_price_display', label: 'Prix de vente', align: 'right' },
    ],
    filters: [
      { key: 'program', label: 'Programme', optionsKey: 'programs' },
      { key: 'status', label: 'Statut', optionsKey: 'asset_statuses' },
    ],
  },

  construction: {
    endpoint: 'construction',
    title: 'Chantiers',
    singular: 'Chantier',
    writable: false,
    titleField: 'title',
    columns: [
      { key: 'code', label: 'Code' },
      { key: 'title', label: 'Intitulé' },
      { key: 'parcel_label', label: 'Lot' },
      { key: 'status_display', label: 'Statut', badge: true },
      { key: 'progress_percent', label: 'Avancement %', align: 'right' },
    ],
    filters: [
      { key: 'status', label: 'Statut', optionsKey: 'construction_statuses' },
    ],
  },
}

export function getResourceConfig(key) {
  return RESOURCES[key] || null
}
