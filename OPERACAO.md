# Guia de Operação — Comparador de Preços NFC-e

---

## 1. O que é cada peça e onde roda

| Componente | Onde roda | Sobe automático? |
|---|---|---|
| **Frontend** (app no celular/browser) | Vercel (nuvem) | ✅ Sim — ao fazer push no GitHub |
| **Backend** (API que busca os cupons) | Render (nuvem) | ✅ Sim — ao fazer push no GitHub |
| **Banco de dados** | MongoDB Atlas (nuvem) | ✅ Sim — sempre ligado |
| **Ollama** (IA que normaliza os nomes) | Sua máquina | ❌ Não — precisa abrir manualmente |
| **ngrok** (túnel para o Ollama) | Sua máquina | ❌ Não — precisa abrir manualmente |

> **Resumo:** A nuvem cuida de si mesma. Você só precisa se preocupar com Ollama e ngrok na sua máquina.

---

## 2. Setup único — fazer só uma vez

Essas etapas só precisam ser feitas na primeira vez ou se formatar a máquina.

### 2.0 Verificar o que já está instalado

Antes de instalar qualquer coisa, rode esses comandos no PowerShell para ver o que já existe:

```powershell
python --version
```
Deve aparecer `Python 3.11.x`. Se não aparecer, siga o passo 2.1.

```powershell
node --version
```
Deve aparecer `v18.x.x` ou superior. Se não aparecer, siga o passo 2.2.

```powershell
ollama list
```
Deve listar os modelos instalados, incluindo `qwen2.5:7b`. Se der erro, siga o passo 2.3.

```powershell
[System.Environment]::GetEnvironmentVariable("OLLAMA_ORIGINS", "User")
```
Deve aparecer `*`. Se estiver vazio, siga o passo 2.4.

```powershell
ngrok version
```
Deve aparecer a versão do ngrok. Se der erro, siga o passo 2.5.



### 2.1 Instalar o Python 3.11

1. Acesse https://www.python.org/downloads/release/python-3119/
2. Baixe o instalador Windows 64-bit
3. Marque a opção **"Add Python to PATH"** antes de instalar
4. Conclua a instalação

Verificar se funcionou — abra o PowerShell e digite:
```powershell
python --version
```
Deve aparecer `Python 3.11.x`.

### 2.2 Instalar o Node.js 18

1. Acesse https://nodejs.org/en/download
2. Baixe a versão **LTS**
3. Instale com as opções padrão

Verificar:
```powershell
node --version
```
Deve aparecer `v18.x.x` ou superior.

### 2.3 Instalar o Ollama e baixar o modelo

1. Acesse https://ollama.com/download e baixe a versão Windows
2. Instale com as opções padrão — o Ollama vai aparecer na bandeja do sistema
3. Abra um PowerShell e baixe o modelo de IA (isso pode demorar, o arquivo tem ~4GB):

```powershell
ollama pull qwen2.5:7b
```

Aguarde finalizar antes de continuar.

### 2.4 Configurar o Ollama para aceitar conexões externas

O Ollama por padrão só aceita requests da própria máquina. Para o Render conseguir falar com ele via ngrok, é preciso liberar:

```powershell
[System.Environment]::SetEnvironmentVariable("OLLAMA_ORIGINS", "*", "User")
```

Depois disso:
1. Clique com o botão direito no ícone do Ollama na bandeja do sistema (canto inferior direito)
2. Clique em **Quit**
3. Abra o Ollama novamente pelo menu Iniciar

Essa configuração é permanente — não precisa repetir.

### 2.5 Instalar o ngrok

1. Crie uma conta gratuita em https://ngrok.com
2. Acesse https://ngrok.com/download e baixe a versão Windows
3. Extraia o arquivo — você vai receber um executável `ngrok.exe`
4. Mova o `ngrok.exe` para `C:\Windows\System32\` (para poder chamar de qualquer pasta)
5. No painel do ngrok (https://dashboard.ngrok.com), vá em **Your Authtoken** e copie o token
6. No PowerShell, configure o token:

```powershell
ngrok config add-authtoken SEU_TOKEN_AQUI
```

### 2.6 Configurar as variáveis no Render

1. Acesse https://dashboard.render.com
2. Clique no serviço **comparador-precos-api**
3. Vá em **Environment**
4. Confirme que essas variáveis estão preenchidas:

| Variável | Valor |
|---|---|
| `MONGODB_URL` | `mongodb+srv://usuario:senha@cluster.mongodb.net/...` |
| `DB_NAME` | `consult-price` |
| `OLLAMA_URL` | (preencher depois — veja Seção 3) |

---

## 3. O que fazer toda vez que for usar

Toda vez que quiser escanear cupons, siga essa ordem:

### Passo 1 — Verificar se o Ollama está rodando

Olhe na bandeja do sistema (canto inferior direito da tela). Se o ícone do Ollama aparecer, ele está rodando.

Se não estiver: abra o Ollama pelo menu Iniciar.

### Passo 2 — Abrir o ngrok

Abra um PowerShell (pode ser qualquer pasta) e rode:

```powershell
ngrok http 11434
```

