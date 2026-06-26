# Roadmap de Features — Comparador de Preços NFC-e

Ordenado do mais simples ao mais complexo. Cada feature lista o que precisa ser feito no
backend, no frontend, e o esforço estimado.

---

## Fase 1 — Sem novas dependências (dados já existem)

### F1 · Preço por unidade normalizado
**O que é:** ao exibir um preço, mostrar preço/kg, preço/L ou preço/unidade para comparar
embalagens diferentes (ex: 1kg de arroz a R$6,50 vs 2×500g a R$3,80 cada).

- **Backend:** nenhuma mudança — `quantity` e `unit` já vêm na `PriceResponse`
- **Frontend:** calcular `unit_price / quantity` e converter `unit` para forma canônica
  (g→kg, ml→L); exibir ao lado do preço total no card de preço
- **Esforço:** ~2h

---

### F2 · Histórico de preços com gráfico
**O que é:** gráfico de linha mostrando a evolução do preço de um produto ao longo do
tempo, por loja.

- **Backend:** endpoint `GET /prices/history` já existe (retorna até 200 registros)
- **Frontend:** adicionar componente de gráfico ao `PriceConsultation.tsx` — uma linha
  por loja, eixo X = data, eixo Y = preço unitário
- **Lib sugerida:** `recharts` (leve, sem dependências pesadas)
- **Esforço:** ~3h

---

### F3 · Inflação pessoal da cesta básica
**O que é:** dado o histórico de compras do usuário, calcular quanto a mesma cesta custava
há 1 mês / 3 meses / 1 ano e comparar com o custo atual.

- **Backend:** nova query — dado uma lista de `product_id`, retornar série temporal de
  preço médio ponderado; novo endpoint `GET /prices/basket?products=...&months=3`
- **Frontend:** nova seção na aba de Preços ou nova aba "Cesta"; seleção de produtos da
  lista existente + gráfico de evolução do custo total
- **Esforço:** ~4h

---

## Fase 2 — Novas queries, sem infraestrutura externa

### F4 · Otimização de lista de compras ⭐
**O que é:** o usuário monta uma lista de produtos e o sistema calcula onde comprar cada
item para minimizar o custo total — melhor mercado único, melhor combinação de 2 mercados.

- **Backend:**
  - Novo repositório: `get_prices_matrix(product_ids, db)` — aggregate MongoDB para
    obter último preço de cada produto por loja
  - Novo endpoint: `POST /shopping-list/optimize`
  - Algoritmo (puro Python, sem lib externa):
    - Melhor mercado único: soma de preços naquele mercado para os produtos disponíveis
    - Melhor par de mercados: testa todas as combinações C(K,2) — rápido para K < 20 lojas
  - Retorna: matriz de preços + recomendação de mercado(s) + economia estimada
- **Frontend:**
  - Nova aba "Lista" no `App.tsx`
  - Novo componente `ShoppingList.tsx`: busca e adiciona produtos, exibe tabela
    produto × loja com células de preço, destaca mínimos, mostra resumo de otimização
- **Esforço:** ~5h

---

### F5 · Ranking de mercados por categoria
**O que é:** mostrar quais mercados têm os melhores preços em categorias como laticínios,
carnes, bebidas — gerado automaticamente a partir dos dados do banco.

- **Backend:** nova query — agrupar produtos por categoria (prefixo do `normalized_name`
  ou campo novo), calcular preço médio por mercado; endpoint `GET /stores/ranking`
- **Frontend:** nova seção "Mercados" com cards de ranking por categoria
- **Esforço:** ~4h

---

### F6 · Lista de compras recorrente
**O que é:** salvar listas nomeadas de produtos para reutilizar nas próximas compras (ex:
"Compra mensal", "Compra semanal").

- **Backend:** nenhuma mudança necessária para MVP — listas ficam no localStorage
- **Frontend:** adicionar gestão de listas salvas ao componente `ShoppingList.tsx` (F4)
  — criar, renomear, deletar, carregar lista salva; persistir em `localStorage`
