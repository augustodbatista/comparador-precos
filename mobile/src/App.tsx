import {
  IonApp,
  IonIcon,
  IonLabel,
  IonRouterOutlet,
  IonTabBar,
  IonTabButton,
  IonTabs,
  setupIonicReact,
} from '@ionic/react'
import { IonReactRouter } from '@ionic/react-router'
import { Redirect, Route } from 'react-router-dom'
import { pricetagOutline, qrCodeOutline, receiptOutline } from 'ionicons/icons'
import { QrReader } from './components/QrReader'
import { PriceConsultation } from './components/PriceConsultation'
import { ReceiptHistory } from './components/ReceiptHistory'

setupIonicReact()

export default function App() {
  return (
    <IonApp>
      <IonReactRouter>
        <IonTabs>
          <IonRouterOutlet>
            <Route exact path="/scanner" component={QrReader} />
            <Route exact path="/prices" component={PriceConsultation} />
            <Route exact path="/history" component={ReceiptHistory} />
            <Route exact path="/">
              <Redirect to="/scanner" />
            </Route>
          </IonRouterOutlet>

          <IonTabBar slot="bottom">
            <IonTabButton tab="scanner" href="/scanner" aria-label="Scanner">
              <IonIcon icon={qrCodeOutline} />
              <IonLabel>Scanner</IonLabel>
            </IonTabButton>
            <IonTabButton tab="prices" href="/prices" aria-label="Preços">
              <IonIcon icon={pricetagOutline} />
              <IonLabel>Preços</IonLabel>
            </IonTabButton>
            <IonTabButton tab="history" href="/history" aria-label="Histórico">
              <IonIcon icon={receiptOutline} />
              <IonLabel>Histórico</IonLabel>
            </IonTabButton>
          </IonTabBar>
        </IonTabs>
      </IonReactRouter>
    </IonApp>
  )
}