Vai aparecer uma tela assim:
```
Forwarding  https://xxxx-xxx-xxx.ngrok-free.app -> http://localhost:11434
```

**Copie a URL** que aparece na linha "Forwarding" (começa com `https://`).

> Deixe essa janela aberta. Se fechar o ngrok, o túnel cai.

### Passo 3 — Verificar se a URL do ngrok mudou

A URL do ngrok muda toda vez que o ngrok é reiniciado. Compare a URL atual com a que está no Render.

**Para ver a URL atual no Render:**
1. Acesse https://dashboard.render.com
2. Clique no serviço **comparador-precos-api**
3. Vá em **Environment**
4. Veja o valor de `OLLAMA_URL`

**Se a URL for diferente da que o ngrok mostrou:**
1. Clique em `OLLAMA_URL` no Render
2. Substitua pelo novo valor (ex: `https://nova-url.ngrok-free.app`)
3. Clique em **Save Changes**
4. O Render vai reiniciar o backend automaticamente — aguarde ~1 minuto

**Se a URL for igual:** pode continuar, não precisa fazer nada.

### Passo 4 — Usar o app

Abra no celular ou no navegador:

```
https://comparador-precos-xi.vercel.app
```

Escaneie o QR Code do cupom e clique em **Salvar**. O nome dos produtos vai aparecer normalizado (ex: `Refrigerante Coca-Cola 2l` em vez de `REFRI COCA COLA PET 2L`).

---

## 4. Deploy — quando mudar o código

Quando você ou o Claude fizer mudanças no código e quiser publicar:

```powershell
cd C:\comparador-precos
git push origin master
```

Isso é suficiente. O Render e o Vercel detectam o push e deployam automaticamente em ~2-3 minutos.

Você pode acompanhar o progresso em:
- Render: https://dashboard.render.com → comparador-precos-api → **Logs**
- Vercel: https://vercel.com/dashboard → comparador-precos → último deploy

---

## 5. Scripts de manutenção

Esses scripts são usados quando algo deu errado (cupons salvos sem normalização, por exemplo).

### Quando usar: cupons salvos com nomes em maiúsculo

Se você salvou cupons enquanto o Ollama estava desligado ou o ngrok estava fora, os produtos ficam com o nome cru (ex: `CAFE 3 CORACOES 500G TRAD.`).

**Como corrigir:**

1. Certifique-se de que o Ollama está rodando (Passo 1 da Seção 3)
2. Abra o PowerShell e navegue até a pasta do backend:

```powershell
cd C:\comparador-precos\backend
```

3. Rode o script de renormalização:

```powershell
$env:PYTHONIOENCODING="utf-8"; python scripts/renormalize_prices.py
```

4. Aguarde finalizar (pode levar alguns minutos dependendo da quantidade de produtos)
5. Reconstrua o catálogo de produtos:

```powershell
$env:PYTHONIOENCODING="utf-8"; python -c "
import asyncio, os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
load_dotenv()
async def main():
    client = AsyncIOMotorClient(os.getenv('MONGODB_URL'))
    db = client[os.getenv('DB_NAME', 'comparador_precos')]
    ids = await db['prices'].distinct('product_id')
    await db['products'].drop()
    now = datetime.now(timezone.utc)
    await db['products'].insert_many([{'normalized_name': i, 'created_at': now} for i in ids])
    await db['products'].create_index('normalized_name', unique=True)
    print(f'{len(ids)} produtos no catalogo')
    client.close()
asyncio.run(main())
"
```

---

## 6. Problemas comuns

### "O cupom foi salvo mas o nome do produto está em maiúsculo"

O Ollama não estava acessível quando o cupom foi salvo (ngrok fora, URL desatualizada, ou Ollama desligado). Siga os passos da Seção 5.

### "O ngrok mudou de URL e o Render ainda não foi atualizado"

Vá ao painel do Render → Environment → atualize `OLLAMA_URL` com a nova URL do ngrok. Aguarde ~1 minuto para o restart.

### "O backend está respondendo mas não está salvando"

Verifique os logs do Render (Dashboard → comparador-precos-api → Logs). Erros de MongoDB geralmente indicam problema na `MONGODB_URL`.

### "O Ollama não responde"

Abra o browser e acesse `http://localhost:11434`. Se carregar, está funcionando. Se não, abra o Ollama pelo menu Iniciar e aguarde alguns segundos.

### "O ngrok aparece mas retorna 403 Forbidden"

Verifique se a variável `OLLAMA_ORIGINS` está configurada. Abra o PowerShell e rode:

```powershell
[System.Environment]::GetEnvironmentVariable("OLLAMA_ORIGINS", "User")
```

Deve aparecer `*`. Se estiver vazio, rode novamente:

```powershell
[System.Environment]::SetEnvironmentVariable("OLLAMA_ORIGINS", "*", "User")
```

Depois reinicie o Ollama pelo ícone na bandeja.

---

## Resumo rápido para uso diário

```
1. Ollama rodando? (ícone na bandeja)
2. ngrok rodando? → ngrok http 11434
3. URL do ngrok mudou? → atualizar OLLAMA_URL no Render
4. Abrir o app → escanear → salvar
```
