import { Suspense, lazy, useEffect, useState } from 'react'
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
import { logOutOutline, pricetagOutline, qrCodeOutline, receiptOutline } from 'ionicons/icons'
import { API_URL } from './config/api'
import { Auth } from './components/Auth'
import { clearToken, getToken, setUnauthorizedHandler, warmUpApi } from './services/apiClient'

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
  const [authToken, setAuthToken] = useState(() => getToken())

  useEffect(() => {
    void warmUpApi(API_URL)
    setUnauthorizedHandler(() => setAuthToken(null))
    return () => setUnauthorizedHandler(null)
  }, [])

  function handleLogout() {
    clearToken()
    setAuthToken(null)
  }

  if (!authToken) {
    return (
      <IonApp>
        <Auth onAuthenticated={setAuthToken} />
      </IonApp>
    )
  }

  return (
    <IonApp>
      <IonReactRouter>
        <IonTabs>
          <IonRouterOutlet>
            <Suspense fallback={<PageFallback />}>
              <Route exact path="/scanner" component={QrReader} />
              <Route exact path="/prices" component={PriceConsultation} />
              <Route exact path="/history" component={ReceiptHistory} />
              <Route exact path="/logout">
                <Redirect to="/scanner" />
              </Route>
            </Suspense>
            <Route exact path="/">
              <Redirect to="/scanner" />
            </Route>
          </IonRouterOutlet>

          <IonTabBar slot="bottom" className="app-tab-bar">
            <IonTabButton tab="scanner" href="/scanner" aria-label="Scanner">
              <IonIcon icon={qrCodeOutline} />
              <IonLabel>Scanner</IonLabel>
            </IonTabButton>
            <IonTabButton tab="prices" href="/prices" aria-label="Preços">
              <IonIcon icon={pricetagOutline} />
              <IonLabel>Preços</IonLabel>
            </IonTabButton>
            <IonTabButton tab="history" href="/history" aria-label="Historico">
              <IonIcon icon={receiptOutline} />
              <IonLabel>Historico</IonLabel>
            </IonTabButton>
            <IonTabButton tab="logout" href="/logout" onClick={handleLogout} aria-label="Sair">
              <IonIcon icon={logOutOutline} />
              <IonLabel>Sair</IonLabel>
            </IonTabButton>
          </IonTabBar>
        </IonTabs>
      </IonReactRouter>
    </IonApp>
  )
}
