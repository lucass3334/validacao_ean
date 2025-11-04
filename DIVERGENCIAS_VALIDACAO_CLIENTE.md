# 📊 ANÁLISE DE DIVERGÊNCIAS - Sistema de Cálculo de Pedido

**Data:** 20 de Outubro de 2025
**Objetivo:** Validação de regras de negócio entre Planilha Manual e Sistema Automatizado
**Status:** Aguardando Decisão da Cliente

---

## 🎯 RESUMO EXECUTIVO

Este documento apresenta as **diferenças identificadas** entre a planilha de cálculo manual enviada pela cliente e o sistema automatizado atual.

**Importante:** Muitas das regras implementadas no sistema atual são **melhorias de segurança e proteção** que podem não estar visíveis na planilha, mas que protegem o negócio contra rupturas de estoque e compras desnecessárias.

---

## 📋 DIVERGÊNCIAS IDENTIFICADAS

### **DIVERGÊNCIA 1: Período de Cálculo da Média de Vendas**
🔴 **CRÍTICA - Impacto: Alto**

| Aspecto | Planilha da Cliente | Sistema Atual |
|---------|---------------------|---------------|
| **Período usado** | HOJE - Data última compra | Data última venda - Data última compra |
| **Exemplo 1 (Ração X)** | 19/10/2025 - 19/08/2025 = **61 dias** | 19/10/2025 (ajustado) - 19/08/2025 = **61 dias** ✅ |
| **Exemplo 2 (Ração Y)** | 19/10/2025 - 19/08/2025 = **61 dias** | 19/10/2025 - 19/08/2025 = **61 dias** ✅ |
| **Com estoque zerado e última venda antiga** | HOJE - última compra = período maior | Última venda (real) - última compra = período menor ⚠️ |

#### **Exemplo de Impacto:**

**Cenário:** Produto parou de vender há 30 dias
- Última compra: 01/09/2025
- Última venda: 20/09/2025 (há 30 dias)
- Vendeu: 60 unidades
- Estoque atual: 0

**Planilha da Cliente:**
```
Período = 20/10/2025 - 01/09/2025 = 49 dias
Média = 60 ÷ 49 = 1.22 un/dia
Sugestão (30 dias) = 1.22 × 30 = 36.7 unidades
```

**Sistema Atual:**
```
Período = 20/09/2025 - 01/09/2025 = 19 dias
Média = 60 ÷ 19 = 3.15 un/dia
Sugestão (30 dias) = 3.15 × 30 = 94.7 unidades
```

**Diferença:** Sistema sugere **158% a mais** (94 vs 36 unidades)

#### **Decisão Necessária:**

- [ ] **Opção A:** Manter planilha (sempre usar HOJE como referência)
  - ✅ Mais conservador em produtos parados
  - ❌ Pode gerar ruptura em produtos com demanda sazonal

- [ ] **Opção B:** Manter sistema atual (usar data real da última venda)
  - ✅ Mais preciso em produtos ativos
  - ❌ Pode superestimar produtos que pararam de vender

- [ ] **Opção C:** Híbrido - usar HOJE se produto vendeu nos últimos X dias, senão usar data real
  - ✅ Equilibra segurança e precisão
  - ⚠️ Adiciona complexidade

---

### **DIVERGÊNCIA 2: Margem de Segurança 25%**
🔴 **CRÍTICA - Impacto: Alto**

| Aspecto | Planilha da Cliente | Sistema Atual |
|---------|---------------------|---------------|
| **Quando aplica** | Apenas quando estoque = 0 | Quando dias_cobertura < 3 **OU** estoque < 2 com alta rotação |
| **Exemplo 1 (Estoque = X)** | NÃO aplica ❌ | Depende dos dias de cobertura |
| **Exemplo 2 (Estoque = 0)** | Aplica 25% ✅ | Aplica 25% ✅ |

#### **Exemplo de Impacto:**

**Cenário 1:** Produto de alta rotação com estoque baixo
- Estoque atual: 5 unidades
- Média: 10 unidades/dia
- Dias de cobertura: 5 ÷ 10 = **0.5 dias** (meio dia de estoque!)
- Sugestão base: 295 unidades

**Planilha da Cliente:**
```
Estoque > 0 → NÃO aplica margem
Sugestão = 295 unidades
```

**Sistema Atual:**
```
Dias cobertura (0.5) < 3 → APLICA margem 25%
Sugestão = 295 × 1.25 = 368 unidades
```

