// Placeholder for React Three Fiber 3D preview.
// Falls back to AtelierWatchSvgPreview in all current builds.
// Requires: @react-three/fiber, @react-three/drei, three
import AtelierWatchSvgPreview from './AtelierWatchSvgPreview'

export default function AtelierWatch3DPreview({ configuration, viewMode }) {
  return <AtelierWatchSvgPreview configuration={configuration} viewMode={viewMode} />
}
