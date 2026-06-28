import AtelierWatchSvgPreview from './AtelierWatchSvgPreview'

export default function AtelierWatchPreview({ configuration, viewMode }) {
  return (
    <div className={`atelier-watch-preview atelier-watch-view-${viewMode}`}>
      <AtelierWatchSvgPreview configuration={configuration} viewMode={viewMode} />
    </div>
  )
}