**Diferença:** Sistema sugere **25% a mais** (368 vs 295 unidades)

**Cenário 2:** Produto de baixa rotação com estoque zerado
- Estoque atual: 0 unidades
- Média: 0.3 unidades/dia
- Sugestão base: 9 unidades

**Planilha da Cliente:**
```
Estoque = 0 → APLICA margem 25%
Sugestão = 9 × 1.25 = 11.25 unidades
```

**Sistema Atual:**
```
Estoque = 0 (mas média baixa 0.3 < 0.5)
Se dias_cobertura < 3 → APLICA margem
Sugestão = 11.25 unidades
```

**Ambos chegam no mesmo resultado neste caso.**

#### **Decisão Necessária:**

- [ ] **Opção A:** Manter planilha (aplicar 25% APENAS se estoque = 0)
  - ✅ Regra simples e clara
  - ❌ Não protege produtos de alta rotação com estoque baixo
  - ⚠️ **Risco de ruptura em produtos críticos**

- [ ] **Opção B:** Manter sistema atual (aplicar 25% baseado em dias de cobertura)
  - ✅ Protege contra rupturas de estoque
  - ✅ Adapta-se ao giro do produto
  - ❌ Pode comprar mais que o esperado pela planilha

- [ ] **Opção C:** Híbrido - aplicar 25% se (estoque = 0 OU dias_cobertura < 1 dia)
  - ✅ Protege casos extremos
  - ⚠️ Adiciona complexidade moderada

---

### **DIVERGÊNCIA 3: Proteção de Estoque Crítico**
🟡 **MÉDIA - Impacto: Médio**

| Aspecto | Planilha da Cliente | Sistema Atual |
|---------|---------------------|---------------|
| **Regra** | Não menciona | Garante pelo menos 1 caixa se dias_cobertura < 3 |

#### **Descrição da Regra do Sistema:**

Após calcular a sugestão e arredondar por embalagem, o sistema **garante pelo menos 1 caixa completa** se:
- Dias de cobertura < 3 dias **E**
- Sugestão arredondada > 0

#### **Exemplo de Impacto:**

**Cenário:** Produto com caixa grande e sugestão pequena
- Estoque atual: 5 unidades
- Média: 10 unidades/dia
- Dias de cobertura: 0.5 dias
- Sugestão calculada: 295 unidades
- Sugestão com margem: 368 unidades
- Itens por caixa: 12
- Arredondamento: 368 ÷ 12 = 30 caixas + 8 unidades → **30 caixas = 360 unidades**

**Sistema Atual:**
```
Dias cobertura (0.5) < 3 → Garante mínimo 1 caixa
max(360, 12) = 360 unidades (já é maior que 1 caixa)
```

Neste caso não muda nada, mas protege cenários extremos.

**Cenário 2:** Arredondamento zeraria o produto
- Sugestão: 5 unidades
- Itens por caixa: 12
- Arredondamento normal: 0 caixas (5 < 6, que é metade de 12)
- Média: 2 unidades/dia (produto tem demanda!)

**Sistema Atual:**
```
Arredondamento resultaria em 0, MAS produto tem demanda (média > 0)
→ Força compra de 1 caixa = 12 unidades
```

#### **Decisão Necessária:**

- [ ] **Opção A:** Remover proteção (seguir apenas arredondamento matemático)
  - ✅ Mais simples
  - ❌ Pode zerar produtos com demanda real
  - ⚠️ **Risco de perder vendas**

- [ ] **Opção B:** Manter proteção (garante 1 caixa mínima)
  - ✅ Evita perder vendas por arredondamento
  - ✅ Protege produtos de alta rotação
  - ❌ Pode comprar mais que planilha sugere

---

### **DIVERGÊNCIA 4: Descarte de Produtos Parados (> 90 dias)**
🟡 **MÉDIA - Impacto: Médio**

| Aspecto | Planilha da Cliente | Sistema Atual |
|---------|---------------------|---------------|
| **Regra** | Não menciona | Produtos parados > 90 dias são descartados |

#### **Descrição da Regra do Sistema:**

Se produto tem:
- Estoque > 0 **E**
- Última venda foi há mais de 90 dias

Então: **Produto é descartado do pedido** (não compra mais)

#### **Exemplo de Impacto:**

**Cenário:** Produto sazonal
- Estoque atual: 50 unidades
- Última venda: 15/07/2025 (há 97 dias)
- Produto sazonal que vende só no verão

**Sistema Atual:**
```
97 dias > 90 dias → DESCARTA produto
Não entra no pedido
```

