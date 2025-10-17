# 📋 REGRAS DE CÁLCULO AUTOMÁTICO DE PEDIDO DE COMPRA

**Documento para:** Equipe de Supply Chain
**Objetivo:** Validação e entendimento completo do algoritmo de sugestão de compra
**Versão:** 2.0 (atualizada com melhorias implementadas)
**Data:** Janeiro 2025

---

## 🎯 VISÃO GERAL

O sistema calcula automaticamente quanto comprar de cada produto de um fornecedor, baseado em:
- Histórico de vendas
- Estoque atual
- Políticas comerciais do fornecedor (desconto, prazo, valor mínimo)
- Regras de segurança para evitar ruptura

---

## 📊 FLUXO DO CÁLCULO

### **ETAPA 1: COLETA DE INFORMAÇÕES**

Para cada fornecedor, o sistema busca:

1. **Políticas Comerciais:**
   - Desconto oferecido (ex: 10%)
   - Bonificação (ex: 10%)
   - Valor mínimo do pedido (ex: R$ 500)
   - Prazo de estoque (ex: 30 dias)

2. **Produtos do Fornecedor:**
   - Código do produto
   - Valor de compra unitário
   - Estoque atual
   - Itens por caixa/embalagem

3. **Histórico de Cada Produto:**
   - Data da última venda
   - Data da última compra
   - Quantidade vendida no período

---

### **ETAPA 2: ANÁLISE PRODUTO POR PRODUTO**

Para cada produto, o sistema executa as seguintes verificações:

---

#### **REGRA 1: Produtos Sem Demanda São Descartados**

**Situação A: Produto sem histórico de vendas e sem estoque**
```
SE produto nunca vendeu E estoque = 0
→ DESCARTA produto (sem demanda comprovada)
```

**Exemplo:**
- Produto novo que nunca vendeu
- Estoque = 0
- **Decisão:** Não compra

---

#### **REGRA 2: Produtos Parados Há Muito Tempo São Descartados**

**Situação B: Produto com estoque mas parado há mais de 90 dias**
```
SE estoque > 0 E última venda foi há mais de 90 dias
→ DESCARTA produto (estoque morto)
```

**Exemplo:**
- Estoque atual: 50 unidades
- Última venda: 15/07/2024 (há 150 dias)
- **Decisão:** Não compra (produto parado, libera capital)

**Justificativa:** Evita acumular mais estoque de produtos sem giro.

---

#### **REGRA 3: Produtos com Estoque Recebem Ajuste de Data**

**Situação C: Produto com estoque e vendendo**
```
SE estoque > 0 E última venda foi há menos de 90 dias
→ Sistema ASSUME que vendeu hoje (considera demanda ativa)
```

**Exemplo:**
- Estoque atual: 5 unidades
- Última venda: 10/12/2024 (há 15 dias)
- **Ajuste:** Sistema considera última venda = HOJE
- **Decisão:** Produto tem demanda ativa, continua análise

**Justificativa:** Produto com estoque que ainda vende tem demanda, então pode precisar de reposição.

---

#### **REGRA 4: Ajuste de Datas Inconsistentes**

**Situação D: Data de venda no futuro**
```
SE última venda está no futuro (erro de cadastro)
→ Ajusta para HOJE
```

**Exemplo:**
- Última venda cadastrada: 15/03/2025
- Data atual: 17/01/2025
- **Ajuste:** Última venda = 17/01/2025

---

**Situação E: Data de compra após data de venda (inconsistência)**
```
SE data da última compra >= data da última venda
→ Ajusta data de compra para [prazo da política] dias antes da venda
```

**Exemplo ANTES (problema):**
- Última venda: 15/01/2025
- Última compra: 15/01/2025 (mesmo dia!)
- Período calculado: 1 dia
- Vendeu 100 unidades em 1 dia = 100 un/dia ❌ (média irreal!)

**Exemplo AGORA (corrigido):**
- Última venda: 15/01/2025
- Última compra: 15/01/2025 (mesmo dia!)
- Prazo da política: 30 dias
- **Ajuste:** Última compra = 16/12/2024 (30 dias antes)
- Período calculado: 30 dias
- Vendeu 100 unidades em 30 dias = 3.33 un/dia ✅ (média realista!)

**Justificativa:** Evita médias absurdamente infladas que gerariam pedidos gigantes desnecessários.

---

**Situação F: Sem data de compra (produto muito antigo)**
```
SE não há registro de data de compra
→ Assume compra foi [prazo da política] dias antes da última venda
```

