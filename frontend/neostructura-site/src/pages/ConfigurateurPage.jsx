import { useState, useEffect } from 'react'
import { Helmet } from 'react-helmet-async'
import Reveal from '../components/Reveal'
import StepIndicator from '../components/configurator/StepIndicator'
import StepMetiers from '../components/configurator/StepMetiers'
import StepMaterials from '../components/configurator/StepMaterials'
import StepIntervention from '../components/configurator/StepIntervention'
import StepBuilding from '../components/configurator/StepBuilding'
import StepContact from '../components/configurator/StepContact'
import StepResult from '../components/configurator/StepResult'
import { submitConfigurator, fetchConfiguratorOptions } from '../api/configurator'

export default function ConfigurateurPage() {
  const [step, setStep] = useState(1)
  const [metiers, setMetiers] = useState([])
  const [materials, setMaterials] = useState({})
  const [qualityLevel, setQualityLevel] = useState('standard')
  const [intervention, setIntervention] = useState('')
  const [urgency, setUrgency] = useState('normal')
  const [building, setBuilding] = useState({})
  const [contact, setContact] = useState({})
  const [notes, setNotes] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const [options, setOptions] = useState(null)
  const [optionsLoading, setOptionsLoading] = useState(true)

  const next = () => setStep(s => Math.min(s + 1, 5))
  const back = () => setStep(s => Math.max(s - 1, 1))

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [step, result])

  useEffect(() => {
    fetchConfiguratorOptions()
      .then(setOptions)
      .catch(() => {})
      .finally(() => setOptionsLoading(false))
  }, [])

  const handleSubmit = async () => {
    setSubmitting(true)
    setError('')
    try {
      const data = await submitConfigurator({ metiers, materials, quality_level: qualityLevel, intervention, urgency, building, contact, notes })
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <Helmet><title>Configurateur — NÉOSTRUCTURA</title></Helmet>

      <section style={{ paddingTop: 'calc(var(--header-h) + 56px)', paddingBottom: 96, minHeight: '90vh' }}>
        <div className="neo-container" style={{ maxWidth: 780 }}>
          {!result && (
            <Reveal style={{ marginBottom: 40 }}>
              <div className="neo-eyebrow">Configurateur</div>
              <h1 style={{ fontSize: 'clamp(26px, 3.6vw, 38px)' }}>Configurez votre projet.</h1>
            </Reveal>
          )}

          {!result && <StepIndicator step={step} />}

          <Reveal key={result ? 'result' : step} className="neo-card" style={{ padding: 44 }}>
            {result ? (
              <StepResult result={result} />
            ) : step === 1 ? (
              <StepMetiers value={metiers} onChange={setMetiers} onNext={next} />
            ) : step === 2 ? (
              <StepMaterials
                metiers={metiers} materials={materials} onChange={setMaterials}
                qualityLevel={qualityLevel} onChangeQuality={setQualityLevel}
                options={options} loading={optionsLoading}
                onNext={next} onBack={back}
              />
            ) : step === 3 ? (
              <StepIntervention
                intervention={intervention} urgency={urgency}
                onChangeIntervention={setIntervention} onChangeUrgency={setUrgency}
                onNext={next} onBack={back}
              />
            ) : step === 4 ? (
              <StepBuilding building={building} onChange={setBuilding} onNext={next} onBack={back} />
            ) : (
              <StepContact
                contact={contact} notes={notes}
                onChangeContact={setContact} onChangeNotes={setNotes}
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