**Justificativa da Regra:**
- Evita acumular mais estoque de produtos sem giro
- Libera capital de giro
- Reduz estoque morto

#### **Decisão Necessária:**

- [ ] **Opção A:** Remover regra (comprar mesmo se parado > 90 dias)
  - ✅ Mantém produtos sazonais no mix
  - ❌ Risco de acumular estoque morto

- [ ] **Opção B:** Manter regra (descartar se parado > 90 dias)
  - ✅ Reduz estoque morto
  - ✅ Libera capital de giro
  - ❌ Pode descartar produtos sazonais válidos

- [ ] **Opção C:** Ajustar prazo (ex: 120 ou 180 dias)
  - ✅ Mais flexível para sazonais
  - ⚠️ Requer definição do prazo ideal

---

### **DIVERGÊNCIA 5: Ajuste de Data de Compra Inconsistente**
🟢 **BAIXA - Impacto: Baixo**

| Aspecto | Planilha da Cliente | Sistema Atual |
|---------|---------------------|---------------|
| **Quando data compra >= data venda** | Não menciona | Ajusta usando prazo da política (30 dias) |

#### **Descrição da Regra do Sistema:**

Se:
- Data última compra >= Data última venda (inconsistência!)

Então: `data_compra_ajustada = data_venda - prazo_politica`

#### **Exemplo de Impacto:**

**Cenário:** Dados inconsistentes (compra no mesmo dia da venda)
- Última venda: 15/01/2025
- Última compra: 15/01/2025 (mesmo dia!)
- Vendeu: 100 unidades
- Prazo da política: 30 dias

**Sem ajuste:**
```
Período = 15/01 - 15/01 = 0 dias (ou 1 dia mínimo)
Média = 100 ÷ 1 = 100 unidades/dia ❌ (média absurda!)
Sugestão = 100 × 30 = 3.000 unidades ❌❌❌
```

**Sistema Atual (com ajuste):**
```
Data compra ajustada = 15/01 - 30 dias = 16/12/2024
Período = 15/01 - 16/12 = 30 dias
Média = 100 ÷ 30 = 3.33 unidades/dia ✅
Sugestão = 3.33 × 30 = 100 unidades ✅
```

#### **Decisão Necessária:**

- [ ] **Opção A:** Remover ajuste (usar dados como estão)
  - ❌ Médias absurdas em dados inconsistentes
  - ❌ Pedidos gigantescos desnecessários

- [ ] **Opção B:** Manter ajuste (corrigir inconsistências)
  - ✅ Evita médias irreais
  - ✅ Protege contra erros de cadastro
  - **👍 RECOMENDADO**

---

## 🎯 TESTE COM EXEMPLOS DA PLANILHA

### **Exemplo 1: Estoque Positivo (Ração X)**

**Dados:**
- Estoque atual: informado (assumindo > 0)
- Data HOJE: 19/10/2025
- Data última compra: 19/08/2025
- Quantidade vendida: 9 unidades
- Prazo: 30 dias

**Planilha da Cliente:**
```
Período = 61 dias
Média = 9 ÷ 61 = 0,147540984 un/dia
Sugestão = (0,147540984 × 30) - estoque = 4,426229508 - estoque
SEM margem de 25% (estoque > 0)
```

**Sistema Atual:**
```
Se estoque > 0: ajusta data_venda para HOJE
Período = 19/10/2025 - 19/08/2025 = 61 dias ✅
Média = 9 ÷ 61 = 0,147540984 un/dia ✅
Sugestão base = (0,147540984 × 30) - estoque

Se dias_cobertura < 3: APLICA margem 25% ⚠️
(Depende do valor do estoque atual)
```

**Alinhamento:** ✅ Período OK | ⚠️ Margem pode divergir

---

### **Exemplo 2: Estoque Zerado (Ração Y)**

**Dados:**
- Estoque atual: 0
- Data última venda: 19/10/2025
- Data última compra: 19/08/2025
- Quantidade vendida: 10 unidades
- Prazo: 30 dias

**Planilha da Cliente:**
```
Período = 61 dias
Média = 10 ÷ 61 = 0,163934426 un/dia
Sugestão base = (0,163934426 × 30) = 4,918032787
COM margem de 25% (estoque = 0)
Sugestão final = 4,918032787 × 1,25 = 6,147540984 unidades
```

