import { useEffect } from 'react'
import MakeupLayout         from '../layouts/MakeupLayout'
import MakeupHero           from '../components/makeup/MakeupHero'
import MakeupTrustBand      from '../components/makeup/MakeupTrustBand'
import MakeupBestSellers    from '../components/makeup/MakeupBestSellers'
import MakeupDarkCollection from '../components/makeup/MakeupDarkCollection'
import MakeupCategories     from '../components/makeup/MakeupCategories'
import MakeupInstagram      from '../components/makeup/MakeupInstagram'
import MakeupNewsletter     from '../components/makeup/MakeupNewsletter'

export default function MakeupHome() {
  useEffect(() => {
    document.title = "LUNEA Maquillage — L'art du maquillage premium"
    let desc = document.querySelector('meta[name="description"]')
    if (!desc) {
      desc = document.createElement('meta')
      desc.name = 'description'
      document.head.appendChild(desc)
    }
    desc.content = "Découvrez LUNEA Maquillage, un univers beauté haut de gamme : teint, lèvres, yeux et accessoires dans une esthétique luxe, lumineuse et moderne."
    return () => { document.title = 'SIÈCLE' }
  }, [])

  return (
    <MakeupLayout>
      <MakeupHero />
      <MakeupTrustBand />
      <MakeupBestSellers />
      <MakeupDarkCollection />
      <MakeupCategories />
      <MakeupInstagram />
      <MakeupNewsletter />
    </MakeupLayout>
  )
}
