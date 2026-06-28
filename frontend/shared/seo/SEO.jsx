import { Helmet } from 'react-helmet-async'

export default function SEO({
  title,
  description,
  image,
  canonicalUrl,
  noindex = false,
  brand = 'siecle',
}) {
  const brandName = brand === 'lunea' ? 'LUNEA' : 'SIÈCLE'
  const fullTitle = title ? `${title} — ${brandName}` : brandName

  return (
    <Helmet>
      <title>{fullTitle}</title>
      {description && <meta name="description" content={description} />}
      {noindex && <meta name="robots" content="noindex,nofollow" />}
      {canonicalUrl && <link rel="canonical" href={canonicalUrl} />}

      {/* Open Graph */}
      <meta property="og:title" content={fullTitle} />
      {description && <meta property="og:description" content={description} />}
      {image && <meta property="og:image" content={image} />}
      <meta property="og:type" content="website" />

      {/* Twitter */}
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:title" content={fullTitle} />
      {description && <meta name="twitter:description" content={description} />}
      {image && <meta name="twitter:image" content={image} />}
    </Helmet>
  )
}