**Sistema Atual:**
```
Estoque = 0 (sem ajuste de data, usa data real da venda)
Período = 19/10/2025 - 19/08/2025 = 61 dias ✅
Média = 10 ÷ 61 = 0,163934426 un/dia ✅
Sugestão base = 0,163934426 × 30 = 4,918032787 ✅

Verifica margem:
- Estoque = 0 → dias_cobertura = 0 (< 3) ✅
- APLICA margem 25% ✅
Sugestão = 4,918032787 × 1,25 = 6,147540984 ✅
```

**Alinhamento:** ✅ Totalmente alinhado neste caso!

---

## 📊 MATRIZ DE DECISÃO

| Divergência | Impacto | Recomendação Técnica | Prioridade |
|-------------|---------|----------------------|------------|
| **1. Período de Cálculo** | 🔴 Alto | Manter sistema atual ou híbrido | Alta |
| **2. Margem 25%** | 🔴 Alto | Manter sistema atual (dias cobertura) | Alta |
| **3. Estoque Crítico** | 🟡 Médio | Manter (protege vendas) | Média |
| **4. Produtos Parados** | 🟡 Médio | Manter (reduz estoque morto) | Média |
| **5. Ajuste de Datas** | 🟢 Baixo | Manter (corrige erros) | Baixa |

---

## 🎓 RECOMENDAÇÕES TÉCNICAS

### **Divergência 1: Período de Cálculo**
**Recomendação:** Manter sistema atual ou implementar lógica híbrida

**Justificativa:**
- Sistema atual é mais preciso para produtos ativos
- Usar sempre HOJE pode superestimar produtos que pararam de vender
- **Sugestão:** Adicionar flag de controle para cliente escolher comportamento

### **Divergência 2: Margem de Segurança**
**Recomendação:** Manter sistema atual (baseado em dias de cobertura)

**Justificativa:**
- Protege produtos de alta rotação contra ruptura
- Mais inteligente que regra binária (estoque = 0)
- Adapta-se ao perfil de giro do produto
- **Risco:** Sem essa proteção, produtos críticos podem faltar

### **Divergência 3: Estoque Crítico**
**Recomendação:** Manter proteção

**Justificativa:**
- Evita zerar produtos com demanda por questão de arredondamento
- Impacto financeiro baixo (1 caixa)
- Evita perda de vendas

### **Divergência 4: Produtos Parados**
**Recomendação:** Manter com possibilidade de ajuste do prazo

**Justificativa:**
- Reduz estoque morto
- Libera capital de giro
- **Sugestão:** Tornar prazo configurável (90, 120 ou 180 dias)

### **Divergência 5: Ajuste de Datas**
**Recomendação:** Manter

**Justificativa:**
- Proteção contra dados inconsistentes
- Evita pedidos absurdos
- Sem impacto negativo em dados corretos

---

## ✅ FORMULÁRIO DE DECISÃO

Preencha as decisões para cada divergência:

### **1. Período de Cálculo**
- [ ] Mudar para regra da planilha (sempre HOJE - data compra)
- [ ] Manter sistema atual (data venda - data compra)
- [ ] Implementar híbrido (com prazo de X dias)
- **Prazo se híbrido:** _____ dias

### **2. Margem de Segurança 25%**
- [ ] Mudar para regra da planilha (aplicar APENAS se estoque = 0)
- [ ] Manter sistema atual (aplicar se dias_cobertura < 3)
- [ ] Implementar híbrido (estoque = 0 OU dias_cobertura < X)
- **Dias se híbrido:** _____ dias

### **3. Proteção de Estoque Crítico**
- [ ] Remover proteção
- [ ] Manter proteção (garante 1 caixa mínima)

### **4. Produtos Parados > 90 dias**
- [ ] Remover regra (comprar mesmo se parado)
- [ ] Manter regra atual (90 dias)
- [ ] Ajustar prazo para: _____ dias

### **5. Ajuste de Datas Inconsistentes**
- [ ] Remover ajuste
- [ ] Manter ajuste

---

## 📝 OBSERVAÇÕES ADICIONAIS

**Espaço para comentários da cliente:**

```
[Insira aqui quaisquer observações, dúvidas ou requisitos adicionais]





```

---

## 🚀 PRÓXIMOS PASSOS

1. Cliente preenche formulário de decisão
2. Equipe técnica implementa ajustes aprovados
3. Atualização da documentação
4. Testes com exemplos da planilha
5. Deploy em ambiente de produção

---

**Documento preparado por:** Equipe de Desenvolvimento
**Data:** 20/10/2025
**Versão:** 1.0