- **Dependência:** F4
- **Esforço:** ~2h

---

## Fase 3 — Geolocalização

### F7 · Cadastro de localização dos mercados
**O que é:** associar lat/lon a cada mercado (CNPJ) para viabilizar cálculo de distância.

- **Backend:**
  - Nova collection `stores`: `{cnpj, name, lat, lon, address}`
  - Endpoint `PUT /stores/{cnpj}` para salvar/atualizar localização
  - Endpoint `GET /stores` para listar mercados conhecidos
- **Frontend:** ao exibir um mercado desconhecido (sem lat/lon), oferecer botão
  "Registrar localização" que abre campo de endereço ou permite pin no mapa
- **Esforço:** ~4h

---

### F8 · Distância até o mercado
**O que é:** mostrar quantos km o usuário está de cada mercado nos cards de preço.

- **Backend:** nenhuma mudança — retornar lat/lon do mercado junto com os preços
- **Frontend:**
  - Solicitar permissão de geolocalização ao usuário (Geolocation API do browser)
  - Calcular distância via fórmula haversine (puro JS, sem API externa)
  - Exibir distância nos cards de preço e nos resultados de otimização (F4)
- **Dependência:** F7
- **Esforço:** ~2h

---

### F9 · Custo real = preço + deslocamento
**O que é:** somar ao custo da compra o custo estimado do deslocamento (combustível ou
transporte), para comparar mercados com fairness.

- **Backend:** nenhuma mudança
- **Frontend:**
  - Configuração do usuário: custo por km (ex: R$0,70/km de combustível ou R$5,00 de ônibus
    por ida e volta)
  - Recalcular "custo total" = preço dos produtos + 2 × distância × custo_por_km
  - Mostrar breakdown: "Produtos R$X + Deslocamento R$Y = Total R$Z"
- **Dependência:** F7, F8
- **Esforço:** ~2h

---

## Fase 4 — Features avançadas

### F10 · Substituições mais baratas
**O que é:** sugerir alternativas mais baratas para produtos da lista (ex: "Marca própria
do mercado A é 38% mais barata que X, mesma categoria").

- **Backend:** usar `normalized_name` para agrupar produtos similares por categoria;
  endpoint `GET /products/{product_id}/alternatives`
- **Frontend:** exibir sugestões no card de cada produto
- **Complexidade:** média-alta (depende da qualidade da normalização)
- **Esforço:** ~6h

---

### F11 · Alertas de preço
**O que é:** notificar o usuário quando um produto da sua lista baixar abaixo de um preço
alvo.

- **Backend:**
  - Nova collection `alerts`: `{user_id, product_id, target_price}`
  - Job periódico (cron) para checar preços — requer infraestrutura nova (background tasks
    ou scheduler externo)
  - Notificação via e-mail (SendGrid ou similar) ou Web Push
- **Frontend:** interface para criar e gerenciar alertas
- **Complexidade:** alta — requer usuários autenticados, infraestrutura de jobs e
  notificações
- **Esforço:** ~2 semanas

---

## Resumo

| # | Feature | Esforço | Depende de |
|---|---------|---------|------------|
| F1 | Preço por unidade | ~2h | — |
| F2 | Gráfico de histórico | ~3h | — |
| F3 | Inflação da cesta | ~4h | — |
| F4 | Otimização de lista ⭐ | ~5h | — |
| F5 | Ranking de mercados | ~4h | — |
| F6 | Listas recorrentes | ~2h | F4 |
| F7 | Localização dos mercados | ~4h | — |
| F8 | Distância até o mercado | ~2h | F7 |
| F9 | Custo real c/ deslocamento | ~2h | F7, F8 |
| F10 | Substituições baratas | ~6h | — |
| F11 | Alertas de preço | ~2 semanas | infra nova |
