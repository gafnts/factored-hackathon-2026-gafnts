import type {
  Action,
  CardSupportHandoff,
  CaseDetail,
  CaseList,
  CaseRow,
  Fact,
  RecordedCall,
} from "../contracts/console";

export type Queue = CaseList["queue"];
export type ReasonCode = CaseRow["reason_code"];
export type Status = CaseDetail["case"]["status"];

// Each is keyed by the contract's own values, so a value a schema adds fails the build until it has its text here
// (ADR-0007, Types from the schemas).
const REASONS: Record<ReasonCode, string> = {
  unrecognized_charge: "Cargo no reconocido",
  customer_request: "Pide hablar con una persona",
  complaint: "Reclamo",
  unblock_request: "Pide desbloquear una tarjeta",
  customer_not_active: "Cliente no activo",
  ambiguous_card: "Tarjeta ambigua",
  action_not_verified: "Acción no verificada",
  block_lapsed: "Bloqueo no confirmado a tiempo",
  unsupported_request: "Solicitud que el chat no atiende",
  clarification_failed: "No se pudo precisar la solicitud",
  record_conflict: "Datos en conflicto",
  missing_data: "Dato faltante",
  tool_failure: "Falla de una herramienta",
};

const REQUESTS: Record<CardSupportHandoff["request"]["label"], string> = {
  card_status: "Estado de una tarjeta",
  available_credit: "Crédito disponible",
  recent_transactions: "Transacciones recientes",
  decline_reason: "Motivo de un rechazo",
  block_card: "Bloquear una tarjeta",
  unrecognized_charge: "Cargo no reconocido",
  unsupported: "Fuera de lo que el chat atiende",
  talk_to_human: "Hablar con una persona",
};

const FIELDS: Record<string, string> = {
  customer_status: "Estado del cliente",
  country: "País",
  product_type: "Tipo de tarjeta",
  last_four: "Últimos cuatro dígitos",
  product_status: "Estado de la tarjeta",
  currency: "Moneda",
  credit_limit: "Límite de crédito",
  current_balance: "Saldo",
  available_credit: "Crédito disponible",
  over_limit_by: "Excede el límite por",
  opening_date: "Apertura",
  expiration_date: "Vencimiento",
  past_expiration: "Vencida",
  product_id: "Tarjeta",
  transaction_date: "Fecha",
  transaction_type: "Tipo",
  transaction_status: "Estado",
  response_code: "Código de respuesta",
  amount: "Monto",
  merchant_name: "Comercio",
  merchant_category: "Categoría del comercio",
  channel: "Canal",
  transaction_country: "País",
  is_fraud: "Marcada como fraude por el banco",
  before_card_opening: "Anterior a la apertura de la tarjeta",
  after_card_expiration: "Posterior al vencimiento de la tarjeta",
};

const RULES: Record<string, string> = {
  unrecorded: "no consta en el registro de ejecución",
  mismatch: "no coincide con el registro de ejecución",
  reserved: "solo la herramienta que archiva el caso puede añadirlo",
  policy: "la política exige prioridad urgente (POL-47)",
  maxItems: "excede el número permitido",
  maxLength: "excede la longitud permitida",
  minLength: "está vacío",
  not: "contiene una secuencia de dígitos no permitida (POL-11)",
  pattern: "no tiene el formato esperado",
  type: "no es del tipo esperado",
  required: "falta",
  enum: "no es un valor permitido",
};

const PARTS: Record<string, string> = {
  verified_facts: "Hecho verificado",
  evidence: "Evidencia",
  actions: "Acción",
  customer_statements: "Lo que dice el cliente",
  unresolved_questions: "Pregunta sin resolver",
};

const WHOLE: Record<string, string> = {
  "/priority": "Prioridad",
  "/request/summary": "Resumen de la solicitud",
  "/verified_facts": "Hechos verificados",
  "/evidence": "Evidencia",
};