**Exemplo:**
- Última venda: 15/01/2025
- Última compra: SEM REGISTRO
- Prazo da política: 30 dias
- **Assume:** Última compra = 16/12/2024

---

#### **REGRA 5: Cálculo da Média Diária de Vendas**

```
Período de análise = Data última venda - Data última compra
Média diária = Quantidade vendida no período ÷ Período em dias
```

**Exemplo:**
- Última compra: 01/12/2024
- Última venda: 15/01/2025
- Período: 45 dias
- Quantidade vendida: 135 unidades
- **Média diária:** 135 ÷ 45 = **3 unidades/dia**

---

#### **REGRA 6: Cálculo da Sugestão Base**

```
Sugestão base = (Média diária × Prazo de estoque da política) - Estoque atual
```

**Exemplo:**
- Média diária: 3 unidades/dia
- Prazo de estoque: 30 dias (política do fornecedor)
- Estoque atual: 10 unidades
- **Sugestão base:** (3 × 30) - 10 = **80 unidades**

**Interpretação:**
- Precisa de 90 unidades para 30 dias
- Já tem 10 em estoque
- Precisa comprar 80

---

#### **REGRA 7: Margem de Segurança para Risco de Ruptura (25%)**

**NOVA REGRA:** Sistema adiciona 25% a mais quando identifica risco de ruptura.

**Critério 1: Dias de cobertura muito baixos**
```
Dias de cobertura = Estoque atual ÷ Média diária

SE dias de cobertura < 3 dias
→ Adiciona 25% na sugestão
```

**Exemplo 1:**
- Estoque atual: 2 unidades
- Média diária: 10 unidades/dia
- Dias de cobertura: 2 ÷ 10 = **0.2 dias** (menos de 1 dia!)
- Sugestão base: 298 unidades
- **Margem aplicada:** 298 × 1.25 = **372.5 ≈ 373 unidades**
- **Buffer extra:** 7.5 dias de proteção contra atrasos

**Critério 2: Estoque crítico com alta rotação**
```
SE estoque < 2 unidades E média > 0.5 unidades/dia
→ Adiciona 25% na sugestão
```

**Exemplo 2:**
- Estoque atual: 1 unidade
- Média diária: 2 unidades/dia
- Sugestão base: 59 unidades
- **Margem aplicada:** 59 × 1.25 = **73.75 ≈ 74 unidades**

**Justificativa:** Protege contra rupturas causadas por:
- Atrasos na entrega do fornecedor
- Picos inesperados de demanda
- Erros de contagem de estoque

**Quando NÃO aplica:**
- Produto com boa cobertura (≥ 3 dias)
- Produto de baixíssima rotação (≤ 0.5/dia), mesmo com estoque baixo

---

#### **REGRA 8: Arredondamento por Embalagem**

Muitos fornecedores vendem em caixas fechadas.

**Regra de Arredondamento:**
```
Resto = Sugestão ÷ Itens por caixa

SE resto >= metade da caixa
→ Arredonda para CIMA (próxima caixa cheia)

SE resto < metade da caixa
→ Arredonda para BAIXO
   MAS se ficar zero E produto tem demanda
   → Garante pelo menos 1 caixa
```

**Exemplo 1: Arredonda para CIMA**
- Sugestão: 47 unidades
- Itens por caixa: 12
- Resto: 47 ÷ 12 = 3 caixas + sobra de 11 unidades
- Como 11 ≥ 6 (metade de 12)
- **Resultado:** 48 unidades (4 caixas completas)

**Exemplo 2: Arredonda para BAIXO**
- Sugestão: 41 unidades
- Itens por caixa: 12
- Resto: 41 ÷ 12 = 3 caixas + sobra de 5 unidades
- Como 5 < 6 (metade de 12)
- **Resultado:** 36 unidades (3 caixas completas)

**Exemplo 3: Proteção contra zerar produto com demanda**
- Sugestão: 5 unidades
- Itens por caixa: 12
- Resto: 5 ÷ 12 = 0 caixas + sobra de 5
- Arredondaria para 0, MAS produto tem média de 2 unidades/dia
- **Proteção ativada:** Garante 12 unidades (1 caixa)

**Justificativa:** Não descartar produtos com demanda real por questão de arredondamento.

---

#### **REGRA 9: Proteção de Estoque Crítico Dinâmica**

**NOVA REGRA:** Baseada em dias de cobertura, não em unidades fixas.

