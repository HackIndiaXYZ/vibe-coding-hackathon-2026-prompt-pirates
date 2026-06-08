import axios, { AxiosError } from 'axios'
import type {
  UploadResponse,
  AnalysisRequest,
  FullAnalysisResponse,
  PrescriptionListResponse,
  PrescriptionSummary,
  HealthResponse,
  ApiError,
} from '@/types/api'
import type { PrescriptionAnalysis, Medicine } from '@/types/medicine'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 480_000,
  headers: { Accept: 'application/json' },
})

// ─── Error normaliser ─────────────────────────────────────────────────────────
export function parseApiError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const axiosErr = error as AxiosError<ApiError>
    const data = axiosErr.response?.data
    if (data?.detail) {
      return typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
    }
    if (data?.message) return data.message
    if (axiosErr.code === 'ECONNABORTED') return 'Request timed out. The server may be busy — please try again.'
    if (axiosErr.code === 'ERR_NETWORK') return 'Cannot reach the backend server. Make sure it is running on port 8000.'
    if (axiosErr.response?.status === 413) return 'File is too large. Please upload a smaller image.'
    if (axiosErr.response?.status === 422) return 'OCR failed. Try a clearer, well-lit photo of the prescription.'
    if (axiosErr.response?.status === 404) return 'Prescription not found. Please upload the image first.'
    if (axiosErr.response?.status === 429) return 'Too many requests. Please wait a moment before trying again.'
    if (axiosErr.response?.status && axiosErr.response.status >= 500)
      return 'Server error. The backend may be starting up — please retry in a moment.'
  }
  if (error instanceof Error) return error.message
  return 'An unexpected error occurred.'
}

// ─── Backend API calls ────────────────────────────────────────────────────────

export async function uploadPrescription(
  file: File,
  onProgress?: (pct: number) => void
): Promise<UploadResponse> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await apiClient.post<UploadResponse>('/api/v1/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => {
      if (e.total && onProgress) onProgress(Math.round((e.loaded / e.total) * 100))
    },
  })
  return data
}

export async function analysePresciption(request: AnalysisRequest): Promise<FullAnalysisResponse> {
  const { data } = await apiClient.post<FullAnalysisResponse>('/api/v1/analysis', request)
  return data
}

export async function getAnalysis(
  prescriptionId: string,
  patientAge?: number | null,
  language = 'en'
): Promise<FullAnalysisResponse> {
  const params: Record<string, string | number> = { language }
  if (patientAge != null) params.patient_age = patientAge
  const { data } = await apiClient.get<FullAnalysisResponse>(`/api/v1/analysis/${prescriptionId}`, { params })
  return data
}

export async function listPrescriptions(limit = 20, offset = 0): Promise<PrescriptionListResponse> {
  const { data } = await apiClient.get<PrescriptionListResponse>('/api/v1/prescriptions', {
    params: { limit, offset },
  })
  return data
}

export async function getPrescription(prescriptionId: string): Promise<PrescriptionSummary> {
  const { data } = await apiClient.get<PrescriptionSummary>(`/api/v1/prescriptions/${prescriptionId}`)
  return data
}

export async function getHealth(): Promise<HealthResponse> {
  const { data } = await apiClient.get<HealthResponse>('/api/v1/health')
  return data
}

// ─── Adapter helpers ──────────────────────────────────────────────────────────

function severityToUI(s: string): 'low' | 'moderate' | 'high' | 'critical' {
  if (s === 'medium') return 'moderate'
  if (s === 'critical') return 'critical'
  if (s === 'high') return 'high'
  return 'low'
}

function drowsinessFromBackend(
  causes: boolean,
  note: string,
  seriousSideEffects: string[]
): 'none' | 'mild' | 'moderate' | 'severe' {
  if (!causes) return 'none'
  const noteL = note.toLowerCase()
  const severe = seriousSideEffects.some((s) => s.toLowerCase().includes('drowsi') || s.toLowerCase().includes('sedati'))
  if (severe || noteL.includes('severe') || noteL.includes('do not drive')) return 'severe'
  if (noteL.includes('moderate') || noteL.includes('avoid driving')) return 'moderate'
  return 'mild'
}

