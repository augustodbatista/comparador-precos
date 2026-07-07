import { Suspense, lazy } from 'react'
import {
  IonApp,
  IonCard,
  IonCardContent,
  IonIcon,
  IonLabel,
  IonRouterOutlet,
  IonSkeletonText,
  IonTabBar,
  IonTabButton,
  IonTabs,
  setupIonicReact,
} from '@ionic/react'
import { IonReactRouter } from '@ionic/react-router'
import { Redirect, Route } from 'react-router-dom'
import { pricetagOutline, qrCodeOutline, receiptOutline } from 'ionicons/icons'

const QrReader = lazy(() => import('./components/QrReader').then((module) => ({ default: module.QrReader })))
const PriceConsultation = lazy(() =>
  import('./components/PriceConsultation').then((module) => ({ default: module.PriceConsultation })),
)
const ReceiptHistory = lazy(() =>
  import('./components/ReceiptHistory').then((module) => ({ default: module.ReceiptHistory })),
)

setupIonicReact()

function PageFallback() {
  return (
    <IonCard className="loading-card" data-testid="route-loader">
      <IonCardContent>
        <IonSkeletonText animated className="skeleton-title" />
        <IonSkeletonText animated />
        <IonSkeletonText animated />
      </IonCardContent>
    </IonCard>
  )
}

export default function App() {
  return (
    <IonApp>
      <IonReactRouter>
        <IonTabs>
          <IonRouterOutlet>
            <Suspense fallback={<PageFallback />}>
              <Route exact path="/scanner" component={QrReader} />
              <Route exact path="/prices" component={PriceConsultation} />
              <Route exact path="/history" component={ReceiptHistory} />
            </Suspense>
            <Route exact path="/">
              <Redirect to="/scanner" />
            </Route>
          </IonRouterOutlet>

          <IonTabBar slot="bottom">
            <IonTabButton tab="scanner" href="/scanner" aria-label="Scanner">
              <IonIcon icon={qrCodeOutline} />
              <IonLabel>Scanner</IonLabel>
            </IonTabButton>
            <IonTabButton tab="prices" href="/prices" aria-label="Precos">
              <IonIcon icon={pricetagOutline} />
              <IonLabel>Precos</IonLabel>
            </IonTabButton>
            <IonTabButton tab="history" href="/history" aria-label="Historico">
              <IonIcon icon={receiptOutline} />
              <IonLabel>Historico</IonLabel>
            </IonTabButton>
          </IonTabBar>
        </IonTabs>
      </IonReactRouter>
    </IonApp>
  )
}
