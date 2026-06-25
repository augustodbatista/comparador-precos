# App Mobile - Comparador de Precos

Aplicacao mobile hibrida em Ionic React + Capacitor. O site web original continua em `../frontend`; esta pasta contem somente o app mobile e o projeto Android.

## Stack

- React 18 + TypeScript + Vite
- Ionic React
- Capacitor
- Android
- Scanner web com `html5-qrcode`

## Comandos

```bash
npm install
npm run ionic:serve
npm run build
npm run test:run
npm run android
npm run cap:open:android
```

## Android

Gerar APK debug:

```bash
cd android
.\gradlew.bat assembleDebug
```

APK gerado em:

```text
android/app/build/outputs/apk/debug/app-debug.apk
```

## API

O app usa `VITE_API_URL` quando definido. Sem essa variavel, usa:

```text
https://comparador-precos-yiqd.onrender.com
```

Para testar no emulador Android com o backend local rodando no PC, crie `mobile/.env.local`:

```text
VITE_API_URL=http://10.0.2.2:8000
```

Para testar em celular fisico na mesma rede, use o IP do computador:

```text
VITE_API_URL=http://SEU_IP_DA_REDE:8000
```

Para o WebView do Capacitor chamar o backend, o backend precisa aceitar:

```text
capacitor://localhost
```

As requisicoes do app Android usam `CapacitorHttp`, evitando bloqueios de CORS do WebView.

## Validacao Atual

Validado com:

```bash
npm run build
npm run test:run -- --reporter=dot
npm run android
cd android
.\gradlew.bat assembleDebug
```

Resultado: build web OK, 27 testes OK, `cap sync android` OK e APK debug gerado com sucesso.

Tambem validado em emulador Android com `adb`: app instalado e aberto, chamadas nativas `CapacitorHttp` retornando HTTP 200 para `/products`, `/receipts`, `/prices/latest`, `/prices/lowest` e `/prices/history`.