/**
 * Build side effects list from backend data.
 *
 * FIX: serious_side_effects now correctly map to severity 'critical' (not 'high').
 * This ensures the card expanded view matches the severity shown in the dashboard summary.
 * The distinction:
 *   - common side_effects    → low severity  (expected, usually manageable)
 *   - serious_side_effects   → critical severity (rare but need immediate attention)
 */
function buildSideEffects(
  commonEffects: string[],
  seriousEffects: string[]
) {
  return [
    ...commonEffects.map((name, i) => ({
      id: `se-common-${i}`,
      name,
      description: name,
      severity: 'low' as const,
      frequency: 'common' as const,
    })),
    ...seriousEffects.map((name, i) => ({
      id: `se-serious-${i}`,
      name,
      description: name,
      // FIXED: was 'high', now correctly 'critical' so card matches dashboard alert
      severity: 'critical' as const,
      // Serious effects are rare; don't imply they're common
      frequency: 'rare' as const,
      actionRequired: 'Stop taking and contact your doctor immediately if this occurs.',
    })),
  ]
}

function buildAgeWarnings(warnings: string[]) {
  return warnings.map((w) => {
    const lower = w.toLowerCase()
    const ageGroup =
      lower.includes('child') || lower.includes('pediatric') || lower.includes('infant') ? 'pediatric' :
      lower.includes('elder') || lower.includes('geriatric') || lower.includes('old') ? 'geriatric' : 'adult'
    return {
      ageGroup: ageGroup as 'pediatric' | 'adult' | 'geriatric',
      warning: w,
      contraindicated: lower.includes('contraindicated') || lower.includes('not approved'),
    }
  })
}

// ─── Main adapter ─────────────────────────────────────────────────────────────