export const AGENT = {
  title: "Consola de casos",
  queues: {
    dispute_intake: "Disputas",
    customer_service: "Servicio al cliente",
  } satisfies Record<Queue, string>,
  priorities: {
    urgent: "Urgente",
    normal: "Normal",
  } satisfies Record<CaseRow["priority"], string>,
  languages: {
    es: "español",
    pt: "portugués",
  } satisfies Record<CaseRow["language"], string>,
  statuses: {
    filed: "Archivado",
    claimed: "Tomado",
    resolved: "Resuelto",
  } satisfies Record<Status, string>,
  triggers: {
    required: "Requerido por la política",
    accepted_offer: "Aceptado por el cliente",
  } satisfies Record<CardSupportHandoff["trigger"], string>,
  outcomes: {
    verified: "Verificado",
    not_verified: "No verificado",
    declined_by_customer: "Cancelado por el cliente",
    lapsed: "Venció sin usarse",
  } satisfies Record<Action["outcome"], string>,
  blockReasons: {
    lost: "pérdida",
    stolen: "robo",
    unrecognized_charge: "cargo no reconocido",
    customer_request: "solicitud del cliente",
  } satisfies Record<Action["reason"], string>,
  subjects: {
    customer: "Cliente",
    card: "Tarjeta",
    transaction: "Transacción",
  } satisfies Record<Fact["subject"], string>,
  callOutcomes: {
    ok: "correcta",
    not_found: "sin resultado",
    refused: "rechazada por la herramienta",
    invalid_input: "entrada inválida",
    failed: "falló",
    denied: "denegada por la política de acceso",
  } satisfies Record<NonNullable<RecordedCall["outcome"]>, string>,
  errors: {
    timeout: "tiempo agotado",
    throttled: "limitada",
    lambda_error: "error de la función",
    transport: "error de red",
    denied: "denegada",
  } satisfies Record<NonNullable<RecordedCall["error_code"]>, string>,
  via: {
    gateway: "por el Gateway",
    direct: "invocación directa",
  } satisfies Record<NonNullable<RecordedCall["via"]>, string>,
  reason: (code: ReasonCode) => REASONS[code],
  request: (label: CardSupportHandoff["request"]["label"]) => REQUESTS[label],
  field: (field: string) => FIELDS[field] ?? field,
  // A path names the payload as the agent built it, before the parts that failed were left out.
  path: (path: string) => {
    const whole = WHOLE[path];
    if (whole) return whole;
    const [, part, index] = /^\/([a-z_]+)\/([0-9]+)/.exec(path) ?? [];
    const name = part === undefined ? undefined : PARTS[part];
    return name && index !== undefined
      ? `${name} n.º ${String(Number(index) + 1)}`
      : path;
  },
  rule: (rule: string) => RULES[rule] ?? `no cumple la regla «${rule}»`,
  value: (value: Fact["value"] | undefined) => {
    if (value === null || value === undefined) return "No registrado";
    if (typeof value === "boolean") return value ? "Sí" : "No";
    return String(value);
  },
  queue: {
    empty: "No hay casos en esta cola.",
    more: "Cargar más",
    flagged: "Marcado",
    count: (n: number, more: boolean) =>
      `${String(n)}${more ? "+" : ""} ${n === 1 && !more ? "caso" : "casos"}`,
  },
  refreshed: (time: string) => `Actualizado a las ${time}`,
  stale: "No se pudo actualizar; se intentará de nuevo.",
  noAccess:
    "Su usuario no tiene acceso a la consola de casos. Cierre la sesión e inicie con un usuario de agente.",
  search: {
    label: "Referencia",
    submit: "Buscar",
    placeholder: "7K2M-9QXA",
    notFound: (reference: string) =>
      `Ningún caso tiene la referencia ${reference}.`,
    invalid: "Una referencia tiene ocho caracteres, como 7K2M-9QXA.",
  },
  case: {
    none: "Elija un caso de una cola, o búsquelo por su referencia.",
    loading: "Cargando el caso…",
    failed: "No se pudo cargar el caso; se intentará de nuevo.",
    close: "Cerrar el caso",
    filed: (time: string) => `Archivado el ${time}`,
    businessDate: (date: string) => `Fecha del banco: ${date}`,
    answerIn: (language: string) => `Responder en ${language}`,
    rules: "Reglas",
    flagged: "Caso marcado",
    flaggedBody:
      "Al archivarlo, el sistema dejó fuera o corrigió partes que no pudo verificar. Ninguna muestra su valor.",
    request: "Solicitud",
    actions: "Acciones",
    noActions: "Ninguna acción sobre la tarjeta.",
    block: (reason: string) => `Bloqueo de la tarjeta por ${reason}`,
    confirmedAt: (time: string) => `Confirmado el ${time}`,
    facts: "Hechos verificados",
    noFacts: "Ningún hecho verificado.",
    readBy: "Leído por",
    statements: "Lo que dice el cliente, sin verificar",
    questions: "Preguntas sin resolver",
    evidence: "Evidencia: las llamadas en el registro de ejecución",
    attempt: (n: number) => `intento ${String(n)}`,
    latency: (ms: number) => `${String(ms)} ms`,
    requestId: "ID de la solicitud",
    notRecorded: "Aún no está en el registro de ejecución.",
    identifiers: "Identificadores",
    customer: "Cliente",
    signIn: "Sesión del cliente",
    handoff: "Caso",
    versions: (policy: number, snapshot: string) =>
      `Política v${String(policy)} · instantánea ${snapshot}`,
  },
};
