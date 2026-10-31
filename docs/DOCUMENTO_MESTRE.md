# SIAP-IA — Documento Mestre v1.1

**Versão 1.1 · 31/10/2026 · Escopo: uso pessoal e não comercial**
Substitui a v1.0 (Word). Consolida decisões e requisitos. Este documento não comprova a situação regulatória de nenhum instrumento e não substitui verificação normativa atualizada.

## O que mudou da v1.0 para a v1.1
| Tema | v1.0 | v1.1 |
|---|---|---|
| Escopo | 10 módulos / 10 fases | **MVP em 4 etapas**; demais módulos após o MVP |
| Aprendizado de máquina | Módulo 04 | **Retirado** |
| Laboratório psicométrico | Único módulo | **Separado**: registro de resultados clínicos (Etapa 3) × estatística de pesquisa (pós-MVP) |
| Execução | Local (Streamlit + SQLite) | **Nuvem**: Streamlit Community Cloud + PostgreSQL (Neon); SQLite só em testes |
| Identificação | Dados sensíveis protegidos | **Sem identificação direta** de avaliandos: apenas códigos |
| SATEPSI | Verificação assistida | Assistida **com evidência obrigatória para favorável e validade** (padrão 90 dias) |
| Documento Mestre | Arquivo Word fora do código | Markdown versionado no repositório + `CLAUDE.md` |

## 1. Visão e escopo
SIAP-IA: apoio ao trabalho de avaliação psicológica em psicodiagnóstico adulto e infantil, seleção e treinamento, trânsito e porte de arma de fogo, e pesquisa. Integra catálogo de instrumentos, conformidade SATEPSI, gestão de avaliações, documentos psicológicos e, depois do MVP, consultoria por IA, análise qualitativa, dashboards e estatística de pesquisa.

## 2. Princípios
1. A IA auxilia; não decide aptidão, diagnóstico, afastamento ou emissão de documento.
2. Nenhum avaliando é identificado diretamente: o sistema usa códigos. A correspondência código↔pessoa fica fora do sistema.
3. Não se implementam itens, estímulos, manuais, normas ou chaves de correção protegidos. Resultados clínicos são **registrados** a partir das fontes oficiais.
4. Cálculos estatísticos vêm de rotinas testadas e reprodutíveis. A IA nunca cria números.
5. Rastreabilidade: auditoria somente de inclusão; histórico SATEPSI imutável.
6. Desenvolvimento e testes apenas com dados sintéticos.

## 3. Arquitetura
- **Aplicação:** Python 3.12 + Streamlit (multipáginas), regras de negócio no pacote `siap/`, independentes da interface.
- **Dados:** SQLAlchemy 2. PostgreSQL (Neon) em produção, SQLite em testes. Migrações com Alembic quando o esquema mudar.
- **Acesso:** app privado no Streamlit Cloud + senha própria (`APP_PASSWORD`).
- **Qualidade:** pytest + GitHub Actions a cada envio.
- **Futuro:** API do Claude com texto pseudonimizado (consultor/redação), `docxtpl` para documentos, R via `Rscript` para psicometria avançada.

## 4. Plano de implementação
| Etapa | Entrega | Situação |
|---|---|---|
| 1. Base | Repositório, app, banco, auditoria, testes, CI, implantação em nuvem | ✅ concluída |
| 2. Catálogo + SATEPSI | Instrumentos/versões, verificação com evidência e validade, bloqueio, backup | ✅ concluída |
| 3. Avaliações | Caso codificado, finalidade/contexto, entrevistas e observações, instrumentos aplicados (somente versões elegíveis para a finalidade), resultados registrados | próxima |
| 4. Documentos | Laudo e atestado (Res. CFP 06/2019), relatório, declaração e parecer; rascunho → revisado → aprovado → emitido; exportação Word/PDF; hash | — |
| Pós-MVP A | Consultor IA metodológico e de redação; análise qualitativa (codificação, matrizes, evidências) | — |
| Pós-MVP B | Dashboards | — |
| Pós-MVP C | Estatística de pesquisa: descritivas, TCT, precisão, AFE/AFC, TRI, normas de estudos próprios | — |

## 5. Inventário inicial (candidatos, todos "não verificado")
| Categoria | Instrumentos |
|---|---|
| Personalidade / expressivos | Pirâmides Coloridas de Pfister; Zulliger; Palográfico |
| Atenção | BPA; AC; TEACO-FF; TEADI; TEALT; d2 e d2-R (versões independentes) |
| Inteligência / raciocínio | R-1; G-36; G-38 |
| Memória | TEM-R; TEPIC-M |

"Teste dos Traços" e "TR" saíram do inventário por falta de identificação. Podem ser cadastrados pelo próprio sistema quando o nome exato for lembrado.

## 6. Política SATEPSI (implementada)
- A situação é avaliada **por versão**. A verificação que vale é a de data de consulta mais recente.
- **Elegível** somente se: situação favorável **e** consulta dentro da validade **e** evidência anexada.
- **Bloqueado** se: sem verificação; desfavorável; restrito/com condições; em avaliação; não localizado; verificação vencida; data inconsistente.
- Verificações nunca são editadas ou apagadas. Corrigir significa registrar nova consulta.
- O bloqueio não apaga dados nem altera documentos já emitidos. Situações anteriores exigem análise profissional.
- Não se presume API pública do SATEPSI.
- Etapa 3: a liberação passará a considerar também a finalidade da avaliação diante das condições registradas.

## 7. Documentação psicológica (Etapa 4)
Fluxo: selecionar avaliação → reunir evidências pertinentes → rascunho → checagem de consistência e requisitos → revisão e aprovação profissional → exportar Word/PDF → arquivar com hash. Adequar à Resolução CFP 06/2019 e às normas vigentes, conferidas antes do uso real. Inclui o prazo de guarda documental exigido pelo CFP.

## 8. Critérios de aceitação
| Critério | Situação |
|---|---|
| Cadastro persiste após reinício e suporta várias versões do mesmo instrumento | ✅ testado |
| Teste desfavorável, não verificado ou vencido não é liberado | ✅ testado |
| Toda alteração gera auditoria; histórico SATEPSI preservado | ✅ testado |
| Backup integral exportável | ✅ testado (restauração automatizada: pendente) |
| Resultados psicométricos reproduzem bases de referência | pós-MVP C |
| IA não cria valores numéricos e distingue cálculo de interpretação | pós-MVP A |
| Documentos permanecem rascunho até aprovação | Etapa 4 |
| Nenhum dado de identificação direta é coletado | regra de projeto (CLAUDE.md) |

## 9. Pendências
- Usuário: conferir no SATEPSI cada versão do inventário e registrar no sistema.
- Usuário: implantar seguindo `docs/IMPLANTACAO.md`.
- Técnica: restauração de backup; Alembic antes da Etapa 3; extensão da regra para finalidade.

## Referências
SATEPSI: <https://satepsi.cfp.org.br/> · CFP: <https://site.cfp.org.br/> · LGPD: Lei nº 13.709/2018 (consultar texto oficial atualizado).
