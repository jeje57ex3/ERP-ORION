import { useState, useEffect, useRef } from 'react'
import { Helmet } from 'react-helmet-async'
import Reveal from '../components/Reveal'
import { useLanguage } from '../i18n/LanguageContext'
import StepIndicator from '../components/configurator/StepIndicator'
import StepDomain from '../components/configurator/StepDomain'
import StepService from '../components/configurator/StepService'
import StepQuestions from '../components/configurator/StepQuestions'
import StepContact from '../components/configurator/StepContact'
import StepResult from '../components/configurator/StepResult'
import {
  fetchDomains, fetchServices, fetchQuestions, estimateLive, submitConfigurator,
  startSession, fetchSession, updateSession, addSessionLot, submitConfiguratorProject,
} from '../api/configurator'

const SESSION_STORAGE_KEY = 'neostructura_configurator_session'

function isAnswered(q, answers) {
  const v = answers[q.identifier]
  if (!q.required) return true
  if (Array.isArray(v)) return v.length > 0
  return v !== undefined && v !== '' && v !== null
}

export default function ConfigurateurPage() {
  const { dict } = useLanguage()
  const cfg = dict.configurator
  const [step, setStep] = useState(1)

  const [domains, setDomains] = useState([])
  const [domainsLoading, setDomainsLoading] = useState(true)
  const [domainCode, setDomainCode] = useState('')

  const [services, setServices] = useState([])
  const [servicesLoading, setServicesLoading] = useState(false)
  const [serviceCode, setServiceCode] = useState('')

  const [questions, setQuestions] = useState([])
  const [questionsLoading, setQuestionsLoading] = useState(false)
  const [answers, setAnswers] = useState({})
  const [urgency, setUrgency] = useState('normal')

  const [liveEstimate, setLiveEstimate] = useState(null)
  const [estimateLoading, setEstimateLoading] = useState(false)

  const [contact, setContact] = useState({})
  const [building, setBuilding] = useState({})
  const [notes, setNotes] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)

  const [sessionKey, setSessionKey] = useState(null)
  const [projectMode, setProjectMode] = useState(false)
  const [lots, setLots] = useState([])
  const debounceRef = useRef(null)
  const sessionDebounceRef = useRef(null)

  const next = () => setStep(s => Math.min(s + 1, 4))
  const back = () => setStep(s => Math.max(s - 1, 1))

  useEffect(() => { window.scrollTo({ top: 0, behavior: 'smooth' }) }, [step, result])

  // Étape 1 : domaines
  useEffect(() => {
    fetchDomains().then(setDomains).catch(() => {}).finally(() => setDomainsLoading(false))
  }, [])

  // Dossier de configuration résumable (§4/§50) : reprend une session en
  // cours si elle existe encore côté navigateur, sinon en crée une nouvelle.
  // Ne bloque jamais le parcours si l'appel échoue (best-effort).
  useEffect(() => {
    const stored = window.localStorage?.getItem(SESSION_STORAGE_KEY)
    const resume = async () => {
      if (stored) {
        const state = await fetchSession(stored).catch(() => null)
        if (state && state.status === 'in_progress' && (state.domain_code || Object.keys(state.answers || {}).length || (state.lots || []).length)) {
          setSessionKey(stored)
          if (state.lots?.length) { setLots(state.lots); setProjectMode(true) }
          if (state.answers) setAnswers(state.answers)
          if (state.urgency) setUrgency(state.urgency)
          if (state.domain_code) {
            setDomainCode(state.domain_code)
            setServicesLoading(true)
            const svcs = await fetchServices(state.domain_code).catch(() => [])
            setServices(svcs)
            setServicesLoading(false)
            setStep(2)
          }
          if (state.service_code) {
            setServiceCode(state.service_code)
            setQuestionsLoading(true)
            const qs = await fetchQuestions(state.service_code, state.answers || {}).catch(() => [])
            setQuestions(qs)
            setQuestionsLoading(false)
            setStep(3)
          }
          return
        }
      }
      const started = await startSession().catch(() => null)
      if (started?.session_key) {
        setSessionKey(started.session_key)
        window.localStorage?.setItem(SESSION_STORAGE_KEY, started.session_key)
      }
    }
    resume()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Persiste l'état courant côté serveur pour permettre une reprise —
  // best-effort, débouncé pour ne pas spammer l'API à chaque frappe.
  useEffect(() => {
    if (!sessionKey) return
    if (sessionDebounceRef.current) clearTimeout(sessionDebounceRef.current)
    sessionDebounceRef.current = setTimeout(() => {
      updateSession(sessionKey, { domain_code: domainCode || undefined, service_code: serviceCode || undefined, urgency, answers }).catch(() => {})
    }, 600)
    return () => clearTimeout(sessionDebounceRef.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionKey, domainCode, serviceCode, urgency, answers])

  const selectDomain = (code) => {
    setDomainCode(code)
    setServiceCode('')
    setServicesLoading(true)
    fetchServices(code).then(setServices).catch(() => {}).finally(() => setServicesLoading(false))
    next()
  }

  const selectService = (code) => {
    setServiceCode(code)
    setAnswers({})
    setLiveEstimate(null)
    setQuestionsLoading(true)
    fetchQuestions(code, {}).then(setQuestions).catch(() => {}).finally(() => setQuestionsLoading(false))
    next()
  }

  // Réponses -> re-résout les questions visibles (parcours adaptatif) et,
  // une fois les questions obligatoires renseignées, l'estimation live.
  const setAnswer = (identifier, value) => {
    setAnswers(prev => ({ ...prev, [identifier]: value }))
  }

  useEffect(() => {
    if (step !== 3 || !serviceCode) return
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      fetchQuestions(serviceCode, answers).then(setQuestions).catch(() => {})
    }, 350)
    return () => clearTimeout(debounceRef.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [answers, serviceCode, step])

  useEffect(() => {
    if (step !== 3 || !serviceCode || questions.length === 0) return
    if (!questions.every(q => isAnswered(q, answers))) { setLiveEstimate(null); return }
    const handle = setTimeout(() => {
      setEstimateLoading(true)
      estimateLive({ service_code: serviceCode, answers, urgency })
        .then(setLiveEstimate).catch(() => {}).finally(() => setEstimateLoading(false))
    }, 400)
    return () => clearTimeout(handle)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [answers, questions, urgency, serviceCode, step])

  // Dossier « mode projet » (§12-14) : ajoute le besoin en cours comme lot
  // du dossier, puis repart de zéro pour en décrire un autre. Une fois un
  // dossier entamé, "Continuer" ajoute aussi le dernier besoin comme lot
  // avant de passer aux coordonnées (au lieu de la soumission simple).
  const commitCurrentAsLot = async () => {
    if (!sessionKey || !serviceCode) return
    const data = await addSessionLot(sessionKey, {
      domain_code: domainCode, service_code: serviceCode, urgency, answers,
      label: service?.name || serviceCode,
    })
    setLots(data.lots)
  }

  const handleAddAnother = async () => {
    await commitCurrentAsLot()
    setProjectMode(true)
    setServiceCode('')
    setAnswers({})
    setQuestions([])
    setLiveEstimate(null)
    setStep(1)
  }

  const handleQuestionsContinue = async () => {
    if (projectMode) await commitCurrentAsLot()
    next()
  }

  const handleSubmit = async () => {
    setSubmitting(true)
    setError('')
    try {
      if (projectMode) {
        const data = await submitConfiguratorProject({ session_key: sessionKey, contact, building, notes })
        setResult({ isProject: true, references: data.references, project: data.project })
      } else {
        const data = await submitConfigurator({
          service_code: serviceCode, urgency, answers, contact, building, notes,
          session_key: sessionKey || undefined,
        })
        setResult(data)
      }
      window.localStorage?.removeItem(SESSION_STORAGE_KEY)
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  const domain = domains.find(d => d.code === domainCode)
  const service = services.find(s => s.code === serviceCode)

  return (
    <>
      <Helmet><title>{cfg.pageTitle}</title></Helmet>

      <section style={{ paddingTop: 'calc(var(--header-h) + 56px)', paddingBottom: 96, minHeight: '90vh' }}>
        <div className="neo-container" style={{ maxWidth: 780 }}>
          {!result && (
            <Reveal style={{ marginBottom: 40 }}>
              <div className="neo-eyebrow">{cfg.eyebrow}</div>
              <h1 style={{ fontSize: 'clamp(26px, 3.6vw, 38px)' }}>{cfg.h1}</h1>
            </Reveal>
          )}

          {!result && <StepIndicator step={step} />}

          {!result && lots.length > 0 && (
            <div className="neo-badge" style={{ marginBottom: 16 }}>
              {cfg.lotsBanner(lots.length)}
            </div>
          )}

          <Reveal key={result ? 'result' : step} className="neo-card" style={{ padding: 44 }}>
            {result ? (
              <StepResult result={result} />
            ) : step === 1 ? (
              <StepDomain domains={domains} loading={domainsLoading} value={domainCode} onSelect={selectDomain} />
            ) : step === 2 ? (
              <StepService
                domain={domain} services={services} loading={servicesLoading}
                value={serviceCode} onSelect={selectService} onBack={back}
              />
            ) : step === 3 ? (
              <StepQuestions
                service={service} questions={questions} loadingQuestions={questionsLoading}
                answers={answers} onAnswerChange={setAnswer}
                urgency={urgency} onUrgencyChange={setUrgency}
                liveEstimate={liveEstimate} estimateLoading={estimateLoading}
                onNext={handleQuestionsContinue} onBack={back} onAddAnother={handleAddAnother}
              />
            ) : (
              <StepContact
                contact={contact} building={building} notes={notes}
                onChangeContact={setContact} onChangeBuilding={setBuilding} onChangeNotes={setNotes}
                onSubmit={handleSubmit} onBack={back}
                submitting={submitting} error={error}
              />
            )}
          </Reveal>
        </div>
      </section>
    </>
  )
}
