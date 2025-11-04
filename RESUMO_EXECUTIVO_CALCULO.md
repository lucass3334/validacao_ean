# 📊 RESUMO EXECUTIVO - Cálculo de Pedido Automático

**Para:** Gestão de Supply Chain
**Resumo:** Principais regras do sistema de sugestão de compra
**Versão:** 2.0 - Atualizada Janeiro 2025

---

## 🎯 O QUE O SISTEMA FAZ

Calcula automaticamente **quanto comprar** de cada produto baseado em:
- Histórico real de vendas
- Estoque atual
- Políticas do fornecedor
- Regras de segurança contra ruptura

---

## 📐 FÓRMULA PRINCIPAL

```
QUANTIDADE = [(Média diária × Prazo da política) - Estoque atual] × Margem de segurança
            + Ajustes de embalagem
            + Proteções contra ruptura
```

---

## ✅ QUANDO COMPRA

1. **Produto tem demanda comprovada** (histórico de vendas)
2. **Estoque insuficiente** para cobrir o prazo da política
3. **Produto ativo** (vendeu nos últimos 90 dias)

---

## ❌ QUANDO NÃO COMPRA

1. **Produto nunca vendeu** e está sem estoque
2. **Produto parado** há mais de 90 dias (estoque morto)
3. **Estoque atual suficiente** para o prazo

---

## 🛡️ PROTEÇÕES AUTOMÁTICAS

### **1. Margem de Segurança +25%**
**Quando:** Estoque = 0 (zerado)
- Produto completamente sem estoque

**Exemplo:**
- Precisa: 300 unidades
- **Com margem:** 375 unidades
- **Buffer extra:** 7.5 dias de proteção

---

### **2. Arredondamento SEMPRE PARA CIMA**
**Quando:** Produto vendido em caixa
- 1.4 caixas → 2 caixas
- Nunca arredonda para baixo

---

### **3. Proteção de 1 Caixa Mínima**
**Quando:** Produto em caixa com sugestão > 0
- Unidade ≠ UN, UNT
- Garante pelo menos 1 caixa completa

---

## 🎯 SELEÇÃO DE MELHOR POLÍTICA (NOVO!)

**Lógica Atualizada:**
1. Calcula pedido para todas políticas
2. Filtra apenas as que **atingem valor mínimo**
3. Entre as válidas, escolhe maior desconto
4. Marca como "melhor"

**Resultado:** Não marca política inacessível como "melhor"

---

## 📊 EXEMPLO RÁPIDO

**Produto:** Ração 15kg
**Situação:**
- Vende 10 sacos/dia
- Estoque: 5 sacos
- Prazo política: 30 dias

**Cálculo:**
1. **Necessidade:** 10 × 30 = 300 sacos
2. **Descontar estoque:** 300 - 5 = 295 sacos
3. **Dias de cobertura:** 5 ÷ 10 = 0.5 dias (< 3 dias! ⚠️)
4. **Margem de segurança:** 295 × 1.25 = **369 sacos**
5. **Estoque final:** 5 + 369 = 374 sacos = **37.4 dias** ✅

**Proteção contra:**
- Atraso do fornecedor
- Pico de demanda
- Erro de estoque

---

## 🚨 PRINCIPAIS MUDANÇAS (v3.0)

| Aspecto | v2.0 | v3.0 (Atual) | Benefício |
|---------|------|--------------|-----------|
| **Margem 25%** | Dias cobertura < 3 | Apenas estoque = 0 | Alinhado com planilha |
| **Arredondamento** | Baseado em metade | SEMPRE PARA CIMA | Nunca falta produto |
| **Proteção 1 caixa** | Dias cobertura < 3 | Baseado em unidade (CX, PCT) | Mais preciso |
| **Produtos parados** | Descarta > 90 dias | Não descarta | Mantém sazonais |

---

## 📋 CHECKLIST RÁPIDO

**Para validar um pedido gerado:**

✅ Produtos sem demanda foram descartados?
✅ Produtos com estoque = 0 receberam +25%?
✅ Arredondamento foi sempre para CIMA?
✅ Produtos em caixa têm pelo menos 1 caixa?
✅ Descontos aplicados corretamente?
✅ "Melhor política" é atingível?
✅ Valores batem com a planilha manual?

---

## 💡 DICAS DE USO

1. **Produtos novos:** Não aparecem sem histórico de venda
2. **Produtos sazonais:** Média considera todo período desde última compra
3. **Produtos parados:** São automaticamente bloqueados
4. **Embalagens:** Sistema respeita múltiplos da caixa
5. **Políticas:** Apenas as atingíveis são consideradas "melhores"

---

## 📞 PARA SABER MAIS

Consulte o documento completo: **REGRAS_CALCULO_PEDIDO.md**
- Explicação detalhada de todas as regras
- Exemplos passo a passo
- Cenários de validação
- Glossário completo

---

**Documento atualizado:** Janeiro 2025
**Contato:** Equipe de Desenvolvimento