```
Dias de cobertura do estoque = Estoque atual ÷ Média diária

SE dias de cobertura < 3 dias
→ Garante compra de pelo menos 1 caixa completa
```

**Exemplo 1: Alta rotação com estoque baixo**
- Estoque: 5 unidades
- Média: 10 unidades/dia
- Dias de cobertura: 5 ÷ 10 = **0.5 dias**
- Sugestão após arredondamento: 8 unidades
- Itens por caixa: 12
- **Proteção:** Garante 12 unidades (1 caixa completa)

**Exemplo 2: Baixa rotação com estoque baixo (NÃO aplica)**
- Estoque: 1 unidade
- Média: 0.3 unidades/dia
- Dias de cobertura: 1 ÷ 0.3 = **3.3 dias** (mais de 3!)
- **Não aplica proteção** (produto de baixíssimo giro)

**Justificativa:** Produtos de alta rotação precisam de proteção maior. Produtos de baixa rotação não precisam de compras forçadas.

---

#### **REGRA 10: Cálculo de Valores**

```
Valor total do produto (sem desconto) = Quantidade × Valor unitário
Valor total com desconto = Valor total × (1 - Desconto ÷ 100)
```

**Exemplo:**
- Quantidade sugerida: 100 unidades
- Valor unitário: R$ 2,50
- Desconto: 10%
- **Valor sem desconto:** 100 × 2,50 = **R$ 250,00**
- **Valor com desconto:** 250 × (1 - 10/100) = 250 × 0.90 = **R$ 225,00**

---

### **ETAPA 3: SELEÇÃO DA MELHOR POLÍTICA**

**NOVA LÓGICA:** Sistema escolhe a melhor política APÓS calcular todos os valores.

#### **Antes (problema):**
1. Escolhia "melhor" política por maior desconto
2. Calculava pedido
3. Política "melhor" podia ter valor mínimo inacessível (ex: R$ 10.000)
4. Pedido só atingia R$ 500
5. Usuário via "melhor_politica: false" e ficava confuso

#### **Agora (corrigido):**
1. Calcula pedido para TODAS as políticas
2. Filtra apenas políticas que ATINGIRAM o valor mínimo
3. Entre as políticas válidas, escolhe a melhor por:
   - **1º critério:** Maior desconto
   - **2º critério:** Menor prazo de estoque (em caso de empate)
4. Marca como "melhor_politica: true"

**Exemplo:**

**Política A:**
- Desconto: 15%
- Valor mínimo: R$ 10.000
- Valor do pedido: R$ 450
- **Status:** Excluída (não atingiu mínimo)

**Política B:**
- Desconto: 10%
- Valor mínimo: R$ 300
- Valor do pedido: R$ 450
- **Status:** Incluída ✓

**Política C:**
- Desconto: 8%
- Valor mínimo: R$ 200
- Valor do pedido: R$ 450
- **Status:** Incluída ✓

**Resultado:** Política B marcada como melhor (maior desconto entre as válidas)

**Justificativa:** Não enganar o usuário com políticas inacessíveis.

---

### **ETAPA 4: VALIDAÇÃO FINAL**

```
Para cada política:
  SE valor total do pedido >= valor mínimo da política
  → Política INCLUÍDA no resultado
  SENÃO
  → Política EXCLUÍDA
```

**Exemplo:**
- Valor total calculado: R$ 450,00
- Política A: valor mínimo R$ 300 → ✓ Incluída
- Política B: valor mínimo R$ 500 → ✗ Excluída
- Política C: valor mínimo R$ 200 → ✓ Incluída

---

## 📋 RESUMO DAS REGRAS DE DESCARTE

Um produto é **DESCARTADO** (não entra no pedido) nas seguintes situações:

| # | Situação | Motivo |
|---|----------|--------|
| 1 | Nunca vendeu E estoque = 0 | Sem demanda comprovada |
| 2 | Estoque > 0 E parado há > 90 dias | Estoque morto, sem giro |
| 3 | Sugestão calculada ≤ 0 | Estoque atual já é suficiente |

---

## 📋 RESUMO DAS REGRAS DE PROTEÇÃO

O sistema AUMENTA a compra nas seguintes situações:

| # | Situação | Ação | Motivo |
|---|----------|------|--------|
| 1 | Cobertura < 3 dias | +25% | Risco de ruptura |
| 2 | Estoque < 2 E alta rotação | +25% | Risco de ruptura |
| 3 | Arredondaria para zero com demanda | +1 caixa | Garantir giro |
| 4 | Cobertura < 3 dias após arredondamento | +1 caixa mínimo | Proteção crítica |