export function adaptBackendToUI(full: FullAnalysisResponse): PrescriptionAnalysis {
  const medicines: Medicine[] = full.medicines.map((m, idx) => {
    const sideEffects = buildSideEffects(m.side_effects, m.serious_side_effects)
    const drowsinessLevel = drowsinessFromBackend(m.causes_drowsiness, m.drowsiness_note, m.serious_side_effects)

    const dosage = {
      standard: m.dosage_info || 'As directed by your doctor',
      maximum: m.dosage_notes.find((n) => n.toLowerCase().includes('max')) || 'As prescribed',
      frequency: m.how_to_take || m.dosage_info || 'As directed',
      route: 'Oral',
      withFood: m.how_to_take.toLowerCase().includes('food') || m.how_to_take.toLowerCase().includes('meal'),
      withWater: true,
      missedDose: m.dosage_notes.find((n) => n.toLowerCase().includes('miss')) ||
        'Take as soon as you remember. Skip if next dose is near. Never double up.',
      overdoseWarning: m.serious_side_effects.length > 0
        ? 'If you suspect overdose, seek emergency medical attention immediately.'
        : undefined,
    }

    const isAlcohol = m.contraindications.some((c) => c.toLowerCase().includes('alcohol'))
    const interactions = isAlcohol ? [{
      id: `int-alcohol-${idx}`,
      drugName: 'Alcohol',
      severity: 'high' as const,
      description: 'Alcohol may interact with this medication.',
      recommendation: 'Avoid alcohol while taking this medicine.',
    }] : []

    const lifestyleRecs = [
      ...(m.causes_drowsiness ? [{
        id: `lr-driving-${idx}`,
        category: 'driving' as const,
        title: 'Driving Caution',
        description: m.drowsiness_note || 'This medication may impair your ability to drive. Exercise caution.',
        severity: drowsinessLevel === 'severe' ? 'critical' as const : 'moderate' as const,
      }] : []),
    ]

    return {
      id: `med-${idx}-${m.medicine_name.replace(/\s+/g, '-').toLowerCase()}`,
      name: m.medicine_name,
      genericName: m.drug_class ? `${m.medicine_name} (${m.drug_class})` : m.medicine_name,
      brandNames: [],
      drugClass: m.drug_class || 'Prescription Medicine',
      indication: m.use_case || 'As prescribed',
      description: m.explanation || 'This medicine is prescribed by your doctor.',
      mechanism: m.mechanism || '',
      dosage,
      sideEffects,
      interactions,
      drowsinessLevel,
      ageWarnings: buildAgeWarnings(m.age_warnings),
      lifestyleRecommendations: lifestyleRecs,
      requiresPrescription: true,
      storageInstructions: 'Store at room temperature. Keep away from children.',
      severity_level: m.severity_level,
      generated_by: m.generated_by,
      contraindications: m.contraindications,
      dosage_notes: m.dosage_notes,
    }
  })

  const overallWarnings: string[] = []
  if (full.overall_drowsiness_warning) overallWarnings.push('One or more medicines may cause drowsiness. Avoid driving or operating machinery.')
  if (full.overall_dosage_concern) overallWarnings.push('Dosage concerns detected. Review with your pharmacist.')
  if (full.overall_age_warning) overallWarnings.push('Age-specific warnings noted. Consult your doctor if in doubt.')

  // ── Awareness Alerts — HIGH threshold ────────────────────────────────────
  // Only surface genuinely important clinical warnings. Minor or common side
  // effects are deliberately excluded even if labelled 'critical' internally.
  //
  // An alert is generated ONLY when ALL of the following are true:
  //   (a) the medicine's overall severity_level is 'critical'  AND
  //   (b) at least one of:
  //       - there is a real serious_side_effect string from the backend, OR
  //       - the medicine is contraindicated (contraindications array non-empty), OR
  //       - drowsiness is severe (patient-safety risk while driving/machinery)
  //
  // Medicines that merely have common side effects mapped to 'critical' severity
  // internally (e.g. sunscreen with contact-dermatitis risk, moisturisers, OTC
  // supplements) are filtered out by requiring severity_level === 'critical'
  // from the backend — the authoritative source for clinical significance.
  const criticalAlerts: string[] = medicines
    .filter((m) => {
      const raw = full.medicines.find((r) => r.medicine_name === m.name)
      const hasBackendSeriousEffect = (raw?.serious_side_effects ?? []).some(
        (s) => s.trim().toLowerCase() !== 'none' && s.trim() !== ''
      )
      const hasContraindication = (raw?.contraindications ?? []).some(
        (c) => c.trim().toLowerCase() !== 'none' && c.trim() !== ''
      )
      const isSevereDrowsiness = m.drowsinessLevel === 'severe'

      // Gate 1: backend must classify as critical (not just a frontend mapping)
      const backendCritical = m.severity_level === 'critical'

      // Gate 2: must have at least one real clinical reason
      const hasRealReason = hasBackendSeriousEffect || hasContraindication || isSevereDrowsiness

      return backendCritical && hasRealReason
    })
    .map((m) => {
      const raw = full.medicines.find((r) => r.medicine_name === m.name)
      // Pick the most clinically meaningful reason to surface
      const seriousEffect = (raw?.serious_side_effects ?? []).find(
        (s) => s.trim().toLowerCase() !== 'none' && s.trim() !== ''
      )
      const contraindication = (raw?.contraindications ?? []).find(
        (c) => c.trim().toLowerCase() !== 'none' && c.trim() !== ''
      )
      const reason =
        seriousEffect ||
        (m.drowsinessLevel === 'severe' ? 'Severe drowsiness — do not drive or operate machinery' : null) ||
        contraindication ||
        'Critical safety profile — consult your doctor or pharmacist'
      return `${m.name}: ${reason}`
    })

  return {
    id: full.prescription_id,
    prescription_id: full.prescription_id,
    patientAge: full.patient_age ?? undefined,
    rawText: full.medicines.map((m) => m.medicine_name).join(', '),
    extractedMedicines: medicines,
    overallWarnings,
    criticalAlerts,
    analysisTimestamp: new Date().toISOString(),
    confidence: 0.85,
    provider_used: full.provider_used,
    overall_severity: full.overall_severity,
    overall_drowsiness_warning: full.overall_drowsiness_warning,
    overall_dosage_concern: full.overall_dosage_concern,
  }
}

export async function mockAnalyzePrescription(
  _request: Record<string, unknown>
): Promise<{ success: boolean; data?: PrescriptionAnalysis; error?: string }> {
  await new Promise((r) => setTimeout(r, 2600))
  const { MOCK_ANALYSIS } = await import('./mockData')
  return { success: true, data: MOCK_ANALYSIS }
}

export default apiClient
