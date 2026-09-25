#!/usr/bin/env bash
# Verifica se a demo publicada está no ar e alcançando o banco.
#
# Por que login com uma conta inexistente: para responder 401 ("e-mail ou
# senha inválidos"), o backend precisa consultar o MongoDB. Então 401 prova as
# três coisas de uma vez -- Render no ar, app de pé e banco alcançável -- sem
# gravar nada. De quebra, a consulta conta como atividade no cluster gratuito
# do Atlas, que é pausado quando fica tempo demais sem conexões (foi isso que
# derrubou a demo em set/2026).
#
# Uso: verificar-demo.sh [URL_DO_BACKEND] [URL_DO_FRONTEND]
set -u

BACKEND="${1:-https://comparador-precos-yiqd.onrender.com}"
FRONTEND="${2:-https://comparador-precos-xi.vercel.app}"
# O plano gratuito do Render adormece o serviço; acordar pode levar ~1 minuto.
TENTATIVAS="${TENTATIVAS:-6}"
ESPERA="${ESPERA:-20}"

status=000
for i in $(seq 1 "$TENTATIVAS"); do
  status=$(curl -s -o /dev/null -w '%{http_code}' --max-time 60 \
    -X POST -H 'Content-Type: application/json' \
    --data '{"email":"verificacao-semanal@example.com","password":"verificacao-semanal"}' \
    "$BACKEND/auth/login")
  case "$status" in
    401)
      echo "backend ok: consultou o banco e recusou a conta inexistente (HTTP 401)"
      break
      ;;
    503)
      echo "::error::Backend no ar, mas o banco está indisponível (HTTP 503). Confira no MongoDB Atlas se o cluster foi pausado, e a MONGODB_URL no Render."
      exit 1
      ;;
    *)
      echo "tentativa $i/$TENTATIVAS: HTTP $status (o Render pode estar acordando)"
      if [ "$i" -lt "$TENTATIVAS" ]; then sleep "$ESPERA"; fi
      ;;
  esac
done

if [ "$status" != "401" ]; then
  echo "::error::O backend não respondeu como esperado após $TENTATIVAS tentativas (último HTTP $status). Confira os logs do serviço no Render."
  exit 1
fi

status=$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 "$FRONTEND")
if [ "$status" != "200" ]; then
  echo "::error::O frontend respondeu HTTP $status. Confira o deploy na Vercel."
  exit 1
fi
echo "frontend ok (HTTP 200)"
