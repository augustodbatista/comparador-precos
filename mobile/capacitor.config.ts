import type { CapacitorConfig } from '@capacitor/cli'

const config: CapacitorConfig = {
  appId: 'br.com.jpcdo00.comparadorprecos',
  appName: 'Comparador de Preços NFC-e',
  webDir: 'dist',
  plugins: {
    CapacitorHttp: {
      enabled: true,
    },
  },
}

export default config