---

## 📊 EXEMPLO COMPLETO PASSO A PASSO

### **Produto: Sabonete Líquido**

**Dados do Produto:**
- Código: 47894933040384
- Valor unitário: R$ 2,77
- Estoque atual: 0 unidades
- Itens por caixa: 1
- Última venda: 12/08/2024
- Última compra: 20/08/2024

**Dados da Política:**
- Desconto: 10%
- Prazo de estoque: 30 dias
- Valor mínimo: R$ 10,00

---

**PASSO 1: Verificar se produto deve ser descartado**
- Estoque = 0, mas TEM histórico de vendas ✓
- Última venda há 158 dias (< 90 dias? NÃO)
- ⚠️ Produto parado, mas sem estoque, então continua análise

**PASSO 2: Ajustar datas**
- Última venda: 12/08/2024
- Última compra: 20/08/2024 (DEPOIS da venda! Inconsistência!)
- **Ajuste:** Última compra = 12/08/2024 - 30 dias = 13/07/2024

**PASSO 3: Calcular período e média**
- Período: 12/08/2024 - 13/07/2024 = 30 dias
- Quantidade vendida: 20 unidades
- **Média diária:** 20 ÷ 30 = **0.67 unidades/dia**

**PASSO 4: Calcular sugestão base**
- Média: 0.67 un/dia
- Prazo: 30 dias
- Estoque: 0
- **Sugestão base:** (0.67 × 30) - 0 = **20 unidades**

**PASSO 5: Verificar margem de segurança**
- Dias de cobertura: 0 ÷ 0.67 = **0 dias** (< 3 dias!)
- Estoque < 2? SIM (0 < 2)
- Média > 0.5? SIM (0.67 > 0.5)
- **Aplica margem:** 20 × 1.25 = **25 unidades**

**PASSO 6: Arredondar por embalagem**
- Itens por caixa: 1
- **Arredondamento:** 25 unidades (sem ajuste)

**PASSO 7: Verificar estoque crítico**
- Dias de cobertura: 0 dias (< 3 dias!)
- **Proteção ativada:** max(25, 1) = **25 unidades**

**PASSO 8: Calcular valores**
- Quantidade final: 25 unidades
- Valor unitário: R$ 2,77
- **Valor sem desconto:** 25 × 2,77 = **R$ 69,25**
- **Valor com desconto:** 69,25 × 0,90 = **R$ 62,33**

**RESULTADO FINAL:**
- ✅ Produto INCLUÍDO no pedido
- Quantidade: 25 unidades
- Valor: R$ 62,33 (com desconto)

---

## 🎯 CENÁRIOS DE VALIDAÇÃO

### **Cenário 1: Produto de Alta Rotação com Estoque Baixo**

**Situação:**
- Vende 50 unidades/dia
- Estoque atual: 10 unidades
- Prazo: 30 dias

**Cálculo:**
1. Dias de cobertura: 10 ÷ 50 = **0.2 dias** (< 3!)
2. Sugestão base: (50 × 30) - 10 = **1.490 unidades**
3. **Margem 25%:** 1.490 × 1.25 = **1.862.5 ≈ 1.863 unidades**
4. Estoque final: 10 + 1.863 = 1.873 unidades = **37.5 dias** (incluindo buffer)

**Resultado:** Protegido contra ruptura com 7.5 dias extras.

---

### **Cenário 2: Produto de Baixa Rotação com Estoque Baixo**

**Situação:**
- Vende 0.2 unidades/dia
- Estoque atual: 1 unidade
- Prazo: 30 dias

**Cálculo:**
1. Dias de cobertura: 1 ÷ 0.2 = **5 dias** (≥ 3)
2. Sugestão base: (0.2 × 30) - 1 = **5 unidades**
3. **NÃO aplica margem** (cobertura ok)
4. Estoque < 2? SIM, mas média ≤ 0.5, **NÃO aplica proteção crítica**

**Resultado:** Não força compra desnecessária de produto de baixo giro.

---

### **Cenário 3: Produto Parado com Estoque**

**Situação:**
- Estoque: 100 unidades
- Última venda: 01/07/2024 (há 200 dias)

**Cálculo:**
1. Estoque > 0? SIM
2. Parado há > 90 dias? SIM (200 dias)
3. **DESCARTA produto**

**Resultado:** Não compra estoque morto.

