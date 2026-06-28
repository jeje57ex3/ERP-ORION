import { useEffect } from 'react'
import SiecleAtelierLayout from '../layouts/SiecleAtelierLayout'
import WatchAtelierExperience from '../components/watches/atelier/WatchAtelierExperience'
import '../styles/siecle-watch-atelier.css'

export default function WatchAtelierPage() {
  useEffect(() => {
    document.title = 'Atelier SIÈCLE — Composez votre montre signature'
    return () => { document.title = 'SIÈCLE' }
  }, [])

  return (
    <SiecleAtelierLayout>
      <WatchAtelierExperience />
    </SiecleAtelierLayout>
  )
}