---

### **Cenário 4: Produto com Caixa Grande e Sugestão Pequena**

**Situação:**
- Sugestão: 7 unidades
- Itens por caixa: 12
- Média: 1 unidade/dia

**Cálculo:**
1. Resto: 7 ÷ 12 = 0 caixas + 7
2. 7 < 6 (metade) → Arredondaria para 0
3. Mas média > 0 (produto tem demanda!)
4. **Proteção:** Garante 12 unidades (1 caixa)

**Resultado:** Produto continua no mix, evita perder vendas.

---

## ✅ CHECKLIST PARA VALIDAÇÃO

Use este checklist para validar se o cálculo está correto:

### **Dados de Entrada**
- [ ] Período de venda está correto? (data_venda - data_compra)
- [ ] Período NÃO está muito curto? (mínimo 1 dia, ideal > 7 dias)
- [ ] Média diária faz sentido? (quantidade_vendida ÷ período)
- [ ] Estoque atual está atualizado?

### **Regras de Descarte**
- [ ] Produto sem venda e sem estoque foi descartado?
- [ ] Produto parado > 90 dias foi descartado?
- [ ] Produto com sugestão ≤ 0 foi descartado?

### **Regras de Proteção**
- [ ] Produto com cobertura < 3 dias recebeu +25%?
- [ ] Produto com estoque < 2 e alta rotação recebeu +25%?
- [ ] Arredondamento não zerou produto com demanda?
- [ ] Produto crítico garantiu pelo menos 1 caixa?

### **Valores**
- [ ] Desconto foi aplicado corretamente? (valor × 0.90 para 10%)
- [ ] Valor total do pedido bate com soma dos produtos?
- [ ] Política incluída atingiu valor mínimo?

### **Melhor Política**
- [ ] "Melhor política" está entre as que ATINGIRAM valor mínimo?
- [ ] Tem o maior desconto entre as válidas?
- [ ] Apenas UMA política está marcada como "melhor"?

---

## 📞 DÚVIDAS FREQUENTES

**1. Por que alguns produtos não aparecem no pedido?**

Pode ser por 3 motivos:
- Nunca venderam e estão sem estoque
- Estão parados há mais de 90 dias
- Estoque atual já é suficiente para o prazo

**2. Por que a quantidade sugerida é maior que o normal?**

Pode ser por 3 motivos:
- Margem de segurança de 25% aplicada (produto em risco de ruptura)
- Arredondamento de embalagem para cima
- Proteção de estoque crítico ativada

**3. Por que a "melhor política" não é a de maior desconto?**

Porque a de maior desconto pode ter valor mínimo inacessível. O sistema só marca como "melhor" políticas que você consegue aproveitar.

**4. Por que o período de venda às vezes muda?**

Para corrigir inconsistências:
- Datas no futuro são ajustadas para hoje
- Data de compra após venda é recalculada
- Produtos com estoque assumem venda recente

**5. Como o sistema evita comprar demais de produtos parados?**

Produtos com estoque e sem venda há mais de 90 dias são automaticamente descartados.

---

## 📊 GLOSSÁRIO

| Termo | Significado |
|-------|-------------|
| **Dias de cobertura** | Quantos dias o estoque atual dura baseado na média de venda |
| **Margem de segurança** | Percentual extra (25%) adicionado para produtos em risco |
| **Prazo de estoque** | Quantos dias de estoque a política do fornecedor exige manter |
| **Valor mínimo** | Menor valor de pedido aceito pelo fornecedor para conceder desconto |
| **Produto parado** | Produto com estoque mas sem vendas há mais de 90 dias |
| **Estoque crítico** | Produto com cobertura menor que 3 dias |

---

## 📅 HISTÓRICO DE ATUALIZAÇÕES

**Versão 2.0 - Janeiro 2025**
- ✅ Adicionada margem de segurança de 25% para risco de ruptura
- ✅ Estoque crítico agora é dinâmico (baseado em cobertura, não fixo)
- ✅ Arredondamento inteligente garante produtos com demanda
- ✅ Ajuste de data usa prazo da política (não mais 1 dia fixo)
- ✅ Detecção e descarte de produtos parados (> 90 dias)
- ✅ Melhor política escolhida apenas entre as atingíveis

**Versão 1.0 - Dezembro 2024**
- Versão inicial do algoritmo

---

**Documento preparado para validação da equipe de Supply Chain**
**Para dúvidas técnicas, consultar a equipe de desenvolvimento**
